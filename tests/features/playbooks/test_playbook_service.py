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
