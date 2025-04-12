),
                        "Inspecteur": st.column_config.TextColumn(
                            "Inspecteur",
                            disabled=True
                        ),
                        "Catégorie": st.column_config.TextColumn(
                            "Catégorie",
                            disabled=True
                        ),
                        "Point de Contrôle": st.column_config.TextColumn(
                            "Point de Contrôle",
                            width="medium",
                            disabled=True
                        ),
                        "Critère Accept.": st.column_config.TextColumn(
                            "Critère",
                            width="small",
                            disabled=True
                        ),
                        "Résultat Obtenu": st.column_config.TextColumn(
                            "Résultat",
                            width="small",
                            disabled=True
                        ),
                        "Commentaire": st.column_config.TextColumn(
                            "Commentaire",
                            width="medium",
                            disabled=True
                        ),
                        "Nb Photos": st.column_config.NumberColumn(
                            "Photos",
                            format="%d 📷",
                            disabled=True
                        ),
                        "Statut Action": st.column_config.SelectboxColumn(
                            "Statut Action",
                            help="Statut du suivi de l'action corrective",
                            options=['À traiter', 'En cours', 'Terminé', 'Annulé'],
                            required=True
                        ),
                        "Note Action": st.column_config.TextColumn(
                            "Note Action",
                            help="Note libre sur l'action corrective (max 200 caractères)",
                            max_chars=200,
                            width="large"
                        ),
                    },
                    column_order=[
                        "Date Insp.", "Inspecteur", "Catégorie", "Point de Contrôle",
                        "Résultat Obtenu", "Commentaire", "Nb Photos",
                        "Statut Action", "Note Action", "ID Insp.", "Critère Accept."
                    ],
                    num_rows="fixed"
                )
            elif selected_view == "Mode carte":
                # Mode carte avec affichage visuel des non-conformités
                for i, row in paginated_df.iterrows():
                    with st.container():
                        st.markdown(f"""
                        <div style="background-color:white; padding:1rem; border-radius:0.5rem; box-shadow:0 1px 3px rgba(0,0,0,0.1); margin-bottom:1rem;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                                <div>
                                    <span style="font-size:0.8rem; color:#6B7280;">{format_date(row['Date Insp.'], include_time=False)} | {row['Inspecteur']}</span>
                                </div>
                                <div>
                                    {status_to_badge(row['Statut Action'])}
                                </div>
                            </div>
                            <h4 style="margin:0.25rem 0; font-size:1.1rem; color:#1E3A8A;">{row['Point de Contrôle']}</h4>
                            <p style="font-size:0.9rem; color:#4B5563; margin:0.25rem 0;"><strong>Catégorie:</strong> {row['Catégorie']}</p>
                            <p style="font-size:0.9rem; margin:0.25rem 0;"><strong>Résultat:</strong> <span style="color:red;">{row['Résultat Obtenu']}</span></p>
                            
                            <div style="display:flex; margin-top:0.75rem;">
                                <div style="flex:2;">
                                    <div style="font-size:0.85rem; background-color:#F3F4F6; padding:0.5rem; border-radius:0.25rem; margin-bottom:0.5rem;">
                                        <strong>Note:</strong> {row['Note Action'] or "Aucune note ajoutée"}
                                    </div>
                                    <div style="font-size:0.85rem;">
                                        <strong>Commentaire inspecteur:</strong> {row['Commentaire'] or "Aucun commentaire"}
                                    </div>
                                </div>
                                <div style="flex:1; text-align:center;">
                        """, unsafe_allow_html=True)
                        
                        # Boutons d'action pour chaque carte
                        cols = st.columns([1, 1])
                        with cols[0]:
                            # Bouton pour éditer le statut
                            if st.button("✏️ Modifier", key=f"edit_{row['inspection_id_hidden']}_{row['point_id_hidden']}"):
                                # Ici on peut afficher un formulaire d'édition spécifique à cette carte
                                st.session_state[f"edit_mode_{row['inspection_id_hidden']}_{row['point_id_hidden']}"] = True
                                st.rerun()
                        
                        with cols[1]:
                            # Bouton pour voir les photos si disponibles
                            has_photos = row['Nb Photos'] > 0
                            if has_photos and st.button("📷 Photos", key=f"photos_{row['inspection_id_hidden']}_{row['point_id_hidden']}"):
                                # Trouver l'inspection et le point correspondants pour récupérer les photos
                                inspection_data = next((data for data in st.session_state.loaded_inspections if data['inspection']['id'] == row['inspection_id_hidden']), None)
                                if inspection_data:
                                    result_data = next((r for r in inspection_data['inspection'].get('results', []) if r.get('idPoint') == row['point_id_hidden']), None)
                                    if result_data and 'photosBase64' in result_data:
                                        st.session_state.modal_photo_list = result_data['photosBase64']
                                        st.session_state.modal_photo_index = 0
                                        st.session_state.modal_photo_caption = f"Photos - {row['Point de Contrôle']}"
                                        st.session_state.show_photo_modal = True
                                        st.rerun()
                        
                        # Afficher le formulaire d'édition si en mode édition
                        edit_state_key = f"edit_mode_{row['inspection_id_hidden']}_{row['point_id_hidden']}"
                        if st.session_state.get(edit_state_key, False):
                            with st.form(key=f"edit_form_{row['inspection_id_hidden']}_{row['point_id_hidden']}"):
                                st.subheader("Mettre à jour l'action corrective")
                                new_status = st.selectbox(
                                    "Statut",
                                    options=['À traiter', 'En cours', 'Terminé', 'Annulé'],
                                    index=['À traiter', 'En cours', 'Terminé', 'Annulé'].index(row['Statut Action']),
                                    key=f"new_status_{row['inspection_id_hidden']}_{row['point_id_hidden']}"
                                )
                                new_note = st.text_area(
                                    "Note",
                                    value=row['Note Action'],
                                    key=f"new_note_{row['inspection_id_hidden']}_{row['point_id_hidden']}",
                                    height=100
                                )
                                
                                # Boutons de sauvegarde/annulation
                                cols = st.columns([1, 1])
                                with cols[0]:
                                    cancel = st.form_submit_button("Annuler")
                                    if cancel:
                                        st.session_state[edit_state_key] = False
                                        st.rerun()
                                
                                with cols[1]:
                                    submit = st.form_submit_button("Enregistrer")
                                    if submit:
                                        # Mettre à jour l'action corrective
                                        action_key = (row['inspection_id_hidden'], row['point_id_hidden'])
                                        st.session_state.corrective_actions[action_key] = {
                                            'status': new_status,
                                            'note': new_note
                                        }
                                        
                                        # Sauvegarder en BDD si mode persistant
                                        if st.session_state.persistent_mode:
                                            save_corrective_action(
                                                row['inspection_id_hidden'],
                                                row['point_id_hidden'],
                                                new_status,
                                                new_note
                                            )
                                        
                                        st.session_state[edit_state_key] = False
                                        st.toast("Action corrective mise à jour !", icon="✅")
                                        st.rerun()
                        
                        st.markdown("""
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            
            elif selected_view == "Mode compact":
                # Mode compact avec une liste dense
                for i, row in paginated_df.iterrows():
                    has_photos = row['Nb Photos'] > 0
                    photo_icon = "📷 " if has_photos else ""
                    
                    st.markdown(f"""
                    <div style="display:flex; align-items:center; padding:0.5rem; border-bottom:1px solid #E5E7EB; font-size:0.9rem;">
                        <div style="width:15%;">{format_date(row['Date Insp.'], include_time=False)}</div>
                        <div style="width:20%;">{row['Catégorie']}</div>
                        <div style="width:30%; font-weight:500;">{row['Point de Contrôle']}</div>
                        <div style="width:15%;">{status_to_badge(row['Statut Action'])}</div>
                        <div style="width:10%; text-align:center;">{photo_icon}{row['Nb Photos'] if has_photos else ""}</div>
                        <div style="width:10%; text-align:right;">
                            <button id="btn_{i}" style="background:none; border:none; cursor:pointer; color:#3B82F6; font-size:0.9rem;">
                                Détails
                            </button>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Ajouter un gestionnaire pour le bouton avec streamlit
                    if st.button("Voir détails", key=f"compact_btn_{i}", help="Voir les détails de cette non-conformité"):
                        # Afficher les détails dans un expander
                        with st.expander("Détails de la non-conformité", expanded=True):
                            st.markdown(f"""
                            <h4 style="margin:0.25rem 0; font-size:1.1rem;">{row['Point de Contrôle']}</h4>
                            <p><strong>Catégorie:</strong> {row['Catégorie']}</p>
                        <p><strong>Fréquence:</strong> {row['Occurrences']} occurrences dans {row['Inspections']} inspections</p>
                        <p><strong>Critère d'acceptation:</strong> {row['Critère']}</p>
                        <div style="display:flex;">
                            <div style="background-color:#FEF2F2; padding:0.5rem; border-radius:0.25rem; margin-right:0.5rem;">
                                <strong style="color:#991B1B;">Cause probable:</strong> Erreur répétitive du processus ou du matériel
                            </div>
                            <div style="background-color:#F0FDF4; padding:0.5rem; border-radius:0.25rem;">
                                <strong style="color:#065F46;">Action recommandée:</strong> Révision des procédures et formation
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Pas assez de données pour identifier les non-conformités récurrentes. Chargez plus d'inspections.")
                
        elif report_type == "Performance par inspecteur":
            st.markdown("#### Analyse des performances par inspecteur")
            
            # Collecter les données par inspecteur
            inspectors_data = {}
            
            for data in st.session_state.loaded_inspections:
                inspection = data['inspection']
                model = data['model']
                inspector = inspection.get('inspectorName', 'Inconnu')
                
                if inspector not in inspectors_data:
                    inspectors_data[inspector] = {
                        'inspections': 0,
                        'points_checked': 0,
                        'points_conform': 0,
                        'non_conformities': 0,
                        'categories': {}
                    }
                
                inspectors_data[inspector]['inspections'] += 1
                
                for result in inspection.get('results', []):
                    point_id = result.get('idPoint')
                    if not point_id: continue
                    
                    point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
                    if not point_model: continue
                    
                    category = point_model.get('Categorie', 'Sans catégorie')
                    if category not in inspectors_data[inspector]['categories']:
                        inspectors_data[inspector]['categories'][category] = {
                            'checked': 0,
                            'conform': 0
                        }
                    
                    # Ne pas compter les points N/A
                    if result.get('isNA', False):
                        continue
                    
                    inspectors_data[inspector]['points_checked'] += 1
                    inspectors_data[inspector]['categories'][category]['checked'] += 1
                    
                    if is_point_of_interest(result, point_model):
                        inspectors_data[inspector]['non_conformities'] += 1
                    else:
                        inspectors_data[inspector]['points_conform'] += 1
                        inspectors_data[inspector]['categories'][category]['conform'] += 1
            
            # Créer un DataFrame pour les inspecteurs
            insp_data = []
            for inspector, data in inspectors_data.items():
                if data['points_checked'] > 0:
                    conformity_rate = (data['points_conform'] / data['points_checked']) * 100
                    insp_data.append({
                        'Inspecteur': inspector,
                        'Taux de conformité (%)': conformity_rate,
                        'Inspections réalisées': data['inspections'],
                        'Points vérifiés': data['points_checked'],
                        'Non-conformités relevées': data['non_conformities']
                    })
            
            insp_df = pd.DataFrame(insp_data)
            
            if not insp_df.empty:
                # Graphique des taux de conformité par inspecteur
                fig = px.bar(
                    insp_df.sort_values('Taux de conformité (%)'),
                    x='Inspecteur',
                    y='Taux de conformité (%)',
                    color='Taux de conformité (%)',
                    text='Taux de conformité (%)',
                    hover_data=['Inspections réalisées', 'Points vérifiés', 'Non-conformités relevées'],
                    color_continuous_scale=px.colors.sequential.Blues,
                    title="Taux de conformité par inspecteur"
                )
                
                fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig.update_layout(
                    height=400,
                    xaxis_title="Inspecteur",
                    yaxis_title="Taux de conformité (%)"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Graphique camembert du nombre d'inspections par inspecteur
                fig2 = px.pie(
                    insp_df,
                    names='Inspecteur',
                    values='Inspections réalisées',
                    title="Répartition des inspections par inspecteur",
                    hole=0.3
                )
                
                fig2.update_layout(
                    height=350,
                    legend_title="Inspecteur"
                )
                
                st.plotly_chart(fig2, use_container_width=True)
                
                # Tableau détaillé
                with st.expander("Voir les données détaillées"):
                    st.dataframe(
                        insp_df.sort_values('Taux de conformité (%)', ascending=False),
                        use_container_width=True,
                        column_config={
                            'Taux de conformité (%)': st.column_config.ProgressColumn(
                                'Taux de conformité (%)',
                                format="%.1f%%",
                                min_value=0,
                                max_value=100
                            )
                        }
                    )
                
                # Analyse des catégories de non-conformités par inspecteur
                st.markdown("#### Comparaison des performances par catégorie")
                
                # Créer un DataFrame pour les catégories par inspecteur
                cat_data = []
                for inspector, data in inspectors_data.items():
                    for category, cat_data in data['categories'].items():
                        if cat_data['checked'] > 0:
                            cat_conformity = (cat_data['conform'] / cat_data['checked']) * 100
                            cat_data.append({
                                'Inspecteur': inspector,
                                'Catégorie': category,
                                'Taux de conformité (%)': cat_conformity,
                                'Points vérifiés': cat_data['checked']
                            })
                
                if cat_data:
                    cat_df = pd.DataFrame(cat_data)
                    
                    fig3 = px.scatter(
                        cat_df,
                        x='Catégorie',
                        y='Taux de conformité (%)',
                        color='Inspecteur',
                        size='Points vérifiés',
                        hover_name='Inspecteur',
                        title="Performance par catégorie et inspecteur"
                    )
                    
                    fig3.update_layout(
                        height=450,
                        xaxis_title="Catégorie",
                        yaxis_title="Taux de conformité (%)",
                        xaxis={'categoryorder': 'total ascending'}
                    )
                    
                    st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("Pas assez de données pour analyser les performances par inspecteur. Chargez plus d'inspections.")
                
        elif report_type == "Efficacité des actions correctives":
            st.markdown("#### Analyse de l'efficacité des actions correctives")
            
            # Collecter les données sur les actions correctives
            action_data = []
            
            for (inspection_id, point_id), action_info in st.session_state.corrective_actions.items():
                # Trouver l'inspection correspondante
                inspection_data = next((data for data in st.session_state.loaded_inspections if data['inspection']['id'] == inspection_id), None)
                if not inspection_data:
                    continue
                
                inspection = inspection_data['inspection']
                model = inspection_data['model']
                
                # Trouver le point et le résultat correspondants
                point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
                if not point_model:
                    continue
                    
                result_data = next((r for r in inspection.get('results', []) if r.get('idPoint') == point_id), None)
                if not result_data:
                    continue
                
                # Collecter les informations
                action_data.append({
                    'Inspection ID': inspection_id,
                    'Point ID': point_id,
                    'Point de contrôle': point_model.get('PointDeControle', f'Point {point_id}'),
                    'Catégorie': point_model.get('Categorie', 'Sans catégorie'),
                    'Statut': action_info.get('status', 'À traiter'),
                    'Note': action_info.get('note', ''),
                    'Date inspection': pd.to_datetime(inspection.get('startDate')).date() if inspection.get('startDate') else None,
                    'Inspecteur': inspection.get('inspectorName', 'Inconnu')
                })
            
            # Créer un DataFrame
            actions_df = pd.DataFrame(action_data)
            
            if not actions_df.empty:
                # Répartition des statuts
                status_counts = actions_df['Statut'].value_counts().reset_index()
                status_counts.columns = ['Statut', 'Nombre']
                
                fig = px.pie(
                    status_counts,
                    names='Statut',
                    values='Nombre',
                    color='Statut',
                    color_discrete_map={
                        'À traiter': '#FEF3C7',
                        'En cours': '#DBEAFE',
                        'Terminé': '#D1FAE5',
                        'Annulé': '#FEE2E2'
                    },
                    title="Répartition des statuts d'actions correctives"
                )
                
                fig.update_layout(
                    height=350,
                    legend_title="Statut"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Répartition par catégorie
                category_status = pd.crosstab(actions_df['Catégorie'], actions_df['Statut'])
                
                if not category_status.empty:
                    fig2 = px.bar(
                        category_status,
                        barmode='stack',
                        title="Actions correctives par catégorie et statut"
                    )
                    
                    fig2.update_layout(
                        height=400,
                        xaxis_title="Catégorie",
                        yaxis_title="Nombre d'actions",
                        legend_title="Statut"
                    )
                    
                    st.plotly_chart(fig2, use_container_width=True)
                
                # KPIs de suivi
                kpi_cols = st.columns(3)
                with kpi_cols[0]:
                    total_actions = len(actions_df)
                    completed_actions = len(actions_df[actions_df['Statut'].isin(['Terminé', 'Annulé'])])
                    completion_rate = (completed_actions / total_actions * 100) if total_actions > 0 else 0
                    
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color:#059669;">{completion_rate:.1f}%</div>
                        <div class="metric-label">Taux de résolution</div>
                        <div style="font-size:0.8rem; color:#6B7280;">{completed_actions}/{total_actions} actions résolues</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with kpi_cols[1]:
                    in_progress = len(actions_df[actions_df['Statut'] == 'En cours'])
                    
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color:#3B82F6;">{in_progress}</div>
                        <div class="metric-label">Actions en cours</div>
                        <div style="font-size:0.8rem; color:#6B7280;">En attente de finalisation</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with kpi_cols[2]:
                    pending = len(actions_df[actions_df['Statut'] == 'À traiter'])
                    
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color:#F59E0B;">{pending}</div>
                        <div class="metric-label">Actions à traiter</div>
                        <div style="font-size:0.8rem; color:#6B7280;">Nécessitent une attention</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Liste détaillée des actions à traiter
                if pending > 0:
                    st.markdown("#### Actions correctives à traiter en priorité")
                    pending_df = actions_df[actions_df['Statut'] == 'À traiter'].sort_values('Date inspection')
                    
                    for _, row in pending_df.iterrows():
                        st.markdown(f"""
                        <div style="background-color:white; padding:1rem; border-radius:0.5rem; margin-bottom:0.75rem; border-left:4px solid #F59E0B;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <h4 style="margin:0; color:#92400E;">{row['Point de contrôle']}</h4>
                                <span style="font-size:0.8rem; color:#6B7280;">{format_date(row['Date inspection'], include_time=False)}</span>
                            </div>
                            <p style="margin:0.25rem 0;"><strong>Catégorie:</strong> {row['Catégorie']} | <strong>Inspecteur:</strong> {row['Inspecteur']}</p>
                            <div style="font-size:0.9rem; color:#4B5563; background-color:#F9FAFB; padding:0.5rem; border-radius:0.25rem; margin-top:0.5rem;">
                                {row['Note'] or "Aucune note disponible."}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("Aucune action corrective n'a été définie. Utilisez l'onglet Vue Agrégée pour définir des actions sur les non-conformités.")

# --- Affichage de la Modale de Détail (déclenché depuis l'onglet Liste) ---
if st.session_state.show_detail_dialog and st.session_state.selected_inspection_id_for_detail:
    # Trouver l'inspection correspondante dans l'état
    inspection_to_show = next((insp for insp in st.session_state.loaded_inspections if insp['inspection']['id'] == st.session_state.selected_inspection_id_for_detail), None)

    if inspection_to_show:
        # Utiliser st.dialog pour une expérience modale
        # Le décorateur @st.dialog gère l'ouverture/fermeture via une fonction
        # Correction de la callback dismissed
        @st.dialog("Détails de l'Inspection", dismissed=lambda: setattr(st.session_state, 'show_detail_dialog', False))
        def show_detail_modal():
            render_inspection_detail(inspection_to_show) # Appeler la fonction de rendu
            if st.button("Fermer", key="close_detail_dialog_button"):
                 # Utiliser setattr pour modifier l'état dans le callback du bouton aussi
                 setattr(st.session_state, 'show_detail_dialog', False)
                 st.rerun() # Forcer le rerun pour fermer la modale

        # Appeler la fonction décorée pour effectivement afficher la modale
        show_detail_modal()
    else:
        # Gérer le cas où l'ID sélectionné n'est plus valide
        st.session_state.selected_inspection_id_for_detail = None
        st.session_state.show_detail_dialog = False
        st.warning("L'inspection sélectionnée pour le détail n'est plus disponible.")
        st.rerun()

# --- Affichage de la Modale Photo (déclenché depuis la vue détail) ---
if st.session_state.show_photo_modal and st.session_state.modal_photo_list:
    # Correction de la callback dismissed
    @st.dialog("Visualiseur de Photos", dismissed=lambda: setattr(st.session_state, 'show_photo_modal', False))
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


# --- Pied de page amélioré ---
st.markdown("""
<div class="footer">
    <p>Application Analyseur d'Inspections Qualité v2.0</p>
    <p>Développée pour le suivi et l'analyse des audits de sécurité alimentaire en Europe</p>
</div>
""", unsafe_allow_html=True)
> {row['Catégorie']}</p>
                            <p><strong>Critère d'acceptation:</strong> {row['Critère Accept.']}</p>
                            <p><strong>Résultat:</strong> <span style="color:red;">{row['Résultat Obtenu']}</span></p>
                            <p><strong>Commentaire:</strong> {row['Commentaire'] or "Aucun commentaire"}</p>
                            <p><strong>Note d'action:</strong> {row['Note Action'] or "Aucune note"}</p>
                            """, unsafe_allow_html=True)
                            
                            # Bouton pour voir les photos
                            if has_photos:
                                st.button("Voir photos", key=f"compact_photos_{i}", on_click=lambda: st.write("Photos affichées"))
            
            # Mettre à jour les actions correctives si le mode tableau a été modifié
            if selected_view == "Mode tableau":
                update_corrective_actions_from_df(edited_df_slice)
            
            # --- Pagination élégante ---
            if total_pages > 1:
                st.markdown("""
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:1rem;">
                """, unsafe_allow_html=True)
                
                pagination_cols = st.columns([1, 3, 1])
                
                with pagination_cols[0]:
                    if st.button("⬅️ Précédent", disabled=(current_page <= 1), key="agg_prev_page", use_container_width=True):
                        st.session_state.aggregated_page_number -= 1
                        st.rerun()
                
                with pagination_cols[1]:
                    # Créer une pagination numérotée
                    pages_to_show = min(5, total_pages)
                    page_start = max(1, current_page - pages_to_show // 2)
                    page_end = min(total_pages, page_start + pages_to_show - 1)
                    
                    page_cols = st.columns(pages_to_show + 2)
                    
                    # Bouton pour page 1 si on est loin du début
                    if page_start > 1:
                        with page_cols[0]:
                            if st.button("1", key="page_first"):
                                st.session_state.aggregated_page_number = 1
                                st.rerun()
                        with page_cols[1]:
                            st.markdown("...")
                        col_offset = 2
                    else:
                        col_offset = 0
                    
                    # Pages numérotées intermédiaires
                    for i, page_num in enumerate(range(page_start, page_end + 1)):
                        with page_cols[i + col_offset]:
                            button_type = "primary" if page_num == current_page else "secondary"
                            if st.button(f"{page_num}", key=f"page_{page_num}", type=button_type):
                                st.session_state.aggregated_page_number = page_num
                                st.rerun()
                    
                    # Bouton pour dernière page si on est loin de la fin
                    if page_end < total_pages:
                        with page_cols[pages_to_show + col_offset]:
                            st.markdown("...")
                        with page_cols[pages_to_show + col_offset + 1]:
                            if st.button(f"{total_pages}", key="page_last"):
                                st.session_state.aggregated_page_number = total_pages
                                st.rerun()
                
                with pagination_cols[2]:
                    if st.button("Suivant ➡️", disabled=(current_page >= total_pages), key="agg_next_page", use_container_width=True):
                        st.session_state.aggregated_page_number += 1
                        st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
                
            # Afficher un résumé de la pagination
            st.caption(f"Affichage des résultats {start_idx + 1} à {end_idx} sur {total_items} au total")
    
    # --- Onglet Rapports ---
    with tab_reports:
        st.subheader("📊 Rapports et Analyses")
        
        # Sélection du type de rapport
        report_type = st.selectbox(
            "Type de rapport",
            options=[
                "Taux de conformité par modèle",
                "Évolution des non-conformités",
                "Performance par inspecteur",
                "Non-conformités récurrentes",
                "Efficacité des actions correctives"
            ],
            index=0
        )
        
        # Construction du rapport sélectionné
        if report_type == "Taux de conformité par modèle":
            # Regrouper les données par modèle d'inspection
            model_metrics = {}
            for data in st.session_state.loaded_inspections:
                model_name = data['model'].get('name', 'Sans nom')
                if model_name not in model_metrics:
                    model_metrics[model_name] = {
                        'total_points': 0,
                        'points_checked': 0,
                        'points_conform': 0,
                        'nc_count': 0
                    }
                
                # Parcourir les résultats pour ce modèle
                inspection = data['inspection']
                model = data['model']
                
                for result in inspection.get('results', []):
                    point_id = result.get('idPoint')
                    if not point_id: continue
                    
                    point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
                    if not point_model: continue
                    
                    model_metrics[model_name]['total_points'] += 1
                    
                    if not result.get('isNA', False):
                        model_metrics[model_name]['points_checked'] += 1
                        
                        # Vérifier si conforme
                        if not is_point_of_interest(result, point_model):
                            model_metrics[model_name]['points_conform'] += 1
                        else:
                            model_metrics[model_name]['nc_count'] += 1
            
            # Créer un DataFrame pour le graphique
            model_df_data = []
            for model_name, metrics in model_metrics.items():
                if metrics['points_checked'] > 0:
                    conformity_rate = (metrics['points_conform'] / metrics['points_checked']) * 100
                    model_df_data.append({
                        'Modèle': model_name,
                        'Taux de conformité (%)': conformity_rate,
                        'Points vérifiés': metrics['points_checked'],
                        'Non-conformités': metrics['nc_count']
                    })
            
            model_df = pd.DataFrame(model_df_data)
            
            # Afficher le rapport
            if not model_df.empty:
                # KPIs en haut
                kpis = st.columns(3)
                with kpis[0]:
                    best_model = model_df.loc[model_df['Taux de conformité (%)'].idxmax()] if len(model_df) > 0 else None
                    if best_model is not None:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div style="font-size:1.1rem; font-weight:500; color:#065F46;">Meilleure performance</div>
                            <div class="metric-value" style="color:#059669;">{best_model['Taux de conformité (%)']:.1f}%</div>
                            <div class="metric-label">{best_model['Modèle']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                
                with kpis[1]:
                    worst_model = model_df.loc[model_df['Taux de conformité (%)'].idxmin()] if len(model_df) > 0 else None
                    if worst_model is not None:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div style="font-size:1.1rem; font-weight:500; color:#991B1B;">Point d'attention</div>
                            <div class="metric-value" style="color:#DC2626;">{worst_model['Taux de conformité (%)']:.1f}%</div>
                            <div class="metric-label">{worst_model['Modèle']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                
                with kpis[2]:
                    avg_rate = model_df['Taux de conformité (%)'].mean()
                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="font-size:1.1rem; font-weight:500; color:#1E40AF;">Taux moyen</div>
                        <div class="metric-value">{avg_rate:.1f}%</div>
                        <div class="metric-label">Conformité globale</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Graphique principal
                st.markdown("#### Taux de conformité par modèle d'inspection")
                
                fig = px.bar(
                    model_df.sort_values('Taux de conformité (%)'),
                    x='Taux de conformité (%)',
                    y='Modèle',
                    orientation='h',
                    text='Taux de conformité (%)',
                    color='Taux de conformité (%)',
                    color_continuous_scale=px.colors.sequential.Greens,
                    hover_data=['Points vérifiés', 'Non-conformités']
                )
                
                fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig.update_layout(
                    height=400,
                    margin=dict(l=0, r=0, t=20, b=0),
                    coloraxis_showscale=False,
                    xaxis_title="Taux de conformité (%)",
                    yaxis_title=None
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Tableau détaillé
                with st.expander("Voir les données détaillées"):
                    st.dataframe(
                        model_df.sort_values('Taux de conformité (%)', ascending=False),
                        use_container_width=True,
                        column_config={
                            'Taux de conformité (%)': st.column_config.ProgressColumn(
                                'Taux de conformité (%)',
                                format="%.1f%%",
                                min_value=0,
                                max_value=100
                            )
                        }
                    )
            else:
                st.info("Pas assez de données pour générer ce rapport. Chargez plus d'inspections.")
        
        elif report_type == "Évolution des non-conformités":
            st.markdown("#### Évolution des non-conformités dans le temps")
            
            # Créer une série temporelle des non-conformités
            time_data = []
            
            # Parcourir toutes les inspections pour extraire les dates et non-conformités
            for data in st.session_state.loaded_inspections:
                inspection = data['inspection']
                model = data['model']
                date = pd.to_datetime(inspection.get('startDate')).date() if inspection.get('startDate') else None
                
                if date:
                    nc_count = 0
                    for result in inspection.get('results', []):
                        point_id = result.get('idPoint')
                        if not point_id: continue
                        
                        point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
                        if is_point_of_interest(result, point_model):
                            nc_count += 1
                    
                    time_data.append({
                        'Date': date,
                        'Non-conformités': nc_count,
                        'Modèle': model.get('name', 'Sans nom')
                    })
            
            # Créer le DataFrame pour le graphique
            if time_data:
                time_df = pd.DataFrame(time_data)
                time_df = time_df.sort_values('Date')
                
                # Graphique d'évolution
                fig = px.line(
                    time_df,
                    x='Date',
                    y='Non-conformités',
                    color='Modèle',
                    markers=True,
                    title="Évolution des non-conformités par inspection"
                )
                
                fig.update_layout(
                    height=400,
                    xaxis_title="Date d'inspection",
                    yaxis_title="Nombre de non-conformités",
                    legend_title="Modèle d'inspection"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Calculer la tendance
                if len(time_df) > 1:
                    # Regrouper par date
                    time_df_grouped = time_df.groupby('Date')['Non-conformités'].sum().reset_index()
                    time_df_grouped = time_df_grouped.sort_values('Date')
                    
                    # Calculer la moyenne mobile sur 3 points
                    if len(time_df_grouped) >= 3:
                        time_df_grouped['Moyenne mobile'] = time_df_grouped['Non-conformités'].rolling(window=3, min_periods=1).mean()
                        
                        # Créer un graphique de tendance
                        fig2 = px.line(
                            time_df_grouped,
                            x='Date',
                            y=['Non-conformités', 'Moyenne mobile'],
                            title="Tendance des non-conformités (moyenne mobile sur 3 inspections)"
                        )
                        
                        fig2.update_layout(
                            height=350,
                            xaxis_title="Date d'inspection",
                            yaxis_title="Nombre de non-conformités",
                            legend_title="Mesure"
                        )
                        
                        st.plotly_chart(fig2, use_container_width=True)
                        
                        # Calculer la direction de la tendance
                        first_avg = time_df_grouped['Moyenne mobile'].iloc[0]
                        last_avg = time_df_grouped['Moyenne mobile'].iloc[-1]
                        
                        if last_avg < first_avg:
                            trend_icon = "✅"
                            trend_color = "#059669"
                            trend_text = "en baisse"
                        elif last_avg > first_avg:
                            trend_icon = "⚠️"
                            trend_color = "#DC2626"
                            trend_text = "en hausse"
                        else:
                            trend_icon = "ℹ️"
                            trend_color = "#4B5563"
                            trend_text = "stable"
                        
                        st.markdown(f"""
                        <div style="background-color:#F9FAFB; padding:1rem; border-radius:0.5rem; text-align:center; margin:1rem 0;">
                            <p style="font-size:1.1rem; margin:0;">
                                {trend_icon} Tendance des non-conformités : <span style="color:{trend_color}; font-weight:500;">{trend_text}</span>
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("Pas assez de données temporelles pour générer ce rapport. Chargez plus d'inspections.")
                
        elif report_type == "Non-conformités récurrentes":
            st.markdown("#### Analyse des non-conformités récurrentes")
            
            # Collecter les points de contrôle non conformes
            nc_points = {}
            
            for data in st.session_state.loaded_inspections:
                inspection = data['inspection']
                model = data['model']
                
                for result in inspection.get('results', []):
                    point_id = result.get('idPoint')
                    if not point_id: continue
                    
                    point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
                    if not point_model: continue
                    
                    if is_point_of_interest(result, point_model):
                        point_name = point_model.get('PointDeControle', f'Point {point_id}')
                        category = point_model.get('Categorie', 'Sans catégorie')
                        
                        key = (point_name, category)
                        if key not in nc_points:
                            nc_points[key] = {
                                'count': 0,
                                'inspections': set(),
                                'critere': point_model.get('CritereAcceptation', 'N/A')
                            }
                        
                        nc_points[key]['count'] += 1
                        nc_points[key]['inspections'].add(inspection['id'])
            
            # Créer un DataFrame pour le graphique
            nc_data = []
            for (point_name, category), data in nc_points.items():
                nc_data.append({
                    'Point de contrôle': point_name,
                    'Catégorie': category,
                    'Occurrences': data['count'],
                    'Inspections': len(data['inspections']),
                    'Critère': data['critere']
                })
            
            nc_df = pd.DataFrame(nc_data)
            
            if not nc_df.empty:
                # Trier et prendre les top 10
                top_nc = nc_df.sort_values('Occurrences', ascending=False).head(10)
                
                # Graphique horizontal des top non-conformités
                fig = px.bar(
                    top_nc,
                    y='Point de contrôle',
                    x='Occurrences',
                    color='Catégorie',
                    orientation='h',
                    hover_data=['Inspections', 'Critère'],
                    title="Top 10 des points de contrôle non conformes"
                )
                
                fig.update_layout(
                    height=500,
                    xaxis_title="Nombre d'occurrences",
                    yaxis_title=None,
                    yaxis={'categoryorder': 'total ascending'}
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Tableau détaillé pour tous les points
                with st.expander("Voir toutes les non-conformités"):
                    st.dataframe(
                        nc_df.sort_values('Occurrences', ascending=False),
                        use_container_width=True
                    )
                
                # Plan d'action suggéré pour les 3 principaux points
                st.markdown("#### Plan d'action suggéré")
                st.markdown("Voici les points qui nécessitent une attention particulière :")
                
                for i, (_, row) in enumerate(top_nc.head(3).iterrows()):
                    st.markdown(f"""
                    <div style="background-color:white; padding:1rem; border-radius:0.5rem; margin-bottom:1rem; border-left:4px solid #DC2626;">
                        <h4 style="margin-top:0;">{i+1}. {row['Point de contrôle']}</h4>
                        <p><strong>Catégorie:</strongimport streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import zipfile
import io
import json
import base64
import sqlite3
import os
from PIL import Image
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Union
import numpy as np

# --- Configuration de la Page Streamlit ---
st.set_page_config(
    page_title="Analyseur d'Inspections Qualité",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS personnalisé pour améliorer l'apparence ---
st.markdown("""
<style>
    /* Styles généraux */
    .main .block-container {padding-top: 1rem;}
    h1, h2, h3 {color: #1E3A8A;}
    
    /* Amélioration des cartes pour les KPIs */
    .metric-card {
        background-color: white;
        border-radius: 0.5rem;
        padding: 1rem;
        box-shadow: 0 0.15rem 0.3rem rgba(0,0,0,0.1);
        text-align: center;
        height: 100%;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1E3A8A;
    }
    .metric-label {
        color: #6B7280;
        font-size: 0.875rem;
    }
    .metric-trend-positive {color: #059669;}
    .metric-trend-negative {color: #DC2626;}
    
    /* Amélioration des expanders */
    .streamlit-expanderHeader {
        background-color: #F3F4F6;
        border-radius: 0.5rem;
    }
    
    /* Style pour les tabs */
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 1rem;
    }
    
    /* Style pour le data editor */
    [data-testid="stDataFrame"] {
        width: 100%;
    }
    
    /* Amélioration de l'apparence des filtres */
    .filter-container {
        background-color: #F9FAFB;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    
    /* Badge pour les statuts */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .status-à-traiter {
        background-color: #FEF3C7;
        color: #92400E;
    }
    .status-en-cours {
        background-color: #DBEAFE; 
        color: #1E40AF;
    }
    .status-terminé {
        background-color: #D1FAE5;
        color: #065F46;
    }
    .status-annulé {
        background-color: #FEE2E2;
        color: #991B1B;
    }
    
    /* Style pour le pied de page */
    .footer {
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #E5E7EB;
        color: #6B7280;
        font-size: 0.75rem;
        text-align: center;
    }
    
    /* Animation du spinner */
    @keyframes fadeIn {
        0% {opacity: 0;}
        100% {opacity: 1;}
    }
    .fade-in {
        animation: fadeIn 0.5s ease-in-out;
    }
</style>
""", unsafe_allow_html=True)

# --- Constantes ---
ITEMS_PER_PAGE_AGGREGATED = 50  # Nombre d'éléments par page dans la vue agrégée
DEFAULT_DB_PATH = "inspections_data.db"  # Chemin par défaut pour la base SQLite
CONFORME_COLOR = "#059669"  # Vert
NON_CONFORME_COLOR = "#DC2626"  # Rouge
NEUTRAL_COLOR = "#6B7280"  # Gris

# --- Initialisation du système de persistance ---
def init_database(db_path=DEFAULT_DB_PATH):
    """
    Initialise ou connecte à la base de données SQLite pour la persistance
    entre les sessions.
    
    Args:
        db_path: Chemin vers le fichier de base de données SQLite.
        
    Returns:
        Connection: Objet de connexion à la base de données.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Créer la table pour les inspections si elle n'existe pas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inspections (
        id TEXT PRIMARY KEY,
        model_id TEXT NOT NULL,
        model_name TEXT NOT NULL,
        inspector_name TEXT,
        start_date TEXT,
        end_date TEXT,
        status TEXT,
        filename TEXT,
        data JSON NOT NULL,
        imported_date TEXT NOT NULL
    )
    ''')
    
    # Créer la table pour les actions correctives
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS corrective_actions (
        inspection_id TEXT NOT NULL,
        point_id TEXT NOT NULL,
        status TEXT NOT NULL,
        note TEXT,
        last_updated TEXT NOT NULL,
        PRIMARY KEY (inspection_id, point_id)
    )
    ''')
    
    conn.commit()
    return conn

# Initialiser la base de données au démarrage
@st.cache_resource
def get_db_connection():
    return init_database()

# --- Initialisation de l'État de Session ---
default_session_state = {
    'loaded_inspections': [],  # Liste pour stocker { "inspection": Dict, "model": Dict, "filename": str }
    'corrective_actions': {},  # Dict: clé = Tuple(inspection_id, point_id), valeur = {'status': str, 'note': str}
    'selected_inspection_id_for_detail': None,  # str | None
    'show_detail_dialog': False,  # bool
    'export_data_prepared': None,  # bytes | None
    'export_filename': "",  # str
    'show_photo_modal': False,  # bool
    'modal_photo_list': [],  # List[str] (base64 strings)
    'modal_photo_index': 0,  # int
    'modal_photo_caption': "",  # str
    'aggregated_page_number': 1,  # int
    'last_refresh_time': datetime.now(),  # Pour afficher quand les données ont été chargées
    'show_welcome': True,  # Pour afficher le tutoriel au premier lancement
    'persistent_mode': False,  # Mode persistent ou volatil
}

for key, default_value in default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- Fonctions de Gestion de Persistance ---
def load_from_database():
    """Charge les inspections et actions correctives depuis la base de données"""
    if not st.session_state.persistent_mode:
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Charger les inspections
    cursor.execute('SELECT id, model_id, model_name, inspector_name, filename, data FROM inspections')
    inspections_rows = cursor.fetchall()
    
    # Reconstruire la liste d'inspections
    inspections_list = []
    for row in inspections_rows:
        inspection_id, model_id, model_name, inspector_name, filename, data_json = row
        try:
            data = json.loads(data_json)
            inspections_list.append({
                "inspection": data.get("inspection", {}),
                "model": data.get("model", {}),
                "filename": filename
            })
        except json.JSONDecodeError:
            st.error(f"Erreur de décodage des données pour l'inspection {inspection_id}")
    
    # Charger les actions correctives
    cursor.execute('SELECT inspection_id, point_id, status, note FROM corrective_actions')
    actions_rows = cursor.fetchall()
    
    # Reconstruire le dictionnaire d'actions
    actions_dict = {}
    for row in actions_rows:
        inspection_id, point_id, status, note = row
        actions_dict[(inspection_id, point_id)] = {'status': status, 'note': note or ''}
    
    # Mettre à jour l'état de session
    st.session_state.loaded_inspections = inspections_list
    st.session_state.corrective_actions = actions_dict
    st.session_state.last_refresh_time = datetime.now()

def save_inspection_to_database(inspection_data):
    """Sauvegarde une inspection dans la base de données"""
    if not st.session_state.persistent_mode:
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inspection = inspection_data.get("inspection", {})
    model = inspection_data.get("model", {})
    filename = inspection_data.get("filename", "")
    
    inspection_id = inspection.get("id", "")
    if not inspection_id:
        return False
    
    try:
        # Sérialiser l'objet complet
        data_json = json.dumps({"inspection": inspection, "model": model})
        
        # Insérer ou mettre à jour l'inspection
        cursor.execute('''
        INSERT OR REPLACE INTO inspections 
        (id, model_id, model_name, inspector_name, start_date, end_date, status, filename, data, imported_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            inspection_id,
            inspection.get("modelId", ""),
            model.get("name", ""),
            inspection.get("inspectorName", ""),
            inspection.get("startDate", ""),
            inspection.get("endDate", ""),
            inspection.get("status", ""),
            filename,
            data_json,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde en base de données: {e}")
        return False

def save_corrective_action(inspection_id, point_id, status, note):
    """Sauvegarde une action corrective dans la base de données"""
    if not st.session_state.persistent_mode:
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT OR REPLACE INTO corrective_actions
        (inspection_id, point_id, status, note, last_updated)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            inspection_id,
            point_id,
            status,
            note,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde de l'action corrective: {e}")
        return False

def delete_inspection_from_database(inspection_id):
    """Supprime une inspection et ses actions correctives de la base de données"""
    if not st.session_state.persistent_mode:
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Supprimer l'inspection
        cursor.execute('DELETE FROM inspections WHERE id = ?', (inspection_id,))
        
        # Supprimer les actions correctives associées
        cursor.execute('DELETE FROM corrective_actions WHERE inspection_id = ?', (inspection_id,))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur lors de la suppression en base de données: {e}")
        return False

def clear_all_data_from_database():
    """Vide toutes les données de la base de données"""
    if not st.session_state.persistent_mode:
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM inspections')
        cursor.execute('DELETE FROM corrective_actions')
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur lors de la suppression de toutes les données: {e}")
        return False

# --- Fonctions Utilitaires ---
def is_point_of_interest(result_data: Optional[Dict], point_model: Optional[Dict]) -> bool:
    """
    Vérifie si un point de contrôle est considéré comme 'd'intérêt'
    (Non Conforme ou Hors Plage Numérique).

    Args:
        result_data: Dictionnaire contenant les résultats du point ('result', 'isNA', etc.).
        point_model: Dictionnaire contenant la définition du point depuis le modèle.

    Returns:
        True si le point est d'intérêt, False sinon.
    """
    if not result_data or not point_model:
        return False
    if result_data.get('isNA', False):  # Ignorer si Non Applicable
        return False

    result_value = result_data.get('result')
    if result_value == 'Non Conforme':
        return True

    # Vérification Plage Numérique
    if point_model.get('TypeParametre') == 'Plage_Numerique' and result_value is not None:
        try:
            # Gestion robuste de la conversion en float (virgule ou point)
            if isinstance(result_value, str):
                value = float(result_value.replace(',', '.'))
            else:
                value = float(result_value)
                
            options_str = point_model.get('OptionsParametre', '')
            if options_str:
                options = options_str.split(';')
                if len(options) == 2:
                    min_val, max_val = map(float, options)
                    if value < min_val or value > max_val:
                        return True
        except (ValueError, TypeError):
            # Ignorer si la conversion échoue
            pass

    # Optionnel: Inclure les points avec commentaires (décommenter si besoin)
    # if result_data.get('comment', '').strip():
    #     return True

    return False

def format_date(date_str, include_time=True):
    """
    Formate une chaîne de date ISO en format lisible.
    
    Args:
        date_str: Chaîne de date au format ISO.
        include_time: Si True, inclut l'heure dans le résultat.
        
    Returns:
        Une chaîne formatée, ou 'N/A' si la date est invalide.
    """
    if not date_str:
        return "N/A"
    
    try:
        dt = pd.to_datetime(date_str)
        if include_time:
            return dt.strftime('%d/%m/%Y %H:%M')
        else:
            return dt.strftime('%d/%m/%Y')
    except:
        return "N/A"

def status_to_badge(status):
    """
    Convertit un statut en HTML pour afficher un badge coloré.
    
    Args:
        status: Le statut à convertir.
        
    Returns:
        HTML pour un badge coloré.
    """
    # Normaliser le statut (minuscules, sans accents)
    normalized_status = status.lower()
    
    if 'traiter' in normalized_status:
        class_name = "status-à-traiter"
    elif 'cours' in normalized_status:
        class_name = "status-en-cours"
    elif 'termin' in normalized_status:
        class_name = "status-terminé"
    elif 'annul' in normalized_status:
        class_name = "status-annulé"
    else:
        class_name = ""
        
    return f'<span class="status-badge {class_name}">{status}</span>'

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
                inspection_data = {
                    "inspection": package_data['inspection'],
                    "model": package_data['model'],
                    "filename": filename
                }
                st.session_state.loaded_inspections.append(inspection_data)
                
                # Sauvegarder en base de données si mode persistant
                if st.session_state.persistent_mode:
                    save_inspection_to_database(inspection_data)
                
                # Ajouter l'ID à l'ensemble pour vérifier les doublons dans ce même lot de chargement
                current_inspection_ids.add(inspection_id)
                newly_loaded_count += 1

                # Initialiser les actions correctives pour les points d'intérêt de cette nouvelle inspection
                for result in package_data['inspection'].get('results', []):
                    point_id = result.get('idPoint')
                    if not point_id: continue  # S'assurer qu'on a un ID de point

                    point_model = next((item for item in package_data['model'].get('items', []) if item.get('ID_Point') == point_id), None)
                    if is_point_of_interest(result, point_model):
                        action_key = (inspection_id, point_id)
                        # Initialiser seulement si pas déjà présent
                        if action_key not in st.session_state.corrective_actions:
                            action_data = {'status': 'À traiter', 'note': ''}
                            st.session_state.corrective_actions[action_key] = action_data
                            # Sauvegarder en base de données si mode persistant
                            if st.session_state.persistent_mode:
                                save_corrective_action(inspection_id, point_id, action_data['status'], action_data['note'])

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
        
    # Mettre à jour l'horodatage
    st.session_state.last_refresh_time = datetime.now()

def prepare_aggregated_dataframe() -> pd.DataFrame:
    """
    Crée un DataFrame Pandas contenant tous les points d'intérêt des inspections chargées,
    enrichi avec les informations des actions correctives stockées en session.

    Returns:
        Un DataFrame Pandas avec les données agrégées. Retourne un DataFrame vide
        si aucune inspection n'est chargée ou aucun point d'intérêt trouvé.
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
                         value_f = float(str(result_value).replace(',','.'))
                         options_str = point_model.get('OptionsParametre', '')
                         if options_str:
                             options = options_str.split(';')
                             if len(options) == 2:
                                min_val, max_val = map(float, options)
                                if value_f < min_val or value_f > max_val:
                                    result_display += f" [Hors Plage: {min_val}-{max_val}]"
                     except (ValueError, TypeError): 
                         pass # Ignorer erreurs de conversion/format

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
    if 'Date Insp.' in df.columns and not df['Date Insp.'].empty:
        df['Date Insp.'] = pd.to_datetime(df['Date Insp.'])
    return df

def update_corrective_actions_from_df(edited_df: pd.DataFrame) -> None:
    """
    Met à jour le dictionnaire st.session_state.corrective_actions en se basant
    sur les modifications effectuées dans le DataFrame retourné par st.data_editor.

    Args:
        edited_df: Le DataFrame tel que retourné par st.data_editor.
    """
    updates_made = 0
    required_cols = ['inspection_id_hidden', 'point_id_hidden', 'Statut Action', 'Note Action']
    if not all(col in edited_df.columns for col in required_cols):
        st.error("Erreur interne: Colonnes manquantes dans le DataFrame édité pour la mise à jour des actions.")
        return

    for index, row in edited_df.iterrows():
        inspection_id = row['inspection_id_hidden']
        point_id = row['point_id_hidden']
        action_key = (inspection_id, point_id)

        # Récupérer les valeurs éditées (ou actuelles si non éditées)
        current_status = row['Statut Action']
        current_note = row['Note Action'] if pd.notna(row['Note Action']) else ""

        # Récupérer l'état précédent ou initialiser si absent
        previous_action = st.session_state.corrective_actions.get(action_key, {'status': 'À traiter', 'note': ''})

        # Comparer et mettre à jour si nécessaire
        if previous_action['status'] != current_status or previous_action['note'] != current_note:
            st.session_state.corrective_actions[action_key] = {'status': current_status, 'note': current_note}
            # Sauvegarder en base de données si mode persistant
            if st.session_state.persistent_mode:
                save_corrective_action(inspection_id, point_id, current_status, current_note)
            updates_made += 1

    if updates_made > 0:
        st.toast(f"{updates_made} mise(s) à jour des actions correctives enregistrée(s).", icon="📝")

def render_inspection_detail(inspection_data: Dict) -> None:
    """
    Affiche les détails formatés d'une inspection (métadonnées, points par catégorie, photos).

    Args:
        inspection_data: Dictionnaire contenant les clés 'inspection', 'model', 'filename'.
    """
    inspection = inspection_data['inspection']
    model = inspection_data['model']
    filename = inspection_data['filename']

    # Style plus élégant pour l'entête
    st.markdown(f"""
    <div style="background-color:#F3F4F6; padding:1rem; border-radius:0.5rem; margin-bottom:1rem;">
        <h3 style="margin:0;">{model.get('name', 'N/A')}</h3>
        <p style="color:#6B7280; margin:0.5rem 0 0 0;">Fichier: {filename} | ID: {inspection.get('id', 'N/A')}</p>
    </div>
    """, unsafe_allow_html=True)

    # Affichage des Métadonnées
    meta_cols = st.columns(2)
    with meta_cols[0]:
        st.markdown(f"""
        <div class="metric-card" style="height:auto; padding:0.5rem;">
            <p><strong>Inspecteur:</strong> {inspection.get('inspectorName', 'N/A')}</p>
            <p><strong>Date Début:</strong> {format_date(inspection.get('startDate'))}</p>
        </div>
        """, unsafe_allow_html=True)
    with meta_cols[1]:
        st.markdown(f"""
        <div class="metric-card" style="height:auto; padding:0.5rem;">
            <p><strong>Statut:</strong> {inspection.get('status', 'N/A')}</p>
            <p><strong>Date Fin:</strong> {format_date(inspection.get('endDate'))}</p>
        </div>
        """, unsafe_allow_html=True)

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

    # Calcul des statistiques pour cette inspection
    total_points = len(model.get('items', []))
    points_na = 0
    points_conform = 0
    points_non_conform = 0
    points_out_of_range = 0
    
    # Compter les différents types de résultats
    for result in inspection.get('results', []):
        point_id = result.get('idPoint')
        if not point_id: continue

        point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
        if not point_model: continue

        if result.get('isNA', False):
            points_na += 1
        elif result.get('result') == 'Conforme':
            points_conform += 1
        elif result.get('result') == 'Non Conforme':
            points_non_conform += 1
        elif point_model.get('TypeParametre') == 'Plage_Numerique' and is_point_of_interest(result, point_model):
            points_out_of_range += 1
    
    # Afficher un résumé des résultats
    st.markdown("### Résumé des résultats")
    stats_cols = st.columns(4)
    
    with stats_cols[0]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{points_conform}</div>
            <div class="metric-label">Points Conformes</div>
        </div>
        """, unsafe_allow_html=True)
        
    with stats_cols[1]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#DC2626;">{points_non_conform}</div>
            <div class="metric-label">Non Conformes</div>
        </div>
        """, unsafe_allow_html=True)
        
    with stats_cols[2]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#FBBF24;">{points_out_of_range}</div>
            <div class="metric-label">Hors Plage</div>
        </div>
        """, unsafe_allow_html=True)
        
    with stats_cols[3]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#9CA3AF;">{points_na}</div>
            <div class="metric-label">Non Applicables</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Onglets pour naviguer entre les vues
    detail_tabs = st.tabs(["Vue par Catégorie", "Points Non Conformes", "Photos"])
    
    # Tab 1: Vue par catégorie
    with detail_tabs[0]:
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
                                is_poi = is_point_of_interest(result_data, point_model)
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
                            # Miniatures dans une grille responsive
                            num_photos = len(photos)
                            cols_per_row = min(num_photos, 5) # Max 5 miniatures par ligne
                            photo_cols = st.columns(cols_per_row)

                            for i, b64_string in enumerate(photos):
                                col_index = i % cols_per_row
                                with photo_cols[col_index]:
                                    try:
                                        # Nettoyer la string base64
                                        if isinstance(b64_string, str) and ',' in b64_string:
                                            b64_string = b64_string.split(',')[1]

                                        # Décoder et afficher la miniature
                                        img_bytes = base64.b64decode(b64_string)
                                        st.image(img_bytes, width=100)

                                        # Bouton pour ouvrir la modale
                                        button_key = f"view_photo_{inspection['id']}_{point_id}_{i}"
                                        if st.button("👁️ Agrandir", key=button_key, type="secondary", use_container_width=True):
                                            st.session_state.modal_photo_list = photos
                                            st.session_state.modal_photo_index = i
                                            st.session_state.modal_photo_caption = f"Photo {i+1} - Point: {point_model.get('PointDeControle', point_id)}"
                                            st.session_state.show_photo_modal = True
                                            st.rerun()

                                    except Exception as img_e:
                                        st.warning(f"Photo {i+1} invalide")
                    else:
                        st.info("Aucun résultat enregistré pour ce point.")
                    st.divider()

    # Tab 2: Points Non Conformes uniquement
    with detail_tabs[1]:
        non_conform_found = False
        
        for category, items in sorted(points_by_category.items()):
            non_conform_points = []
            
            for point_model in items:
                point_id = point_model.get('ID_Point')
                result_data = next((r for r in inspection.get('results', []) if r.get('idPoint') == point_id), None)
                
                if result_data and is_point_of_interest(result_data, point_model):
                    non_conform_points.append((point_model, result_data))
            
            if non_conform_points:
                non_conform_found = True
                with st.expander(f"**{category}** ({len(non_conform_points)} point(s) d'intérêt)", expanded=True):
                    for point_model, result_data in non_conform_points:
                        point_id = point_model.get('ID_Point')
                        
                        # Layout amélioré pour les points d'intérêt
                        st.markdown(f"""
                        <div style="background-color:#FEF2F2; padding:0.75rem; border-radius:0.375rem; margin-bottom:1rem;">
                            <h4 style="margin:0; color:#991B1B;">{point_model.get('PointDeControle', 'N/A')}</h4>
                            <p style="margin:0.25rem 0; font-size:0.875rem;">ID: {point_id}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.caption(f"**Critère:** {point_model.get('CritereAcceptation', 'N/A')}")
                        
                        # Affichage du résultat et des actions
                        result_cols = st.columns([2, 3])
                        with result_cols[0]:
                            # Format spécial selon le type de non-conformité
                            result_value = result_data.get('result')
                            if result_value == 'Non Conforme':
                                st.markdown("<span style='color:#991B1B; font-weight:bold;'>⚠️ Non Conforme</span>", unsafe_allow_html=True)
                            elif point_model.get('TypeParametre') == 'Plage_Numerique':
                                options_str = point_model.get('OptionsParametre', '')
                                if options_str:
                                    options = options_str.split(';')
                                    if len(options) == 2:
                                        min_val, max_val = map(float, options)
                                        st.markdown(f"<span style='color:#991B1B;'>⚠️ Hors plage [{min_val} - {max_val}]:</span> <b>{result_value}</b>", unsafe_allow_html=True)
                        
                        with result_cols[1]:
                            comment = result_data.get('comment', '')
                            if comment:
                                st.markdown(f"**Commentaire:** {comment}")
                            
                            # Afficher statut action corrective
                            action_key = (inspection['id'], point_id)
                            action_info = st.session_state.corrective_actions.get(action_key, {'status': 'À traiter', 'note': ''})
                            
                            st.markdown(f"**Statut action:** {status_to_badge(action_info['status'])}", unsafe_allow_html=True)
                            
                            if action_info['note']:
                                st.markdown(f"**Note action:** {action_info['note']}")
                        
                        # Affichage plus compact des photos si présentes
                        photos = result_data.get('photosBase64', [])
                        if photos:
                            if len(photos) == 1:
                                try:
                                    b64_string = photos[0]
                                    if isinstance(b64_string, str) and ',' in b64_string:
                                        b64_string = b64_string.split(',')[1]
                                    img_bytes = base64.b64decode(b64_string)
                                    st.image(img_bytes, width=250)
                                except:
                                    st.warning("Impossible d'afficher la photo")
                            else:
                                st.markdown(f"**{len(photos)} photos disponibles**")
                                if st.button(f"Voir les photos", key=f"view_all_{point_id}"):
                                    st.session_state.modal_photo_list = photos
                                    st.session_state.modal_photo_index = 0
                                    st.session_state.modal_photo_caption = f"Photos - Point: {point_model.get('PointDeControle', point_id)}"
                                    st.session_state.show_photo_modal = True
                                    st.rerun()
                        
                        st.divider()
                        
        if not non_conform_found:
            st.success("Aucun point non conforme trouvé dans cette inspection. Tout est conforme! 👍")
            
    # Tab 3: Photos uniquement
    with detail_tabs[2]:
        all_photos = []
        for result in inspection.get('results', []):
            point_id = result.get('idPoint')
            photos = result.get('photosBase64', [])
            
            if photos:
                point_model = next((item for item in model.get('items', []) if item.get('ID_Point') == point_id), None)
                point_name = point_model.get('PointDeControle', f'Point {point_id}') if point_model else f'Point {point_id}'
                
                for i, photo in enumerate(photos):
                    all_photos.append({
                        'point_id': point_id,
                        'point_name': point_name,
                        'photo': photo,
                        'index': i,
                        'category': point_model.get('Categorie', 'Sans Catégorie') if point_model else 'Sans Catégorie'
                    })
        
        if all_photos:
            st.markdown(f"### Galerie des Photos ({len(all_photos)} photos)")
            # Créer une grille de photos
            cols_per_row = 3
            for i in range(0, len(all_photos), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(all_photos):
                        photo_info = all_photos[i + j]
                        with cols[j]:
                            try:
                                photo = photo_info['photo']
                                if isinstance(photo, str) and ',' in photo:
                                    photo = photo.split(',')[1]
                                img_bytes = base64.b64decode(photo)
                                
                                st.image(img_bytes, use_column_width=True)
                                st.caption(f"{photo_info['point_name']}")
                                
                                if st.button("Agrandir", key=f"gallery_{photo_info['point_id']}_{photo_info['index']}"):
                                    # Trouver toutes les photos du même point
                                    point_photos = [p['photo'] for p in all_photos if p['point_id'] == photo_info['point_id']]
                                    point_index = next((idx for idx, p in enumerate(point_photos) if p == photo_info['photo']), 0)
                                    
                                    st.session_state.modal_photo_list = point_photos
                                    st.session_state.modal_photo_index = point_index
                                    st.session_state.modal_photo_caption = f"Photo - {photo_info['point_name']}"
                                    st.session_state.show_photo_modal = True
                                    st.rerun()
                            except:
                                st.warning("Impossible d'afficher cette photo")
        else:
            st.info("Aucune photo disponible dans cette inspection.")
