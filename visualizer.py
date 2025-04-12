import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import zipfile
import io
import json
import base64
from PIL import Image
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union # Ajout pour Type Hinting

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
# Essentiel pour stocker les données entre les re-exécutions de Streamlit
default_session_state = {
    'loaded_inspections': [], # Liste pour stocker { "inspection": Dict, "model": Dict, "filename": str }
    'corrective_actions': {}, # Dict: clé = Tuple(inspection_id, point_id), valeur = {'status': str, 'note': str}
    'selected_inspection_id_for_detail': None, # str | None
    'show_detail_dialog': False, # bool
    'export_data_prepared': None, # bytes | None
    'export_filename': "", # str
    'show_photo_modal': False, # bool
    'modal_photo_list': [], # List[str] (base64 strings)
    'modal_photo_index': 0, # int
    'modal_photo_caption': "", # str
    'aggregated_page_number': 1 # int
}

for key, default_value in default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- Fonctions Utilitaires ---

def is_point_of_interest(result_data: Optional[Dict], point_model: Optional[Dict]) -> bool:
    """
    Vérifie si un point de contrôle est considéré comme 'd'intérêt'
    (Non Conforme ou Hors Plage Numérique).

    Args:
        result_data: Dictionnaire contenant les résultats du point ('result', 'isNA', etc.).
        point_model: Dictionnaire contenant la définition du point depuis le modèle ('TypeParametre', 'OptionsParametre', etc.).

    Returns:
        True si le point est d'intérêt, False sinon.
    """
    if not result_data or not point_model:
        return False
    if result_data.get('isNA', False): # Ignorer si Non Applicable
        return False

    result_value = result_data.get('result')
    if result_value == 'Non Conforme':
        return True

    # Vérification Plage Numérique
    if point_model.get('TypeParametre') == 'Plage_Numerique' and result_value is not None:
        try:
            # Essayer de convertir en float, gérer les erreurs potentielles
            value = float(str(result_value).replace(',','.')) # Remplacer virgule par point pour conversion
            options_str = point_model.get('OptionsParametre', '')
            if options_str:
                options = options_str.split(';')
                if len(options) == 2:
                    min_val, max_val = map(float, options)
                    if value < min_val or value > max_val:
                        return True
        except (ValueError, TypeError):
            # Ignorer si la conversion échoue ou si les options sont invalides
            # On pourrait logguer une erreur ici si nécessaire
            pass

    # Optionnel: Inclure les points avec commentaires (décommenter si besoin)
    # if result_data.get('comment', '').strip():
    #     return True

    return False

def load_zip_data(uploaded_files: List[st.runtime.uploaded_file_manager.UploadedFile]) -> None:
    """
    Traite une liste de fichiers ZIP uploadés, extrait les données d'inspection,
    valide, vérifie les doublons et met à jour l'état de session.

    Args:
        uploaded_files: Liste d'objets UploadedFile fournie par st.file_uploader.
    """
    newly_loaded_count = 0
    duplicate_count = 0
    error_count = 0

    # Obtenir les IDs des inspections déjà chargées pour vérifier les doublons
    current_inspection_ids = {insp['inspection']['id'] for insp in st.session_state.loaded_inspections}

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        try:
            # Lire le contenu du fichier ZIP en mémoire
            with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue()), 'r') as zip_ref:
                # Vérifier la présence du fichier JSON attendu
                if "inspection_data.json" not in zip_ref.namelist():
                    st.error(f"Erreur dans '{filename}': Fichier 'inspection_data.json' introuvable.")
                    error_count += 1
                    continue

                # Lire et parser le fichier JSON
                json_data = zip_ref.read("inspection_data.json")
                package_data = json.loads(json_data)

                # Validation structurelle minimale
                if not isinstance(package_data, dict) or \
                   not all(k in package_data for k in ['inspection', 'model']) or \
                   not isinstance(package_data['inspection'], dict) or \
                   not all(k in package_data['inspection'] for k in ['id', 'modelId', 'startDate', 'results']) or \
                   not isinstance(package_data['model'], dict) or \
                   not all(k in package_data['model'] for k in ['name', 'items']):
                    st.error(f"Erreur dans '{filename}': Structure JSON invalide ou incomplète.")
                    error_count += 1
                    continue

                inspection_id = package_data['inspection']['id']

                # Vérification de doublon
                if inspection_id in current_inspection_ids:
                    st.warning(f"'{filename}' ignoré: Inspection ID '{inspection_id[:8]}...' déjà chargée.")
                    duplicate_count += 1
                    continue

                # Stockage des données valides dans l'état de session
                st.session_state.loaded_inspections.append({
                    "inspection": package_data['inspection'],
                    "model": package_data['model'],
                    "filename": filename
                })
                # Ajouter l'ID à l'ensemble pour vérifier les doublons dans ce même lot de chargement
                current_inspection_ids.add(inspection_id)
                newly_loaded_count += 1

                # Initialiser les actions correctives pour les points d'intérêt de cette nouvelle inspection
                for result in package_data['inspection'].get('results', []):
                    point_id = result.get('idPoint')
                    if not point_id: continue # S'assurer qu'on a un ID de point

                    point_model = next((item for item in package_data['model'].get('items', []) if item.get('ID_Point') == point_id), None)
                    if is_point_of_interest(result, point_model):
                        action_key = (inspection_id, point_id)
                        # Initialiser seulement si pas déjà présent (ne devrait pas arriver ici, mais par sécurité)
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

    # Afficher un résumé du chargement
    if newly_loaded_count > 0:
        st.success(f"{newly_loaded_count} nouvelle(s) inspection(s) chargée(s).")
    if duplicate_count > 0:
        st.info(f"{duplicate_count} inspection(s) étaient déjà chargées.")
    if error_count > 0:
        st.warning(f"{error_count} fichier(s) n'ont pas pu être traités.")

