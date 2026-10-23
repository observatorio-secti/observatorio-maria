"""Reescrita de MATCH_TEXT para SQL portável (PostgreSQL e SQLite)."""

from sqlglot import exp, parse_one

from observatorio_maria.query.errors import QueryValidationError

FROM_ACCENTS = 'áàâãäéèêëíìîïóòôõöúùûüç'
TO_ACCENTS = 'aaaaaeeeeiiiiooooouuuuc'
ACCENT_TRANS = str.maketrans(FROM_ACCENTS, TO_ACCENTS)


def normalize_term(term: str) -> str:
    """Normaliza termo para busca léxica."""
    t = term.strip().lower()
    t = t.translate(ACCENT_TRANS)
    t = (
        t.replace('\\', '\\\\')
        .replace('%', '\\%')
        .replace('_', '\\_')
        .replace("'", "''")
    )
    return t


def _extract_terms(nodes: list[exp.Expression]) -> list[str]:
    if not nodes:
        raise QueryValidationError('Termo de busca textual não pode ser vazio')
    raw_terms = []
    for term_node in nodes:
        if isinstance(term_node, exp.Literal) and term_node.is_string:
            val = term_node.this
        elif isinstance(term_node, exp.Literal):
            val = str(term_node.this)
        else:
            val = term_node.name or str(term_node)

        if not val or not val.strip():
            raise QueryValidationError(
                'Termo de busca textual não pode ser vazio'
            )
        raw_terms.append(val)
    return raw_terms


def _check_searchable(
    col_expr: exp.Column,
    searchable_columns: set[tuple[str, str]],
    table_resolver,
) -> None:
    col_name = col_expr.name.lower()
    table_name = col_expr.table.lower() if col_expr.table else None
    if table_resolver and table_name:
        resolved = table_resolver(table_name)
        if resolved:
            table_name = resolved

    if table_name:
        is_searchable = (table_name, col_name) in searchable_columns
    else:
        is_searchable = any(c == col_name for _, c in searchable_columns)

    if not is_searchable:
        raise QueryValidationError(
            f"Coluna '{col_expr.name}' não aceita busca textual"
        )


def rewrite_match_text(
    ast: exp.Expression,
    dialect: str,
    searchable_columns: set[tuple[str, str]],
    table_resolver=None,
) -> None:
    """Valida e reescreve todas as chamadas a MATCH_TEXT na AST."""
    for node in ast.find_all(exp.Anonymous):
        if node.name.lower() != 'match_text':
            continue

        if not node.expressions:
            raise QueryValidationError(
                'MATCH_TEXT requer ao menos uma coluna e um termo'
            )

        col_expr = node.expressions[0]
        if not isinstance(col_expr, exp.Column):
            raise QueryValidationError(
                'Primeiro argumento de MATCH_TEXT deve ser uma coluna'
            )

        _check_searchable(col_expr, searchable_columns, table_resolver)
        raw_terms = _extract_terms(node.expressions[1:])

        col_sql = col_expr.sql(dialect=dialect)
        norm_col = (
            f"translate(lower({col_sql}), '{FROM_ACCENTS}', '{TO_ACCENTS}')"
        )
        clauses = [
            f"{norm_col} LIKE '%{normalize_term(term)}%' ESCAPE '\\'"
            for term in raw_terms
        ]
        combined = ' OR '.join(clauses)
        node.replace(parse_one(f'({combined})', read=dialect))
