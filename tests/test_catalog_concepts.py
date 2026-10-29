from http import HTTPStatus

import pytest

from tests.test_catalog_api import entities_by_name

PROJETOS = {
    'id': 'projetos',
    'label': 'Projetos',
    'description': 'Projetos de pesquisa.',
    'synonyms': ['projeto'],
    'instructions': '- No fomento são projetos com bolsa.',
}


@pytest.fixture
async def synced(client, datasource, source_db):
    response = await client.post('/catalog/datasources/origem/sync')
    assert response.status_code == HTTPStatus.OK


@pytest.fixture
async def concept(client):
    response = await client.post('/catalog/concepts', json=PROJETOS)
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


async def link(client, entity_name, concept_id):
    entity = (await entities_by_name(client))[entity_name]
    return await client.patch(
        f'/catalog/entities/{entity["id"]}', json={'concept_id': concept_id}
    )


async def test_create_and_list_concept(client, concept):
    assert concept['entities'] == []

    response = await client.get('/catalog/concepts')

    assert response.status_code == HTTPStatus.OK
    (listed,) = response.json()['concepts']
    assert listed['id'] == 'projetos'
    assert listed['instructions'] == PROJETOS['instructions']


async def test_concept_id_must_be_unique(client, concept):
    response = await client.post('/catalog/concepts', json=PROJETOS)

    assert response.status_code == HTTPStatus.CONFLICT
    assert len((await client.get('/catalog/concepts')).json()['concepts']) == 1


async def test_update_concept_keeps_id(client, concept):
    response = await client.patch(
        '/catalog/concepts/projetos', json={'instructions': 'Nova política.'}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['instructions'] == 'Nova política.'
    rejected = await client.patch(
        '/catalog/concepts/projetos', json={'id': 'outro'}
    )
    assert rejected.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_unknown_concept(client):
    response = await client.get('/catalog/concepts/nao-existe')

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_link_entity_to_concept(client, synced, concept):
    response = await link(client, 'bolsas', 'projetos')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['concept_id'] == 'projetos'
    assert (await entities_by_name(client))['bolsas']['concept_id'] == (
        'projetos'
    )
    detail = (await client.get('/catalog/concepts/projetos')).json()
    assert [(e['datasource_id'], e['name']) for e in detail['entities']] == [
        ('origem', 'bolsas')
    ]


async def test_unlink_entity(client, synced, concept):
    await link(client, 'bolsas', 'projetos')

    response = await link(client, 'bolsas', None)

    assert response.json()['concept_id'] is None


async def test_link_to_unknown_concept(client, synced):
    response = await link(client, 'bolsas', 'nao-existe')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_delete_concept_keeps_entities(client, synced, concept):
    await link(client, 'bolsas', 'projetos')
    await link(client, 'instituicoes', 'projetos')

    response = await client.delete('/catalog/concepts/projetos')

    assert response.status_code == HTTPStatus.NO_CONTENT
    entities = await entities_by_name(client)
    assert entities['bolsas']['concept_id'] is None
    assert entities['instituicoes']['concept_id'] is None
    assert (await client.get('/catalog/concepts')).json()['concepts'] == []
