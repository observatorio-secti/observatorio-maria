"""Formato YAML do catálogo, compartilhado pelo seed e pela exportação.

O YAML é ponto de partida, não fonte de verdade: o seed só cria o que ainda
não existe no catálogo (ou recria a fonte inteira com `reset`).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
    relationship_key,
)
from observatorio_maria.models import (
    CatalogColumn,
    CatalogConcept,
    CatalogDataSource,
    CatalogEntity,
    CatalogRelationship,
    ColumnAccess,
    RelationshipOrigin,
    ValueListing,
)

SLUG_PATTERN = r'^[a-z][a-z0-9_-]{0,63}$'
ENV_PATTERN = r'^[A-Z_][A-Z0-9_]{0,99}$'

# Entidade de um conceito: `fonte:schema.entidade`.
ENTITY_REF_PATTERN = r'^[a-z][a-z0-9_-]{0,63}:[^.:\s]+\.[^.:\s]+$'

Slug = Annotated[str, Field(pattern=SLUG_PATTERN)]
EnvName = Annotated[str, Field(pattern=ENV_PATTERN)]
EntityRef = Annotated[str, Field(pattern=ENTITY_REF_PATTERN)]


class CatalogFileError(ValueError):
    """Arquivo YAML inválido ou incoerente com o catálogo."""


class ColumnValue(BaseModel):
    model_config = ConfigDict(extra='forbid')

    value: str | int | float | bool
    description: str | None = None


class ColumnDoc(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str
    label: str | None = None
    description: str | None = None
    synonyms: list[str] = []
    values: list[ColumnValue] = []
    visible: bool = True
    access: ColumnAccess = ColumnAccess.FULL
    searchable: bool = False
    list_values: ValueListing = ValueListing.AUTO


class EntityDoc(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    name: str
    schema_name: str | None = Field(None, alias='schema')
    label: str | None = None
    description: str | None = None
    synonyms: list[str] = []
    visible: bool = True
    # Omitido: acompanha `visible`.
    queryable: bool | None = None
    columns: list[ColumnDoc] = []

    @model_validator(mode='after')
    def queryable_requires_visible(self) -> Self:
        if self.queryable and not self.visible:
            raise ValueError(
                f'{self.name}: uma entidade consultável precisa ser visível'
            )
        return self


class RelationshipDoc(BaseModel):
    """`from`/`to` no formato `[schema.]entidade.coluna[,coluna...]`."""

    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    from_: str = Field(alias='from')
    to: str
    description: str | None = None
    enabled: bool = True


class QueryExampleDoc(BaseModel):
    model_config = ConfigDict(extra='forbid')

    question: str = Field(min_length=1, max_length=500)
    sql: str = Field(min_length=1)


class DataSourceDoc(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: Slug
    name: str = Field(min_length=1, max_length=200)
    connection_env: EnvName
    description: str | None = None
    instructions: str | None = None
    examples: list[QueryExampleDoc] = []
    schemas: list[str] = Field(['public'], min_length=1)
    enabled: bool = True
    auto_sync: bool = False


class CatalogFile(BaseModel):
    model_config = ConfigDict(extra='forbid')

    datasource: DataSourceDoc
    entities: list[EntityDoc] = []
    relationships: list[RelationshipDoc] = []


class ConceptDoc(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: Slug
    label: str = Field(min_length=1, max_length=200)
    description: str | None = None
    synonyms: list[str] = []
    instructions: str | None = None
    entities: list[EntityRef] = []


class ConceptsFile(BaseModel):
    """Arquivo de conceitos: assuntos que aparecem em mais de uma fonte."""

    model_config = ConfigDict(extra='forbid')

    concepts: list[ConceptDoc]

    @model_validator(mode='after')
    def unique_ids(self) -> Self:
        ids = [c.id for c in self.concepts]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise ValueError(f'conceito(s) repetido(s): {", ".join(repeated)}')
        return self


@dataclass
class SeedReport:
    datasource_created: bool = False
    entities: int = 0
    columns: int = 0
    relationships: int = 0


@dataclass
class ConceptSeedReport:
    created: int = 0
    linked: int = 0
    # Entidades citadas no arquivo que não estão no catálogo.
    missing: list[str] = field(default_factory=list)


def load_catalog_file(path: Path) -> CatalogFile:
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        return CatalogFile.model_validate(data)
    except (yaml.YAMLError, ValueError) as exc:
        raise CatalogFileError(f'{path}: {exc}') from exc


def load_seed_file(path: Path) -> CatalogFile | ConceptsFile:
    """Arquivo de fonte (`datasource:`) ou de conceitos (`concepts:`)."""
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and 'concepts' in data:
            return ConceptsFile.model_validate(data)
        return CatalogFile.model_validate(data)
    except (yaml.YAMLError, ValueError) as exc:
        raise CatalogFileError(f'{path}: {exc}') from exc


class _Dumper(yaml.SafeDumper):
    """Textos com quebra de linha em bloco literal (`|`), como no seed."""


def _represent_str(dumper, value):
    style = '|' if '\n' in value else None
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style=style)


_Dumper.add_representer(str, _represent_str)


def dump_concepts_file(document: ConceptsFile) -> str:
    data = document.model_dump(mode='json', exclude_defaults=True)
    return yaml.dump(
        data, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=88
    )


def dump_catalog_file(document: CatalogFile) -> str:
    data = document.model_dump(
        mode='json', by_alias=True, exclude_defaults=True
    )
    # `id`, `name` e `connection_env` sempre saem; schemas também, por clareza.
    data['datasource']['schemas'] = document.datasource.schemas
    return yaml.dump(
        data, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=88
    )


def _parse_ref(ref: str, default_schema: str):
    entity_part, _, columns = ref.rpartition('.')
    if not entity_part or not columns:
        raise CatalogFileError(f'Referência inválida: {ref!r}')
    schema, _, entity = entity_part.rpartition('.')
    return (schema or default_schema, entity), [
        c.strip() for c in columns.split(',')
    ]


def _format_ref(entity: CatalogEntity, columns, default_schema: str) -> str:
    name = (
        entity.name
        if entity.schema_name == default_schema
        else entity.qualified_name
    )
    return f'{name}.{",".join(columns)}'


async def _seed_entities(session, datasource, document, report):
    default_schema = datasource.schemas[0]
    entities = {
        (e.schema_name, e.name): e
        for e in await load_entities(session, datasource.id)
    }
    for entity_doc in document.entities:
        key = (entity_doc.schema_name or default_schema, entity_doc.name)
        entity = entities.get(key)
        if entity is None:
            entity = CatalogEntity(
                datasource_id=datasource.id,
                schema_name=key[0],
                name=entity_doc.name,
                label=entity_doc.label,
                description=entity_doc.description,
                synonyms=entity_doc.synonyms,
                visible=entity_doc.visible,
                queryable=(
                    entity_doc.visible
                    if entity_doc.queryable is None
                    else entity_doc.queryable
                ),
            )
            session.add(entity)
            entities[key] = entity
            report.entities += 1

        existing = {column.name for column in entity.columns}
        for column_doc in entity_doc.columns:
            if column_doc.name in existing:
                continue
            entity.columns.append(
                CatalogColumn(
                    entity_id=entity.id,
                    **column_doc.model_dump(mode='json'),
                )
            )
            existing.add(column_doc.name)
            report.columns += 1
    return entities


async def _seed_relationships(session, datasource, document, entities, report):
    default_schema = datasource.schemas[0]
    relationships = {
        relationship_key(r)
        for r in await load_relationships(session, datasource.id)
    }
    for relationship_doc in document.relationships:
        refs = []
        for ref in (relationship_doc.from_, relationship_doc.to):
            entity_key, columns = _parse_ref(ref, default_schema)
            if entity_key not in entities:
                raise CatalogFileError(
                    f'Relacionamento {ref!r}: entidade desconhecida'
                )
            refs.append((entities[entity_key], columns))
        (source, from_columns), (target, to_columns) = refs
        key = (source.id, tuple(from_columns), target.id, tuple(to_columns))
        if key in relationships:
            continue
        session.add(
            CatalogRelationship(
                datasource_id=datasource.id,
                from_entity_id=source.id,
                from_columns=from_columns,
                to_entity_id=target.id,
                to_columns=to_columns,
                origin=RelationshipOrigin.MANUAL,
                description=relationship_doc.description,
                enabled=relationship_doc.enabled,
            )
        )
        relationships.add(key)
        report.relationships += 1


async def seed_catalog(
    session: AsyncSession, document: CatalogFile, *, reset: bool = False
) -> SeedReport:
    """Cria o que falta do `document` no catálogo, num único commit."""
    report = SeedReport()
    doc = document.datasource
    datasource = await session.get(CatalogDataSource, doc.id)
    try:
        if datasource is not None and reset:
            # Remoção pelo ORM (e não só pelo CASCADE do banco) para que a
            # sessão não guarde objetos já apagados.
            for item in [
                *await load_relationships(session, datasource.id),
                *await load_entities(session, datasource.id),
                datasource,
            ]:
                await session.delete(item)
            await session.flush()
            datasource = None
        if datasource is None:
            datasource = CatalogDataSource(**doc.model_dump())
            session.add(datasource)
            report.datasource_created = True

        entities = await _seed_entities(session, datasource, document, report)
        await _seed_relationships(
            session, datasource, document, entities, report
        )
    except CatalogFileError:
        await session.rollback()
        raise

    await session.commit()
    return report


def _column_doc(column: CatalogColumn) -> dict[str, Any]:
    return {
        'name': column.name,
        'label': column.label,
        'description': column.description,
        'synonyms': column.synonyms,
        'values': column.values,
        'visible': column.visible,
        'access': column.access,
        'searchable': column.searchable,
        'list_values': column.list_values,
    }


async def export_catalog(
    session: AsyncSession, datasource: CatalogDataSource
) -> CatalogFile:
    default_schema = datasource.schemas[0]
    entities = await load_entities(session, datasource.id)
    by_id = {entity.id: entity for entity in entities}
    relationships = sorted(
        await load_relationships(session, datasource.id),
        key=lambda r: (
            by_id[r.from_entity_id].qualified_name,
            r.from_columns,
            by_id[r.to_entity_id].qualified_name,
        ),
    )
    return CatalogFile(
        datasource=DataSourceDoc(
            id=datasource.id,
            name=datasource.name,
            connection_env=datasource.connection_env,
            description=datasource.description,
            instructions=datasource.instructions,
            examples=[
                QueryExampleDoc.model_validate(eg)
                for eg in (datasource.examples or [])
            ],
            schemas=datasource.schemas,
            enabled=datasource.enabled,
            auto_sync=datasource.auto_sync,
        ),
        entities=[
            EntityDoc(
                name=entity.name,
                schema_name=(
                    None
                    if entity.schema_name == default_schema
                    else entity.schema_name
                ),
                label=entity.label,
                description=entity.description,
                synonyms=entity.synonyms,
                visible=entity.visible,
                queryable=(
                    None
                    if entity.queryable == entity.visible
                    else entity.queryable
                ),
                columns=[
                    ColumnDoc.model_validate(_column_doc(column))
                    for column in entity.columns
                ],
            )
            for entity in entities
        ],
        relationships=[
            RelationshipDoc(
                from_=_format_ref(
                    by_id[r.from_entity_id], r.from_columns, default_schema
                ),
                to=_format_ref(
                    by_id[r.to_entity_id], r.to_columns, default_schema
                ),
                description=r.description,
                enabled=r.enabled,
            )
            for r in relationships
        ],
    )


def _parse_entity_ref(ref: str) -> tuple[str, str, str]:
    datasource_id, qualified = ref.split(':', 1)
    schema_name, name = qualified.split('.', 1)
    return datasource_id, schema_name, name


async def _find_entity(session: AsyncSession, ref: str):
    datasource_id, schema_name, name = _parse_entity_ref(ref)
    return await session.scalar(
        select(CatalogEntity).where(
            CatalogEntity.datasource_id == datasource_id,
            CatalogEntity.schema_name == schema_name,
            CatalogEntity.name == name,
        )
    )


async def seed_concepts(
    session: AsyncSession, document: ConceptsFile, *, reset: bool = False
) -> ConceptSeedReport:
    """Cria os conceitos que faltam e vincula as entidades sem conceito.

    Com `reset`, recria os conceitos do arquivo e seus vínculos; conceitos
    que não estão no arquivo ficam como estão.
    """
    report = ConceptSeedReport()
    for doc in document.concepts:
        concept = await session.get(CatalogConcept, doc.id)
        if concept is not None and reset:
            for entity in await session.scalars(
                select(CatalogEntity).where(CatalogEntity.concept_id == doc.id)
            ):
                entity.concept_id = None
            await session.delete(concept)
            await session.flush()
            concept = None
        if concept is None:
            session.add(CatalogConcept(**doc.model_dump(exclude={'entities'})))
            await session.flush()
            report.created += 1
        for ref in doc.entities:
            entity = await _find_entity(session, ref)
            if entity is None:
                report.missing.append(ref)
            elif entity.concept_id is None:
                entity.concept_id = doc.id
                report.linked += 1
    await session.commit()
    return report


async def export_concepts(session: AsyncSession) -> ConceptsFile:
    concepts = await session.scalars(
        select(CatalogConcept).order_by(CatalogConcept.id)
    )
    entities = await session.scalars(
        select(CatalogEntity)
        .where(CatalogEntity.concept_id.is_not(None))
        .order_by(
            CatalogEntity.datasource_id,
            CatalogEntity.schema_name,
            CatalogEntity.name,
        )
    )
    refs: dict[str, list[str]] = {}
    for entity in entities:
        refs.setdefault(entity.concept_id, []).append(
            f'{entity.datasource_id}:{entity.qualified_name}'
        )
    return ConceptsFile(
        concepts=[
            ConceptDoc(
                id=concept.id,
                label=concept.label,
                description=concept.description,
                synonyms=concept.synonyms,
                instructions=concept.instructions,
                entities=refs.get(concept.id, []),
            )
            for concept in concepts
        ]
    )
