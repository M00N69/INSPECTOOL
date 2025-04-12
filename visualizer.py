# visualizer_app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import zipfile
import io
import json
import base64
from PIL import Image, UnidentifiedImageError # Importer aussi UnidentifiedImageError
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union # Type Hinting

# --- Configuration de la Page Streamlit ---
st.set_page_config(
    page_title="Visualiseur d'Inspections",
    page_icon="📊",
    layout="wide",  # Utiliser toute la largeur de la page
    initial_sidebar_state="expanded" # Garder la sidebar ouverte par défaut
)

# --- Constantes ---
ITEMS_PER_PAGE_AGGREGATED = 50 # Nombre d'éléments par page dans la vue agrégée

# --- Initialisation de l'État de Session ---
# Utilisation d'un dictionnaire pour définir les valeurs par défaut
default_session_state = {
    'loaded_inspections': [], # List[Dict[str, Union[Dict, str]]] -> { "inspection": {...}, "model": {...}, "filename": "..." }
    'corrective_actions': {}, # Dict[Tuple[str, str], Dict[str, str]] -> {(insp_id, point_id): {'status': '...', 'note': ''}}
    'selected_inspection_id_for_detail': None, # Optional[str]
    'show_detail_dialog': False, # bool
    'export_data_prepared': None, # Optional[bytes]
    'export_filename': "", # str
    'show_photo_modal': False, # bool
    'modal_photo_list': [], # List[str] (base64 strings)
    'modal_photo_index': 0, # int
    'modal_photo_caption': "", # str
    'aggregated_page_number': 1, # int
    # 'confirm_clear_all': False # Optionnel: pour une confirmation de suppression en 2 étapes
}

# Initialiser chaque clé si elle n'existe pas déjà dans st.session_state
for key, default_value in default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- Fonctions Utilitaires ---

def is_point_of_interest(result_data: Optional[Dict], point_model: Optional[Dict]) -> bool:
    """
    Vérifie si un point de contrôle est considéré comme 'd'intérêt'
    (Non Conforme ou Hors Plage Numérique).

    Args:
        result_data: Dictionnaire contenant les résultats du point.
        point_model: Dictionnaire contenant la définition du point depuis le modèle.

    Returns:
        True si le point est d'intérêt, False sinon.
    """
    if not result_data or not point_model:
        return False
    if result_data.get('isNA', False):
        return False

    result_value = result_data.get('result')
    if result_value == 'Non Conforme':
        return True

    if point_model.get('TypeParametre') == 'Plage_Numerique' and result_value is not None:
        try:
            value = float(str(result_value).replace(',','.'))
            options_str = point_model.get('OptionsParametre', '')
            if options_str:
                options = options_str.split(';')
                if len(options) == 2:
                    min_val, max_val = map(float, options)
                    if value < min_val or value > max_val:
                        return True
        except (ValueError, TypeError):
             # Ignorer si la conversion échoue ou si les options sont mal formatées
            pass

    return False

def load_zip_data(uploaded_files: List[st.runtime.uploaded_file_manager.UploadedFile]) -> None:
    """
    Traite une liste de fichiers ZIP uploadés, extrait, valide, vérifie les doublons
    et met à jour l'état de session (loaded_inspections, corrective_actions).

    Args:
        uploaded_files: Liste d'objets UploadedFile fournie par st.file_uploader.
    """
    newly_loaded_count = 0
    duplicate_count = 0
    error_count = 0
    current_inspection_ids = {insp['inspection']['id'] for insp in st.session_state.loaded_inspections}

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        try:
            with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue()), 'r') as zip_ref:
                if "inspection_data.json" not in zip_ref.namelist():
                    st.error(f"Erreur dans '{filename}': Fichier 'inspection_data.json' introuvable.")
                    error_count += 1
                    continue

                json_data = zip_ref.read("inspection_data.json")
                package_data = json.loads(json_data)

                # Validation structurelle minimale plus précise
                if not isinstance(package_data, dict) or \
                   not all(k in package_data for k in ['inspection', 'model']) or \
                   not isinstance(package_data['inspection'], dict) or \
                   not all(k in package_data['inspection'] for k in ['id', 'modelId', 'startDate', 'results']) or \
                   not isinstance(package_data['model'], dict) or \
                   not all(k in package_data['model'] for k in ['name', 'items']) or \
                   not isinstance(package_data['inspection']['results'], list) or \
                   not isinstance(package_data['model']['items'], list):
                    st.error(f"Erreur dans '{filename}': Structure JSON invalide ou incomplète.")
                    error_count += 1
                    continue

                inspection_id = package_data['inspection']['id']
                if not isinstance(inspection_id, str) or not inspection_id:
                     st.error(f"Erreur dans '{filename}': ID d'inspection manquant ou invalide.")
                     error_count += 1
                     continue

                if inspection_id in current_inspection_ids:
                    st.warning(f"'{filename}' ignoré: Inspection ID '{inspection_id[:8]}...' déjà chargée.")
                    duplicate_count += 1
                    continue

                st.session_state.loaded_inspections.append({
                    "inspection": package_data['inspection'],
                    "model": package_data['model'],
                    "filename": filename
                })
                current_inspection_ids.add(inspection_id)
                newly_loaded_count += 1

                # Initialiser les actions correctives pour les points d'intérêt
                for result in package_data['inspection'].get('results', []):
                    point_id = result.get('idPoint')
                    if not point_id: continue
                    point_model = next((item for item in package_data['model'].get('items', []) if item.get('ID_Point') == point_id), None)
                    if is_point_of_interest(result, point_model):
                        action_key = (inspection_id, point_id)
                        if action_key not in st.session_state.corrective_actions:
                            st.session_state.corrective_actions[action_key] = {'status': 'À traiter', 'note': ''}

        except json.JSONDecodeError:
            st.error(f"Erreur dans '{filename}': Impossible de parser 'inspection_data.json'. Fichier corrompu ?")
            error_count += 1
        except zipfile.BadZipFile:
            st.error(f"Erreur dans '{filename}': Fichier ZIP invalide ou corrompu.")
            error_count += 1
        except Exception as e:
            st.error(f"Erreur inattendue lors du traitement de '{filename}': {e}")
            error_count += 1

    # Afficher un résumé du chargement à la fin
    if newly_loaded_count > 0:
        st.success(f"{newly_loaded_count} nouvelle(s) inspection(s) chargée(s).")
    if duplicate_count > 0:
        st.info(f"{duplicate_count} inspection(s) étaient déjà chargées.")
    if error_count > 0:
        st.warning(f"{error_count} fichier(s) n'ont pas pu être traités.")

