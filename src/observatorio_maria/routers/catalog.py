from dataclasses import asdict
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.catalog.context import (
    check_examples,
    load_concept_labels,
    load_concepts_context,
    render_context,
)
from observatorio_maria.catalog.drift import check_datasource
from observatorio_maria.catalog.introspection import (
    ConnectionNotConfiguredError,
    Introspector,
    SourceUnavailableError,
    get_introspector,
    resolve_connection_url,
)
from observatorio_maria.catalog.links import (
    find_entity,
    has_column,
    load_links,
    resolve_link,
)
from observatorio_maria.catalog.observed import refresh_observed_values
from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
    sync_datasource,
)
from observatorio_maria.catalog.yaml_io import (
    dump_catalog_file,
    dump_concepts_file,
    export_catalog,
    export_concepts,
)
from observatorio_maria.database import get_session
from observatorio_maria.models import (
    CatalogColumn,
    CatalogConcept,
    CatalogDataSource,
    CatalogEntity,
    CatalogRelationship,
    CatalogSourceLink,
    ColumnAccess,
)
from observatorio_maria.schemas import (
    CheckResultPublic,
    ColumnPublic,
    ColumnUpdate,
    ConceptContextPreview,
    ConceptCreate,
    ConceptEntity,
    ConceptList,
    ConceptPublic,
    ConceptUpdate,
    ContextPreview,
    DataSourceCreate,
    DataSourceList,
    DataSourcePublic,
    DataSourceUpdate,
    EntityDetail,
    EntityList,
    EntityUpdate,
    RelationshipList,
    RelationshipPublic,
    RelationshipUpdate,
    SourceLinkCreate,
    SourceLinkList,
    SourceLinkPublic,
    SourceLinkUpdate,
    SyncReportPublic,
)
from observatorio_maria.services.chat import (
    get_consultable_sources_and_contexts,
)

router = APIRouter(prefix='/catalog', tags=['catalog'])

Session = Annotated[AsyncSession, Depends(get_session)]


def not_found(detail: str):
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=detail)


async def get_datasource(datasource_id: str, session: Session):
    datasource = await session.get(CatalogDataSource, datasource_id)
    if not datasource:
        raise not_found('Fonte de dados não encontrada')
    return datasource


async def get_entity(entity_id: UUID, session: Session):
    entity = await session.get(CatalogEntity, entity_id)
    if not entity:
        raise not_found('Entidade não encontrada')
    return entity


CurrentDataSource = Annotated[CatalogDataSource, Depends(get_datasource)]
CurrentEntity = Annotated[CatalogEntity, Depends(get_entity)]


async def with_counts(session: AsyncSession, datasources):
    rows = await session.execute(
        select(
            CatalogEntity.datasource_id,
            func.count(),
            func.count().filter(CatalogEntity.visible),
            func.count().filter(CatalogEntity.queryable),
        )
        .where(CatalogEntity.datasource_id.in_([d.id for d in datasources]))
        .group_by(CatalogEntity.datasource_id)
    )
    counts = {row[0]: row[1:] for row in rows}
    result = []
    for datasource in datasources:
        total, visible, queryable = counts.get(datasource.id, (0, 0, 0))
        result.append(
            DataSourcePublic.model_validate(datasource).model_copy(
                update={
                    'entities_total': total,
                    'entities_visible': visible,
                    'entities_queryable': queryable,
                }
            )
        )
    return result


def entity_payload(entity: CatalogEntity, *, detail: bool = False):
    payload = {
        **{
            field: getattr(entity, field)
            for field in (
                'id',
                'datasource_id',
                'schema_name',
                'name',
                'kind',
                'label',
                'description',
                'synonyms',
                'concept_id',
                'visible',
                'queryable',
                'present',
            )
        },
        'columns_total': len(entity.columns),
        'columns_visible': sum(c.visible for c in entity.columns),
    }
    if detail:
        payload['columns'] = entity.columns
    return payload


async def relationship_payloads(session, relationships):
    names = {
        entity.id: entity.qualified_name
        for entity in await session.scalars(
            select(CatalogEntity).where(
                CatalogEntity.id.in_({
                    entity_id
                    for r in relationships
                    for entity_id in (r.from_entity_id, r.to_entity_id)
                })
            )
        )
    }
    return [
        RelationshipPublic(
            id=r.id,
            from_entity_id=r.from_entity_id,
            from_entity=names[r.from_entity_id],
            from_columns=r.from_columns,
            to_entity_id=r.to_entity_id,
            to_entity=names[r.to_entity_id],
            to_columns=r.to_columns,
            origin=r.origin,
            description=r.description,
            enabled=r.enabled,
            present=r.present,
        )
        for r in relationships
    ]


