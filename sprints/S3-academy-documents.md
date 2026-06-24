# SPRINT 3 — Academy, Documents & Opportunités : « apprendre, progresser, devenir visible » (Semaines 5-6) · backend

> 🎯 **Objectif :** modules pédagogiques, progression, construire guidé (l'IA explique, le
> porteur écrit), gestion des documents, et **orientation vers les opportunités** (le porteur
> devient *visible* : « pour quoi suis-je prêt, que me manque-t-il »).
> 🧪 **Démo :** un porteur lit un module, construit une section de BP guidé, voit sa progression,
> et découvre les **opportunités pour lesquelles son score le rend éligible**.

**Capacité backend : 26 pts.** Détail : [BACKLOG.md](../docs/BACKLOG.md).

## Board

### ✅ Fait
- **IDX-ACADEMY-01** Modules pédagogiques `[5]` — `academy_lessons`, `GET /academy/lessons` (filtre `?topic=`).
- **IDX-ACADEMY-02** Progression & suivi `[3]` — `learning_progress`, `complete` idempotent, `GET /academy/progress`.
- **IDX-ACADEMY-03** Construire guidé (assistant IA) `[8]` — `guided_sessions`, prompt coach (le porteur reste l'auteur), brouillon + tours.
- **IDX-DOC-01** Upload documents (presigned MinIO) `[5]` — `upload-url` (5 min) → `confirm` ; ≤ 20 Mo ; types validés ; `GET/DELETE`.
- **IDX-OPP-01** Espace opportunités `[5]` — `opportunities` + `GET /opportunities`, **éligibilité déterministe** (pure, zéro LLM) ; « ce qu'il te manque » ; intérêt → event.

> ✅ Livré & prouvé : **82 tests verts** (dont intégration Academy/Opportunités), migration baseline → 17 tables (5 nouvelles) réversible, seed (6 leçons / 4 opportunités). DASH (front) suivi dans idea-front.

## Cadrage stratégique (vision)
- **ACADEMY résout les `next_actions`** (l'intent « Apprends : … » obtient une vraie destination) → la **boucle porteur se ferme**.
- **OPP-01 = la « visibilité »** (composant MVP #9) : la face porteur du pont B2B, **même moteur déterministe** que le routage. C'est ce qui distingue Ideaxion d'une formation : *« tu apprends, tu structures, tu es scoré, tu progresses, tu deviens visible »*.

## Point de vigilance
- **Frontière gratuit/payant** : `ACADEMY-03` doit cadrer « apprendre à faire » (gratuit) vs
  « faire avec toi » (v2) — le porteur **reste l'auteur**, pas de génération clé en main (GUIDE §11).
- `DOC-01` est un **pré-requis** de `DIAG-02` (upload) — à prioriser si DIAG-02 a glissé.

## DoD du sprint
- [ ] Modules lisibles via API ; progression persistée par porteur.
- [ ] Assistant guidé : sauvegarde brouillon, routage LLM **bon marché** (coût freemium).
- [ ] Upload presigned : l'API ne fait jamais transiter les octets ; types/taille validés.
- [ ] Opportunités : éligibilité **déterministe** (pas de LLM), event `opportunity_interest` émis, catalogue curé (la matière vient du produit).
