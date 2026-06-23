# SPRINT 5 — Mentors & Back-office admin (Semaines 9-10) · backend

> 🎯 **Objectif :** onboarder des mentors (candidature CV+email → compte créé par l'admin), les
> rendre découvrables par les porteurs, donner à l'admin de quoi curer et piloter.
> 🧪 **Démo :** l'admin crée un compte mentor depuis une candidature ; un porteur choisit un mentor ; l'admin pilote un projet.

**Capacité backend : 31 pts.** Détail : [BACKLOG.md](../docs/BACKLOG.md#sprint-5--mentors--back-office-admin).

## Board

### ⬜ To Do
- **IDX-MENTOR-01** Candidature & création de compte par l'admin `[5]` — `POST /mentors/apply` (CV presigned), `/admin/mentor-applications`, invitation, audit. *(Le modèle `Invitation` est déjà posé dans `app/iam/invitations.py`.)*
- **IDX-MENTOR-02** Profil mentor `[5]` — secteurs, bio, agenda, honoraires (champ, non facturé), `GET/PATCH /mentors/me`.
- **IDX-MENTOR-03** Marketplace découverte (côté porteur) `[5]` — `GET /mentors` filtrable, `POST /mentors/{id}/request` *(booking/paiement = v2)*.
- **IDX-ADMIN-01** Back-office projets (liste, détail, pilotage) `[8]` — `GET /projects` filtré, `PATCH /projects/{id}/status` (machine à états MVP + audit), assignation analyste/mentor.
- **IDX-ADMIN-02** Curation mentors & gouvernance grille `[5]` — activer/suspendre/refuser, **versionner la grille Radar** + catégories.
- **IDX-ADMIN-03** Audit logs & timeline `[3]` — `GET /projects/{id}/timeline`, `GET /admin/audit-logs`.

## Réutilisations déjà en place
- Machine à états projet : [`app/projects/models.py`](../app/projects/models.py) (`ALLOWED_TRANSITIONS`, `can_transition`).
- Audit transactionnel : [`app/audit`](../app/audit) — brancher `ADMIN-01`/`ADMIN-03` dessus.
- Permission `MENTOR_APPROVE`, `PERMISSION_GRANT`, `AUDIT_READ` déjà au catalogue (`app/iam/permissions.py`).

## DoD du sprint
- [ ] Création de compte mentor par l'admin via le flux d'invitation (token usage unique, expiration, audit des deux bouts).
- [ ] `PATCH /projects/{id}/status` : transitions illégales → 422 ; audit dans la même transaction.
- [ ] Cloisonnement testé (un mentor non-certificateur ne signe pas ; un porteur ne voit pas le projet d'un autre).
