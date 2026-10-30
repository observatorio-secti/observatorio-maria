from uuid import uuid4

import pytest

from observatorio_maria.catalog.links import ResolvedLink
from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
)
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.federated_validator import (
    build_federated_schema,
    validate_federated_query,
)


def column(name, **fields):
    data = {
        'name': name,
        'visible': True,
        'present': True,
        'data_type': 'TEXT',
    }
    return CatalogColumn(entity_id=uuid4(), **{**data, **fields})


def entity(source, name, *columns, **fields):
    data = {'visible': True, 'queryable': True, 'present': True}
    item = CatalogEntity(
        datasource_id=source,
        schema_name='public',
        name=name,
        **{**data, **fields},
    )
    item.columns = list(columns)
    return item


def lattes_link(**fields):
    data = {
        'id': uuid4(),
        'from_datasource_id': 'fomento',
        'from_entity': 'public.pesquisadores',
        'from_column': 'lattes',
        'to_datasource_id': 'simcc',
        'to_entity': 'public.researcher',
        'to_column': 'lattes_id',
        'description': None,
        'enabled': True,
        'active': True,
    }
    return ResolvedLink(**{**data, **fields})


def schema(links=None):
    fomento = CatalogDataSource(id='fomento', name='F', connection_env='A')
    simcc = CatalogDataSource(id='simcc', name='S', connection_env='B')
    return build_federated_schema(
        [
            (
                fomento,
                [
                    entity(
                        'fomento',
                        'pesquisadores',
                        column('id'),
                        column('lattes'),
                        column('oculta', visible=False),
                    ),
                    entity(
                        'fomento',
                        'bolsas',
                        column('pesquisador_id'),
                        column('modalidade'),
                        column('cep', access='aggregate'),
                    ),
                    entity('fomento', 'instituicoes', column('nome')),
                    entity('fomento', 'tabela', column('cep')),
                    entity(
                        'fomento',
                        'referencia',
                        column('x'),
                        queryable=False,
                    ),
                ],
            ),
            (
                simcc,
                [
                    entity(
                        'simcc',
                        'researcher',
                        column('id'),
                        column('lattes_id'),
                        column('name', searchable=True),
                    ),
                    entity('simcc', 'institution', column('name')),
                    entity('simcc', 'tabela', column('cep')),
                ],
            ),
        ],
        [lattes_link()] if links is None else links,
    )


JOIN = (
    'SELECT p.id, r.name FROM fomento.public.pesquisadores p '
    'JOIN simcc.public.researcher r ON r.lattes_id = p.lattes'
)


def refused(sql, match, target=None):
    with pytest.raises(QueryValidationError, match=match):
        validate_federated_query(sql, target or schema())


def test_join_by_link_is_accepted():
    result = validate_federated_query(JOIN, schema())

    assert result.sources == ('fomento', 'simcc')
    assert '"fomento"."public"."pesquisadores"' in result.sql


def test_link_in_where_and_reverse_order_are_accepted():
    sql = (
        'SELECT p.id FROM simcc.public.researcher r, '
        'fomento.public.pesquisadores p WHERE p.lattes = r.lattes_id'
    )

    assert validate_federated_query(sql, schema())


def test_in_subquery_by_link_is_accepted():
    sql = (
        'SELECT COUNT(*) FROM fomento.public.pesquisadores p WHERE p.lattes '
        'IN (SELECT r.lattes_id FROM simcc.public.researcher r)'
    )

    assert validate_federated_query(sql, schema())


def test_table_without_full_name_is_refused():
    refused('SELECT id FROM public.pesquisadores', 'nome completo')


def test_single_source_is_refused():
    refused('SELECT id FROM fomento.public.pesquisadores', 'query_data')


def test_unknown_source_is_refused():
    refused('SELECT a FROM outra.public.t', "'outra'")


def test_more_than_two_sources_is_refused():
    target = schema()
    target.source_ids.add('terceira')
    target.queryable_tables['terceira.public.t'] = 't'
    refused(
        JOIN + ' JOIN terceira.public.t t ON t.a = p.id', 'no máximo', target
    )


def test_hidden_column_and_table_are_refused():
    refused(JOIN.replace('p.id', 'p.oculta'), 'oculta')
    refused(
        JOIN + ' JOIN fomento.public.referencia x ON x.x = p.id',
        'somente de referência',
    )


def test_star_is_refused():
    refused(JOIN.replace('p.id, r.name', '*'), 'explicitamente')


