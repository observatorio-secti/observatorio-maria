"""Relatório da avaliação no terminal e em JSON."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from observatorio_maria.evaluation.reference import ReferenceQuestion
from observatorio_maria.evaluation.runner import QuestionRun
from observatorio_maria.llm.registry import ModelRegistry

STATUS_LABELS = {'passed': 'ok', 'failed': 'falhou', 'error': 'erro'}


@dataclass
class QuestionSummary:
    question_id: str
    tags: list[str]
    passed: int
    runs: int
    avg_tokens: float
    avg_model_calls: float
    avg_queries: float
    sources: list[str]
    problems: list[str]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(
    questions: list[ReferenceQuestion], runs: list[QuestionRun]
) -> list[QuestionSummary]:
    summaries = []
    for question in questions:
        own = [r for r in runs if r.question_id == question.id]
        if not own:
            continue
        problems = []
        for run in own:
            if run.error:
                problems.append(f'#{run.repetition} erro: {run.error}')
            problems.extend(
                f'#{run.repetition} {check.type} '
                f'({STATUS_LABELS[check.status]}): {check.detail}'
                for check in run.checks
                if check.status != 'passed'
            )
        summaries.append(
            QuestionSummary(
                question_id=question.id,
                tags=question.tags,
                passed=sum(r.status == 'passed' for r in own),
                runs=len(own),
                avg_tokens=_mean([r.tokens for r in own]),
                avg_model_calls=_mean([r.model_calls for r in own]),
                avg_queries=_mean([len(r.queries) for r in own]),
                sources=sorted({
                    q.source for r in own for q in r.queries if not q.error
                }),
                problems=problems,
            )
        )
    return summaries


def _br(value: float, digits: int = 0) -> str:
    text = f'{value:,.{digits}f}'
    return text.replace(',', '_').replace('.', ',').replace('_', '.')


def format_summary(summaries: list[QuestionSummary]) -> str:
    width = max((len(s.question_id) for s in summaries), default=10)
    lines = []
    for s in summaries:
        lines.append(
            f'{s.question_id:<{width}}  {s.passed}/{s.runs}  '
            f'tokens {_br(s.avg_tokens):>7}  '
            f'chamadas {_br(s.avg_model_calls, 1)}  '
            f'consultas {_br(s.avg_queries, 1)}  '
            f'fontes {", ".join(s.sources) or "-"}'
        )
        lines.extend(f'    {problem}' for problem in s.problems)
    passed = sum(s.passed for s in summaries)
    total = sum(s.runs for s in summaries)
    tokens = sum(s.avg_tokens * s.runs for s in summaries)
    lines.append('')
    lines.append(f'Acertos: {passed}/{total}  Tokens: {_br(tokens)}')
    return '\n'.join(lines)


def build_report(
    questions: list[ReferenceQuestion],
    runs: list[QuestionRun],
    registry: ModelRegistry,
    started_at: datetime,
) -> dict[str, Any]:
    summaries = summarize(questions, runs)
    by_id = {q.id: q for q in questions}
    return {
        'started_at': started_at.isoformat(),
        'models': {str(m.tier): m.name for m in registry.all()},
        'passed': sum(s.passed for s in summaries),
        'runs': sum(s.runs for s in summaries),
        'questions': [
            {
                **asdict(summary),
                'question': by_id[summary.question_id].question,
                'results': [
                    asdict(r)
                    for r in runs
                    if r.question_id == summary.question_id
                ],
            }
            for summary in summaries
        ],
    }


def write_report(report: dict[str, Any], results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.fromisoformat(report['started_at'])
    path = results_dir / f'{started_at:%Y-%m-%dT%H-%M-%S}.json'
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding='utf-8',
    )
    return path
