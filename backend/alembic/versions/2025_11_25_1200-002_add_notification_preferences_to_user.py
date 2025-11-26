"""Add notification preferences to user

Revision ID: 002_notification_prefs
Revises: 001
Create Date: 2025-11-25 12:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_notification_prefs'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """Add notification preference columns to users table."""
    # Add email_notifications_enabled column
    op.add_column('users',
        sa.Column('email_notifications_enabled',
                  sa.Boolean(),
                  nullable=False,
                  server_default='true')
    )

    # Add webhook_url column
    op.add_column('users',
        sa.Column('webhook_url',
                  sa.String(length=2048),
                  nullable=True)
    )

    # Add notification_events column (JSONB array)
    op.add_column('users',
        sa.Column('notification_events',
                  postgresql.JSONB(),
                  nullable=True)
    )

    # Remove server_default after adding the column
    # This ensures existing records get the default value but new records
    # will use the application-level default
    op.alter_column('users', 'email_notifications_enabled',
                    server_default=None)


def downgrade():
    """Remove notification preference columns from users table."""
    op.drop_column('users', 'notification_events')
    op.drop_column('users', 'webhook_url')
    op.drop_column('users', 'email_notifications_enabled')