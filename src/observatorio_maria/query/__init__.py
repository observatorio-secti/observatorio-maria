"""Pacote de validação e execução de consultas a dados do catálogo."""

from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.execution import (
    QueryResult,
    ResultStore,
    execute_readonly_query,
    infer_column_types,
    sanitize_purpose,
    serialize_value,
)
from observatorio_maria.query.match_text import (
    normalize_term,
    rewrite_match_text,
)
from observatorio_maria.query.tool import QueryRunner
from observatorio_maria.query.validator import (
    QuerySchema,
    build_query_schema,
    validate_query,
)

__all__ = [
    'QueryResult',
    'QueryRunner',
    'QuerySchema',
    'QueryValidationError',
    'ResultStore',
    'build_query_schema',
    'execute_readonly_query',
    'infer_column_types',
    'normalize_term',
    'rewrite_match_text',
    'sanitize_purpose',
    'serialize_value',
    'validate_query',
]
