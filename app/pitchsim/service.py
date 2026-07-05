"""Service deck de pitch — upload direct + parsing → slides typées.

Le deck a besoin de ses octets pour être parsé : on l'uploade donc directement (multipart),
contrairement à la data-room (DOC-01 presigned). Les octets bruts peuvent être archivés dans
MinIO (best-effort, pour les vignettes en V2) ; le texte par slide est persisté en base.
"""

from __future__ import annotations

import asyncio
import base64
from uuid import UUID

from app.core.errors import BusinessRuleError, NotFoundError
from app.core.storage import ObjectStorage
from app.iam.dependencies import AuthContext, guard_owner_access
from app.llm.base import LLMProvider
from app.llm.prompt import build_pitch_prompt, build_verdict_prompt
from app.pitchsim import evaluate, forme, orchestrator, postmortem, scenario
from app.pitchsim.constants import BIO_AXES, FORMATS, committee_timing, format_qa, resolve_personas
from app.pitchsim.constants import committee as get_committee
from app.pitchsim.models import PitchDeck, PitchSession, PitchSlide, PitchStatus, PitchTurn, SlideKind
from app.pitchsim.parser import (
    ALLOWED_DECK_TYPES,
    MAX_MAIN_SLIDES,
    PDF_TYPES,
    PRESENTABLE_TYPES,
    parse_deck,
)
from app.pitchsim.render import png_to_data_url, render_pdf_to_pngs
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
from app.projects.repository import ProjectRepository
from app.scoring import engine

MAX_DECK_BYTES = 20 * 1024 * 1024  # 20 Mo


def deck_to_out(
    deck: PitchDeck, slides: list[PitchSlide], storage: ObjectStorage | None
) -> DeckOut:
    """DeckOut + URL présignée du fichier source (présentation dans le salon)."""
    file_url: str | None = None
    if deck.source_key and storage is not None:
        try:
            file_url = storage.presigned_get(deck.source_key)
        except Exception:  # storage indisponible → on dégrade (deck sans aperçu visuel)
            file_url = None
    return DeckOut(
        id=deck.id,
        title=deck.title,
        project_id=deck.project_id,
        slides=[SlideOut.model_validate(s) for s in slides],
        file_url=file_url,
        content_type=deck.source_content_type,
    )


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
        store_deck_source(self.storage, deck, content_type, data)  # présentation persistée
        await self.session.commit()
        return await self._deck_out(deck)

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
        return await self._deck_out(deck)

    async def get_deck(self, ctx: AuthContext, deck_id: UUID) -> DeckOut:
        deck = await self.repo.get_deck(deck_id)
        if deck is None:
            raise NotFoundError("pitch_deck")
        guard_owner_access(owner_id=deck.owner_id, ctx=ctx)
        return await self._deck_out(deck)

    async def _deck_out(self, deck: PitchDeck) -> DeckOut:
        rows = await self.repo.slides_for_deck(deck.id)
        return deck_to_out(deck, rows, self.storage)


