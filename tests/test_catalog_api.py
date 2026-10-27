import sqlite3
from http import HTTPStatus

import pytest
import yaml

from observatorio_maria.app import app
from observatorio_maria.catalog.introspection import (
    SourceUnavailableError,
    get_introspector,
)

NEW_DATASOURCE = {
    'id': 'fomento',
    'name': 'Fomento',
    'connection_env': 'FOMENTO_DATABASE_URL',
}


@pytest.fixture
async def synced(client, datasource, source_db):
    response = await client.post('/catalog/datasources/origem/sync')
    assert response.status_code == HTTPStatus.OK
    return response.json()


async def entities_by_name(client, datasource_id='origem'):
    response = await client.get(
        f'/catalog/datasources/{datasource_id}/entities'
    )
    return {e['name']: e for e in response.json()['entities']}


async def entity_detail(client, name):
    entity = (await entities_by_name(client))[name]
    return (await client.get(f'/catalog/entities/{entity["id"]}')).json()


# --- Fontes ------------------------------------------------------------------


async def test_create_datasource(client):
    response = await client.post('/catalog/datasources', json=NEW_DATASOURCE)

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['id'] == 'fomento'
    assert data['schemas'] == ['public']
    assert data['enabled'] is True
    assert data['entities_total'] == 0
    assert data['last_synced_at'] is None
    assert data['examples'] == []


async def test_create_datasource_with_examples(client):
    payload = NEW_DATASOURCE | {
        'examples': [
            {
                'question': 'Quantas bolsas ativas?',
                'sql': 'SELECT count(*) FROM bolsas;',
            }
        ]
    }
    response = await client.post('/catalog/datasources', json=payload)

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['examples'] == [
        {
            'question': 'Quantas bolsas ativas?',
            'sql': 'SELECT count(*) FROM bolsas;',
        }
    ]