def prepare_aggregated_dataframe() -> pd.DataFrame:
    """
    Crée un DataFrame Pandas contenant tous les points d'intérêt des inspections chargées,
    enrichi avec les informations des actions correctives stockées en session.

    Returns:
        Un DataFrame Pandas avec les données agrégées. Retourne un DataFrame vide
        avec les colonnes attendues si aucune inspection n'est chargée ou aucun point d'intérêt trouvé.
    """
    data_for_df = []
    expected_columns = [
        'ID Unique', 'Date Insp.', 'ID Insp.', 'Inspecteur', 'Catégorie',
        'Point de Contrôle', 'Critère Accept.', 'Résultat Obtenu', 'Commentaire',
        'Nb Photos', 'Statut Action', 'Note Action', 'inspection_id_hidden', 'point_id_hidden'
    ]

    if not st.session_state.loaded_inspections:
        return pd.DataFrame(columns=expected_columns)

    for idx, data in enumerate(st.session_state.loaded_inspections):
        inspection = data['inspection']
        model = data['model']
        # filename = data['filename'] # Pas utilisé directement dans le DF agrégé
        inspection_id = inspection['id']

        for result in inspection.get('results', []):
            point_id = result.get('idPoint')
            if not point_id: continue

            point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)

            if is_point_of_interest(result, point_model):
                action_key = (inspection_id, point_id)
                # Récupérer l'info d'action ou utiliser les valeurs par défaut
                action_info = st.session_state.corrective_actions.get(action_key, {'status': 'À traiter', 'note': ''})

                # Formatter le résultat pour un affichage clair dans le tableau
                result_value = result.get('result', '')
                result_display = str(result_value) if result_value is not None else ''
                if point_model and point_model.get('TypeParametre') == 'Plage_Numerique' and result_value is not None:
                     try:
                         value_f = float(str(result_value).replace(',','.')) # Remplacer virgule par point
                         options_str = point_model.get('OptionsParametre', '')
                         if options_str:
                             options = options_str.split(';')
                             if len(options) == 2:
                                min_val, max_val = map(float, options)
                                if value_f < min_val or value_f > max_val:
                                    result_display += f" [Hors Plage: {min_val}-{max_val}]"
                     except (ValueError, TypeError): pass # Ignorer erreurs de conversion/format

                data_for_df.append({
                    'ID Unique': f"{inspection_id[:8]}_{point_id}",
                    'Date Insp.': pd.to_datetime(inspection.get('startDate')).date() if inspection.get('startDate') else None,
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
                    'inspection_id_hidden': inspection_id, # Pour référence interne
                    'point_id_hidden': point_id # Pour référence interne
                })

    if not data_for_df:
         return pd.DataFrame(columns=expected_columns)

    df = pd.DataFrame(data_for_df)
    # Assurer le type Date pour le tri
    if 'Date Insp.' in df.columns:
        df['Date Insp.'] = pd.to_datetime(df['Date Insp.'])
    return df

def update_corrective_actions_from_df(edited_df: pd.DataFrame) -> None:
    """
    Met à jour le dictionnaire st.session_state.corrective_actions en se basant
    sur les modifications effectuées dans le DataFrame retourné par st.data_editor.

    Args:
        edited_df: Le DataFrame tel que retourné par st.data_editor, contenant potentiellement
                   des modifications dans les colonnes 'Statut Action' et 'Note Action'.
                   Ce DF peut être une tranche paginée du DF complet.
    """
    updates_made = 0
    # Colonnes nécessaires pour identifier et mettre à jour l'action
    required_cols = ['inspection_id_hidden', 'point_id_hidden', 'Statut Action', 'Note Action']
    if not all(col in edited_df.columns for col in required_cols):
        st.error("Erreur interne: Colonnes manquantes dans le DataFrame édité pour la mise à jour des actions.")
        return

    for index, row in edited_df.iterrows():
        inspection_id = row['inspection_id_hidden']
        point_id = row['point_id_hidden']
        action_key = (inspection_id, point_id)

        # Récupérer les valeurs potentiellement éditées
        current_status = row['Statut Action']
        # Gérer les NaN potentiels si la colonne Note est laissée vide dans l'éditeur
        current_note = row['Note Action'] if pd.notna(row['Note Action']) else ""

        # Récupérer l'état précédent ou initialiser si absent (par sécurité)
        previous_action = st.session_state.corrective_actions.get(action_key, {'status': 'À traiter', 'note': ''})

        # Comparer l'état actuel avec l'état précédent stocké en session
        if previous_action['status'] != current_status or previous_action['note'] != current_note:
            # Mettre à jour l'état de session si une différence est détectée
            st.session_state.corrective_actions[action_key] = {'status': current_status, 'note': current_note}
            updates_made += 1

    if updates_made > 0:
        # Afficher une notification indiquant que des mises à jour ont été prises en compte
        st.toast(f"{updates_made} mise(s) à jour des actions correctives enregistrée(s) pour cette session.", icon="📝")

