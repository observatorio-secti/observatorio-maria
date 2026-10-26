"""Ferramentas LangChain para consulta e apresentação de dados."""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from observatorio_maria.catalog.introspection import (
    ConnectionNotConfiguredError,
    SourceUnavailableError,
    create_readonly_engine,
    resolve_connection_url,
)
from observatorio_maria.catalog.sync import load_entities
from observatorio_maria.models import CatalogDataSource
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.execution import (
    ResultStore,
    execute_readonly_query,
    sanitize_purpose,
)
from observatorio_maria.query.sanitization import (
    format_untrusted_data_xml,
    sanitize_untrusted_text,
)
from observatorio_maria.query.validator import (
    QuerySchema,
    build_query_schema,
    validate_query,
)


class QueryDataInput(BaseModel):
    source: str = Field(
        description='Identificador da fonte no catálogo (ex.: "fomento").'
    )
    sql: str = Field(
        description='Instrução SELECT SQL a ser executada na fonte.'
    )
    purpose: str = Field(
        default='',
        description='Descrição curta do que está sendo consultado '
        '(ex.: "Buscando projetos sobre dengue").',
    )


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
            backend = 'sqlite'
            try:
                url = resolve_connection_url(datasource.connection_env)
                if 'postgres' in url or 'psycopg' in url:
                    backend = 'postgres'
            except ConnectionNotConfiguredError:
                pass
            schema = build_query_schema(datasource, entities, dialect=backend)
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

    async def query_data(  # noqa: PLR0911
        self, source: str, sql: str, purpose: str = ''
    ) -> dict[str, Any]:
        """Executa a ferramenta query_data."""
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
            return {
                'result_id': result.result_id,
                'columns': result.columns,
                'rows': sanitized_rows,
                'untrusted_data': untrusted_xml,
                'truncated': result.truncated,
                'calls_left': self.calls_left,
            }
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

    def show_chart(
        self,
        result_id: str,
        chart_type: str,
        title: str,
        x: str,
        series: list[str],
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
                'label': x,
                'type': result.column_types.get(x, 'category'),
            },
            'series': [{'key': s, 'label': s} for s in series],
            'data': [
                {
                    col_name: val
                    for col_name, val in zip(result.columns, row, strict=False)
                    if col_name == x or col_name in series
                }
                for row in result.rows
            ],
        }
        self.pending_blocks.append(chart_block)
        return {'status': 'ok', 'block_index': len(self.pending_blocks)}

    def show_table(
        self,
        result_id: str,
        columns: list[str],
        title: str | None = None,
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
                    'label': c,
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
        }
        self.pending_blocks.append(table_block)
        return {'status': 'ok', 'block_index': len(self.pending_blocks)}

    def build_query_tools(self) -> list[StructuredTool]:
        """Ferramentas completas (consulta + apresentação)."""
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

    def build_presentation_tools(self) -> list[StructuredTool]:
        """Apenas ferramentas de apresentação."""
        return [
            StructuredTool.from_function(
                func=self.show_chart,
                name='show_chart',
                description='Gera um gráfico a partir de um result_id.',
                args_schema=ShowChartInput,
            ),
            StructuredTool.from_function(
                func=self.show_table,
                name='show_table',
                description='Gera uma tabela a partir de um result_id.',
                args_schema=ShowTableInput,
            ),
        ]

    async def close(self) -> None:
        """Descarta engines abertos."""
        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()
