# visualizer_app_enhanced.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import zipfile
import io
import json
import base64
from PIL import Image, UnidentifiedImageError
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union

# --- Configuration de la Page Streamlit ---
st.set_page_config(
    page_title="Visualiseur d'Inspections",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Constantes ---
ITEMS_PER_PAGE_AGGREGATED = 50

# --- Initialisation de l'État de Session ---
default_session_state = {
    'loaded_inspections': [],
    'corrective_actions': {},
    'selected_inspection_id_for_detail': None,
    'show_detail_dialog': False,
    'export_data_prepared': None,
    'export_filename': "",
    'show_photo_modal': False,
    'modal_photo_list': [],
    'modal_photo_index': 0,
    'modal_photo_caption': "",
    'aggregated_page_number': 1,
    # États pour les filtres (pour pouvoir les réinitialiser)
    'agg_search': '',
    'agg_cat_filter': '',
    'agg_insp_filter': '',
    'agg_point_filter': '',
    'agg_status_filter': '',
    'agg_problem_type_filter': '' # Nouveau filtre
}
for key, default_value in default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- Fonctions Utilitaires ---

def get_problem_type_and_display(result_data: Optional[Dict], point_model: Optional[Dict]) -> Tuple[str, str]:
    """
    Détermine le type de problème et le format d'affichage pour un résultat.

    Returns:
        Tuple[str, str]: (Type de Problème, Résultat formaté pour affichage).
                         Type Problème: "Conforme", "Non Conforme", "Inférieur Min", "Supérieur Max", "N/A", "Erreur Valeur/Plage", "Inconnu".
    """
    if not result_data or not point_model:
        return "Inconnu", ""
    if result_data.get('isNA', False):
        return "N/A", "N/A"

    result_value = result_data.get('result')
    result_display = str(result_value) if result_value is not None else ''

    if result_value == 'Non Conforme':
        return "Non Conforme", f"🔴 {result_display}" # Emoji ajouté
    if result_value == 'Conforme':
        return "Conforme", f"✅ {result_display}" # Emoji ajouté

    # Vérification Plage Numérique
    if point_model.get('TypeParametre') == 'Plage_Numerique' and result_value is not None:
        try:
            value = float(str(result_value).replace(',','.'))
            options_str = point_model.get('OptionsParametre', '')
            if options_str:
                options = options_str.split(';')
                if len(options) == 2:
                    min_val, max_val = map(float, options)
                    range_str = f" [Plage: {min_val}-{max_val}]"
                    if value < min_val:
                        return "Inférieur Min", f"⬇️ {result_display}{range_str}"
                    elif value > max_val:
                        return "Supérieur Max", f"⬆️ {result_display}{range_str}"
                    else: # Dans la plage mais peut-être non 'Conforme' formellement? On le traite comme conforme ici.
                         return "Conforme (Plage OK)", f"✅ {result_display}" # Ou juste result_display
        except (ValueError, TypeError):
            return "Erreur Valeur/Plage", f"⚠️ {result_display} (Erreur plage)" # Indiquer l'erreur

    # Cas par défaut (texte, date, etc.)
    return "Conforme", result_display # Par défaut, si pas NC ou hors plage, considéré conforme pour le type

def is_point_of_interest_enhanced(result_data: Optional[Dict], point_model: Optional[Dict]) -> bool:
    """Vérifie si un point est d'intérêt (Non Conforme, Hors Plage)."""
    problem_type, _ = get_problem_type_and_display(result_data, point_model)
    return problem_type in ["Non Conforme", "Inférieur Min", "Supérieur Max", "Erreur Valeur/Plage"]

def load_zip_data(uploaded_files: List[st.runtime.uploaded_file_manager.UploadedFile]) -> None:
    """Traite les ZIPs uploadés."""
    newly_loaded_count, duplicate_count, error_count = 0, 0, 0
    current_inspection_ids = {insp['inspection']['id'] for insp in st.session_state.loaded_inspections}

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        try:
            with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue()), 'r') as zip_ref:
                if "inspection_data.json" not in zip_ref.namelist(): raise ValueError("Fichier 'inspection_data.json' introuvable")
                package_data = json.loads(zip_ref.read("inspection_data.json"))

                # Validation structurelle
                if not isinstance(package_data, dict) or \
                   not all(k in package_data for k in ['inspection', 'model']) or \
                   not isinstance(package_data['inspection'], dict) or \
                   not all(k in package_data['inspection'] for k in ['id', 'modelId', 'startDate', 'results']) or \
                   not isinstance(package_data['model'], dict) or \
                   not all(k in package_data['model'] for k in ['name', 'items']) or \
                   not isinstance(package_data['inspection']['results'], list) or \
                   not isinstance(package_data['model']['items'], list):
                   raise ValueError("Structure JSON invalide ou incomplète")

                inspection_id = package_data['inspection']['id']
                if not isinstance(inspection_id, str) or not inspection_id: raise ValueError("ID d'inspection manquant ou invalide")

                if inspection_id in current_inspection_ids:
                    st.warning(f"'{filename}' ignoré: ID '{inspection_id[:8]}...' déjà chargé.")
                    duplicate_count += 1; continue

                # Stockage
                st.session_state.loaded_inspections.append({"inspection": package_data['inspection'], "model": package_data['model'], "filename": filename})
                current_inspection_ids.add(inspection_id)
                newly_loaded_count += 1

                # Initialisation actions correctives
                for result in package_data['inspection'].get('results', []):
                    point_id = result.get('idPoint')
                    if not point_id: continue
                    point_model = next((item for item in package_data['model'].get('items', []) if item.get('ID_Point') == point_id), None)
                    # Utiliser la nouvelle fonction is_point_of_interest_enhanced
                    if is_point_of_interest_enhanced(result, point_model):
                        action_key = (inspection_id, point_id)
                        if action_key not in st.session_state.corrective_actions:
                            st.session_state.corrective_actions[action_key] = {'status': 'À traiter', 'note': ''}

        except (json.JSONDecodeError, zipfile.BadZipFile, ValueError, Exception) as e:
            st.error(f"Erreur traitement '{filename}': {e}")
            error_count += 1

    # Feedback
    if newly_loaded_count > 0: st.success(f"{newly_loaded_count} inspection(s) chargée(s).")
    if duplicate_count > 0: st.info(f"{duplicate_count} inspection(s) étaient déjà chargées.")
    if error_count > 0: st.warning(f"{error_count} fichier(s) non traités.")