# --- Fontes de dados ---------------------------------------------------------


@router.get('/datasources', response_model=DataSourceList)
async def list_datasources(session: Session):
    datasources = await session.scalars(
        select(CatalogDataSource).order_by(CatalogDataSource.name)
    )
    return {'datasources': await with_counts(session, datasources.all())}


@router.post(
    '/datasources',
    status_code=HTTPStatus.CREATED,
    response_model=DataSourcePublic,
)
async def create_datasource(data: DataSourceCreate, session: Session):
    if await session.get(CatalogDataSource, data.id):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Já existe uma fonte de dados com esse identificador',
        )
    datasource = CatalogDataSource(**data.model_dump())
    session.add(datasource)
    await session.commit()
    return datasource


@router.get('/datasources/{datasource_id}', response_model=DataSourcePublic)
async def read_datasource(datasource: CurrentDataSource, session: Session):
    (result,) = await with_counts(session, [datasource])
    return result


@router.patch('/datasources/{datasource_id}', response_model=DataSourcePublic)
async def update_datasource(
    data: DataSourceUpdate, datasource: CurrentDataSource, session: Session
):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(datasource, field, value)
    await session.commit()
    (result,) = await with_counts(session, [datasource])
    return result


@router.delete(
    '/datasources/{datasource_id}', status_code=HTTPStatus.NO_CONTENT
)
async def delete_datasource(datasource: CurrentDataSource, session: Session):
    for item in [
        *await load_relationships(session, datasource.id),
        *await load_entities(session, datasource.id),
        datasource,
    ]:
        await session.delete(item)
    await session.commit()


@router.post(
    '/datasources/{datasource_id}/sync', response_model=SyncReportPublic
)
async def sync(
    datasource: CurrentDataSource,
    session: Session,
    introspect: Annotated[Introspector, Depends(get_introspector)],
):
    try:
        url = resolve_connection_url(datasource.connection_env)
        snapshot = await introspect(url, datasource.schemas)
    except ConnectionNotConfiguredError as exc:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except SourceUnavailableError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY, detail=str(exc)
        ) from exc
    report = await sync_datasource(session, datasource, snapshot)
    await refresh_observed_values(session, datasource)
    return report


@router.post(
    '/datasources/{datasource_id}/check', response_model=CheckResultPublic
)
async def check(
    datasource: CurrentDataSource,
    session: Session,
    introspect: Annotated[Introspector, Depends(get_introspector)],
):
    """Compara o schema atual da origem com a última sincronização."""
    return await check_datasource(session, datasource, introspect)


@router.get(
    '/datasources/{datasource_id}/context', response_model=ContextPreview
)
async def preview_context(datasource: CurrentDataSource, session: Session):
    entities = await load_entities(session, datasource.id)
    content = render_context(
        datasource,
        entities,
        await load_relationships(session, datasource.id),
        await load_concept_labels(session),
    )
    _, rejected = check_examples(datasource, entities)
    return ContextPreview(
        datasource_id=datasource.id,
        enabled=datasource.enabled,
        content=content,
        rejected_examples=rejected,
    )


@router.get(
    '/datasources/{datasource_id}/export',
    response_class=Response,
    responses={200: {'content': {'application/yaml': {}}}},
)
async def export_datasource(datasource: CurrentDataSource, session: Session):
    document = await export_catalog(session, datasource)
    return Response(
        dump_catalog_file(document),
        media_type='application/yaml',
        headers={
            'Content-Disposition': (
                f'attachment; filename="{datasource.id}.yaml"'
            )
        },
    )


# --- Entidades e colunas -----------------------------------------------------


@router.get('/datasources/{datasource_id}/entities', response_model=EntityList)
async def list_entities(datasource: CurrentDataSource, session: Session):
    entities = await load_entities(session, datasource.id)
    return {'entities': [entity_payload(e) for e in entities]}


@router.get('/entities/{entity_id}', response_model=EntityDetail)
async def read_entity(entity: CurrentEntity):
    return entity_payload(entity, detail=True)


