"""Structure des modules Academy — une par dimension Radar (d1..d12).

Chaque module définit :
- `context_questions` : 3-4 questions que le coach pose au porteur au démarrage
- `form_sections` : sections structurées du formulaire (pré-remplies par l'IA après la conversation)
"""

from __future__ import annotations

DIMENSION_MODULES: dict[str, dict] = {
    "d1": {
        "label": "Problème",
        "context_questions": [
            "Décris en 2-3 phrases le problème que résout ton projet.",
            "Qui vit ce problème concrètement ? Quel est leur profil ?",
            "Comment ce problème est-il géré aujourd'hui (solutions existantes) ?",
        ],
        "form_sections": [
            {"key": "problem_statement", "label": "Le problème", "hint": "Description précise du problème résolu"},
            {"key": "target_users", "label": "Qui le vit", "hint": "Profil des personnes concernées, taille estimée"},
            {"key": "frequency", "label": "Fréquence", "hint": "À quelle fréquence ce problème survient-il ?"},
            {"key": "existing_solutions", "label": "Solutions actuelles", "hint": "Ce qui existe déjà pour y répondre"},
            {"key": "proof", "label": "Preuves du problème", "hint": "Entretiens, données, observations terrain"},
            {
                "key": "missing",
                "label": "Ce qui manque",
                "hint": "Ce qu'il faut pour valider définitivement le problème",
            },
        ],
    },
    "d2": {
        "label": "Solution",
        "context_questions": [
            "Décris ta solution en 2-3 phrases concrètes.",
            "Comment fonctionne-t-elle techniquement ou opérationnellement ?",
            "Qu'est-ce qui est déjà construit ou testé ?",
        ],
        "form_sections": [
            {
                "key": "solution_description",
                "label": "Ta solution",
                "hint": "Description concrète de ce que fait ta solution",
            },
            {"key": "how_it_works", "label": "Comment ça fonctionne", "hint": "Mécanisme technique ou opérationnel"},
            {"key": "built_status", "label": "Ce qui est construit", "hint": "Idée, prototype, MVP, produit lancé ?"},
            {
                "key": "technical_feasibility",
                "label": "Faisabilité technique",
                "hint": "Stack, ressources, compétences nécessaires",
            },
            {
                "key": "missing_to_build",
                "label": "Ce qui manque pour construire",
                "hint": "Technologies, compétences, ressources",
            },
        ],
    },
    "d3": {
        "label": "Proposition de valeur",
        "context_questions": [
            "Quelle est la promesse unique de ton projet en une phrase ?",
            "En quoi es-tu différent des alternatives existantes ?",
            "Pour qui spécifiquement cette promesse est-elle forte ?",
        ],
        "form_sections": [
            {"key": "value_prop", "label": "La promesse", "hint": "En une phrase claire et mémorable"},
            {
                "key": "differentiators",
                "label": "Ce qui différencie",
                "hint": "Par rapport aux alternatives existantes",
            },
            {
                "key": "target_customer",
                "label": "Pour qui",
                "hint": "Le profil client qui bénéficie le plus de cette promesse",
            },
            {"key": "before_after", "label": "Avant / Après", "hint": "La vie du client avant et après ton produit"},
        ],
    },
    "d4": {
        "label": "Marché",
        "context_questions": [
            "Sur quel marché opères-tu ? Quelle est sa taille estimée ?",
            "Quel est ton segment initial prioritaire ?",
            "Comment comptes-tu accéder à ce segment ?",
        ],
        "form_sections": [
            {"key": "market_size", "label": "Taille du marché", "hint": "TAM/SAM/SOM si disponible, sinon estimation"},
            {
                "key": "target_segment",
                "label": "Segment initial",
                "hint": "Sous-marché prioritaire pour les 12 premiers mois",
            },
            {"key": "market_growth", "label": "Croissance du marché", "hint": "Tendances, croissance annuelle estimée"},
            {
                "key": "access_strategy",
                "label": "Comment y accéder",
                "hint": "Canaux, réseaux, partenariats pour atteindre ce segment",
            },
            {"key": "missing", "label": "Ce qui manque", "hint": "Données de marché, validations, accès à confirmer"},
        ],
    },
    "d5": {
        "label": "Concurrence",
        "context_questions": [
            "Qui sont tes principaux concurrents directs et indirects ?",
            "Quel est ton avantage concurrentiel réel ?",
            "Qu'est-ce qui te protège de la copie ?",
        ],
        "form_sections": [
            {"key": "direct_competitors", "label": "Concurrents directs", "hint": "Qui fait la même chose ou presque"},
            {
                "key": "indirect_competitors",
                "label": "Concurrents indirects",
                "hint": "Solutions alternatives au problème",
            },
            {"key": "competitive_advantage", "label": "Ton avantage", "hint": "En quoi tu es meilleur ou différent"},
            {
                "key": "barriers",
                "label": "Barrières à l'entrée",
                "hint": "Ce qui protège ton avantage (brevet, réseau, data, marque...)",
            },
            {"key": "positioning", "label": "Positionnement", "hint": "Prix, qualité, spécialisation, géographie"},
        ],
    },
    "d6": {
        "label": "Modèle économique",
        "context_questions": [
            "Comment ton projet génère-t-il des revenus ?",
            "Quelles sont tes principales charges (investissement initial et mensuel) ?",
            "À partir de combien de clients ton projet est-il viable ?",
        ],
        "form_sections": [
            {
                "key": "revenue_model",
                "label": "Comment tu génères des revenus",
                "hint": "Abonnement, commission, vente, licence...",
            },
            {
                "key": "capex",
                "label": "Investissement initial (CAPEX)",
                "hint": "Matériel, dev, installation, équipement",
            },
            {
                "key": "opex",
                "label": "Charges mensuelles (OPEX)",
                "hint": "Salaires, hébergement, marketing, maintenance",
            },
            {
                "key": "mvp_cost",
                "label": "Coût du MVP",
                "hint": "Ce qu'il faut pour lancer une première version testable",
            },
            {
                "key": "break_even",
                "label": "Point d'équilibre",
                "hint": "Nombre de clients ou revenus pour couvrir les charges",
            },
            {
                "key": "missing_resources",
                "label": "Ressources manquantes",
                "hint": "Ce qui manque pour que le modèle tienne",
            },
        ],
    },
    "d7": {
        "label": "Traction & Preuves",
        "context_questions": [
            "As-tu des clients, utilisateurs ou revenus réels ?",
            "Quels signaux d'intérêt concrets as-tu (entretiens, listes d'attente, pilotes) ?",
            "Comment mesures-tu ta progression ?",
        ],
        "form_sections": [
            {"key": "current_users", "label": "Utilisateurs / clients actuels", "hint": "Nombre, profil, source"},
            {"key": "revenue", "label": "Revenus générés", "hint": "Montant, récurrence, mode de paiement"},
            {"key": "testimonials", "label": "Témoignages et retours", "hint": "Citations, feedback terrain, NPS"},
            {
                "key": "growth_signals",
                "label": "Signaux de croissance",
                "hint": "Rétention, références, inscription organique",
            },
            {
                "key": "missing_proof",
                "label": "Preuve manquante",
                "hint": "Ce qu'il te faudrait pour démontrer la traction",
            },
        ],
    },
    "d8": {
        "label": "Potentiel de croissance",
        "context_questions": [
            "Comment passes-tu de tes 10 premiers clients à 1 000 ?",
            "Est-ce que tes coûts augmentent proportionnellement à tes revenus ?",
            "Quels effets réseau ou avantages de volume peux-tu créer ?",
        ],
        "form_sections": [
            {
                "key": "growth_levers",
                "label": "Leviers de croissance",
                "hint": "Ce qui fait grossir le projet sans proportionner les coûts",
            },
            {
                "key": "scalability",
                "label": "Scalabilité",
                "hint": "Comment les coûts évoluent vs les revenus quand tu grandis",
            },
            {
                "key": "network_effects",
                "label": "Effets réseau",
                "hint": "La valeur augmente-t-elle avec plus d'utilisateurs ?",
            },
            {
                "key": "automation",
                "label": "Automatisation possible",
                "hint": "Quelles tâches peuvent être automatisées",
            },
            {"key": "expansion", "label": "Plan d'expansion", "hint": "Géographie, segments, produits suivants"},
        ],
    },
    "d9": {
        "label": "Go-to-Market",
        "context_questions": [
            "Par quels canaux comptes-tu acquérir tes premiers clients ?",
            "Quel est ton coût d'acquisition estimé ?",
            "Comment vas-tu lancer concrètement dans les 3 prochains mois ?",
        ],
        "form_sections": [
            {
                "key": "acquisition_channels",
                "label": "Canaux d'acquisition",
                "hint": "Comment tu trouves et convaincs les clients",
            },
            {"key": "cac", "label": "Coût d'acquisition", "hint": "Combien coûte en moyenne l'acquisition d'un client"},
            {
                "key": "first_100_plan",
                "label": "Plan 100 premiers clients",
                "hint": "Actions concrètes pour les premiers clients",
            },
            {
                "key": "launch_timeline",
                "label": "Timeline de lancement",
                "hint": "Ce qui se passe dans les 30-60-90 prochains jours",
            },
            {"key": "missing", "label": "Ce qui manque", "hint": "Budget, équipe commerciale, contenu, partenariats"},
        ],
    },
    "d10": {
        "label": "Équipe & Compétences",
        "context_questions": [
            "Qui compose ton équipe aujourd'hui et quel est le rôle de chacun ?",
            "Quelles compétences clés manquent pour faire avancer le projet ?",
            "As-tu besoin d'un cofondateur ou de recruter ? Quel profil ?",
        ],
        "form_sections": [
            {"key": "current_team", "label": "Équipe actuelle", "hint": "Qui fait quoi, compétences, disponibilité"},
            {
                "key": "missing_skills",
                "label": "Compétences manquantes",
                "hint": "Ce dont le projet a besoin mais n'a pas encore",
            },
            {
                "key": "key_hires",
                "label": "Recrutements prioritaires",
                "hint": "Les 1-2 profils les plus urgents à trouver",
            },
            {
                "key": "cofondateur",
                "label": "Besoin d'un cofondateur",
                "hint": "Oui/non, quel profil, quel rôle, quelle association",
            },
            {"key": "timeline", "label": "Timing", "hint": "Quand as-tu besoin de ces renforts ?"},
        ],
    },
    "d11": {
        "label": "Niveau d'avancement",
        "context_questions": [
            "Où en es-tu concrètement dans la construction de ton projet ?",
            "Qu'est-ce qui est fait, testé, validé ?",
            "Quelle est la prochaine étape clé et qu'est-ce qui te bloque ?",
        ],
        "form_sections": [
            {
                "key": "what_is_done",
                "label": "Ce qui est fait",
                "hint": "Prototype, MVP, validations, revenus, équipe...",
            },
            {"key": "what_is_missing", "label": "Ce qui manque", "hint": "Pour atteindre la prochaine étape"},
            {"key": "next_milestone", "label": "Prochain jalon", "hint": "L'objectif concret à 3-6 mois"},
            {"key": "blockers", "label": "Bloqueurs actuels", "hint": "Ce qui empêche d'avancer aujourd'hui"},
            {
                "key": "resources_needed",
                "label": "Ressources nécessaires",
                "hint": "Financement, temps, compétences, équipe",
            },
        ],
    },
    "d12": {
        "label": "Risques & Freins",
        "context_questions": [
            "Quels sont les 3 risques majeurs qui pourraient faire échouer ton projet ?",
            "As-tu un plan pour réduire ou gérer chacun de ces risques ?",
            "Y a-t-il des contraintes réglementaires ou légales à anticiper ?",
        ],
        "form_sections": [
            {
                "key": "top_risks",
                "label": "Top 3 risques",
                "hint": "Les risques qui pourraient faire échouer le projet",
            },
            {"key": "mitigation", "label": "Plan de mitigation", "hint": "Comment tu comptes réduire chaque risque"},
            {
                "key": "dependencies",
                "label": "Dépendances critiques",
                "hint": "Fournisseurs, partenaires, technologies dont tu dépends",
            },
            {
                "key": "regulatory",
                "label": "Risques réglementaires",
                "hint": "Licences, conformité, réglementation sectorielle",
            },
            {
                "key": "missing_expertise",
                "label": "Expertises manquantes",
                "hint": "Domaines où tu manques de connaissances",
            },
        ],
    },
}
