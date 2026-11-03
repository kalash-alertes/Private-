"""Écrit un fichier JSON par fiche IRM publique dans `db/playbooks/` (outil de développement).

Source : « Incident Response Methodologies » (IRM) du CERT Société Générale, traduites en français et mises à jour
par le CERT aDvens, licence Creative Commons Attribution 3.0 (CC BY 3.0) :
    https://github.com/certsocietegenerale/IRM   (original, anglais)
    https://github.com/cert-advens/IRM           (version française utilisée ici)
La licence permet de reproduire et d'adapter, à condition de citer l'auteur, la licence, et d'indiquer les
modifications : la `source` de chaque playbook le fait.

Fonctionnement :
1. liste les fiches françaises par l'API GitHub (`/repos/cert-advens/IRM/contents/FR`), télécharge celles de
   `SELECTED_IRM_SHEETS` (ou les lit dans `--pdf-directory`, utile hors ligne) ;
2. extrait le texte (PyMuPDF), retire en-têtes, pieds de page et sommaire, puis découpe la fiche selon ses phases
   (Préparation, Identification, Confinement, Remédiation, Récupération, Capitalisation ; titres repris de la fiche) :
   une phase = une étape.
   Une phase trop longue pour une étape (MAXIMUM_STEP_DESCRIPTION_CHARACTERS) est coupée à ses sous-titres ;
3. écrit UN fichier par playbook dans `db/playbooks/` (format de `backend/features/playbooks/playbook_files.py`),
   en gardant l'`id` du playbook et de ses étapes si le fichier existe déjà (le suivi des incidents est préservé) ;
   la base est mise à jour au prochain démarrage, ou par « Synchroniser avec les fichiers » (page Playbooks).

Le texte n'est PAS réécrit : seule la mise en forme change (lignes recollées, puces). Relancer le script après une
mise à jour des fiches, relire le diff des JSON, puis synchroniser.

Usage (PyMuPDF n'est requis que pour cet outil, pas par l'application) :
    pip install pymupdf
    python -m scripts.build_reference_playbooks_from_cert_irm [--pdf-directory DOSSIER]
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from backend.features.playbooks.playbook_file_names import build_playbook_file_name

IRM_FRENCH_DIRECTORY_API_URL = "https://api.github.com/repos/cert-advens/IRM/contents/FR"
IRM_FRENCH_REPOSITORY_URL = "https://github.com/cert-advens/IRM"
IRM_ORIGINAL_REPOSITORY_URL = "https://github.com/certsocietegenerale/IRM"
CC_BY_3_LICENSE_URL = "https://creativecommons.org/licenses/by/3.0/"
PLAYBOOK_FILES_DIRECTORY = Path(__file__).resolve().parent.parent / "db" / "playbooks"
DOWNLOAD_ATTEMPTS = 5
# Limite d'une description d'étape côté application (playbooks/schemas.py : 10 000), avec une marge.
MAXIMUM_STEP_DESCRIPTION_CHARACTERS = 9_500

# Numéro de fiche -> catégorie d'incident de l'application. La catégorie sert à proposer automatiquement le playbook
# aux incidents de cette catégorie : quand un sous-type de log FortiGate correspond clairement (virus = antivirus,
# ips = prévention d'intrusion, anomaly = politiques anti-DoS, dlp = fuite de données), il est utilisé tel quel.
SELECTED_IRM_SHEETS = {
    "01": "ver",
    "02": "intrusion_windows",
    "03": "intrusion_linux",
    "04": "anomaly",
    "05": "ips",
    "06": "defacement",
    "07": "virus",
    "11": "dlp",
    "16": "phishing",
    "17": "ransomware",
    "18": "compromission_large_perimetre",
    "22": "compromission_messagerie",
}

# Titre de phase dans le corps de la fiche : « 2. IDENTIFICATION » ou « 4. REMÉDIATION (EXTERNE) » (en capitales,
# seul sur sa ligne). Les fiches suivent les 6 phases du NIST, mais certaines les subdivisent (IRM-22).
PHASE_HEADING_REGEX = re.compile(r"^([1-9])\.\s+([A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ'() ]{5,})$")
SUBHEADING_REGEX = re.compile(r"^\d\.\d+(\.\d+)?\.\s+\S")
PAGE_DECORATION_REGEXES = (
    re.compile(r"^IRM-\d+$"),
    re.compile(r"^CERT aDvens - CSIRT"),
    re.compile(r"^\d+ / \d+$"),
)
# Ligne courte sans ponctuation finale : un intertitre (« Le rapport d'incident »), pas une phrase coupée.
MAXIMUM_INLINE_HEADING_CHARACTERS = 60
SHEET_DATE_REGEX = re.compile(r"(\d{4}-\d{2}-\d{2}) \| IRM-(\d+)")
BULLET_PREFIXES = ("→", "-", "•", "*")
PRIVATE_USE_CHARACTERS_REGEX = re.compile(r"[-]")


def download_bytes(url: str) -> bytes:
    """Télécharge `url` (plusieurs essais : le réseau du poste est parfois instable). Lève la dernière erreur."""
    last_error: Exception | None = None
    for attempt_number in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "intelligentsia-soc-playbook-builder"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except OSError as download_error:
            last_error = download_error
            time.sleep(attempt_number * 2)
    raise last_error


def fetch_selected_irm_pdfs(pdf_directory: Path | None) -> dict[str, tuple[str, bytes]]:
    """Retourne {numéro de fiche: (nom du fichier, contenu PDF)} pour les fiches de SELECTED_IRM_SHEETS."""
    if pdf_directory is not None:
        pdf_paths = sorted(pdf_directory.glob("IRM-*.pdf"))
        named_contents = [(pdf_path.name, pdf_path.read_bytes) for pdf_path in pdf_paths]
    else:
        directory_listing = json.loads(download_bytes(IRM_FRENCH_DIRECTORY_API_URL))
        named_contents = [
            (entry["name"], lambda url=entry["download_url"]: download_bytes(url))
            for entry in directory_listing
            if entry["name"].endswith(".pdf")
        ]
    selected_pdfs = {}
    for file_name, read_content in named_contents:
        sheet_number = re.match(r"IRM-(\d+)", file_name).group(1).zfill(2)
        if sheet_number in SELECTED_IRM_SHEETS:
            selected_pdfs[sheet_number] = (file_name, read_content())
    missing_sheets = sorted(set(SELECTED_IRM_SHEETS) - set(selected_pdfs))
    if missing_sheets:
        raise SystemExit(f"Fiches introuvables : IRM-{', IRM-'.join(missing_sheets)}")
    return selected_pdfs


def extract_text_lines(pdf_content: bytes) -> list[str]:
    import pymupdf  # Import tardif : dépendance de cet outil seulement.

    with pymupdf.open(stream=pdf_content, filetype="pdf") as pdf_document:
        page_texts = [page.get_text() for page in pdf_document]
    # Les pictogrammes du PDF (avertissement...) sont des caractères « à usage privé » sans sens hors de leur police.
    return [
        " ".join(PRIVATE_USE_CHARACTERS_REGEX.sub("", line).split())
        for page_text in page_texts
        for line in page_text.splitlines()
    ]


def build_playbook_from_irm(sheet_number: str, file_name: str, pdf_content: bytes) -> dict:
    """Transforme une fiche en playbook : {nom, description, categorie, source, etapes: [{titre, description}]}."""
    text_lines = extract_text_lines(pdf_content)
    # Le titre peut tenir sur plusieurs lignes, toujours suivies de « Méthodologie de réponse à incident ».
    method_line_index = next(index for index, line in enumerate(text_lines) if line.startswith("Méthodologie de réponse"))
    sheet_title = " ".join(text_lines[:method_line_index])
    date_match = next((SHEET_DATE_REGEX.search(line) for line in text_lines[:8] if SHEET_DATE_REGEX.search(line)), None)
    sheet_date = date_match.group(1) if date_match else "date inconnue"
    # En-têtes et pieds de chaque page : « IRM-07 », le titre, « CERT aDvens - CSIRT | TLP-CLEAR | date », « 3 / 9 ».
    body_lines = [
        line for line in text_lines
        if line and line != sheet_title and not any(regex.match(line) for regex in PAGE_DECORATION_REGEXES)
    ]

    phases: list[tuple[str, list[str]]] = []
    for line in body_lines:
        heading_match = PHASE_HEADING_REGEX.match(line)
        # Le sommaire contient aussi « 1. Préparation » mais en minuscules et suivi de points : seul le corps matche.
        if heading_match:
            phases.append((heading_match.group(2).strip().capitalize(), []))
        elif phases:
            phases[-1][1].append(line)
    if len(phases) < 4:
        raise SystemExit(f"{file_name} : phases non reconnues {[title for title, _ in phases]}")

    steps = []
    for phase_title, phase_lines in phases:
        phase_text = join_wrapped_lines(phase_lines)
        phase_parts = split_long_phase(phase_text)
        for part_index, part_text in enumerate(phase_parts, start=1):
            part_count = len(phase_parts)
            step_title = phase_title + (f" ({part_index}/{part_count})" if part_count > 1 else "")
            steps.append({"titre": step_title, "description": part_text})

    sheet_label = f"IRM-{int(sheet_number):02d}"
    return {
        "nom": f"{sheet_label} — {sheet_title}",
        "description": (
            f"Méthodologie de réponse à incident « {sheet_title} » ({sheet_label}, version du {sheet_date}) : "
            "phases issues du NIST (préparation, identification, confinement, remédiation, récupération, "
            "capitalisation). À adapter au contexte de l'organisation avant usage."
        ),
        "categorie": SELECTED_IRM_SHEETS[sheet_number],
        "source": (
            f"CERT aDvens, d'après les fiches IRM du CERT Société Générale — {sheet_label} « {sheet_title} », "
            f"version du {sheet_date}. Fichier : {IRM_FRENCH_REPOSITORY_URL}/blob/HEAD/FR/{file_name} "
            f"(original : {IRM_ORIGINAL_REPOSITORY_URL}). Licence Creative Commons Attribution 3.0 ({CC_BY_3_LICENSE_URL}). "
            "Modifications : texte extrait du PDF et découpé par phase, mise en forme adaptée ; contenu non réécrit."
        ),
        "etapes": steps,
    }


def join_wrapped_lines(phase_lines: list[str]) -> str:
    """Recolle les lignes coupées par la mise en page ; garde les puces, sous-titres et objectifs sur leur ligne."""
    paragraphs: list[str] = []
    for line in phase_lines:
        starts_new_paragraph = (
            not paragraphs
            or line.startswith(BULLET_PREFIXES)
            or SUBHEADING_REGEX.match(line)
            or line.startswith("Objectif")
            or SUBHEADING_REGEX.match(paragraphs[-1])
            or paragraphs[-1].endswith((":", "."))
            or (
                len(paragraphs[-1]) <= MAXIMUM_INLINE_HEADING_CHARACTERS
                and not paragraphs[-1].startswith(BULLET_PREFIXES)
                and not paragraphs[-1].endswith((",", ";"))
                and line[:1].isupper()
            )
        )
        if starts_new_paragraph:
            paragraphs.append("• " + line[1:].strip() if line.startswith("→") else line)
        else:
            paragraphs[-1] = f"{paragraphs[-1]} {line}"
    return "\n".join(re.sub(r"\s{2,}", " ", paragraph).strip() for paragraph in paragraphs).strip()


def split_long_phase(phase_text: str) -> list[str]:
    """Coupe une phase trop longue à ses sous-titres (« 2.3. ... ») pour respecter la limite d'une étape."""
    if len(phase_text) <= MAXIMUM_STEP_DESCRIPTION_CHARACTERS:
        return [phase_text]
    parts, current_lines = [], []
    for line in phase_text.splitlines():
        current_length = sum(len(current_line) + 1 for current_line in current_lines)
        if current_lines and current_length + len(line) > MAXIMUM_STEP_DESCRIPTION_CHARACTERS and (
            SUBHEADING_REGEX.match(line) or current_length > MAXIMUM_STEP_DESCRIPTION_CHARACTERS * 0.9
        ):
            parts.append("\n".join(current_lines))
            current_lines = []
        current_lines.append(line)
    parts.append("\n".join(current_lines))
    return parts


