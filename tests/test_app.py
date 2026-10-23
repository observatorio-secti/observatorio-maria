from http import HTTPStatus

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from observatorio_maria.app import mount_demo
from observatorio_maria.settings import Settings


async def test_read_root_returns_ok_and_message(client):
    response = await client.get('/')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Olá Mundo!'}


async def test_openapi_exposes_content_block_schemas(client):
    response = await client.get('/openapi.json')

    schemas = response.json()['components']['schemas']
    assert {'TextBlock', 'ChartBlock', 'TableBlock'} <= schemas.keys()


async def test_demo_page_is_mounted(client):
    response = await client.get('/demo/')

    assert response.status_code == HTTPStatus.OK
    assert '<title>Maria · Demo</title>' in response.text


async def test_demo_page_can_be_disabled():
    app = FastAPI()
    mount_demo(app, Settings(_env_file=None, DEMO_ENABLED=False))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        response = await ac.get('/demo/')

    assert response.status_code == HTTPStatus.NOT_FOUND
