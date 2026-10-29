"""Aides à la lecture des formulaires HTML et à la présentation des erreurs de validation.

Un champ de formulaire vide arrive sous forme de chaîne vide : on le convertit en None pour que la validation
Pydantic des services (champ facultatif) s'applique comme pour l'API JSON.
"""

from pydantic import ValidationError

from backend.core.domain_errors import DomainError


def convert_blank_to_none(form_value: str | None) -> str | None:
    """`""` ou espaces seuls → None ; sinon la valeur telle quelle (les schémas retirent les espaces)."""
    if form_value is None or not form_value.strip():
        return None
    return form_value


def describe_action_error(action_error: Exception) -> str:
    """Message lisible pour une erreur métier ou de validation (sans recopier les valeurs saisies)."""
    if isinstance(action_error, DomainError):
        return action_error.message
    if isinstance(action_error, ValidationError):
        error_messages = []
        for validation_error in action_error.errors(include_url=False, include_input=False, include_context=False):
            field_path = ".".join(str(location) for location in validation_error["loc"])
            error_messages.append(f"{field_path} : {validation_error['msg']}" if field_path else validation_error["msg"])
        return "Données invalides — " + " ; ".join(error_messages)
    raise action_error
