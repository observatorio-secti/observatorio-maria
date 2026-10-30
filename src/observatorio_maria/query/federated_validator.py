"""Validação de consultas entre fontes, contra vários catálogos.

As regras de consulta são as de `validator.py`; aqui as tabelas têm o nome
completo (`fonte.schema.tabela`), as chaves levam a fonte e as fontes só se
juntam por ligações declaradas no catálogo.
"""

from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope
from sqlglot.schema import MappingSchema

from observatorio_maria.catalog.links import ResolvedLink
from observatorio_maria.models import (
    CatalogDataSource,
    CatalogEntity,
    ColumnAccess,
)
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.match_text import rewrite_match_text
from observatorio_maria.query.validator import (
    _check_aggregate_columns,
    _check_functions,
    _check_limit,
    _check_stars,
    _check_statement,
    _qualify_query,
)

DIALECT = 'duckdb'
MAX_SOURCES = 2

COMPARISONS = (
    exp.EQ,
    exp.NEQ,
    exp.GT,
    exp.GTE,
    exp.LT,
    exp.LTE,
    exp.Like,
    exp.ILike,
    exp.In,
    exp.Between,
)


@dataclass(frozen=True)
class FederatedSchema:
    """Itens visíveis e presentes, com chave `fonte.schema.tabela`."""

    dialect: str
    mapping_schema: MappingSchema
    links: list[ResolvedLink]
    source_ids: set[str]
    queryable_tables: dict[str, str] = field(default_factory=dict)
    reference_only_tables: set[str] = field(default_factory=set)
    aggregate_columns: set[tuple[str, str]] = field(default_factory=set)
    searchable_columns: set[tuple[str, str]] = field(default_factory=set)


@dataclass(frozen=True)
class CoverageQuery:
    """Conta as chaves da fonte de origem e as encontradas na outra."""

    sql: str
    source: str
    target: str


@dataclass(frozen=True)
class FederatedQuery:
    sql: str
    sources: tuple[str, ...]
    coverage: CoverageQuery | None = None
    coverage_reason: str | None = None


def build_federated_schema(
    sources: list[tuple[CatalogDataSource, list[CatalogEntity]]],
    links: list[ResolvedLink],
) -> FederatedSchema:
    """Monta o schema das fontes ativas, para validar uma consulta."""
    tables: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
    queryable: dict[str, str] = {}
    reference_only: set[str] = set()
    aggregate: set[tuple[str, str]] = set()
    searchable: set[tuple[str, str]] = set()

    for datasource, entities in sources:
        for entity in entities:
            if not entity.visible or not entity.present:
                continue
            key = f'{datasource.id}.{entity.qualified_name}'.lower()
            if not entity.queryable:
                reference_only.add(key)
                continue
            queryable[key] = entity.name
            columns: dict[str, str] = {}
            for column in entity.columns:
                if not column.visible or not column.present:
                    continue
                name = column.name.lower()
                columns[name] = column.data_type or 'text'
                if column.access == ColumnAccess.AGGREGATE:
                    aggregate.add((key, name))
                if column.searchable:
                    searchable.add((key, name))
            schemas = tables.setdefault(datasource.id.lower(), {})
            schemas.setdefault(entity.schema_name.lower(), {})[
                entity.name.lower()
            ] = columns

    return FederatedSchema(
        dialect=DIALECT,
        mapping_schema=MappingSchema(tables, dialect=DIALECT),
        links=[link for link in links if link.active],
        source_ids={datasource.id.lower() for datasource, _ in sources},
        queryable_tables=queryable,
        reference_only_tables=reference_only,
        aggregate_columns=aggregate,
        searchable_columns=searchable,
    )


def _table_key(table: exp.Table) -> str:
    return f'{table.catalog}.{table.db}.{table.name}'.lower()


def _check_tables(stmt: exp.Expression, schema: FederatedSchema) -> set[str]:
    """Confere as tabelas e devolve as fontes citadas."""
    ctes = {cte.alias_or_name.lower() for cte in stmt.find_all(exp.CTE)}
    sources: set[str] = set()
    for table in stmt.find_all(exp.Table):
        if not table.db and table.name.lower() in ctes:
            continue
        if not (table.catalog and table.db):
            raise QueryValidationError(
                f"Use o nome completo da tabela '{table.name}': "
                'fonte.schema.tabela'
            )
        key = _table_key(table)
        if table.catalog.lower() not in schema.source_ids:
            raise QueryValidationError(
                f"Fonte '{table.catalog}' não encontrada ou desativada"
            )
        if key in schema.reference_only_tables:
            raise QueryValidationError(
                f"Entidade '{table.name}' é somente de referência e não "
                'pode ser consultada'
            )
        if key not in schema.queryable_tables:
            raise QueryValidationError(
                f"Tabela ou view '{table.name}' não encontrada"
            )
        sources.add(table.catalog.lower())
    return sources


