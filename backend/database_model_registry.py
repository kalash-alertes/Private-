"""Importe tous les modèles de tables pour qu'Alembic et les tests voient le schéma complet.

À chaque nouvelle fonctionnalité qui ajoute une table : ajouter son import ici.
"""

from backend.core.database import DatabaseModelBase
from backend.features.audit_journal.models import AuditEvent  # noqa: F401
from backend.features.import_runs.models import ImportRun  # noqa: F401
from backend.features.incident_response_settings.models import IncidentResponseDeadlineRule  # noqa: F401
from backend.features.incidents.models import Incident, IncidentPlaybookStepCompletion  # noqa: F401
from backend.features.playbooks.models import Playbook, PlaybookStep  # noqa: F401
from backend.features.source_logs.models import SourceLog  # noqa: F401

__all__ = ["DatabaseModelBase"]