def render_inspection_detail(inspection_data: Dict) -> None:
    """
    Affiche les détails formatés d'une inspection (métadonnées, points par catégorie, photos).
    Utilisé typiquement à l'intérieur d'un st.dialog ou d'une section dédiée.

    Args:
        inspection_data: Dictionnaire contenant les clés 'inspection', 'model', 'filename'.
    """
    inspection = inspection_data['inspection']
    model = inspection_data['model']
    filename = inspection_data['filename']

    st.subheader(f"Détails Inspection: {model.get('name', 'N/A')}")
    st.caption(f"Fichier d'origine: {filename} | ID: {inspection.get('id', 'N/A')}")

    # Affichage des Métadonnées
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
        if cat not in points_by_category:
            points_by_category[cat] = []
        points_by_category[cat].append(item)

    # Affichage des points par catégorie dans des expanders
    if not points_by_category:
        st.warning("Aucun point de contrôle trouvé dans le modèle de cette inspection.")
        return

    for category, items in sorted(points_by_category.items()):
        with st.expander(f"**{category}** ({len(items)} points)", expanded=False):
            for point_model in items:
                point_id = point_model.get('ID_Point')
                # Trouver les résultats correspondants pour ce point
                result_data = next((r for r in inspection.get('results', []) if r.get('idPoint') == point_id), None)

                st.markdown(f"**{point_model.get('PointDeControle', 'N/A')}** (ID: {point_id})")
                st.caption(f"Description: {point_model.get('Description', 'N/A')}")
                st.caption(f"Critère: {point_model.get('CritereAcceptation', 'N/A')}")

                if result_data:
                    res_col1, res_col2 = st.columns([1, 2]) # Colonnes pour résultat et commentaire
                    with res_col1: # Affichage formaté du résultat
                        result_value = result_data.get('result')
                        if result_data.get('isNA'):
                            st.markdown(f"Résultat: *N/A*")
                        elif result_value == 'Non Conforme':
                             st.markdown(f"Résultat: <span style='color:red; font-weight:bold;'>Non Conforme</span>", unsafe_allow_html=True)
                        elif result_value == 'Conforme':
                            st.markdown(f"Résultat: <span style='color:green;'>Conforme</span>", unsafe_allow_html=True)
                        elif point_model.get('TypeParametre') == 'Plage_Numerique' and result_value is not None:
                            display_val = str(result_value)
                            is_poi = is_point_of_interest(result_data, point_model) # Réutiliser la fonction
                            color = "red" if is_poi else "inherit"
                            options = point_model.get('OptionsParametre', '')
                            range_str = f" [Plage: {options}]" if options and is_poi else ""
                            st.markdown(f"Résultat: <span style='color:{color};'>{display_val}</span>{range_str}", unsafe_allow_html=True)
                        elif point_model.get('TypeParametre') == 'Date_Heure' and result_value:
                             try:
                                 date_str = pd.to_datetime(result_value).strftime('%d/%m/%Y %H:%M')
                                 st.markdown(f"Résultat: {date_str}")
                             except Exception: # Gérer date invalide
                                 st.markdown(f"Résultat: {result_value} (date invalide?)")
                        else:
                            st.markdown(f"Résultat: {result_value}")

                    with res_col2: # Affichage du commentaire
                        st.markdown(f"**Commentaire:** {result_data.get('comment') or 'Aucun'}")

                    # --- Affichage des miniatures de photos ---
                    photos = result_data.get('photosBase64', [])
                    if photos:
                        st.markdown("**Photos:**")
                        # Utiliser st.columns pour afficher les miniatures côte à côte
                        num_photos = len(photos)
                        # Ajuster le nombre de colonnes en fonction du nombre de photos pour un meilleur affichage
                        cols_per_row = min(num_photos, 5) # Max 5 miniatures par ligne
                        photo_cols = st.columns(cols_per_row)

                        for i, b64_string in enumerate(photos):
                            col_index = i % cols_per_row
                            with photo_cols[col_index]:
                                try:
                                    # Nettoyer la string base64 (enlever le préfixe si présent)
                                    if isinstance(b64_string, str) and ',' in b64_string:
                                        b64_string = b64_string.split(',')[1]

                                    # Décoder et afficher la miniature
                                    img_bytes = base64.b64decode(b64_string)
                                    st.image(img_bytes, width=100, caption=f"Photo {i+1}") # Afficher une miniature

                                    # Bouton sous la miniature pour ouvrir la modale
                                    button_key = f"view_photo_{inspection['id']}_{point_id}_{i}"
                                    if st.button("Agrandir", key=button_key, help="Voir l'image en grand"):
                                        st.session_state.modal_photo_list = photos # Liste des photos pour ce point
                                        st.session_state.modal_photo_index = i # Index de la photo cliquée
                                        st.session_state.modal_photo_caption = f"Photo {i+1} - Point: {point_model.get('PointDeControle', point_id)}"
                                        st.session_state.show_photo_modal = True
                                        st.rerun() # Re-exécuter pour afficher la modale

                                except Exception as img_e:
                                    st.warning(f"Photo {i+1} invalide: {img_e}")
                else:
                    st.info("Aucun résultat enregistré pour ce point.")
                st.divider() # Séparateur entre les points de contrôle