@router.patch('/entities/{entity_id}', response_model=EntityDetail)
async def update_entity(
    data: EntityUpdate, entity: CurrentEntity, session: Session
):
    changes = data.model_dump(exclude_unset=True)
    # Consultável implica visível: ocultar desliga a consulta, e ligar a
    # consulta de uma entidade que continua oculta é rejeitado.
    if not changes.get('visible', entity.visible):
        if changes.get('queryable'):
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail='Uma entidade consultável precisa ser visível',
            )
        changes['queryable'] = False
    concept_id = changes.get('concept_id')
    if concept_id and not await session.get(CatalogConcept, concept_id):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f"Conceito '{concept_id}' não encontrado",
        )
    for field, value in changes.items():
        setattr(entity, field, value)
    await session.commit()
    return entity_payload(entity, detail=True)


@router.patch('/columns/{column_id}', response_model=ColumnPublic)
async def update_column(column_id: UUID, data: ColumnUpdate, session: Session):
    column = await session.get(CatalogColumn, column_id)
    if not column:
        raise not_found('Coluna não encontrada')
    for field, value in data.model_dump(
        mode='json', exclude_unset=True
    ).items():
        setattr(column, field, value)
    if column.access == ColumnAccess.AGGREGATE:
        # Valores lidos dos dados não ficam guardados em coluna sensível.
        column.observed_values = None
    await session.commit()
    return column


# --- Conceitos ---------------------------------------------------------------


async def get_concept(concept_id: str, session: Session):
    concept = await session.get(CatalogConcept, concept_id)
    if not concept:
        raise not_found('Conceito não encontrado')
    return concept


CurrentConcept = Annotated[CatalogConcept, Depends(get_concept)]


async def concept_payloads(session: AsyncSession, concepts):
    entities = await session.scalars(
        select(CatalogEntity)
        .where(CatalogEntity.concept_id.in_([c.id for c in concepts]))
        .order_by(
            CatalogEntity.datasource_id,
            CatalogEntity.schema_name,
            CatalogEntity.name,
        )
    )
    by_concept: dict[str, list] = {}
    for entity in entities:
        by_concept.setdefault(entity.concept_id, []).append(entity)
    return [
        ConceptPublic.model_validate(concept).model_copy(
            update={
                'entities': [
                    ConceptEntity(
                        id=e.id,
                        datasource_id=e.datasource_id,
                        schema_name=e.schema_name,
                        name=e.name,
                        label=e.label,
                    )
                    for e in by_concept.get(concept.id, [])
                ]
            }
        )
        for concept in concepts
    ]


@router.get('/concepts', response_model=ConceptList)
async def list_concepts(session: Session):
    concepts = await session.scalars(
        select(CatalogConcept).order_by(CatalogConcept.label)
    )
    return {'concepts': await concept_payloads(session, concepts.all())}


@router.post(
    '/concepts', status_code=HTTPStatus.CREATED, response_model=ConceptPublic
)
async def create_concept(data: ConceptCreate, session: Session):
    if await session.get(CatalogConcept, data.id):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Já existe um conceito com esse identificador',
        )
    concept = CatalogConcept(**data.model_dump())
    session.add(concept)
    await session.commit()
    (payload,) = await concept_payloads(session, [concept])
    return payload


@router.get('/concepts/context', response_model=ConceptContextPreview)
async def preview_concepts_context(session: Session):
    """Seção de conceitos para as fontes que entram hoje no prompt."""
    datasources, _ = await get_consultable_sources_and_contexts(session)
    return {'content': await load_concepts_context(session, datasources)}


@router.get(
    '/concepts/export',
    response_class=Response,
    responses={200: {'content': {'application/yaml': {}}}},
)
async def export_concepts_yaml(session: Session):
    return Response(
        dump_concepts_file(await export_concepts(session)),
        media_type='application/yaml',
        headers={
            'Content-Disposition': 'attachment; filename="concepts.yaml"'
        },
    )


@router.get('/concepts/{concept_id}', response_model=ConceptPublic)
async def read_concept(concept: CurrentConcept, session: Session):
    (payload,) = await concept_payloads(session, [concept])
    return payload


