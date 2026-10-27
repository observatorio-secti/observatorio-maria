"""Validação determinística de consultas SQL contra o catálogo de dados."""

import re
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope
from sqlglot.schema import MappingSchema

from observatorio_maria.catalog.introspection import (
    ConnectionNotConfiguredError,
    resolve_connection_url,
)
from observatorio_maria.models import (
    CatalogDataSource,
    CatalogEntity,
    ColumnAccess,
)
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.match_text import rewrite_match_text

ALLOWED_FUNC_CLASSES = (
    exp.Count,
    exp.Sum,
    exp.Avg,
    exp.Min,
    exp.Max,
    exp.Coalesce,
    exp.Nullif,
    exp.Lower,
    exp.Upper,
    exp.Trim,
    exp.Length,
    exp.Substring,
    exp.TimestampTrunc,
    exp.DateTrunc,
    exp.Extract,
    exp.Cast,
    exp.Round,
    exp.Abs,
    exp.GroupConcat,
    exp.Case,
    exp.Connector,
    exp.Exists,
)

ALLOWED_ANONYMOUS_FUNCS = {
    'match_text',
    'date_part',
    'date_trunc',
    'string_agg',
}

AGG_FUNC_CLASSES = (
    exp.Count,
    exp.Sum,
    exp.Avg,
    exp.Min,
    exp.Max,
    exp.GroupConcat,
)


@dataclass(frozen=True)
class QuerySchema:
    """Schema de validação com itens visíveis e presentes."""

    datasource_id: str
    dialect: str
    mapping_schema: MappingSchema
    queryable_tables: dict[str, str] = field(default_factory=dict)
    reference_only_tables: set[str] = field(default_factory=set)
    aggregate_columns: set[tuple[str, str]] = field(default_factory=set)
    searchable_columns: set[tuple[str, str]] = field(default_factory=set)


def source_dialect(datasource: CatalogDataSource) -> str:
    """Dialeto SQL da origem, deduzido da URL; SQLite sem conexão."""
    try:
        url = resolve_connection_url(datasource.connection_env)
    except ConnectionNotConfiguredError:
        return 'sqlite'
    return 'postgres' if 'postgres' in url or 'psycopg' in url else 'sqlite'


def build_query_schema(
    datasource: CatalogDataSource,
    entities: list[CatalogEntity],
    dialect: str = 'postgres',
) -> QuerySchema:
    """Monta o QuerySchema a partir do catálogo da fonte."""
    tables_dict: dict[str, dict[str, dict[str, str]]] = {}
    queryable_tables: dict[str, str] = {}
    reference_only_tables: set[str] = set()
    aggregate_columns: set[tuple[str, str]] = set()
    searchable_columns: set[tuple[str, str]] = set()

    for entity in entities:
        if not entity.visible or not entity.present:
            continue

        name_lower = entity.name.lower()
        qualified_lower = entity.qualified_name.lower()

        if not entity.queryable:
            reference_only_tables.add(name_lower)
            reference_only_tables.add(qualified_lower)
            continue

        queryable_tables[name_lower] = entity.name
        queryable_tables[qualified_lower] = entity.name

        schema_key = entity.schema_name.lower()
        if schema_key not in tables_dict:
            tables_dict[schema_key] = {}

        cols_dict: dict[str, str] = {}
        for col in entity.columns:
            if not col.visible or not col.present:
                continue

            c_name = col.name.lower()
            cols_dict[c_name] = col.data_type or 'text'

            if col.access == ColumnAccess.AGGREGATE:
                aggregate_columns.add((name_lower, c_name))
                aggregate_columns.add((qualified_lower, c_name))

            if col.searchable:
                searchable_columns.add((name_lower, c_name))
                searchable_columns.add((qualified_lower, c_name))

        tables_dict[schema_key][name_lower] = cols_dict

    mapping_schema = MappingSchema(tables_dict)
    return QuerySchema(
        datasource_id=datasource.id,
        dialect=dialect,
        mapping_schema=mapping_schema,
        queryable_tables=queryable_tables,
        reference_only_tables=reference_only_tables,
        aggregate_columns=aggregate_columns,
        searchable_columns=searchable_columns,
    )


def _check_statement(
    statements: list[exp.Expression | None],
) -> exp.Expression:
    non_empty = [s for s in statements if s is not None]
    if len(non_empty) != 1:
        raise QueryValidationError('Apenas uma instrução SQL é permitida')
    stmt = non_empty[0]
    if not isinstance(stmt, (exp.Select, exp.Union)):
        raise QueryValidationError('Apenas consultas SELECT são permitidas')
    return stmt


def _check_tables(stmt: exp.Expression, schema: QuerySchema) -> None:
    ctes = {cte.alias_or_name.lower() for cte in stmt.find_all(exp.CTE)}
    for table_node in stmt.find_all(exp.Table):
        t_name = table_node.name.lower()
        if t_name in ctes:
            continue

        t_db = table_node.db.lower() if table_node.db else None
        q_name = f'{t_db}.{t_name}' if t_db else t_name

        if (
            t_name in schema.reference_only_tables
            or q_name in schema.reference_only_tables
        ):
            raise QueryValidationError(
                f"Entidade '{table_node.name}' é somente de referência "
                'e não pode ser consultada'
            )

        if (
            t_name not in schema.queryable_tables
            and q_name not in schema.queryable_tables
        ):
            raise QueryValidationError(
                f"Tabela ou view '{table_node.name}' não encontrada"
            )


