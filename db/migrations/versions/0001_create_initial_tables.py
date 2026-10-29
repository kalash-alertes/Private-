"""create initial tables

Revision ID: 0001
Revises: 
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables : executions_import (collectes), logs (alertes connues), incidents (suivi métier).
    op.create_table('executions_import',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('debut', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('fin', sa.DateTime(timezone=True), nullable=True),
    sa.Column('statut', sa.String(), nullable=False),
    sa.Column('nb_logs_recus', sa.Integer(), nullable=False),
    sa.Column('nb_logs_inseres', sa.Integer(), nullable=False),
    sa.Column('nb_logs_ignores', sa.Integer(), nullable=False),
    sa.Column('erreur', sa.Text(), nullable=True),
    sa.Column('curseur_synchronisation', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("(statut = 'en_cours') = (fin IS NULL)", name=op.f('ck_executions_import_fin_set_only_when_finished')),
    sa.CheckConstraint("statut IN ('en_cours', 'reussie', 'partielle', 'echouee')", name=op.f('ck_executions_import_statut_allowed_values')),
    sa.CheckConstraint('nb_logs_recus >= 0 AND nb_logs_inseres >= 0 AND nb_logs_ignores >= 0', name=op.f('ck_executions_import_log_counters_not_negative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_executions_import'))
    )
    op.create_table('logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('identifiant_source', sa.String(length=255), nullable=False),
    sa.Column('date_evenement', sa.DateTime(timezone=True), nullable=False),
    sa.Column('type', sa.String(length=255), nullable=False),
    sa.Column('criticite_source', sa.String(length=32), nullable=False),
    sa.Column('donnees_brutes', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('reference_opensearch', sa.String(length=255), nullable=True),
    sa.Column('arrivee_db', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('execution_import_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("criticite_source IN ('information', 'faible', 'moyenne', 'haute', 'critique')", name=op.f('ck_logs_criticite_source_allowed_values')),
    sa.ForeignKeyConstraint(['execution_import_id'], ['executions_import.id'], name=op.f('fk_logs_execution_import_id_executions_import'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_logs')),
    sa.UniqueConstraint('identifiant_source', name=op.f('uq_logs_identifiant_source'))
    )
    op.create_index('ix_logs_criticite_source', 'logs', ['criticite_source'], unique=False)
    op.create_index('ix_logs_date_evenement', 'logs', ['date_evenement'], unique=False)
    op.create_index('ix_logs_execution_import_id', 'logs', ['execution_import_id'], unique=False)
    op.create_table('incidents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('log_id', sa.Uuid(), nullable=False),
    sa.Column('statut', sa.String(length=32), nullable=False),
    sa.Column('criticite_actuelle', sa.String(length=32), nullable=False),
    sa.Column('faux_positif', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('justification', sa.Text(), nullable=True),
    sa.Column('assigne_a', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("(statut = 'cloture') = (closed_at IS NOT NULL)", name=op.f('ck_incidents_closed_at_set_only_when_closed')),
    sa.CheckConstraint("criticite_actuelle IN ('information', 'faible', 'moyenne', 'haute', 'critique')", name=op.f('ck_incidents_criticite_actuelle_allowed_values')),
    sa.CheckConstraint("faux_positif = false OR (justification IS NOT NULL AND justification <> '')", name=op.f('ck_incidents_faux_positif_requires_justification')),
    sa.CheckConstraint("statut IN ('nouveau', 'en_cours', 'en_attente', 'resolu', 'cloture')", name=op.f('ck_incidents_statut_allowed_values')),
    sa.ForeignKeyConstraint(['log_id'], ['logs.id'], name=op.f('fk_incidents_log_id_logs'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_incidents')),
    sa.UniqueConstraint('log_id', name=op.f('uq_incidents_log_id'))
    )
    op.create_index('ix_incidents_assigne_a', 'incidents', ['assigne_a'], unique=False)
    op.create_index('ix_incidents_statut', 'incidents', ['statut'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_incidents_statut', table_name='incidents')
    op.drop_index('ix_incidents_assigne_a', table_name='incidents')
    op.drop_table('incidents')
    op.drop_index('ix_logs_execution_import_id', table_name='logs')
    op.drop_index('ix_logs_date_evenement', table_name='logs')
    op.drop_index('ix_logs_criticite_source', table_name='logs')
    op.drop_table('logs')
    op.drop_table('executions_import')
    # ### end Alembic commands ###
