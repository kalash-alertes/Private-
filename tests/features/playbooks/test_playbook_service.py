"""Tests du service `playbooks` : création, remplacement des étapes, unicité, suppression. Données synthétiques."""

import pytest
from pydantic import ValidationError

from backend.core.domain_errors import BusinessRuleViolationError, ResourceConflictError, ResourceNotFoundError
from backend.core.pagination import PaginationParameters
from backend.features.playbooks import service as playbooks_service
from backend.features.playbooks.schemas import PlaybookListFilters, PlaybookStepWriteRequest, PlaybookWriteRequest
from tests.synthetic_data import build_synthetic_playbook_request


def test_playbook_is_created_with_ordered_steps(database_session) -> None:
    playbook = playbooks_service.create_playbook(database_session, build_synthetic_playbook_request(step_count=3))

    assert [step.ordre for step in playbook.etapes] == [1, 2, 3]
    assert [step.titre for step in playbook.etapes] == ["Étape synthétique 1", "Étape synthétique 2", "Étape synthétique 3"]
    assert playbooks_service.find_playbook_id_for_category(database_session, "synthetique_intrusion") == playbook.id


def test_playbook_requires_a_source_and_at_least_one_step() -> None:
    with pytest.raises(ValidationError):
        PlaybookWriteRequest(nom="Sans source", source="  ", etapes=[PlaybookStepWriteRequest(titre="Étape")])
    with pytest.raises(ValidationError):
        PlaybookWriteRequest(nom="Sans étape", source="Source synthétique", etapes=[])


def test_playbook_name_and_category_are_unique(database_session) -> None:
    playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())

    with pytest.raises(ResourceConflictError):
        playbooks_service.create_playbook(database_session, build_synthetic_playbook_request(categorie="autre"))
    with pytest.raises(ResourceConflictError):
        playbooks_service.create_playbook(database_session, build_synthetic_playbook_request(nom="Autre nom"))
    # Plusieurs playbooks peuvent n'avoir aucune catégorie.
    playbooks_service.create_playbook(database_session, build_synthetic_playbook_request(categorie=None, nom="A"))
    playbooks_service.create_playbook(database_session, build_synthetic_playbook_request(categorie=None, nom="B"))


def test_update_keeps_steps_sent_with_their_id_and_reorders_them(database_session) -> None:
    playbook = playbooks_service.create_playbook(database_session, build_synthetic_playbook_request(step_count=3))
    first_step, second_step, third_step = playbook.etapes

    updated_playbook = playbooks_service.update_playbook(
        database_session,
        playbook.id,
        PlaybookWriteRequest(
            nom="Playbook renommé",
            source="Source synthétique",
            etapes=[
                PlaybookStepWriteRequest(id=third_step.id, titre="Ancienne étape 3"),
                PlaybookStepWriteRequest(titre="Nouvelle étape"),
                PlaybookStepWriteRequest(id=first_step.id, titre="Ancienne étape 1"),
            ],
        ),
    )

    assert [step.titre for step in updated_playbook.etapes] == ["Ancienne étape 3", "Nouvelle étape", "Ancienne étape 1"]
    assert [step.ordre for step in updated_playbook.etapes] == [1, 2, 3]
    assert updated_playbook.etapes[0].id == third_step.id and updated_playbook.etapes[2].id == first_step.id
    assert second_step.id not in {step.id for step in updated_playbook.etapes}
    assert updated_playbook.categorie is None


def test_update_rejects_a_step_from_another_playbook(database_session) -> None:
    playbook = playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())
    other_playbook = playbooks_service.create_playbook(
        database_session, build_synthetic_playbook_request(categorie="autre", nom="Autre")
    )

    with pytest.raises(BusinessRuleViolationError):
        playbooks_service.update_playbook(
            database_session,
            playbook.id,
            PlaybookWriteRequest(
                nom=playbook.nom,
                source=playbook.source,
                etapes=[PlaybookStepWriteRequest(id=other_playbook.etapes[0].id, titre="Volée")],
            ),
        )


def test_deleted_playbook_disappears(database_session) -> None:
    playbook = playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())

    playbooks_service.delete_playbook(database_session, playbook.id)

    with pytest.raises(ResourceNotFoundError):
        playbooks_service.fetch_playbook_detail(database_session, playbook.id)
    page = playbooks_service.list_playbooks(database_session, PlaybookListFilters(), PaginationParameters())
    assert page.total == 0
    with pytest.raises(ResourceNotFoundError):
        playbooks_service.delete_playbook(database_session, playbook.id)



