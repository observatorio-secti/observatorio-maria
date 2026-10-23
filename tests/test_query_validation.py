from pathlib import Path

import pytest

from observatorio_maria.catalog.yaml_io import load_catalog_file
from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
    ColumnAccess,
)
from observatorio_maria.query.match_text import normalize_term
from observatorio_maria.query.validator import (
    QueryValidationError,
    build_query_schema,
    validate_query,
)


@pytest.fixture
def fomento_schema():
    fomento_path = Path('catalog/fomento.yaml')
    doc = load_catalog_file(fomento_path)
    entities = []
    for ed in doc.entities:
        e = CatalogEntity(
            datasource_id='fomento',
            schema_name=ed.schema_name or 'public',
            name=ed.name,
            visible=ed.visible,
            queryable=ed.visible if ed.queryable is None else ed.queryable,
            present=True,
        )
        for cd in ed.columns:
            c = CatalogColumn(
                entity_id=e.id,
                name=cd.name,
                visible=cd.visible,
                access=cd.access,
                searchable=cd.searchable,
                present=True,
            )
            e.columns.append(c)
        entities.append(e)

    ds = CatalogDataSource(
        id='fomento',
        name='Fomento à pesquisa',
        connection_env='FOMENTO_DATABASE_URL',
        schemas=['public'],
    )
    return build_query_schema(ds, entities, dialect='postgres')


@pytest.fixture
def sample_schema():
    ds = CatalogDataSource(
        id='origem',
        name='Origem',
        connection_env='ORIGEM_URL',
        schemas=['main'],
    )
    # Bolsas: queryable, visible, present
    bolsas = CatalogEntity(
        datasource_id='origem',
        schema_name='main',
        name='bolsas',
        visible=True,
        queryable=True,
        present=True,
    )
    bolsas.columns = [
        CatalogColumn(
            entity_id=bolsas.id,
            name='id',
            visible=True,
            present=True,
            data_type='INTEGER',
        ),
        CatalogColumn(
            entity_id=bolsas.id,
            name='status',
            visible=True,
            present=True,
            data_type='TEXT',
        ),
        CatalogColumn(
            entity_id=bolsas.id,
            name='cep_referencia',
            visible=True,
            present=True,
            access=ColumnAccess.AGGREGATE,
            data_type='TEXT',
        ),
        CatalogColumn(
            entity_id=bolsas.id,
            name='coluna_oculta',
            visible=False,
            present=True,
            data_type='TEXT',
        ),
        CatalogColumn(
            entity_id=bolsas.id,
            name='coluna_ausente',
            visible=True,
            present=False,
            data_type='TEXT',
        ),
    ]

    # Projetos: queryable, visible, present, com colunas pesquisáveis
    projetos = CatalogEntity(
        datasource_id='origem',
        schema_name='main',
        name='projetos',
        visible=True,
        queryable=True,
        present=True,
    )
    projetos.columns = [
        CatalogColumn(
            entity_id=projetos.id,
            name='id',
            visible=True,
            present=True,
            data_type='INTEGER',
        ),
        CatalogColumn(
            entity_id=projetos.id,
            name='nome',
            visible=True,
            present=True,
            searchable=True,
            data_type='TEXT',
        ),
        CatalogColumn(
            entity_id=projetos.id,
            name='resumo',
            visible=True,
            present=True,
            searchable=True,
            data_type='TEXT',
        ),
        CatalogColumn(
            entity_id=projetos.id,
            name='ano',
            visible=True,
            present=True,
            searchable=False,
            data_type='INTEGER',
        ),
    ]

    # Referência: visible, present, mas NOT queryable
    referencia = CatalogEntity(
        datasource_id='origem',
        schema_name='main',
        name='tabela_referencia',
        visible=True,
        queryable=False,
        present=True,
    )
    referencia.columns = [
        CatalogColumn(
            entity_id=referencia.id,
            name='id',
            visible=True,
            present=True,
            data_type='INTEGER',
        ),
    ]

    # Oculta: visible=False
    oculta = CatalogEntity(
        datasource_id='origem',
        schema_name='main',
        name='tabela_oculta',
        visible=False,
        queryable=False,
        present=True,
    )

    entities = [bolsas, projetos, referencia, oculta]
    return build_query_schema(ds, entities, dialect='sqlite')


def test_build_query_schema_from_fomento_seed(fomento_schema):
    assert fomento_schema.datasource_id == 'fomento'
    assert 'projetos' in fomento_schema.queryable_tables
    assert 'bolsas' in fomento_schema.queryable_tables
    assert ('projetos', 'nome') in fomento_schema.searchable_columns
    assert ('projetos', 'resumo') in fomento_schema.searchable_columns
    assert ('palavras_chave', 'termo') in fomento_schema.searchable_columns
    assert ('areas_conhecimento', 'termo') in fomento_schema.searchable_columns
    assert ('projetos', 'id') not in fomento_schema.searchable_columns


def test_reject_multiple_statements(sample_schema):
    with pytest.raises(
        QueryValidationError, match='Apenas uma instrução SQL é permitida'
    ):
        validate_query('SELECT 1; DELETE FROM bolsas', sample_schema)


def test_reject_empty_query(sample_schema):
    with pytest.raises(QueryValidationError, match='Consulta vazia'):
        validate_query('   ', sample_schema)


def test_reject_syntax_error(sample_schema):
    with pytest.raises(QueryValidationError, match='Erro de sintaxe SQL'):
        validate_query('SELECT FROM WHERE ;', sample_schema)


def test_reject_non_select(sample_schema):
    with pytest.raises(
        QueryValidationError, match='Apenas consultas SELECT são permitidas'
    ):
        validate_query("UPDATE bolsas SET status = 'REGULAR'", sample_schema)