def prepare_aggregated_dataframe() -> pd.DataFrame:
    """
    Crée un DataFrame Pandas avec les points d'intérêt et les actions correctives.

    Returns:
        Un DataFrame Pandas avec les données agrégées, ou un DF vide si aucune donnée.
    """
    data_for_df = []
    expected_columns = [
        'ID Unique', 'Date Insp.', 'ID Insp.', 'Inspecteur', 'Catégorie',
        'Point de Contrôle', 'Critère Accept.', 'Résultat Obtenu', 'Commentaire',
        'Nb Photos', 'Statut Action', 'Note Action', 'inspection_id_hidden', 'point_id_hidden'
    ]

    if not st.session_state.loaded_inspections:
        return pd.DataFrame(columns=expected_columns)

    for data in st.session_state.loaded_inspections:
        inspection = data['inspection']
        model = data['model']
        inspection_id = inspection['id']

        for result in inspection.get('results', []):
            point_id = result.get('idPoint')
            if not point_id: continue
            point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)

            if is_point_of_interest(result, point_model):
                action_key = (inspection_id, point_id)
                action_info = st.session_state.corrective_actions.get(action_key, {'status': 'À traiter', 'note': ''})

                # Formatage du résultat
                result_value = result.get('result', '')
                result_display = str(result_value) if result_value is not None else ''
                if point_model and point_model.get('TypeParametre') == 'Plage_Numerique' and result_value is not None:
                     try:
                         value_f = float(str(result_value).replace(',','.'))
                         options_str = point_model.get('OptionsParametre', '')
                         if options_str:
                             options = options_str.split(';')
                             if len(options) == 2:
                                min_val, max_val = map(float, options)
                                if value_f < min_val or value_f > max_val:
                                    result_display += f" [Hors Plage: {min_val}-{max_val}]"
                     except (ValueError, TypeError): pass

                data_for_df.append({
                    'ID Unique': f"{inspection_id[:8]}_{point_id}",
                    'Date Insp.': pd.to_datetime(inspection.get('startDate'), errors='coerce').date() if inspection.get('startDate') else None,
                    'ID Insp.': inspection_id[:8] + "...",
                    'Inspecteur': inspection.get('inspectorName', 'N/A'),
                    'Catégorie': point_model.get('Categorie', 'N/A') if point_model else 'N/A',
                    'Point de Contrôle': point_model.get('PointDeControle', 'N/A') if point_model else 'N/A',
                    'Critère Accept.': point_model.get('CritereAcceptation', 'N/A') if point_model else 'N/A',
                    'Résultat Obtenu': result_display,
                    'Commentaire': result.get('comment', ''),
                    'Nb Photos': len(result.get('photosBase64', [])),
                    'Statut Action': action_info.get('status', 'À traiter'),
                    'Note Action': action_info.get('note', ''),
                    'inspection_id_hidden': inspection_id,
                    'point_id_hidden': point_id
                })

    if not data_for_df:
         return pd.DataFrame(columns=expected_columns)

    df = pd.DataFrame(data_for_df)
    if 'Date Insp.' in df.columns:
        df['Date Insp.'] = pd.to_datetime(df['Date Insp.'])
    return df

