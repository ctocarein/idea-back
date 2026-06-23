# SPRINT 3 — Academy & Documents : « apprendre et progresser » (Semaines 5-6) · backend

> 🎯 **Objectif :** modules pédagogiques, progression, construire guidé (l'IA explique, le
> porteur écrit), gestion des documents.
> 🧪 **Démo :** un porteur lit un module, construit une section de BP guidé, voit sa progression.

**Capacité backend : 21 pts.** Détail : [BACKLOG.md](../docs/BACKLOG.md#sprint-3--academy--dashboard--apprendre-et-progresser).

## Board

### ⬜ To Do
- **IDX-ACADEMY-01** Modules pédagogiques `[5]` — `academy_lessons`, `GET /academy/lessons`.
- **IDX-ACADEMY-02** Progression & suivi `[3]` — `learning_progress`, `GET /academy/progress`.
- **IDX-ACADEMY-03** Construire guidé (assistant IA) `[8]` — sessions guidées, **garde-fous anti-production complète** (frontière gratuit/v2).
- **IDX-DOC-01** Upload documents (presigned MinIO) `[5]` — `upload-url` (5 min) → `confirm` ; ≤ 20 Mo ; `GET/DELETE`.

## Point de vigilance
- **Frontière gratuit/payant** : `ACADEMY-03` doit cadrer « apprendre à faire » (gratuit) vs
  « faire avec toi » (v2) — le porteur **reste l'auteur**, pas de génération clé en main (GUIDE §11).
- `DOC-01` est un **pré-requis** de `DIAG-02` (upload) — à prioriser si DIAG-02 a glissé.

## DoD du sprint
- [ ] Modules lisibles via API ; progression persistée par porteur.
- [ ] Assistant guidé : sauvegarde brouillon, routage LLM **bon marché** (coût freemium).
- [ ] Upload presigned : l'API ne fait jamais transiter les octets ; types/taille validés.
