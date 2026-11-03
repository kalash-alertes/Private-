"""Fichiers JSON des playbooks (`PLAYBOOK_FILES_DIRECTORY`, par défaut `db/playbooks/`) : UN fichier lisible par playbook.

Décision (demande de l'équipe, 03/11/2026) : les playbooks sont des fichiers JSON clairs, consultables et versionnables ;
la base en est l'INDEX (recherche, lien avec les incidents, suivi des étapes cochées). Toute création, modification ou
suppression faite dans l'interface écrit le fichier ET la base (`service.py`) ; au démarrage, la synchronisation
(`service.synchronize_playbooks_with_files`) enregistre en base les fichiers ajoutés ou modifiés à la main.

Format d'un fichier (les clés suivent le vocabulaire de la base) :

    {
      "id": "…uuid…",                 # absent dans un nouveau fichier écrit à la main : ajouté à la synchronisation
      "nom": "IRM-07 — Malware sous Windows",
      "categorie": "virus",             # ou null
      "description": "…",               # texte, ou liste de lignes pour un texte sur plusieurs lignes
      "source": "…",                    # obligatoire : référence vérifiable
      "etapes": [
        {"id": "…uuid…", "titre": "Préparation", "description": ["ligne 1", "ligne 2"]}
      ]
    }

L'ordre des étapes est celui de la liste. L'`id` d'une étape préserve son suivi (« réalisée ») dans les incidents.
Écriture atomique (fichier temporaire puis remplacement) : un fichier n'est jamais à moitié écrit.
"""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

from backend.core.settings import get_application_settings
from backend.features.playbooks.playbook_file_names import PLAYBOOK_FILE_EXTENSION, build_playbook_file_name
from backend.features.playbooks.schemas import PlaybookStepWriteRequest, PlaybookWriteRequest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FILE_ENCODING = "utf-8"

MultilineText = str | list[str]


class PlaybookFileStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    titre: str
    description: MultilineText | None = None


class PlaybookFile(BaseModel):
    """Contenu d'un fichier de playbook, tel qu'écrit sur disque."""

    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    nom: str
    categorie: str | None = None
    description: MultilineText | None = None
    source: MultilineText
    etapes: list[PlaybookFileStep]

    def to_write_request(self) -> PlaybookWriteRequest:
        """Convertit en demande d'enregistrement (mêmes validations que l'interface). Lève ValidationError."""
        return PlaybookWriteRequest(
            nom=self.nom,
            description=_join_lines(self.description),
            categorie=self.categorie,
            source=_join_lines(self.source),
            etapes=[
                PlaybookStepWriteRequest(id=step.id, titre=step.titre, description=_join_lines(step.description))
                for step in self.etapes
            ],
        )


@dataclass(frozen=True)
class PlaybookFileReading:
    """Un fichier lu : son contenu, ou le motif pour lequel il est illisible."""

    path: Path
    content: PlaybookFile | None
    error: str | None


@dataclass(frozen=True)
class PreviousFileState:
    """État d'un fichier avant une écriture, pour l'annuler si la base refuse la modification."""

    path: Path
    previous_bytes: bytes | None


def get_playbook_files_directory() -> Path:
    """Dossier des fichiers (relatif à la racine du projet s'il n'est pas absolu), créé au besoin."""
    configured_directory = Path(get_application_settings().playbook_files_directory)
    directory = configured_directory if configured_directory.is_absolute() else PROJECT_ROOT / configured_directory
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_all_playbook_files() -> list[PlaybookFileReading]:
    """Lit tous les `*.json` du dossier (ordre alphabétique). Ne lève pas : un fichier invalide porte son erreur."""
    readings = []
    for file_path in sorted(get_playbook_files_directory().glob(f"*{PLAYBOOK_FILE_EXTENSION}")):
        try:
            content = PlaybookFile.model_validate(json.loads(file_path.read_text(encoding=FILE_ENCODING)))
            readings.append(PlaybookFileReading(file_path, content, None))
        except (OSError, json.JSONDecodeError, ValidationError) as reading_error:
            readings.append(PlaybookFileReading(file_path, None, f"{file_path.name} : {reading_error}"))
    return readings