def read_playbook_files() -> dict[str, dict]:
    import json

    from backend.features.playbooks.playbook_files import get_playbook_files_directory

    files = {}
    for file_path in get_playbook_files_directory().glob("*.json"):
        try:
            files[file_path.name] = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # fichier volontairement cassé par un test
    return files


def test_each_playbook_is_a_readable_json_file_kept_in_step_with_the_database(database_session) -> None:
    playbook = playbooks_service.create_playbook(
        database_session,
        build_synthetic_playbook_request(nom="Réponse synthétique — Été", step_count=2),
    )
    created_file = read_playbook_files()["reponse-synthetique-ete.json"]
    assert created_file["id"] == str(playbook.id) and created_file["nom"] == "Réponse synthétique — Été"
    assert [step["id"] for step in created_file["etapes"]] == [str(step.id) for step in playbook.etapes]

    renamed_request = build_synthetic_playbook_request(nom="Nouveau nom synthétique", step_count=1).model_copy(
        update={"description": "ligne 1\nligne 2"}
    )
    playbooks_service.update_playbook(database_session, playbook.id, renamed_request)
    files = read_playbook_files()
    # Renommer le playbook renomme son fichier ; un texte sur plusieurs lignes devient une liste de lignes.
    assert list(files) == ["nouveau-nom-synthetique.json"]
    assert files["nouveau-nom-synthetique.json"]["description"] == ["ligne 1", "ligne 2"]

    playbooks_service.delete_playbook(database_session, playbook.id)
    assert read_playbook_files() == {}


def test_a_file_that_cannot_be_written_leaves_the_database_unchanged(database_session, monkeypatch) -> None:
    from backend.features.playbooks import playbook_files

    def refuse_writing(*_arguments, **_keyword_arguments):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(playbook_files, "write_playbook_file", refuse_writing)

    with pytest.raises(BusinessRuleViolationError, match="fichier"):
        playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())
    assert playbooks_service.find_playbook_id_for_category(database_session, "synthetique_intrusion") is None


def test_synchronization_creates_updates_and_writes_missing_files(database_session) -> None:
    import json

    from backend.features.playbooks.playbook_files import get_playbook_files_directory

    directory = get_playbook_files_directory()
    # Fichier écrit à la main, sans id, avec une description en lignes.
    (directory / "ecrit-a-la-main.json").write_text(
        json.dumps({
            "nom": "Playbook écrit à la main",
            "categorie": "ips",
            "source": "Source synthétique vérifiable",
            "etapes": [{"titre": "Contenir", "description": ["ligne A", "ligne B"]}],
        }),
        encoding="utf-8",
    )
    (directory / "casse.json").write_text("{ pas du json", encoding="utf-8")

    first_report = playbooks_service.synchronize_playbooks_with_files(database_session)

    assert first_report.created == ["Playbook écrit à la main"] and len(first_report.errors) == 1
    assert "casse.json" in first_report.errors[0]
    playbook_id = playbooks_service.find_playbook_id_for_category(database_session, "ips")
    playbook = playbooks_service.fetch_playbook_detail(database_session, playbook_id)
    assert playbook.etapes[0].description == "ligne A\nligne B"
    # Le fichier a été complété avec les id (playbook et étapes) et renommé d'après le nom du playbook.
    completed_file = read_playbook_files()["playbook-ecrit-a-la-main.json"]
    assert completed_file["id"] == str(playbook_id) and completed_file["etapes"][0]["id"] == str(playbook.etapes[0].id)
    assert "ecrit-a-la-main.json" not in read_playbook_files()

    # Modification à la main du fichier : la base suit, l'étape (même id) est conservée.
    completed_file["etapes"][0]["titre"] = "Contenir la menace"
    (directory / "playbook-ecrit-a-la-main.json").write_text(json.dumps(completed_file), encoding="utf-8")
    (directory / "casse.json").unlink()
    second_report = playbooks_service.synchronize_playbooks_with_files(database_session)
    assert second_report.updated == ["Playbook écrit à la main"] and second_report.errors == []
    updated = playbooks_service.fetch_playbook_detail(database_session, playbook_id)
    assert updated.etapes[0].titre == "Contenir la menace" and updated.etapes[0].id == playbook.etapes[0].id

    # Fichier supprimé à la main : le playbook n'est pas supprimé (incidents), son fichier est réécrit.
    (directory / "playbook-ecrit-a-la-main.json").unlink()
    third_report = playbooks_service.synchronize_playbooks_with_files(database_session)
    assert third_report.files_written == ["Playbook écrit à la main"]
    assert "playbook-ecrit-a-la-main.json" in read_playbook_files()