async def test_update_datasource_examples(client, datasource):
    response = await client.patch(
        '/catalog/datasources/origem',
        json={
            'examples': [
                {
                    'question': 'Nova pergunta?',
                    'sql': 'SELECT 1;',
                }
            ]
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['examples'] == [
        {
            'question': 'Nova pergunta?',
            'sql': 'SELECT 1;',
        }
    ]

    context_res = await client.get('/catalog/datasources/origem/context')
    assert context_res.status_code == HTTPStatus.OK
    assert (
        '## Exemplos de consultas (few-shot)' in context_res.json()['content']
    )


async def test_datasource_never_exposes_connection_url(
    client, synced, source_db
):
    for path in ('', '/export'):
        response = await client.get(f'/catalog/datasources/origem{path}')
        assert 'SOURCE_DATABASE_URL' in response.text
        assert str(source_db) not in response.text


async def test_create_datasource_duplicate_id(client):
    await client.post('/catalog/datasources', json=NEW_DATASOURCE)

    response = await client.post('/catalog/datasources', json=NEW_DATASOURCE)

    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    'changes',
    [
        {'id': 'Fomento!'},
        {'connection_env': 'postgresql://user:senha@host/db'},
        {'schemas': []},
        {'extra': 'campo'},
    ],
)
async def test_create_datasource_invalid(client, changes):
    response = await client.post(
        '/catalog/datasources', json=NEW_DATASOURCE | changes
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_unknown_datasource(client):
    for method, path in [
        ('get', ''),
        ('patch', ''),
        ('delete', ''),
        ('post', '/sync'),
        ('get', '/entities'),
        ('get', '/relationships'),
        ('get', '/context'),
        ('get', '/export'),
    ]:
        kwargs = {'json': {}} if method == 'patch' else {}
        response = await getattr(client, method)(
            f'/catalog/datasources/nada{path}', **kwargs
        )
        assert response.status_code == HTTPStatus.NOT_FOUND, path


async def test_update_datasource(client, datasource):
    response = await client.patch(
        '/catalog/datasources/origem',
        json={'instructions': 'Inclua pendentes.', 'enabled': False},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['instructions'] == 'Inclua pendentes.'
    assert data['enabled'] is False
    assert data['name'] == 'Origem de teste'


async def test_update_datasource_rejects_null_name(client, datasource):
    response = await client.patch(
        '/catalog/datasources/origem', json={'name': None}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_list_datasources_with_counts(client, synced):
    entities = await entities_by_name(client)
    await client.patch(
        f'/catalog/entities/{entities["bolsas"]["id"]}',
        json={'visible': True, 'queryable': True},
    )
    await client.patch(
        f'/catalog/entities/{entities["pesquisadores"]["id"]}',
        json={'visible': True},
    )

    response = await client.get('/catalog/datasources')

    (data,) = response.json()['datasources']
    assert data['entities_total'] == 4  # noqa: PLR2004
    assert data['entities_visible'] == 2  # noqa: PLR2004
    assert data['entities_queryable'] == 1
    assert data['last_synced_at'] is not None


async def test_delete_datasource_removes_catalog(client, synced):
    entity_id = (await entities_by_name(client))['bolsas']['id']

    response = await client.delete('/catalog/datasources/origem')

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert (await client.get('/catalog/datasources')).json() == {
        'datasources': []
    }
    response = await client.get(f'/catalog/entities/{entity_id}')
    assert response.status_code == HTTPStatus.NOT_FOUND


# --- Sincronização -----------------------------------------------------------


async def test_sync_reports_changes(synced):
    assert sorted(synced['added_entities']) == [
        'main.bolsas',
        'main.bolsas_por_status',
        'main.instituicoes',
        'main.pesquisadores',
    ]
    assert synced['missing_entities'] == []
    assert synced['added_relationships'] == 2  # noqa: PLR2004


async def test_sync_without_connection_env(client, datasource, monkeypatch):
    monkeypatch.delenv('SOURCE_DATABASE_URL', raising=False)

    response = await client.post('/catalog/datasources/origem/sync')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'SOURCE_DATABASE_URL' in response.json()['detail']


async def test_sync_unreachable_source_changes_nothing(client, synced):
    async def unavailable(url, schemas):
        raise SourceUnavailableError('Não foi possível ler a origem: recusada')

    app.dependency_overrides[get_introspector] = lambda: unavailable

    response = await client.post('/catalog/datasources/origem/sync')

    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert 'recusada' in response.json()['detail']
    assert all(e['present'] for e in (await entities_by_name(client)).values())


# --- Entidades ---------------------------------------------------------------


async def test_entity_detail_lists_columns(client, synced):
    detail = await entity_detail(client, 'bolsas')

    assert detail['kind'] == 'table'
    assert detail['columns_total'] == 4  # noqa: PLR2004
    assert detail['columns_visible'] == 0
    assert [c['name'] for c in detail['columns']] == [
        'id',
        'status',
        'pesquisador_id',
        'instituicao_id',
    ]
    assert detail['columns'][0]['primary_key'] is True


async def test_make_entity_visible_and_queryable(client, synced):
    entity = (await entities_by_name(client))['bolsas']

    response = await client.patch(
        f'/catalog/entities/{entity["id"]}',
        json={
            'visible': True,
            'queryable': True,
            'label': 'Bolsas',
            'description': 'Bolsas concedidas',
            'synonyms': ['fomento'],
        },
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['visible'] is True
    assert data['queryable'] is True
    assert data['synonyms'] == ['fomento']


async def test_hiding_entity_disables_query(client, synced):
    entity = (await entities_by_name(client))['bolsas']
    path = f'/catalog/entities/{entity["id"]}'
    await client.patch(path, json={'visible': True, 'queryable': True})

    response = await client.patch(path, json={'visible': False})

    assert response.json()['visible'] is False
    assert response.json()['queryable'] is False


async def test_queryable_requires_visible(client, synced):
    entity = (await entities_by_name(client))['bolsas']

    response = await client.patch(
        f'/catalog/entities/{entity["id"]}', json={'queryable': True}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    detail = await entity_detail(client, 'bolsas')
    assert detail['queryable'] is False


async def test_unknown_entity_and_column(client):
    uuid = '00000000-0000-0000-0000-000000000000'
    assert (await client.get(f'/catalog/entities/{uuid}')).status_code == 404  # noqa: PLR2004
    response = await client.patch(f'/catalog/columns/{uuid}', json={})
    assert response.status_code == HTTPStatus.NOT_FOUND


# --- Colunas -----------------------------------------------------------------


async def test_update_column(client, synced):
    status = (await entity_detail(client, 'bolsas'))['columns'][1]

    response = await client.patch(
        f'/catalog/columns/{status["id"]}',
        json={
            'visible': True,
            'access': 'aggregate',
            'searchable': True,
            'description': 'Situação',
            'values': [{'value': 'REGULAR', 'description': 'válida'}],
        },
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['access'] == 'aggregate'
    assert data['searchable'] is True
    assert data['values'] == [{'value': 'REGULAR', 'description': 'válida'}]


async def test_update_column_rejects_null_searchable(client, synced):
    status = (await entity_detail(client, 'bolsas'))['columns'][1]

    response = await client.patch(
        f'/catalog/columns/{status["id"]}', json={'searchable': None}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_update_column_invalid_access(client, synced):
    status = (await entity_detail(client, 'bolsas'))['columns'][1]

    response = await client.patch(
        f'/catalog/columns/{status["id"]}', json={'access': 'secreto'}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- Relacionamentos, prévia e exportação ------------------------------------


async def make_visible(client, *names):
    for name in names:
        detail = await entity_detail(client, name)
        await client.patch(
            f'/catalog/entities/{detail["id"]}',
            json={'visible': True, 'queryable': True},
        )
        for column in detail['columns']:
            await client.patch(
                f'/catalog/columns/{column["id"]}', json={'visible': True}
            )


async def test_list_and_disable_relationship(client, synced):
    await make_visible(client, 'bolsas', 'pesquisadores')
    response = await client.get('/catalog/datasources/origem/relationships')
    relationships = response.json()['relationships']
    assert [
        (r['from_entity'], r['from_columns'], r['to_entity'])
        for r in relationships
    ] == [
        ('main.bolsas', ['instituicao_id'], 'main.instituicoes'),
        ('main.bolsas', ['pesquisador_id'], 'main.pesquisadores'),
    ]
    link = '`main.bolsas.pesquisador_id` -> `main.pesquisadores.id`'
    context = await client.get('/catalog/datasources/origem/context')
    assert link in context.json()['content']

    response = await client.patch(
        f'/catalog/relationships/{relationships[1]["id"]}',
        json={'enabled': False, 'description': 'Bolsista'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['enabled'] is False
    assert response.json()['description'] == 'Bolsista'
    context = await client.get('/catalog/datasources/origem/context')
    assert link not in context.json()['content']


async def test_context_preview(client, synced):
    await make_visible(client, 'bolsas')
    nome_entity = await entity_detail(client, 'pesquisadores')

    response = await client.get('/catalog/datasources/origem/context')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['enabled'] is True
    assert '`main.bolsas` (tabela)' in data['content']
    assert nome_entity['name'] not in data['content'].replace(
        'pesquisador_id', ''
    )


async def test_context_preview_disabled_datasource(client, synced):
    await make_visible(client, 'bolsas')
    await client.patch('/catalog/datasources/origem', json={'enabled': False})

    data = (await client.get('/catalog/datasources/origem/context')).json()

    assert data == {
        'datasource_id': 'origem',
        'enabled': False,
        'content': '',
        'rejected_examples': [],
    }


async def test_export_yaml(client, synced):
    await make_visible(client, 'bolsas')

    response = await client.get('/catalog/datasources/origem/export')

    assert response.status_code == HTTPStatus.OK
    assert response.headers['content-type'].startswith('application/yaml')
    assert 'origem.yaml' in response.headers['content-disposition']
    document = yaml.safe_load(response.text)
    assert document['datasource']['connection_env'] == 'SOURCE_DATABASE_URL'
    entities = {e['name']: e for e in document['entities']}
    assert 'visible' not in entities['bolsas']  # padrão do YAML: visível
    assert entities['instituicoes']['visible'] is False


# --- Defasagem ---------------------------------------------------------------


async def test_datasource_exposes_schema_state(client, synced):
    data = (await client.get('/catalog/datasources/origem')).json()

    assert data['schema_status'] == 'up_to_date'
    assert data['last_checked_at'] is not None
    assert data['drift'] is None
    assert data['check_error'] is None
    assert data['auto_sync'] is False


async def test_check_up_to_date(client, synced):
    response = await client.post('/catalog/datasources/origem/check')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['status'] == 'up_to_date'
    assert data['drift'] is None
    assert data['sync'] is None


async def test_check_outdated_exposes_drift(client, synced, source_db):
    with sqlite3.connect(source_db) as conn:
        conn.execute('ALTER TABLE bolsas ADD COLUMN modalidade TEXT')

    data = (await client.post('/catalog/datasources/origem/check')).json()

    assert data['status'] == 'outdated'
    assert data['drift']['added_columns'] == ['main.bolsas.modalidade']
    datasource = (await client.get('/catalog/datasources/origem')).json()
    assert datasource['schema_status'] == 'outdated'
    assert datasource['drift']['added_columns'] == ['main.bolsas.modalidade']

    await client.post('/catalog/datasources/origem/sync')
    datasource = (await client.get('/catalog/datasources/origem')).json()
    assert datasource['schema_status'] == 'up_to_date'
    assert datasource['drift'] is None


async def test_check_with_auto_sync(client, synced, source_db):
    response = await client.patch(
        '/catalog/datasources/origem', json={'auto_sync': True}
    )
    assert response.json()['auto_sync'] is True
    with sqlite3.connect(source_db) as conn:
        conn.execute('CREATE TABLE projetos (id INTEGER PRIMARY KEY)')

    data = (await client.post('/catalog/datasources/origem/check')).json()

    assert data['status'] == 'up_to_date'
    assert data['sync']['added_entities'] == ['main.projetos']
    assert 'projetos' in await entities_by_name(client)


async def test_check_error(client, synced, monkeypatch):
    monkeypatch.delenv('SOURCE_DATABASE_URL')

    data = (await client.post('/catalog/datasources/origem/check')).json()

    assert data['status'] == 'error'
    assert 'SOURCE_DATABASE_URL' in data['error']
    datasource = (await client.get('/catalog/datasources/origem')).json()
    assert datasource['schema_status'] == 'error'
    assert 'SOURCE_DATABASE_URL' in datasource['check_error']


async def test_check_unknown_datasource(client):
    response = await client.post('/catalog/datasources/nada/check')

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_column_exposes_enum_review_fields(client, synced):
    status = (await entity_detail(client, 'bolsas'))['columns'][1]

    assert status['enum_values'] is None
    assert status['undescribed_values'] == []
    assert status['obsolete_values'] == []


async def test_export_includes_auto_sync(client, synced):
    await client.patch('/catalog/datasources/origem', json={'auto_sync': True})

    response = await client.get('/catalog/datasources/origem/export')

    assert yaml.safe_load(response.text)['datasource']['auto_sync'] is True