def calculate_dashboard_metrics() -> Dict[str, Any]:
    """
    Calcule les métriques clés et prépare les DataFrames nécessaires pour
    l'affichage du tableau de bord, basé sur les inspections chargées et
    les actions correctives en session.

    Returns:
        Un dictionnaire contenant les métriques calculées et les DataFrames préparés.
        Retourne des valeurs par défaut et des DataFrames vides si aucune inspection n'est chargée.
    """
    # Initialisation des métriques avec des valeurs par défaut
    metrics = {
        'total_inspections': len(st.session_state.loaded_inspections),
        'total_points_of_interest': 0,
        'total_points_checked': 0,
        'total_points_conform': 0,
        'action_status_counts': {'À traiter': 0, 'En cours': 0, 'Terminé': 0, 'Annulé': 0},
        'conformity_by_category': {},
        'non_conformity_counts_by_point': {},
        'category_compliance_rates_df': pd.DataFrame(columns=['Catégorie', 'Taux Conformité (%)']),
        'top_non_conformities_df': pd.DataFrame(columns=['Point de Contrôle', 'Nombre Occurrences']),
        'action_status_df': pd.DataFrame(columns=['Statut', 'Nombre']),
        'overall_compliance_rate': 0.0
    }

    if not st.session_state.loaded_inspections:
        return metrics # Retourner les métriques initialisées si aucune donnée

    # Itération sur les données chargées pour calculer les métriques
    for data in st.session_state.loaded_inspections:
        inspection = data['inspection']
        model = data['model']
        inspection_id = inspection['id']

        for result in inspection.get('results', []):
            point_id = result.get('idPoint')
            if not point_id: continue

            point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)

            if not point_model or result.get('isNA', False):
                continue # Ignorer points non trouvés ou N/A

            metrics['total_points_checked'] += 1
            category = point_model.get('Categorie', 'Sans Catégorie')

            # Initialiser la catégorie si nécessaire
            if category not in metrics['conformity_by_category']:
                metrics['conformity_by_category'][category] = {'conform': 0, 'checked': 0}
            metrics['conformity_by_category'][category]['checked'] += 1

            is_poi = is_point_of_interest(result, point_model)

            if is_poi:
                metrics['total_points_of_interest'] += 1
                action_key = (inspection_id, point_id)
                status = st.session_state.corrective_actions.get(action_key, {}).get('status', 'À traiter')
                if status in metrics['action_status_counts']:
                    metrics['action_status_counts'][status] += 1

                point_name = point_model.get('PointDeControle', 'N/A')
                metrics['non_conformity_counts_by_point'][point_name] = metrics['non_conformity_counts_by_point'].get(point_name, 0) + 1
            else:
                # Point vérifié et non 'd'intérêt' => Conforme
                metrics['total_points_conform'] += 1
                metrics['conformity_by_category'][category]['conform'] += 1

    # --- Calculs finaux et préparation des DataFrames pour Plotly ---
    if metrics['total_points_checked'] > 0:
        metrics['overall_compliance_rate'] = (metrics['total_points_conform'] / metrics['total_points_checked'] * 100)

    # Taux de conformité par catégorie
    cat_rates_data = []
    for name, data in metrics['conformity_by_category'].items():
        rate = (data['conform'] / data['checked'] * 100) if data['checked'] > 0 else 0.0
        cat_rates_data.append({'Catégorie': name, 'Taux Conformité (%)': rate})
    if cat_rates_data:
        metrics['category_compliance_rates_df'] = pd.DataFrame(cat_rates_data).sort_values(by='Catégorie')

    # Top 5 points non conformes
    if metrics['non_conformity_counts_by_point']:
        metrics['top_non_conformities_df'] = pd.DataFrame(
            metrics['non_conformity_counts_by_point'].items(), columns=['Point de Contrôle', 'Nombre Occurrences']
        ).nlargest(5, 'Nombre Occurrences')

    # Répartition des statuts d'action
    if sum(metrics['action_status_counts'].values()) > 0:
        metrics['action_status_df'] = pd.DataFrame(
             metrics['action_status_counts'].items(), columns=['Statut', 'Nombre']
         ).sort_values(by='Statut')

    return metrics


def prepare_export_data() -> List[Dict]:
    """
    Prépare la liste complète des données d'inspection chargées, en ajoutant
    les informations de statut et note d'action corrective les plus récentes
    depuis st.session_state.corrective_actions.

    Returns:
        Une liste de dictionnaires, chaque dictionnaire représentant une inspection
        complète (incluant 'inspection', 'model', 'filename', et les champs
        'statutAction'/'noteAction' ajoutés aux résultats pertinents).
    """
    updated_inspections_list = []
    # Utiliser une copie profonde pour éviter de modifier l'état original en place
    import copy
    inspections_to_export = copy.deepcopy(st.session_state.loaded_inspections)

    for data in inspections_to_export:
        inspection_id = data['inspection']['id']
        # Itérer sur les résultats pour ajouter les infos d'action corrective
        if 'results' in data['inspection'] and isinstance(data['inspection']['results'], list):
            for result in data['inspection']['results']:
                # S'assurer que result est un dictionnaire et a un idPoint
                if isinstance(result, dict) and 'idPoint' in result:
                    point_id = result.get('idPoint')
                    action_key = (inspection_id, point_id)
                    # Ajouter les champs si une action corrective existe pour ce point
                    if action_key in st.session_state.corrective_actions:
                        action_info = st.session_state.corrective_actions[action_key]
                        result['statutAction'] = action_info.get('status')
                        result['noteAction'] = action_info.get('note')
                    # Optionnel: Ne pas ajouter les champs si aucune action n'est enregistrée
                    # ou ajouter des valeurs par défaut si nécessaire pour la structure de sortie
                    # else:
                    #     result['statutAction'] = None # ou 'Non applicable' etc.
                    #     result['noteAction'] = None

        updated_inspections_list.append(data)
    return updated_inspections_list