def _check_stars(stmt: exp.Expression) -> None:
    for star in stmt.find_all(exp.Star):
        if isinstance(star.parent, exp.Count) or star.find_ancestor(
            exp.Exists
        ):
            continue
        raise QueryValidationError(
            "Selecione as colunas explicitamente em vez de usar '*'"
        )


def _check_functions(stmt: exp.Expression) -> None:
    for node in stmt.walk():
        if isinstance(node, exp.Anonymous):
            f_name = node.name.lower()
            if f_name not in ALLOWED_ANONYMOUS_FUNCS:
                raise QueryValidationError(
                    f"Função '{node.name}' não permitida"
                )
        elif isinstance(node, exp.Func):
            if not isinstance(node, ALLOWED_FUNC_CLASSES):
                f_name = (
                    node.key or node.sql_name() or type(node).__name__
                ).lower()
                raise QueryValidationError(f"Função '{f_name}' não permitida")


def _check_limit(stmt: exp.Expression, max_rows: int = 100) -> None:
    for limit_node in stmt.find_all(exp.Limit):
        expr = limit_node.expression
        if isinstance(expr, exp.Neg):
            raise QueryValidationError(
                'O limite da consulta deve ser um inteiro positivo'
            )
        if isinstance(expr, exp.Literal) and expr.is_int:
            val = int(expr.this)
        else:
            try:
                val = int(expr.name or str(expr))
            except (ValueError, TypeError) as exc:
                raise QueryValidationError(
                    'O limite da consulta deve ser um número inteiro'
                ) from exc
        if val <= 0:
            raise QueryValidationError(
                f'O limite da consulta ({val}) deve ser um inteiro positivo'
            )
        if val > max_rows:
            raise QueryValidationError(
                f'O limite solicitado na consulta ({val}) excede o '
                f'máximo permitido ({max_rows})'
            )


def _qualify_query(
    stmt: exp.Expression, schema: QuerySchema
) -> exp.Expression:
    try:
        return qualify(
            stmt.copy(),
            schema=schema.mapping_schema,
            dialect=schema.dialect,
        )
    except Exception as exc:
        err_str = str(exc)
        match = re.search(
            r"(?:Column '([^']+)' could not be resolved|"
            r'Unknown column:\s*(\w+))',
            err_str,
        )
        if match:
            col = match.group(1) or match.group(2)
            raise QueryValidationError(
                f"Coluna '{col}' não encontrada"
            ) from exc
        raise QueryValidationError(f'Erro de validação SQL: {exc}') from exc


def _is_inside_aggregate(col: exp.Column, top_expr: exp.Expression) -> bool:
    curr = col.parent
    while curr is not None and curr is not top_expr:
        if isinstance(curr, AGG_FUNC_CLASSES):
            return True
        curr = curr.parent
    return False


def _check_aggregate_columns(
    qualified: exp.Expression,
    schema: QuerySchema,
    sources: dict[str, Any],
) -> None:
    for select in qualified.find_all(exp.Select):
        for expr in select.expressions:
            for col in expr.find_all(exp.Column):
                if _is_inside_aggregate(col, expr):
                    continue

                table_name = None
                if col.table:
                    src = sources.get(col.table)
                    if isinstance(src, exp.Table):
                        table_name = src.name.lower()
                    elif col.table.lower() in schema.queryable_tables:
                        table_name = col.table.lower()

                col_name = col.name.lower()
                is_agg = (
                    (table_name, col_name) in schema.aggregate_columns
                    if table_name
                    else any(
                        c == col_name for _, c in schema.aggregate_columns
                    )
                )
                if is_agg:
                    raise QueryValidationError(
                        f"Coluna '{col.name}' é somente para agregação e "
                        'não pode ser exibida diretamente'
                    )


def validate_query(sql: str, schema: QuerySchema, max_rows: int = 100) -> str:
    """Valida a consulta SQL e devolve o SQL reescrito."""
    if not sql or not sql.strip():
        raise QueryValidationError('Consulta vazia')

    try:
        statements = sqlglot.parse(sql, read=schema.dialect)
    except Exception as exc:
        raise QueryValidationError(f'Erro de sintaxe SQL: {exc}') from exc

    stmt = _check_statement(statements)
    _check_tables(stmt, schema)
    _check_stars(stmt)
    _check_functions(stmt)
    _check_limit(stmt, max_rows)

    qualified = _qualify_query(stmt, schema)
    all_sources: dict[str, Any] = {}
    for sc in traverse_scope(qualified):
        all_sources.update(sc.sources)

    _check_aggregate_columns(qualified, schema, all_sources)

    def table_resolver(alias: str) -> str | None:
        src = all_sources.get(alias)
        if isinstance(src, exp.Table):
            return src.name.lower()
        return alias.lower()

    rewrite_match_text(
        qualified,
        schema.dialect,
        schema.searchable_columns,
        table_resolver,
    )

    return qualified.sql(dialect=schema.dialect)
