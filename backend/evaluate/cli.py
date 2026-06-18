"""CLI sub-commands for seeding datasets into OGI databases."""
from __future__ import annotations

import asyncio
import uuid
import typer
from sqlmodel import select

from ogi.config import settings
from ogi.db import database as db
from ogi.models import Project
from ogi.models.auth import UserProfile
from ogi.models.project import ProjectCreate
from ogi.store.project_store import ProjectStore
from evaluate.dataset import seed_dataset_to_project

app = typer.Typer(
    name="evaluate-cli",
    help="CLI tools for OGI investigator benchmarking and dataset seeding.",
    no_args_is_help=True,
)


def _run(coro) -> None:
    asyncio.run(coro)


async def _seed(dataset: str, project_name: str, db_url: str | None) -> None:
    if db_url:
        settings.database_url = db_url
        settings.use_sqlite = False

    typer.echo(f"Initializing database connection (use_sqlite={settings.use_sqlite})...")
    await db.init_db()

    anon_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

    async with db.async_session_maker() as session:
        # Ensure anonymous profile exists
        profile = await session.get(UserProfile, anon_id)
        if not profile:
            typer.echo("Seeding anonymous user profile...")
            profile = UserProfile(id=anon_id, email="local@localhost")
            session.add(profile)
            await session.flush()

        project_store = ProjectStore(session)

        # Check if project exists, delete first to refresh
        stmt = select(Project).where(Project.name == project_name)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            typer.echo(f"Deleting existing project '{project_name}'...")
            await project_store.delete(existing.id)
            await session.commit()

        # Create new project
        typer.echo(f"Creating project '{project_name}'...")
        project = await project_store.create(
            ProjectCreate(
                name=project_name,
                description=f"Seeded STIX dataset from {dataset}",
                is_public=True,
            ),
            owner_id=anon_id,
        )
        await session.commit()
        await session.refresh(project)

        typer.echo(f"Seeding STIX dataset into project '{project_name}' (ID: {project.id})...")
        entities, edges = await seed_dataset_to_project(session, dataset, project.id)
        typer.echo(f"Seeded {len(entities)} entities and {len(edges)} edges successfully.")

    await db.close_db()


@app.command("seed")
def seed_dataset(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Path to STIX 2.1 JSON dataset"),
    project_name: str = typer.Option(..., "--project-name", "-p", help="Name of project to seed"),
    db_url: str = typer.Option(
        None,
        "--db-url",
        help="Override database URL (e.g. postgresql://postgres:postgres@localhost:5432/ogi)",
    ),
) -> None:
    """Seed a STIX 2.1 dataset into the OGI database."""
    _run(_seed(dataset, project_name, db_url))


@app.command("info")
def info() -> None:
    """Print information about the OGI evaluation CLI."""
    typer.echo("OpenGraph Intel (OGI) Evaluation CLI - Phase 1")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