def prepare_aggregated_dataframe() -> pd.DataFrame:
    """Crée le DataFrame Pandas agrégé avec la nouvelle colonne 'Type Problème'."""
    data_for_df = []
    expected_columns = [
        'ID Unique', 'Date Insp.', 'ID Insp.', 'Inspecteur', 'Catégorie',
        'Point de Contrôle', 'Type Problème', # Nouvelle colonne
        'Résultat Obtenu', 'Commentaire',
        'Photos Str', 'Statut Action', 'Note Action',
        'inspection_id_hidden', 'point_id_hidden', 'Critère Accept.' # Critère ajouté pour recherche
    ]

    if not st.session_state.loaded_inspections:
        return pd.DataFrame(columns=expected_columns)

    for data in st.session_state.loaded_inspections:
        inspection, model, inspection_id = data['inspection'], data['model'], data['inspection']['id']

        for result in inspection.get('results', []):
            point_id = result.get('idPoint')
            if not point_id: continue
            point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)

            # Utiliser la fonction améliorée pour déterminer si c'est un POI
            if is_point_of_interest_enhanced(result, point_model):
                action_key = (inspection_id, point_id)
                action_info = st.session_state.corrective_actions.get(action_key, {'status': 'À traiter', 'note': ''})
                problem_type, result_display_formatted = get_problem_type_and_display(result, point_model) # Récupérer les deux valeurs

                nb_photos = len(result.get('photosBase64', []))
                photos_str = f"📷 {nb_photos}" if nb_photos > 0 else "—"

                data_for_df.append({
                    'ID Unique': f"{inspection_id[:8]}_{point_id}",
                    'Date Insp.': pd.to_datetime(inspection.get('startDate'), errors='coerce').date() if inspection.get('startDate') else None,
                    'ID Insp.': inspection_id[:8] + "...",
                    'Inspecteur': inspection.get('inspectorName', 'N/A'),
                    'Catégorie': point_model.get('Categorie', 'N/A') if point_model else 'N/A',
                    'Point de Contrôle': point_model.get('PointDeControle', 'N/A') if point_model else 'N/A',
                    'Critère Accept.': point_model.get('CritereAcceptation', 'N/A') if point_model else 'N/A', # Pour recherche
                    'Type Problème': problem_type, # Ajout
                    'Résultat Obtenu': result_display_formatted, # Utiliser la version formatée
                    'Commentaire': result.get('comment', ''),
                    'Photos Str': photos_str, # Utiliser la version formatée
                    'Statut Action': action_info.get('status', 'À traiter'),
                    'Note Action': action_info.get('note', ''),
                    'inspection_id_hidden': inspection_id,
                    'point_id_hidden': point_id
                })

    if not data_for_df: return pd.DataFrame(columns=expected_columns)
    df = pd.DataFrame(data_for_df)
    if 'Date Insp.' in df.columns: df['Date Insp.'] = pd.to_datetime(df['Date Insp.'])
    return df