@router.patch('/concepts/{concept_id}', response_model=ConceptPublic)
async def update_concept(
    data: ConceptUpdate, concept: CurrentConcept, session: Session
):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(concept, field, value)
    await session.commit()
    (payload,) = await concept_payloads(session, [concept])
    return payload


@router.delete('/concepts/{concept_id}', status_code=HTTPStatus.NO_CONTENT)
async def delete_concept(concept: CurrentConcept, session: Session):
    # As entidades ficam sem conceito (ON DELETE SET NULL); o mesmo é feito
    # na sessão, para os objetos já carregados não ficarem desatualizados.
    for entity in await session.scalars(
        select(CatalogEntity).where(CatalogEntity.concept_id == concept.id)
    ):
        entity.concept_id = None
    await session.delete(concept)
    await session.commit()


# --- Ligações entre fontes ---------------------------------------------------


async def get_source_link(link_id: UUID, session: Session):
    link = await session.get(CatalogSourceLink, link_id)
    if not link:
        raise not_found('Ligação não encontrada')
    return link


CurrentSourceLink = Annotated[CatalogSourceLink, Depends(get_source_link)]


async def link_end(session: AsyncSession, end) -> CatalogEntity:
    entity = await find_entity(
        session, end.datasource_id, end.schema_name, end.entity
    )
    if not entity or not await has_column(session, entity, end.column):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=(
                f"Coluna '{end.datasource_id}:{end.schema_name}."
                f"{end.entity}.{end.column}' não encontrada"
            ),
        )
    return entity


async def link_payload(session: AsyncSession, link: CatalogSourceLink):
    source = await session.get(CatalogEntity, link.from_entity_id)
    target = await session.get(CatalogEntity, link.to_entity_id)
    return SourceLinkPublic(**asdict(resolve_link(link, source, target)))


@router.get('/links', response_model=SourceLinkList)
async def list_source_links(session: Session):
    links = await load_links(session)
    return {'links': [SourceLinkPublic(**asdict(r)) for r in links]}


@router.post(
    '/links',
    status_code=HTTPStatus.CREATED,
    response_model=SourceLinkPublic,
)
async def create_source_link(data: SourceLinkCreate, session: Session):
    source = await link_end(session, data.source)
    target = await link_end(session, data.target)
    if source.datasource_id == target.datasource_id:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='Uma ligação precisa unir duas fontes diferentes',
        )
    pairs = {
        (source.id, data.source.column, target.id, data.target.column),
        (target.id, data.target.column, source.id, data.source.column),
    }
    existing = await session.scalars(select(CatalogSourceLink))
    if any(
        (e.from_entity_id, e.from_column, e.to_entity_id, e.to_column) in pairs
        for e in existing
    ):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Já existe uma ligação entre essas colunas',
        )
    link = CatalogSourceLink(
        from_entity_id=source.id,
        from_column=data.source.column,
        to_entity_id=target.id,
        to_column=data.target.column,
        description=data.description,
        enabled=data.enabled,
    )
    session.add(link)
    await session.commit()
    return await link_payload(session, link)


@router.patch('/links/{link_id}', response_model=SourceLinkPublic)
async def update_source_link(
    data: SourceLinkUpdate, link: CurrentSourceLink, session: Session
):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(link, field, value)
    await session.commit()
    return await link_payload(session, link)


@router.delete('/links/{link_id}', status_code=HTTPStatus.NO_CONTENT)
async def delete_source_link(link: CurrentSourceLink, session: Session):
    await session.delete(link)
    await session.commit()


# --- Relacionamentos ---------------------------------------------------------


@router.get(
    '/datasources/{datasource_id}/relationships',
    response_model=RelationshipList,
)
async def list_relationships(datasource: CurrentDataSource, session: Session):
    relationships = await load_relationships(session, datasource.id)
    payloads = await relationship_payloads(session, relationships)
    payloads.sort(key=lambda r: (r.from_entity, r.from_columns, r.to_entity))
    return {'relationships': payloads}


@router.patch(
    '/relationships/{relationship_id}', response_model=RelationshipPublic
)
async def update_relationship(
    relationship_id: UUID, data: RelationshipUpdate, session: Session
):
    relationship = await session.get(CatalogRelationship, relationship_id)
    if not relationship:
        raise not_found('Relacionamento não encontrado')
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(relationship, field, value)
    await session.commit()
    (payload,) = await relationship_payloads(session, [relationship])
    return payload
