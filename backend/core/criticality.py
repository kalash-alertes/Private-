"""Niveaux de criticité communs aux logs (criticité source) et aux incidents (criticité réévaluée).

Valeurs PROVISOIRES : à confirmer après examen des niveaux réellement fournis par l'API FortiAnalyzer
(voir explain_project.md, section 15). Toute modification nécessite une migration (contrainte CHECK).
"""

from enum import StrEnum


class CriticalityLevel(StrEnum):
    INFORMATION = "information"
    LOW = "faible"
    MEDIUM = "moyenne"
    HIGH = "haute"
    CRITICAL = "critique"


def build_allowed_values_sql_list(allowed_values: type[StrEnum]) -> str:
    """Construit `'a', 'b', 'c'` pour les contraintes CHECK (valeurs issues d'un enum, donc sûres)."""
    return ", ".join(f"'{allowed_value.value}'" for allowed_value in allowed_values)

