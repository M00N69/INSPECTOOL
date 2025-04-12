# Documentation Projet : Outils d'Inspection & Visualisation

Ce document décrit le fonctionnement et la structure de deux applications web complémentaires conçues pour faciliter la gestion des inspections qualité :

1.  **Application d'Inspection (HTML/CSS/JS)** : Permet aux inspecteurs de réaliser des inspections sur le terrain, même hors-ligne.
2.  **Visualiseur d'Inspections (Python/Streamlit)** : Permet aux superviseurs/managers d'analyser les données collectées, de suivre les actions correctives et d'obtenir des vues synthétiques.

---

## 1. Application d'Inspection (HTML/CSS/JS)

Cette application est une **Single Page Application (SPA)** construite entièrement en HTML, CSS (Tailwind CSS via CDN) et JavaScript (Vanilla JS). Elle fonctionne **côté client** et utilise **IndexedDB** pour le stockage local des données, permettant une utilisation hors-ligne.

### Fonctionnement Utilisateur

1.  **Gestion des Modèles de Checklists :**
    *   **Importation :** L'utilisateur peut importer des modèles de checklist au format Excel (`.xlsx`). Le fichier doit respecter un format précis (colonnes : `ID_Point`, `Categorie`, `PointDeControle`, `Description`, `CritereAcceptation`, `TypeParametre`, `OptionsParametre`). L'application valide le format et les types de données.
    *   **Nommage & Stockage :** Après validation, l'utilisateur nomme la checklist. Si un modèle du même nom existe, il peut le remplacer. Le modèle est stocké localement dans IndexedDB (`ChecklistModelsStore`).
    *   **Visualisation & Suppression :** Les modèles stockés sont listés. L'utilisateur peut les visualiser (aperçu des points) ou les supprimer.

2.  **Réalisation d'une Inspection :**
    *   **Démarrage :** L'utilisateur choisit un modèle existant, entre son nom (champ libre), et démarre l'inspection. L'heure de début est enregistrée. Une nouvelle entrée d'inspection est créée dans IndexedDB (`InspectionsStore`).
    *   **Interface :** L'application affiche les points de contrôle du modèle choisi. Un filtre par catégorie est disponible.
    *   **Saisie des Données :** Pour chaque point, l'utilisateur voit la description, le critère et dispose d'une zone de saisie adaptée au `TypeParametre` défini dans le modèle :
        *   `Booleen_CNC` : Boutons Conforme / Non Conforme.
        *   `Nombre_Decimal`/`Nombre_Entier` : Champ numérique (avec unité si spécifiée).
        *   `Texte_Libre` : Zone de texte.
        *   `Liste_Deroulante` : Menu déroulant.
        *   `Plage_Numerique` : Champ numérique avec validation par rapport aux seuils min/max. Une indication visuelle apparaît si hors plage.
        *   `Date_Heure` : Sélecteur de date et heure.
    *   **Option N/A :** Une case "Non Applicable" permet d'ignorer un point sans saisir de résultat.
    *   **Commentaires :** Un champ optionnel permet d'ajouter des précisions.
    *   **Photos :** L'utilisateur peut ajouter plusieurs photos par point (via l'appareil photo ou la galerie). Les photos sont redimensionnées/compressées côté client avant d'être stockées en Base64 dans IndexedDB pour limiter l'espace utilisé. Des miniatures sont affichées.
    *   **Sauvegarde Auto :** Chaque modification (résultat, commentaire, ajout/suppression photo) est automatiquement sauvegardée dans IndexedDB (`InspectionsStore`) après un court délai (debounce). La progression est affichée.
    *   **Finalisation :** Un bouton "Terminer l'Inspection" enregistre l'heure de fin et marque l'inspection comme "Terminée".

3.  **Gestion des Inspections :**
    *   **Liste :** Affiche les inspections en cours et terminées stockées localement.
    *   **Continuer :** Permet de reprendre une inspection "En cours".
    *   **Exporter Package (.zip) :** Pour chaque inspection (en cours ou terminée), l'utilisateur peut générer un fichier `.zip`. Ce package contient :
        *   Un fichier `inspection_data.json` avec toutes les métadonnées de l'inspection, les résultats, commentaires, les photos (encodées en Base64) et la structure complète du modèle de checklist utilisé.
        *   Le nom du fichier exporté inclut le nom de l'inspecteur et la date/heure d'export.
    *   **Importer Package (.zip) :** Permet de charger un fichier `.zip` précédemment exporté. L'application lit le `inspection_data.json`.
        *   Si une inspection avec le même ID existe déjà localement, elle propose de la remplacer/mettre à jour.
        *   Sinon, elle importe l'inspection comme une nouvelle entrée.
        *   Le modèle de checklist contenu dans le package est également importé/mis à jour si nécessaire.
    *   **Supprimer :** Permet de supprimer une inspection de la base locale.

