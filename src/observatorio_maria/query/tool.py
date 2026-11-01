"""Ferramentas LangChain para consulta e apresentação de dados."""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unicodedata import normalize

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from observatorio_maria.catalog.introspection import (
    ConnectionNotConfiguredError,
    SourceUnavailableError,
    create_readonly_engine,
    resolve_connection_url,
)
from observatorio_maria.catalog.links import load_links
from observatorio_maria.catalog.sync import load_entities
from observatorio_maria.models import CatalogDataSource
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.execution import (
    QueryResult,
    ResultStore,
    execute_readonly_query,
    sanitize_purpose,
)
from observatorio_maria.query.federated_validator import (
    FederatedSchema,
    build_federated_schema,
    cited_sources,
    validate_federated_query,
)
from observatorio_maria.query.federation import (
    FederationLimits,
    execute_federated_query,
)
from observatorio_maria.query.sanitization import (
    format_untrusted_data_xml,
    mask_pii,
    mask_value,
    sanitize_untrusted_text,
)
from observatorio_maria.query.validator import (
    QuerySchema,
    build_query_schema,
    source_dialect,
    validate_query,
)
from observatorio_maria.schemas import is_year_column


@dataclass(frozen=True)
class QueryObservation:
    """Consulta feita pelo agente, para quem observa a resposta de fora."""

    source: str
    sql: str
    row_count: int
    error: str | None = None
    # Fontes consultadas; só numa consulta entre fontes há mais de uma.
    sources: tuple[str, ...] = ()


QueryObserver = Callable[[QueryObservation], None]

MAX_CHART_GROUPS = 5
GROUPABLE_CHART_TYPES = {'bar', 'line', 'area'}
SERIES_KEY_MAX_LENGTH = 40
NO_GROUP_LABEL = 'Não informado'

EMPTY_RESULT_HINT = (
    'A consulta não trouxe dados (nenhuma linha ou só valores nulos). Se ela '
    'filtra colunas de texto, confira os valores existentes (por exemplo, '
    'SELECT DISTINCT coluna FROM entidade) antes de concluir que não há '
    'dados, e refaça a consulta com os valores exatos.'
)


def is_empty_result(rows: list) -> bool:
    """Zero linhas ou uma única linha só com nulos (ex.: SUM sem linhas)."""
    if not rows:
        return True
    return len(rows) == 1 and all(value is None for value in rows[0])


class QueryDataInput(BaseModel):
    source: str = Field(
        description='Identificador da fonte no catálogo (ex.: "fomento").'
    )
    sql: str = Field(
        description='Instrução SELECT SQL a ser executada na fonte.'
    )
    purpose: str = Field(
        default='',
        description='Descrição curta do que está sendo consultado, para '
        'quem lê, sem nomes de tabelas ou colunas '
        '(ex.: "Buscando projetos sobre dengue").',
    )


class QueryAcrossSourcesInput(BaseModel):
    sql: str = Field(
        description=(
            'SELECT com tabelas no formato fonte.schema.tabela, juntando as '
            'fontes pelas ligações do catálogo.'
        )
    )
    purpose: str = Field(
        description=(
            'Descrição curta, em português, do que está sendo buscado, para '
            'quem lê, sem nomes de tabelas ou colunas.'
        )
    )


