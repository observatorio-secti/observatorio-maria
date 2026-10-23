from http import HTTPStatus


async def test_read_root_returns_ok_and_message(client):
    response = await client.get('/')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Olá Mundo!'}


async def test_openapi_exposes_content_block_schemas(client):
    response = await client.get('/openapi.json')

    schemas = response.json()['components']['schemas']
    assert {'TextBlock', 'ChartBlock', 'TableBlock'} <= schemas.keys()