def update_corrective_actions_from_df(edited_df: pd.DataFrame) -> None:
    """
    Met à jour st.session_state.corrective_actions à partir du DataFrame édité
    par st.data_editor (potentiellement une tranche paginée).

    Args:
        edited_df: Le DataFrame retourné par st.data_editor.
    """
    updates_made = 0
    required_cols = ['inspection_id_hidden', 'point_id_hidden', 'Statut Action', 'Note Action']
    if not all(col in edited_df.columns for col in required_cols):
        # Ne pas afficher d'erreur si le DF est simplement vide
        if not edited_df.empty:
            st.error("Erreur interne: Colonnes manquantes pour la mise à jour des actions.")
        return

    for index, row in edited_df.iterrows():
        inspection_id = row['inspection_id_hidden']
        point_id = row['point_id_hidden']
        action_key = (inspection_id, point_id)

        current_status = row['Statut Action']
        current_note = row['Note Action'] if pd.notna(row['Note Action']) else ""

        # Récupérer l'état précédent ou initialiser si absent
        previous_action = st.session_state.corrective_actions.get(action_key, {'status': 'À traiter', 'note': ''})

        # Comparer et mettre à jour si nécessaire
        if previous_action['status'] != current_status or previous_action['note'] != current_note:
            st.session_state.corrective_actions[action_key] = {'status': current_status, 'note': current_note}
            updates_made += 1

    if updates_made > 0:
        st.toast(f"{updates_made} mise(s) à jour des actions correctives enregistrée(s) pour cette session.", icon="📝")


def render_inspection_detail(inspection_data: Dict) -> None:
    """
    Affiche les détails formatés d'une inspection.

    Args:
        inspection_data: Dictionnaire contenant 'inspection', 'model', 'filename'.
    """
    inspection = inspection_data['inspection']
    model = inspection_data['model']
    filename = inspection_data['filename']

    st.subheader(f"Détails Inspection: {model.get('name', 'N/A')}")
    st.caption(f"Fichier d'origine: {filename} | ID: {inspection.get('id', 'N/A')}")

    # Métadonnées
    meta_cols = st.columns(2)
    with meta_cols[0]:
        st.write(f"**Inspecteur:** {inspection.get('inspectorName', 'N/A')}")
        start_date = inspection.get('startDate')
        st.write(f"**Date Début:** {pd.to_datetime(start_date).strftime('%d/%m/%Y %H:%M') if start_date else 'N/A'}")
    with meta_cols[1]:
        st.write(f"**Statut:** {inspection.get('status', 'N/A')}")
        end_date = inspection.get('endDate')
        st.write(f"**Date Fin:** {pd.to_datetime(end_date).strftime('%d/%m/%Y %H:%M') if end_date else 'N/A'}")

    st.divider()

    # Regroupement des points par catégorie
    points_by_category = {}
    for item in model.get('items', []):
        cat = item.get('Categorie', 'Sans Catégorie')
        if cat not in points_by_category: points_by_category[cat] = []
        points_by_category[cat].append(item)

    if not points_by_category:
        st.warning("Aucun point de contrôle trouvé dans le modèle de cette inspection.")
        return

    # Affichage des points
    for category, items in sorted(points_by_category.items()):
        with st.expander(f"**{category}** ({len(items)} points)", expanded=False):
            for point_model in items:
                point_id = point_model.get('ID_Point')
                result_data = next((r for r in inspection.get('results', []) if isinstance(r, dict) and r.get('idPoint') == point_id), None)

                st.markdown(f"**{point_model.get('PointDeControle', 'N/A')}** (ID: {point_id})")
                st.caption(f"Description: {point_model.get('Description', 'N/A')}")
                st.caption(f"Critère: {point_model.get('CritereAcceptation', 'N/A')}")

                if result_data:
                    res_col1, res_col2 = st.columns([1, 2])
                    with res_col1: # Résultat formaté
                        result_value = result_data.get('result')
                        is_na = result_data.get('isNA', False)
                        if is_na:
                            st.markdown(f"Résultat: *N/A*")
                        elif result_value == 'Non Conforme':
                             st.markdown(f"Résultat: <span style='color:red; font-weight:bold;'>Non Conforme</span>", unsafe_allow_html=True)
                        elif result_value == 'Conforme':
                            st.markdown(f"Résultat: <span style='color:green;'>Conforme</span>", unsafe_allow_html=True)
                        elif point_model.get('TypeParametre') == 'Plage_Numerique' and result_value is not None:
                            display_val = str(result_value)
                            is_poi = is_point_of_interest(result_data, point_model)
                            color = "red" if is_poi else "inherit"
                            options = point_model.get('OptionsParametre', '')
                            range_str = f" [Plage: {options}]" if options and is_poi else ""
                            st.markdown(f"Résultat: <span style='color:{color};'>{display_val}</span>{range_str}", unsafe_allow_html=True)
                        elif point_model.get('TypeParametre') == 'Date_Heure' and result_value:
                             try: date_str = pd.to_datetime(result_value).strftime('%d/%m/%Y %H:%M'); st.markdown(f"Résultat: {date_str}")
                             except Exception: st.markdown(f"Résultat: {result_value} (date invalide?)")
                        else: st.markdown(f"Résultat: {result_value}")

                    with res_col2: # Commentaire
                        st.markdown(f"**Commentaire:** {result_data.get('comment') or 'Aucun'}")

                    # --- Affichage des miniatures de photos et bouton Agrandir ---
                    photos = result_data.get('photosBase64', [])
                    if photos and isinstance(photos, list):
                        st.markdown("**Photos:**")
                        num_photos = len(photos)
                        cols_per_row = min(num_photos, 5)
                        photo_cols = st.columns(cols_per_row)

                        for i, b64_string in enumerate(photos):
                            col_index = i % cols_per_row
                            with photo_cols[col_index]:
                                try:
                                    if isinstance(b64_string, str) and ',' in b64_string: b64_string = b64_string.split(',')[1]
                                    img_bytes = base64.b64decode(b64_string)
                                    st.image(img_bytes, width=100, caption=f"Photo {i+1}")

                                    # *** CORRECTION ICI ***
                                    button_key = f"view_photo_{inspection['id']}_{point_id}_{i}"
                                    if st.button("Agrandir", key=button_key, help="Voir l'image en grand"):
                                        st.session_state.modal_photo_list = photos
                                        st.session_state.modal_photo_index = i
                                        st.session_state.modal_photo_caption = f"Photo {i+1} - Point: {point_model.get('PointDeControle', point_id)}"
                                        st.session_state.show_photo_modal = True
                                        # Fermer la modale détail AVANT d'ouvrir la modale photo
                                        st.session_state.show_detail_dialog = False
                                        st.rerun() # Re-exécuter pour afficher la modale photo

                                except (base64.binascii.Error, UnidentifiedImageError, Exception) as img_e: # Gestion erreurs image plus specifique
                                    st.warning(f"Photo {i+1} invalide", icon="⚠️") # Message plus court
                                    # st.caption(f"Erreur: {img_e}") # Optionnel: afficher l'erreur technique

                else:
                    st.info("Aucun résultat enregistré pour ce point.")
                st.divider()