def test_reject_unknown_and_hidden_entities_with_same_message(sample_schema):
    # Inexistente
    with pytest.raises(
        QueryValidationError, match="Tabela ou view 'fantasma' não encontrada"
    ):
        validate_query('SELECT 1 FROM fantasma', sample_schema)

    # Oculta: deve dar a mesma mensagem sem revelar existência
    with pytest.raises(
        QueryValidationError,
        match="Tabela ou view 'tabela_oculta' não encontrada",
    ):
        validate_query('SELECT 1 FROM tabela_oculta', sample_schema)


def test_reject_reference_only_entity(sample_schema):
    with pytest.raises(
        QueryValidationError,
        match="Entidade 'tabela_referencia' é somente de referência "
        'e não pode ser consultada',
    ):
        validate_query('SELECT 1 FROM tabela_referencia', sample_schema)


def test_reject_asterisk(sample_schema):
    with pytest.raises(
        QueryValidationError, match=r'Selecione as colunas explicitamente'
    ):
        validate_query('SELECT * FROM bolsas', sample_schema)

    with pytest.raises(
        QueryValidationError, match=r'Selecione as colunas explicitamente'
    ):
        validate_query('SELECT b.* FROM bolsas b', sample_schema)


def test_accept_count_star(sample_schema):
    sql = validate_query('SELECT count(*) FROM bolsas', sample_schema)
    assert 'COUNT(*)' in sql


def test_reject_unknown_and_hidden_columns_with_same_message(sample_schema):
    with pytest.raises(
        QueryValidationError, match="Coluna 'coluna_fantasma' não encontrada"
    ):
        validate_query('SELECT coluna_fantasma FROM bolsas', sample_schema)

    with pytest.raises(
        QueryValidationError, match="Coluna 'coluna_oculta' não encontrada"
    ):
        validate_query('SELECT coluna_oculta FROM bolsas', sample_schema)

    with pytest.raises(
        QueryValidationError, match="Coluna 'coluna_ausente' não encontrada"
    ):
        validate_query('SELECT coluna_ausente FROM bolsas', sample_schema)


def test_reject_disallowed_functions(sample_schema):
    with pytest.raises(
        QueryValidationError, match="Função 'pg_sleep' não permitida"
    ):
        validate_query('SELECT pg_sleep(10) FROM bolsas', sample_schema)

    with pytest.raises(
        QueryValidationError, match="Função 'sin' não permitida"
    ):
        validate_query('SELECT sin(id) FROM bolsas', sample_schema)


def test_aggregate_column_rules(sample_schema):
    # Aceito dentro de agregação
    sql1 = validate_query(
        'SELECT count(distinct cep_referencia) FROM bolsas', sample_schema
    )
    assert 'COUNT(DISTINCT' in sql1 or 'count(DISTINCT' in sql1.lower()

    # Aceito fora da lista de seleção (em WHERE ou GROUP BY)
    sql2 = validate_query(
        'SELECT status, count(id) FROM bolsas '
        "WHERE cep_referencia LIKE '40%' GROUP BY status",
        sample_schema,
    )
    assert 'WHERE' in sql2

    # Recusado quando projetado diretamente
    with pytest.raises(
        QueryValidationError,
        match="Coluna 'cep_referencia' é somente para agregação e "
        'não pode ser exibida diretamente',
    ):
        validate_query(
            'SELECT cep_referencia FROM bolsas GROUP BY cep_referencia',
            sample_schema,
        )

    # Recusado em CTE quando projetado fora de agregação
    with pytest.raises(
        QueryValidationError,
        match="Coluna 'cep_referencia' é somente para agregação e "
        'não pode ser exibida diretamente',
    ):
        validate_query(
            'WITH cte AS (SELECT cep_referencia FROM bolsas) '
            'SELECT cep_referencia FROM cte',
            sample_schema,
        )


def test_match_text_rewrite_and_validation(sample_schema):
    # Recusa coluna não pesquisável
    with pytest.raises(
        QueryValidationError, match="Coluna 'ano' não aceita busca textual"
    ):
        validate_query(
            "SELECT nome FROM projetos WHERE MATCH_TEXT(ano, '2024')",
            sample_schema,
        )

    # Recusa termos vazios
    with pytest.raises(
        QueryValidationError, match='Termo de busca textual não pode ser vazio'
    ):
        validate_query(
            "SELECT nome FROM projetos WHERE MATCH_TEXT(resumo, '')",
            sample_schema,
        )

    with pytest.raises(
        QueryValidationError, match='Termo de busca textual não pode ser vazio'
    ):
        validate_query(
            "SELECT nome FROM projetos WHERE MATCH_TEXT(resumo, '   ')",
            sample_schema,
        )

    # Reescrita correta com múltiplos termos e acentos
    sql = validate_query(
        'SELECT nome FROM projetos WHERE '
        "MATCH_TEXT(resumo, 'Dengue', 'Aedes aegypti', 'Saúde')",
        sample_schema,
    )
    assert 'TRANSLATE(LOWER(' in sql or 'translate(lower(' in sql.lower()
    assert '%dengue%' in sql
    assert '%aedes aegypti%' in sql
    assert '%saude%' in sql
    assert 'ESCAPE' in sql


def test_normalize_term_escaping():
    assert normalize_term('DENGUE') == 'dengue'
    assert normalize_term('Arbovirose!') == 'arbovirose!'
    assert normalize_term('Saúde & Inovação') == 'saude & inovacao'
    assert normalize_term('100%_concluído') == '100\\%\\_concluido'
    assert normalize_term("d'água") == "d''agua"
