# SPRINT 6 — Instrumentation, sécurité, RGPD & prod (Semaines 11-12) · backend

> 🎯 **Objectif :** rendre le freemium **apprenant** (tableau de bord d'apprentissage), durcir,
> rendre conforme, déployer.
> 🧪 **Démo :** le dashboard d'apprentissage montre la transformation ; la recette passe ; la prod est en ligne.

**Capacité backend : 31 pts.** Détail : [BACKLOG.md](../docs/BACKLOG.md#sprint-6--instrumentation-sécurité-rgpd--prod).

## Board

### ⬜ To Do
- **IDX-INSTRUM-01 ★** Tableau de bord d'apprentissage `[8]` — captation d'événements (diag, modules, pitchs, readiness, intérêt Pro) ; `GET /admin/learning-dashboard` (Radar avant/après, rétention, signaux d'intention de payer). **Raison d'être du freemium — prioritaire.**
- **IDX-OPS-01** Tests de recette `[5]` — scénarios `CAHIER_RECETTE` automatisés ; couverture backend ≥ 70 %.
- **IDX-OPS-02** Durcissement sécurité `[5]` — headers, sanitization, rate-limit effectif ; **tests 401/403 exhaustifs**.
- **IDX-OPS-03** Conformité RGPD `[5]` — export JSON ; effacement cascade (projet/diag/docs + objets MinIO) ; transactionnel.
- **IDX-OPS-04** Monitoring & supervision jobs `[3]` — Sentry + métriques ; `GET /admin/jobs` + relance ; alerte job échoué.
- **IDX-OPS-05** CI/CD & mise en production `[5]` — push `develop`→staging, merge `main`→prod, health post-déploiement.

## ⚠️ Anticipation obligatoire
**INSTRUM ne se construit pas qu'en S6** : les événements doivent être **émis dès qu'ils existent**
(S2-S5). Prévoir l'émission dans chaque story de parcours, pas un rattrapage final (GUIDE §9).

## DoD du sprint
- [ ] Dashboard d'apprentissage opérationnel (transformation mesurée).
- [ ] Recette `CAHIER_RECETTE` verte ; couverture backend ≥ 70 %.
- [ ] RGPD : export + effacement cascade (DB + MinIO) testés.
- [ ] Prod en ligne ; staging auto sur `develop` ; health post-déploiement OK.
