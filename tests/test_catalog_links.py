from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import select

from observatorio_maria.catalog.context import render_source_links
from observatorio_maria.catalog.links import ResolvedLink
from observatorio_maria.catalog.yaml_io import (
    CatalogFile,
    dump_concepts_file,
    export_concepts,
    load_seed_file,
    seed_catalog,
    seed_concepts,
)
from observatorio_maria.models import CatalogDataSource, CatalogSourceLink
from tests.test_catalog_api import entities_by_name, make_visible


def end(column, datasource='origem', entity='pesquisadores'):
    return {
        'datasource_id': datasource,
        'schema_name': 'main',
        'entity': entity,
        'column': column,
    }


@pytest.fixture
async def two_sources(client, datasource, source_db):
    await client.post('/catalog/datasources/origem/sync')
    response = await client.post(
        '/catalog/datasources',
        json={
            'id': 'outra',
            'name': 'Outra',
            'connection_env': 'SOURCE_DATABASE_URL',
            'schemas': ['main'],
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    await client.post('/catalog/datasources/outra/sync')


async def create_link(client, **fields):
    body = {
        'from': end('lattes'),
        'to': end('lattes', 'outra'),
        **fields,
    }
    return await client.post('/catalog/links', json=body)


async def test_create_and_list_link(client, two_sources):
    response = await create_link(client, description='Lattes')

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['from_datasource_id'] == 'origem'
    assert data['to_entity'] == 'main.pesquisadores'
    assert data['active'] is False  # colunas ainda ocultas
    (listed,) = (await client.get('/catalog/links')).json()['links']
    assert listed['id'] == data['id']


async def test_link_is_active_with_visible_columns(client, two_sources):
    await create_link(client)
    await make_visible(client, 'pesquisadores')
    detail = (await entities_by_name(client, 'outra'))['pesquisadores']
    await client.patch(
        f'/catalog/entities/{detail["id"]}',
        json={'visible': True, 'queryable': True},
    )
    columns = (await client.get(f'/catalog/entities/{detail["id"]}')).json()
    for column in columns['columns']:
        await client.patch(
            f'/catalog/columns/{column["id"]}', json={'visible': True}
        )

    (link,) = (await client.get('/catalog/links')).json()['links']
    assert link['active'] is True

    await client.patch(f'/catalog/links/{link["id"]}', json={'enabled': False})

    (link,) = (await client.get('/catalog/links')).json()['links']
    assert link['active'] is False


async def test_same_source_is_rejected(client, two_sources):
    response = await client.post(
        '/catalog/links',
        json={'from': end('lattes'), 'to': end('id')},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_unknown_column_is_rejected(client, two_sources):
    response = await client.post(
        '/catalog/links',
        json={'from': end('nao_existe'), 'to': end('lattes', 'outra')},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'nao_existe' in response.json()['detail']


async def test_repeated_link_is_rejected(client, two_sources):
    await create_link(client)

    repeated = await create_link(client)
    reverse = await client.post(
        '/catalog/links',
        json={'from': end('lattes', 'outra'), 'to': end('lattes')},
    )

    assert repeated.status_code == HTTPStatus.CONFLICT
    assert reverse.status_code == HTTPStatus.CONFLICT


async def test_delete_link(client, two_sources):
    link = (await create_link(client)).json()

    response = await client.delete(f'/catalog/links/{link["id"]}')

    assert response.status_code == HTTPStatus.NO_CONTENT
    missing = await client.delete(f'/catalog/links/{link["id"]}')
    assert missing.status_code == HTTPStatus.NOT_FOUND


async def test_sync_keeps_disabled_link(client, two_sources):
    link = (await create_link(client)).json()
    await client.patch(f'/catalog/links/{link["id"]}', json={'enabled': False})

    await client.post('/catalog/datasources/origem/sync')

    (listed,) = (await client.get('/catalog/links')).json()['links']
    assert listed['enabled'] is False


LINKS_YAML = """
concepts: []
links:
  - from: a:public.p.lattes
    to: b:public.r.lattes_id
    description: Lattes
  - from: a:public.p.lattes
    to: b:public.nao_existe.x
"""


def source_doc(name, table, column):
    return CatalogFile.model_validate({
        'datasource': {'id': name, 'name': name, 'connection_env': 'X'},
        'entities': [{'name': table, 'columns': [{'name': column}]}],
    })


@pytest.fixture
async def seeded(session, tmp_path):
    await seed_catalog(session, source_doc('a', 'p', 'lattes'))
    await seed_catalog(session, source_doc('b', 'r', 'lattes_id'))
    path = tmp_path / 'concepts.yaml'
    path.write_text(LINKS_YAML, encoding='utf-8')
    return path, await seed_concepts(session, load_seed_file(path))


async def test_seed_creates_link_and_warns(seeded):
    _, report = seeded

    assert report.links == 1
    assert report.missing == ['b:public.nao_existe.x']


async def test_seed_keeps_edited_link(session, seeded):
    path, _ = seeded
    link = await session.scalar(select_link())
    link.enabled = False
    await session.commit()

    report = await seed_concepts(session, load_seed_file(path))

    assert report.links == 0
    assert link.enabled is False


async def test_seed_reset_recreates_link(session, seeded):
    path, _ = seeded
    link = await session.scalar(select_link())
    link.enabled = False
    await session.commit()

    report = await seed_concepts(session, load_seed_file(path), reset=True)

    assert report.links == 1
    assert (await session.scalar(select_link())).enabled is True


async def test_export_includes_links(session, seeded):
    text = dump_concepts_file(await export_concepts(session))

    assert 'from: a:public.p.lattes' in text
    assert 'to: b:public.r.lattes_id' in text


def select_link():
    return select(CatalogSourceLink)


def resolved(**overrides):
    data = {
        'id': uuid4(),
        'from_datasource_id': 'fomento',
        'from_entity': 'public.pesquisadores',
        'from_column': 'lattes',
        'to_datasource_id': 'simcc',
        'to_entity': 'public.researcher',
        'to_column': 'lattes_id',
        'description': 'Lattes',
        'enabled': True,
        'active': True,
    }
    return ResolvedLink(**{**data, **overrides})


SOURCES = [
    CatalogDataSource(id='fomento', name='Fomento', connection_env='A'),
    CatalogDataSource(id='simcc', name='Simcc', connection_env='B'),
]


def test_active_link_is_in_context():
    text = render_source_links([resolved()], SOURCES)

    assert text.startswith('# Consultas entre fontes')
    assert 'query_across_sources' in text
    assert (
        '`fomento.public.pesquisadores.lattes` = '
        '`simcc.public.researcher.lattes_id`: Lattes'
    ) in text


def test_inactive_link_is_not_in_context():
    assert not render_source_links([resolved(active=False)], SOURCES)


def test_link_with_source_out_is_not_in_context():
    assert not render_source_links([resolved()], SOURCES[:1])
