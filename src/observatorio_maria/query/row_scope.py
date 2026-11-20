"""Escopo obrigatório de linhas para a fonte ODA/SIMCC."""

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

from observatorio_maria.query.errors import QueryValidationError

SIMCC_INSTITUTION_ACRONYMS = (
    'UFBA',
    'EBMSP',
    'UESB',
    'UFOB',
    'UFSB',
    'UEFS',
    'UESC',
    'UFRB',
    'UNEB',
    'IFBA',
)

_ACRONYMS_SQL = ', '.join(
    f"'{acronym}'" for acronym in SIMCC_INSTITUTION_ACRONYMS
)


def _institution_filter(alias: str) -> str:
    # Mesmo critério de shared/database/src/simcc.ts no ODA.
    return (
        f'{alias}.sigla IN ({_ACRONYMS_SQL}) OR '
        f"{alias}.sigla ILIKE 'IFBA -%' OR "
        f"({alias}.sigla = 'FIOCRUZ' AND {alias}.nome ILIKE '%Moniz%')"
    )


def _eligible_group(alias: str) -> str:
    # PostgreSQL guarda o valor mapeado pelo Prisma: `sede`, não `SEDE`.
    return (
        'EXISTS ('
        'SELECT 1 FROM public.grupo_pesquisa_instituicao AS scope_gpi '
        'JOIN public.instituicao AS scope_inst '
        'ON scope_inst.id = scope_gpi.instituicao_id '
        f'WHERE scope_gpi.grupo_id = {alias}.id '
        "AND scope_gpi.tipo_relacao = 'sede' "
        f'AND ({_institution_filter("scope_inst")})'
        ')'
    )


def _eligible_line(alias: str) -> str:
    return (
        'EXISTS ('
        'SELECT 1 FROM public.linha_pesquisa AS scope_line '
        'JOIN public.grupo_pesquisa AS scope_group '
        'ON scope_group.id = scope_line.grupo_id '
        f'WHERE scope_line.id = {alias}.linha_pesquisa_id '
        f'AND {_eligible_group("scope_group")}'
        ')'
    )


def _policy(table_name: str) -> str | None:  # noqa: PLR0911
    group = _eligible_group('scope_group')
    if table_name == 'instituicao':
        return _institution_filter('_scope')
    if table_name == 'grupo_pesquisa':
        return _eligible_group('_scope')
    if table_name == 'grupo_pesquisa_instituicao':
        return (
            "_scope.tipo_relacao = 'sede' AND "
            '_scope.instituicao_id IN ('
            'SELECT scope_inst.id FROM public.instituicao AS scope_inst '
            f'WHERE {_institution_filter("scope_inst")})'
        )
    if table_name == 'membro_grupo':
        return (
            'EXISTS (SELECT 1 FROM public.grupo_pesquisa AS scope_group '
            f'WHERE scope_group.id = _scope.grupo_id AND {group})'
        )
    if table_name == 'pesquisador':
        return (
            'EXISTS (SELECT 1 FROM public.membro_grupo AS scope_member '
            'JOIN public.grupo_pesquisa AS scope_group '
            'ON scope_group.id = scope_member.grupo_id '
            'WHERE scope_member.pesquisador_id = _scope.id '
            f'AND {group})'
        )
    if table_name == 'linha_pesquisa':
        return (
            'EXISTS (SELECT 1 FROM public.grupo_pesquisa AS scope_group '
            'WHERE scope_group.id = _scope.grupo_id '
            f'AND {group})'
        )
    if table_name == 'membro_linha_pesquisa':
        return _eligible_line('_scope')
    if table_name == 'linha_pesquisa_setor_aplicacao':
        return _eligible_line('_scope')
    if table_name == 'setor_aplicacao':
        return (
            'EXISTS ('
            'SELECT 1 FROM public.linha_pesquisa_setor_aplicacao AS scope_map '
            'JOIN public.linha_pesquisa AS scope_line '
            'ON scope_line.id = scope_map.linha_pesquisa_id '
            'JOIN public.grupo_pesquisa AS scope_group '
            'ON scope_group.id = scope_line.grupo_id '
            'WHERE scope_map.setor_aplicacao_id = _scope.id '
            f'AND {_eligible_group("scope_group")}'
            ')'
        )
    return None


def _predicate_expression(predicate: str) -> exp.Expression:
    parsed = sqlglot.parse_one(f'SELECT 1 WHERE {predicate}', read='postgres')
    return parsed.args['where'].this


def apply_oda_simcc_scope(
    statement: exp.Expression, datasource_id: str
) -> exp.Expression:
    """Restringe toda referência às entidades ODA ao recorte SIMCC.

    O filtro é aplicado à árvore SQL validada, não só às instruções enviadas
    ao modelo. A origem é acessada com credenciais somente leitura.
    """
    if datasource_id != 'oda':
        return statement

    scopes = list(traverse_scope(statement))
    for scope in scopes:
        for table_alias, (_, source) in scope.selected_sources.items():
            if not isinstance(source, exp.Table):
                continue
            predicate_sql = _policy(source.name.lower())
            if predicate_sql is None:
                raise QueryValidationError(
                    f"A entidade '{source.name}' não está liberada "
                    'na fonte ODA/SIMCC.'
                )

            predicate = _predicate_expression(predicate_sql)
            original_alias = source.args.get('alias')
            if original_alias is None:
                for column in scope.expression.find_all(exp.Column):
                    nearest_select = column.find_ancestor(exp.Select)
                    if (
                        nearest_select is scope.expression
                        and column.table.lower() == source.name.lower()
                    ):
                        column.set('db', None)
                        column.set('table', exp.to_identifier(table_alias))

            inner_table = source.copy()
            # O alias do cliente só existe fora da subconsulta filtrada.
            # Assim ele nunca captura as referências internas da política.
            inner_table.set(
                'alias', exp.TableAlias(this=exp.to_identifier('_scope'))
            )

            scoped_select = exp.Select(
                expressions=[exp.Star()],
                from_=exp.From(this=inner_table),
                where=exp.Where(this=predicate),
            )
            outer_alias = (
                original_alias.copy()
                if original_alias is not None
                else exp.TableAlias(this=exp.to_identifier(table_alias))
            )
            source.replace(exp.Subquery(this=scoped_select, alias=outer_alias))

    return statement
