# Sprints — IDEAXION backend

Tableaux kanban par sprint (To Do / In Progress / Done). Le backlog complet, les
dépendances et les points vivent dans [`docs/BACKLOG.md`](../docs/BACKLOG.md) ;
le périmètre et les critères d'acceptation détaillés dans `GUIDE.md`.

| Sprint | Thème | Capacité back | Statut |
| :--- | :--- | ---: | :--- |
| [S1](S1-socle.md) | Socle (FND, AUTH) | 31 | 🟡 en cours (≈ 21 livrés au socle) |
| [S2](S2-diagnostic-radar.md) | Diagnostic & Radar (LLM, SCORING, DIAG, JOB) | 39 | 🟡 amorcé (JOB, LLM) |
| [S3](S3-academy-documents.md) | Academy & Documents (ACADEMY, DOC) | 21 | ⬜ |
| [S4](S4-pitch-simulator.md) | Simulateur de pitch (PITCHSIM) | 19 | ⬜ |
| [S5](S5-mentors-admin.md) | Mentors & Admin (MENTOR, ADMIN) | 31 | ⬜ |
| [S6](S6-instrumentation-ops.md) | Instrumentation, sécurité, RGPD, prod (INSTRUM, OPS) | 31 | ⬜ |

**Total backend MVP ≈ 164 pts** (hors stories front DS/DASH suivies dans `idea-front`).

## Rituels (rappel GUIDE §2.3)
Planning (lundi J1) · Daily (15 min) · Refinement (milieu) · Review/démo (vendredi J10) · Rétro.
Vélocité recalibrée après **S1 (sprint étalon)** : si < 32 pts observés → étaler sur 14-18 semaines.

## Convention de mise à jour
À chaque story terminée : déplacer la ligne dans le board du sprint (To Do → In Progress → Done)
**et** mettre à jour le statut dans `docs/BACKLOG.md`. Une story = une PR (GitHub Flow, branche
`feature/IDX-…`, squash merge sur `develop`).