def _check_source_count(sources: set[str]) -> None:
    if len(sources) < MAX_SOURCES:
        raise QueryValidationError(
            'A consulta cita uma só fonte: use a ferramenta query_data'
        )
    if len(sources) > MAX_SOURCES:
        raise QueryValidationError(
            f'Uma consulta entre fontes aceita no máximo {MAX_SOURCES} fontes'
        )


def _alias_sources(qualified: exp.Expression) -> dict[str, Any]:
    """Tabelas e derivadas por alias, nos escopos da consulta."""
    sources: dict[str, Any] = {}
    for scope in traverse_scope(qualified):
        for alias, source in scope.sources.items():
            known = sources.get(alias)
            if (
                isinstance(known, exp.Table)
                and isinstance(source, exp.Table)
                and _table_key(known) != _table_key(source)
            ):
                raise QueryValidationError(
                    f"O alias '{alias}' aponta para tabelas diferentes: "
                    'use aliases distintos'
                )
            sources[alias] = source
    return sources


def _column_origin(
    column: exp.Column, sources: dict[str, Any], depth: int = 0
) -> tuple[str, str] | None:
    """Tabela e coluna de origem, seguindo projeções simples de CTEs e
    subconsultas; None quando a coluna é calculada."""
    source = sources.get(column.table)
    if isinstance(source, exp.Table):
        return _table_key(source), column.name.lower()
    select = getattr(source, 'expression', None)
    if not isinstance(select, exp.Select) or depth > 8:  # noqa: PLR2004
        return None
    for projection in select.expressions:
        if projection.alias_or_name.lower() != column.name.lower():
            continue
        inner = projection.unalias()
        if isinstance(inner, exp.Column):
            return _column_origin(inner, sources, depth + 1)
    return None


def _link_for(
    left: tuple[str, str], right: tuple[str, str], links: list[ResolvedLink]
) -> ResolvedLink | None:
    pair = {left, right}
    for link in links:
        ends = {
            (link.from_table.lower(), link.from_column.lower()),
            (link.to_table.lower(), link.to_column.lower()),
        }
        if pair == ends:
            return link
    return None


def _catalog(origin: tuple[str, str]) -> str:
    return origin[0].split('.', 1)[0]


def _in_query_column(node: exp.In) -> exp.Column | None:
    query = node.args.get('query')
    select = query.this if isinstance(query, exp.Subquery) else query
    if not isinstance(select, exp.Select) or len(select.expressions) != 1:
        return None
    inner = select.expressions[0].unalias()
    return inner if isinstance(inner, exp.Column) else None


def _comparison_columns(node: exp.Expression) -> list[exp.Column]:
    """Colunas da própria comparação, sem as de subconsultas."""
    return [
        column
        for column in node.find_all(exp.Column)
        if column.find_ancestor(exp.Select) is node.find_ancestor(exp.Select)
    ]


def _check_cross_source(  # noqa: C901
    qualified: exp.Expression,
    schema: FederatedSchema,
    sources: dict[str, Any],
) -> ResolvedLink:
    """Toda comparação entre fontes precisa ser uma ligação ativa."""
    used: list[ResolvedLink] = []
    refusal = (
        'Fontes diferentes só se juntam por ligações declaradas no '
        'catálogo, com igualdade entre as colunas da ligação'
    )
    for node in qualified.find_all(*COMPARISONS):
        if isinstance(node, exp.In) and node.args.get('query'):
            left = node.this
            inner = _in_query_column(node)
            if not isinstance(left, exp.Column) or inner is None:
                continue
            pair = [left, inner]
        elif isinstance(node, exp.EQ) and all(
            isinstance(side, exp.Column) for side in (node.left, node.right)
        ):
            pair = [node.left, node.right]
        else:
            columns = _comparison_columns(node)
            origins = [_column_origin(c, sources) for c in columns]
            catalogs = {_catalog(o) for o in origins if o}
            if len(catalogs) > 1:
                raise QueryValidationError(refusal)
            continue
        origins = [_column_origin(c, sources) for c in pair]
        known = [o for o in origins if o]
        if len(known) < len(pair):
            raise QueryValidationError(refusal)
        if _catalog(known[0]) == _catalog(known[1]):
            continue
        link = _link_for(known[0], known[1], schema.links)
        if link is None:
            raise QueryValidationError(refusal)
        used.append(link)
    if not used:
        raise QueryValidationError(refusal)
    return used[0]


