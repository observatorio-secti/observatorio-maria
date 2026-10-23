"""Execução somente leitura com limites de tempo e linhas."""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from observatorio_maria.catalog.introspection import SourceUnavailableError
from observatorio_maria.query.errors import QueryValidationError

MAX_PURPOSE_LENGTH = 120


class QueryTimeoutError(QueryValidationError):
    """Tempo limite de execução da consulta esgotado."""

    def __init__(self, message: str = 'Tempo limite de execução esgotado'):
        super().__init__(message)


def serialize_value(val: Any) -> Any:
    """Converte valores do banco para tipos JSON seguros."""
    if val is None or isinstance(val, (bool, int, float, str)):
        return val
    if isinstance(val, (datetime, date, time)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return int(val) if val % 1 == 0 else float(val)
    if isinstance(val, (list, tuple)):
        return [serialize_value(x) for x in val]
    if isinstance(val, dict):
        return {str(k): serialize_value(v) for k, v in val.items()}
    return (
        val.decode('utf-8', errors='replace')
        if isinstance(val, bytes)
        else str(val)
    )


def _infer_type(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return 'date'
    if isinstance(val, (int, float, Decimal)):
        return 'number'
    if isinstance(val, str) and re.match(r'^\d{4}-\d{2}-\d{2}', val):
        return 'date'
    return 'string'


def infer_column_types(
    columns: list[str], rows: list[list[Any]]
) -> dict[str, str]:
    """Infere tipos ('date', 'number', 'string') a partir das linhas."""
    types: dict[str, str] = {}
    for col_idx, col_name in enumerate(columns):
        col_type = 'string'
        for row in rows:
            if col_idx < len(row):
                inferred = _infer_type(row[col_idx])
                if inferred:
                    col_type = inferred
                    break
        types[col_name] = col_type
    return types


@dataclass
class QueryResult:
    """Resultado de uma consulta retido em memória durante a resposta."""

    result_id: str
    source: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool
    column_types: dict[str, str] = field(default_factory=dict)


class ResultStore:
    """Armazenamento em memória de resultados por resposta."""

    def __init__(self):
        self._results: dict[str, QueryResult] = {}
        self._counter: int = 0

    def add(  # noqa: PLR0913
        self,
        source: str,
        sql: str,
        columns: list[str],
        rows: list[list[Any]],
        *,
        truncated: bool,
        column_types: dict[str, str] | None = None,
    ) -> QueryResult:
        self._counter += 1
        result_id = f'r{self._counter}'
        res = QueryResult(
            result_id=result_id,
            source=source,
            sql=sql,
            columns=columns,
            rows=rows,
            truncated=truncated,
            column_types=column_types or {},
        )
        self._results[result_id] = res
        return res

    def get(self, result_id: str) -> QueryResult | None:
        return self._results.get(result_id)

    def all(self) -> list[QueryResult]:
        return list(self._results.values())


def sanitize_purpose(purpose: str | None, source_name: str) -> str:
    """Garante descrição curta válida para evento activity (até 120 chars)."""
    if not purpose or not purpose.strip():
        return f'Consultando {source_name}'
    cleaned = purpose.strip()
    upper = cleaned.upper()
    if upper.startswith(('SELECT', 'WITH', 'FROM', 'WHERE')):
        return f'Consultando {source_name}'
    if len(cleaned) > MAX_PURPOSE_LENGTH:
        cleaned = cleaned[: MAX_PURPOSE_LENGTH - 3] + '...'
    return cleaned


def _clean_error(exc: Exception) -> str:
    msg = str(exc)
    msg = re.sub(r'//[^@/]+@[^/]+', '//***@***', msg)
    msg = re.sub(r'(?:postgresql|sqlite)\S+', '[conexao]', msg)
    msg = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[ip]', msg)
    return msg.strip()


async def execute_readonly_query(
    engine: AsyncEngine,
    sql: str,
    *,
    max_rows: int = 100,
    timeout_seconds: float = 15.0,
) -> tuple[list[str], list[list[Any]], bool, dict[str, str]]:
    """Executa a consulta na origem somente leitura com limite e timeout."""
    wrapped_sql = f'SELECT * FROM ({sql}) AS q LIMIT {max_rows + 1}'
    backend = engine.url.get_backend_name()

    try:
        async with asyncio.timeout(timeout_seconds):
            try:
                async with engine.connect() as conn:
                    if backend == 'postgresql':
                        timeout_ms = int(timeout_seconds * 1000)
                        await conn.execute(
                            text(f'SET LOCAL statement_timeout = {timeout_ms}')
                        )
                        await conn.execute(text('SET TRANSACTION READ ONLY'))

                    cursor = await conn.execute(text(wrapped_sql))
                    columns = list(cursor.keys())
                    raw_rows = cursor.fetchall()
                    truncated = len(raw_rows) > max_rows
                    if truncated:
                        raw_rows = raw_rows[:max_rows]

                    column_types = infer_column_types(columns, raw_rows)
                    serialized_rows = [
                        [serialize_value(val) for val in row]
                        for row in raw_rows
                    ]
                    return columns, serialized_rows, truncated, column_types
            except (OperationalError, DBAPIError) as exc:
                low = str(exc).lower()
                if (
                    'connection' in low
                    or 'refused' in low
                    or 'could not connect' in low
                    or 'server closed' in low
                ):
                    raise SourceUnavailableError(
                        'Não foi possível conectar à fonte de dados'
                    ) from exc
                raise
    except TimeoutError as exc:
        raise QueryTimeoutError('Tempo limite de execução esgotado') from exc
    except SourceUnavailableError:
        raise
    except (DBAPIError, OperationalError, SQLAlchemyError) as exc:
        err_msg = _clean_error(exc)
        low = err_msg.lower()
        if 'timeout' in low or 'canceling statement' in low:
            raise QueryTimeoutError(
                'Tempo limite de execução esgotado'
            ) from exc
        raise QueryValidationError(
            f'Erro na execução da consulta: {err_msg}'
        ) from exc