def test_aggregate_column_is_refused_only_in_its_source():
    sql = (
        'SELECT b.cep FROM fomento.public.bolsas b '
        'JOIN fomento.public.pesquisadores p ON p.id = b.pesquisador_id '
        'JOIN simcc.public.researcher r ON r.lattes_id = p.lattes'
    )
    refused(sql, 'somente para agregação')
    allowed = sql.replace('b.cep', 'COUNT(DISTINCT b.cep)')
    assert validate_federated_query(allowed, schema())
    same_name = (
        'SELECT t.cep FROM simcc.public.tabela t '
        'JOIN simcc.public.researcher r ON r.id = t.cep '
        'JOIN fomento.public.pesquisadores p ON r.lattes_id = p.lattes'
    )
    assert validate_federated_query(same_name, schema())


@pytest.mark.parametrize(
    ('sql', 'match'),
    [
        (
            "SELECT a FROM postgres_query('fomento', 'select 1')",
            'não permitida',
        ),
        ("SELECT a FROM read_csv('/etc/passwd')", 'não permitida'),
        ("SELECT a FROM '/etc/passwd'", 'nome completo'),
        ("SELECT a FROM 'dados.csv'", 'nome completo'),
    ],
)
def test_external_access_is_refused(sql, match):
    refused(sql, match)


def test_match_text_rewritten_only_on_searchable_column():
    sql = JOIN + " WHERE MATCH_TEXT(r.name, 'Saúde')"
    assert "LIKE '%saude%'" in validate_federated_query(sql, schema()).sql
    refused(JOIN + " WHERE MATCH_TEXT(p.lattes, 'x')", 'busca textual')


def test_join_by_other_columns_is_refused():
    sql = (
        'SELECT i.nome FROM fomento.public.instituicoes i '
        'JOIN simcc.public.institution s ON s.name = i.nome'
    )
    refused(sql, 'ligações declaradas')


def test_undeclared_join_next_to_link_is_refused():
    refused(JOIN + ' AND r.name = p.id', 'ligações declaradas')


def test_cross_join_is_refused():
    sql = (
        'SELECT p.id FROM fomento.public.pesquisadores p '
        'CROSS JOIN simcc.public.researcher r'
    )
    refused(sql, 'ligações declaradas')


def test_other_operator_between_sources_is_refused():
    refused(
        JOIN.replace('r.lattes_id = p.lattes', 'r.lattes_id <> p.lattes'),
        'ligações declaradas',
    )


def test_union_without_link_is_refused():
    sql = (
        'SELECT id FROM fomento.public.pesquisadores '
        'UNION SELECT id FROM simcc.public.researcher'
    )
    refused(sql, 'ligações declaradas')


def test_disabled_link_is_refused():
    target = schema([lattes_link(active=False)])
    refused(JOIN, 'ligações declaradas', target)


def test_cte_cannot_hide_undeclared_join():
    sql = (
        'WITH n AS (SELECT i.nome AS nome '
        'FROM fomento.public.instituicoes i) SELECT n.nome FROM n '
        'JOIN simcc.public.institution s ON s.name = n.nome'
    )
    refused(sql, 'ligações declaradas')


def test_coverage_uses_only_filters_of_the_origin_source():
    sql = (
        'SELECT COUNT(*) AS total FROM fomento.public.bolsas b '
        'JOIN fomento.public.pesquisadores p ON p.id = b.pesquisador_id '
        'JOIN simcc.public.researcher r ON r.lattes_id = p.lattes '
        "WHERE b.modalidade = 'Doutorado' AND r.name = 'Ana'"
    )

    result = validate_federated_query(sql, schema())

    coverage = result.coverage
    assert (coverage.source, coverage.target) == ('fomento', 'simcc')
    assert "'Doutorado'" in coverage.sql
    assert "'Ana'" not in coverage.sql
    assert '"p"."lattes"' in coverage.sql
    assert 'IN (SELECT "lattes_id" FROM "simcc"."public"."researcher")' in (
        coverage.sql
    )


def test_coverage_is_null_with_cte():
    sql = (
        'WITH p AS (SELECT q.lattes AS lattes '
        'FROM fomento.public.pesquisadores q) '
        'SELECT COUNT(*) AS total FROM p '
        'JOIN simcc.public.researcher r ON r.lattes_id = p.lattes'
    )

    result = validate_federated_query(sql, schema())

    assert result.coverage is None
    assert 'CTE' in result.coverage_reason
