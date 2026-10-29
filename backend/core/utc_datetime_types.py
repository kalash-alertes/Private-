"""Types de dates garantissant le stockage et l'exposition en UTC.

- `AwareUtcDatetimeInput` : pour les données entrantes. Refuse une date sans fuseau horaire (ambiguë), puis convertit
  en UTC. Indispensable car SQLite (tests) ne conserve pas le fuseau : tout doit déjà être en UTC avant écriture.
- `StoredUtcDatetime` : pour les données sortantes. Une date relue sans fuseau (cas de SQLite) est interprétée comme UTC,
  puisque tout est stocké en UTC ; l'API expose donc toujours des dates avec fuseau.
"""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime


def convert_datetime_to_utc(aware_datetime: datetime) -> datetime:
    """Convertit une date avec fuseau en UTC."""
    return aware_datetime.astimezone(UTC)


def interpret_stored_datetime_as_utc(stored_datetime: datetime) -> datetime:
    """Ajoute le fuseau UTC à une date relue sans fuseau ; convertit en UTC sinon."""
    if stored_datetime.tzinfo is None:
        return stored_datetime.replace(tzinfo=UTC)
    return stored_datetime.astimezone(UTC)


AwareUtcDatetimeInput = Annotated[AwareDatetime, AfterValidator(convert_datetime_to_utc)]
StoredUtcDatetime = Annotated[datetime, AfterValidator(interpret_stored_datetime_as_utc)]
