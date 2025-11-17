"""create initial schema for all models

Revision ID: 001
Revises:
Create Date: 2025-11-17 19:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('auth_provider', sa.String(length=50), nullable=True),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_external_id'), 'users', ['external_id'], unique=False)
    op.create_index('ix_users_email_auth_provider', 'users', ['email', 'auth_provider'], unique=False)

    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_roles_name')
    )
    op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)

    # Create user_roles association table
    op.create_table(
        'user_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', name='uq_user_role')
    )
    op.create_index('ix_user_roles_user_id', 'user_roles', ['user_id'], unique=False)
    op.create_index('ix_user_roles_role_id', 'user_roles', ['role_id'], unique=False)

    # Create requests table
    op.create_table(
        'requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('source_system', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('cim_required', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_requests_created_by'), 'requests', ['created_by'], unique=False)
    op.create_index(op.f('ix_requests_status'), 'requests', ['status'], unique=False)
    op.create_index('ix_requests_status_created_at', 'requests', ['status', 'created_at'], unique=False)

    # Create log_samples table
    op.create_table(
        'log_samples',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('storage_bucket', sa.String(length=100), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('sample_preview', sa.Text(), nullable=True),
        sa.Column('retention_until', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_log_samples_request_id'), 'log_samples', ['request_id'], unique=False)
    op.create_index(op.f('ix_log_samples_storage_key'), 'log_samples', ['storage_key'], unique=False)
    op.create_index('ix_log_samples_retention_until', 'log_samples', ['retention_until'], unique=False)

    # Create ta_revisions table
    op.create_table(
        'ta_revisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('storage_bucket', sa.String(length=100), nullable=False),
        sa.Column('generated_by', sa.String(length=50), nullable=False),
        sa.Column('generated_by_user', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('config_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('generation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['generated_by_user'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id', 'version', name='uq_request_version')
    )
    op.create_index(op.f('ix_ta_revisions_request_id'), 'ta_revisions', ['request_id'], unique=False)
    op.create_index('ix_ta_revisions_request_id_version', 'ta_revisions', ['request_id', 'version'], unique=False)
    op.create_index('ix_ta_revisions_generated_by', 'ta_revisions', ['generated_by'], unique=False)

    # Create validation_runs table
    op.create_table(
        'validation_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ta_revision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('results_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('debug_bundle_key', sa.String(length=500), nullable=True),
        sa.Column('debug_bundle_bucket', sa.String(length=100), nullable=True),
        sa.Column('splunk_container_id', sa.String(length=255), nullable=True),
        sa.Column('validation_logs', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ta_revision_id'], ['ta_revisions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_validation_runs_request_id'), 'validation_runs', ['request_id'], unique=False)
    op.create_index(op.f('ix_validation_runs_ta_revision_id'), 'validation_runs', ['ta_revision_id'], unique=False)
    op.create_index(op.f('ix_validation_runs_status'), 'validation_runs', ['status'], unique=False)
    op.create_index('ix_validation_runs_request_id_created_at', 'validation_runs', ['request_id', 'created_at'], unique=False)
    op.create_index('ix_validation_runs_started_at', 'validation_runs', ['started_at'], unique=False)

    # Create knowledge_documents table
    op.create_table(
        'knowledge_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('storage_bucket', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pinecone_indexed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('pinecone_index_name', sa.String(length=100), nullable=True),
        sa.Column('embedding_count', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_knowledge_documents_document_type', 'knowledge_documents', ['document_type'], unique=False)
    op.create_index('ix_knowledge_documents_uploaded_by', 'knowledge_documents', ['uploaded_by'], unique=False)
    op.create_index('ix_knowledge_documents_pinecone_indexed', 'knowledge_documents', ['pinecone_indexed'], unique=False)
    op.create_index('ix_knowledge_documents_is_active', 'knowledge_documents', ['is_active'], unique=False)

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)
    op.create_index('ix_audit_logs_user_id_timestamp', 'audit_logs', ['user_id', 'timestamp'], unique=False)
    op.create_index('ix_audit_logs_entity_type_entity_id', 'audit_logs', ['entity_type', 'entity_id'], unique=False)
    op.create_index('ix_audit_logs_correlation_id', 'audit_logs', ['correlation_id'], unique=False)

    # Create system_config table
    op.create_table(
        'system_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_secret', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_system_config_key')
    )
    op.create_index('ix_system_config_key', 'system_config', ['key'], unique=True)
    op.create_index('ix_system_config_updated_at', 'system_config', ['updated_at'], unique=False)


def downgrade() -> None:
    # Drop all tables in reverse order to handle foreign key constraints
    op.drop_index('ix_system_config_updated_at', table_name='system_config')
    op.drop_index('ix_system_config_key', table_name='system_config')
    op.drop_table('system_config')

    op.drop_index('ix_audit_logs_correlation_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_entity_type_entity_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_id_timestamp', table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_timestamp'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_entity_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index('ix_knowledge_documents_is_active', table_name='knowledge_documents')
    op.drop_index('ix_knowledge_documents_pinecone_indexed', table_name='knowledge_documents')
    op.drop_index('ix_knowledge_documents_uploaded_by', table_name='knowledge_documents')
    op.drop_index('ix_knowledge_documents_document_type', table_name='knowledge_documents')
    op.drop_table('knowledge_documents')

    op.drop_index('ix_validation_runs_started_at', table_name='validation_runs')
    op.drop_index('ix_validation_runs_request_id_created_at', table_name='validation_runs')
    op.drop_index(op.f('ix_validation_runs_status'), table_name='validation_runs')
    op.drop_index(op.f('ix_validation_runs_ta_revision_id'), table_name='validation_runs')
    op.drop_index(op.f('ix_validation_runs_request_id'), table_name='validation_runs')
    op.drop_table('validation_runs')

    op.drop_index('ix_ta_revisions_generated_by', table_name='ta_revisions')
    op.drop_index('ix_ta_revisions_request_id_version', table_name='ta_revisions')
    op.drop_index(op.f('ix_ta_revisions_request_id'), table_name='ta_revisions')
    op.drop_table('ta_revisions')

    op.drop_index('ix_log_samples_retention_until', table_name='log_samples')
    op.drop_index(op.f('ix_log_samples_storage_key'), table_name='log_samples')
    op.drop_index(op.f('ix_log_samples_request_id'), table_name='log_samples')
    op.drop_table('log_samples')

    op.drop_index('ix_requests_status_created_at', table_name='requests')
    op.drop_index(op.f('ix_requests_status'), table_name='requests')
    op.drop_index(op.f('ix_requests_created_by'), table_name='requests')
    op.drop_table('requests')

    op.drop_index('ix_user_roles_role_id', table_name='user_roles')
    op.drop_index('ix_user_roles_user_id', table_name='user_roles')
    op.drop_table('user_roles')

    op.drop_index(op.f('ix_roles_name'), table_name='roles')
    op.drop_table('roles')

    op.drop_index('ix_users_email_auth_provider', table_name='users')
    op.drop_index(op.f('ix_users_external_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
