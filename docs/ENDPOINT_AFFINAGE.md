# Endpoint d'affinage analyste — design (✅ IMPLÉMENTÉ)

> **Statut : implémenté** — `app/reports/{router,edit_service,dependencies}.py`,
> `app/iam/dependencies.py::guard_assigned_or_admin`, schéma `ScoreAdjustIn`, tests `test_guards.py`.

**« L'IA propose, l'humain dispose. »** L'analyste/mentor affine le pré-diagnostic à DEUX niveaux :
le **rapport structuré** (verdict, risques, concurrence, recos…) et les **12 scores** du Radar.
Document de cadrage : le quoi, les gardes, et le squelette prêt à coder.

> Cohérent avec la robustesse : chaque ajustement de score crée un **`ScoreRun` `source=human`**
> (rejouable, auditable) — il alimente la calibration IA↔humain. Le rapport édité est audité.

---

## 1. Les deux endpoints

| Endpoint | Rôle | Corps |
| :--- | :--- | :--- |
| `PATCH /reports/{id}/report` | Éditer la **couche structurée** (champs partiels) | `DiagnosticReport` partiel (merge `exclude_unset`) |
| `PATCH /reports/{id}/scores` | Ajuster les **12 dimensions** /10 | `ScoreAdjustIn { axes, justifications?, grid_version? }` |

Lecture inchangée : `GET /reports/{id}` renvoie le rapport affiné (la dernière version).

## 2. Permissions & garde-fou

- **Permission** : la route est gardée par `get_current_user` (authentifié) ; le contrôle fin
  est dans la **garde** (car l'admin a `PROJECT_READ_ANY` mais **pas** `MENTOR_REVIEW`) :
  admin (`PROJECT_READ_ANY`) **ou** mentor/analyste (`MENTOR_REVIEW`) **assigné**.
  Le **porteur n'édite pas** (ni l'une ni l'autre permission).
- **Garde de ressource** : admin → tout ; mentor/analyste → **uniquement le projet qui lui est
  assigné** (`project.assignee_id == ctx.user.id`). Sinon `403`.

```python
# app/iam/dependencies.py (à ajouter)
def guard_assigned_or_admin(*, project, ctx: AuthContext) -> None:
    if Permission.PROJECT_READ_ANY in ctx.permissions:
        return
    if Permission.MENTOR_REVIEW in ctx.permissions and project.assignee_id == ctx.user.id:
        return
    raise ForbiddenError("project")
```

## 3. Étapes — `PATCH /reports/{id}/scores` (le cœur)

1. Charger report → project ; `guard_assigned_or_admin`.
2. `scoring.build_score(source=HUMAN, axes=data.axes, justifications=…, category=project.sector,
   project_id, diagnostic_id, report_id, grid_version=data.grid_version)`
   → **validation stricte** (bornes + ancres) + **nouveau `ScoreRun`** + agrégation pondérée.
3. Mettre à jour le report : `radar_score = {gridVersion, axes}`, `comprehension = {pillars, overall}`.
4. **Audit** `report.rescored` (old/new axes, `actor=analyste`).
5. (Optionnel) enqueue `regenerate_bilan_pdf` pour régénérer le PDF avec les scores humains.
6. Commit unique. Retour : `ScoreResult`.

## 4. Étapes — `PATCH /reports/{id}/report`

1. Charger report → project ; `guard_assigned_or_admin`.
2. `patch.model_dump(exclude_unset=True)` → **fusion** dans `report.insights` (n'écrase que les
   champs fournis ; re-valider via `DiagnosticReport`).
3. **Audit** `report.edited`.
4. Commit. Retour : `ReportDetailOut`.

## 5. Squelette à déposer

```python
# app/reports/router.py — gardé par get_current_user ; la garde fait le contrôle fin.
@router.patch("/{report_id}/scores", response_model=ScoreResult)
async def adjust_report_scores(report_id: UUID, body: ScoreAdjustIn,
        ctx: AuthContext = Depends(get_current_user),
        svc: ReportEditService = Depends(get_report_edit_service)) -> ScoreResult:
    return await svc.adjust_scores(report_id, ctx, body)

@router.patch("/{report_id}/report", response_model=ReportDetailOut)
async def edit_report_content(report_id: UUID, body: DiagnosticReport,
        ctx: AuthContext = Depends(get_current_user),
        svc: ReportEditService = Depends(get_report_edit_service)) -> ReportDetailOut:
    return await svc.edit_report(report_id, ctx, body)
```

```python
# app/reports/edit_service.py  (assemble reports + projects + scoring + audit)
class ReportEditService:
    def __init__(self, reports, projects, scoring: ScoringService, auditor): ...

    async def adjust_scores(self, report_id, ctx, data: ScoreAdjustIn) -> ScoreResult:
        report = await self.reports.get_by_id(report_id) or raise NotFoundError("report")
        project = await self.projects.get_by_id(report.project_id)
        guard_assigned_or_admin(project=project, ctx=ctx)
        result = await self.scoring.build_score(
            project_id=project.id, diagnostic_id=report.diagnostic_id, report_id=report.id,
            category=project.sector, axes=data.axes, justifications=data.justifications,
            grid_version=data.grid_version, source=ScoreSource.HUMAN, model="human")
        report.radar_score = {"gridVersion": result.grid_version, "axes": result.axes}
        report.comprehension = {"pillars": result.pillars, "overall": result.overall}
        await self.auditor.record(actor_id=ctx.user.id, action="report.rescored",
                                  entity="report", entity_id=report.id, new_value={"overall": result.overall})
        await self.session.commit()
        return result

    async def edit_report(self, report_id, ctx, patch: DiagnosticReport) -> ReportDetailOut:
        report = await self.reports.get_by_id(report_id) or raise NotFoundError("report")
        project = await self.projects.get_by_id(report.project_id)
        guard_assigned_or_admin(project=project, ctx=ctx)
        merged = {**(report.insights or {}), **patch.model_dump(exclude_unset=True)}
        report.insights = DiagnosticReport.model_validate(merged).model_dump()
        await self.auditor.record(actor_id=ctx.user.id, action="report.edited",
                                  entity="report", entity_id=report.id)
        await self.session.commit()
        return ReportDetailOut.model_validate(report)
```

## 6. À prévoir
- `ScoreSource.HUMAN` (existe déjà) ; `model="human"` sur le ScoreRun.
- **Transaction** : pattern autobegin + `commit()` (jamais `session.begin()` en requête).
- **PDF** : régénération optionnelle après ajustement (job `regenerate_bilan_pdf`) — sinon le PDF
  garde les scores IA jusqu'au prochain run.
- **Calibration** : un `ScoreRun source=human` à côté du `source=llm` = la donnée d'accord IA↔expert
  pour le golden set / les métriques (`make calibrate`).
- **Tests prioritaires** : 403 (mentor non assigné), validation stricte (axe hors bornes/ancres),
  audit présent, fusion partielle du rapport.

## 7. Côté front (à construire à l'épic MENTOR/ADMIN)
- **`RadarScoreForm`** (saisie des 12 dims, rôle analyste/mentor) → `PATCH /reports/{id}/scores`.
- Édition du rapport (verdict/risques/concurrence/recos) dans `admin/projects/[id]` →
  `PATCH /reports/{id}/report`. Bouton masqué si non assigné (le back reste juge → 403).

*Backend implémenté. Reste : régénération PDF après ajustement (job optionnel) et l'UI front.*