4.  **Stockage Local (IndexedDB) :**
    *   Toutes les données (modèles, inspections, photos) sont stockées dans la base IndexedDB du navigateur.
    *   **Avertissement :** Un message permanent rappelle à l'utilisateur que vider le cache du navigateur effacera toutes les données locales. L'export régulier des packages est recommandé.
    *   Une estimation de l'espace de stockage utilisé est affichée.

### Structure du Code (HTML/CSS/JS)

*   **HTML (`index.html`) :** Structure la page avec les différentes sections (modèles, inspections, formulaire), les modales, l'indicateur de chargement, le conteneur de toasts et le pied de page. Inclut les CDN pour Tailwind, JSZip, SheetJS (pour Excel) et Font Awesome.
*   **CSS (dans `<style>` et Tailwind) :** Utilise principalement les classes utilitaires de Tailwind CSS. Quelques styles additionnels sont définis pour les modales, toasts, miniatures, etc.
*   **JavaScript (dans `<script>`) :** Organisé en objets littéraux agissant comme des modules :
    *   **`Utils` :** Fonctions utilitaires (génération ID, formatage dates, traitement images Base64, parsing Excel via SheetJS, création/extraction ZIP via JSZip, estimation stockage).
    *   **`Database` :** Encapsule toutes les interactions avec IndexedDB (initialisation, ajout/lecture/mise à jour/suppression de modèles et inspections). Gère les transactions et les erreurs (dont `QuotaExceededError`).
    *   **`UI` :** Gère la manipulation du DOM (références éléments, changement de vues, affichage listes, génération formulaire dynamique, affichage messages/modales, mise à jour barre progression, gestion miniatures photos, indicateur chargement).
    *   **`ChecklistManager` :** Logique métier pour la gestion des modèles (import Excel, sauvegarde, suppression, affichage liste, peuplement dropdown).
    *   **`InspectionManager` :** Logique métier pour les inspections (démarrage, continuation, sauvegarde auto via `scheduleAutoSave`, gestion des saisies formulaire, finalisation, export/import package, suppression, calcul progression).
    *   **Point d'Entrée (`DOMContentLoaded`) :** Initialise la base de données, puis les modules UI, ChecklistManager, et InspectionManager. Charge les données initiales.

---

## 2. Visualiseur d'Inspections (Python/Streamlit)

Cette application est construite avec **Python** et le framework **Streamlit**. Elle est conçue pour être déployée facilement (par exemple sur Streamlit Cloud) et permet l'analyse centralisée (bien que fonctionnant sur le serveur lors de l'exécution) des données exportées par l'application d'inspection.

### Fonctionnement Utilisateur

1.  **Chargement des Packages :**
    *   Via la barre latérale, l'utilisateur peut uploader un ou plusieurs fichiers `.zip` (packages d'inspection).
    *   L'application traite chaque ZIP côté serveur (Python) : extrait `inspection_data.json`, valide sa structure, vérifie les doublons par rapport aux inspections déjà chargées **en session**.
    *   Les données valides (`inspection` et `model`) sont stockées dans l'état de session Streamlit (`st.session_state`). Les statuts/notes d'actions correctives sont également initialisés dans `st.session_state`.
    *   Des notifications informent du succès/échec de chaque chargement.

