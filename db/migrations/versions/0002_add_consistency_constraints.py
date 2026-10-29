"""add consistency constraints

Ajoute les garde-fous de cohérence nécessaires aux services métier (cf. docs/technical/database.md) :
- executions_import : compteurs cohérents, erreur obligatoire si partielle/échouée, absente si réussie,
  fin postérieure au début, index sur `debut` (tri de l'historique) ;
- logs : identifiant_source non vide ;
- incidents : clôture postérieure à la création, `assigne_a` jamais vide (NULL = non assigné),
  index sur `criticite_actuelle` (filtre de liste).

`batch_alter_table` : nécessaire pour SQLite (tests), qui ne sait pas ajouter une contrainte CHECK à une table
existante ; sur PostgreSQL, Alembic émet de simples ALTER TABLE.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('executions_import') as batch_operations:
        batch_operations.create_check_constraint(
            op.f('ck_executions_import_processed_logs_not_above_received_logs'),
            'nb_logs_inseres + nb_logs_ignores <= nb_logs_recus',
        )
        batch_operations.create_check_constraint(
            op.f('ck_executions_import_erreur_required_when_partial_or_failed'),
            "statut NOT IN ('partielle', 'echouee') OR (erreur IS NOT NULL AND erreur <> '')",
        )
        batch_operations.create_check_constraint(
            op.f('ck_executions_import_erreur_absent_when_succeeded'),
            "statut <> 'reussie' OR erreur IS NULL",
        )
        batch_operations.create_check_constraint(
            op.f('ck_executions_import_fin_not_before_debut'),
            'fin IS NULL OR fin >= debut',
        )
    op.create_index('ix_executions_import_debut', 'executions_import', ['debut'], unique=False)

    with op.batch_alter_table('logs') as batch_operations:
        batch_operations.create_check_constraint(
            op.f('ck_logs_identifiant_source_not_blank'),
            "identifiant_source <> ''",
        )

    with op.batch_alter_table('incidents') as batch_operations:
        batch_operations.create_check_constraint(
            op.f('ck_incidents_closed_at_not_before_created_at'),
            'closed_at IS NULL OR closed_at >= created_at',
        )
        batch_operations.create_check_constraint(
            op.f('ck_incidents_assigne_a_not_blank'),
            "assigne_a IS NULL OR assigne_a <> ''",
        )
    op.create_index('ix_incidents_criticite_actuelle', 'incidents', ['criticite_actuelle'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_incidents_criticite_actuelle', table_name='incidents')
    with op.batch_alter_table('incidents') as batch_operations:
        batch_operations.drop_constraint(op.f('ck_incidents_assigne_a_not_blank'), type_='check')
        batch_operations.drop_constraint(op.f('ck_incidents_closed_at_not_before_created_at'), type_='check')

    with op.batch_alter_table('logs') as batch_operations:
        batch_operations.drop_constraint(op.f('ck_logs_identifiant_source_not_blank'), type_='check')

    op.drop_index('ix_executions_import_debut', table_name='executions_import')
    with op.batch_alter_table('executions_import') as batch_operations:
        batch_operations.drop_constraint(op.f('ck_executions_import_fin_not_before_debut'), type_='check')
        batch_operations.drop_constraint(op.f('ck_executions_import_erreur_absent_when_succeeded'), type_='check')
        batch_operations.drop_constraint(
            op.f('ck_executions_import_erreur_required_when_partial_or_failed'), type_='check'
        )
        batch_operations.drop_constraint(
            op.f('ck_executions_import_processed_logs_not_above_received_logs'), type_='check'
        )
