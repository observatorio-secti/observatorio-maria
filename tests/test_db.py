from http import HTTPStatus

from sqlalchemy import text

from observatorio_maria.database import get_session


def test_database_connection(session):
    result = session.execute(text('SELECT 1')).scalar()
    assert result == 1


def test_get_session():
    session_generator = get_session()
    session = next(session_generator)
    assert session is not None
    session_generator.close()


def test_health_check_endpoint(client):
    response = client.get('/health')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'status': 'ok', 'database': 'connected'}