2.  **Navigation par Onglets :**
    *   **📈 Tableau de Bord :**
        *   Affiche des KPIs clés calculés sur l'ensemble des données chargées : nombre d'inspections, nombre de non-conformités, nombre de valeurs hors plage, taux de conformité global.
        *   Présente des graphiques (Plotly) : répartition des statuts d'action, taux de conformité par catégorie, top 5 des points d'intérêt les plus fréquents.
    *   **📋 Liste Inspections :**
        *   Liste les inspections chargées avec des informations clés (modèle, inspecteur, date).
        *   Un indicateur ⚠️ signale les inspections contenant des points d'intérêt.
        *   Chaque inspection est dans un `st.expander`. Cliquer sur "Voir Détails" ouvre une modale (`st.dialog`) affichant l'inspection complète. Cliquer sur "Retirer" supprime l'inspection et ses actions associées de la session actuelle.
        *   Un bouton "Vider Toutes les Données" (avec confirmation) permet de réinitialiser la session.
    *   **🔍 Vue Agrégée POI :**
        *   Affiche **uniquement les points d'intérêt** (Non Conforme, Hors Plage, Erreur Valeur) de toutes les inspections chargées, **regroupés par catégorie** dans des `st.expander`.
        *   Chaque expander de catégorie affiche un résumé (nombre de points, % terminé) et une barre de progression.
        *   À l'intérieur de chaque catégorie, un tableau éditable (`st.data_editor`) affiche les points d'intérêt correspondants.
        *   **Colonnes Clés :** Date, Inspecteur, Point de Contrôle, **Type Problème** (ex: "Non Conforme", "Inférieur Min"), Résultat (avec indicateur visuel 🔴⬇️⬆️), **Statut Action** (éditable via Selectbox), **Note Action** (éditable via champ texte), Commentaire, Nb Photos.
        *   Des filtres globaux (recherche texte, inspecteur, point, statut action, type problème) permettent d'affiner la vue sur l'ensemble des catégories.
        *   Les modifications faites dans `st.data_editor` (Statut Action, Note Action) sont sauvegardées **dans l'état de session** (`st.session_state.corrective_actions`).
    *   **📝 Suivi Actions :**
        *   **Sous-onglet Liste & Édition :** Affiche toutes les actions correctives (une ligne par point d'intérêt) sous forme de cartes. Permet de filtrer (statut, catégorie, type problème, recherche). Un bouton "Éditer" ouvre un formulaire détaillé pour modifier le statut, la note, assigner un responsable et une date d'échéance. Affiche aussi les photos associées au point.
        *   **Sous-onglet Planification & Calendrier :** Affiche un tableau éditable (`st.data_editor`) des actions non terminées/annulées pour assigner/modifier la date d'échéance et le responsable. Un mini-calendrier visuel (widget date + rendu HTML) montre les échéances du mois sélectionné.
        *   **Sous-onglet Statistiques Actions :** Affiche des graphiques sur la répartition des statuts, le suivi par catégorie et par responsable.

3.  **Visualisation Détaillée (Modale) :**
    *   Affiche l'intégralité d'une inspection sélectionnée.
    *   Les points d'intérêt sont **mis en évidence** avec un fond et une bordure colorés.
    *   Les photos sont affichées en miniatures cliquables qui ouvrent une **modale photo** dédiée avec navigation (Précédent/Suivant) et affichage en grand.
    *   Si un point est un POI, les champs pour éditer le **Statut Action** et la **Note Action** apparaissent directement dans la vue détaillée.

4.  **Exports :**
    *   **Export Agrégé (ZIP) :** Un bouton dans la sidebar permet de générer un nouveau fichier `.zip`. Ce ZIP contient un unique fichier `aggregated_export.json` incluant **toutes les données des inspections chargées ET les dernières mises à jour des statuts/notes d'actions correctives et de planification** faites pendant la session. C'est le moyen principal de sauvegarder le travail de suivi.
    *   **Export Actions (Excel) :** Un bouton dans l'onglet "Suivi Actions" génère un fichier `.xlsx` formaté contenant la liste de toutes les actions correctives avec leurs détails (point, inspection, problème, statut, note, échéance, responsable). Inclut une feuille de récapitulatif.

5.  **Persistance (Volatile) :**
    *   **Important :** Par défaut (déploiement sur Streamlit Cloud gratuit), toutes les données chargées et les modifications des actions correctives/planification sont **perdues** lorsque l'utilisateur ferme l'onglet ou la session expire. L'**Export ZIP** ou **Excel** est crucial pour sauvegarder le travail. Un avertissement est affiché.

### Structure du Code (Python/Streamlit)

*   **Fichier Principal (`visualizer_app_v2.py`) :** Contient l'ensemble du code Streamlit.
    *   **Configuration & Initialisation :** `st.set_page_config`, initialisation de `st.session_state`.
    *   **Fonctions Utilitaires :** `get_problem_type_and_display`, `is_point_of_interest_enhanced`, `load_zip_data`, `prepare_aggregated_dataframe`, `update_corrective_actions_from_df`, `render_inspection_detail`, `calculate_dashboard_metrics`, `prepare_export_data`, `create_export_zip`, `export_actions_to_excel`.
    *   **Interface Utilisateur :** Définition de la `st.sidebar` (chargement, actions globales, exports), définition des `st.tabs` principaux, et logique d'affichage/interaction pour chaque onglet et sous-onglet, y compris l'utilisation de `st.expander`, `st.data_editor`, `st.metric`, `st.plotly_chart`, `st.dialog`.
    *   **Logique Applicative :** Utilisation intensive de `st.session_state` pour maintenir l'état, appels aux fonctions utilitaires, gestion des callbacks `on_click` pour les boutons.
*   **Fichier `requirements.txt` :** Liste les dépendances Python (`streamlit`, `pandas`, `plotly`, `pillow`, `openpyxl`).

---

Ce README fournit une vue d'ensemble complète pour comprendre et utiliser les deux applications.
