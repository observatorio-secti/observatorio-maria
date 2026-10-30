"""Carrega arquivos YAML no catálogo.

Uso: python -m observatorio_maria.catalog.seed ARQUIVO... [--reset]

Cada arquivo é de uma fonte (`datasource:`) ou de conceitos (`concepts:`).
Os conceitos são aplicados depois das fontes, para as entidades já existirem.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from observatorio_maria.catalog.yaml_io import (
    CatalogFile,
    CatalogFileError,
    ConceptsFile,
    load_seed_file,
    seed_catalog,
    seed_concepts,
)
from observatorio_maria.database import SessionLocal


async def run(paths: list[Path], *, reset: bool) -> None:
    # Valida todos os arquivos antes de gravar qualquer um.
    documents = [(path, load_seed_file(path)) for path in paths]
    sources = [(p, d) for p, d in documents if isinstance(d, CatalogFile)]
    concepts = [(p, d) for p, d in documents if isinstance(d, ConceptsFile)]
    async with SessionLocal() as session:
        for path, document in sources:
            report = await seed_catalog(session, document, reset=reset)
            status = 'criada' if report.datasource_created else 'existente'
            print(
                f'{path}: fonte {document.datasource.id} ({status}); '
                f'{report.entities} entidade(s), {report.columns} coluna(s) '
                f'e {report.relationships} relacionamento(s) criados'
            )
        for path, document in concepts:
            report = await seed_concepts(session, document, reset=reset)
            print(
                f'{path}: {report.created} conceito(s) criado(s) e '
                f'{report.linked} entidade(s) vinculada(s) e '
                f'{report.links} ligação(ões) criada(s)'
            )
            for ref in report.missing:
                print(
                    f'{path}: aviso: entidade {ref} não está no catálogo',
                    file=sys.stderr,
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('paths', nargs='+', type=Path)
    parser.add_argument(
        '--reset',
        action='store_true',
        help=(
            'recria cada fonte e os conceitos a partir dos arquivos, '
            'descartando edições'
        ),
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
