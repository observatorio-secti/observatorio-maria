"""Validação de enums e busca textual exclusiva da fonte ODA."""

from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope

from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.match_text import rewrite_match_text


def _origins(scope: Scope, column: exp.Column, visited=frozenset()):
    key = (id(scope), column.table, column.name)
    if key in visited:
        return set()
    visited |= {key}
    source = scope.sources.get(column.table)
    if isinstance(source, exp.Table):
        return {(source.name.lower(), column.name.lower())}
    if isinstance(source, Scope):
        for position, projection in enumerate(source.expression.selects):
            if projection.alias_or_name == column.name:
                return _output_origins(source, position, visited)
    if scope.parent and column.table not in scope.sources:
        return _origins(scope.parent, column, visited)
    return set()


def _output_origins(scope: Scope, position: int, visited):
    if scope.set_operation_scopes:
        origins = set()
        for branch in scope.set_operation_scopes:
            origins.update(_output_origins(branch, position, visited))
        return origins
    projections = scope.expression.selects
    if position >= len(projections):
        return set()
    inner = projections[position].unalias()
    # Origem desconhecida deve impedir MATCH_TEXT em todo o UNION.
    return (
        _origins(scope, inner, visited)
        if isinstance(inner, exp.Column)
        else {('', '')}
    )


def _enum_domains(expression, scope, enum_values):
    if isinstance(expression, exp.Column):
        return [
            enum_values[o]
            for o in _origins(scope, expression)
            if o in enum_values
        ]
    if isinstance(expression, exp.Paren):
        return _enum_domains(expression.this, scope, enum_values)
    if isinstance(expression, exp.Coalesce):
        arguments = [expression.this, *expression.expressions]
    elif isinstance(expression, exp.Case):
        arguments = [
            branch.args.get('true')
            for branch in expression.args.get('ifs', [])
        ]
        arguments.append(expression.args.get('default'))
    else:
        return []
    return [
        domain
        for arg in arguments
        for domain in _enum_domains(arg, scope, enum_values)
    ]


def _check_literal(expression, literal, scope, enum_values):
    if not isinstance(literal, exp.Literal) or not literal.is_string:
        return
    for values in _enum_domains(expression, scope, enum_values):
        if literal.this not in values:
            raise QueryValidationError(
                f"Valor '{literal.this}' inválido para o enum consultado. "
                f'Valores aceitos: {", ".join(values)}'
            )


def _check_enum_node(node, scope, enum_values):
    if isinstance(node, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)):
        _check_literal(node.left, node.right, scope, enum_values)
        _check_literal(node.right, node.left, scope, enum_values)
    elif isinstance(node, exp.In):
        for value in node.expressions:
            _check_literal(node.this, value, scope, enum_values)
    elif isinstance(node, exp.Between):
        for key in ('low', 'high'):
            _check_literal(node.this, node.args[key], scope, enum_values)
    elif isinstance(node, exp.Coalesce):
        for value in [node.this, *node.expressions]:
            _check_literal(node, value, scope, enum_values)
    elif isinstance(node, exp.Case):
        for branch in node.args.get('ifs', []):
            _check_literal(node.this, branch.this, scope, enum_values)
            _check_literal(node, branch.args.get('true'), scope, enum_values)
        _check_literal(node, node.args.get('default'), scope, enum_values)


def _rewrite_search(node, scope, schema):
    column = node.expressions[0] if node.expressions else None
    origins = (
        _origins(scope, column) if isinstance(column, exp.Column) else set()
    )
    temporary = exp.select(node.copy())
    searchable = (
        {(column.table.lower(), column.name.lower())}
        if origins and origins <= schema.searchable_columns
        else set()
    )
    rewrite_match_text(
        temporary,
        schema.dialect,
        searchable,
        lambda alias: alias.lower(),
        datasource_id='oda',
    )
    node.replace(temporary.expressions[0].copy())


def prepare_oda_query(statement, schema):
    """Usa o escopo original antes da inclusão dos filtros obrigatórios."""
    for scope in traverse_scope(statement):
        for node in list(scope.expression.walk()):
            if node.find_ancestor(exp.Select) is not scope.expression:
                continue
            _check_enum_node(node, scope, schema.enum_values)
            if (
                isinstance(node, exp.Anonymous)
                and node.name.lower() == 'match_text'
            ):
                _rewrite_search(node, scope, schema)