def main() -> None:
    argument_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argument_parser.add_argument("--pdf-directory", type=Path, help="Lire les PDF dans ce dossier au lieu de GitHub.")
    arguments = argument_parser.parse_args()
    selected_pdfs = fetch_selected_irm_pdfs(arguments.pdf_directory)
    playbooks = [
        build_playbook_from_irm(sheet_number, file_name, pdf_content)
        for sheet_number, (file_name, pdf_content) in sorted(selected_pdfs.items())
    ]
    PLAYBOOK_FILES_DIRECTORY.mkdir(parents=True, exist_ok=True)
    existing_files_by_name = read_existing_playbook_files_by_name()
    for playbook in playbooks:
        existing_path, existing_content = existing_files_by_name.get(playbook["nom"], (None, {}))
        playbook_file = build_playbook_file_content(playbook, existing_content)
        target_path = PLAYBOOK_FILES_DIRECTORY / build_playbook_file_name(playbook["nom"])
        target_path.write_text(json.dumps(playbook_file, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if existing_path is not None and existing_path != target_path:
            existing_path.unlink()
        print(f"{target_path.name} : {len(playbook['etapes'])} étape(s)", file=sys.stderr)


def read_existing_playbook_files_by_name() -> dict[str, tuple[Path, dict]]:
    """{nom du playbook: (fichier, contenu)} pour les fichiers déjà présents (fichiers illisibles ignorés)."""
    existing_files = {}
    for file_path in PLAYBOOK_FILES_DIRECTORY.glob("*.json"):
        try:
            content = json.loads(file_path.read_text(encoding="utf-8"))
            existing_files[content["nom"]] = (file_path, content)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return existing_files


def build_playbook_file_content(playbook: dict, existing_content: dict) -> dict:
    """Même format que l'application (textes sur plusieurs lignes en listes) ; garde les id existants : celui du
    playbook, et celui de chaque étape dont le titre n'a pas changé."""
    existing_step_ids = {step.get("titre"): step.get("id") for step in existing_content.get("etapes", [])}
    file_content = {"id": existing_content["id"]} if existing_content.get("id") else {}
    file_content.update(
        {
            "nom": playbook["nom"],
            "categorie": playbook["categorie"],
            "description": split_lines(playbook["description"]),
            "source": split_lines(playbook["source"]),
            "etapes": [
                ({"id": existing_step_ids[step["titre"]]} if existing_step_ids.get(step["titre"]) else {})
                | {"titre": step["titre"], "description": split_lines(step["description"])}
                for step in playbook["etapes"]
            ],
        }
    )
    return file_content


def split_lines(text: str | None) -> str | list[str] | None:
    """Texte sur plusieurs lignes → liste de lignes (même règle que l'application)."""
    return text.split("\n") if text and "\n" in text else text


if __name__ == "__main__":
    main()
