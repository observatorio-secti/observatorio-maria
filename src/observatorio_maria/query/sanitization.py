"""Sanitização, mascaramento de PII e envelopamento de dados não confiáveis."""

import re
from typing import Any

MAX_CELL_LENGTH = 2000
TRUNCATION_SUFFIX = '... [texto truncado]'

CPF_PATTERN = re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b')
CPF_UNPUNCTUATED = re.compile(r'\b(CPF\s*[:=]?\s*)\d{11}\b', re.IGNORECASE)
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
)
DELIMITER_TAG_PATTERN = re.compile(
    r'<\s*(/?\s*(?:untrusted_database_data|record|field)\b[^>]*)>',
    re.IGNORECASE,
)


def mask_pii(text: str) -> str:
    """Mascara CPFs e e-mails pessoais identificáveis no texto."""
    text = CPF_PATTERN.sub('[CPF MASCARADO]', text)
    text = CPF_UNPUNCTUATED.sub(r'\1[CPF MASCARADO]', text)
    return EMAIL_PATTERN.sub('[E-MAIL MASCARADO]', text)


def mask_value(val: Any) -> Any:
    """Mascara PII em strings, inclusive dentro de listas e objetos."""
    if isinstance(val, str):
        return mask_pii(val)
    if isinstance(val, list):
        return [mask_value(item) for item in val]
    if isinstance(val, dict):
        return {mask_pii(key): mask_value(item) for key, item in val.items()}
    return val


def escape_quarantine_delimiters(text: str) -> str:
    """Escapa tags que simulam fechamento ou abertura da quarentena."""
    return DELIMITER_TAG_PATTERN.sub(r'&lt;\1&gt;', text)


def truncate_cell_text(text: str, max_length: int = MAX_CELL_LENGTH) -> str:
    """Trunca células com texto excessivamente longo para evitar saturação."""
    if len(text) > max_length:
        return text[:max_length] + TRUNCATION_SUFFIX
    return text


def sanitize_untrusted_text(val: Any) -> Any:
    """Aplica mascaramento de PII, escape de tags e truncamento em strings."""
    if isinstance(val, list):
        return [sanitize_untrusted_text(item) for item in val]
    if isinstance(val, dict):
        return {
            sanitize_untrusted_text(key): sanitize_untrusted_text(item)
            for key, item in val.items()
        }
    if not isinstance(val, str):
        return val

    masked = mask_pii(val)
    escaped = escape_quarantine_delimiters(masked)
    return truncate_cell_text(escaped)


def format_untrusted_data_xml(
    source: str,
    result_id: str,
    columns: list[str],
    rows: list[list[Any]],
    truncated: bool = False,
) -> str:
    """Empacota os dados em tags XML semânticas de quarentena para o modelo."""
    escaped_source = source.replace('"', '&quot;')
    escaped_result_id = result_id.replace('"', '&quot;')

    parts = [
        f'<untrusted_database_data source="{escaped_source}" '
        f'result_id="{escaped_result_id}" row_count="{len(rows)}" '
        f'truncated="{str(truncated).lower()}">'
    ]

    for idx, row in enumerate(rows, start=1):
        parts.append(f'  <record index="{idx}">')
        for col_name, val in zip(columns, row):
            clean_col = (
                col_name.replace('"', '&quot;')
                .replace('<', '')
                .replace('>', '')
            )
            clean_val = sanitize_untrusted_text(val)
            val_str = str(clean_val) if clean_val is not None else ''
            parts.append(f'    <field name="{clean_col}">{val_str}</field>')
        parts.append('  </record>')

    parts.append('</untrusted_database_data>')
    return '\n'.join(parts)
