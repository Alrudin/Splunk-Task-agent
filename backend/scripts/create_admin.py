"""
Script to create initial admin user.
"""
import asyncio
import sys
import re
import click

from backend.database import async_session_factory
from backend.repositories.user_repository import UserRepository
from backend.repositories.role_repository import RoleRepository
from backend.core.security import hash_password
from backend.models.enums import UserRoleEnum


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"

    return True, ""


async def create_admin_user(
    username: str,
    email: str,
    password: str,
    full_name: str,
    force: bool = False
):
    """
    Create admin user.

    Args:
        username: Username
        email: Email address
        password: Password
        full_name: Full name
        force: If True, recreate user if exists
    """
    async with async_session_factory() as session:
        try:
            user_repo = UserRepository(session)
            role_repo = RoleRepository(session)

            # Check if user exists
            existing_user = await user_repo.get_by_username(username)
            if existing_user:
                if force:
                    click.echo(f"User '{username}' already exists. Updating...")
                    # Update existing user
                    hashed_password = hash_password(password)
                    await user_repo.update(
                        existing_user.id,
                        email=email,
                        full_name=full_name,
                        hashed_password=hashed_password,
                        is_active=True,
                        is_superuser=True
                    )
                    user = existing_user
                    click.echo(f"✓ Updated user: {username}")
                else:
                    click.echo(f"✗ User '{username}' already exists. Use --force to recreate.", err=True)
                    sys.exit(1)
            else:
                # Create user
                hashed_password = hash_password(password)
                user = await user_repo.create(
                    username=username,
                    email=email,
                    hashed_password=hashed_password,
                    full_name=full_name,
                    auth_provider="local",
                    is_active=True,
                    is_superuser=True
                )
                click.echo(f"✓ Created user: {username}")

            # Assign ADMIN role
            admin_role = await role_repo.get_by_name(UserRoleEnum.ADMIN)
            if not admin_role:
                click.echo("✗ ADMIN role not found. Please run 'python -m backend.scripts.seed_roles' first.", err=True)
                sys.exit(1)

            # Check if user already has ADMIN role
            user_roles = [role.name for role in user.roles]
            if UserRoleEnum.ADMIN.value not in user_roles:
                await user_repo.add_role(user.id, admin_role.id)
                click.echo(f"✓ Assigned ADMIN role to {username}")
            else:
                click.echo(f"→ User already has ADMIN role")

            await session.commit()

            click.echo(f"\n✓ Admin user created successfully!")
            click.echo(f"\nUser Details:")
            click.echo(f"  Username: {username}")
            click.echo(f"  Email: {email}")
            click.echo(f"  Full Name: {full_name}")
            click.echo(f"  Superuser: Yes")
            click.echo(f"  Roles: ADMIN")

        except Exception as e:
            await session.rollback()
            click.echo(f"✗ Error creating admin user: {e}", err=True)
            sys.exit(1)


@click.command()
@click.option(
    "--username",
    prompt=True,
    help="Admin username"
)
@click.option(
    "--email",
    prompt=True,
    help="Admin email address"
)
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Admin password"
)
@click.option(
    "--full-name",
    prompt=True,
    help="Admin full name"
)
@click.option(
    "--force",
    is_flag=True,
    help="Recreate user if exists"
)
def main(username: str, email: str, password: str, full_name: str, force: bool):
    """Create an admin user."""
    # Validate password
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        click.echo(f"✗ {error_msg}", err=True)
        sys.exit(1)

    click.echo("Creating admin user...")
    asyncio.run(create_admin_user(username, email, password, full_name, force))


if __name__ == "__main__":
    main()