def update_corrective_actions_from_df(edited_df: pd.DataFrame) -> None:
    """Met à jour st.session_state.corrective_actions depuis le DF édité."""
    updates_made = 0
    required_cols = ['inspection_id_hidden', 'point_id_hidden', 'Statut Action', 'Note Action']
    if not all(col in edited_df.columns for col in required_cols):
        if not edited_df.empty: st.error("Err. interne: Colonnes manquantes pour màj actions.")
        return

    for _, row in edited_df.iterrows():
        action_key = (row['inspection_id_hidden'], row['point_id_hidden'])
        current_status = row['Statut Action']
        current_note = row['Note Action'] if pd.notna(row['Note Action']) else ""
        previous_action = st.session_state.corrective_actions.get(action_key, {'status': 'N/A', 'note': 'N/A'}) # Comparaison sûre

        if previous_action['status'] != current_status or previous_action['note'] != current_note:
            st.session_state.corrective_actions[action_key] = {'status': current_status, 'note': current_note}
            updates_made += 1

    # if updates_made > 0: st.toast(f"{updates_made} màj actions enregistrée(s).", icon="📝") # Peut devenir bruyant

# --- Fonction de Rendu Vue Détaillée (avec mise en évidence) ---
def render_inspection_detail(inspection_data: Dict) -> None:
    """Affiche les détails d'une inspection avec mise en évidence des POI."""
    inspection, model, filename = inspection_data['inspection'], inspection_data['model'], inspection_data['filename']
    st.subheader(f"Détails: {model.get('name', 'N/A')}")
    st.caption(f"Fichier: {filename} | ID: {inspection.get('id', 'N/A')}")

    meta_cols = st.columns(2)
    with meta_cols[0]: st.write(f"**Inspecteur:** {inspection.get('inspectorName', 'N/A')}"); start_date = inspection.get('startDate'); st.write(f"**Début:** {pd.to_datetime(start_date).strftime('%d/%m/%Y %H:%M') if start_date else 'N/A'}")
    with meta_cols[1]: st.write(f"**Statut:** {inspection.get('status', 'N/A')}"); end_date = inspection.get('endDate'); st.write(f"**Fin:** {pd.to_datetime(end_date).strftime('%d/%m/%Y %H:%M') if end_date else 'N/A'}")
    st.divider()

    points_by_category = {}
    for item in model.get('items', []):
        cat = item.get('Categorie', 'Sans Catégorie'); points_by_category.setdefault(cat, []).append(item)
    if not points_by_category: st.warning("Aucun point de contrôle trouvé."); return

    for category, items in sorted(points_by_category.items()):
        with st.expander(f"**{category}** ({len(items)} points)", expanded=False):
            for point_model in items:
                point_id = point_model.get('ID_Point')
                result_data = next((r for r in inspection.get('results', []) if isinstance(r, dict) and r.get('idPoint') == point_id), None)

                # *** Amélioration: Mise en évidence POI ***
                is_poi = is_point_of_interest_enhanced(result_data, point_model) if result_data else False
                div_style = "border: 1px solid #eee; padding: 12px; margin-bottom: 12px; border-radius: 8px;"
                if is_poi: div_style += " background-color: #fff2f2; border-left: 5px solid #e53e3e;" # Rouge Tailwind 600

                st.markdown(f"<div style='{div_style}'>", unsafe_allow_html=True) # Ouvrir div

                st.markdown(f"**{point_model.get('PointDeControle', 'N/A')}** (ID: {point_id})")
                st.caption(f"Desc: {point_model.get('Description', 'N/A')} | Critère: {point_model.get('CritereAcceptation', 'N/A')}")

                if result_data:
                    res_col1, res_col2 = st.columns([1, 2])
                    with res_col1: # Résultat formaté
                        problem_type, result_display = get_problem_type_and_display(result_data, point_model)
                        if problem_type == "N/A": st.markdown(f"Résultat: *N/A*")
                        else: st.markdown(f"Résultat: {result_display}", unsafe_allow_html=True) # HTML pour les emojis/couleurs

                    with res_col2: # Commentaire
                        st.markdown(f"**Commentaire:** {result_data.get('comment') or 'Aucun'}")

                    # Photos avec bouton Agrandir
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

                                    button_key = f"view_photo_{inspection['id']}_{point_id}_{i}"
                                    # Utiliser on_click pour gérer l'état avant rerun
                                    def open_photo_modal(photo_list, index, caption):
                                        st.session_state.modal_photo_list = photo_list
                                        st.session_state.modal_photo_index = index
                                        st.session_state.modal_photo_caption = caption
                                        st.session_state.show_photo_modal = True
                                        st.session_state.show_detail_dialog = False # Fermer modale détail

                                    photo_caption = f"Photo {i+1} - Point: {point_model.get('PointDeControle', point_id)}"
                                    st.button("Agrandir", key=button_key, help="Voir l'image en grand",
                                              on_click=open_photo_modal, args=(photos, i, photo_caption))

                                except (base64.binascii.Error, UnidentifiedImageError, Exception):
                                    st.warning(f"Photo {i+1} invalide", icon="⚠️")
                else: st.info("Aucun résultat enregistré.")
                st.markdown("</div>", unsafe_allow_html=True) # Fermer div