def _conjuncts(condition: exp.Expression | None) -> list[exp.Expression]:
    if condition is None:
        return []
    return [
        part.unnest()
        for part in (
            condition.flatten()
            if isinstance(condition, exp.And)
            else [condition]
        )
    ]


def _coverage_query(  # noqa: PLR0911, PLR0914
    qualified: exp.Expression,
    link: ResolvedLink,
    sources: dict[str, Any],
) -> tuple[CoverageQuery | None, str | None]:
    """Reescreve a consulta só com as tabelas e os filtros da fonte de
    origem da ligação, para contar as chaves encontradas na outra."""
    not_flat = 'A consulta usa CTE ou subconsulta na fonte de origem'
    if not isinstance(qualified, exp.Select) or qualified.find(exp.CTE):
        return None, not_flat
    from_clause = qualified.args.get('from') or qualified.args.get('from_')
    joins = qualified.args.get('joins') or []
    if from_clause is None:
        return None, not_flat
    relations = [from_clause.this, *(join.this for join in joins)]
    if not all(isinstance(r, exp.Table) for r in relations):
        return None, not_flat

    origin = link.from_datasource_id.lower()
    tables = [r for r in relations if r.catalog.lower() == origin]
    keys = [r for r in tables if _table_key(r) == link.from_table.lower()]
    if not keys:
        return None, 'A tabela da ligação não está no FROM da consulta'
    aliases = {t.alias_or_name for t in tables}

    conditions = _conjuncts(
        qualified.args['where'].this if qualified.args.get('where') else None
    )
    for join in joins:
        conditions += _conjuncts(join.args.get('on'))
    kept = [
        c.sql(dialect=DIALECT)
        for c in conditions
        if not c.find(exp.Select)
        and all(col.table in aliases for col in c.find_all(exp.Column))
    ]

    key = exp.column(
        link.from_column, table=keys[0].alias_or_name, quoted=True
    ).sql(dialect=DIALECT)
    schema_name, table_name = link.to_entity.split('.', 1)
    target = f'"{link.to_datasource_id}"."{schema_name}"."{table_name}"'
    other = f'SELECT "{link.to_column}" FROM {target}'
    relations_sql = ', '.join(t.sql(dialect=DIALECT) for t in tables)
    where = f' WHERE {" AND ".join(kept)}' if kept else ''
    sql = (
        f'SELECT COUNT(DISTINCT {key}) AS total, '
        f'COUNT(DISTINCT CASE WHEN {key} IN ({other}) THEN {key} END) '
        f'AS found FROM {relations_sql}{where}'
    )
    return CoverageQuery(sql, origin, link.to_datasource_id.lower()), None


def cited_sources(sql: str) -> list[str]:
    """Fontes citadas no SQL, para anunciar a consulta; sem validar."""
    try:
        statement = sqlglot.parse_one(sql, read=DIALECT)
    except Exception:  # noqa: BLE001
        return []
    return sorted({
        table.catalog.lower()
        for table in statement.find_all(exp.Table)
        if table.catalog
    })


def validate_federated_query(
    sql: str, schema: FederatedSchema, max_rows: int = 100
) -> FederatedQuery:
    """Valida a consulta entre fontes e devolve o SQL para o DuckDB."""
    if not sql or not sql.strip():
        raise QueryValidationError('Consulta vazia')
    try:
        statements = sqlglot.parse(sql, read=DIALECT)
    except Exception as exc:
        raise QueryValidationError(f'Erro de sintaxe SQL: {exc}') from exc

    stmt = _check_statement(statements)
    _check_functions(stmt)
    cited = _check_tables(stmt, schema)
    _check_source_count(cited)
    _check_stars(stmt)
    _check_limit(stmt, max_rows)

    qualified = _qualify_query(stmt, schema)
    sources = _alias_sources(qualified)
    _check_aggregate_columns(qualified, schema, sources, _table_key)
    link = _check_cross_source(qualified, schema, sources)

    def table_resolver(alias: str) -> str | None:
        source = sources.get(alias)
        if isinstance(source, exp.Table):
            return _table_key(source)
        return alias.lower()

    rewrite_match_text(
        qualified, DIALECT, schema.searchable_columns, table_resolver
    )
    coverage, reason = _coverage_query(qualified, link, sources)
    return FederatedQuery(
        sql=qualified.sql(dialect=DIALECT),
        sources=tuple(sorted(cited)),
        coverage=coverage,
        coverage_reason=reason,
    )