def create_export_zip(export_data: List[Dict]) -> bytes:
    """
    Crée un fichier ZIP en mémoire contenant un unique fichier 'aggregated_export.json'
    qui est la sérialisation JSON de la liste des données d'inspection fournies.

    Args:
        export_data: La liste des dictionnaires d'inspection à exporter.

    Returns:
        Les bytes du fichier ZIP généré, ou des bytes vides en cas d'erreur.
    """
    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Créer le contenu JSON, gérer les types non sérialisables comme datetime
            def default_serializer(obj):
                if isinstance(obj, (datetime, pd.Timestamp)):
                    return obj.isoformat()
                # Ajouter d'autres types si nécessaire
                raise TypeError(f"Type {type(obj)} not serializable")

            json_string = json.dumps(export_data, indent=2, ensure_ascii=False, default=default_serializer)
            # Ajouter le fichier JSON au ZIP
            zip_file.writestr("aggregated_export.json", json_string)
    except Exception as e:
        st.error(f"Erreur lors de la création du fichier ZIP : {e}")
        return b"" # Retourner des bytes vides en cas d'erreur

    # Se positionner au début du buffer avant de lire sa valeur
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

# --- Interface Utilisateur Streamlit ---

st.title("📊 Visualiseur et Analyseur d'Inspections")
st.caption("Chargez des packages d'inspection (.zip) pour visualiser, agréger et analyser les données.")

# -- Barre Latérale --
with st.sidebar:
    st.header("Chargement des Données")
    # Widget pour uploader les fichiers
    uploaded_files = st.file_uploader(
        "Sélectionner un ou plusieurs packages (.zip)",
        type='zip',
        accept_multiple_files=True,
        key="file_uploader", # Clé unique pour ce widget
        help="Chargez les fichiers .zip contenant 'inspection_data.json'"
    )

    # Bouton pour déclencher le traitement après sélection
    if uploaded_files:
        # Utiliser un bouton pour que le traitement ne se fasse qu'au clic
        if st.button("Traiter les Fichiers Chargés"):
            with st.spinner("Traitement des fichiers..."):
                load_zip_data(uploaded_files)
            # Forcer un rerun pour rafraîchir l'interface et vider l'état visuel de l'uploader
            st.rerun()

    st.divider()

    # Actions globales si des données sont chargées
    if st.session_state.loaded_inspections:
        st.header("Actions Globales")
        # Bouton pour vider toutes les données
        if st.button("⚠️ Vider Toutes les Données Chargées"):
            # Demander confirmation via une modale serait plus sûr pour une action destructive
            # Pour l'instant, action directe après clic
            st.session_state.loaded_inspections = []
            st.session_state.corrective_actions = {}
            st.session_state.selected_inspection_id_for_detail = None
            st.session_state.show_detail_dialog = False
            st.session_state.export_data_prepared = None
            st.session_state.aggregated_page_number = 1 # Réinitialiser la pagination
            st.toast("Toutes les données ont été vidées.", icon="🗑️")
            st.rerun()

        st.divider()
        st.header("Export")
        st.caption("Exporte toutes les inspections chargées avec les derniers statuts/notes d'action corrective ajoutés dans cette session.")

        # Bouton pour préparer les données d'export
        if st.button("Préparer l'Export Agrégé"):
             with st.spinner("Préparation de l'export..."):
                try:
                    export_list = prepare_export_data()
                    zip_bytes = create_export_zip(export_list)
                    if zip_bytes: # Vérifier si la création du zip a réussi
                        st.session_state.export_data_prepared = zip_bytes
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        st.session_state.export_filename = f"export_agregé_{timestamp}.zip"
                        st.toast("Export prêt à être téléchargé.", icon="✅")
                    # else: l'erreur a déjà été affichée dans create_export_zip
                except Exception as prep_e:
                    st.error(f"Erreur lors de la préparation de l'export: {prep_e}")
                    st.session_state.export_data_prepared = None # Assurer que le bouton de DL ne s'affiche pas

        # Afficher le bouton de téléchargement seulement si les données sont prêtes
        if st.session_state.export_data_prepared:
            st.download_button(
                label="⬇️ Télécharger le Package Agrégé (.zip)",
                data=st.session_state.export_data_prepared,
                file_name=st.session_state.export_filename,
                mime="application/zip",
                key="download_export_button"
                # Au clic, le téléchargement est lancé par Streamlit
            )


# -- Contenu Principal avec Onglets --
if not st.session_state.loaded_inspections:
    st.info("👋 Bienvenue ! Commencez par charger un ou plusieurs packages d'inspection (.zip) via la barre latérale.")
