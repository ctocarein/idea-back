"""Sprint 4 bout en bout : comités (lecture) + upload/parsing d'un deck."""

from __future__ import annotations

from io import BytesIO

import pytest

pytestmark = pytest.mark.integration

PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


async def _register(client, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Sophie", "email": email, "password": "s3cret-pwd", "consent": True},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_pptx(titles: list[str]) -> bytes:
    from pptx import Presentation

    prs = Presentation()
    for t in titles:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = t
    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()


async def test_list_committees(client) -> None:
    headers = await _register(client, "pitch-committees@ideaxion.io")
    r = await client.get("/api/v1/pitchsim/committees", headers=headers)
    assert r.status_code == 200, r.text
    keys = {c["key"] for c in r.json()}
    assert keys == {"incubateur", "concours", "investisseur"}
    incub = next(c for c in r.json() if c["key"] == "incubateur")
    assert len(incub["personas"]) == 4


async def test_upload_deck_parses_slides(client) -> None:
    headers = await _register(client, "pitch-deck@ideaxion.io")
    data = _make_pptx(["Probleme", "Solution", "Marche"])

    r = await client.post(
        "/api/v1/pitchsim/decks",
        headers=headers,
        files={"file": ("deck.pptx", data, PPTX_TYPE)},
        data={"title": "Mon pitch"},
    )
    assert r.status_code == 200, r.text
    deck = r.json()
    assert deck["title"] == "Mon pitch"
    assert len(deck["slides"]) == 3
    assert all(s["kind"] == "main" for s in deck["slides"])

    # Relecture du deck par son id.
    r = await client.get(f"/api/v1/pitchsim/decks/{deck['id']}", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["slides"]) == 3


async def test_upload_deck_rejects_bad_type(client) -> None:
    headers = await _register(client, "pitch-badtype@ideaxion.io")
    r = await client.post(
        "/api/v1/pitchsim/decks",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"title": "x"},
    )
    assert r.status_code == 422, r.text


async def test_pitch_session_flow_with_committee(client) -> None:
    headers = await _register(client, "pitch-session@ideaxion.io")

    # Démarrer une session devant le comité Incubateur.
    r = await client.post(
        "/api/v1/pitchsim/sessions",
        headers=headers,
        json={"committee_key": "incubateur", "mode": "slides"},
    )
    assert r.status_code == 200, r.text
    ps = r.json()
    assert ps["status"] == "in_progress"
    sid = ps["id"]
    assert any(t["kind"] == "deliberation" for t in ps["turns"])  # briefing

    # Narration faible (courte, sans chiffres) → un juge interrompt sur sa faiblesse.
    r = await client.post(
        f"/api/v1/pitchsim/sessions/{sid}/slide",
        headers=headers,
        json={"narration": "Bonjour, voici mon projet."},
    )
    assert r.status_code == 200, r.text
    turns = r.json()["turns"]
    interruptions = [t for t in turns if t["kind"] == "interruption"]
    assert interruptions, "une faiblesse aurait dû déclencher une interruption"
    assert interruptions[0]["meta"].get("axis")

    # Le porteur répond.
    r = await client.post(
        f"/api/v1/pitchsim/sessions/{sid}/answer",
        headers=headers,
        json={"answer": "Le marché fait 500M€ selon l'étude McKinsey 2025."},
    )
    assert r.status_code == 200

    # Imprévu forcé (entraînement).
    r = await client.post(f"/api/v1/pitchsim/sessions/{sid}/imprevu", headers=headers)
    assert r.status_code == 200
    assert any(t["kind"] == "imprevu" for t in r.json()["turns"])

    # Fin → délibération + scoring + statut completed.
    r = await client.post(f"/api/v1/pitchsim/sessions/{sid}/finish", headers=headers)
    assert r.status_code == 200, r.text
    final = r.json()
    assert final["status"] == "completed"
    assert any(t["kind"] == "deliberation" for t in final["turns"])

    # Le score (Fond credential + Forme coaching) est disponible.
    r = await client.get(f"/api/v1/pitchsim/sessions/{sid}/run", headers=headers)
    assert r.status_code == 200, r.text
    run = r.json()
    assert len(run["fond_scores"]) == 8  # 8 axes Fond
    assert 0 <= run["overall_fond"] <= 10
    assert set(run["forme_scores"]) == {"concision", "fluidite", "completude", "structure"}
    assert 0 <= run["overall_global"] <= 10
    assert len(run["strengths"]) == 3 and len(run["weaknesses"]) == 3

    # Post-mortem : radar 10 axes, progression, plan d'entraînement → Academy/OPP.
    r = await client.get(f"/api/v1/pitchsim/sessions/{sid}/post-mortem", headers=headers)
    assert r.status_code == 200, r.text
    pm = r.json()
    assert len(pm["radar"]) == 10  # 8 Fond + 2 bio
    assert pm["scores"]["level"]["title"]
    assert pm["training_plan"][-1]["type"] == "opportunity"
    assert pm["progression"]

    # Action après finish interdite (machine à états).
    r = await client.post(
        f"/api/v1/pitchsim/sessions/{sid}/slide",
        headers=headers,
        json={"narration": "encore"},
    )
    assert r.status_code == 422


