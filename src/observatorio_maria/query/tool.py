"""Ferramentas LangChain para consulta e apresentação de dados."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
    sanitize_untrusted_text,
)
from observatorio_maria.query.validator import (
    QuerySchema,
    build_query_schema,
    source_dialect,
    validate_query,
)


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


def column_label(key: str, labels: dict[str, str] | None) -> str:
    """Rótulo informado pelo modelo ou, sem ele, a chave legível."""
    if labels and labels.get(key):
        return labels[key]
    text = key.replace('_', ' ').strip()
    return text[:1].upper() + text[1:]


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

        chart_block = {
            'type': 'chart',
            'chart_type': chart_type,
            'title': title,
            'x': {
                'key': x,
                'label': column_label(x, labels),
                'type': result.column_types.get(x, 'category'),
            },
            'series': [
                {
                    'key': s,
                    'label': column_label(s, labels),
                    'unit': (units or {}).get(s) or None,
                }
                for s in series
            ],
            'data': [
                {
                    col_name: val
                    for col_name, val in zip(result.columns, row, strict=False)
                    if col_name == x or col_name in series
                }
                for row in result.rows
            ],
            'truncated': result.truncated,
            'origin': result.origin,
        }
        self.pending_blocks.append(chart_block)
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

        table_block = {
            'type': 'table',
            'title': title,
            'columns': [
                {
                    'key': c,
                    'label': column_label(c, labels),
                    'type': result.column_types.get(c, 'string'),
                }
                for c in columns
            ],
            'rows': [
                {
                    col_name: val
                    for col_name, val in zip(result.columns, row, strict=False)
                    if col_name in columns
                }
                for row in result.rows
            ],
            'truncated': result.truncated,
            'origin': result.origin,
        }
        self.pending_blocks.append(table_block)
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
                    'O servidor preenche os dados automaticamente.'
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