def calculate_dashboard_metrics() -> Dict[str, Any]:
    """
    Calcule les métriques et prépare les DataFrames pour le tableau de bord.

    Returns:
        Un dictionnaire contenant les métriques et DataFrames.
    """
    metrics = {
        'total_inspections': len(st.session_state.loaded_inspections),
        'total_points_of_interest': 0, 'total_points_checked': 0, 'total_points_conform': 0,
        'action_status_counts': {'À traiter': 0, 'En cours': 0, 'Terminé': 0, 'Annulé': 0},
        'conformity_by_category': {}, 'non_conformity_counts_by_point': {},
        'category_compliance_rates_df': pd.DataFrame(columns=['Catégorie', 'Taux Conformité (%)']),
        'top_non_conformities_df': pd.DataFrame(columns=['Point de Contrôle', 'Nombre Occurrences']),
        'action_status_df': pd.DataFrame(columns=['Statut', 'Nombre']),
        'overall_compliance_rate': 0.0
    }
    if not st.session_state.loaded_inspections: return metrics

    for data in st.session_state.loaded_inspections:
        inspection = data['inspection']
        model = data['model']
        inspection_id = inspection['id']
        for result in inspection.get('results', []):
            point_id = result.get('idPoint')
            if not point_id: continue
            point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
            if not point_model or result.get('isNA', False): continue

            metrics['total_points_checked'] += 1
            category = point_model.get('Categorie', 'Sans Catégorie')
            if category not in metrics['conformity_by_category']: metrics['conformity_by_category'][category] = {'conform': 0, 'checked': 0}
            metrics['conformity_by_category'][category]['checked'] += 1

            is_poi = is_point_of_interest(result, point_model)
            if is_poi:
                metrics['total_points_of_interest'] += 1
                action_key = (inspection_id, point_id)
                status = st.session_state.corrective_actions.get(action_key, {}).get('status', 'À traiter')
                if status in metrics['action_status_counts']: metrics['action_status_counts'][status] += 1
                point_name = point_model.get('PointDeControle', 'N/A')
                metrics['non_conformity_counts_by_point'][point_name] = metrics['non_conformity_counts_by_point'].get(point_name, 0) + 1
            else:
                metrics['total_points_conform'] += 1
                metrics['conformity_by_category'][category]['conform'] += 1

    # Calculs finaux et préparation DFs
    if metrics['total_points_checked'] > 0: metrics['overall_compliance_rate'] = (metrics['total_points_conform'] / metrics['total_points_checked'] * 100)
    cat_rates_data = [{'Catégorie': name, 'Taux Conformité (%)': (d['conform'] / d['checked'] * 100) if d['checked'] > 0 else 0.0} for name, d in metrics['conformity_by_category'].items()]
    if cat_rates_data: metrics['category_compliance_rates_df'] = pd.DataFrame(cat_rates_data).sort_values(by='Catégorie')
    if metrics['non_conformity_counts_by_point']: metrics['top_non_conformities_df'] = pd.DataFrame(metrics['non_conformity_counts_by_point'].items(), columns=['Point de Contrôle', 'Nombre Occurrences']).nlargest(5, 'Nombre Occurrences')
    if sum(metrics['action_status_counts'].values()) > 0: metrics['action_status_df'] = pd.DataFrame(metrics['action_status_counts'].items(), columns=['Statut', 'Nombre']).sort_values(by='Statut')

    return metrics