# --- Fonction de Calcul Dashboard (avec KPIs séparés) ---
def calculate_dashboard_metrics() -> Dict[str, Any]:
    """Calcule les métriques pour le dashboard, incluant KPIs séparés."""
    metrics = { # Initialisation complète
        'total_inspections': len(st.session_state.loaded_inspections),
        'total_points_of_interest': 0, 'total_nc_direct': 0, 'total_out_of_range': 0,
        'total_points_checked': 0, 'total_points_conform': 0,
        'action_status_counts': {'À traiter': 0, 'En cours': 0, 'Terminé': 0, 'Annulé': 0},
        'conformity_by_category': {}, 'non_conformity_counts_by_point': {},
        'category_compliance_rates_df': pd.DataFrame(columns=['Catégorie', 'Taux Conformité (%)']),
        'top_non_conformities_df': pd.DataFrame(columns=['Point de Contrôle', 'Nombre Occurrences']),
        'action_status_df': pd.DataFrame(columns=['Statut', 'Nombre']),
        'overall_compliance_rate': 0.0
    }
    if not st.session_state.loaded_inspections: return metrics

    for data in st.session_state.loaded_inspections:
        inspection, model, inspection_id = data['inspection'], data['model'], data['inspection']['id']
        for result in inspection.get('results', []):
            point_id = result.get('idPoint'); point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
            if not point_id or not point_model or result.get('isNA', False): continue

            metrics['total_points_checked'] += 1
            category = point_model.get('Categorie', 'Sans Catégorie'); metrics['conformity_by_category'].setdefault(category, {'conform': 0, 'checked': 0})['checked'] += 1

            problem_type, _ = get_problem_type_and_display(result, point_model)
            is_poi = problem_type in ["Non Conforme", "Inférieur Min", "Supérieur Max", "Erreur Valeur/Plage"]

            if is_poi:
                metrics['total_points_of_interest'] += 1
                if problem_type == "Non Conforme": metrics['total_nc_direct'] += 1
                if problem_type in ["Inférieur Min", "Supérieur Max"]: metrics['total_out_of_range'] += 1

                action_key = (inspection_id, point_id); status = st.session_state.corrective_actions.get(action_key, {}).get('status', 'À traiter')
                if status in metrics['action_status_counts']: metrics['action_status_counts'][status] += 1
                point_name = point_model.get('PointDeControle', 'N/A'); metrics['non_conformity_counts_by_point'][point_name] = metrics['non_conformity_counts_by_point'].get(point_name, 0) + 1
            else: # Conforme ou Conforme (Plage OK)
                metrics['total_points_conform'] += 1
                metrics['conformity_by_category'][category]['conform'] += 1

    # Calculs finaux & DFs
    if metrics['total_points_checked'] > 0: metrics['overall_compliance_rate'] = (metrics['total_points_conform'] / metrics['total_points_checked'] * 100)
    cat_rates_data = [{'Catégorie': name, 'Taux Conformité (%)': (d['conform'] / d['checked'] * 100) if d['checked'] > 0 else 0.0} for name, d in metrics['conformity_by_category'].items()]
    if cat_rates_data: metrics['category_compliance_rates_df'] = pd.DataFrame(cat_rates_data).sort_values(by='Catégorie')
    if metrics['non_conformity_counts_by_point']: metrics['top_non_conformities_df'] = pd.DataFrame(metrics['non_conformity_counts_by_point'].items(), columns=['Point de Contrôle', 'Nombre Occurrences']).nlargest(5, 'Nombre Occurrences')
    if sum(metrics['action_status_counts'].values()) > 0: metrics['action_status_df'] = pd.DataFrame(metrics['action_status_counts'].items(), columns=['Statut', 'Nombre']).sort_values(by='Statut')

    return metrics

