"""Niveaux de criticité communs aux logs (criticité source) et aux incidents (criticité réévaluée).

Valeurs PROVISOIRES : à confirmer après examen des niveaux réellement fournis par les logs FortiAnalyzer
(voir explain_project.md, section 15). Toute modification nécessite une migration (contrainte CHECK).
"""

from enum import StrEnum


class CriticalityLevel(StrEnum):
    INFORMATION = "information"
    LOW = "faible"
    MEDIUM = "moyenne"
    HIGH = "haute"
    CRITICAL = "critique"


# Rang de gravité, pour comparer deux niveaux (ex. « au moins haute »).
CRITICALITY_RANK = {
    CriticalityLevel.INFORMATION: 0,
    CriticalityLevel.LOW: 1,
    CriticalityLevel.MEDIUM: 2,
    CriticalityLevel.HIGH: 3,
    CriticalityLevel.CRITICAL: 4,
}


def is_at_least_as_severe(criticality: CriticalityLevel, minimum_criticality: CriticalityLevel) -> bool:
    """Vrai si `criticality` est aussi grave ou plus grave que `minimum_criticality`."""
    return CRITICALITY_RANK[criticality] >= CRITICALITY_RANK[minimum_criticality]


def build_allowed_values_sql_list(allowed_values: type[StrEnum]) -> str:
    """Construit `'a', 'b', 'c'` pour les contraintes CHECK (valeurs issues d'un enum, donc sûres)."""
    return ", ".join(f"'{allowed_value.value}'" for allowed_value in allowed_values)

