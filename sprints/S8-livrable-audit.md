# SPRINT 8 — Le livrable client · backend

> 🎯 **Objectif :** produire un **rapport d'audit remettable à une institution**, chaque constat
> relu et validé.
> 🧪 **Démo :** un PDF et un CSV remis sur un lot de 30 dossiers réels, avec la phrase
> « X dossiers sur Y ne présentent aucune incohérence détectée ».

**Capacité backend : 24 pts.** Trame de référence : [`docs/kit-audit-retrospectif.md` §3](../docs/kit-audit-retrospectif.md).

## Board

### ✅ Done
- **IDX-RAPPORT-01 ★** Relecture humaine `[8]` — [`review.py`](../app/inconsistencies/review.py). Export d'un fichier de relecture (`;` + BOM : s'ouvre directement dans un tableur francophone), tri par gravité, identifiant de constat **stable par empreinte** — le relecteur trie et filtre sans casser l'appariement. Alias `oui`/`non` acceptés. **`ensure_publishable` refuse de produire le moindre rapport tant qu'un constat reste `pending`** : la garantie est câblée, pas confiée à la discipline de l'opérateur. Les motifs de rejet sont récupérables (`rejection_notes`) — c'est la matière qui corrige le prompt au tour suivant.
- **IDX-RAPPORT-02 ★** Rendu HTML `[5]` — [`report.py`](../app/inconsistencies/report.py), conforme à la trame du kit. Pur (stdlib), testable hors-ligne, autonome (~8 Ko, aucune ressource externe). Sobre et institutionnel : un rapport d'audit ne doit pas ressembler au bilan porteur.
- **IDX-RAPPORT-03** Export PDF `[3]` — via **WeasyPrint**, comme `render_bilan_pdf` *(la fiche disait Playwright : c'était faux)*. Import paresseux, dégradation propre si l'extra `pdf` est absent — le HTML reste livrable.
- **IDX-RAPPORT-04** Export tableur `[2]` — libellés en clair, `;` + BOM, seuls les constats validés.
- **IDX-RAPPORT-05** Anonymisation `[3]` — assurée à l'ingestion (`--anonymize`, empreinte stable et non réversible) ; le rapport ne connaît que la référence.
- **IDX-RAPPORT-06** Tests `[3]` — 37 tests, dont : refus de publier sans relecture, échappement du contenu LLM, **lot sans constat produisant un rapport valide**, et une vérification qu'aucune note, aucun classement ni aucune recommandation n'apparaît.

### ⬜ To Do
- **IDX-RAPPORT-07** Installer l'extra `pdf` (WeasyPrint) sur le poste de production `[1]`.

## ⚠️ Anticipation obligatoire
La section **« ce que nous n'avons pas cherché » n'est pas optionnelle**. Elle énonce qu'on
n'évalue pas la qualité du projet, qu'on ne vérifie rien contre des sources externes, et qu'une
affirmation fausse mais cohérente ne sera pas détectée.

> Elle protège juridiquement **et** fonde la crédibilité : un auditeur qui énonce ses angles
> morts est plus crédible qu'un oracle. **Aucun rapport ne se génère sans elle.**

Deuxième règle non négociable : **aucune note, aucun classement, aucune recommandation**. Dès
qu'on note, on redevient contestable et on perd ce qui fait la force du produit.

## DoD du sprint
- [x] Rapport conforme à la trame, incluant la ligne « ne présentant aucune incohérence détectée ». *(PDF conditionné à `IDX-RAPPORT-07` ; le HTML est livrable en l'état.)*
- [x] Aucun constat publié sans relecture — **vérifié en conditions réelles** : la production a été refusée sur 8 constats non tranchés.
- [x] Anonymisation vérifiée sur un lot réel (références `D-xxxxxxxx`).
- [x] Un lot à zéro constat produit un rapport correct.
- [ ] **Un audit rétrospectif réellement livré à un interlocuteur externe**, avec retour écrit. ← *seule case restante ; elle ne se coche pas depuis l'éditeur.*

## Répétition générale (lot de démonstration)

Chaîne complète exécutée de bout en bout : **9 dossiers soumis → 7 analysés → 8 constats →
relecture → 6 publiés**.

La relecture a écarté deux constats, et c'est exactement ce qu'on attendait d'elle :
- un **jugement de plausibilité** (« un porteur seul ne peut pas gérer 15 000 utilisateurs ») — vrai peut-être, mais ce n'est pas une incompatibilité factuelle ;
- une **inférence du modèle** : il citait « cotisations reversées *intégralement* » alors que le récit ne contient pas ce mot. Le mot ajouté créait la contradiction.

> Le second cas est le meilleur argument pour le filtre humain : le constat était bien ancré
> dans le récit, bien formé, plausible — et faux. Aucune règle déterministe ne l'aurait attrapé.
