from http import HTTPStatus

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from observatorio_maria.app import apply_root_path, mount_demo
from observatorio_maria.settings import Settings


async def test_read_root_returns_ok_and_message(client):
    response = await client.get('/')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Olá Mundo!'}


async def test_openapi_exposes_content_block_schemas(client):
    response = await client.get('/openapi.json')

    schemas = response.json()['components']['schemas']
    assert {'TextBlock', 'ChartBlock', 'TableBlock'} <= schemas.keys()


def _app_behind_proxy():
    app = FastAPI()
    settings = Settings(_env_file=None, ROOT_PATH='/api-maria/')
    apply_root_path(app, settings)
    mount_demo(app, settings)

    @app.get('/health')
    async def health():
        return {'status': 'ok'}

    return AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    )


async def test_swagger_uses_public_prefix_behind_proxy():
    async with _app_behind_proxy() as ac:
        swagger = await ac.get('/docs')
        direct = await ac.get('/openapi.json')
        prefixed = await ac.get('/api-maria/openapi.json')

    assert "url: '/api-maria/openapi.json'" in swagger.text
    assert direct.json()['servers'] == [{'url': '/api-maria'}]
    assert prefixed.status_code == HTTPStatus.OK


@pytest.mark.parametrize('prefix', ['', '/api-maria'])
@pytest.mark.parametrize('path', ['/health', '/demo/', '/demo/app.js'])
async def test_app_answers_whether_proxy_strips_prefix_or_not(prefix, path):
    async with _app_behind_proxy() as ac:
        response = await ac.get(f'{prefix}{path}')

    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize('prefix', ['', '/api-maria'])
async def test_demo_redirect_keeps_public_prefix(prefix):
    async with _app_behind_proxy() as ac:
        response = await ac.get(f'{prefix}/demo')

    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert response.headers['location'] == 'http://test/api-maria/demo/'


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
