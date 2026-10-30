"""Ligações entre fontes: colunas equivalentes em dois catálogos."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.models import (
    CatalogColumn,
    CatalogEntity,
    CatalogSourceLink,
)


@dataclass(frozen=True)
class ResolvedLink:
    """Ligação com os nomes das duas pontas."""

    id: UUID
    from_datasource_id: str
    from_entity: str  # schema.entidade
    from_column: str
    to_datasource_id: str
    to_entity: str
    to_column: str
    description: str | None
    enabled: bool
    active: bool

    @property
    def from_table(self) -> str:
        return f'{self.from_datasource_id}.{self.from_entity}'

    @property
    def to_table(self) -> str:
        return f'{self.to_datasource_id}.{self.to_entity}'


def _usable(entity: CatalogEntity, column: str) -> bool:
    found = next((c for c in entity.columns if c.name == column), None)
    return bool(
        entity.visible
        and entity.queryable
        and entity.present
        and found is not None
        and found.visible
        and found.present
    )


def resolve_link(
    link: CatalogSourceLink,
    source: CatalogEntity,
    target: CatalogEntity,
) -> ResolvedLink:
    return ResolvedLink(
        id=link.id,
        from_datasource_id=source.datasource_id,
        from_entity=source.qualified_name,
        from_column=link.from_column,
        to_datasource_id=target.datasource_id,
        to_entity=target.qualified_name,
        to_column=link.to_column,
        description=link.description,
        enabled=link.enabled,
        active=(
            link.enabled
            and _usable(source, link.from_column)
            and _usable(target, link.to_column)
        ),
    )


async def load_links(session: AsyncSession) -> list[ResolvedLink]:
    links = list(await session.scalars(select(CatalogSourceLink)))
    ids = {
        entity_id
        for link in links
        for entity_id in (link.from_entity_id, link.to_entity_id)
    }
    entities = {
        e.id: e
        for e in await session.scalars(
            select(CatalogEntity).where(CatalogEntity.id.in_(ids))
        )
    }
    resolved = [
        resolve_link(
            link, entities[link.from_entity_id], entities[link.to_entity_id]
        )
        for link in links
    ]
    return sorted(resolved, key=lambda r: (r.from_table, r.from_column))


async def find_entity(
    session: AsyncSession, datasource_id: str, schema_name: str, name: str
) -> CatalogEntity | None:
    return await session.scalar(
        select(CatalogEntity).where(
            CatalogEntity.datasource_id == datasource_id,
            CatalogEntity.schema_name == schema_name,
            CatalogEntity.name == name,
        )
    )


async def has_column(
    session: AsyncSession, entity: CatalogEntity, column: str
) -> bool:
    found = await session.scalar(
        select(CatalogColumn.id).where(
            CatalogColumn.entity_id == entity.id,
            CatalogColumn.name == column,
        )
    )
    return found is not None