# --- Fonctions Export (inchangées mais robustes) ---
def prepare_export_data() -> List[Dict]:
    """Prépare les données pour l'export."""
    import copy
    updated_inspections_list = []
    inspections_to_export = copy.deepcopy(st.session_state.loaded_inspections)
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
    """Crée le fichier ZIP d'export."""
    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            def default_serializer(obj):
                if isinstance(obj, (datetime, pd.Timestamp)): return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            json_string = json.dumps(export_data, indent=2, ensure_ascii=False, default=default_serializer)
            zip_file.writestr("aggregated_export.json", json_string)
    except Exception as e:
        st.error(f"Erreur création ZIP : {e}"); return b""
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


# --- Interface Utilisateur Streamlit ---

st.title("📊 Visualiseur et Analyseur d'Inspections")
st.caption("Chargez des packages (.zip) pour visualiser, agréger, analyser et suivre les actions.")

# -- Barre Latérale --
with st.sidebar:
    st.header("Chargement des Données")
    uploaded_files = st.file_uploader("Sélectionner package(s) (.zip)", type='zip', accept_multiple_files=True, key="file_uploader", help="Chargez les .zip contenant 'inspection_data.json'")
    if uploaded_files:
        if st.button("Traiter Fichiers"):
            with st.spinner("Traitement..."): load_zip_data(uploaded_files)
            st.rerun()
    st.divider()
    if st.session_state.loaded_inspections:
        st.header("Actions")
        # Confirmation pour Vider Tout
        if st.button("⚠️ Vider Toutes les Données", key="clear_all_btn", help="Supprime toutes les données de cette session."):
             st.session_state.confirm_clear_all = True # Activer la confirmation

        if st.session_state.get('confirm_clear_all', False):
             st.warning("Êtes-vous sûr de vouloir tout supprimer ? Cette action est irréversible pour la session actuelle.")
             clear_cols = st.columns(2)
             if clear_cols[0].button("Oui, Supprimer Tout", type="primary"):
                 # Vider l'état
                 for key in default_session_state.keys(): # Réinitialiser tout l'état lié aux données
                      if key not in ['confirm_clear_all']: # Ne pas réinitialiser le flag de confirmation lui-même ici
                           st.session_state[key] = default_session_state[key]
                 st.session_state.confirm_clear_all = False # Désactiver la confirmation après action
                 st.toast("Données vidées.", icon="🗑️"); st.rerun()
             if clear_cols[1].button("Annuler"):
                 st.session_state.confirm_clear_all = False; st.rerun()

        st.divider()
        st.header("Export")
        st.caption("Exporte toutes les inspections chargées avec les statuts/notes d'action corrective.")
        if st.button("Préparer l'Export Agrégé"):
             with st.spinner("Préparation..."):
                try:
                    export_list = prepare_export_data(); zip_bytes = create_export_zip(export_list)
                    if zip_bytes:
                        st.session_state.export_data_prepared = zip_bytes; timestamp = datetime.now().strftime("%Y%m%d_%H%M%S"); st.session_state.export_filename = f"export_agregé_{timestamp}.zip"; st.toast("Export prêt.", icon="✅")
                except Exception as prep_e: st.error(f"Erreur export: {prep_e}"); st.session_state.export_data_prepared = None

        if st.session_state.export_data_prepared:
            st.download_button("⬇️ Télécharger Package (.zip)", data=st.session_state.export_data_prepared, file_name=st.session_state.export_filename, mime="application/zip", key="download_export_button")

# -- Contenu Principal avec Onglets --
if not st.session_state.loaded_inspections:
    st.info("👋 Bienvenue ! Chargez des packages d'inspection (.zip) via la barre latérale.")
