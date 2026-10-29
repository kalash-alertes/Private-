"""Tests du nettoyage des messages d'erreur d'import (aucun secret ne doit être enregistré)."""

import pytest

from backend.features.import_runs.error_message_sanitizer import (
    MAXIMUM_IMPORT_ERROR_MESSAGE_LENGTH,
    build_import_error_message_from_exception,
    sanitize_import_error_message,
)


@pytest.mark.parametrize(
    ("raw_error_message", "secret_value"),
    [
        ("connexion https://utilisateur:SecretSynthetique1@hote.invalide/api refusée", "SecretSynthetique1"),
        ("401 avec Authorization: Bearer jeton.synthetique.xyz", "jeton.synthetique.xyz"),
        ("échec password=MotDePasseSynthetique&user=x", "MotDePasseSynthetique"),
        ('réponse {"session": "SessionSynthetique123", "code": -11}', "SessionSynthetique123"),
        ("paramètre api_key: CleSynthetique456 invalide", "CleSynthetique456"),
    ],
)
def test_known_secret_patterns_are_redacted(raw_error_message, secret_value) -> None:
    sanitized_message = sanitize_import_error_message(raw_error_message)

    assert secret_value not in sanitized_message
    assert "***" in sanitized_message


def test_message_without_secret_is_kept_intact() -> None:
    assert sanitize_import_error_message("  Délai dépassé après 30 s  ") == "Délai dépassé après 30 s"


def test_long_message_is_truncated() -> None:
    sanitized_message = sanitize_import_error_message("x" * (MAXIMUM_IMPORT_ERROR_MESSAGE_LENGTH * 2))

    assert len(sanitized_message) <= MAXIMUM_IMPORT_ERROR_MESSAGE_LENGTH
    assert sanitized_message.endswith("[...tronqué]")


def test_exception_message_includes_its_type_and_is_sanitized() -> None:
    message = build_import_error_message_from_exception(ConnectionError("échec token=abc-synthetique"))

    assert message.startswith("ConnectionError: ")
    assert "abc-synthetique" not in message
    assert build_import_error_message_from_exception(TimeoutError()) == "TimeoutError"
