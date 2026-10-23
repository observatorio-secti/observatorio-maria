"""Carrega arquivos YAML no catálogo.

Uso: python -m observatorio_maria.catalog.seed ARQUIVO... [--reset]
"""

import argparse
import asyncio
import sys
from pathlib import Path

from observatorio_maria.catalog.yaml_io import (
    CatalogFileError,
    load_catalog_file,
    seed_catalog,
)
from observatorio_maria.database import SessionLocal


async def run(paths: list[Path], *, reset: bool) -> None:
    # Valida todos os arquivos antes de gravar qualquer um.
    documents = [load_catalog_file(path) for path in paths]
    async with SessionLocal() as session:
        for path, document in zip(paths, documents, strict=True):
            report = await seed_catalog(session, document, reset=reset)
            status = 'criada' if report.datasource_created else 'existente'
            print(
                f'{path}: fonte {document.datasource.id} ({status}); '
                f'{report.entities} entidade(s), {report.columns} coluna(s) '
                f'e {report.relationships} relacionamento(s) criados'
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('paths', nargs='+', type=Path)
    parser.add_argument(
        '--reset',
        action='store_true',
        help='recria cada fonte a partir do arquivo, descartando edições',
    )
    args = parser.parse_args(argv)
    try:
        asyncio.run(run(args.paths, reset=args.reset))
    except (CatalogFileError, OSError) as exc:
        print(f'Erro: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
