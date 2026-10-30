"""Critérios determinísticos sobre os blocos da resposta."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from observatorio_maria.evaluation.reference import (
    ListCheck,
    NumbersCheck,
    SourcesCheck,
)
from observatorio_maria.query.tool import QueryObservation

CheckStatus = Literal['passed', 'failed', 'error']

# Ordem importa: milhar com ponto ("3.653", "1.234,5"), decimal com vírgula,
# decimal com ponto e inteiro.
NUMBER_PATTERN = re.compile(
    r'(?<![\d.,])'
    r'(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d+\.\d+|\d+)'
    r'(?![\d])'
)


@dataclass(frozen=True)
class CheckResult:
    type: str
    status: CheckStatus
    detail: str


def _cell_texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [t for v in value.values() for t in _cell_texts(v)]
    if isinstance(value, list | tuple):
        return [t for v in value for t in _cell_texts(v)]
    return [str(value)]


def answer_texts(blocks: list[dict[str, Any]]) -> list[str]:
    """Textos avaliados: blocos de texto, células de tabela e dados de
    gráfico."""
    texts: list[str] = []
    for block in blocks:
        match block.get('type'):
            case 'text':
                texts.append(block.get('text') or '')
            case 'table':
                texts.extend(_cell_texts(block.get('rows')))
            case 'chart':
                texts.extend(_cell_texts(block.get('data')))
    return texts


def parse_number(raw: str) -> Decimal | None:
    """Converte um número escrito à brasileira ou em formato de máquina."""
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?', raw):
        raw = raw.replace('.', '').replace(',', '.')
    else:
        raw = raw.replace(',', '.')
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def extract_numbers(texts: list[str]) -> set[Decimal]:
    numbers = set()
    for text in texts:
        for raw in NUMBER_PATTERN.findall(text):
            number = parse_number(raw)
            if number is not None:
                numbers.add(number)
    return numbers


# Travessões e hifens tipográficos viram hífen simples.
DASHES = str.maketrans(
    dict.fromkeys('\u2010\u2011\u2012\u2013\u2014\u2212', '-')
)


def normalize_text(text: str) -> str:
    """Minúsculas, sem acentos, com um só tipo de hífen e espaços
    colapsados."""
    decomposed = unicodedata.normalize('NFKD', text.translate(DASHES))
    stripped = ''.join(c for c in decomposed if not unicodedata.combining(c))
    return ' '.join(stripped.lower().split())


def _format_number(value: Decimal) -> str:
    return format(value.normalize(), 'f')


def check_numbers(check: NumbersCheck, texts: list[str]) -> CheckResult:
    found = extract_numbers(texts)
    missing = [v for v in check.values if v not in found]
    if missing:
        return CheckResult(
            'numbers',
            'failed',
            'Não encontrado(s) na resposta: '
            + ', '.join(_format_number(v) for v in missing),
        )
    return CheckResult(
        'numbers', 'passed', f'{len(check.values)} valor(es) encontrado(s)'
    )


def check_list(check: ListCheck, texts: list[str]) -> CheckResult:
    haystack = normalize_text('\n'.join(texts))
    found = [i for i in check.items if normalize_text(i) in haystack]
    total = len(check.items)
    ratio = len(found) / total
    detail = f'{len(found)}/{total} itens encontrados'
    if ratio + 1e-9 < check.min_ratio:
        return CheckResult(
            'list',
            'failed',
            f'{detail} (mínimo {check.min_ratio:.0%})',
        )
    return CheckResult('list', 'passed', detail)


def check_sources(
    check: SourcesCheck, queries: list[QueryObservation]
) -> CheckResult:
    consulted = {
        source
        for q in queries
        if not q.error
        for source in (q.sources or (q.source,))
    }
    missing = sorted(set(check.required) - consulted)
    forbidden = sorted(set(check.forbidden) & consulted)
    listed = ', '.join(sorted(consulted)) or 'nenhuma'
    problems = []
    if missing:
        problems.append('não consultou ' + ', '.join(missing))
    if forbidden:
        problems.append('consultou ' + ', '.join(forbidden))
    if problems:
        return CheckResult(
            'sources',
            'failed',
            '; '.join(problems) + f' (fontes consultadas: {listed})',
        )
    return CheckResult('sources', 'passed', f'fontes consultadas: {listed}')
