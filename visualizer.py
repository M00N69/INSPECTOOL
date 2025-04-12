# visualizer_app_v2.py

import streamlit as st
import pandas as pd
import plotly.express as px
# import plotly.graph_objects as go # Moins utilisé avec px
import zipfile
import io
import json
import base64
from PIL import Image, UnidentifiedImageError
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Union

# --- Configuration de la Page Streamlit ---
st.set_page_config(
    page_title="Visualiseur d'Inspections & Suivi Actions",
    page_icon="✅", # Nouvel icône
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Constantes ---
ITEMS_PER_PAGE_AGGREGATED = 50 # Pour l'ancienne vue agrégée (gardé si réutilisé)

# --- Initialisation de l'État de Session ---
default_session_state = {
    'loaded_inspections': [],
    'corrective_actions': {},
    'action_dates': {}, # NOUVEAU: Pour la planification {(insp_id, point_id): {'due_date': date, 'assigned_to': str}}
    'selected_inspection_id_for_detail': None,
    'show_detail_dialog': False,
    'export_data_prepared': None,
    'export_filename': "",
    'show_photo_modal': False,
    'modal_photo_list': [],
    'modal_photo_index': 0,
    'modal_photo_caption': "",
    # 'aggregated_page_number': 1, # Moins pertinent avec le regroupement par catégorie
    'editing_action': None, # NOUVEAU: Pour savoir quelle action est en cours d'édition dans l'onglet Suivi Actions (insp_id, point_id) | None
    'confirm_clear_all': False,
    # États pour les filtres de l'onglet Suivi Actions
    'action_status_filter': ['À traiter', 'En cours'], # Filtre par défaut
    'action_category_filter': [],
    'action_problem_type_filter': [],
    'action_search_term': '',
    # États pour les filtres de la vue agrégée (si on la garde à part)
    'agg_search': '', 'agg_cat_filter': '', 'agg_insp_filter': '',
    'agg_point_filter': '', 'agg_status_filter': '', 'agg_problem_type_filter': ''
}
for key, default_value in default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- Styles CSS Personnalisés (Optionnel mais utile) ---
st.markdown("""
<style>
    /* Améliorer l'apparence des boutons dans les colonnes */
    .stButton>button {
        width: 100%;
        padding: 0.25rem 0.5rem;
        font-size: 0.875rem;
    }
    /* Espacement et style des cartes dans l'onglet Suivi */
    .action-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
        background-color: white;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    /* Style pour le calendrier */
    .calendar-grid {
        display:grid;
        grid-template-columns:repeat(7, 1fr);
        grid-gap: 3px; /* Légèrement plus d'espace */
    }
    .calendar-day {
        padding: 5px;
        min-height: 80px; /* Hauteur minimale */
        overflow: hidden;
        font-size: 0.8em;
        border-radius: 4px;
        position: relative;
        display: flex;
        flex-direction: column; /* Organiser contenu verticalement */
        border: 1px solid #e8e8e8; /* Bordure par défaut */
    }
    .calendar-day-header {
        font-weight: bold;
        margin-bottom: 3px; /* Espace sous le numéro du jour */
        text-align: right; /* Numéro à droite */
    }
    .calendar-task {
        background-color: #dbeafe; /* Bleu clair par défaut */
        color: #1e40af; /* Bleu foncé */
        padding: 1px 4px;
        border-radius: 3px;
        margin-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 0.9em; /* Taille légèrement plus grande */
        cursor: default; /* Indiquer qu'on ne peut pas cliquer */
    }
    .calendar-task-todo { background-color: #fee2e2; color: #991b1b; } /* Rouge */
    .calendar-task-inprogress { background-color: #ffedd5; color: #9a3412; } /* Orange */
    .calendar-task-done { background-color: #dcfce7; color: #166534; } /* Vert */
    .calendar-task-cancelled { background-color: #f3f4f6; color: #4b5563; } /* Gris */
    .calendar-today { background-color: #e0f2fe; border: 2px solid #0ea5e9; } /* Bleu ciel pour aujourd'hui */
    .calendar-other-month { background-color: #f8fafc; } /* Gris très clair pour hors mois */

</style>
""", unsafe_allow_html=True)


# --- Fonctions Utilitaires (Peu de changements nécessaires ici) ---

# get_problem_type_and_display et is_point_of_interest_enhanced sont cruciales et semblent correctes
def get_problem_type_and_display(result_data: Optional[Dict], point_model: Optional[Dict]) -> Tuple[str, str]:
    """Détermine type problème et format affichage."""
    if not result_data or not point_model: return "Inconnu", ""
    if result_data.get('isNA', False): return "N/A", "N/A"
    result_value = result_data.get('result')
    result_display = str(result_value) if result_value is not None else ''
    if result_value == 'Non Conforme': return "Non Conforme", f"🔴 {result_display}"
    if result_value == 'Conforme': return "Conforme", f"✅ {result_display}"
    if point_model.get('TypeParametre') == 'Plage_Numerique' and result_value is not None:
        try:
            value = float(str(result_value).replace(',','.'))
            options_str = point_model.get('OptionsParametre', ''); options = options_str.split(';')
            if len(options) == 2:
                min_val, max_val = map(float, options); range_str = f" [Plage: {min_val}-{max_val}]"
                if value < min_val: return "Inférieur Min", f"⬇️ {result_display}{range_str}"
                if value > max_val: return "Supérieur Max", f"⬆️ {result_display}{range_str}"
                return "Conforme (Plage OK)", f"✅ {result_display}" # Dans la plage
        except (ValueError, TypeError): return "Erreur Valeur/Plage", f"⚠️ {result_display} (Erreur plage)"
    return "Conforme", result_display # Autres cas

def is_point_of_interest_enhanced(result_data: Optional[Dict], point_model: Optional[Dict]) -> bool:
    """Vérifie si un point est d'intérêt (Non Conforme, Hors Plage, Erreur)."""
    problem_type, _ = get_problem_type_and_display(result_data, point_model)
    return problem_type in ["Non Conforme", "Inférieur Min", "Supérieur Max", "Erreur Valeur/Plage"]

# load_zip_data semble correcte
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
                if not isinstance(package_data, dict) or not all(k in package_data for k in ['inspection', 'model']) or \
                   not isinstance(package_data['inspection'], dict) or not all(k in package_data['inspection'] for k in ['id', 'modelId', 'startDate', 'results']) or \
                   not isinstance(package_data['model'], dict) or not all(k in package_data['model'] for k in ['name', 'items']) or \
                   not isinstance(package_data['inspection']['results'], list) or not isinstance(package_data['model']['items'], list):
                   raise ValueError("Structure JSON invalide")
                inspection_id = package_data['inspection']['id']
                if not isinstance(inspection_id, str) or not inspection_id: raise ValueError("ID inspection invalide")
                if inspection_id in current_inspection_ids: duplicate_count += 1; st.warning(f"'{filename}' ignoré: ID '{inspection_id[:8]}...' déjà chargé."); continue
                st.session_state.loaded_inspections.append({"inspection": package_data['inspection'], "model": package_data['model'], "filename": filename})
                current_inspection_ids.add(inspection_id); newly_loaded_count += 1
                for result in package_data['inspection'].get('results', []):
                    point_id = result.get('idPoint'); point_model = next((item for item in package_data['model'].get('items', []) if item.get('ID_Point') == point_id), None)
                    if point_id and is_point_of_interest_enhanced(result, point_model):
                        action_key = (inspection_id, point_id); st.session_state.corrective_actions.setdefault(action_key, {'status': 'À traiter', 'note': ''})
        except (json.JSONDecodeError, zipfile.BadZipFile, ValueError, Exception) as e: st.error(f"Erreur '{filename}': {e}"); error_count += 1
    if newly_loaded_count > 0: st.success(f"{newly_loaded_count} inspection(s) chargée(s).")
    if duplicate_count > 0: st.info(f"{duplicate_count} inspection(s) déjà chargées.")
    if error_count > 0: st.warning(f"{error_count} fichier(s) non traités.")

# Fonction pour préparer le DF pour la vue agrégée (utilisée par l'onglet regroupé)
def prepare_aggregated_dataframe() -> pd.DataFrame:
    """Crée le DataFrame Pandas agrégé avec la colonne 'Type Problème'."""
    data_for_df = []
    expected_columns = [ # Colonnes nécessaires pour le regroupement et l'éditeur
        'ID Unique', 'Date Insp.', 'ID Insp.', 'Inspecteur', 'Catégorie',
        'Point de Contrôle', 'Type Problème', 'Résultat Obtenu', 'Commentaire',
        'Photos Str', 'Statut Action', 'Note Action',
        'inspection_id_hidden', 'point_id_hidden', 'Critère Accept.'
    ]
    if not st.session_state.loaded_inspections: return pd.DataFrame(columns=expected_columns)

    for data in st.session_state.loaded_inspections:
        inspection, model, inspection_id = data['inspection'], data['model'], data['inspection']['id']
        for result in inspection.get('results', []):
            point_id = result.get('idPoint'); point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
            if point_id and is_point_of_interest_enhanced(result, point_model):
                action_key = (inspection_id, point_id); action_info = st.session_state.corrective_actions.get(action_key, {'status': 'À traiter', 'note': ''})
                problem_type, result_display_formatted = get_problem_type_and_display(result, point_model)
                nb_photos = len(result.get('photosBase64', [])); photos_str = f"📷 {nb_photos}" if nb_photos > 0 else "—"
                data_for_df.append({
                    'ID Unique': f"{inspection_id[:8]}_{point_id}",
                    'Date Insp.': pd.to_datetime(inspection.get('startDate'), errors='coerce').date() if inspection.get('startDate') else None,
                    'ID Insp.': inspection_id[:8] + "...",
                    'Inspecteur': inspection.get('inspectorName', 'N/A'),
                    'Catégorie': point_model.get('Categorie', 'N/A') if point_model else 'N/A',
                    'Point de Contrôle': point_model.get('PointDeControle', 'N/A') if point_model else 'N/A',
                    'Critère Accept.': point_model.get('CritereAcceptation', 'N/A') if point_model else 'N/A',
                    'Type Problème': problem_type,
                    'Résultat Obtenu': result_display_formatted,
                    'Commentaire': result.get('comment', ''),
                    'Photos Str': photos_str,
                    'Statut Action': action_info.get('status', 'À traiter'),
                    'Note Action': action_info.get('note', ''),
                    'inspection_id_hidden': inspection_id,
                    'point_id_hidden': point_id
                })
    if not data_for_df: return pd.DataFrame(columns=expected_columns)
    df = pd.DataFrame(data_for_df)
    if 'Date Insp.' in df.columns: df['Date Insp.'] = pd.to_datetime(df['Date Insp.'])
    return df

# Fonction pour mettre à jour l'état depuis le data_editor (utilisée par l'onglet regroupé)
def update_corrective_actions_from_df(edited_df: pd.DataFrame) -> None:
    """Met à jour st.session_state.corrective_actions depuis le DF édité."""
    updates_made = 0
    required_cols = ['inspection_id_hidden', 'point_id_hidden', 'Statut Action', 'Note Action']
    if not all(col in edited_df.columns for col in required_cols):
        if not edited_df.empty: st.error("Err. interne: Colonnes manquantes màj actions.")
        return
    for _, row in edited_df.iterrows():
        action_key = (row['inspection_id_hidden'], row['point_id_hidden'])
        current_status = row['Statut Action']; current_note = row['Note Action'] if pd.notna(row['Note Action']) else ""
        previous_action = st.session_state.corrective_actions.get(action_key, {'status': 'N/A', 'note': 'N/A'})
        if previous_action['status'] != current_status or previous_action['note'] != current_note:
            st.session_state.corrective_actions[action_key] = {'status': current_status, 'note': current_note}
            updates_made += 1
    # Optionnel: if updates_made > 0: st.toast(...)

# --- Fonction de Rendu Vue Détaillée (Améliorée) ---
def render_inspection_detail(inspection_data: Dict) -> None:
    """Affiche les détails d'une inspection avec mise en évidence améliorée et stats."""
    inspection, model, filename = inspection_data['inspection'], inspection_data['model'], inspection_data['filename']
    st.header(f"{model.get('name', 'N/A')}", divider="blue")
    # Layout en colonnes pour les métadonnées et KPI inspection
    meta_cols = st.columns([2, 2, 1]) # Ajuster ratios si besoin
    with meta_cols[0]:
        st.markdown(f"**Fichier:** {filename}\n\n**ID:** {inspection.get('id', 'N/A')}\n\n**Inspecteur:** {inspection.get('inspectorName', 'N/A')}")
    with meta_cols[1]:
        start_date = inspection.get('startDate'); end_date = inspection.get('endDate')
        st.markdown(f"**Début:** {pd.to_datetime(start_date).strftime('%d/%m/%Y %H:%M') if start_date else 'N/A'}\n\n"
                    f"**Fin:** {pd.to_datetime(end_date).strftime('%d/%m/%Y %H:%M') if end_date else 'N/A'}\n\n"
                    f"**Statut:** {inspection.get('status', 'N/A')}")
    with meta_cols[2]:
        # Calcul stats spécifiques à cette inspection
        total_points = len(model.get('items', [])); poi_count = 0
        results_map = {res.get('idPoint'): res for res in inspection.get('results', []) if isinstance(res, dict)}
        model_map = {item.get('ID_Point'): item for item in model.get('items', []) if isinstance(item, dict)}
        for point_id, item_model in model_map.items():
            result_data = results_map.get(point_id)
            if is_point_of_interest_enhanced(result_data, item_model): poi_count += 1
        conformity_rate = ((total_points - poi_count) / total_points * 100) if total_points > 0 else 0
        st.metric("Points d'intérêt", f"{poi_count} / {total_points}", delta=f"{conformity_rate:.0f}% conformes", delta_color="inverse", help="Nombre de points Non Conformes ou Hors Plage sur le total.")

    st.divider()
    # Organisation par catégories avec tri par nb de POI
    points_by_category = {}; category_stats = {}
    for item in model.get('items', []):
        cat = item.get('Categorie', 'Sans Catégorie'); points_by_category.setdefault(cat, []).append(item)
        category_stats.setdefault(cat, {'total': 0, 'poi': 0})['total'] += 1
    for point_id, result_data in results_map.items():
        point_model = model_map.get(point_id)
        if point_model and is_point_of_interest_enhanced(result_data, point_model):
            cat = point_model.get('Categorie', 'Sans Catégorie'); category_stats[cat]['poi'] += 1
    if not points_by_category: st.warning("Aucun point de contrôle trouvé."); return

    # Affichage des catégories triées, avec points conformes optionnellement cachés
    hide_conform = st.checkbox("Masquer les points conformes dans les catégories avec problèmes", value=True, key=f"hide_conform_{inspection['id']}")

    for category, items in sorted(points_by_category.items(), key=lambda x: category_stats[x[0]]['poi'], reverse=True):
        stats = category_stats[category]; poi_percent = (stats['poi'] / stats['total'] * 100) if stats['total'] > 0 else 0
        cat_color = "#ef4444" if poi_percent > 50 else "#f97316" if poi_percent > 20 else "#22c55e"
        expander_title = f"**{category}** ({stats['poi']} problèmes / {stats['total']} points)"
        auto_expand = stats['poi'] > 0

        with st.expander(expander_title, expanded=auto_expand):
            # Barre de progression conformité pour la catégorie
            progress_html = f"""<div style="width:100%; background-color:#f0f0f0; height:8px; border-radius:4px; margin:10px 0;">
                                 <div style="width:{100-poi_percent:.1f}%; background-color:{cat_color}; height:8px; border-radius:4px;"></div></div>
                               <p style="font-size:0.8em; margin:0 0 15px 0; text-align:right;">{100-poi_percent:.1f}% conformes</p>"""
            st.markdown(progress_html, unsafe_allow_html=True)

            # Affichage des points triés (POI en premier)
            for point_model in sorted(items, key=lambda x: (0 if is_point_of_interest_enhanced(results_map.get(x.get('ID_Point')), x) else 1, x.get('PointDeControle', ''))):
                point_id = point_model.get('ID_Point'); result_data = results_map.get(point_id)
                is_poi = is_point_of_interest_enhanced(result_data, point_model) if result_data else False

                # Option pour masquer les points conformes si la catégorie a des problèmes
                if hide_conform and stats['poi'] > 0 and not is_poi: continue

                # Style de la carte du point
                base_card_style = "padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);"
                if is_poi: card_style = base_card_style + "border: 1px solid #fecaca; background-color: #fee2e2; border-left: 5px solid #ef4444;"
                else: card_style = base_card_style + "border: 1px solid #dcfce7; background-color: #f0fdf4; border-left: 5px solid #22c55e;"
                st.markdown(f"<div style='{card_style}' class='point-card'>", unsafe_allow_html=True) # Classe ajoutée

                # En-tête Point + Badge Problème
                problem_type, result_display = get_problem_type_and_display(result_data, point_model)
                problem_badge = ""; color_map = {"Non Conforme": "#ef4444", "Inférieur Min": "#f97316", "Supérieur Max": "#f97316", "Erreur Valeur/Plage": "#f59e0b"} # Couleurs Tailwind
                if problem_type in color_map: problem_badge = f'<span style="background-color:{color_map[problem_type]};color:white;padding:2px 8px;border-radius:12px;font-size:0.75em;margin-left:10px;vertical-align:middle;">{problem_type}</span>'
                st.markdown(f"**{point_model.get('PointDeControle', 'N/A')}**{problem_badge}", unsafe_allow_html=True)
                st.caption(f"ID: {point_id}")

                # Description & Critère en colonnes
                with st.container():
                    desc_cols = st.columns(2)
                    with desc_cols[0]: st.caption(f"**Description:** {point_model.get('Description', 'N/A')}")
                    with desc_cols[1]: st.caption(f"**Critère:** {point_model.get('CritereAcceptation', 'N/A')}")

                if result_data: # Résultat & Commentaire
                    res_cols = st.columns([1, 2])
                    with res_cols[0]: st.markdown(f"**Résultat:** {result_display}", unsafe_allow_html=True)
                    with res_cols[1]: comment = result_data.get('comment'); st.markdown(f"**Commentaire:** {comment or 'Aucun'}")

                    # Suivi Action Corrective (si POI)
                    if is_poi:
                        st.markdown("---") # Séparateur léger
                        action_key = (inspection['id'], point_id)
                        action_info = st.session_state.corrective_actions.get(action_key, {'status': 'À traiter', 'note': ''})
                        action_cols = st.columns([1, 2]) # Colonnes pour Statut et Note
                        with action_cols[0]: # Statut
                            status_options = ['À traiter', 'En cours', 'Terminé', 'Annulé']
                            current_status_idx = status_options.index(action_info['status']) if action_info['status'] in status_options else 0
                            new_status = st.selectbox("Statut Action", options=status_options, index=current_status_idx, key=f"status_{inspection['id']}_{point_id}", label_visibility="collapsed")
                            if new_status != action_info['status']: st.session_state.corrective_actions[action_key]['status'] = new_status; # Met à jour direct l'état
                        with action_cols[1]: # Note
                            new_note = st.text_area("Note Action", value=action_info['note'], placeholder="Détails action...", key=f"note_{inspection['id']}_{point_id}", height=75, label_visibility="collapsed")
                            if new_note != action_info['note']: st.session_state.corrective_actions[action_key]['note'] = new_note; # Met à jour direct l'état

                    # Photos
                    photos = result_data.get('photosBase64', []);
                    if photos and isinstance(photos, list):
                        st.markdown("**Photos:**")
                        num_photos = len(photos); cols_per_row = min(num_photos, 4)
                        photo_cols = st.columns(cols_per_row)
                        for i, b64_string in enumerate(photos):
                            if i >= 4 and num_photos > 5: # Limiter les vignettes affichées si > 5 photos
                                if i == 4: photo_cols[i % cols_per_row].caption(f"+ {num_photos - 4} autres...")
                                continue
                            with photo_cols[i % cols_per_row]:
                                try:
                                    if isinstance(b64_string, str) and ',' in b64_string: b64_string = b64_string.split(',')[1]
                                    img_bytes = base64.b64decode(b64_string)
                                    st.image(img_bytes, width=120) # Augmenter taille vignette
                                    def open_photo_modal(pl, ix, cap): st.session_state.modal_photo_list=pl; st.session_state.modal_photo_index=ix; st.session_state.modal_photo_caption=cap; st.session_state.show_photo_modal=True; st.session_state.show_detail_dialog=False
                                    photo_caption = f"Photo {i+1} - {point_model.get('PointDeControle', point_id)[:30]}..."
                                    st.button("🔍", key=f"view_photo_{inspection['id']}_{point_id}_{i}", help="Agrandir", on_click=open_photo_modal, args=(photos, i, photo_caption))
                                except (base64.binascii.Error, UnidentifiedImageError, Exception) as img_e: st.warning("?", icon="🖼️", help=f"Erreur image: {img_e}")
                else: st.info("Aucun résultat enregistré.")
                st.markdown("</div>", unsafe_allow_html=True) # Fermer div point-card

# --- Fonctions Calcul Dashboard (inchangée, utilise les fonctions utilitaires mises à jour) ---
def calculate_dashboard_metrics() -> Dict[str, Any]:
    """Calcule les métriques pour le dashboard."""
    metrics = { # Initialisation complète
        'total_inspections': len(st.session_state.loaded_inspections),
        'total_points_of_interest': 0, 'total_nc_direct': 0, 'total_out_of_range': 0, 'total_error_value': 0,
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
            is_poi = problem_type not in ["Conforme", "Conforme (Plage OK)", "N/A", "Inconnu"]
            if is_poi:
                metrics['total_points_of_interest'] += 1
                if problem_type == "Non Conforme": metrics['total_nc_direct'] += 1
                elif problem_type in ["Inférieur Min", "Supérieur Max"]: metrics['total_out_of_range'] += 1
                elif problem_type == "Erreur Valeur/Plage": metrics['total_error_value'] += 1
                action_key = (inspection_id, point_id); status = st.session_state.corrective_actions.get(action_key, {}).get('status', 'À traiter')
                if status in metrics['action_status_counts']: metrics['action_status_counts'][status] += 1
                point_name = point_model.get('PointDeControle', 'N/A'); metrics['non_conformity_counts_by_point'][point_name] = metrics['non_conformity_counts_by_point'].get(point_name, 0) + 1
            else: metrics['total_points_conform'] += 1; metrics['conformity_by_category'][category]['conform'] += 1
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
                    # Ajouter aussi les infos de planification à l'export
                    planning_info = st.session_state.action_dates.get(action_key, {})
                    result['dateEcheanceAction'] = planning_info.get('due_date')
                    result['responsableAction'] = planning_info.get('assigned_to')
        updated_inspections_list.append(data)
    return updated_inspections_list

def create_export_zip(export_data: List[Dict]) -> bytes:
    """Crée le fichier ZIP d'export."""
    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            def default_serializer(obj):
                if isinstance(obj, (datetime, pd.Timestamp, pd.Period, pd.NaT.__class__, datetime.date)): return obj.isoformat() # Gérer plus de types date
                raise TypeError(f"Type {type(obj)} non sérialisable pour JSON")
            json_string = json.dumps(export_data, indent=2, ensure_ascii=False, default=default_serializer)
            zip_file.writestr("aggregated_export.json", json_string)
    except Exception as e: st.error(f"Erreur création ZIP : {e}"); return b""
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

# --- Export Excel Actions (Amélioré) ---
def export_actions_to_excel() -> Optional[bytes]:
    """Exporte les actions correctives vers un fichier Excel formaté."""
    if not st.session_state.corrective_actions:
        st.warning("Aucune action corrective à exporter."); return None
    export_data = []
    for (inspection_id, point_id), action_info in st.session_state.corrective_actions.items():
        inspection_data = next((data for data in st.session_state.loaded_inspections if data['inspection']['id'] == inspection_id), None)
        if not inspection_data: continue
        inspection, model = inspection_data['inspection'], inspection_data['model']
        point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
        result_data = next((r for r in inspection.get('results', []) if isinstance(r, dict) and r.get('idPoint') == point_id), None)
        if not point_model or not result_data: continue
        problem_type, result_display_formatted = get_problem_type_and_display(result_data, point_model)
        planning_info = st.session_state.action_dates.get((inspection_id, point_id), {'due_date': None, 'assigned_to': 'N/A'})
        export_data.append({
            'ID_Inspection': inspection_id, 'ID_Point': point_id,
            'Date_Inspection': pd.to_datetime(inspection.get('startDate'), errors='coerce').date() if inspection.get('startDate') else None,
            'Inspecteur': inspection.get('inspectorName', 'N/A'), 'Catégorie': point_model.get('Categorie', 'N/A'),
            'Point_de_Contrôle': point_model.get('PointDeControle', 'N/A'), 'Type_Problème': problem_type,
            'Résultat_Original': result_data.get('result', ''), 'Commentaire_Original': result_data.get('comment', ''),
            'Statut_Action': action_info.get('status', 'À traiter'), 'Note_Action': action_info.get('note', ''),
            'Date_Échéance': planning_info.get('due_date'), 'Responsable': planning_info.get('assigned_to', 'N/A'),
            'Nb_Photos': len(result_data.get('photosBase64', []))
        })
    if not export_data: st.warning("Aucune donnée à exporter."); return None
    export_df = pd.DataFrame(export_data)
    excel_buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter', date_format='dd/mm/yyyy', datetime_format='dd/mm/yyyy') as writer:
            export_df.to_excel(writer, sheet_name='Actions_Correctives', index=False)
            workbook = writer.book; worksheet = writer.sheets['Actions_Correctives']
            header_format = workbook.add_format({'bold': True, 'bg_color': '#374151', 'font_color': 'white', 'border': 1, 'text_wrap': True, 'valign': 'top'}) # Gris foncé
            status_formats = {'À traiter': workbook.add_format({'bg_color': '#FEE2E2'}), 'En cours': workbook.add_format({'bg_color': '#FEF3C7'}), # Couleurs Tailwind
                              'Terminé': workbook.add_format({'bg_color': '#D1FAE5'}), 'Annulé': workbook.add_format({'bg_color': '#E5E7EB'})}
            wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'}) # Format pour retour à la ligne
            for col_num, value in enumerate(export_df.columns.values): worksheet.write(0, col_num, value, header_format)
            status_col_idx = export_df.columns.get_loc('Statut_Action')
            for row_num, status in enumerate(export_df['Statut_Action']): worksheet.set_row(row_num + 1, None, status_formats.get(status))
            # Appliquer wrap text à certaines colonnes
            for col_name in ['Point_de_Contrôle', 'Commentaire_Original', 'Note_Action']:
                 col_idx = export_df.columns.get_loc(col_name); worksheet.set_column(col_idx, col_idx, None, wrap_format)
            worksheet.autofit() # Ajuster largeur colonnes
            # Feuille Récap (optionnelle)
            if 'Catégorie' in export_df.columns:
                 recap_by_cat = pd.crosstab(export_df['Catégorie'], export_df['Statut_Action']); recap_by_cat['Total'] = recap_by_cat.sum(axis=1)
                 recap_by_cat.to_excel(writer, sheet_name='Récap_Catégorie')
                 writer.sheets['Récap_Catégorie'].autofit()
    except Exception as e: st.error(f"Erreur création Excel: {e}"); return None
    excel_buffer.seek(0)
    return excel_buffer.getvalue()

# --- Interface Utilisateur Streamlit ---

st.title("📊 Visualiseur Inspections & Suivi Actions")
st.caption("Chargez des packages (.zip), visualisez, analysez et suivez les actions correctives.")

# -- Barre Latérale --
with st.sidebar:
    st.header("Chargement")
    uploaded_files = st.file_uploader("Sélectionner package(s) (.zip)", type='zip', accept_multiple_files=True, key="file_uploader", help="Chargez les .zip contenant 'inspection_data.json'")
    if uploaded_files:
        if st.button("Traiter Fichiers"):
            with st.spinner("Traitement..."): load_zip_data(uploaded_files)
            st.rerun()
    st.divider()
    if st.session_state.loaded_inspections:
        st.header("Actions")
        # Confirmation Vider Tout
        if st.button("⚠️ Vider Toutes les Données", key="clear_all_btn", help="Supprime toutes les données de cette session."):
             st.session_state.confirm_clear_all = True
        if st.session_state.get('confirm_clear_all', False):
             st.warning("Êtes-vous sûr ? Action irréversible pour la session.")
             clear_cols = st.columns(2)
             if clear_cols[0].button("Oui, Supprimer", type="primary", key="confirm_clear"):
                 # Réinitialiser l'état
                 for key in default_session_state.keys():
                      if key != 'confirm_clear_all': st.session_state[key] = default_session_state[key]
                 st.session_state.confirm_clear_all = False
                 st.toast("Données vidées.", icon="🗑️"); st.rerun()
             if clear_cols[1].button("Annuler", key="cancel_clear"): st.session_state.confirm_clear_all = False; st.rerun()
        st.divider()
        st.header("Exports")
        # Export Agrégé (ZIP)
        if st.button("Préparer Export Agrégé (ZIP)", help="Exporte toutes les données chargées + actions/planification dans un ZIP."):
             with st.spinner("Préparation..."):
                try:
                    export_list = prepare_export_data(); zip_bytes = create_export_zip(export_list)
                    if zip_bytes: st.session_state.export_data_prepared = zip_bytes; timestamp = datetime.now().strftime("%Y%m%d_%H%M%S"); st.session_state.export_filename = f"export_agregé_{timestamp}.zip"; st.toast("Export ZIP prêt.", icon="✅")
                except Exception as prep_e: st.error(f"Erreur export ZIP: {prep_e}"); st.session_state.export_data_prepared = None
        if st.session_state.export_data_prepared:
            st.download_button("⬇️ Télécharger Package (ZIP)", data=st.session_state.export_data_prepared, file_name=st.session_state.export_filename, mime="application/zip", key="download_export_zip")
        # Export Actions (Excel)
        excel_data_bytes = export_actions_to_excel() # Préparer les données Excel
        if excel_data_bytes:
            timestamp_excel = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_excel = f"suivi_actions_{timestamp_excel}.xlsx"
            st.download_button(label="📊 Exporter Actions (Excel)", data=excel_data_bytes, file_name=filename_excel, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_export_excel")

# -- Contenu Principal avec Onglets --
if not st.session_state.loaded_inspections:
    st.info("👋 Bienvenue ! Chargez des packages (.zip) via la barre latérale.")
else:
    # Calcul des métriques une fois pour tous les onglets
    metrics = calculate_dashboard_metrics()

    # Définition des onglets avec indicateur d'actions à traiter
    nb_a_traiter = metrics['action_status_counts']['À traiter']
    tab_titles = ["📈 Tableau de Bord", f"📋 Inspections ({len(st.session_state.loaded_inspections)})", "🔍 Vue Agrégée POI", f"📝 Suivi Actions {'🔴' if nb_a_traiter > 0 else '✅'}"]
    tab_dashboard, tab_list, tab_aggregated, tab_actions = st.tabs(tab_titles)

    # --- Onglet Tableau de Bord ---
    with tab_dashboard:
        st.subheader("📈 Tableau de Bord Synthétique")
        kpi_cols = st.columns(4)
        kpi_cols[0].metric("Inspections", metrics['total_inspections'])
        kpi_cols[1].metric("Non-Conformes", metrics['total_nc_direct'], help="Résultat 'Non Conforme'")
        kpi_cols[2].metric("Hors Plage", metrics['total_out_of_range'], help="Valeurs numériques hors limites")
        kpi_cols[3].metric("Tx Conformité", f"{metrics['overall_compliance_rate']:.1f}%", delta_color="off", help="% points conformes / points vérifiés")
        st.divider()
        chart_cols = st.columns(2)
        with chart_cols[0]: # Graphiques Gauche
            st.markdown("**Statuts Actions**")
            if not metrics['action_status_df'].empty and metrics['action_status_df']['Nombre'].sum() > 0:
                fig_pie = px.pie(metrics['action_status_df'], names='Statut', values='Nombre', title="Répartition Actions Correctives", hole=0.4, color='Statut', color_discrete_map={'À traiter': '#ef4444','En cours': '#f97316','Terminé': '#22c55e','Annulé': '#6b7280'})
                fig_pie.update_layout(legend_title_text='Statut', height=350); st.plotly_chart(fig_pie, use_container_width=True)
            else: st.caption("Aucune action.")
            st.markdown(f"**Top {len(metrics['top_non_conformities_df'])} Points d'Intérêt**")
            if not metrics['top_non_conformities_df'].empty:
                 df_top_nc = metrics['top_non_conformities_df'].sort_values(by='Nombre Occurrences', ascending=True)
                 fig_bar_nc = px.bar(df_top_nc, x='Nombre Occurrences', y='Point de Contrôle', orientation='h', title="Points d'Intérêt les Plus Fréquents")
                 fig_bar_nc.update_layout(yaxis_title=None, xaxis_title="Nb Occurrences", height=350); st.plotly_chart(fig_bar_nc, use_container_width=True)
            else: st.caption("Aucun point d'intérêt.")
        with chart_cols[1]: # Graphiques Droite
            st.markdown("**Conformité par Catégorie**")
            if not metrics['category_compliance_rates_df'].empty:
                fig_bar_cat = px.bar(metrics['category_compliance_rates_df'], x='Catégorie', y='Taux Conformité (%)', title="Taux de Conformité Moyen par Catégorie", range_y=[0, 100], color='Taux Conformité (%)', color_continuous_scale=px.colors.sequential.Greens)
                fig_bar_cat.update_layout(xaxis_tickangle=-45, yaxis_title="Tx Conformité (%)", height=350); st.plotly_chart(fig_bar_cat, use_container_width=True)
            else: st.caption("Aucune donnée par catégorie.")

    # --- Onglet Liste des Inspections ---
    with tab_list:
        st.subheader(f"📋 Liste des Inspections Chargées ({len(st.session_state.loaded_inspections)})")
        if not st.session_state.loaded_inspections: st.info("Aucune inspection chargée.")
        else:
            for index, data in enumerate(st.session_state.loaded_inspections):
                inspection, model, filename, inspection_id = data['inspection'], data['model'], data['filename'], data['inspection']['id']
                has_poi = any(is_point_of_interest_enhanced(res, next((item for item in model.get('items', []) if item.get('ID_Point') == res.get('idPoint')), None)) for res in inspection.get('results', []) if isinstance(res, dict))
                expander_title = f"**{model.get('name', 'N/A')}** par **{inspection.get('inspectorName', 'N/A')}** (ID: ...{inspection_id[-8:]})"
                if has_poi: expander_title += " ⚠️"
                with st.expander(expander_title, expanded=False):
                    exp_cols = st.columns([3, 1])
                    with exp_cols[0]:
                        start_date_str = pd.to_datetime(inspection.get('startDate'), errors='coerce').strftime('%d/%m/%Y %H:%M') if inspection.get('startDate') else 'N/A'
                        st.caption(f"Fichier: {filename} | Statut: {inspection.get('status', 'N/A')} | Début: {start_date_str}")
                        if has_poi: poi_count = sum(1 for res in inspection.get('results', []) if isinstance(res, dict) and is_point_of_interest_enhanced(res, next((item for item in model.get('items', []) if item.get('ID_Point') == res.get('idPoint')), None))); st.warning(f"{poi_count} point(s) d'intérêt.", icon="⚠️")
                    with exp_cols[1]:
                        def set_detail_view_state(insp_id): st.session_state.selected_inspection_id_for_detail = insp_id; st.session_state.show_detail_dialog = True
                        st.button("👁️ Détails", key=f"detail_{inspection_id}_{index}", on_click=set_detail_view_state, args=(inspection_id,))
                        def remove_inspection(insp_id):
                            st.session_state.loaded_inspections = [insp for insp in st.session_state.loaded_inspections if insp['inspection']['id'] != insp_id]
                            keys_to_remove = [key for key in st.session_state.corrective_actions if key[0] == insp_id]; del st.session_state.action_dates[key] # Retirer aussi la planification
                            for key in keys_to_remove: del st.session_state.corrective_actions[key]
                            st.toast(f"Inspection ...{insp_id[-8:]} retirée.", icon="🗑️")
                            if st.session_state.selected_inspection_id_for_detail == insp_id: st.session_state.selected_inspection_id_for_detail = None; st.session_state.show_detail_dialog = False
                        st.button("🗑️ Retirer", key=f"remove_{inspection_id}_{index}", type="secondary", on_click=remove_inspection, args=(inspection_id,))

    # --- Onglet Vue Agrégée POI (Regroupée par catégorie) ---
    with tab_aggregated:
        st.subheader("🔍 Vue Agrégée des Points d'Intérêt (par Catégorie)")
        st.caption("Modifiez 'Statut Action' et 'Note Action' directement dans les tableaux ci-dessous.")
        aggregated_df_full = prepare_aggregated_dataframe()

        # Filtres Globaux pour cet onglet
        st.markdown("**Filtres Globaux :**")
        agg_filter_cols = st.columns(5)
        with agg_filter_cols[0]: st.session_state.agg_search = st.text_input("Recherche", value=st.session_state.agg_search, key="agg_search_input_tab")
        with agg_filter_cols[1]: inspectors = [''] + sorted(aggregated_df_full['Inspecteur'].astype(str).unique()); st.session_state.agg_insp_filter = st.selectbox("Inspecteur", options=inspectors, index=inspectors.index(st.session_state.agg_insp_filter) if st.session_state.agg_insp_filter in inspectors else 0, key="agg_insp_select_tab")
        with agg_filter_cols[2]: points_ctrl = [''] + sorted(aggregated_df_full['Point de Contrôle'].astype(str).unique()); st.session_state.agg_point_filter = st.selectbox("Point Contrôle", options=points_ctrl, index=points_ctrl.index(st.session_state.agg_point_filter) if st.session_state.agg_point_filter in points_ctrl else 0, key="agg_point_select_tab")
        with agg_filter_cols[3]: action_statuses = [''] + ['À traiter', 'En cours', 'Terminé', 'Annulé']; st.session_state.agg_status_filter = st.selectbox("Statut Action", options=action_statuses, index=action_statuses.index(st.session_state.agg_status_filter) if st.session_state.agg_status_filter in action_statuses else 0, key="agg_status_select_tab")
        with agg_filter_cols[4]: problem_types = [''] + sorted(aggregated_df_full['Type Problème'].astype(str).unique()); st.session_state.agg_problem_type_filter = st.selectbox("Type Problème", options=problem_types, index=problem_types.index(st.session_state.agg_problem_type_filter) if st.session_state.agg_problem_type_filter in problem_types else 0, key="agg_problem_type_select_tab")

        # Appliquer filtres globaux
        filtered_df = aggregated_df_full.copy()
        if st.session_state.agg_search:
            search_term_lower = st.session_state.agg_search.lower()
            text_search_cols = ['Point de Contrôle', 'Commentaire', 'Note Action', 'Résultat Obtenu', 'Critère Accept.', 'Type Problème']
            mask = pd.Series([False]*len(filtered_df));
            for col in text_search_cols:
                if col in filtered_df.columns: mask |= filtered_df[col].astype(str).str.lower().str.contains(search_term_lower, na=False)
            filtered_df = filtered_df[mask]
        if st.session_state.agg_insp_filter: filtered_df = filtered_df[filtered_df['Inspecteur'] == st.session_state.agg_insp_filter]
        if st.session_state.agg_point_filter: filtered_df = filtered_df[filtered_df['Point de Contrôle'] == st.session_state.agg_point_filter]
        if st.session_state.agg_status_filter: filtered_df = filtered_df[filtered_df['Statut Action'] == st.session_state.agg_status_filter]
        if st.session_state.agg_problem_type_filter: filtered_df = filtered_df[filtered_df['Type Problème'] == st.session_state.agg_problem_type_filter]

        st.divider()

        # Regroupement et affichage par catégorie
        if filtered_df.empty:
            if not aggregated_df_full.empty: st.warning("Aucun point ne correspond aux filtres.")
            else: st.info("Aucun point d'intérêt trouvé.")
        else:
            categories_filtered = filtered_df['Catégorie'].unique()
            cat_summary = {}
            for cat in categories_filtered:
                cat_df_filtered = filtered_df[filtered_df['Catégorie'] == cat]
                status_counts = cat_df_filtered['Statut Action'].value_counts().to_dict()
                total_cat = len(cat_df_filtered)
                cat_summary[cat] = {
                    'total': total_cat, 'status_counts': status_counts,
                    'percent_complete': (status_counts.get('Terminé', 0) / total_cat * 100) if total_cat > 0 else 0
                }
            sorted_categories = sorted(categories_filtered, key=lambda x: cat_summary[x]['total'], reverse=True)

            # Config commune pour les data_editors par catégorie
            column_config_agg = {
                "inspection_id_hidden": None, "point_id_hidden": None, "ID Unique": None, "Critère Accept.": None, "Catégorie": None, # Cacher car déjà dans l'expander
                "Date Insp.": st.column_config.DateColumn("Date", format="DD/MM/YY", disabled=True, width="small"),
                "ID Insp.": st.column_config.TextColumn("ID Insp.", disabled=True, width="small"),
                "Inspecteur": st.column_config.TextColumn("Inspecteur", disabled=True, width="small"),
                "Point de Contrôle": st.column_config.TextColumn("Point Contrôle", disabled=True, width="medium"),
                "Type Problème": st.column_config.TextColumn("Type Problème", width="medium", disabled=True),
                "Résultat Obtenu": st.column_config.TextColumn("Résultat", width="medium", disabled=True),
                "Commentaire": st.column_config.TextColumn("Commentaire", disabled=True, width="large"),
                "Photos Str": st.column_config.TextColumn("Photos", disabled=True, width="small"),
                "Statut Action": st.column_config.SelectboxColumn("Statut Action", width="medium", options=['À traiter', 'En cours', 'Terminé', 'Annulé'], required=True),
                "Note Action": st.column_config.TextColumn("Note Action", max_chars=200, width="large"),
            }
            column_order_agg = [ # Ordre sans Catégorie
                "Date Insp.", "Inspecteur", "Point de Contrôle", "Type Problème",
                "Résultat Obtenu", "Statut Action", "Note Action", "Commentaire", "Photos Str", "ID Insp."
            ]

            for cat in sorted_categories:
                summary = cat_summary[cat]
                # Calcul couleur progression
                completion_color_rgb = f"rgb({255 * (1 - summary['percent_complete']/100)}, {255 * (summary['percent_complete']/100)}, 0)"
                # Titre expander avec résumé
                expander_title = f"**{cat}** ({summary['total']} points) - "
                expander_title += f"🟢{summary['status_counts'].get('Terminé', 0)} "
                expander_title += f"🟠{summary['status_counts'].get('En cours', 0)} "
                expander_title += f"🔴{summary['status_counts'].get('À traiter', 0)}"

                with st.expander(expander_title, expanded=True): # Ouvrir par défaut ?
                    # Barre progression visuelle
                    progress_html = f"""<div style="width:100%; background-color:#f0f0f0; height:10px; border-radius:5px; margin: 5px 0 10px 0;">
                                         <div style="width:{summary['percent_complete']}%; background: linear-gradient(to right, #f97316, #22c55e); height:10px; border-radius:5px;"></div></div>""" # Dégradé orange vers vert
                    st.markdown(progress_html, unsafe_allow_html=True)

                    # Afficher le data editor pour cette catégorie
                    cat_df_display = filtered_df[filtered_df['Catégorie'] == cat]
                    edited_cat_df = st.data_editor(
                        cat_df_display, key=f"cat_editor_{cat.replace(' ', '_').replace('/', '_')}", # Clé unique et valide
                        use_container_width=True, hide_index=True,
                        column_config=column_config_agg, column_order=column_order_agg,
                        num_rows="dynamic" # Ajuster hauteur dynamiquement
                    )
                    # Mise à jour de l'état après édition
                    update_corrective_actions_from_df(edited_cat_df)

    # --- Onglet Suivi Actions (Amélioré) ---
    with tab_actions:
        st.subheader("📝 Suivi des Actions Correctives")
        if not st.session_state.corrective_actions: st.info("Aucune action corrective enregistrée.")
        else:
            # Préparer le DataFrame complet des actions
            action_data = []
            for (inspection_id, point_id), action_info in st.session_state.corrective_actions.items():
                inspection_data = next((data for data in st.session_state.loaded_inspections if data['inspection']['id'] == inspection_id), None)
                if not inspection_data: continue
                inspection, model = inspection_data['inspection'], inspection_data['model']
                point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
                result_data = next((r for r in inspection.get('results', []) if isinstance(r, dict) and r.get('idPoint') == point_id), None)
                if not point_model or not result_data: continue
                problem_type, result_display_formatted = get_problem_type_and_display(result_data, point_model)
                planning_info = st.session_state.action_dates.get((inspection_id, point_id), {'due_date': None, 'assigned_to': 'N/A'})
                action_data.append({
                    'ID Action': f"{inspection_id[:8]}_{point_id}",
                    'Date Inspection': pd.to_datetime(inspection.get('startDate'), errors='coerce').date() if inspection.get('startDate') else None,
                    'Inspecteur': inspection.get('inspectorName', 'N/A'),
                    'Catégorie': point_model.get('Categorie', 'N/A'),
                    'Point de Contrôle': point_model.get('PointDeControle', 'N/A'),
                    'Type Problème': problem_type,
                    'Résultat': result_display_formatted, # Utiliser la version formatée
                    'Statut': action_info.get('status', 'À traiter'),
                    'Note': action_info.get('note', ''),
                    'Date Échéance': planning_info.get('due_date'),
                    'Responsable': planning_info.get('assigned_to', 'N/A'),
                    'inspection_id': inspection_id, 'point_id': point_id
                })
            actions_df = pd.DataFrame(action_data)
            if 'Date Échéance' in actions_df.columns: actions_df['Date Échéance'] = pd.to_datetime(actions_df['Date Échéance'], errors='coerce').dt.date

            # -- Sous-onglets pour l'organisation --
            action_tabs = st.tabs(["➡️ Liste & Édition", "🗓️ Planification & Calendrier", "📊 Statistiques Actions"])

            # --- Sous-onglet Liste & Édition ---
            with action_tabs[0]:
                st.markdown("#### Liste des Actions")
                # Filtres pour la liste
                list_filter_cols = st.columns(4)
                with list_filter_cols[0]: st.session_state.action_status_filter = st.multiselect("Filtrer Statut", options=['À traiter', 'En cours', 'Terminé', 'Annulé'], default=st.session_state.action_status_filter, key="action_list_status_filter")
                with list_filter_cols[1]: action_cats = sorted(actions_df['Catégorie'].unique()); st.session_state.action_category_filter = st.multiselect("Filtrer Catégorie", options=action_cats, default=st.session_state.action_category_filter, key="action_list_cat_filter")
                with list_filter_cols[2]: action_problems = sorted(actions_df['Type Problème'].unique()); st.session_state.action_problem_type_filter = st.multiselect("Filtrer Type Problème", options=action_problems, default=st.session_state.action_problem_type_filter, key="action_list_prob_filter")
                with list_filter_cols[3]: st.session_state.action_search_term = st.text_input("Recherche", value=st.session_state.action_search_term, key="action_list_search")

                # Application des filtres
                filtered_actions = actions_df.copy()
                if st.session_state.action_status_filter: filtered_actions = filtered_actions[filtered_actions['Statut'].isin(st.session_state.action_status_filter)]
                if st.session_state.action_category_filter: filtered_actions = filtered_actions[filtered_actions['Catégorie'].isin(st.session_state.action_category_filter)]
                if st.session_state.action_problem_type_filter: filtered_actions = filtered_actions[filtered_actions['Type Problème'].isin(st.session_state.action_problem_type_filter)]
                if st.session_state.action_search_term:
                    search_mask = pd.Series([False]*len(filtered_actions)); search_cols = ['Point de Contrôle', 'Note', 'Résultat', 'Inspecteur', 'Responsable']
                    for col in search_cols: search_mask |= filtered_actions[col].astype(str).str.contains(st.session_state.action_search_term, case=False, na=False)
                    filtered_actions = filtered_actions[search_mask]

                # Affichage de l'éditeur ou de la liste
                if st.session_state.editing_action:
                    action_row = filtered_actions[(filtered_actions['inspection_id'] == st.session_state.editing_action[0]) & (filtered_actions['point_id'] == st.session_state.editing_action[1])]
                    if not action_row.empty:
                        # --- Fonction interne pour l'éditeur d'action ---
                        def display_action_editor(row_data):
                            st.markdown(f"#### Édition Action : {row_data['Point de Contrôle']}")
                            edit_cols = st.columns([2, 3]) # Colonnes pour infos et édition
                            with edit_cols[0]: # Informations
                                st.markdown(f"**Catégorie:** {row_data['Catégorie']} | **Insp.:** {row_data['Inspecteur']} ({pd.to_datetime(row_data['Date Inspection']).strftime('%d/%m/%y')})")
                                st.markdown(f"**Problème:** {row_data['Type Problème']} | **Résultat:** {row_data['Résultat']}", unsafe_allow_html=True)
                                # Statut
                                status_options = ['À traiter', 'En cours', 'Terminé', 'Annulé']
                                status_colors = {'À traiter': '#ef4444','En cours': '#f97316','Terminé': '#22c55e','Annulé': '#6b7280'}
                                current_status = row_data['Statut']
                                new_status = st.selectbox("Statut Action", options=status_options, index=status_options.index(current_status), key=f"status_edit_{row_data['inspection_id']}_{row_data['point_id']}")
                                st.markdown(f"""<div style='background-color:{status_colors.get(new_status, '#6b7280')}; color:white; padding:8px; border-radius:4px; text-align:center; font-weight:bold; margin-bottom:15px;'>{new_status}</div>""", unsafe_allow_html=True)
                            with edit_cols[1]: # Note et Planification
                                new_note = st.text_area("Note d'action", value=row_data['Note'], height=150, placeholder="Actions correctives...", key=f"note_edit_{row_data['inspection_id']}_{row_data['point_id']}")
                                plan_info = st.session_state.action_dates.get((row_data['inspection_id'], row_data['point_id']), {'due_date': None, 'assigned_to': 'N/A'})
                                new_due_date = st.date_input("Date Échéance", value=plan_info['due_date'], key=f"date_edit_{row_data['inspection_id']}_{row_data['point_id']}")
                                new_assigned_to = st.text_input("Responsable", value=plan_info['assigned_to'], key=f"resp_edit_{row_data['inspection_id']}_{row_data['point_id']}")
                            # Boutons
                            btn_cols = st.columns(2)
                            if btn_cols[0].button("💾 Enregistrer", type="primary", key=f"save_{row_data['inspection_id']}_{row_data['point_id']}"):
                                action_key = (row_data['inspection_id'], row_data['point_id'])
                                st.session_state.corrective_actions[action_key] = {'status': new_status, 'note': new_note}
                                st.session_state.action_dates[action_key] = {'due_date': new_due_date, 'assigned_to': new_assigned_to}
                                st.toast("Action mise à jour !"); st.session_state.editing_action = None; st.rerun()
                            if btn_cols[1].button("❌ Annuler", key=f"cancel_{row_data['inspection_id']}_{row_data['point_id']}"): st.session_state.editing_action = None; st.rerun()
                            # Affichage photos (si présentes)
                            insp_data = next((d for d in st.session_state.loaded_inspections if d['inspection']['id'] == row_data['inspection_id']), None)
                            res_data = next((r for r in insp_data['inspection'].get('results', []) if isinstance(r, dict) and r.get('idPoint') == row_data['point_id']), None) if insp_data else None
                            photos = res_data.get('photosBase64', []) if res_data else []
                            if photos:
                                st.markdown("---"); st.markdown("**Photos Associées**")
                                photo_display_cols = st.columns(min(len(photos), 4))
                                for i, b64 in enumerate(photos):
                                     with photo_display_cols[i % 4]:
                                          try:
                                               if isinstance(b64, str) and ',' in b64: b64 = b64.split(',')[1]
                                               st.image(base64.b64decode(b64), width=100)
                                          except: st.caption("Err. Photo")
                        # --- Fin Fonction Interne ---
                        display_action_editor(action_row.iloc[0])
                    else: st.error("Action introuvable!"); st.session_state.editing_action = None
                else: # Affichage de la liste si pas d'édition en cours
                    if filtered_actions.empty: st.info("Aucune action ne correspond aux filtres.")
                    else:
                        st.markdown(f"Affichage de **{len(filtered_actions)}** action(s)")
                        status_colors_map = {'À traiter': '#ef4444','En cours': '#f97316','Terminé': '#22c55e','Annulé': '#6b7280'}
                        for i, row in filtered_actions.sort_values(by=['Statut', 'Date Inspection'], ascending=[True, True]).iterrows():
                            st.markdown(f"<div class='action-card' style='border-left-color: {status_colors_map.get(row['Statut'], '#6b7280')};'>", unsafe_allow_html=True)
                            list_cols = st.columns([3, 2, 1]) # Point | Statut/Note | Bouton
                            with list_cols[0]:
                                st.markdown(f"**{row['Point de Contrôle']}**")
                                st.caption(f"{row['Catégorie']} | {row['Inspecteur']} ({pd.to_datetime(row['Date Inspection']).strftime('%d/%m/%y')}) | {row['Type Problème']}")
                            with list_cols[1]:
                                st.markdown(f"**{row['Statut']}** {('🗓️ '+pd.to_datetime(row['Date Échéance']).strftime('%d/%m/%y')) if pd.notna(row['Date Échéance']) else ''} {('👤 '+row['Responsable']) if row['Responsable'] != 'N/A' and row['Responsable'] else ''}")
                                note_preview = (row['Note'][:60] + "...") if isinstance(row['Note'], str) and len(row['Note']) > 60 else row['Note']
                                st.caption(f"{note_preview or 'Aucune note'}")
                            with list_cols[2]:
                                def edit_action(insp_id, p_id): st.session_state.editing_action = (insp_id, p_id)
                                st.button("✏️ Éditer/Voir", key=f"edit_btn_{row['inspection_id']}_{row['point_id']}", on_click=edit_action, args=(row['inspection_id'], row['point_id']))
                            st.markdown("</div>", unsafe_allow_html=True)

            # --- Sous-onglet Planification & Calendrier ---
            with action_tabs[1]:
                st.markdown("#### Planification des Actions")
                plan_cols = st.columns([2, 1]) # Colonne pour tableau, colonne pour calendrier ?
                with plan_cols[0]: # Tableau éditable de planification
                    plan_data = []
                    for (inspection_id, point_id), action_info in st.session_state.corrective_actions.items():
                        if action_info.get('status') in ['Terminé', 'Annulé']: continue # Exclure terminés/annulés
                        insp_data=next((d for d in st.session_state.loaded_inspections if d['inspection']['id']==inspection_id), None)
                        if not insp_data: continue
                        point_model = next((item for item in insp_data['model'].get('items',[]) if item.get('ID_Point') == point_id), None)
                        plan_info = st.session_state.action_dates.get((inspection_id, point_id), {'due_date': None, 'assigned_to': 'N/A'})
                        plan_data.append({
                            'ID Action': f"{inspection_id[:8]}_{point_id}", 'Catégorie': point_model.get('Categorie', 'N/A') if point_model else 'N/A',
                            'Point de Contrôle': point_model.get('PointDeControle', 'N/A') if point_model else 'N/A',
                            'Statut': action_info.get('status', 'À traiter'), 'Date Échéance': plan_info.get('due_date'), 'Responsable': plan_info.get('assigned_to', 'N/A'),
                            'inspection_id': inspection_id, 'point_id': point_id
                        })
                    plan_df = pd.DataFrame(plan_data)
                    if plan_df.empty: st.info("Aucune action à planifier (vérifiez les filtres ou toutes les actions sont terminées/annulées).")
                    else:
                        edited_plan_df = st.data_editor(plan_df, key="planning_editor", hide_index=True, use_container_width=True,
                            column_config={
                                "ID Action": None, "inspection_id": None, "point_id": None, # Cacher IDs
                                "Catégorie": st.column_config.TextColumn("Catégorie", disabled=True, width="medium"),
                                "Point de Contrôle": st.column_config.TextColumn("Point", disabled=True, width="large"),
                                "Statut": st.column_config.TextColumn("Statut", disabled=True, width="small"),
                                "Date Échéance": st.column_config.DateColumn("Date Échéance", format="DD/MM/YYYY", min_value=datetime.now().date(), width="medium", help="Date cible"),
                                "Responsable": st.column_config.TextColumn("Responsable", width="medium", help="Qui doit faire l'action ?")
                            },
                            column_order=["Point de Contrôle", "Catégorie", "Statut", "Date Échéance", "Responsable"]
                        )
                        # Mise à jour de la planification après édition
                        def update_planning_state(edited_plan_dataframe):
                            plan_updates = 0
                            for _, row in edited_plan_dataframe.iterrows():
                                action_key = (row['inspection_id'], row['point_id'])
                                current_planning = st.session_state.action_dates.get(action_key, {'due_date': None, 'assigned_to': 'N/A'})
                                new_date = pd.to_datetime(row['Date Échéance']).date() if pd.notna(row['Date Échéance']) else None
                                new_resp = row['Responsable'] if pd.notna(row['Responsable']) else ""
                                if current_planning.get('due_date') != new_date or current_planning.get('assigned_to') != new_resp:
                                    st.session_state.action_dates[action_key] = {'due_date': new_date, 'assigned_to': new_resp}
                                    plan_updates += 1
                            # if plan_updates > 0: st.toast(f"{plan_updates} planification(s) mise(s) à jour.", icon="🗓️")
                        update_planning_state(edited_plan_df)

                with plan_cols[1]: # Calendrier
                    st.markdown("##### Calendrier des Échéances")
                    # Préparer les données pour le calendrier
                    calendar_events = {}
                    status_color_map_cal = {'À traiter': 'red','En cours': 'orange','Terminé': 'green','Annulé': 'grey'}
                    for (insp_id, p_id), plan_info in st.session_state.action_dates.items():
                        due_date = plan_info.get('due_date');
                        if due_date:
                             if isinstance(due_date, str): # Convertir si besoin
                                try: due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
                                except: continue
                             date_str = due_date.strftime("%Y-%m-%d")
                             action_info = st.session_state.corrective_actions.get((insp_id, p_id), {})
                             insp_data = next((d for d in st.session_state.loaded_inspections if d['inspection']['id'] == insp_id), None)
                             point_model = next((item for item in insp_data['model'].get('items', []) if item.get('ID_Point') == p_id), None) if insp_data else None
                             if point_model:
                                 status = action_info.get('status', '?')
                                 color = status_color_map_cal.get(status, 'grey')
                                 event_text = f"{point_model.get('PointDeControle', '?')} ({plan_info.get('assigned_to', 'N/A')})"
                                 calendar_events.setdefault(date_str, []).append({'title': event_text, 'color': color})

                    # Utiliser un composant calendrier (simpliste ici, des composants externes existent)
                    selected_date = st.date_input("Choisir une date pour voir les échéances", datetime.now().date())
                    st.write(f"Échéances pour le {selected_date.strftime('%d/%m/%Y')}:")
                    events_today = calendar_events.get(selected_date.strftime("%Y-%m-%d"), [])
                    if events_today:
                        for event in events_today:
                            st.markdown(f"<span style='color:{event['color']}; font-weight:bold;'>•</span> {event['title']}", unsafe_allow_html=True)
                    else: st.caption("Aucune échéance ce jour.")
                    # Une vraie vue calendrier serait plus complexe à implémenter manuellement

            # --- Sous-onglet Statistiques Actions ---
            with action_tabs[2]:
                st.markdown("#### Statistiques des Actions")
                if actions_df.empty: st.info("Aucune action pour les statistiques.")
                else:
                    stats_cols = st.columns(2)
                    with stats_cols[0]: # Répartition par Statut
                        status_counts_stats = actions_df['Statut'].value_counts().reset_index(); status_counts_stats.columns = ['Statut', 'Nombre']
                        fig_status_stats = px.pie(status_counts_stats, names='Statut', values='Nombre', title="Répartition Statuts", hole=0.4, color='Statut', color_discrete_map=status_color_map_cal)
                        st.plotly_chart(fig_status_stats, use_container_width=True)
                    with stats_cols[1]: # Répartition par Catégorie
                        cat_counts_stats = actions_df.groupby('Catégorie')['Statut'].value_counts().unstack().fillna(0)
                        if not cat_counts_stats.empty:
                            fig_cat_stats = px.bar(cat_counts_stats, title="Actions par Catégorie et Statut", barmode='stack', color_discrete_map=status_color_map_cal)
                            fig_cat_stats.update_layout(xaxis_title=None, yaxis_title="Nombre d'actions")
                            st.plotly_chart(fig_cat_stats, use_container_width=True)
                        else: st.caption("Pas assez de données par catégorie.")
                    # Actions par Responsable
                    if 'Responsable' in actions_df.columns:
                        resp_stats = actions_df[actions_df['Responsable'] != 'N/A'].groupby('Responsable')['Statut'].value_counts().unstack().fillna(0)
                        if not resp_stats.empty:
                            st.markdown("##### Actions par Responsable")
                            resp_stats['Total'] = resp_stats.sum(axis=1); resp_stats = resp_stats.sort_values('Total', ascending=False)
                            st.dataframe(resp_stats, use_container_width=True)

# --- Modale Détail ---
if st.session_state.show_detail_dialog and st.session_state.selected_inspection_id_for_detail:
    inspection_to_show = next((insp for insp in st.session_state.loaded_inspections if insp['inspection']['id'] == st.session_state.selected_inspection_id_for_detail), None)
    if inspection_to_show:
        @st.dialog("Détails de l'Inspection", WIDE=True) # Utiliser toute la largeur pour la modale détail
        def show_detail_modal():
            render_inspection_detail(inspection_to_show)
            def close_detail_modal(): setattr(st.session_state, 'show_detail_dialog', False)
            st.button("Fermer Détails", key="close_detail_dialog_button", on_click=close_detail_modal, type="primary")
        show_detail_modal()
    else: st.session_state.selected_inspection_id_for_detail = None; st.session_state.show_detail_dialog = False # Nettoyer si ID invalide

# --- Modale Photo (Améliorée) ---
if st.session_state.show_photo_modal and st.session_state.modal_photo_list:
    @st.dialog("Visualiseur de Photos")
    def show_photo_viewer():
        st.subheader(st.session_state.modal_photo_caption)
        current_index = st.session_state.modal_photo_index
        photos = st.session_state.modal_photo_list
        num_photos = len(photos)
        try:
            b64_string = photos[current_index]; img_container = st.container()
            if isinstance(b64_string, str) and ',' in b64_string: b64_string = b64_string.split(',')[1]
            img_bytes = base64.b64decode(b64_string)
            with img_container: st.image(img_bytes, use_column_width=True)
        except Exception as e: st.error(f"Affichage image {current_index + 1} impossible: {e}")

        # Navigation et Miniatures
        if num_photos > 1:
            nav_cols = st.columns([1, 6, 1]) # Ratios pour boutons et miniatures
            with nav_cols[0]: # Précédent
                def go_prev_photo(): st.session_state.modal_photo_index = (current_index - 1 + num_photos) % num_photos # Boucle
                st.button("⬅️", key="prev_photo", on_click=go_prev_photo, help="Photo précédente", use_container_width=True)
            with nav_cols[1]: # Miniatures
                st.markdown(f"<div style='text-align:center; margin-bottom: 5px;'>Photo {current_index + 1} / {num_photos}</div>", unsafe_allow_html=True)
                num_thumbnails = min(num_photos, 7) # Afficher jusqu'à 7 miniatures
                thumb_indices = [(current_index - (num_thumbnails//2) + i + num_photos) % num_photos for i in range(num_thumbnails)] # Centrer sur l'actuelle
                thumbnail_cols = st.columns(num_thumbnails)
                for i, idx in enumerate(thumb_indices):
                    with thumbnail_cols[i]:
                        try:
                            thumb_b64 = photos[idx]; thumb_style = "padding:2px; border-radius:4px; cursor:pointer; aspect-ratio: 1 / 1; object-fit: cover;" # Style vignette
                            if isinstance(thumb_b64, str) and ',' in thumb_b64: thumb_b64 = thumb_b64.split(',')[1]
                            thumb_bytes = base64.b64decode(thumb_b64)
                            if idx == current_index: thumb_style += " border:3px solid #3b82f6; box-shadow:0 0 5px #3b82f6;"
                            else: thumb_style += " border:1px solid #e5e7eb; opacity:0.6;"
                            st.markdown(f"<div style='{thumb_style}'>", unsafe_allow_html=True)
                            st.image(thumb_bytes, width=60) # Taille fixe pour miniatures
                            st.markdown("</div>", unsafe_allow_html=True)
                            def go_to_photo(idx_to_go): st.session_state.modal_photo_index = idx_to_go
                            # Bouton invisible sur l'image pour le clic
                            st.button(" ", key=f"thumb_{idx}", on_click=go_to_photo, args=(idx,), help=f"Voir photo {idx+1}")
                        except: pass # Ignorer erreur vignette
            with nav_cols[2]: # Suivant
                def go_next_photo(): st.session_state.modal_photo_index = (current_index + 1) % num_photos # Boucle
                st.button("➡️", key="next_photo", on_click=go_next_photo, help="Photo suivante", use_container_width=True)
        st.divider()
        def close_photo_viewer(): setattr(st.session_state, 'show_photo_modal', False)
        st.button("Fermer Visualiseur", key="close_photo_modal_button", on_click=close_photo_viewer, type="primary")
    show_photo_viewer()

# --- Barre de Statut Globale (si des inspections sont chargées) ---
if st.session_state.loaded_inspections:
    st.divider()
    total_actions = len(st.session_state.corrective_actions)
    actions_status = {'À traiter': 0, 'En cours': 0, 'Terminé': 0, 'Annulé': 0}
    for action_info in st.session_state.corrective_actions.values(): status = action_info.get('status', 'À traiter'); actions_status[status] += 1 if status in actions_status else 0
    completion_percent = ((actions_status['Terminé'] + actions_status['Annulé']) / total_actions * 100) if total_actions > 0 else 0
    # Barre de progression visuelle HTML
    progress_html = f"""
    <div style='margin:10px 0;'>
        <div style='display:flex; justify-content:space-between; margin-bottom:5px; font-size: 0.9em;'>
            <span>Progression Actions Correctives</span><span><b>{actions_status['Terminé']}/{total_actions}</b> ({completion_percent:.0f}%)</span>
        </div>
        <div style='width:100%; background-color:#e5e7eb; height:15px; border-radius:10px; overflow:hidden; display:flex;'>
            <div style='background-color:#22c55e; width:{100*actions_status['Terminé']/total_actions if total_actions > 0 else 0}%;' title='Terminé: {actions_status['Terminé']}'></div>
            <div style='background-color:#f97316; width:{100*actions_status['En cours']/total_actions if total_actions > 0 else 0}%;' title='En cours: {actions_status['En cours']}'></div>
            <div style='background-color:#ef4444; width:{100*actions_status['À traiter']/total_actions if total_actions > 0 else 0}%;' title='À traiter: {actions_status['À traiter']}'></div>
            <div style='background-color:#6b7280; width:{100*actions_status['Annulé']/total_actions if total_actions > 0 else 0}%;' title='Annulé: {actions_status['Annulé']}'></div>
        </div>
    </div>"""
    st.markdown(progress_html, unsafe_allow_html=True)

# --- Pied de page ---
st.divider()
st.caption("Visualiseur v2.0 (Suivi Amélioré, Planification, Export Excel) - Mode Volatile")
st.caption("⚠️ Données de suivi (Statuts, Notes, Planification) perdues à la fermeture. Utilisez l'export Excel pour sauvegarder.")
