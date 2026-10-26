"""Pacote de validação e execução de consultas a dados do catálogo."""

from observatorio_maria.query.errors import (
    QueryCostExceededError,
    QueryValidationError,
)
from observatorio_maria.query.execution import (
    QueryResult,
    ResultStore,
    check_query_cost,
    execute_readonly_query,
    infer_column_types,
    sanitize_purpose,
    serialize_value,
)
from observatorio_maria.query.match_text import (
    normalize_term,
    rewrite_match_text,
)
from observatorio_maria.query.sanitization import (
    format_untrusted_data_xml,
    sanitize_untrusted_text,
)
from observatorio_maria.query.tool import QueryRunner
from observatorio_maria.query.validator import (
    QuerySchema,
    build_query_schema,
    validate_query,
)

__all__ = [
    'QueryCostExceededError',
    'QueryResult',
    'QueryRunner',
    'QuerySchema',
    'QueryValidationError',
    'ResultStore',
    'build_query_schema',
    'check_query_cost',
    'execute_readonly_query',
    'format_untrusted_data_xml',
    'infer_column_types',
    'normalize_term',
    'rewrite_match_text',
    'sanitize_purpose',
    'sanitize_untrusted_text',
    'serialize_value',
    'validate_query',
]