def build_origin(
    sources: list[str],
    purpose: str,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Origem gravada nos blocos, sem SQL nem identificadores internos."""
    description = sanitize_purpose(purpose, ' e '.join(sources))
    return {
        'sources': sources,
        'description': sanitize_untrusted_text(description),
        'queried_at': datetime.now(UTC).isoformat(),
        'coverage': (
            {'keys': coverage['keys'], 'found': coverage['found']}
            if coverage and coverage.get('available')
            else None
        ),
    }


def axis_type(column_type: str | None) -> str:
    """Tipo aceito no eixo de um gráfico: texto é categoria."""
    return column_type if column_type in {'number', 'date'} else 'category'


def table_column_type(column_type: str | None) -> str:
    """Tipo aceito numa coluna de tabela: categoria é texto."""
    return column_type if column_type in {'number', 'date'} else 'string'


def column_label(key: str, labels: dict[str, str] | None) -> str:
    """Rótulo informado pelo modelo ou, sem ele, a chave legível."""
    if labels and labels.get(key):
        return labels[key]
    text = key.replace('_', ' ').strip()
    return text[:1].upper() + text[1:]


def series_key(value: str, taken: set[str]) -> str:
    """Chave ASCII de uma série, sem repetir as já usadas."""
    plain = normalize('NFKD', value).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-z0-9]+', '_', plain.lower()).strip('_')
    base = slug[:SERIES_KEY_MAX_LENGTH].rstrip('_') or 'serie'
    key = base
    suffix = 1
    while key in taken:
        suffix += 1
        key = f'{base}_{suffix}'
    taken.add(key)
    return key


def plain_chart_rows(
    result: QueryResult, chart_type: str, x: str, series: list[str]
) -> list[dict[str, Any]]:
    """Registros de um gráfico sem grupo; `x` só repete em dispersão."""
    x_index = result.columns.index(x)
    axis_values = [repr(row[x_index]) for row in result.rows]
    if chart_type != 'scatter' and len(set(axis_values)) < len(axis_values):
        raise ValueError(
            f"A coluna '{x}' repete valores no resultado. Informe em group_by "
            'a coluna que separa as séries ou agregue a consulta para ter '
            'uma linha por valor de x.'
        )
    return [
        {
            col_name: val
            for col_name, val in zip(result.columns, row, strict=False)
            if col_name == x or col_name in series
        }
        for row in result.rows
    ]


def check_group_request(
    result: QueryResult,
    chart_type: str,
    x: str,
    series: list[str],
    group_by: str,
) -> None:
    """Recusa pedidos com `group_by` que não formam séries por categoria."""
    if group_by not in result.columns:
        raise ValueError(f"Coluna '{group_by}' não encontrada no resultado.")
    if chart_type not in GROUPABLE_CHART_TYPES:
        raise ValueError(f"group_by não se aplica a gráficos '{chart_type}'.")
    if group_by == x or group_by in series:
        raise ValueError(
            'group_by precisa ser uma coluna diferente de x e das séries.'
        )
    if len(series) != 1:
        raise ValueError('Com group_by, informe uma só coluna em series.')


def group_chart_rows(
    result: QueryResult, x: str, value: str, group_by: str
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Passa de uma linha por `x` e grupo a uma linha por `x`.

    Devolve as séries (chave → rótulo) e os registros. Combinação sem linha
    fica nula: zero só seria correto em contagens.
    """
    x_index = result.columns.index(x)
    value_index = result.columns.index(value)
    group_index = result.columns.index(group_by)

    keys: dict[str, str] = {}
    taken = {x}
    labels: dict[str, str] = {}
    records: dict[str, dict[str, Any]] = {}
    for row in result.rows:
        group = row[group_index]
        label = NO_GROUP_LABEL if group is None else mask_pii(str(group))
        key = keys.get(repr(group))
        if key is None:
            key = series_key(label, taken)
            keys[repr(group)] = key
            labels[key] = label
        record = records.setdefault(repr(row[x_index]), {x: row[x_index]})
        if key in record:
            raise ValueError(
                f"A coluna '{x}' repete um valor no mesmo grupo: agregue a "
                'consulta antes de pedir o gráfico.'
            )
        record[key] = row[value_index]

    if len(labels) > MAX_CHART_GROUPS:
        raise ValueError(
            f"A coluna '{group_by}' tem {len(labels)} valores e o limite é "
            f'{MAX_CHART_GROUPS}. Refaça a consulta mantendo os maiores e, se '
            'a medida puder ser somada, reúna os demais em "Outros".'
        )
    data = [
        {x: record[x], **{key: record.get(key) for key in labels}}
        for record in records.values()
    ]
    if axis_type(result.column_types.get(x)) != 'category':
        data.sort(key=lambda record: (record[x] is None, record[x]))
    return labels, data


class ShowChartInput(BaseModel):
    result_id: str = Field(
        description='Identificador do resultado da consulta (ex.: "r1").'
    )
    chart_type: str = Field(
        description='Tipo: "bar", "line", "area", "pie" ou "scatter".'
    )
    title: str = Field(description='Título do gráfico.')
    x: str = Field(description='Nome da coluna para o eixo X.')
    series: list[str] = Field(
        description='Lista de nomes de colunas numéricas para as séries.'
    )
    group_by: str | None = Field(
        default=None,
        description=(
            'Coluna de categoria que separa as séries, quando o resultado '
            'tem várias linhas por valor de x (ex.: "modalidade" em ano, '
            'modalidade, total). Exige uma só coluna em series. Até '
            f'{MAX_CHART_GROUPS} valores; não vale para pie e scatter.'
        ),
    )
    labels: dict[str, str] | None = Field(
        default=None,
        description=(
            'Rótulos legíveis em português, de coluna para rótulo '
            '(ex.: {"ano_inicio": "Ano de início"}).'
        ),
    )
    units: dict[str, str] | None = Field(
        default=None,
        description=(
            'Unidade de cada série, de coluna para unidade '
            '(ex.: {"orcamento": "R$"}).'
        ),
    )


class ShowTableInput(BaseModel):
    result_id: str = Field(
        description='Identificador do resultado da consulta (ex.: "r1").'
    )
    title: str | None = Field(
        default=None, description='Título opcional da tabela.'
    )
    columns: list[str] = Field(
        description='Lista de nomes de colunas a exibir na tabela.'
    )
    labels: dict[str, str] | None = Field(
        default=None,
        description=(
            'Rótulos legíveis em português, de coluna para rótulo '
            '(ex.: {"nome": "Instituição"}).'
        ),
    )


ActivityCallback = Callable[[str, str, str], Awaitable[None]]


class QueryRunner:
    """Orquestrador das ferramentas durante a geração de uma resposta."""

    def __init__(  # noqa: PLR0913
        self,
        session: AsyncSession,
        result_store: ResultStore,
        *,
        max_rows: int = 100,
        timeout_seconds: float = 15.0,
        max_cost: float = 0.0,
        max_per_call: int = 4,
        on_activity: ActivityCallback | None = None,
        calls_left: int = 0,
        engine_factory: Callable[[str], AsyncEngine] | None = None,
        query_observer: QueryObserver | None = None,
        federation_limits: FederationLimits | None = None,
    ):
        self.session = session
        self.result_store = result_store
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds
        self.max_cost = max_cost
        self.max_per_call = max_per_call
        self.on_activity = on_activity
        self.calls_left = calls_left
        self.engine_factory = engine_factory or create_readonly_engine
        self.query_observer = query_observer
        self.federation_limits = federation_limits or FederationLimits(
            max_rows=max_rows, timeout_seconds=timeout_seconds
        )

        self.queries_in_current_call: int = 0
        self.total_queries: int = 0
        self._schemas: dict[str, QuerySchema] = {}
        self._datasources: dict[str, CatalogDataSource] = {}
        self._engines: dict[str, AsyncEngine] = {}
        self.pending_blocks: list[dict[str, Any]] = []

    def reset_call_budget(self, calls_left: int) -> None:
        """Reinicia o contador de consultas da chamada atual."""
        self.queries_in_current_call = 0
        self.calls_left = calls_left

    async def _get_datasource(
        self, source_id: str
    ) -> CatalogDataSource | None:
        if source_id not in self._datasources:
            ds = await self.session.get(CatalogDataSource, source_id)
            if ds:
                self._datasources[source_id] = ds
        return self._datasources.get(source_id)

    async def _get_query_schema(
        self, datasource: CatalogDataSource
    ) -> QuerySchema:
        if datasource.id not in self._schemas:
            entities = await load_entities(self.session, datasource.id)
            schema = build_query_schema(
                datasource, entities, dialect=source_dialect(datasource)
            )
            self._schemas[datasource.id] = schema
        return self._schemas[datasource.id]

    async def _get_engine(self, datasource: CatalogDataSource) -> AsyncEngine:
        if datasource.id not in self._engines:
            url = resolve_connection_url(datasource.connection_env)
            self._engines[datasource.id] = self.engine_factory(url)
        return self._engines[datasource.id]

    async def _emit_activity(
        self, datasource: CatalogDataSource, purpose: str
    ) -> None:
        if self.on_activity:
            clean = sanitize_purpose(purpose, datasource.name)
            await self.on_activity(datasource.id, datasource.name, clean)

    async def query_data(
        self, source: str, sql: str, purpose: str = ''
    ) -> dict[str, Any]:
        """Executa a ferramenta query_data e avisa o observador, se houver."""
        response = await self._run_query_data(source, sql, purpose)
        if self.query_observer:
            result = self.result_store.get(response.get('result_id', ''))
            self.query_observer(
                QueryObservation(
                    source=source,
                    sql=result.sql if result else sql,
                    row_count=len(response.get('rows', [])),
                    error=response.get('error'),
                )
            )
        return response

    async def _run_query_data(  # noqa: PLR0911
        self, source: str, sql: str, purpose: str
    ) -> dict[str, Any]:
        self.queries_in_current_call += 1
        self.total_queries += 1

        if self.queries_in_current_call > self.max_per_call:
            return {
                'error': (
                    'Limite de consultas por chamada excedido '
                    f'(máximo {self.max_per_call}).'
                ),
                'calls_left': self.calls_left,
            }

        datasource = await self._get_datasource(source)
        if not datasource or not datasource.enabled:
            return {
                'error': f"Fonte '{source}' não encontrada ou desativada.",
                'calls_left': self.calls_left,
            }

        await self._emit_activity(datasource, purpose)

        try:
            schema = await self._get_query_schema(datasource)
            validated_sql = validate_query(sql, schema, max_rows=self.max_rows)
            engine = await self._get_engine(datasource)
            cols, rows, trunc, col_types = await execute_readonly_query(
                engine,
                validated_sql,
                max_rows=self.max_rows,
                timeout_seconds=self.timeout_seconds,
                max_cost=self.max_cost,
            )
            result = self.result_store.add(
                datasource.id,
                validated_sql,
                cols,
                rows,
                truncated=trunc,
                column_types=col_types,
                origin=build_origin(
                    [datasource.name or datasource.id], purpose
                ),
            )
            sanitized_rows = [
                [sanitize_untrusted_text(val) for val in row] for row in rows
            ]
            untrusted_xml = format_untrusted_data_xml(
                datasource.name or datasource.id,
                result.result_id,
                result.columns,
                sanitized_rows,
                truncated=result.truncated,
            )
            response = {
                'result_id': result.result_id,
                'columns': result.columns,
                'rows': sanitized_rows,
                'untrusted_data': untrusted_xml,
                'truncated': result.truncated,
                'calls_left': self.calls_left,
            }
            if is_empty_result(rows):
                response['hint'] = EMPTY_RESULT_HINT
            return response
        except QueryValidationError as exc:
            return {
                'error': exc.message,
                'calls_left': self.calls_left,
            }
        except ConnectionNotConfiguredError:
            return {
                'error': f"A fonte '{source}' não possui conexão configurada.",
                'calls_left': self.calls_left,
            }
        except SourceUnavailableError:
            return {
                'error': f"A fonte '{source}' está indisponível.",
                'calls_left': self.calls_left,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                'error': f'Erro ao consultar os dados: {exc}',
                'calls_left': self.calls_left,
            }

    async def _federated_schema(self) -> FederatedSchema:
        datasources = await self.session.scalars(
            select(CatalogDataSource).where(
                CatalogDataSource.enabled.is_(True)
            )
        )
        sources = [
            (datasource, await load_entities(self.session, datasource.id))
            for datasource in datasources
        ]
        return build_federated_schema(sources, await load_links(self.session))

    async def query_across_sources(
        self, sql: str, purpose: str = ''
    ) -> dict[str, Any]:
        """Executa a ferramenta query_across_sources."""
        response, sources, final_sql = await self._run_across_sources(
            sql, purpose
        )
        if self.query_observer:
            self.query_observer(
                QueryObservation(
                    source='+'.join(sources),
                    sql=final_sql,
                    row_count=len(response.get('rows', [])),
                    error=response.get('error'),
                    sources=sources,
                )
            )
        return response

    async def _run_across_sources(  # noqa: PLR0911
        self, sql: str, purpose: str
    ) -> tuple[dict[str, Any], tuple[str, ...], str]:
        self.queries_in_current_call += 1
        self.total_queries += 1
        cited = tuple(cited_sources(sql))

        def refused(message: str):
            return (
                {'error': message, 'calls_left': self.calls_left},
                cited,
                sql,
            )

        if self.queries_in_current_call > self.max_per_call:
            return refused(
                'Limite de consultas por chamada excedido '
                f'(máximo {self.max_per_call}).'
            )
        try:
            schema = await self._federated_schema()
            query = validate_federated_query(
                sql, schema, max_rows=self.max_rows
            )
            datasources = {
                source: await self._get_datasource(source)
                for source in query.sources
            }
            names = ' e '.join(ds.name for ds in datasources.values())
            if self.on_activity:
                await self.on_activity(
                    '+'.join(query.sources),
                    names,
                    sanitize_purpose(purpose, names),
                )
            urls = {
                source: resolve_connection_url(ds.connection_env)
                for source, ds in datasources.items()
            }
            executed = await execute_federated_query(
                query, urls, self.federation_limits
            )
        except QueryValidationError as exc:
            return refused(exc.message)
        except ConnectionNotConfiguredError:
            return refused('Uma das fontes não possui conexão configurada.')
        except SourceUnavailableError as exc:
            return refused(f"A fonte '{exc}' está indisponível.")

        result = self.result_store.add(
            '+'.join(query.sources),
            query.sql,
            executed.columns,
            executed.rows,
            truncated=executed.truncated,
            column_types=executed.column_types,
            origin=build_origin(
                [ds.name for ds in datasources.values()],
                purpose,
                executed.coverage,
            ),
        )
        rows = [
            [sanitize_untrusted_text(val) for val in row]
            for row in executed.rows
        ]
        response = {
            'result_id': result.result_id,
            'columns': result.columns,
            'rows': rows,
            'untrusted_data': format_untrusted_data_xml(
                names,
                result.result_id,
                result.columns,
                rows,
                truncated=result.truncated,
            ),
            'truncated': result.truncated,
            'coverage': executed.coverage,
            'calls_left': self.calls_left,
        }
        if is_empty_result(executed.rows):
            response['hint'] = EMPTY_RESULT_HINT
        return response, query.sources, query.sql

    def show_chart(  # noqa: PLR0913, PLR0917
        self,
        result_id: str,
        chart_type: str,
        title: str,
        x: str,
        series: list[str],
        labels: dict[str, str] | None = None,
        units: dict[str, str] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        """Registra pedido de gráfico a ser montado pelo servidor."""
        result = self.result_store.get(result_id)
        if not result:
            return {'error': f"Resultado '{result_id}' não encontrado."}

        cols_set = set(result.columns)
        if x not in cols_set:
            return {'error': f"Coluna '{x}' não encontrada no resultado."}

        for s in series:
            if s not in cols_set:
                return {'error': f"Coluna '{s}' não encontrada no resultado."}

        try:
            if group_by:
                check_group_request(result, chart_type, x, series, group_by)
                groups, data = group_chart_rows(result, x, series[0], group_by)
                group = {
                    'key': group_by,
                    'label': column_label(group_by, labels),
                }
                chart_series = [
                    {
                        'key': key,
                        'label': (labels or {}).get(key) or label,
                        'unit': (units or {}).get(series[0]) or None,
                    }
                    for key, label in groups.items()
                ]
            else:
                data = plain_chart_rows(result, chart_type, x, series)
                group = None
                chart_series = [
                    {
                        'key': s,
                        'label': column_label(s, labels),
                        'unit': (units or {}).get(s) or None,
                    }
                    for s in series
                ]
        except ValueError as exc:
            return {'error': str(exc)}

        chart_block = {
            'type': 'chart',
            'chart_type': chart_type,
            'title': title,
            'x': {
                'key': x,
                'label': column_label(x, labels),
                'type': axis_type(result.column_types.get(x)),
            },
            'series': chart_series,
            'data': data,
            'group': group,
            'truncated': result.truncated,
            'origin': result.origin,
        }
        self.pending_blocks.append(mask_value(chart_block))
        return {'status': 'ok', 'block_index': len(self.pending_blocks)}

    def show_table(
        self,
        result_id: str,
        columns: list[str],
        title: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Registra pedido de tabela a ser montada pelo servidor."""
        result = self.result_store.get(result_id)
        if not result:
            return {'error': f"Resultado '{result_id}' não encontrado."}

        cols_set = set(result.columns)
        for c in columns:
            if c not in cols_set:
                return {'error': f"Coluna '{c}' não encontrada no resultado."}

        rows = [
            {
                col_name: val
                for col_name, val in zip(result.columns, row, strict=False)
                if col_name in columns
            }
            for row in result.rows
        ]
        table_block = {
            'type': 'table',
            'title': title,
            'columns': [
                {
                    'key': c,
                    'label': column_label(c, labels),
                    'type': (
                        'string'
                        if is_year_column(c, (row.get(c) for row in rows))
                        else table_column_type(result.column_types.get(c))
                    ),
                }
                for c in columns
            ],
            'rows': rows,
            'truncated': result.truncated,
            'origin': result.origin,
        }
        self.pending_blocks.append(mask_value(table_block))
        return {'status': 'ok', 'block_index': len(self.pending_blocks)}

    def build_query_tools(
        self, *, across_sources: bool = False
    ) -> list[StructuredTool]:
        """Ferramentas completas (consulta + apresentação)."""
        federated = [
            StructuredTool.from_function(
                coroutine=self.query_across_sources,
                name='query_across_sources',
                description=(
                    'Consulta duas fontes numa só consulta, juntando-as por '
                    'uma ligação do catálogo. Devolve linhas, colunas, '
                    'result_id e a cobertura da ligação.'
                ),
                args_schema=QueryAcrossSourcesInput,
            )
        ]
        return [
            StructuredTool.from_function(
                coroutine=self.query_data,
                name='query_data',
                description=(
                    'Consulta uma fonte de dados ativa do catálogo usando SQL '
                    'somente leitura. Devolve linhas, colunas e result_id.'
                ),
                args_schema=QueryDataInput,
            ),
            *(federated if across_sources else []),
            StructuredTool.from_function(
                func=self.show_chart,
                name='show_chart',
                description=(
                    'Gera um gráfico a partir de um resultado prévio. '
                    'O servidor preenche os dados automaticamente. Para '
                    'comparar categorias ao longo de x, use group_by.'
                ),
                args_schema=ShowChartInput,
            ),
            StructuredTool.from_function(
                func=self.show_table,
                name='show_table',
                description=(
                    'Gera uma tabela a partir de um resultado prévio. '
                    'O servidor preenche os dados automaticamente.'
                ),
                args_schema=ShowTableInput,
            ),
        ]

    async def close(self) -> None:
        """Descarta engines abertos."""
        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()
