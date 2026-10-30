"""Arquivo versionado de perguntas de referência (evals/reference.yaml)."""

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ReferenceFileError(Exception):
    """Arquivo de perguntas de referência ausente ou inválido."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class NumbersCheck(_Strict):
    """Todos os valores devem aparecer na resposta."""

    type: Literal['numbers']
    values: list[Decimal] = Field(min_length=1)


class ListCheck(_Strict):
    """Uma fração mínima dos itens deve aparecer na resposta."""

    type: Literal['list']
    items: list[str] = Field(min_length=1)
    min_ratio: float = Field(1.0, gt=0, le=1)


class SourcesCheck(_Strict):
    """Fontes que a resposta deve consultar e as que não pode consultar."""

    type: Literal['sources']
    required: list[str] = []
    forbidden: list[str] = []


class JudgeCheck(_Strict):
    """Critério textual avaliado pelo modelo-juiz."""

    type: Literal['judge']
    criterion: str = Field(min_length=1)


Check = Annotated[
    NumbersCheck | ListCheck | SourcesCheck | JudgeCheck,
    Field(discriminator='type'),
]


class VerifyStep(_Strict):
    """Consulta de conferência que produziu a resposta esperada.

    No SQL, `{previous}` vira a lista de valores da primeira coluna da etapa
    anterior e `{previous_count}`, o número de linhas dela. Com `source` igual
    a `federated`, a etapa é uma consulta entre fontes.
    """

    source: str
    sql: str
    column: str | None = None


class ReferenceQuestion(_Strict):
    id: str = Field(pattern=r'^[a-z0-9][a-z0-9-]*$')
    question: str = Field(min_length=1)
    tags: list[str] = []
    checks: list[Check] = Field(min_length=1)
    verify: list[VerifyStep] = []


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = '.'.join(str(part) for part in error['loc'])
    return f'{location}: {error["msg"]}' if location else error['msg']


def load_reference_file(path: Path) -> list[ReferenceQuestion]:
    """Carrega e valida o arquivo; o erro cita a pergunta com problema."""
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
    except OSError as exc:
        raise ReferenceFileError(
            f'Não foi possível ler {path}: {exc}'
        ) from exc
    except yaml.YAMLError as exc:
        raise ReferenceFileError(
            f'{path} não é um YAML válido: {exc}'
        ) from exc

    raw_questions = data.get('questions') if isinstance(data, dict) else None
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ReferenceFileError(f'{path}: a lista "questions" está vazia.')

    questions: list[ReferenceQuestion] = []
    seen: set[str] = set()
    for position, raw in enumerate(raw_questions, start=1):
        name = raw.get('id') if isinstance(raw, dict) else None
        label = f'"{name}"' if name else f'nº {position}'
        try:
            question = ReferenceQuestion.model_validate(raw)
        except ValidationError as exc:
            raise ReferenceFileError(
                f'Pergunta {label}: {_first_error(exc)}'
            ) from exc
        if question.id in seen:
            raise ReferenceFileError(
                f'Pergunta {label}: identificador repetido.'
            )
        seen.add(question.id)
        questions.append(question)
    return questions


def select_questions(
    questions: list[ReferenceQuestion],
    *,
    ids: list[str] | None = None,
    tags: list[str] | None = None,
) -> list[ReferenceQuestion]:
    """Filtra por identificador ou tag; sem filtros, devolve todas."""
    ids = ids or []
    tags = tags or []
    unknown = set(ids) - {q.id for q in questions}
    if unknown:
        raise ReferenceFileError(
            'Pergunta(s) inexistente(s): ' + ', '.join(sorted(unknown))
        )
    if not ids and not tags:
        return list(questions)
    return [q for q in questions if q.id in ids or set(q.tags) & set(tags)]
