import os

from observatorio_maria.settings import Settings


def test_export_environment_exports_extra_dotenv_variables(
    tmp_path, monkeypatch
):
    env_file = tmp_path / '.env'
    env_file.write_text(
        'QUERY_MAX_ROWS=5\n'
        'TEST_EXPORT_SOURCE_URL="sqlite+aiosqlite:///origem.db"\n'
        'TEST_EXPORT_API_KEY=do-arquivo\n',
        encoding='utf-8',
    )
    monkeypatch.delenv('TEST_EXPORT_SOURCE_URL', raising=False)
    monkeypatch.setenv('TEST_EXPORT_API_KEY', 'do-ambiente')

    settings = Settings(_env_file=env_file)
    settings.export_environment()

    assert settings.QUERY_MAX_ROWS == 5  # noqa: PLR2004
    # O nome da variável é preservado: as fontes guardam o nome exato.
    assert os.environ['TEST_EXPORT_SOURCE_URL'] == (
        'sqlite+aiosqlite:///origem.db'
    )
    # O ambiente tem prioridade sobre o .env.
    assert os.environ['TEST_EXPORT_API_KEY'] == 'do-ambiente'
    # Campos do Settings não são exportados.
    assert 'QUERY_MAX_ROWS' not in os.environ
    monkeypatch.delenv('TEST_EXPORT_SOURCE_URL')
