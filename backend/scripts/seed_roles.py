"""
Script to seed initial roles in the database.
"""
import asyncio
import sys
import click

from backend.database import async_session_factory
from backend.repositories.role_repository import RoleRepository
from backend.models.enums import UserRoleEnum


ROLE_DESCRIPTIONS = {
    UserRoleEnum.REQUESTOR: "Can submit TA generation requests and view own requests",
    UserRoleEnum.APPROVER: "Can approve/reject TA generation requests",
    UserRoleEnum.ADMIN: "Full system access including configuration and user management",
    UserRoleEnum.KNOWLEDGE_MANAGER: "Can upload and manage knowledge documents"
}


async def seed_roles(force: bool = False):
    """
    Seed roles in the database.

    Args:
        force: If True, recreate roles even if they exist
    """
    async with async_session_factory() as session:
        try:
            role_repo = RoleRepository(session)
            created_count = 0
            updated_count = 0

            for role_enum in UserRoleEnum:
                role_name = role_enum.value
                description = ROLE_DESCRIPTIONS[role_enum]

                # Check if role exists
                existing_role = await role_repo.get_by_name(role_enum)

                if existing_role:
                    if force:
                        # Update role description
                        await role_repo.update(
                            existing_role.id,
                            description=description
                        )
                        updated_count += 1
                        click.echo(f"✓ Updated role: {role_name}")
                    else:
                        click.echo(f"→ Role already exists: {role_name}")
                else:
                    # Create role
                    await role_repo.create(
                        name=role_name,
                        description=description
                    )
                    created_count += 1
                    click.echo(f"✓ Created role: {role_name}")

            await session.commit()

            click.echo(f"\nSummary:")
            click.echo(f"  Created: {created_count}")
            click.echo(f"  Updated: {updated_count}")
            click.echo(f"  Total: {len(UserRoleEnum)}")
            click.echo(f"\n✓ Roles seeded successfully!")

        except Exception as e:
            await session.rollback()
            click.echo(f"✗ Error seeding roles: {e}", err=True)
            sys.exit(1)


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="Recreate roles even if they exist"
)
def main(force: bool):
    """Seed initial roles in the database."""
    click.echo("Seeding roles...")
    asyncio.run(seed_roles(force))


if __name__ == "__main__":
    main()
