"""Execução de consultas entre fontes num DuckDB em memória.

Cada consulta tem o seu banco, descartado no fim. As origens entram em modo
somente leitura; depois disso, o acesso externo é desligado e a configuração,
travada. O SQL já passou por `validate_federated_query`.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import duckdb
from sqlalchemy.engine import make_url

from observatorio_maria.catalog.introspection import SourceUnavailableError
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.execution import (
    QueryTimeoutError,
    _clean_error,
    infer_column_types,
    serialize_value,
)
from observatorio_maria.query.federated_validator import FederatedQuery

logger = logging.getLogger(__name__)

# Tempo para o DuckDB parar depois da interrupção.
INTERRUPT_GRACE_SECONDS = 5.0
MEMORY_ERROR = (
    'A consulta excedeu o limite de memória. Filtre mais ou use as views '
    'canônicas para reduzir o volume lido.'
)


@dataclass(frozen=True)
class FederationLimits:
    max_rows: int = 100
    timeout_seconds: float = 15.0
    memory_limit: str = '512MB'
    threads: int = 2
    max_concurrent: int = 2


@dataclass(frozen=True)
class FederatedResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool
    column_types: dict[str, str]
    coverage: dict[str, Any] | None


@lru_cache
def _slots(max_concurrent: int) -> threading.BoundedSemaphore:
    """Vagas de consulta do processo; a espera acontece na thread da
    consulta, então não depende do laço de eventos."""
    return threading.BoundedSemaphore(max_concurrent)


def _libpq_value(value: Any) -> str:
    text = str(value).replace('\\', '\\\\').replace("'", "\\'")
    return f"'{text}'"


def _attach_statement(source: str, url: str, timeout_ms: int) -> str:
    """ATTACH somente leitura; no Postgres, a própria conexão limita o tempo
    de cada comando e abre transações somente leitura."""
    parsed = make_url(url)
    backend = parsed.get_backend_name()
    if backend == 'sqlite':
        target = parsed.database
        kind = 'sqlite'
    else:
        options = (
            f'-c statement_timeout={timeout_ms} '
            '-c default_transaction_read_only=on'
        )
        fields = {
            'host': parsed.host,
            'port': parsed.port,
            'dbname': parsed.database,
            'user': parsed.username,
            'password': parsed.password,
            'options': options,
        }
        target = ' '.join(
            f'{key}={_libpq_value(value)}'
            for key, value in fields.items()
            if value is not None
        )
        kind = 'postgres'
    literal = target.replace("'", "''")
    return f'ATTACH \'{literal}\' AS "{source}" (TYPE {kind}, READ_ONLY)'


class _Execution:
    """Uma consulta numa thread, interrompível de fora."""

    def __init__(
        self,
        query: FederatedQuery,
        urls: dict[str, str],
        limits: FederationLimits,
    ):
        self.query = query
        self.urls = urls
        self.limits = limits
        self.deadline = time.monotonic() + limits.timeout_seconds
        self.connection: duckdb.DuckDBPyConnection | None = None
        self.cancelled = False

    def interrupt(self) -> None:
        self.cancelled = True
        if self.connection is not None:
            self.connection.interrupt()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        connection = duckdb.connect(
            ':memory:',
            config={
                'memory_limit': self.limits.memory_limit,
                'threads': str(self.limits.threads),
                'autoinstall_known_extensions': 'false',
                'autoload_known_extensions': 'false',
            },
        )
        self.connection = connection
        kinds = {
            make_url(url).get_backend_name() for url in self.urls.values()
        }
        for kind in kinds:
            connection.execute(
                f'LOAD {"sqlite" if kind == "sqlite" else "postgres"}'
            )
        timeout_ms = int(self.limits.timeout_seconds * 1000)
        for source, url in self.urls.items():
            try:
                connection.execute(_attach_statement(source, url, timeout_ms))
            except duckdb.Error as exc:
                raise SourceUnavailableError(source) from exc
        connection.execute('SET enable_external_access=false')
        connection.execute('SET lock_configuration=true')
        return connection

    def _coverage(self, connection) -> dict[str, Any] | None:
        coverage = self.query.coverage
        if coverage is None:
            return {'available': False, 'reason': self.query.coverage_reason}
        try:
            total, found = connection.execute(coverage.sql).fetchone()
        except duckdb.Error as exc:
            logger.warning('Cobertura não calculada: %s', _clean_error(exc))
            return {
                'available': False,
                'reason': 'Não foi possível calcular a cobertura',
            }
        return {
            'available': True,
            'source': coverage.source,
            'target': coverage.target,
            'keys': total,
            'found': found,
        }

    def run(self) -> FederatedResult:
        slots = _slots(self.limits.max_concurrent)
        wait = max(self.deadline - time.monotonic(), 0)
        if not slots.acquire(timeout=wait):
            raise QueryTimeoutError
        try:
            if self.cancelled:
                raise QueryTimeoutError
            return self._execute()
        finally:
            slots.release()

    def _execute(self) -> FederatedResult:
        connection = self._connect()
        try:
            max_rows = self.limits.max_rows
            cursor = connection.execute(
                f'SELECT * FROM ({self.query.sql}) AS q LIMIT {max_rows + 1}'
            )
            columns = [item[0] for item in cursor.description]
            raw_rows = cursor.fetchall()
            truncated = len(raw_rows) > max_rows
            raw_rows = raw_rows[:max_rows]
            return FederatedResult(
                columns=columns,
                rows=[[serialize_value(v) for v in row] for row in raw_rows],
                truncated=truncated,
                column_types=infer_column_types(columns, raw_rows),
                coverage=self._coverage(connection),
            )
        finally:
            connection.close()


async def execute_federated_query(
    query: FederatedQuery,
    urls: dict[str, str],
    limits: FederationLimits,
) -> FederatedResult:
    """Executa a consulta em thread própria, dentro do tempo limite."""
    execution = _Execution(query, urls, limits)
    task = asyncio.ensure_future(asyncio.to_thread(execution.run))
    try:
        return await asyncio.wait_for(
            asyncio.shield(task), limits.timeout_seconds
        )
    except TimeoutError as exc:
        execution.interrupt()
        await asyncio.wait({task}, timeout=INTERRUPT_GRACE_SECONDS)
        if task.done():
            task.exception()
        raise QueryTimeoutError from exc
    except duckdb.InterruptException as exc:
        raise QueryTimeoutError from exc
    except duckdb.OutOfMemoryException as exc:
        raise QueryValidationError(MEMORY_ERROR) from exc
    except duckdb.Error as exc:
        raise QueryValidationError(
            f'Erro ao executar a consulta entre fontes: {_clean_error(exc)}'
        ) from exc
