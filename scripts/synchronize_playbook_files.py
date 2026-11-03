"""Synchronise la base avec les fichiers JSON des playbooks (`db/playbooks/`, un fichier lisible par playbook).

Usage (base désignée par DATABASE_URL, déjà migrée) :
    python -m scripts.synchronize_playbook_files
ou, dans le conteneur : wsl docker compose exec backend python -m scripts.synchronize_playbook_files
Même effet que le bouton « Synchroniser avec les fichiers » de la page Playbooks (et que le démarrage de l'application).
"""

from backend.core.database import get_database_session_factory
from backend.features.playbooks import service as playbooks_service


def main() -> None:
    with get_database_session_factory()() as database_session:
        report = playbooks_service.synchronize_playbooks_with_files(database_session)
    print(
        f"{len(report.created)} créé(s), {len(report.updated)} mis à jour, {len(report.unchanged)} inchangé(s), "
        f"{len(report.files_written)} fichier(s) écrit(s) depuis la base, {len(report.errors)} refusé(s)."
    )
    for error_message in report.errors:
        print(f"  ! {error_message}")


if __name__ == "__main__":
    main()
