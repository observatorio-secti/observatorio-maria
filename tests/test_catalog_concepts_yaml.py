from pathlib import Path

import pytest
from sqlalchemy import select

from observatorio_maria.catalog import seed as seed_cli
from observatorio_maria.catalog.yaml_io import (
    CatalogFileError,
    ConceptsFile,
    dump_concepts_file,
    export_concepts,
    load_catalog_file,
    load_seed_file,
    seed_catalog,
    seed_concepts,
)
from observatorio_maria.models import CatalogConcept, CatalogEntity
from tests.test_catalog_yaml import CATALOG_YAML

CONCEPTS_YAML = """
concepts:
  - id: bolsas
    label: Bolsas
    description: Bolsas concedidas.
    synonyms: [bolsa]
    instructions: |
      - Use a fonte origem.
    entities: [origem:main.bolsas, origem:main.bolsas_por_status]
  - id: pessoas
    label: Pessoas
    entities: [origem:main.pesquisadores, outra:public.researcher]
"""


@pytest.fixture
def files(tmp_path):
    source = tmp_path / 'origem.yaml'
    source.write_text(CATALOG_YAML, encoding='utf-8')
    concepts = tmp_path / 'concepts.yaml'
    concepts.write_text(CONCEPTS_YAML, encoding='utf-8')
    return source, concepts


@pytest.fixture
async def seeded(session, files):
    source, concepts = files
    await seed_catalog(session, load_catalog_file(source))
    return await seed_concepts(session, load_seed_file(concepts))


async def concept_of(session):
    rows = await session.execute(
        select(CatalogEntity.name, CatalogEntity.concept_id)
    )
    return dict(rows.all())


async def test_seed_creates_concepts_and_links(session, seeded):
    assert seeded.created == 2  # noqa: PLR2004
    assert seeded.linked == 3  # noqa: PLR2004
    assert seeded.missing == ['outra:public.researcher']
    assert await concept_of(session) == {
        'bolsas': 'bolsas',
        'bolsas_por_status': 'bolsas',
        'pesquisadores': 'pessoas',
    }
    bolsas = await session.get(CatalogConcept, 'bolsas')
    assert bolsas.instructions.strip() == '- Use a fonte origem.'


async def test_seed_keeps_edited_concept_and_links(session, files, seeded):
    bolsas = await session.get(CatalogConcept, 'bolsas')
    bolsas.instructions = 'Política editada.'
    entity = await session.scalar(
        select(CatalogEntity).where(CatalogEntity.name == 'pesquisadores')
    )
    entity.concept_id = 'bolsas'
    await session.commit()

    report = await seed_concepts(session, load_seed_file(files[1]))

    assert (report.created, report.linked) == (0, 0)
    assert bolsas.instructions == 'Política editada.'
    assert (await concept_of(session))['pesquisadores'] == 'bolsas'


async def test_seed_reset_recreates_concepts(session, files, seeded):
    bolsas = await session.get(CatalogConcept, 'bolsas')
    bolsas.instructions = 'Política editada.'
    await session.commit()

    report = await seed_concepts(session, load_seed_file(files[1]), reset=True)

    assert report.created == 2  # noqa: PLR2004
    bolsas = await session.get(CatalogConcept, 'bolsas')
    assert bolsas.instructions.strip() == '- Use a fonte origem.'
    assert (await concept_of(session))['bolsas_por_status'] == 'bolsas'


async def test_export_round_trip(session, files, seeded):
    exported = await export_concepts(session)
    text = dump_concepts_file(exported)
    path = files[1].parent / 'exportado.yaml'
    path.write_text(text, encoding='utf-8')

    await seed_concepts(session, load_seed_file(path), reset=True)

    assert await export_concepts(session) == exported
    assert 'origem:main.bolsas_por_status' in text
    assert 'outra:public.researcher' not in text


async def test_export_route(client, session, seeded):
    response = await client.get('/catalog/concepts/export')

    assert response.status_code == 200  # noqa: PLR2004
    assert response.headers['content-type'].startswith('application/yaml')
    assert 'id: bolsas' in response.text


@pytest.mark.parametrize(
    ('content', 'message'),
    [
        (
            'concepts:\n  - id: a\n    label: A\n  - id: a\n    label: B\n',
            'repetido',
        ),
        (
            'concepts:\n  - id: a\n    label: A\n    entities: [semfonte]\n',
            'entities',
        ),
        ('concepts:\n  - id: A\n    label: A\n', 'id'),
    ],
)
def test_invalid_concepts_file(tmp_path, content, message):
    path = tmp_path / 'concepts.yaml'
    path.write_text(content, encoding='utf-8')

    with pytest.raises(CatalogFileError, match=message):
        load_seed_file(path)


def test_cli_rejects_invalid_concepts_before_writing(files, capsys):
    source, concepts = files
    concepts.write_text('concepts:\n  - id: A\n    label: A\n')

    assert seed_cli.main([str(concepts), str(source)]) == 1
    assert 'Erro' in capsys.readouterr().err


def test_repository_concepts_file_is_valid():
    document = load_seed_file(Path('catalog/concepts.yaml'))

    assert isinstance(document, ConceptsFile)
    assert {c.id for c in document.concepts} == {
        'projetos',
        'instituicoes',
        'pesquisadores',
    }


async def test_repository_concepts_link_seeded_sources(session):
    for name in ('fomento', 'simcc'):
        await seed_catalog(
            session, load_catalog_file(Path(f'catalog/{name}.yaml'))
        )

    report = await seed_concepts(
        session, load_seed_file(Path('catalog/concepts.yaml'))
    )

    assert report.missing == []
    expected = sum(
        len(c.entities)
        for c in load_seed_file(Path('catalog/concepts.yaml')).concepts
    )
    assert report.linked == expected