else:
    # Définition des onglets
    tab_titles = [
        "📈 Tableau de Bord",
        f"📋 Liste Inspections ({len(st.session_state.loaded_inspections)})",
        "🔍 Vue Agrégée"
    ]
    tab_dashboard, tab_list, tab_aggregated = st.tabs(tab_titles)

    # --- Onglet Tableau de Bord ---
    with tab_dashboard:
        st.subheader("📈 Tableau de Bord Synthétique")
        # Calculer les métriques à chaque affichage de l'onglet
        metrics = calculate_dashboard_metrics()

        # Affichage des KPIs
        kpi_cols = st.columns(3)
        kpi_cols[0].metric("Inspections Chargées", metrics['total_inspections'])
        kpi_cols[1].metric("Points d'Intérêt Trouvés", metrics['total_points_of_interest'])
        kpi_cols[2].metric("Taux Conformité Global", f"{metrics['overall_compliance_rate']:.1f}%",
                           help="Calculé sur les points vérifiés (non N/A)")

        st.divider()

        # Affichage des Graphiques
        chart_cols = st.columns(2)
        with chart_cols[0]:
            st.markdown("**Répartition Statuts Action**")
            # Afficher le graphique seulement si des données existent
            if not metrics['action_status_df'].empty and metrics['action_status_df']['Nombre'].sum() > 0:
                fig_pie = px.pie(metrics['action_status_df'], names='Statut', values='Nombre',
                                 title="Statuts des Actions Correctives", hole=0.3)
                fig_pie.update_layout(legend_title_text='Statut')
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.caption("Aucune action corrective à afficher.")

            st.markdown(f"**Top {len(metrics['top_non_conformities_df'])} Points Non-Conformes**")
            if not metrics['top_non_conformities_df'].empty:
                 # Trier pour affichage correct dans barres horizontales
                 df_top_nc = metrics['top_non_conformities_df'].sort_values(by='Nombre Occurrences', ascending=True)
                 fig_bar_nc = px.bar(df_top_nc,
                                  x='Nombre Occurrences', y='Point de Contrôle', orientation='h',
                                  title="Points les plus fréquents en Non-Conformité / Hors Plage")
                 fig_bar_nc.update_layout(yaxis_title=None, xaxis_title="Nombre d'occurrences")
                 st.plotly_chart(fig_bar_nc, use_container_width=True)
            else:
                 st.caption("Aucune non-conformité trouvée.")

        with chart_cols[1]:
            st.markdown("**Taux de Conformité par Catégorie**")
            if not metrics['category_compliance_rates_df'].empty:
                fig_bar_cat = px.bar(metrics['category_compliance_rates_df'], x='Catégorie', y='Taux Conformité (%)',
                                     title="Conformité par Catégorie", range_y=[0, 100],
                                     color='Taux Conformité (%)', # Colorer par valeur
                                     color_continuous_scale=px.colors.sequential.Greens) # Palette de couleurs
                fig_bar_cat.update_layout(xaxis_tickangle=-45, yaxis_title="Taux de Conformité (%)")
                st.plotly_chart(fig_bar_cat, use_container_width=True)
            else:
                st.caption("Aucune donnée de catégorie à afficher.")

    # --- Onglet Liste des Inspections ---
    with tab_list:
        st.subheader(f"📋 Liste des Inspections Chargées ({len(st.session_state.loaded_inspections)})")

        if not st.session_state.loaded_inspections:
            st.info("Aucune inspection chargée.")
        else:
            # Afficher chaque inspection dans un expander
            for index, data in enumerate(st.session_state.loaded_inspections):
                inspection = data['inspection']
                model = data['model']
                filename = data['filename']
                inspection_id = inspection['id']

                # Clé unique pour l'expander
                expander_key = f"expander_{inspection_id}_{index}"
                with st.expander(f"**{model.get('name', 'N/A')}** par **{inspection.get('inspectorName', 'N/A')}** (ID: ...{inspection_id[-8:]})", expanded=False):
                    # Afficher quelques métadonnées directement dans l'expander
                    exp_cols = st.columns([3, 1])
                    with exp_cols[0]:
                        start_date_str = pd.to_datetime(inspection.get('startDate')).strftime('%d/%m/%Y %H:%M') if inspection.get('startDate') else 'N/A'
                        st.caption(f"Fichier: {filename} | Statut: {inspection.get('status', 'N/A')} | Début: {start_date_str}")
                    with exp_cols[1]:
                        # Boutons d'action avec des clés uniques
                        if st.button("👁️ Voir Détails", key=f"detail_{inspection_id}_{index}"):
                            st.session_state.selected_inspection_id_for_detail = inspection_id
                            st.session_state.show_detail_dialog = True
                            st.rerun() # Forcer rerun pour ouvrir la modale

                        if st.button("🗑️ Retirer", key=f"remove_{inspection_id}_{index}", type="secondary"):
                            # Logique de suppression
                            st.session_state.loaded_inspections = [insp for insp in st.session_state.loaded_inspections if insp['inspection']['id'] != inspection_id]
                            keys_to_remove = [key for key in st.session_state.corrective_actions if key[0] == inspection_id]
                            for key in keys_to_remove:
                                del st.session_state.corrective_actions[key]
                            st.toast(f"Inspection ...{inspection_id[-8:]} retirée.", icon="🗑️")
                            if st.session_state.selected_inspection_id_for_detail == inspection_id:
                                st.session_state.selected_inspection_id_for_detail = None
                                st.session_state.show_detail_dialog = False
                            st.rerun()

    # --- Onglet Vue Agrégée ---
    with tab_aggregated:
        st.subheader("🔍 Vue Agrégée des Points d'Intérêt")
        st.caption("Affiche les points 'Non Conforme' ou 'Hors Plage'. Les colonnes 'Statut Action' et 'Note Action' sont modifiables pour cette session.")

        # Préparer le DataFrame complet (contient tous les points d'intérêt)
        aggregated_df_full = prepare_aggregated_dataframe()

        # Filtres pour le DataFrame
        st.markdown("**Filtres :**")
        filter_cols = st.columns([2, 1, 1, 1, 1]) # Ajuster les largeurs relatives
        with filter_cols[0]:
            search_term = st.text_input("Recherche libre (Point, Commentaire, Note...)", key="agg_search")
        with filter_cols[1]:
            # Utiliser les catégories uniques du DF complet pour le filtre
            categories = [''] + sorted(aggregated_df_full['Catégorie'].astype(str).unique())
            selected_category = st.selectbox("Catégorie", options=categories, key="agg_cat_filter")
        with filter_cols[2]:
             # Utiliser les inspecteurs uniques du DF complet
            inspectors = [''] + sorted(aggregated_df_full['Inspecteur'].astype(str).unique())
            selected_inspector = st.selectbox("Inspecteur", options=inspectors, key="agg_insp_filter")
        with filter_cols[3]:
             # Utiliser les points uniques du DF complet
            points_ctrl = [''] + sorted(aggregated_df_full['Point de Contrôle'].astype(str).unique())
            selected_point = st.selectbox("Point Contrôle", options=points_ctrl, key="agg_point_filter")
        with filter_cols[4]:
            action_statuses = [''] + ['À traiter', 'En cours', 'Terminé', 'Annulé']
            selected_action_status = st.selectbox("Statut Action", options=action_statuses, key="agg_status_filter")

        # Appliquer les filtres sur une copie du DataFrame
        filtered_df = aggregated_df_full.copy()
        # Filtrage Texte Libre (insensible à la casse)
        if search_term:
            search_term_lower = search_term.lower()
            # Appliquer la recherche sur plusieurs colonnes pertinentes
            text_search_cols = ['Point de Contrôle', 'Commentaire', 'Note Action', 'Résultat Obtenu', 'Critère Accept.']
            mask = pd.Series([False] * len(filtered_df)) # Initialiser le masque
            for col in text_search_cols:
                if col in filtered_df.columns:
                     # S'assurer que la colonne est de type string avant d'appliquer .str
                     mask |= filtered_df[col].astype(str).str.lower().str.contains(search_term_lower, na=False)
            filtered_df = filtered_df[mask]

        # Filtrage par Selectbox
        if selected_category:
            filtered_df = filtered_df[filtered_df['Catégorie'] == selected_category]
        if selected_inspector:
            filtered_df = filtered_df[filtered_df['Inspecteur'] == selected_inspector]
        if selected_point:
            filtered_df = filtered_df[filtered_df['Point de Contrôle'] == selected_point]
        if selected_action_status:
            filtered_df = filtered_df[filtered_df['Statut Action'] == selected_action_status]

        st.divider()

        # Affichage avec st.data_editor et Pagination
        total_items = len(filtered_df)
        if total_items == 0:
            if not aggregated_df_full.empty:
                 st.warning("Aucun point d'intérêt ne correspond aux filtres actuels.")
            else:
                 st.info("Aucun point d'intérêt trouvé dans les inspections chargées.")
        else:
            st.markdown(f"**{total_items}** point(s) d'intérêt trouvé(s)")

            # --- Logique de Pagination ---
            total_pages = max(1, (total_items + ITEMS_PER_PAGE_AGGREGATED - 1) // ITEMS_PER_PAGE_AGGREGATED)
            # Assurer que la page actuelle est valide
            current_page = min(st.session_state.aggregated_page_number, total_pages)
            st.session_state.aggregated_page_number = current_page # Mettre à jour si elle a été ajustée

            start_idx = (current_page - 1) * ITEMS_PER_PAGE_AGGREGATED
            end_idx = start_idx + ITEMS_PER_PAGE_AGGREGATED
            # Sélectionner la tranche de données pour la page actuelle
            # Utiliser .iloc pour le slicing basé sur la position entière
            paginated_df = filtered_df.iloc[start_idx:end_idx]

            # Afficher le data editor avec les données paginées
            edited_df_slice = st.data_editor(
                paginated_df,
                key="aggregated_data_editor", # Clé unique pour l'éditeur
                use_container_width=True,
                hide_index=True, # Cacher l'index pandas
                # Configuration des colonnes pour l'édition et l'affichage
                column_config={
                    "inspection_id_hidden": None, # Cacher
                    "point_id_hidden": None, # Cacher
                    "ID Unique": None, # Cacher
                    "Date Insp.": st.column_config.DateColumn("Date Insp.", format="DD/MM/YYYY", disabled=True),
                    "ID Insp.": st.column_config.TextColumn("ID Insp.", help="Début de l'ID de l'inspection", disabled=True),
                    "Inspecteur": st.column_config.TextColumn("Inspecteur", disabled=True),
                    "Catégorie": st.column_config.TextColumn("Catégorie", disabled=True),
                    "Point de Contrôle": st.column_config.TextColumn("Point Contrôle", width="medium", disabled=True),
                    "Critère Accept.": st.column_config.TextColumn("Critère", width="small", disabled=True), # Raccourci titre
                    "Résultat Obtenu": st.column_config.TextColumn("Résultat", width="small", disabled=True), # Raccourci titre
                    "Commentaire": st.column_config.TextColumn("Commentaire", width="medium", disabled=True),
                    "Nb Photos": st.column_config.NumberColumn("Photos", format="%d 📷", disabled=True), # Raccourci titre
                    "Statut Action": st.column_config.SelectboxColumn(
                        "Statut Action",
                        help="Statut du suivi de l'action corrective",
                        options=['À traiter', 'En cours', 'Terminé', 'Annulé'],
                        required=True # Rendre obligatoire la sélection
                    ),
                    "Note Action": st.column_config.TextColumn(
                        "Note Action",
                        help="Note libre sur l'action corrective (max 200 caractères)",
                        max_chars=200,
                        width="large" # Donner plus de place à la note
                    ),
                },
                # Définir l'ordre souhaité des colonnes visibles
                column_order=[
                    "Date Insp.", "Inspecteur", "Catégorie", "Point de Contrôle",
                    "Résultat Obtenu", "Commentaire", "Nb Photos",
                    "Statut Action", "Note Action", "ID Insp.", "Critère Accept."
                ],
                num_rows="fixed" # Ajuster la hauteur si nécessaire, ou "dynamic"
            )

            # --- Mise à jour de l'état après édition ---
            # Comparer la tranche éditée avec la tranche originale (avant édition) pour détecter les changements
            # Il faut s'assurer que la comparaison se fait sur les mêmes index et colonnes pertinentes
            # Note: La comparaison directe avec paginated_df peut être trompeuse si les types ont changé.
            # Une approche plus sûre est de toujours appeler la fonction de mise à jour,
            # qui vérifiera en interne si les valeurs ont réellement changé dans st.session_state.corrective_actions.
            update_corrective_actions_from_df(edited_df_slice)

            # --- Contrôles de Pagination ---
            st.divider()
            if total_pages > 1:
                pagination_cols = st.columns([1, 2, 1]) # Ratio pour les boutons et le texte
                with pagination_cols[0]: # Bouton Précédent
                    if st.button("⬅️ Précédent", disabled=(current_page <= 1), key="agg_prev_page"):
                        st.session_state.aggregated_page_number -= 1
                        st.rerun() # Re-exécuter pour afficher la page précédente
                with pagination_cols[1]: # Affichage du numéro de page
                    st.markdown(f"<div style='text-align: center;'>Page **{current_page}** sur **{total_pages}**</div>", unsafe_allow_html=True)
                    # st.write(f"Page **{current_page}** sur **{total_pages}** (Éléments {start_idx + 1} - {min(end_idx, total_items)} sur {total_items})") # Version plus détaillée
                with pagination_cols[2]: # Bouton Suivant
                    if st.button("Suivant ➡️", disabled=(current_page >= total_pages), key="agg_next_page"):
                        st.session_state.aggregated_page_number += 1
                        st.rerun() # Re-exécuter pour afficher la page suivante


# --- Affichage de la Modale de Détail (déclenché depuis l'onglet Liste) ---
if st.session_state.show_detail_dialog and st.session_state.selected_inspection_id_for_detail:
    # Trouver l'inspection correspondante dans l'état
    inspection_to_show = next((insp for insp in st.session_state.loaded_inspections if insp['inspection']['id'] == st.session_state.selected_inspection_id_for_detail), None)

    if inspection_to_show:
        # Utiliser st.dialog pour une expérience modale
        # Retrait de l'argument 'dismissed' pour éviter l'erreur TypeError
        @st.dialog("Détails de l'Inspection")
        def show_detail_modal():
            render_inspection_detail(inspection_to_show) # Appeler la fonction de rendu
            if st.button("Fermer", key="close_detail_dialog_button"):
                 # Utiliser setattr pour modifier l'état dans le callback du bouton
                 setattr(st.session_state, 'show_detail_dialog', False)
                 st.rerun() # Forcer le rerun pour fermer la modale

        # Appeler la fonction décorée pour effectivement afficher la modale
        show_detail_modal()
    else:
        # Gérer le cas où l'ID sélectionné n'est plus valide
        st.session_state.selected_inspection_id_for_detail = None
        st.session_state.show_detail_dialog = False
        st.warning("L'inspection sélectionnée pour le détail n'est plus disponible.")
        # Pas besoin de rerun ici car l'état est déjà réinitialisé pour la prochaine exécution

# --- Affichage de la Modale Photo (déclenché depuis la vue détail) ---
if st.session_state.show_photo_modal and st.session_state.modal_photo_list:
    # Retrait de l'argument 'dismissed' pour éviter l'erreur TypeError
    @st.dialog("Visualiseur de Photos")
    def show_photo_viewer():
        st.subheader(st.session_state.modal_photo_caption)
        current_index = st.session_state.modal_photo_index
        photos = st.session_state.modal_photo_list
        num_photos = len(photos)

        # Afficher l'image actuelle
        try:
            b64_string = photos[current_index]
            # Nettoyer la string base64 (enlever le préfixe si présent)
            if isinstance(b64_string, str) and ',' in b64_string:
                b64_string = b64_string.split(',')[1]
            img_bytes = base64.b64decode(b64_string)
            # Afficher l'image en utilisant la largeur de la colonne/modale
            st.image(img_bytes, use_column_width=True)
        except Exception as e:
            st.error(f"Impossible d'afficher l'image {current_index + 1}: {e}")

        # Ajouter la navigation si plusieurs photos
        if num_photos > 1:
            nav_cols = st.columns([1, 2, 1]) # Boutons Préc/Suiv et compteur
            with nav_cols[0]:
                if st.button("⬅️ Précédent", disabled=(current_index == 0), key="prev_photo"):
                    st.session_state.modal_photo_index -= 1
                    st.rerun() # Re-exécuter pour afficher la nouvelle image
            with nav_cols[1]:
                st.write(f"Photo {current_index + 1} / {num_photos}")
            with nav_cols[2]:
                if st.button("Suivant ➡️", disabled=(current_index == num_photos - 1), key="next_photo"):
                    st.session_state.modal_photo_index += 1
                    st.rerun() # Re-exécuter pour afficher la nouvelle image

        # Bouton Fermer la modale photo
        if st.button("Fermer", key="close_photo_modal_button"):
            # Utiliser setattr pour modifier l'état dans le callback du bouton
            setattr(st.session_state, 'show_photo_modal', False)
            st.rerun()

    # Appeler la fonction pour afficher la modale photo
    show_photo_viewer()


# --- Pied de page (optionnel) ---
st.divider()
st.caption("Application Visualiseur d'Inspections v1.1 (Pagination, Modale Photo) - Mode Volatile")
st.caption("Les statuts et notes d'actions correctives sont conservés uniquement pendant cette session.")

