from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.catalog.context import check_examples, render_context
from observatorio_maria.catalog.drift import check_datasource
from observatorio_maria.catalog.introspection import (
    ConnectionNotConfiguredError,
    Introspector,
    SourceUnavailableError,
    get_introspector,
    resolve_connection_url,
)
from observatorio_maria.catalog.observed import refresh_observed_values
from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
    sync_datasource,
)
from observatorio_maria.catalog.yaml_io import (
    dump_catalog_file,
    export_catalog,
)
from observatorio_maria.database import get_session
from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
    CatalogRelationship,
    ColumnAccess,
)
from observatorio_maria.schemas import (
    CheckResultPublic,
    ColumnPublic,
    ColumnUpdate,
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
    SyncReportPublic,
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