def prepare_export_data() -> List[Dict]:
    """
    Prépare la liste des inspections avec les actions correctives mises à jour pour l'export.

    Returns:
        Liste des dictionnaires d'inspection mis à jour.
    """
    import copy
    updated_inspections_list = []
    inspections_to_export = copy.deepcopy(st.session_state.loaded_inspections) # Copie profonde !

    for data in inspections_to_export:
        inspection_id = data['inspection']['id']
        if 'results' in data['inspection'] and isinstance(data['inspection']['results'], list):
            for result in data['inspection']['results']:
                if isinstance(result, dict) and 'idPoint' in result:
                    point_id = result.get('idPoint')
                    action_key = (inspection_id, point_id)
                    if action_key in st.session_state.corrective_actions:
                        action_info = st.session_state.corrective_actions[action_key]
                        result['statutAction'] = action_info.get('status')
                        result['noteAction'] = action_info.get('note')
        updated_inspections_list.append(data)
    return updated_inspections_list

def create_export_zip(export_data: List[Dict]) -> bytes:
    """
    Crée le fichier ZIP d'export contenant aggregated_export.json.

    Args:
        export_data: Liste des dictionnaires d'inspection à exporter.

    Returns:
        Bytes du ZIP, ou bytes vides si erreur.
    """
    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            def default_serializer(obj): # Gérer dates pour JSON
                if isinstance(obj, (datetime, pd.Timestamp)): return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            json_string = json.dumps(export_data, indent=2, ensure_ascii=False, default=default_serializer)
            zip_file.writestr("aggregated_export.json", json_string)
    except Exception as e:
        st.error(f"Erreur lors de la création du fichier ZIP : {e}")
        return b""
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

# --- Interface Utilisateur Streamlit ---

st.title("📊 Visualiseur et Analyseur d'Inspections")
st.caption("Chargez des packages d'inspection (.zip) pour visualiser, agréger et analyser les données.")

# -- Barre Latérale --
with st.sidebar:
    st.header("Chargement des Données")
    uploaded_files = st.file_uploader(
        "Sélectionner un ou plusieurs packages (.zip)", type='zip',
        accept_multiple_files=True, key="file_uploader",
        help="Chargez les fichiers .zip contenant 'inspection_data.json'"
    )
    if uploaded_files:
        if st.button("Traiter les Fichiers Chargés"):
            with st.spinner("Traitement des fichiers..."): load_zip_data(uploaded_files)
            st.rerun() # Rafraîchir et vider l'uploader visuellement

    st.divider()

    # Actions Globales
    if st.session_state.loaded_inspections:
        st.header("Actions Globales")
        if st.button("⚠️ Vider Toutes les Données", help="Supprime toutes les inspections chargées et les actions correctives de cette session."):
            # TODO: Ajouter une confirmation modale ici pour la sécurité
            st.session_state.loaded_inspections = []
            st.session_state.corrective_actions = {}
            st.session_state.selected_inspection_id_for_detail = None
            st.session_state.show_detail_dialog = False
            st.session_state.export_data_prepared = None
            st.session_state.aggregated_page_number = 1
            st.toast("Toutes les données ont été vidées.", icon="🗑️")
            st.rerun()

        st.divider()
        st.header("Export")
        st.caption("Exporte toutes les inspections chargées avec les derniers statuts/notes d'action corrective.")
        if st.button("Préparer l'Export Agrégé"):
             with st.spinner("Préparation de l'export..."):
                try:
                    export_list = prepare_export_data()
                    zip_bytes = create_export_zip(export_list)
                    if zip_bytes:
                        st.session_state.export_data_prepared = zip_bytes
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        st.session_state.export_filename = f"export_agregé_{timestamp}.zip"
                        st.toast("Export prêt à être téléchargé.", icon="✅")
                except Exception as prep_e:
                    st.error(f"Erreur préparation export: {prep_e}")
                    st.session_state.export_data_prepared = None

        if st.session_state.export_data_prepared:
            st.download_button(label="⬇️ Télécharger le Package Agrégé (.zip)",
                               data=st.session_state.export_data_prepared,
                               file_name=st.session_state.export_filename,
                               mime="application/zip", key="download_export_button")

