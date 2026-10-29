"""Tests du service `import_runs` : démarrage, fin (réussie / partielle / échouée), cohérence et conflits."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.core.domain_errors import ResourceConflictError, ResourceNotFoundError
from backend.core.pagination import PaginationParameters
from backend.features.import_runs import service as import_runs_service
from backend.features.import_runs.models import ImportRunStatus
from backend.features.import_runs.schemas import ImportRunFinishedOutcome, ImportRunListFilters


def build_finished_outcome(**outcome_values) -> ImportRunFinishedOutcome:
    default_values = {"statut": "reussie", "nb_logs_recus": 3, "nb_logs_inseres": 2, "nb_logs_ignores": 1}
    return ImportRunFinishedOutcome(**(default_values | outcome_values))


def test_started_import_run_is_in_progress_without_end_date(database_session) -> None:
    import_run = import_runs_service.start_import_run(database_session)

    assert import_run.statut == ImportRunStatus.IN_PROGRESS
    assert import_run.fin is None
    assert (import_run.nb_logs_recus, import_run.nb_logs_inseres, import_run.nb_logs_ignores) == (0, 0, 0)
    assert import_run.debut.tzinfo is not None


def test_succeeded_import_run_keeps_counters_cursor_and_end_date(database_session) -> None:
    started_import_run = import_runs_service.start_import_run(database_session)

    finished_import_run = import_runs_service.finish_import_run(
        database_session,
        started_import_run.id,
        build_finished_outcome(curseur_synchronisation="curseur-synthetique-42"),
    )

    assert finished_import_run.statut == ImportRunStatus.SUCCEEDED
    assert (finished_import_run.nb_logs_recus, finished_import_run.nb_logs_inseres) == (3, 2)
    assert finished_import_run.nb_logs_ignores == 1
    assert finished_import_run.erreur is None
    assert finished_import_run.curseur_synchronisation == "curseur-synthetique-42"
    assert finished_import_run.fin is not None
    assert finished_import_run.fin >= finished_import_run.debut


def test_partially_succeeded_import_run_stores_a_sanitized_error(database_session) -> None:
    started_import_run = import_runs_service.start_import_run(database_session)

    finished_import_run = import_runs_service.finish_import_run(
        database_session,
        started_import_run.id,
        build_finished_outcome(
            statut="partielle",
            nb_logs_recus=5,
            nb_logs_inseres=2,
            nb_logs_ignores=1,
            erreur="2 logs rejetés ; requête https://admin:motdepasse-synthetique@hote.invalide/api?token=abc123",
        ),
    )

    assert finished_import_run.statut == ImportRunStatus.PARTIALLY_SUCCEEDED
    assert "motdepasse-synthetique" not in finished_import_run.erreur
    assert "abc123" not in finished_import_run.erreur
    assert finished_import_run.erreur.startswith("2 logs rejetés")


def test_failed_import_run_can_have_no_processed_logs(database_session) -> None:
    started_import_run = import_runs_service.start_import_run(database_session)

    finished_import_run = import_runs_service.finish_import_run(
        database_session,
        started_import_run.id,
        build_finished_outcome(
            statut="echouee", nb_logs_recus=0, nb_logs_inseres=0, nb_logs_ignores=0, erreur="TimeoutError: délai dépassé"
        ),
    )

    assert finished_import_run.statut == ImportRunStatus.FAILED
    assert finished_import_run.erreur == "TimeoutError: délai dépassé"


@pytest.mark.parametrize(
    "invalid_outcome_values",
    [
        pytest.param({"statut": "echouee", "erreur": None}, id="echec_sans_erreur"),
        pytest.param({"statut": "partielle", "erreur": "   "}, id="partielle_avec_erreur_vide"),
        pytest.param({"statut": "reussie", "erreur": "inattendu"}, id="reussite_avec_erreur"),
        pytest.param({"statut": "reussie", "nb_logs_recus": 4}, id="reussite_avec_logs_rejetes"),
        pytest.param({"nb_logs_recus": 1}, id="traites_superieurs_aux_recus"),
        pytest.param({"nb_logs_inseres": -1}, id="compteur_negatif"),
        pytest.param({"statut": "en_cours"}, id="statut_final_en_cours"),
        pytest.param({"compteur_inconnu": 1}, id="champ_inconnu"),
    ],
)
def test_inconsistent_finished_outcome_is_rejected(invalid_outcome_values) -> None:
    with pytest.raises(ValidationError):
        build_finished_outcome(**invalid_outcome_values)


def test_finished_import_run_cannot_be_finished_again(database_session) -> None:
    started_import_run = import_runs_service.start_import_run(database_session)
    import_runs_service.finish_import_run(database_session, started_import_run.id, build_finished_outcome())

    with pytest.raises(ResourceConflictError):
        import_runs_service.finish_import_run(
            database_session, started_import_run.id, build_finished_outcome(statut="echouee", erreur="tardif")
        )

    assert import_runs_service.fetch_import_run(database_session, started_import_run.id).statut == "reussie"


def test_finishing_unknown_import_run_raises_not_found(database_session) -> None:
    with pytest.raises(ResourceNotFoundError):
        import_runs_service.finish_import_run(database_session, uuid4(), build_finished_outcome())


def test_finished_import_run_no_longer_accepts_new_logs(database_session) -> None:
    started_import_run = import_runs_service.start_import_run(database_session)
    import_runs_service.ensure_import_run_accepts_new_logs(database_session, started_import_run.id)
    import_runs_service.finish_import_run(database_session, started_import_run.id, build_finished_outcome())

    with pytest.raises(ResourceConflictError):
        import_runs_service.ensure_import_run_accepts_new_logs(database_session, started_import_run.id)
    with pytest.raises(ResourceNotFoundError):
        import_runs_service.ensure_import_run_accepts_new_logs(database_session, uuid4())


def test_import_runs_list_is_paginated_and_filterable_by_status(database_session) -> None:
    started_import_run_ids = [import_runs_service.start_import_run(database_session).id for _ in range(5)]
    import_runs_service.finish_import_run(database_session, started_import_run_ids[0], build_finished_outcome())

    first_page = import_runs_service.list_import_runs(
        database_session, ImportRunListFilters(), PaginationParameters(limit=2, offset=0)
    )
    remaining_page = import_runs_service.list_import_runs(
        database_session, ImportRunListFilters(), PaginationParameters(limit=10, offset=2)
    )
    succeeded_only = import_runs_service.list_import_runs(
        database_session, ImportRunListFilters(statut="reussie"), PaginationParameters()
    )

    assert first_page.total == 5 and len(first_page.items) == 2
    listed_ids = {item.id for item in first_page.items} | {item.id for item in remaining_page.items}
    assert listed_ids == set(started_import_run_ids)
    assert [item.id for item in succeeded_only.items] == [started_import_run_ids[0]]
