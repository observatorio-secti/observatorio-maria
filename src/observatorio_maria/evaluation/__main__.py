"""Avalia a Maria com o modelo real contra as perguntas de referência.

Uso: python -m observatorio_maria.evaluation [--question ID]... [--tag TAG]...
     [--repeat N] [--check-expected] [--file ARQUIVO]
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from observatorio_maria.evaluation.reference import (
    ReferenceFileError,
    ReferenceQuestion,
    load_reference_file,
    select_questions,
)
from observatorio_maria.evaluation.report import (
    STATUS_LABELS,
    build_report,
    format_summary,
    summarize,
    write_report,
)
from observatorio_maria.evaluation.runner import (
    EvaluationError,
    QuestionRun,
    maria_database_copy,
    run_evaluation,
)
from observatorio_maria.evaluation.verify import (
    check_expected,
    format_expected,
)
from observatorio_maria.llm.registry import build_model_registry
from observatorio_maria.settings import Settings

DEFAULT_FILE = Path('evals/reference.yaml')
DEFAULT_RESULTS_DIR = Path('evals/results')


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('deve ser maior que zero')
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--file', type=Path, default=DEFAULT_FILE)
    parser.add_argument(
        '--question',
        action='append',
        default=[],
        metavar='ID',
        help='roda só esta pergunta (repetível)',
    )
    parser.add_argument(
        '--tag',
        action='append',
        default=[],
        help='roda as perguntas com esta tag (repetível)',
    )
    parser.add_argument(
        '--repeat',
        type=positive_int,
        default=1,
        help='repetições por pergunta (padrão 1)',
    )
    parser.add_argument(
        '--check-expected',
        action='store_true',
        help='confere as respostas esperadas nos bancos, sem chamar o modelo',
    )
    parser.add_argument(
        '--results-dir', type=Path, default=DEFAULT_RESULTS_DIR
    )
    return parser


def print_progress(run: QuestionRun, done: int, total: int) -> None:
    print(
        f'[{done}/{total}] {run.question_id} #{run.repetition}: '
        f'{STATUS_LABELS[run.status]} ({run.duration_seconds:.0f} s)',
        file=sys.stderr,
        flush=True,
    )


async def run_check_expected(
    questions: list[ReferenceQuestion], settings: Settings
) -> int:
    async with maria_database_copy(settings.DATABASE_URL) as session_factory:
        results = await check_expected(
            questions, session_factory=session_factory, settings=settings
        )
    print(format_expected(results))
    return int(any(r.status in {'divergent', 'error'} for r in results))


async def run_models(
    questions: list[ReferenceQuestion],
    settings: Settings,
    args: argparse.Namespace,
) -> int:
    try:
        registry = build_model_registry(settings)
    except Exception as exc:
        raise EvaluationError(
            f'Não foi possível instanciar os modelos: {exc}'
        ) from exc
    started_at = datetime.now(UTC)
    runs = await run_evaluation(
        questions,
        registry=registry,
        database_url=settings.DATABASE_URL,
        settings=settings,
        repeat=args.repeat,
        on_run=print_progress,
    )
    print(format_summary(summarize(questions, runs)))
    report = build_report(questions, runs, registry, started_at)
    path = write_report(report, args.results_dir)
    print(f'Relatório: {path}')
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        questions = select_questions(
            load_reference_file(args.file),
            ids=args.question,
            tags=args.tag,
        )
        if not questions:
            raise ReferenceFileError('Nenhuma pergunta com esses filtros.')
        settings = Settings()
        # Como na API: credenciais dos provedores e URLs das fontes.
        settings.export_environment()
        if args.check_expected:
            return asyncio.run(run_check_expected(questions, settings))
        return asyncio.run(run_models(questions, settings, args))
    except (ReferenceFileError, EvaluationError, OSError) as exc:
        print(f'Erro: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
