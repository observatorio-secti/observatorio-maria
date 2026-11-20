"""Validação de enums e busca textual exclusiva da fonte ODA."""

from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope

from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.match_text import rewrite_match_text


def _origin(scope: Scope, column: exp.Column):
    source = scope.sources.get(column.table)
    if isinstance(source, exp.Table):
        return source.name.lower(), column.name.lower()
    if isinstance(source, Scope):
        for projection in source.expression.selects:
            if projection.alias_or_name == column.name:
                inner = projection.unalias()
                if isinstance(inner, exp.Column):
                    return _origin(source, inner)
    if scope.parent and column.table not in scope.sources:
        return _origin(scope.parent, column)
    return None


def _check_literal(column, literal, scope, enum_values):
    if not isinstance(column, exp.Column):
        return
    if not isinstance(literal, exp.Literal) or not literal.is_string:
        return
    values = enum_values.get(_origin(scope, column))
    if values is not None and literal.this not in values:
        raise QueryValidationError(
            f"Valor '{literal.this}' inválido para '{column.name}'. "
            f'Valores aceitos: {", ".join(values)}'
        )


def prepare_oda_query(statement, schema):
    """Usa o escopo original antes da inclusão dos filtros obrigatórios."""
    comparisons = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)
    for scope in traverse_scope(statement):
        for node in list(scope.expression.walk()):
            if node.find_ancestor(exp.Select) is not scope.expression:
                continue
            if isinstance(node, comparisons):
                _check_literal(
                    node.left, node.right, scope, schema.enum_values
                )
                _check_literal(
                    node.right, node.left, scope, schema.enum_values
                )
            elif isinstance(node, exp.In):
                for value in node.expressions:
                    _check_literal(node.this, value, scope, schema.enum_values)
            elif isinstance(node, exp.Between):
                for key in ('low', 'high'):
                    _check_literal(
                        node.this, node.args[key], scope, schema.enum_values
                    )
            elif isinstance(node, exp.Anonymous):
                if node.name.lower() != 'match_text':
                    continue
                column = node.expressions[0] if node.expressions else None
                origin = (
                    _origin(scope, column)
                    if isinstance(column, exp.Column)
                    else None
                )
                temporary = exp.select(node.copy())
                searchable = (
                    {(origin[0], column.name.lower())}
                    if origin in schema.searchable_columns
                    else set()
                )
                rewrite_match_text(
                    temporary,
                    schema.dialect,
                    searchable,
                    lambda alias, origin=origin: origin[0] if origin else '',
                    datasource_id='oda',
                )
                node.replace(temporary.expressions[0].copy())
