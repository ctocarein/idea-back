"""Brouillon de diagnostic — persistance serveur de la saisie en cours.

Prouve le câblage réel : unicité partielle en base, propriété imposée (jamais désignée),
clôture DANS la transaction de soumission, et couverture RGPD.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email: str, name: str = "Awa") -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": "s3cret-pwd", "consent": True},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_draft_is_absent_until_first_save(client) -> None:
    headers = await _register(client, "draft-empty@ideaxion.io")
    r = await client.get("/api/v1/diagnostics/draft", headers=headers)
    # 404 = « rien à reprendre » : c'est le signal que le front attend.
    assert r.status_code == 404


async def test_put_is_idempotent_and_keeps_a_single_row(client) -> None:
    headers = await _register(client, "draft-put@ideaxion.io")

    first = await client.put(
        "/api/v1/diagnostics/draft",
        headers=headers,
        json={"answers": {"d1": "un problème"}, "payload": {"title": "Tontine+"}, "lastDimension": "d1"},
    )
    assert first.status_code == 200, first.text

    second = await client.put(
        "/api/v1/diagnostics/draft",
        headers=headers,
        json={"answers": {"d1": "un problème", "d2": "ma solution"}, "payload": {}, "lastDimension": "d2"},
    )
    assert second.status_code == 200, second.text

    # UNE seule ligne : l'appel est répété à chaque dimension, il ne doit rien accumuler.
    assert second.json()["id"] == first.json()["id"]

    r = await client.get("/api/v1/diagnostics/draft", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["answers"] == {"d1": "un problème", "d2": "ma solution"}
    assert body["lastDimension"] == "d2"  # le champ qui situe le décrochage


async def test_draft_is_scoped_to_its_owner(client) -> None:
    # La propriété est IMPOSÉE, pas vérifiée : un porteur ne peut pas désigner un autre
    # `owner_id`, donc il n'existe aucun chemin pour lire le brouillon de quelqu'un d'autre.
    awa = await _register(client, "draft-awa@ideaxion.io", "Awa")
    kofi = await _register(client, "draft-kofi@ideaxion.io", "Kofi")

    await client.put(
        "/api/v1/diagnostics/draft",
        headers=awa,
        json={"answers": {"d1": "secret d'Awa"}, "payload": {}},
    )
    assert (await client.get("/api/v1/diagnostics/draft", headers=kofi)).status_code == 404

    await client.put("/api/v1/diagnostics/draft", headers=kofi, json={"answers": {"d1": "à Kofi"}, "payload": {}})
    assert (await client.get("/api/v1/diagnostics/draft", headers=awa)).json()["answers"]["d1"] == "secret d'Awa"


async def test_delete_discards_and_is_idempotent(client) -> None:
    headers = await _register(client, "draft-delete@ideaxion.io")
    await client.put("/api/v1/diagnostics/draft", headers=headers, json={"answers": {"d1": "x"}, "payload": {}})

    assert (await client.delete("/api/v1/diagnostics/draft", headers=headers)).status_code == 204
    assert (await client.get("/api/v1/diagnostics/draft", headers=headers)).status_code == 404
    # Rejouable : le front n'a pas à distinguer « supprimé » de « rien à supprimer ».
    assert (await client.delete("/api/v1/diagnostics/draft", headers=headers)).status_code == 204


async def test_submission_closes_the_draft_and_frees_the_slot(client) -> None:
    headers = await _register(client, "draft-submit@ideaxion.io")
    await client.put(
        "/api/v1/diagnostics/draft",
        headers=headers,
        json={"answers": {"d1": "une idée"}, "payload": {"title": "Tontine+"}, "lastDimension": "d3"},
    )

    r = await client.post(
        "/api/v1/diagnostics",
        headers=headers,
        json={
            "projectName": "Tontine+",
            "sector": "finance",
            "description": "Appli de tontine via mobile money, traçabilité et confiance.",
            "consent": True,
        },
    )
    assert r.status_code == 202, r.text

    # Clos dans LA MÊME transaction : sinon le front proposerait de « reprendre » une
    # saisie déjà partie en diagnostic.
    assert (await client.get("/api/v1/diagnostics/draft", headers=headers)).status_code == 404

    # Et l'unicité partielle n'empêche pas d'en commencer un nouveau : elle ne porte que
    # sur les brouillons VIVANTS.
    again = await client.put(
        "/api/v1/diagnostics/draft", headers=headers, json={"answers": {"d1": "autre"}, "payload": {}}
    )
    assert again.status_code == 200, again.text


async def test_submission_without_draft_succeeds(client) -> None:
    # Parcours direct / upload : la soumission ne doit jamais échouer à cause d'un
    # brouillon absent.
    headers = await _register(client, "draft-none@ideaxion.io")
    r = await client.post(
        "/api/v1/diagnostics",
        headers=headers,
        json={
            "projectName": "Direct",
            "sector": "commerce",
            "description": "Boutique de quartier qui veut vendre en ligne, livraison locale.",
            "consent": True,
        },
    )
    assert r.status_code == 202, r.text


async def test_draft_is_covered_by_the_gdpr_export(client) -> None:
    headers = await _register(client, "draft-rgpd@ideaxion.io")
    await client.put(
        "/api/v1/diagnostics/draft",
        headers=headers,
        json={"answers": {"d1": "donnée personnelle"}, "payload": {}, "lastDimension": "d1"},
    )
    r = await client.get("/api/v1/me/export", headers=headers)
    assert r.status_code == 200, r.text
    drafts = r.json()["diagnostic_drafts"]
    assert len(drafts) == 1
    assert drafts[0]["answers"] == {"d1": "donnée personnelle"}
    assert drafts[0]["consent_at"] is not None  # consentement PROPRE au brouillon


async def test_draft_requires_authentication(client) -> None:
    # Aucune persistance serveur en anonyme : le parcours anonyme reste sur localStorage.
    assert (await client.get("/api/v1/diagnostics/draft")).status_code == 401
    assert (await client.put("/api/v1/diagnostics/draft", json={"answers": {}, "payload": {}})).status_code == 401