def build_playbook_file(
    playbook_id: UUID, playbook_request: PlaybookWriteRequest, step_ids: list[UUID]
) -> PlaybookFile:
    """Contenu du fichier d'un playbook enregistré (`step_ids` : id des étapes, dans l'ordre)."""
    return PlaybookFile(
        id=playbook_id,
        nom=playbook_request.nom,
        categorie=playbook_request.categorie,
        description=_split_lines(playbook_request.description),
        source=_split_lines(playbook_request.source),
        etapes=[
            PlaybookFileStep(id=step_id, titre=step.titre, description=_split_lines(step.description))
            for step_id, step in zip(step_ids, playbook_request.etapes, strict=True)
        ],
    )


def write_playbook_file(playbook_file: PlaybookFile, current_path: Path | None = None) -> list[PreviousFileState]:
    """Écrit le fichier sous le nom dérivé du nom du playbook ; supprime l'ancien fichier du même playbook s'il avait
    un autre nom (renommage). Retourne l'état précédent des fichiers touchés (pour `restore_files`)."""
    directory = get_playbook_files_directory()
    target_path = directory / build_playbook_file_name(playbook_file.nom)
    existing_path = current_path or find_playbook_file_path(playbook_file.id)
    if target_path != existing_path and target_path.exists() and _read_file_id(target_path) != playbook_file.id:
        # Deux noms différents donnent le même nom de fichier : l'id raccourci les départage.
        target_path = directory / f"{target_path.stem}-{str(playbook_file.id)[:8]}{PLAYBOOK_FILE_EXTENSION}"
    previous_states = [_capture_state(target_path)]
    file_text = json.dumps(playbook_file.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    _write_atomically(target_path, file_text)
    if existing_path is not None and existing_path != target_path and existing_path.exists():
        previous_states.append(_capture_state(existing_path))
        existing_path.unlink()
    return previous_states


def delete_playbook_file(playbook_id: UUID) -> list[PreviousFileState]:
    """Supprime le fichier du playbook (s'il existe) ; retourne son état précédent (pour `restore_files`)."""
    file_path = find_playbook_file_path(playbook_id)
    if file_path is None:
        return []
    previous_state = _capture_state(file_path)
    file_path.unlink()
    return [previous_state]


def restore_files(previous_states: list[PreviousFileState]) -> None:
    """Remet les fichiers dans leur état précédent (la base a refusé l'opération : fichiers et base restent alignés)."""
    for previous_state in reversed(previous_states):
        if previous_state.previous_bytes is None:
            previous_state.path.unlink(missing_ok=True)
        else:
            previous_state.path.write_bytes(previous_state.previous_bytes)


def find_playbook_file_path(playbook_id: UUID | None) -> Path | None:
    """Fichier dont le champ `id` vaut `playbook_id`, ou None."""
    if playbook_id is None:
        return None
    for file_path in get_playbook_files_directory().glob(f"*{PLAYBOOK_FILE_EXTENSION}"):
        if _read_file_id(file_path) == playbook_id:
            return file_path
    return None


def _read_file_id(file_path: Path) -> UUID | None:
    try:
        file_id = json.loads(file_path.read_text(encoding=FILE_ENCODING)).get("id")
        return UUID(file_id) if file_id else None
    except (OSError, json.JSONDecodeError, ValueError, AttributeError, TypeError):
        return None


def _capture_state(file_path: Path) -> PreviousFileState:
    return PreviousFileState(file_path, file_path.read_bytes() if file_path.exists() else None)


def _write_atomically(target_path: Path, file_text: str) -> None:
    file_descriptor, temporary_path = tempfile.mkstemp(dir=target_path.parent, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(file_descriptor, "w", encoding=FILE_ENCODING, newline="\n") as temporary_file:
            temporary_file.write(file_text)
        os.replace(temporary_path, target_path)
    except BaseException:
        Path(temporary_path).unlink(missing_ok=True)
        raise


def _split_lines(text: str | None) -> MultilineText | None:
    """Texte sur plusieurs lignes → liste de lignes (bien plus lisible dans un JSON que des « \\n »)."""
    if text is None or "\n" not in text:
        return text
    return text.split("\n")


def _join_lines(text: MultilineText | None) -> str | None:
    if isinstance(text, list):
        return "\n".join(text)
    return text
