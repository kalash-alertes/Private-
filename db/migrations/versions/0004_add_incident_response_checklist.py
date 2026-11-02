"""add incident-specific suggested response checklist

Revision ID: 0004
Revises: 0003
"""

from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

CHECKLIST_DEFINITIONS = (
    ("documenter_les_faits", "Documenter les faits", "Machine, utilisateur, preuve (alerte, inventaire logiciel)."),
    (
        "faire_cesser_l_usage_non_conforme",
        "Faire cesser l’usage non conforme",
        "Appliquer la mesure validée et préserver les éléments utiles à l’analyse.",
    ),
    (
        "informer_hierarchie_et_ressources_humaines",
        "Informer la hiérarchie et les ressources humaines",
        "Transmettre les faits aux interlocuteurs concernés selon les règles internes.",
    ),
    (
        "preserver_les_preuves",
        "Préserver les preuves",
        "Horodater les éléments collectés et noter leur origine et leurs conditions de conservation.",
    ),
    (
        "evaluer_impact",
        "Évaluer l’impact",
        "Repérer les comptes, équipements, données et services potentiellement concernés.",
    ),
    (
        "definir_actions_correctives",
        "Définir les actions correctives",
        "Noter les mesures autorisées, les responsables et les vérifications attendues.",
    ),
    (
        "verifier_retour_a_la_normale",
        "Vérifier le retour à la normale",
        "Consigner les contrôles réalisés et les risques restant à suivre.",
    ),
)


def upgrade() -> None:
    op.create_table(
        "incident_response_checklist",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.Column("cle", sa.String(length=64), nullable=False),
        sa.Column("titre", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("terminee_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminee_par", sa.String(length=255), nullable=True),
        sa.CheckConstraint("cle <> ''", name=op.f("ck_incident_response_checklist_cle_not_blank")),
        sa.CheckConstraint("titre <> ''", name=op.f("ck_incident_response_checklist_titre_not_blank")),
        sa.CheckConstraint("description <> ''", name=op.f("ck_incident_response_checklist_description_not_blank")),
        sa.CheckConstraint("ordre >= 1", name=op.f("ck_incident_response_checklist_ordre_positive")),
        sa.CheckConstraint(
            "terminee_par IS NULL OR terminee_par <> ''",
            name=op.f("ck_incident_response_checklist_terminee_par_not_blank"),
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", "cle", name="uq_incident_response_checklist_incident_id_cle"),
        sa.UniqueConstraint("incident_id", "ordre", name="uq_incident_response_checklist_incident_id_ordre"),
    )

    checklist_table = sa.table(
        "incident_response_checklist",
        sa.column("id", sa.Uuid()),
        sa.column("incident_id", sa.Uuid()),
        sa.column("ordre", sa.Integer()),
        sa.column("cle", sa.String()),
        sa.column("titre", sa.String()),
        sa.column("description", sa.Text()),
    )
    existing_incident_ids = op.get_bind().execute(sa.text("SELECT id FROM incidents")).scalars()
    for incident_id in existing_incident_ids:
        normalized_incident_id = incident_id if isinstance(incident_id, UUID) else UUID(incident_id)
        op.bulk_insert(
            checklist_table,
            [
                {
                    "id": uuid4(),
                    "incident_id": normalized_incident_id,
                    "ordre": position,
                    "cle": key,
                    "titre": title,
                    "description": description,
                }
                for position, (key, title, description) in enumerate(CHECKLIST_DEFINITIONS, start=1)
            ],
        )


def downgrade() -> None:
    op.drop_table("incident_response_checklist")
