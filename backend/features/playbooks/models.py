"""Tables `playbooks` et `etapes_playbook` : une procédure de réponse et ses étapes ordonnées."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import DatabaseModelBase, TimestampWithTimezoneColumnType


class Playbook(DatabaseModelBase):
    __tablename__ = "playbooks"
    __table_args__ = (
        CheckConstraint("nom <> ''", name="nom_not_blank"),
        # Règle du projet : une procédure de réponse cite TOUJOURS sa source (doc officielle, procédure interne validée).
        CheckConstraint("source <> ''", name="source_not_blank"),
        CheckConstraint("categorie IS NULL OR categorie <> ''", name="categorie_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    nom: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    # Catégorie d'incident traitée par ce playbook. UNIQUE (plusieurs NULL permis) : à la création d'un incident, le
    # playbook de sa catégorie lui est proposé automatiquement, il ne doit donc y en avoir qu'un par catégorie.
    categorie: Mapped[str | None] = mapped_column(String(255), unique=True)
    source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TimestampWithTimezoneColumnType, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TimestampWithTimezoneColumnType, server_default=func.now(), onupdate=func.now()
    )

    etapes: Mapped[list["PlaybookStep"]] = relationship(
        back_populates="playbook", cascade="all, delete-orphan", order_by="PlaybookStep.ordre", passive_deletes=True
    )


class PlaybookStep(DatabaseModelBase):
    __tablename__ = "etapes_playbook"
    __table_args__ = (
        UniqueConstraint("playbook_id", "ordre", name="uq_etapes_playbook_playbook_id_ordre"),
        CheckConstraint("ordre >= 1", name="ordre_positive"),
        CheckConstraint("titre <> ''", name="titre_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # CASCADE : supprimer un playbook supprime ses étapes (et, par cascade, leur suivi dans les incidents).
    playbook_id: Mapped[UUID] = mapped_column(ForeignKey("playbooks.id", ondelete="CASCADE"))
    # Position de l'étape (1, 2, 3...), sans trou : recalculée par le service à chaque enregistrement.
    ordre: Mapped[int] = mapped_column(Integer)
    titre: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    playbook: Mapped[Playbook] = relationship(back_populates="etapes")