# -- Contenu Principal avec Onglets --
if not st.session_state.loaded_inspections:
    st.info("👋 Bienvenue ! Commencez par charger un ou plusieurs packages d'inspection (.zip) via la barre latérale.")
else:
    tab_titles = ["📈 Tableau de Bord", f"📋 Liste Inspections ({len(st.session_state.loaded_inspections)})", "🔍 Vue Agrégée"]
    tab_dashboard, tab_list, tab_aggregated = st.tabs(tab_titles)

    # --- Onglet Tableau de Bord ---
    with tab_dashboard:
        st.subheader("📈 Tableau de Bord Synthétique")
        metrics = calculate_dashboard_metrics() # Recalculer à chaque affichage
        kpi_cols = st.columns(3)
        kpi_cols[0].metric("Inspections Chargées", metrics['total_inspections'])
        kpi_cols[1].metric("Points d'Intérêt Trouvés", metrics['total_points_of_interest'])
        kpi_cols[2].metric("Taux Conformité Global", f"{metrics['overall_compliance_rate']:.1f}%", help="Calculé sur les points vérifiés (non N/A)")
        st.divider()
        chart_cols = st.columns(2)
        with chart_cols[0]:
            st.markdown("**Répartition Statuts Action**")
            if not metrics['action_status_df'].empty and metrics['action_status_df']['Nombre'].sum() > 0:
                fig_pie = px.pie(metrics['action_status_df'], names='Statut', values='Nombre', title="Statuts Actions Correctives", hole=0.3)
                fig_pie.update_layout(legend_title_text='Statut')
                st.plotly_chart(fig_pie, use_container_width=True)
            else: st.caption("Aucune action corrective à afficher.")
            st.markdown(f"**Top {len(metrics['top_non_conformities_df'])} Points Non-Conformes**")
            if not metrics['top_non_conformities_df'].empty:
                 df_top_nc = metrics['top_non_conformities_df'].sort_values(by='Nombre Occurrences', ascending=True)
                 fig_bar_nc = px.bar(df_top_nc, x='Nombre Occurrences', y='Point de Contrôle', orientation='h', title="Points Fréquemment Non-Conformes / Hors Plage")
                 fig_bar_nc.update_layout(yaxis_title=None, xaxis_title="Nombre d'occurrences")
                 st.plotly_chart(fig_bar_nc, use_container_width=True)
            else: st.caption("Aucune non-conformité trouvée.")
        with chart_cols[1]:
            st.markdown("**Taux de Conformité par Catégorie**")
            if not metrics['category_compliance_rates_df'].empty:
                fig_bar_cat = px.bar(metrics['category_compliance_rates_df'], x='Catégorie', y='Taux Conformité (%)', title="Conformité par Catégorie", range_y=[0, 100], color='Taux Conformité (%)', color_continuous_scale=px.colors.sequential.Greens)
                fig_bar_cat.update_layout(xaxis_tickangle=-45, yaxis_title="Taux de Conformité (%)")
                st.plotly_chart(fig_bar_cat, use_container_width=True)
            else: st.caption("Aucune donnée de catégorie à afficher.")

    # --- Onglet Liste des Inspections ---
    with tab_list:
        st.subheader(f"📋 Liste des Inspections Chargées ({len(st.session_state.loaded_inspections)})")
        if not st.session_state.loaded_inspections: st.info("Aucune inspection chargée.")
        else:
            for index, data in enumerate(st.session_state.loaded_inspections):
                inspection, model, filename, inspection_id = data['inspection'], data['model'], data['filename'], data['inspection']['id']
                expander_key = f"expander_{inspection_id}_{index}"
                with st.expander(f"**{model.get('name', 'N/A')}** par **{inspection.get('inspectorName', 'N/A')}** (ID: ...{inspection_id[-8:]})", expanded=False):
                    exp_cols = st.columns([3, 1])
                    with exp_cols[0]:
                        start_date_str = pd.to_datetime(inspection.get('startDate'), errors='coerce').strftime('%d/%m/%Y %H:%M') if inspection.get('startDate') else 'N/A'
                        st.caption(f"Fichier: {filename} | Statut: {inspection.get('status', 'N/A')} | Début: {start_date_str}")
                    with exp_cols[1]:
                        # Utilisation de `on_click` pour gérer l'état avant rerun
                        def set_detail_view_state(insp_id):
                            st.session_state.selected_inspection_id_for_detail = insp_id
                            st.session_state.show_detail_dialog = True

                        st.button("👁️ Voir Détails", key=f"detail_{inspection_id}_{index}", on_click=set_detail_view_state, args=(inspection_id,))

                        def remove_inspection(insp_id):
                            st.session_state.loaded_inspections = [insp for insp in st.session_state.loaded_inspections if insp['inspection']['id'] != insp_id]
                            keys_to_remove = [key for key in st.session_state.corrective_actions if key[0] == insp_id]
                            for key in keys_to_remove: del st.session_state.corrective_actions[key]
                            st.toast(f"Inspection ...{insp_id[-8:]} retirée.", icon="🗑️")
                            if st.session_state.selected_inspection_id_for_detail == insp_id:
                                st.session_state.selected_inspection_id_for_detail = None
                                st.session_state.show_detail_dialog = False
                            # Le rerun sera déclenché automatiquement par Streamlit après le on_click

                        st.button("🗑️ Retirer", key=f"remove_{inspection_id}_{index}", type="secondary", on_click=remove_inspection, args=(inspection_id,))

    # --- Onglet Vue Agrégée ---
    with tab_aggregated:
        st.subheader("🔍 Vue Agrégée des Points d'Intérêt")
        st.caption("Affiche les points 'Non Conforme' ou 'Hors Plage'. Les colonnes 'Statut Action' et 'Note Action' sont modifiables pour cette session.")
        aggregated_df_full = prepare_aggregated_dataframe() # Préparer toutes les données pertinentes

        st.markdown("**Filtres :**")
        filter_cols = st.columns([2, 1, 1, 1, 1])
        with filter_cols[0]: search_term = st.text_input("Recherche libre", key="agg_search")
        with filter_cols[1]: categories = [''] + sorted(aggregated_df_full['Catégorie'].astype(str).unique()); selected_category = st.selectbox("Catégorie", options=categories, key="agg_cat_filter")
        with filter_cols[2]: inspectors = [''] + sorted(aggregated_df_full['Inspecteur'].astype(str).unique()); selected_inspector = st.selectbox("Inspecteur", options=inspectors, key="agg_insp_filter")
        with filter_cols[3]: points_ctrl = [''] + sorted(aggregated_df_full['Point de Contrôle'].astype(str).unique()); selected_point = st.selectbox("Point Contrôle", options=points_ctrl, key="agg_point_filter")
        with filter_cols[4]: action_statuses = [''] + ['À traiter', 'En cours', 'Terminé', 'Annulé']; selected_action_status = st.selectbox("Statut Action", options=action_statuses, key="agg_status_filter")

        # Appliquer les filtres
        filtered_df = aggregated_df_full.copy()
        if search_term:
            search_term_lower = search_term.lower()
            text_search_cols = ['Point de Contrôle', 'Commentaire', 'Note Action', 'Résultat Obtenu', 'Critère Accept.']
            mask = pd.Series([False] * len(filtered_df))
            for col in text_search_cols:
                if col in filtered_df.columns: mask |= filtered_df[col].astype(str).str.lower().str.contains(search_term_lower, na=False)
            filtered_df = filtered_df[mask]
        if selected_category: filtered_df = filtered_df[filtered_df['Catégorie'] == selected_category]
        if selected_inspector: filtered_df = filtered_df[filtered_df['Inspecteur'] == selected_inspector]
        if selected_point: filtered_df = filtered_df[filtered_df['Point de Contrôle'] == selected_point]
        if selected_action_status: filtered_df = filtered_df[filtered_df['Statut Action'] == selected_action_status]

        st.divider()
        total_items = len(filtered_df)
        if total_items == 0:
            if not aggregated_df_full.empty: st.warning("Aucun point d'intérêt ne correspond aux filtres actuels.")
            else: st.info("Aucun point d'intérêt trouvé dans les inspections chargées.")
        else:
            st.markdown(f"**{total_items}** point(s) d'intérêt trouvé(s)")
            total_pages = max(1, (total_items + ITEMS_PER_PAGE_AGGREGATED - 1) // ITEMS_PER_PAGE_AGGREGATED)
            current_page = min(st.session_state.aggregated_page_number, total_pages)
            st.session_state.aggregated_page_number = current_page # Mettre à jour si ajustée
            start_idx = (current_page - 1) * ITEMS_PER_PAGE_AGGREGATED
            end_idx = start_idx + ITEMS_PER_PAGE_AGGREGATED
            paginated_df = filtered_df.iloc[start_idx:end_idx]

            # Affichage du data editor
            edited_df_slice = st.data_editor(
                paginated_df, key="aggregated_data_editor", use_container_width=True, hide_index=True,
                column_config={ # Configuration détaillée des colonnes
                    "inspection_id_hidden": None, "point_id_hidden": None, "ID Unique": None,
                    "Date Insp.": st.column_config.DateColumn("Date", format="DD/MM/YY", disabled=True, width="small"), # Plus court
                    "ID Insp.": st.column_config.TextColumn("ID Insp.", disabled=True, width="small"),
                    "Inspecteur": st.column_config.TextColumn("Inspecteur", disabled=True, width="small"),
                    "Catégorie": st.column_config.TextColumn("Catégorie", disabled=True, width="medium"),
                    "Point de Contrôle": st.column_config.TextColumn("Point Contrôle", disabled=True, width="medium"),
                    "Critère Accept.": None, # Cacher par défaut, trop long
                    "Résultat Obtenu": st.column_config.TextColumn("Résultat", disabled=True, width="medium"),
                    "Commentaire": st.column_config.TextColumn("Commentaire", disabled=True, width="large"),
                    "Nb Photos": st.column_config.NumberColumn("Photos", format="%d📷", disabled=True, width="small"),
                    "Statut Action": st.column_config.SelectboxColumn("Statut Action", width="medium", options=['À traiter', 'En cours', 'Terminé', 'Annulé'], required=True),
                    "Note Action": st.column_config.TextColumn("Note Action", max_chars=200, width="large"),
                },
                column_order=[ # Ordre d'affichage
                    "Date Insp.", "Inspecteur", "Catégorie", "Point de Contrôle", "Résultat Obtenu",
                    "Statut Action", "Note Action", "Commentaire", "Nb Photos", "ID Insp."
                ],
                num_rows="fixed" # Hauteur fixe pour le tableau
            )

            # Mise à jour de l'état après édition (toujours appeler, la fonction gère la comparaison)
            update_corrective_actions_from_df(edited_df_slice)

            # Contrôles de Pagination
            st.divider()
            if total_pages > 1:
                pagination_cols = st.columns([1, 2, 1])
                with pagination_cols[0]:
                    if st.button("⬅️ Précédent", disabled=(current_page <= 1), key="agg_prev_page"):
                        st.session_state.aggregated_page_number -= 1; st.rerun()
                with pagination_cols[1]:
                    st.markdown(f"<div style='text-align: center;'>Page **{current_page}** / **{total_pages}**</div>", unsafe_allow_html=True)
                with pagination_cols[2]:
                    if st.button("Suivant ➡️", disabled=(current_page >= total_pages), key="agg_next_page"):
                        st.session_state.aggregated_page_number += 1; st.rerun()


# --- Modale de Détail (affichage conditionnel basé sur l'état) ---
if st.session_state.show_detail_dialog and st.session_state.selected_inspection_id_for_detail:
    inspection_to_show = next((insp for insp in st.session_state.loaded_inspections if insp['inspection']['id'] == st.session_state.selected_inspection_id_for_detail), None)
    if inspection_to_show:
        @st.dialog("Détails de l'Inspection") # Décorateur pour la modale
        def show_detail_modal():
            render_inspection_detail(inspection_to_show) # Contenu
            if st.button("Fermer", key="close_detail_dialog_button"):
                 setattr(st.session_state, 'show_detail_dialog', False); st.rerun() # Fermer et rafraîchir
        show_detail_modal() # Appeler pour afficher
    else: # Si l'ID n'est plus valide, réinitialiser l'état
        st.session_state.selected_inspection_id_for_detail = None
        st.session_state.show_detail_dialog = False
        # Pas besoin de st.warning ou rerun ici, car la condition if ne sera plus remplie au prochain cycle

# --- Modale Photo (affichage conditionnel basé sur l'état) ---
if st.session_state.show_photo_modal and st.session_state.modal_photo_list:
    @st.dialog("Visualiseur de Photos") # Décorateur pour la modale
    def show_photo_viewer():
        st.subheader(st.session_state.modal_photo_caption)
        current_index = st.session_state.modal_photo_index
        photos = st.session_state.modal_photo_list
        num_photos = len(photos)
        try: # Affichage image actuelle
            b64_string = photos[current_index]
            if isinstance(b64_string, str) and ',' in b64_string: b64_string = b64_string.split(',')[1]
            img_bytes = base64.b64decode(b64_string)
            st.image(img_bytes, use_column_width=True)
        except Exception as e: st.error(f"Impossible d'afficher l'image {current_index + 1}: {e}")

        if num_photos > 1: # Navigation
            nav_cols = st.columns([1, 2, 1])
            with nav_cols[0]:
                def go_prev_photo(): st.session_state.modal_photo_index -= 1
                st.button("⬅️ Précédent", disabled=(current_index == 0), key="prev_photo", on_click=go_prev_photo)
            with nav_cols[1]: st.write(f"Photo {current_index + 1} / {num_photos}")
            with nav_cols[2]:
                def go_next_photo(): st.session_state.modal_photo_index += 1
                st.button("Suivant ➡️", disabled=(current_index == num_photos - 1), key="next_photo", on_click=go_next_photo)

        def close_photo_viewer(): setattr(st.session_state, 'show_photo_modal', False)
        st.button("Fermer", key="close_photo_modal_button", on_click=close_photo_viewer)

    show_photo_viewer() # Appeler pour afficher

# --- Pied de page ---
st.divider()
st.caption("Application Visualiseur d'Inspections v1.1 - Mode Volatile")
st.caption("Les statuts et notes d'actions correctives sont conservés uniquement pendant cette session (sauf si exportés).")
