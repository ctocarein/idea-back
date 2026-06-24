"""Service deck de pitch — upload direct + parsing → slides typées.

Le deck a besoin de ses octets pour être parsé : on l'uploade donc directement (multipart),
contrairement à la data-room (DOC-01 presigned). Les octets bruts peuvent être archivés dans
MinIO (best-effort, pour les vignettes en V2) ; le texte par slide est persisté en base.
"""

from __future__ import annotations

from uuid import UUID

from app.core.errors import BusinessRuleError, NotFoundError
from app.core.storage import ObjectStorage
from app.iam.dependencies import AuthContext, guard_owner_access
from app.llm.base import LLMProvider
from app.llm.prompt import build_pitch_prompt
from app.pitchsim import evaluate, forme, postmortem, scenario
from app.pitchsim.constants import BIO_AXES
from app.pitchsim.constants import committee as get_committee
from app.pitchsim.models import PitchSession, PitchStatus, PitchTurn, SlideKind
from app.pitchsim.parser import ALLOWED_DECK_TYPES, MAX_MAIN_SLIDES, parse_deck
from app.pitchsim.repository import (
    PitchDeckRepository,
    PitchRubricRepository,
    PitchRunRepository,
    PitchSessionRepository,
)
from app.pitchsim.schemas import (
    DeckOut,
    PitchRunOut,
    PostMortemOut,
    SessionOut,
    SessionStartIn,
    SlideOut,
    TurnOut,
)
from app.scoring import engine

MAX_DECK_BYTES = 20 * 1024 * 1024  # 20 Mo


class PitchDeckService:
    def __init__(self, repo: PitchDeckRepository, storage: ObjectStorage | None) -> None:
        self.repo = repo
        self.storage = storage
        self.session = repo.session

    def _validate(self, content_type: str, data: bytes) -> None:
        if content_type not in ALLOWED_DECK_TYPES:
            raise BusinessRuleError(f"Type de deck non supporté : {content_type} (PDF ou PPTX).")
        if not data:
            raise BusinessRuleError("Fichier vide.")
        if len(data) > MAX_DECK_BYTES:
            raise BusinessRuleError("Deck trop volumineux (max 20 Mo).")

    async def create_deck(
        self,
        ctx: AuthContext,
        *,
        title: str,
        project_id: UUID | None,
        content_type: str,
        data: bytes,
    ) -> DeckOut:
        self._validate(content_type, data)
        slides = parse_deck(content_type, data)[:MAX_MAIN_SLIDES]  # deck principal court
        if not slides:
            raise BusinessRuleError("Aucune slide détectée dans le fichier.")
        deck = await self.repo.create_deck(owner_id=ctx.user.id, project_id=project_id, title=title)
        await self.repo.add_slides(deck.id, SlideKind.MAIN, slides)
        await self.session.commit()
        return await self._deck_out(deck.id, title, project_id)

    async def add_slides(
        self,
        ctx: AuthContext,
        deck_id: UUID,
        *,
        kind: SlideKind,
        content_type: str,
        data: bytes,
    ) -> DeckOut:
        if kind == SlideKind.MAIN:
            raise BusinessRuleError("Le deck principal se crée via POST /pitchsim/decks.")
        deck = await self.repo.get_deck(deck_id)
        if deck is None:
            raise NotFoundError("pitch_deck")
        guard_owner_access(owner_id=deck.owner_id, ctx=ctx)
        self._validate(content_type, data)
        slides = parse_deck(content_type, data)
        await self.repo.add_slides(deck_id, kind, slides)
        await self.session.commit()
        return await self._deck_out(deck.id, deck.title, deck.project_id)

    async def get_deck(self, ctx: AuthContext, deck_id: UUID) -> DeckOut:
        deck = await self.repo.get_deck(deck_id)
        if deck is None:
            raise NotFoundError("pitch_deck")
        guard_owner_access(owner_id=deck.owner_id, ctx=ctx)
        return await self._deck_out(deck.id, deck.title, deck.project_id)

    async def _deck_out(self, deck_id: UUID, title: str, project_id: UUID | None) -> DeckOut:
        rows = await self.repo.slides_for_deck(deck_id)
        return DeckOut(
            id=deck_id,
            title=title,
            project_id=project_id,
            slides=[SlideOut.model_validate(r) for r in rows],
        )