async def test_silent_committee_flow(client) -> None:
    # Parcours « comité silencieux » (PITCH-06) bout en bout sur le Postgres de test.
    headers = await _register(client, "silent@ideaxion.io")
    base = "/api/v1/pitchsim/sessions"

    r = await client.post(base, headers=headers, json={"committee_key": "incubateur", "mode": "slides"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert r.json()["phase"] == "briefing"
    # Comité résolu = 4 fixes + expert métier (ici « Expert Secteur » car pas de projet).
    assert any("Expert Secteur" in t["content"] for t in r.json()["turns"])

    # BRIEFING → PITCHING
    r = await client.post(f"{base}/{sid}/start-pitch", headers=headers)
    assert r.status_code == 200 and r.json()["phase"] == "pitching"

    # Narration → réactions SILENCIEUSES (aucune interruption), indicateurs en meta.
    r = await client.post(f"{base}/{sid}/narrate", headers=headers, json={"narration": "Bonjour, voici mon projet."})
    s = r.json()
    assert s["phase"] == "pitching"
    assert not any(t["kind"] == "interruption" for t in s["turns"])  # règle d'or n°1
    last_narr = [t for t in s["turns"] if t["kind"] == "narration"][-1]
    assert last_narr["meta"].get("reactions")

    # « J'ai terminé » → QA + 1re question servie.
    r = await client.post(f"{base}/{sid}/end-pitch", headers=headers)
    s = r.json()
    assert s["phase"] == "qa"
    assert any(t["kind"] == "question" for t in s["turns"])

    # Répond à chaque juge dans l'ordre (jusqu'à 2 questions/juge) → tour libre.
    for _ in range(20):
        cur = (await client.get(f"{base}/{sid}", headers=headers)).json()
        if cur["phase"] != "qa":
            break
        r = await client.post(
            f"{base}/{sid}/respond",
            headers=headers,
            json={"answer": "Réponse chiffrée et sourcée."},
        )
        assert r.status_code == 200, r.text
    assert (await client.get(f"{base}/{sid}", headers=headers)).json()["phase"] == "free_round"

    # Délibération + scoring → COMPLETED.
    r = await client.post(f"{base}/{sid}/deliberate", headers=headers)
    s = r.json()
    assert s["phase"] == "completed" and s["status"] == "completed"
    assert any(t["kind"] == "deliberation" for t in s["turns"])

    # Le score (credential) et le post-mortem sont disponibles.
    assert (await client.get(f"{base}/{sid}/run", headers=headers)).status_code == 200
    assert (await client.get(f"{base}/{sid}/post-mortem", headers=headers)).status_code == 200


async def _run_silent_qa(client, headers, project_id) -> set:
    base = "/api/v1/pitchsim/sessions"
    r = await client.post(base, headers=headers, json={"committee_key": "incubateur", "project_id": project_id})
    sid = r.json()["id"]
    await client.post(f"{base}/{sid}/start-pitch", headers=headers)
    await client.post(f"{base}/{sid}/narrate", headers=headers, json={"narration": "Projet de tontine."})
    await client.post(f"{base}/{sid}/end-pitch", headers=headers)
    for _ in range(20):
        cur = (await client.get(f"{base}/{sid}", headers=headers)).json()
        if cur["phase"] != "qa":
            break
        await client.post(f"{base}/{sid}/respond", headers=headers, json={"answer": "Réponse."})
    s = (await client.get(f"{base}/{sid}", headers=headers)).json()
    await client.post(f"{base}/{sid}/deliberate", headers=headers)
    return {(t["meta"]["axis"], t["meta"]["angle"]) for t in s["turns"] if t["kind"] == "question"}


async def test_questions_vary_across_sessions(client) -> None:
    # La mémoire inter-sessions doit faire varier les angles d'une session à l'autre.
    headers = await _register(client, "vary@ideaxion.io")
    r = await client.post(
        "/api/v1/diagnostics",
        headers=headers,
        json={
            "projectName": "Tontine+",
            "sector": "fintech",
            "description": "Appli de tontine via mobile money, traçabilité et confiance.",
            "consent": True,
            "archetype": "terrain",
        },
    )
    created = r.json()
    from app.diagnostics.handlers import handle_run_diagnostic

    await handle_run_diagnostic(
        {
            "diagnostic_id": created["diagnostic_id"],
            "project_id": created["project_id"],
            "report_id": created["report_id"],
            "mode": "guided",
        }
    )
    pid = created["project_id"]

    s1 = await _run_silent_qa(client, headers, pid)
    s2 = await _run_silent_qa(client, headers, pid)
    assert s1 and s2
    # Au moins un angle de la 2e session n'a pas été posé en 1re (variété inter-sessions).
    assert s2 - s1, "la 2e session devrait varier les angles posés"
