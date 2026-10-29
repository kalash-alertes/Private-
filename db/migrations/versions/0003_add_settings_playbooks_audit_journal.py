"""add settings, playbooks, audit journal and incident tracking fields

Ajoute (cf. docs/technical/database.md) :
- `playbooks` + `etapes_playbook` : procédures de réponse (nom, source obligatoire, étapes ordonnées) ;
- `delais_reponse_incidents` : délai de traitement et escalade automatique par criticité, avec 5 lignes PAR DÉFAUT
  (escalade désactivée) que l'équipe doit ajuster dans Paramètres ;
- `journal_audit` : événements du système ;
- `incidents` : référence séquentielle, titre, catégorie, playbook, date de traitement, date d'escalade ;
- `etapes_realisees_incident` : avancement du playbook pour chaque incident.

Incidents existants : numérotés par date de création ; titre « Alerte <type du log> » ; catégorie = type du log ;
`traite_le` = date de clôture (ou, à défaut, dernière mise à jour) pour les incidents résolus ou clôturés.

Revision ID: 0003
Revises: 0002
"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

# Valeurs de départ à ajuster par l'équipe (Paramètres > Réponse aux incidents) ; ce ne sont pas des normes.
DEFAULT_PROCESSING_DELAY_MINUTES_BY_CRITICALITY = {
    'critique': 60,
    'haute': 4 * 60,
    'moyenne': 24 * 60,
    'faible': 72 * 60,
    'information': 7 * 24 * 60,
}


def upgrade() -> None:
    op.create_table('playbooks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('nom', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('categorie', sa.String(length=255), nullable=True),
    sa.Column('source', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("nom <> ''", name=op.f('ck_playbooks_nom_not_blank')),
    sa.CheckConstraint("source <> ''", name=op.f('ck_playbooks_source_not_blank')),
    sa.CheckConstraint("categorie IS NULL OR categorie <> ''", name=op.f('ck_playbooks_categorie_not_blank')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_playbooks')),
    sa.UniqueConstraint('nom', name=op.f('uq_playbooks_nom')),
    sa.UniqueConstraint('categorie', name=op.f('uq_playbooks_categorie'))
    )
    op.create_table('etapes_playbook',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('playbook_id', sa.Uuid(), nullable=False),
    sa.Column('ordre', sa.Integer(), nullable=False),
    sa.Column('titre', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.CheckConstraint('ordre >= 1', name=op.f('ck_etapes_playbook_ordre_positive')),
    sa.CheckConstraint("titre <> ''", name=op.f('ck_etapes_playbook_titre_not_blank')),
    sa.ForeignKeyConstraint(['playbook_id'], ['playbooks.id'], name=op.f('fk_etapes_playbook_playbook_id_playbooks'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_etapes_playbook')),
    sa.UniqueConstraint('playbook_id', 'ordre', name='uq_etapes_playbook_playbook_id_ordre')
    )

    response_deadline_rules_table = op.create_table('delais_reponse_incidents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('criticite', sa.String(length=32), nullable=False),
    sa.Column('delai_traitement_minutes', sa.Integer(), nullable=False),
    sa.Column('escalade_automatique_activee', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('escalader_vers', sa.String(length=255), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("criticite IN ('information', 'faible', 'moyenne', 'haute', 'critique')", name=op.f('ck_delais_reponse_incidents_criticite_allowed_values')),
    sa.CheckConstraint('delai_traitement_minutes > 0', name=op.f('ck_delais_reponse_incidents_delai_traitement_minutes_positive')),
    sa.CheckConstraint("escalader_vers IS NULL OR escalader_vers <> ''", name=op.f('ck_delais_reponse_incidents_escalader_vers_not_blank')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_delais_reponse_incidents')),
    sa.UniqueConstraint('criticite', name=op.f('uq_delais_reponse_incidents_criticite'))
    )
    op.bulk_insert(
        response_deadline_rules_table,
        [
            {'id': uuid4(), 'criticite': criticite, 'delai_traitement_minutes': delay_minutes, 'escalade_automatique_activee': False}
            for criticite, delay_minutes in DEFAULT_PROCESSING_DELAY_MINUTES_BY_CRITICALITY.items()
        ],
    )

    op.create_table('journal_audit',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('date_evenement', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('type_evenement', sa.String(length=64), nullable=False),
    sa.Column('acteur', sa.String(length=255), nullable=True),
    sa.Column('type_ressource', sa.String(length=64), nullable=True),
    sa.Column('identifiant_ressource', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('details', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('adresse_ip', sa.String(length=64), nullable=True),
    sa.CheckConstraint(
        "type_evenement IN ('connexion_reussie', 'connexion_echouee', 'deconnexion', 'incident_cree', 'incident_modifie', "
        "'incident_escalade', 'playbook_cree', 'playbook_modifie', 'playbook_supprime', 'parametres_modifies')",
        name=op.f('ck_journal_audit_type_evenement_allowed_values'),
    ),
    sa.CheckConstraint("description <> ''", name=op.f('ck_journal_audit_description_not_blank')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_journal_audit'))
    )
    op.create_index('ix_journal_audit_date_evenement', 'journal_audit', ['date_evenement'], unique=False)
    op.create_index('ix_journal_audit_type_evenement', 'journal_audit', ['type_evenement'], unique=False)

    # Incidents : colonnes ajoutées d'abord facultatives, remplies pour les lignes existantes, puis rendues obligatoires.
    with op.batch_alter_table('incidents') as batch_operations:
        batch_operations.add_column(sa.Column('numero_reference', sa.Integer(), nullable=True))
        batch_operations.add_column(sa.Column('titre', sa.String(length=255), nullable=True))
        batch_operations.add_column(sa.Column('categorie', sa.String(length=255), nullable=True))
        batch_operations.add_column(sa.Column('playbook_id', sa.Uuid(), nullable=True))
        batch_operations.add_column(sa.Column('traite_le', sa.DateTime(timezone=True), nullable=True))
        batch_operations.add_column(sa.Column('escalade_le', sa.DateTime(timezone=True), nullable=True))
    _fill_new_columns_of_existing_incidents()
    with op.batch_alter_table('incidents') as batch_operations:
        batch_operations.alter_column('numero_reference', existing_type=sa.Integer(), nullable=False)
        batch_operations.alter_column('titre', existing_type=sa.String(length=255), nullable=False)
        batch_operations.alter_column('categorie', existing_type=sa.String(length=255), nullable=False)
        batch_operations.create_unique_constraint(op.f('uq_incidents_numero_reference'), ['numero_reference'])
        batch_operations.create_foreign_key(
            op.f('fk_incidents_playbook_id_playbooks'), 'playbooks', ['playbook_id'], ['id'], ondelete='SET NULL'
        )
        batch_operations.create_check_constraint(
            op.f('ck_incidents_traite_le_set_only_when_handled'),
            "(statut IN ('resolu', 'cloture')) = (traite_le IS NOT NULL)",
        )
        batch_operations.create_check_constraint(
            op.f('ck_incidents_traite_le_not_before_created_at'), 'traite_le IS NULL OR traite_le >= created_at'
        )
        batch_operations.create_check_constraint(op.f('ck_incidents_titre_not_blank'), "titre <> ''")
        batch_operations.create_check_constraint(op.f('ck_incidents_categorie_not_blank'), "categorie <> ''")
        batch_operations.create_check_constraint(
            op.f('ck_incidents_numero_reference_positive'), 'numero_reference >= 1'
        )
    op.create_index('ix_incidents_categorie', 'incidents', ['categorie'], unique=False)
    op.create_index('ix_incidents_playbook_id', 'incidents', ['playbook_id'], unique=False)

    op.create_table('etapes_realisees_incident',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('incident_id', sa.Uuid(), nullable=False),
    sa.Column('etape_playbook_id', sa.Uuid(), nullable=False),
    sa.Column('realisee_le', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('realisee_par', sa.String(length=255), nullable=True),
    sa.CheckConstraint("realisee_par IS NULL OR realisee_par <> ''", name=op.f('ck_etapes_realisees_incident_realisee_par_not_blank')),
    sa.ForeignKeyConstraint(['etape_playbook_id'], ['etapes_playbook.id'], name=op.f('fk_etapes_realisees_incident_etape_playbook_id_etapes_playbook'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], name=op.f('fk_etapes_realisees_incident_incident_id_incidents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_etapes_realisees_incident')),
    sa.UniqueConstraint('incident_id', 'etape_playbook_id', name='uq_etapes_realisees_incident_incident_id_etape_playbook_id')
    )


def _fill_new_columns_of_existing_incidents() -> None:
    """Remplit les nouvelles colonnes des incidents déjà présents (en Python : identique sur PostgreSQL et SQLite)."""
    database_connection = op.get_bind()
    # Colonnes typées : sans cela, SQLite renverrait l'id et les dates en texte (PostgreSQL en objets Python).
    existing_incidents = database_connection.execute(sa.text(
        'SELECT incidents.id, logs.type, incidents.statut, incidents.closed_at, incidents.updated_at '
        'FROM incidents JOIN logs ON logs.id = incidents.log_id '
        'ORDER BY incidents.created_at, incidents.id'
    ).columns(
        sa.column('id', sa.Uuid()),
        sa.column('type', sa.String()),
        sa.column('statut', sa.String()),
        sa.column('closed_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )).all()
    for numero_reference, (incident_id, log_type, statut, closed_at, updated_at) in enumerate(existing_incidents, start=1):
        database_connection.execute(
            sa.text(
                'UPDATE incidents SET numero_reference = :numero_reference, titre = :titre, categorie = :categorie, '
                'traite_le = :traite_le WHERE id = :incident_id'
            ).bindparams(sa.bindparam('incident_id', type_=sa.Uuid()), sa.bindparam('traite_le', type_=sa.DateTime(timezone=True))),
            {
                'numero_reference': numero_reference,
                'titre': f'Alerte {log_type}',
                'categorie': log_type,
                'traite_le': (closed_at or updated_at) if statut in ('resolu', 'cloture') else None,
                'incident_id': incident_id,
            },
        )


def downgrade() -> None:
    op.drop_table('etapes_realisees_incident')
    op.drop_index('ix_incidents_playbook_id', table_name='incidents')
    op.drop_index('ix_incidents_categorie', table_name='incidents')
    with op.batch_alter_table('incidents') as batch_operations:
        batch_operations.drop_constraint(op.f('ck_incidents_numero_reference_positive'), type_='check')
        batch_operations.drop_constraint(op.f('ck_incidents_categorie_not_blank'), type_='check')
        batch_operations.drop_constraint(op.f('ck_incidents_titre_not_blank'), type_='check')
        batch_operations.drop_constraint(op.f('ck_incidents_traite_le_not_before_created_at'), type_='check')
        batch_operations.drop_constraint(op.f('ck_incidents_traite_le_set_only_when_handled'), type_='check')
        batch_operations.drop_constraint(op.f('fk_incidents_playbook_id_playbooks'), type_='foreignkey')
        batch_operations.drop_constraint(op.f('uq_incidents_numero_reference'), type_='unique')
        batch_operations.drop_column('escalade_le')
        batch_operations.drop_column('traite_le')
        batch_operations.drop_column('playbook_id')
        batch_operations.drop_column('categorie')
        batch_operations.drop_column('titre')
        batch_operations.drop_column('numero_reference')
    op.drop_index('ix_journal_audit_type_evenement', table_name='journal_audit')
    op.drop_index('ix_journal_audit_date_evenement', table_name='journal_audit')
    op.drop_table('journal_audit')
    op.drop_table('delais_reponse_incidents')
    op.drop_table('etapes_playbook')
    op.drop_table('playbooks')