else:
    tab_titles = ["📈 Tableau de Bord", f"📋 Liste Inspections ({len(st.session_state.loaded_inspections)})", "🔍 Vue Agrégée"]
    tab_dashboard, tab_list, tab_aggregated = st.tabs(tab_titles)

    # --- Onglet Tableau de Bord ---
    with tab_dashboard:
        st.subheader("📈 Tableau de Bord Synthétique")
        metrics = calculate_dashboard_metrics()
        # KPIs Améliorés
        kpi_cols = st.columns(4)
        kpi_cols[0].metric("Inspections Chargées", metrics['total_inspections'])
        kpi_cols[1].metric("Non-Conformités", metrics['total_nc_direct'], help="Résultat direct 'Non Conforme'")
        kpi_cols[2].metric("Valeurs Hors Plage", metrics['total_out_of_range'], help="Points numériques hors des limites définies")
        kpi_cols[3].metric("Tx Conformité Global", f"{metrics['overall_compliance_rate']:.1f}%", help="Points conformes / Points vérifiés (non N/A)")
        st.divider()
        chart_cols = st.columns(2)
        with chart_cols[0]: # Graphiques Gauche
            st.markdown("**Répartition Statuts Action**")
            if not metrics['action_status_df'].empty and metrics['action_status_df']['Nombre'].sum() > 0:
                fig_pie = px.pie(metrics['action_status_df'], names='Statut', values='Nombre', title="Statuts Actions Correctives", hole=0.3)
                fig_pie.update_layout(legend_title_text='Statut'); st.plotly_chart(fig_pie, use_container_width=True)
            else: st.caption("Aucune action corrective.")
            st.markdown(f"**Top {len(metrics['top_non_conformities_df'])} Points d'Intérêt**")
            if not metrics['top_non_conformities_df'].empty:
                 df_top_nc = metrics['top_non_conformities_df'].sort_values(by='Nombre Occurrences', ascending=True)
                 fig_bar_nc = px.bar(df_top_nc, x='Nombre Occurrences', y='Point de Contrôle', orientation='h', title="Points d'Intérêt les Plus Fréquents")
                 fig_bar_nc.update_layout(yaxis_title=None, xaxis_title="Nombre d'occurrences"); st.plotly_chart(fig_bar_nc, use_container_width=True)
            else: st.caption("Aucun point d'intérêt.")
        with chart_cols[1]: # Graphiques Droite
            st.markdown("**Taux de Conformité par Catégorie**")
            if not metrics['category_compliance_rates_df'].empty:
                fig_bar_cat = px.bar(metrics['category_compliance_rates_df'], x='Catégorie', y='Taux Conformité (%)', title="Conformité par Catégorie", range_y=[0, 100], color='Taux Conformité (%)', color_continuous_scale=px.colors.sequential.Greens)
                fig_bar_cat.update_layout(xaxis_tickangle=-45, yaxis_title="Tx Conformité (%)"); st.plotly_chart(fig_bar_cat, use_container_width=True)
            else: st.caption("Aucune donnée par catégorie.")

    # --- Onglet Liste des Inspections ---
    with tab_list:
        st.subheader(f"📋 Liste des Inspections Chargées ({len(st.session_state.loaded_inspections)})")
        if not st.session_state.loaded_inspections: st.info("Aucune inspection chargée.")
        else:
            for index, data in enumerate(st.session_state.loaded_inspections):
                inspection, model, filename, inspection_id = data['inspection'], data['model'], data['filename'], data['inspection']['id']
                # Indicateur Visuel POI
                has_poi = any(is_point_of_interest_enhanced(res, next((item for item in model.get('items', []) if item.get('ID_Point') == res.get('idPoint')), None)) for res in inspection.get('results', []) if isinstance(res, dict))
                expander_title = f"**{model.get('name', 'N/A')}** par **{inspection.get('inspectorName', 'N/A')}** (ID: ...{inspection_id[-8:]})"
                if has_poi: expander_title += " ⚠️"

                with st.expander(expander_title, expanded=False):
                    exp_cols = st.columns([3, 1])
                    with exp_cols[0]:
                        start_date_str = pd.to_datetime(inspection.get('startDate'), errors='coerce').strftime('%d/%m/%Y %H:%M') if inspection.get('startDate') else 'N/A'
                        st.caption(f"Fichier: {filename} | Statut: {inspection.get('status', 'N/A')} | Début: {start_date_str}")
                        # Résumé POI si applicable
                        if has_poi:
                            poi_count = sum(1 for res in inspection.get('results', []) if isinstance(res, dict) and is_point_of_interest_enhanced(res, next((item for item in model.get('items', []) if item.get('ID_Point') == res.get('idPoint')), None)))
                            st.warning(f"{poi_count} point(s) d'intérêt trouvé(s).", icon="⚠️")
                    with exp_cols[1]:
                        def set_detail_view_state(insp_id): st.session_state.selected_inspection_id_for_detail = insp_id; st.session_state.show_detail_dialog = True
                        st.button("👁️ Voir Détails", key=f"detail_{inspection_id}_{index}", on_click=set_detail_view_state, args=(inspection_id,))
                        def remove_inspection(insp_id):
                            st.session_state.loaded_inspections = [insp for insp in st.session_state.loaded_inspections if insp['inspection']['id'] != insp_id]
                            keys_to_remove = [key for key in st.session_state.corrective_actions if key[0] == insp_id]
                            for key in keys_to_remove: del st.session_state.corrective_actions[key]
                            st.toast(f"Inspection ...{insp_id[-8:]} retirée.", icon="🗑️")
                            if st.session_state.selected_inspection_id_for_detail == insp_id: st.session_state.selected_inspection_id_for_detail = None; st.session_state.show_detail_dialog = False
                        st.button("🗑️ Retirer", key=f"remove_{inspection_id}_{index}", type="secondary", on_click=remove_inspection, args=(inspection_id,))

    # --- Onglet Vue Agrégée ---
    with tab_aggregated:
        st.subheader("🔍 Vue Agrégée des Points d'Intérêt")
        st.caption("Affiche les points 'Non Conforme' ou 'Hors Plage'. Modifiez 'Statut Action' et 'Note Action' pour le suivi (session uniquement).")
        aggregated_df_full = prepare_aggregated_dataframe()

        st.markdown("**Filtres :**")
        filter_cols = st.columns(6) # Ajout colonne pour Type Problème
        with filter_cols[0]: st.session_state.agg_search = st.text_input("Recherche libre", value=st.session_state.agg_search, key="agg_search_input")
        with filter_cols[1]: categories = [''] + sorted(aggregated_df_full['Catégorie'].astype(str).unique()); st.session_state.agg_cat_filter = st.selectbox("Catégorie", options=categories, index=categories.index(st.session_state.agg_cat_filter) if st.session_state.agg_cat_filter in categories else 0, key="agg_cat_select")
        with filter_cols[2]: inspectors = [''] + sorted(aggregated_df_full['Inspecteur'].astype(str).unique()); st.session_state.agg_insp_filter = st.selectbox("Inspecteur", options=inspectors, index=inspectors.index(st.session_state.agg_insp_filter) if st.session_state.agg_insp_filter in inspectors else 0, key="agg_insp_select")
        with filter_cols[3]: points_ctrl = [''] + sorted(aggregated_df_full['Point de Contrôle'].astype(str).unique()); st.session_state.agg_point_filter = st.selectbox("Point Contrôle", options=points_ctrl, index=points_ctrl.index(st.session_state.agg_point_filter) if st.session_state.agg_point_filter in points_ctrl else 0, key="agg_point_select")
        with filter_cols[4]: action_statuses = [''] + ['À traiter', 'En cours', 'Terminé', 'Annulé']; st.session_state.agg_status_filter = st.selectbox("Statut Action", options=action_statuses, index=action_statuses.index(st.session_state.agg_status_filter) if st.session_state.agg_status_filter in action_statuses else 0, key="agg_status_select")
        with filter_cols[5]: # Nouveau filtre: Type Problème
             problem_types = [''] + sorted(aggregated_df_full['Type Problème'].astype(str).unique()); st.session_state.agg_problem_type_filter = st.selectbox("Type Problème", options=problem_types, index=problem_types.index(st.session_state.agg_problem_type_filter) if st.session_state.agg_problem_type_filter in problem_types else 0, key="agg_problem_type_select")

        # Appliquer filtres
        filtered_df = aggregated_df_full.copy()
        if st.session_state.agg_search:
            search_term_lower = st.session_state.agg_search.lower()
            text_search_cols = ['Point de Contrôle', 'Commentaire', 'Note Action', 'Résultat Obtenu', 'Critère Accept.', 'Type Problème']
            mask = pd.Series([False] * len(filtered_df));
            for col in text_search_cols:
                if col in filtered_df.columns: mask |= filtered_df[col].astype(str).str.lower().str.contains(search_term_lower, na=False)
            filtered_df = filtered_df[mask]
        if st.session_state.agg_cat_filter: filtered_df = filtered_df[filtered_df['Catégorie'] == st.session_state.agg_cat_filter]
        if st.session_state.agg_insp_filter: filtered_df = filtered_df[filtered_df['Inspecteur'] == st.session_state.agg_insp_filter]
        if st.session_state.agg_point_filter: filtered_df = filtered_df[filtered_df['Point de Contrôle'] == st.session_state.agg_point_filter]
        if st.session_state.agg_status_filter: filtered_df = filtered_df[filtered_df['Statut Action'] == st.session_state.agg_status_filter]
        if st.session_state.agg_problem_type_filter: filtered_df = filtered_df[filtered_df['Type Problème'] == st.session_state.agg_problem_type_filter] # Appliquer nouveau filtre

        st.divider()
        total_items = len(filtered_df)
        if total_items == 0:
            if not aggregated_df_full.empty: st.warning("Aucun point ne correspond aux filtres.")
            else: st.info("Aucun point d'intérêt trouvé.")
        else:
            st.markdown(f"**{total_items}** point(s) d'intérêt trouvé(s)")
            total_pages = max(1, (total_items + ITEMS_PER_PAGE_AGGREGATED - 1) // ITEMS_PER_PAGE_AGGREGATED)
            current_page = min(st.session_state.aggregated_page_number, total_pages); st.session_state.aggregated_page_number = current_page
            start_idx, end_idx = (current_page - 1) * ITEMS_PER_PAGE_AGGREGATED, current_page * ITEMS_PER_PAGE_AGGREGATED
            paginated_df = filtered_df.iloc[start_idx:end_idx]

            edited_df_slice = st.data_editor(
                paginated_df, key="aggregated_data_editor", use_container_width=True, hide_index=True,
                column_config={ # Configuration avec nouvelle colonne Type Problème
                    "inspection_id_hidden": None, "point_id_hidden": None, "ID Unique": None, "Critère Accept.": None,
                    "Date Insp.": st.column_config.DateColumn("Date", format="DD/MM/YY", disabled=True, width="small"),
                    "ID Insp.": st.column_config.TextColumn("ID Insp.", disabled=True, width="small"),
                    "Inspecteur": st.column_config.TextColumn("Inspecteur", disabled=True, width="small"),
                    "Catégorie": st.column_config.TextColumn("Catégorie", disabled=True, width="medium"),
                    "Point de Contrôle": st.column_config.TextColumn("Point Contrôle", disabled=True, width="medium"),
                    "Type Problème": st.column_config.TextColumn("Type Problème", help="Catégorie du problème", width="medium", disabled=True), # Afficher
                    "Résultat Obtenu": st.column_config.TextColumn("Résultat", help="Résultat brut avec indicateur visuel", width="medium", disabled=True), # Titre plus court
                    "Commentaire": st.column_config.TextColumn("Commentaire", disabled=True, width="large"),
                    "Photos Str": st.column_config.TextColumn("Photos", help="Nombre de photos", disabled=True, width="small"),
                    "Statut Action": st.column_config.SelectboxColumn("Statut Action", width="medium", options=['À traiter', 'En cours', 'Terminé', 'Annulé'], required=True),
                    "Note Action": st.column_config.TextColumn("Note Action", max_chars=200, width="large"),
                },
                column_order=[ # Nouvel ordre avec Type Problème
                    "Date Insp.", "Inspecteur", "Catégorie", "Point de Contrôle", "Type Problème",
                    "Résultat Obtenu", "Statut Action", "Note Action", "Commentaire", "Photos Str", "ID Insp."
                ],
                num_rows="fixed"
            )
            # Mise à jour état après édition
            update_corrective_actions_from_df(edited_df_slice)

            # Pagination
            st.divider()
            if total_pages > 1:
                pagination_cols = st.columns([1, 2, 1])
                with pagination_cols[0]:
                    def go_prev_agg_page(): st.session_state.aggregated_page_number -= 1
                    st.button("⬅️ Précédent", disabled=(current_page <= 1), key="agg_prev_page", on_click=go_prev_agg_page)
                with pagination_cols[1]: st.markdown(f"<div style='text-align: center;'>Page **{current_page}** / **{total_pages}**</div>", unsafe_allow_html=True)
                with pagination_cols[2]:
                    def go_next_agg_page(): st.session_state.aggregated_page_number += 1
                    st.button("Suivant ➡️", disabled=(current_page >= total_pages), key="agg_next_page", on_click=go_next_agg_page)

# --- Modale Détail ---
if st.session_state.show_detail_dialog and st.session_state.selected_inspection_id_for_detail:
    inspection_to_show = next((insp for insp in st.session_state.loaded_inspections if insp['inspection']['id'] == st.session_state.selected_inspection_id_for_detail), None)
    if inspection_to_show:
        @st.dialog("Détails de l'Inspection")
        def show_detail_modal():
            render_inspection_detail(inspection_to_show)
            def close_detail_modal(): setattr(st.session_state, 'show_detail_dialog', False)
            st.button("Fermer", key="close_detail_dialog_button", on_click=close_detail_modal)
        show_detail_modal()
    else: st.session_state.selected_inspection_id_for_detail = None; st.session_state.show_detail_dialog = False

# --- Modale Photo ---
if st.session_state.show_photo_modal and st.session_state.modal_photo_list:
    @st.dialog("Visualiseur de Photos")
    def show_photo_viewer():
        st.subheader(st.session_state.modal_photo_caption)
        current_index = st.session_state.modal_photo_index
        photos = st.session_state.modal_photo_list
        num_photos = len(photos)
        try:
            b64_string = photos[current_index]
            if isinstance(b64_string, str) and ',' in b64_string: b64_string = b64_string.split(',')[1]
            img_bytes = base64.b64decode(b64_string)
            st.image(img_bytes, use_column_width=True)
        except Exception as e: st.error(f"Affichage image {current_index + 1} impossible: {e}")
        if num_photos > 1:
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
    show_photo_viewer()

# --- Pied de page ---
st.divider()
st.caption("Visualiseur v1.2 (KPIs+, Type Problème, Pagination, Modales) - Mode Volatile")
st.caption("⚠️ Données de suivi Actions Correctives perdues à la fermeture.")
