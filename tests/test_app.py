from http import HTTPStatus

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from observatorio_maria.app import app, mount_demo
from observatorio_maria.settings import Settings


async def test_read_root_returns_ok_and_message(client):
    response = await client.get('/')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Olá Mundo!'}


async def test_openapi_exposes_content_block_schemas(client):
    response = await client.get('/openapi.json')

    schemas = response.json()['components']['schemas']
    assert {'TextBlock', 'ChartBlock', 'TableBlock'} <= schemas.keys()


async def test_swagger_uses_public_prefix_behind_proxy(monkeypatch):
    monkeypatch.setenv('ROOT_PATH', '/api-maria')
    monkeypatch.setattr(app, 'root_path', Settings().ROOT_PATH)
    monkeypatch.setattr(app, 'openapi_schema', None)
    monkeypatch.setattr(app, 'servers', [])
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        swagger = await ac.get('/docs')
        direct = await ac.get('/openapi.json')
        prefixed = await ac.get('/api-maria/openapi.json')

    assert "url: '/api-maria/openapi.json'" in swagger.text
    assert direct.json()['servers'] == [{'url': '/api-maria'}]
    assert prefixed.status_code == HTTPStatus.OK


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