class PitchSessionService:
    """Cycle de vie d'une session : briefing → tours (narration/réponse/imprévus) → délibération.

    Pendant les tours, la pré-notation est une **heuristique déterministe** (coût ~0) qui pilote
    les imprévus. Le vrai scoring LLM arrive à `finish` (PITCH-04).
    """

    def __init__(
        self,
        repo: PitchSessionRepository,
        rubrics: PitchRubricRepository,
        runs: PitchRunRepository,
        decks: PitchDeckRepository,
        provider: LLMProvider,
    ) -> None:
        self.repo = repo
        self.rubrics = rubrics
        self.runs = runs
        self.decks = decks
        self.provider = provider
        self.session = repo.session

    async def _load_owned(self, ctx: AuthContext, session_id: UUID) -> PitchSession:
        ps = await self.repo.get_session(session_id)
        if ps is None:
            raise NotFoundError("pitch_session")
        guard_owner_access(owner_id=ps.owner_id, ctx=ctx)
        return ps

    def _require_in_progress(self, ps: PitchSession) -> None:
        if ps.status != PitchStatus.IN_PROGRESS:
            raise BusinessRuleError(f"Session {ps.status.value} : action impossible.")

    def _personas(self, committee_key: str) -> list[dict]:
        committee = get_committee(committee_key)
        if committee is None:
            raise BusinessRuleError(f"Comité inconnu : {committee_key}")
        return committee["personas"]

    async def _add(self, ps: PitchSession, *, actor: str, kind: str, content: str, **kw: object) -> PitchTurn:
        seq = await self.repo.turn_count(ps.id)
        return await self.repo.add_turn(
            ps.id,
            seq=seq,
            actor=actor,
            kind=kind,
            content=content,
            **kw,  # type: ignore[arg-type]
        )

    async def start_session(self, ctx: AuthContext, data: SessionStartIn) -> SessionOut:
        self._personas(data.committee_key)  # valide le comité
        rubric = await self.rubrics.get_active()
        if rubric is None:
            raise BusinessRuleError("Aucune rubrique de pitch active.")
        ps = await self.repo.create_session(
            owner_id=ctx.user.id,
            project_id=data.project_id,
            deck_id=data.deck_id,
            committee_key=data.committee_key,
            mode=data.mode,
            rubric_version=rubric.version,
            config={
                "imprevus": data.imprevus,
                "hard_questions": data.hard_questions,
                "silence": data.silence,
                "duration_min": data.duration_min,
            },
        )
        # Briefing : le comité se présente (Écran 2, 00:10).
        names = ", ".join(p["name"] for p in self._personas(data.committee_key))
        await self._add(ps, actor="systeme", kind="deliberation", content=f"Le comité : {names}. Vous avez la parole.")
        await self.session.commit()
        return await self._out(ps)

    async def submit_slide(
        self, ctx: AuthContext, session_id: UUID, narration: str, slide_id: UUID | None
    ) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        self._require_in_progress(ps)
        await self._add(ps, actor="porteur", kind="narration", content=narration, slide_id=slide_id)
        # Pré-notation heuristique → un juge interrompt si une faiblesse touche son obsession.
        weak = scenario.assess_weakness(narration)
        interruption = scenario.choose_interruption(
            self._personas(ps.committee_key),
            weak,
            imprevus_enabled=ps.config.get("imprevus", True) and not ps.config.get("silence", False),
            hard_questions=ps.config.get("hard_questions", True),
            seed_key=f"{ps.id}:{await self.repo.turn_count(ps.id)}",
        )
        if interruption is not None:
            await self._add(
                ps,
                actor=interruption["actor"],
                kind="interruption",
                content=interruption["content"],
                meta={"axis": interruption["axis"], "imprevu_type": interruption["type"]},
            )
        await self.session.commit()
        return await self._out(ps)

    async def answer(self, ctx: AuthContext, session_id: UUID, answer: str, shown_slide_id: UUID | None) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        self._require_in_progress(ps)
        await self._add(ps, actor="porteur", kind="answer", content=answer, slide_id=shown_slide_id)
        await self.session.commit()
        return await self._out(ps)

    async def force_imprevu(self, ctx: AuthContext, session_id: UUID) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        self._require_in_progress(ps)
        surprise = scenario.investor_surprise()
        await self._add(
            ps,
            actor=surprise["actor"],
            kind="imprevu",
            content=surprise["content"],
            meta={"imprevu_type": surprise["type"]},
        )
        await self.session.commit()
        return await self._out(ps)

    async def finish(self, ctx: AuthContext, session_id: UUID) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        self._require_in_progress(ps)
        await self.repo.set_status(ps, PitchStatus.DELIBERATING)
        turns = await self.repo.turns_for_session(ps.id)

        # Verdicts du comité (déterministes), à partir des faiblesses cumulées.
        weak: set[str] = set()
        for t in turns:
            if t.kind == "narration":
                weak.update(scenario.assess_weakness(t.content))
        for v in scenario.deliberation(self._personas(ps.committee_key), list(weak)):
            await self._add(ps, actor=v["actor"], kind="deliberation", content=v["content"])

        # Scoring à finish : Fond (LLM ancré) + Forme (déterministe).
        await self._score(ps, turns)

        await self.repo.set_status(ps, PitchStatus.COMPLETED)
        await self.session.commit()
        return await self._out(ps)

    async def _score(self, ps: PitchSession, turns: list[PitchTurn]) -> None:
        rubric = await self.rubrics.get_active()
        if rubric is None:
            raise BusinessRuleError("Aucune rubrique de pitch active.")
        narration = "\n".join(t.content for t in turns if t.kind == "narration")
        transcript = "\n".join(t.content for t in turns if t.kind in ("narration", "answer"))
        n_questions = sum(1 for t in turns if t.kind in ("interruption", "question", "imprevu"))
        n_answers = sum(1 for t in turns if t.kind == "answer")

        # Texte des slides du deck (les juges « voient » les slides).
        slide_text = ""
        if ps.deck_id is not None:
            slides = await self.decks.slides_for_deck(ps.deck_id)
            slide_text = "\n".join(s.extracted_text for s in slides)

        committee = get_committee(ps.committee_key)
        label = committee["label"] if committee else ps.committee_key
        prompt = build_pitch_prompt(
            rubric_axes=rubric.axes,
            committee_label=label,
            transcript=transcript,
            slide_text=slide_text,
        )
        raw = await self.provider.analyze_json(prompt)
        axes = {k: int(v) for k, v in raw.get("axes", {}).items()}
        engine.validate_axes(rubric.axes, axes, rubric.scale_max)  # strict : le credential doit tenir
        justifications = raw.get("justifications", {})

        overall_fond = evaluate.weighted_overall(rubric.axes, axes)
        strengths, weaknesses = evaluate.top_bottom(rubric.axes, axes, justifications)
        forme_result = forme.score_forme(
            narration_text=narration,
            n_questions=n_questions,
            n_answers=n_answers,
            duration_min=int(ps.config.get("duration_min", 5)),
        )
        overall_global = round(0.7 * overall_fond + 0.3 * forme_result["overall"], 1)

        await self.runs.create(
            session_id=ps.id,
            project_id=ps.project_id,
            rubric_version=rubric.version,
            source="llm",
            model=getattr(self.provider, "model", ""),
            raw_output=raw,
            fond_scores=axes,
            overall_fond=overall_fond,
            forme_scores=forme_result["scores"],
            overall_forme=forme_result["overall"],
            overall_global=overall_global,
            strengths=strengths,
            weaknesses=weaknesses,
        )

    async def get_run(self, ctx: AuthContext, session_id: UUID) -> PitchRunOut:
        ps = await self._load_owned(ctx, session_id)
        run = await self.runs.latest_for_session(ps.id)
        if run is None:
            raise NotFoundError("pitch_run")
        return PitchRunOut.model_validate(run)

    async def post_mortem(self, ctx: AuthContext, session_id: UUID) -> PostMortemOut:
        ps = await self._load_owned(ctx, session_id)
        run = await self.runs.latest_for_session(ps.id)
        if run is None:
            raise NotFoundError("pitch_run")  # session pas encore terminée
        rubric = await self.rubrics.get_active()
        labels = {a["key"]: a["label"] for a in (rubric.axes if rubric else [])}

        # Radar 10 axes : 8 Fond notés + 2 biométriques (null, Mode Caméra).
        radar = [{"axis": k, "label": labels.get(k, k), "score": v, "kind": "fond"} for k, v in run.fond_scores.items()]
        radar += [{"axis": a["key"], "label": a["label"], "score": None, "kind": "bio"} for a in BIO_AXES]

        global_100 = round(run.overall_global * 10)
        scores = {
            "global": run.overall_global,
            "fond": run.overall_fond,
            "forme": run.overall_forme,
            "global_100": global_100,
            "level": postmortem.level_for(global_100),
        }

        # Progression : tous les runs du projet (sinon juste celui-ci).
        if ps.project_id is not None:
            history = await self.runs.list_for_project(ps.project_id)
            progression = [{"global": r.overall_global} for r in history]
        else:
            progression = [{"global": run.overall_global}]

        turns = await self.repo.turns_for_session(ps.id)
        return PostMortemOut(
            committee_key=ps.committee_key,
            scores=scores,
            radar=radar,
            timeline=[TurnOut.model_validate(t) for t in turns],
            strengths=run.strengths,
            weaknesses=run.weaknesses,
            progression=progression,
            training_plan=postmortem.training_plan(run.weaknesses),
        )

    async def abandon(self, ctx: AuthContext, session_id: UUID) -> None:
        ps = await self._load_owned(ctx, session_id)
        await self.repo.set_status(ps, PitchStatus.ABANDONED)
        await self.session.commit()

    async def get_session(self, ctx: AuthContext, session_id: UUID) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        return await self._out(ps)

    async def _out(self, ps: PitchSession) -> SessionOut:
        turns = await self.repo.turns_for_session(ps.id)
        return SessionOut(
            id=ps.id,
            committee_key=ps.committee_key,
            mode=ps.mode,
            status=ps.status.value,
            config=ps.config,
            turns=[TurnOut.model_validate(t) for t in turns],
        )