def store_deck_source(
    storage: ObjectStorage | None, deck: PitchDeck, content_type: str, data: bytes
) -> None:
    """Persiste le fichier source du deck (présentation visuelle) si présentable + storage dispo."""
    if storage is None or content_type not in PRESENTABLE_TYPES:
        return
    key = f"pitch-decks/{deck.id}/source"
    try:
        storage.put_bytes(key=key, data=data, content_type=content_type)
        deck.source_key = key
        deck.source_content_type = content_type
    except Exception:  # storage KO → deck sans aperçu (dégradation gracieuse)
        pass


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
        projects: ProjectRepository,
        provider: LLMProvider,
        storage: ObjectStorage | None = None,
    ) -> None:
        self.repo = repo
        self.rubrics = rubrics
        self.runs = runs
        self.decks = decks
        self.projects = projects
        self.provider = provider
        self.storage = storage
        self.session = repo.session

    def _session_personas(self, ps: PitchSession) -> list[dict]:
        # Le comité SNAPSHOTTÉ (personas fixes + expert métier) ; repli sur le comité de base.
        snap = ps.orch.get("personas")
        return snap if snap else self._personas(ps.committee_key)

    async def _deck_text(self, ps: PitchSession) -> str:
        """Texte des slides du deck partagé (ce que les juges « voient ») — vide si aucun deck."""
        if ps.deck_id is None:
            return ""
        slides = await self.decks.slides_for_deck(ps.deck_id)
        return "\n".join(s.extracted_text for s in slides if s.extracted_text)

    async def _deck_images(self, ps: PitchSession) -> list[str]:
        """Images des slides (data URLs) pour la VISION — vide si pas de deck/storage/provider vision.

        Le deck source (PDF) est téléchargé puis rendu en PNG ; une image partagée telle quelle
        devient directement une data URL. Coûteux → on ne le fait que si le provider voit les images.
        """
        if ps.deck_id is None or self.storage is None:
            return []
        if not getattr(self.provider, "supports_vision", False):
            return []
        deck = await self.decks.get_deck(ps.deck_id)
        if deck is None or not deck.source_key:
            return []
        try:
            data = await asyncio.to_thread(self.storage.get_bytes, deck.source_key)
        except Exception:  # objet absent / storage KO → on dégrade (critique texte seul)
            return []
        ctype = deck.source_content_type or ""
        if ctype in PDF_TYPES:
            pngs = await asyncio.to_thread(render_pdf_to_pngs, data)
            return [png_to_data_url(p) for p in pngs]
        if ctype.startswith("image/"):
            return [f"data:{ctype};base64,{base64.b64encode(data).decode('ascii')}"]
        return []

    async def _load_owned(self, ctx: AuthContext, session_id: UUID) -> PitchSession:
        ps = await self.repo.get_session(session_id)
        if ps is None:
            raise NotFoundError("pitch_session")
        guard_owner_access(owner_id=ps.owner_id, ctx=ctx)
        return ps

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

        # SEC-01 : vérifier la propriété du projet ET du deck avant de les associer à la session.
        sector = None
        if data.project_id is not None:
            project = await self.projects.get_by_id(data.project_id)
            if project is None:
                raise NotFoundError("project")
            guard_owner_access(owner_id=project.owner_id, ctx=ctx)
            sector = project.sector

        if data.deck_id is not None:
            deck = await self.decks.get_deck(data.deck_id)
            if deck is None:
                raise NotFoundError("pitch_deck")
            guard_owner_access(owner_id=deck.owner_id, ctx=ctx)
            # Le deck doit appartenir au même projet (ou ne pas être lié à un projet).
            if data.project_id is not None and deck.project_id not in (None, data.project_id):
                raise BusinessRuleError("Ce deck n'appartient pas au projet sélectionné.")
        # Timing : contexte (comité) × format (dans les bornes autorisées).
        # NB : gating par niveau/palier freemium = hook futur (pas de modèle d'abonnement encore).
        timing = committee_timing(data.committee_key)
        fmt = data.format or timing["default_format"]
        if fmt not in timing["allowed_formats"]:
            raise BusinessRuleError(f"Format « {fmt} » non autorisé pour ce comité.")
        qa = format_qa(fmt)  # profondeur Q&A pilotée par le format
        personas = resolve_personas(data.committee_key, sector)
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
                "format": fmt,
                "duration_min": FORMATS.get(fmt, 5),
                "qa_questions_per_agent": qa["qa_questions_per_agent"],
                "qa_minutes": qa["qa_minutes"],
                "answer_target_s": qa["answer_target_s"],
                "tour_libre": timing["tour_libre"],
            },
        )
        # Snapshot du comité résolu (rejouable, inclut l'expert métier).
        ps.orch = {"personas": personas}
        names = ", ".join(p["name"] for p in personas)
        await self._add(ps, actor="systeme", kind="deliberation", content=f"Le comité : {names}. Vous avez la parole.")
        await self.session.commit()
        return await self._out(ps)

    async def _score(self, ps: PitchSession, turns: list[PitchTurn], verdicts: list[dict] | None = None, lang: str = "fr") -> None:
        rubric = await self.rubrics.get_active()
        if rubric is None:
            raise BusinessRuleError("Aucune rubrique de pitch active.")
        narration = "\n".join(t.content for t in turns if t.kind == "narration")
        transcript = "\n".join(t.content for t in turns if t.kind in ("narration", "answer"))
        n_questions = sum(1 for t in turns if t.kind in ("interruption", "question", "imprevu"))
        n_answers = sum(1 for t in turns if t.kind == "answer")

        # Texte des slides du deck (les juges « voient » les slides).
        slide_text = await self._deck_text(ps)

        committee = get_committee(ps.committee_key)
        label = committee["label"] if committee else ps.committee_key
        prompt = build_pitch_prompt(
            rubric_axes=rubric.axes,
            committee_label=label,
            transcript=transcript,
            slide_text=slide_text,
            lang=lang,
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
            verdicts=verdicts or [],
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
            verdicts=run.verdicts,
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
        deck_out: DeckOut | None = None
        if ps.deck_id is not None:
            deck = await self.decks.get_deck(ps.deck_id)
            if deck is not None:
                slides = await self.decks.slides_for_deck(deck.id)
                deck_out = deck_to_out(deck, slides, self.storage)
        return SessionOut(
            id=ps.id,
            committee_key=ps.committee_key,
            mode=ps.mode,
            status=ps.status.value,
            phase=ps.phase,
            config=ps.config,
            convictions=ps.orch.get("convictions", {}),
            turns=[TurnOut.model_validate(t) for t in turns],
            deck=deck_out,
        )

    async def attach_deck(
        self, ctx: AuthContext, session_id: UUID, *, content_type: str, data: bytes
    ) -> SessionOut:
        """Le porteur partage son deck dans le salon → persisté + rattaché à la session."""
        # Portes d'entrée AVANT tout accès DB (fail-fast + testable sans dépôt).
        if content_type not in PRESENTABLE_TYPES:
            raise BusinessRuleError(
                "Format non présentable. Exporte ton PowerPoint en PDF (ou partage une image)."
            )
        if not data:
            raise BusinessRuleError("Fichier vide.")
        if len(data) > MAX_DECK_BYTES:
            raise BusinessRuleError("Fichier trop volumineux (max 20 Mo).")
        ps = await self._load_owned(ctx, session_id)
        deck = await self.decks.create_deck(
            owner_id=ctx.user.id, project_id=ps.project_id, title="Deck de pitch"
        )
        # Texte pour les juges : seulement le PDF (les images n'ont pas de texte extractible).
        if content_type in PDF_TYPES:
            slides = parse_deck(content_type, data)[:MAX_MAIN_SLIDES]
            if slides:
                await self.decks.add_slides(deck.id, SlideKind.MAIN, slides)
        store_deck_source(self.storage, deck, content_type, data)
        ps.deck_id = deck.id
        await self.session.commit()
        return await self._out(ps)

    # --- Flux « comité silencieux » (PITCH-06) — additif, ne remplace pas encore 4A ---

    def _phase(self, ps: PitchSession) -> orchestrator.PitchPhase:
        return orchestrator.PitchPhase(ps.phase)

    async def _set_phase(self, ps: PitchSession, target: orchestrator.PitchPhase) -> None:
        orchestrator.assert_transition(self._phase(ps), target)  # saut illégal → 422
        ps.phase = target.value
        await self.session.flush()

    async def start_pitch(self, ctx: AuthContext, session_id: UUID) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        await self._set_phase(ps, orchestrator.PitchPhase.PITCHING)
        await self.session.commit()
        return await self._out(ps)

    async def narrate(self, ctx: AuthContext, session_id: UUID, narration: str, slide_id: UUID | None) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        if self._phase(ps) != orchestrator.PitchPhase.PITCHING:
            raise BusinessRuleError("Le pitch n'est pas en cours.")
        personas = self._session_personas(ps)
        weak = scenario.assess_weakness(narration)
        current = ps.orch.get("convictions", {})
        # Comité SILENCIEUX : réactions visuelles (obsession + humeur accumulée), jamais de parole.
        reactions = orchestrator.micro_reactions(personas, weak, current)
        convictions = orchestrator.update_convictions(current, personas, weak)
        fillers = scenario.count_fillers(narration)
        indicators = {
            "confiance": max(0, 10 - fillers),
            "clarte": 10 if len(narration.split()) >= 12 else 5,
        }
        await self._add(
            ps,
            actor="porteur",
            kind="narration",
            content=narration,
            slide_id=slide_id,
            meta={"reactions": reactions, "indicators": indicators},
        )
        ps.orch = {**ps.orch, "convictions": convictions}
        await self.session.commit()
        return await self._out(ps)

    async def end_pitch(self, ctx: AuthContext, session_id: UUID) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        turns = await self.repo.turns_for_session(ps.id)
        if not any(t.kind == "narration" for t in turns):
            raise BusinessRuleError("Présentez votre pitch avant de dire « j'ai terminé ».")
        await self._set_phase(ps, orchestrator.PitchPhase.QA)
        personas = self._session_personas(ps)
        # Mémoire inter-sessions : angles déjà posés aux sessions passées du projet.
        history = await self.repo.project_question_angles(ps.project_id) if ps.project_id else {}
        ps.orch = {
            **ps.orch,
            "qa_order": orchestrator.qa_order(personas),
            "qa_index": 0,
            "qa_asked": 0,  # questions déjà posées par le juge au micro
            "asked": {},
            "history": history,
        }
        await self._serve_question(ps, personas)
        await self.session.commit()
        return await self._out(ps)

    async def _serve_question(self, ps: PitchSession, personas: list[dict]) -> bool:
        # Sert une question au juge courant (angle varié, anti-doublon). False si rien à servir.
        order = ps.orch["qa_order"]
        idx = ps.orch["qa_index"]
        name = orchestrator.next_speaker(order, idx)
        if name is None:
            return False
        persona = next(p for p in personas if p["name"] == name)
        asked_n = ps.orch.get("qa_asked", 0)
        q = orchestrator.next_question(
            persona,
            ps.orch.get("asked", {}),
            seed_key=f"{ps.id}:{idx}:{asked_n}",
            history_by_axis=ps.orch.get("history", {}),
        )
        if q is None:
            return False
        asked = {**ps.orch.get("asked", {})}
        asked[q["axis"]] = [*asked.get(q["axis"], []), q["angle"]]
        ps.orch = {**ps.orch, "asked": asked, "current_speaker": name, "qa_asked": asked_n + 1}
        await self._add(
            ps,
            actor=name,
            kind="question",
            content=q["content"],
            meta={"axis": q["axis"], "angle": q["angle"]},
        )
        return True

    async def _advance_qa(self, ps: PitchSession, personas: list[dict]) -> None:
        # Passe au juge suivant (compteur remis à 0) ; plus de juge → tour libre.
        ps.orch = {**ps.orch, "qa_index": ps.orch.get("qa_index", 0) + 1, "qa_asked": 0}
        if orchestrator.next_speaker(ps.orch["qa_order"], ps.orch["qa_index"]) is None:
            await self._set_phase(ps, orchestrator.PitchPhase.FREE_ROUND)
        elif not await self._serve_question(ps, personas):
            await self._advance_qa(ps, personas)  # ce juge n'a aucune question → suivant

    async def respond(self, ctx: AuthContext, session_id: UUID, answer: str, shown_slide_id: UUID | None) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        if self._phase(ps) != orchestrator.PitchPhase.QA:
            raise BusinessRuleError("Ce n'est pas la phase de questions.")
        await self._add(ps, actor="porteur", kind="answer", content=answer, slide_id=shown_slide_id)
        personas = self._session_personas(ps)
        q_per = int(ps.config.get("qa_questions_per_agent", 1))
        # Le juge garde le micro tant qu'il n'a pas posé son quota (et qu'il a des angles).
        if ps.orch.get("qa_asked", 0) < q_per and await self._serve_question(ps, personas):
            pass
        else:
            await self._advance_qa(ps, personas)
        await self.session.commit()
        return await self._out(ps)

    async def deliberate(self, ctx: AuthContext, session_id: UUID) -> SessionOut:
        ps = await self._load_owned(ctx, session_id)
        personas = self._session_personas(ps)
        convictions = ps.orch.get("convictions", {})
        if self._phase(ps) == orchestrator.PitchPhase.QA:
            await self._set_phase(ps, orchestrator.PitchPhase.FREE_ROUND)
        # Tour libre : les agents se parlent (déterministe, d'après les convictions).
        for ex in orchestrator.free_round(personas, convictions):
            await self._add(ps, actor=ex["actor"], kind="free_round", content=ex["content"])
        await self._set_phase(ps, orchestrator.PitchPhase.DELIBERATING)

        turns = await self.repo.turns_for_session(ps.id)
        transcript = "\n".join(t.content for t in turns if t.kind in ("narration", "answer"))
        slide_text = await self._deck_text(ps)  # le verdict juge AUSSI la cohérence dit/montré
        slide_images = await self._deck_images(ps)  # vision : les juges VOIENT les slides (Pixtral)
        # Verdicts VERBATIM : un appel LLM par persona (ses mots, son style — Règle d'or n°5).
        verdicts: list[dict] = []
        for p in personas:
            prompt = build_verdict_prompt(
                persona=p,
                transcript=transcript,
                slide_text=slide_text,
                conviction=int(convictions.get(p["name"], 0)),
                lang=ctx.user.language,
            )
            if slide_images and hasattr(self.provider, "analyze_json_with_images"):
                raw = await self.provider.analyze_json_with_images(prompt, images=slide_images)
            else:
                raw = await self.provider.analyze_json(prompt)
            text = raw.get("verdict", "")
            verdicts.append({"agent": p["name"], "text": text, "vote": raw.get("vote", "conditional")})
            await self._add(ps, actor=p["name"], kind="deliberation", content=text)

        await self._score(ps, turns, verdicts=verdicts, lang=ctx.user.language)
        await self._set_phase(ps, orchestrator.PitchPhase.COMPLETED)
        ps.status = PitchStatus.COMPLETED
        await self.session.commit()
        return await self._out(ps)
