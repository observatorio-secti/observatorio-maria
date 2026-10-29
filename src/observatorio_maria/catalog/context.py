"""Texto que o modelo recebe sobre uma fonte de dados.

É a única porta entre o catálogo e o prompt: o que não sai daqui o modelo
não enxerga. Itens ocultos ou ausentes nunca entram.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.models import (
    CatalogColumn,
    CatalogConcept,
    CatalogDataSource,
    CatalogEntity,
    CatalogRelationship,
    ColumnAccess,
    EntityKind,
    ValueListing,
)
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.validator import (
    build_query_schema,
    source_dialect,
    validate_query,
)
from observatorio_maria.settings import Settings

KIND_LABELS = {
    EntityKind.TABLE: 'tabela',
    EntityKind.VIEW: 'view',
    EntityKind.MATERIALIZED_VIEW: 'view materializada',
}


def _value(item: dict) -> str:
    text = f'`{item["value"]}`'
    if item.get('description'):
        text += f' = {item["description"]}'
    return text


def _known_values(column: CatalogColumn) -> list[dict]:
    """Valores que o modelo deve conhecer: os da origem (enum ou observados
    nos dados), na ordem dela, com as descrições editoriais (obsoletos ficam
    de fora); sem valores da origem, os valores editoriais."""
    if column.source_values is None:
        return column.values
    described = {str(item['value']): item for item in column.values}
    return [described.get(v, {'value': v}) for v in column.source_values]


# Média máxima de caracteres dos valores observados de uma categoria.
CATEGORY_MAX_AVERAGE_LENGTH = 30


def _listed_values(column: CatalogColumn, max_values: int) -> list[dict]:
    """Valores que entram no contexto, conforme `list_values`.

    Em `auto`, entram os de enum, os de colunas com valores descritos e os
    observados que parecem uma categoria: coluna não pesquisável, com até
    `max_values` valores curtos.
    """
    if column.list_values == ValueListing.NEVER:
        return []
    values = _known_values(column)
    if column.list_values == ValueListing.ALWAYS or not values:
        return values
    if column.enum_values is not None or column.source_values is None:
        return values
    if any(item.get('description') for item in column.values):
        return values
    average = sum(len(str(v['value'])) for v in values) / len(values)
    if (
        column.searchable
        or len(values) > max_values
        or average > CATEGORY_MAX_AVERAGE_LENGTH
    ):
        return []
    return values


def _column_line(
    column: CatalogColumn, max_values: int, link: str | None = None
) -> str:
    details = [column.data_type or 'tipo desconhecido']
    if column.primary_key:
        details.append('chave primária')
    line = f'- `{column.name}` ({", ".join(details)})'
    description = ': '.join(filter(None, [column.label, column.description]))
    if description:
        line += f': {description}'
    notes = []
    if column.synonyms:
        notes.append(f'Sinônimos: {", ".join(column.synonyms)}')
    if column.access == ColumnAccess.AGGREGATE:
        notes.append(
            '**Somente agregação**: use em filtros, agrupamentos e '
            'contagens, nunca liste valores individuais'
        )
    if column.searchable:
        notes.append('aceita busca textual')
    values = _listed_values(column, max_values)
    if values:
        notes.append(f'Valores: {"; ".join(_value(v) for v in values)}')
    for note in notes:
        line = f'{line.rstrip(".")}. {note}'
    if link:
        line = f'{line} {link}'
    return line


def _entity_section(
    entity: CatalogEntity,
    max_values: int,
    concept_label: str | None = None,
    links: dict[str, str] | None = None,
) -> list[str]:
    kind = KIND_LABELS.get(entity.kind, entity.kind or 'entidade')
    title = f'### `{entity.qualified_name}` ({kind})'
    if entity.label:
        title += f': {entity.label}'
    lines = [title]
    if entity.description:
        lines.append(entity.description)
    if entity.synonyms:
        lines.append(f'Sinônimos: {", ".join(entity.synonyms)}.')
    if concept_label:
        lines.append(
            f'Conceito: {concept_label} (veja "Conceitos em várias fontes").'
        )
    if not entity.queryable:
        lines.append('_Somente referência: não pode ser consultada._')
    columns = [c for c in entity.columns if c.visible and c.present]
    columns.sort(key=lambda c: (c.position is None, c.position, c.name))
    lines.append('Colunas:')
    links = links or {}
    lines.extend(
        _column_line(c, max_values, links.get(c.name)) for c in columns
    )
    return lines


def _examples_section(examples: list[dict] | None) -> list[str]:
    if not examples:
        return []
    lines = ['', '## Exemplos de consultas (few-shot)']
    for eg in examples:
        q = eg.get('question', '').strip()
        sql = eg.get('sql', '').strip()
        if q and sql:
            lines.append(f'- Pergunta: "{q}"')
            lines.append('  ```sql')
            for sql_line in sql.splitlines():
                lines.append(f'  {sql_line}')
            lines.append('  ```')
    return lines


def check_examples(
    datasource: CatalogDataSource, entities: list[CatalogEntity]
) -> tuple[list[dict], list[dict]]:
    """Separa os exemplos que passam nas regras de `query_data` dos
    recusados, que voltam com pergunta e motivo."""
    schema = build_query_schema(
        datasource, entities, dialect=source_dialect(datasource)
    )
    accepted, rejected = [], []
    for eg in datasource.examples or []:
        try:
            validate_query(eg.get('sql', ''), schema)
        except QueryValidationError as exc:
            rejected.append({
                'question': eg.get('question', ''),
                'reason': exc.message,
            })
        else:
            accepted.append(eg)
    return accepted, rejected


def _same_text(a: str | None, b: str | None) -> bool:
    def clean(text):
        return (text or '').strip().rstrip('.').casefold()

    return clean(a) == clean(b)


def _visible_columns(entity: CatalogEntity) -> set[str]:
    return {c.name for c in entity.columns if c.visible and c.present}


def _column_links(
    relationships: list[CatalogRelationship],
    by_id: dict,
) -> dict:
    """Relacionamentos na linha da primeira coluna de origem, por entidade.

    Entram só os ligados e presentes, entre entidades incluídas e com todas
    as colunas das duas pontas visíveis.
    """
    links: dict = {}
    for r in sorted(
        relationships, key=lambda r: (r.from_columns, r.to_columns)
    ):
        source = by_id.get(r.from_entity_id)
        target = by_id.get(r.to_entity_id)
        if not (r.enabled and r.present and source and target):
            continue
        if not set(r.from_columns) <= _visible_columns(source):
            continue
        if not set(r.to_columns) <= _visible_columns(target):
            continue
        text = f'→ {target.qualified_name}.{", ".join(r.to_columns)}'
        if len(r.from_columns) > 1:
            text += f' (com {", ".join(r.from_columns)})'
        first = r.from_columns[0]
        # A descrição só entra quando acrescenta algo à da própria coluna.
        column_text = next(
            (c.description for c in source.columns if c.name == first), None
        )
        if r.description and not _same_text(r.description, column_text):
            text += f' ({r.description})'
        own = links.setdefault(source.id, {})
        own[first] = f'{own[first]}; {text}' if first in own else text
    return links


def render_context(
    datasource: CatalogDataSource,
    entities: list[CatalogEntity],
    relationships: list[CatalogRelationship],
    concept_labels: dict[str, str] | None = None,
    max_values: int | None = None,
) -> str:
    if not datasource.enabled:
        return ''
    if max_values is None:
        max_values = Settings().CATALOG_CONTEXT_VALUES_MAX

    included = sorted(
        (e for e in entities if e.visible and e.present),
        key=lambda e: (e.schema_name, e.name),
    )
    by_id = {entity.id: entity for entity in included}
    lines = [f'# Fonte de dados: {datasource.name} (`{datasource.id}`)']
    if datasource.description:
        lines += ['', datasource.description]
    if datasource.instructions:
        lines += ['', '## Instruções', datasource.instructions.strip()]

    lines += ['', '## Entidades']
    if not included:
        lines.append('Nenhuma entidade disponível.')
    links = _column_links(relationships, by_id)
    for entity in included:
        label = (concept_labels or {}).get(entity.concept_id)
        lines += [
            '',
            *_entity_section(entity, max_values, label, links.get(entity.id)),
        ]

    accepted, _ = check_examples(datasource, entities)
    lines.extend(_examples_section(accepted))

    return '\n'.join(lines) + '\n'


CONCEPTS_INTRO = (
    'Estes assuntos aparecem em mais de uma fonte, com significados '
    'diferentes. Siga a política de cada um para escolher a fonte e diga ao '
    'usuário de qual fonte vem cada número.'
)


def render_concepts(
    concepts: list[CatalogConcept],
    entities: list[CatalogEntity],
    datasources: list[CatalogDataSource],
) -> str:
    """Seção "Conceitos em várias fontes"; vazia se nenhum conceito tem
    entidades visíveis e presentes em duas ou mais das fontes dadas."""
    names = {ds.id: ds.name for ds in datasources}
    sections = []
    for concept in sorted(concepts, key=lambda c: c.label):
        own = sorted(
            (
                e
                for e in entities
                if e.concept_id == concept.id
                and e.visible
                and e.present
                and e.datasource_id in names
            ),
            key=lambda e: (e.datasource_id, e.schema_name, e.name),
        )
        sources = sorted({e.datasource_id for e in own})
        if len(sources) < 2:  # noqa: PLR2004
            continue
        lines = ['', f'## {concept.label} (`{concept.id}`)']
        if concept.description:
            lines.append(concept.description.strip())
        if concept.synonyms:
            lines.append(f'Sinônimos: {", ".join(concept.synonyms)}.')
        lines.append('Entidades:')
        for source in sources:
            refs = ', '.join(
                f'`{e.qualified_name}`' + (f' ({e.label})' if e.label else '')
                for e in own
                if e.datasource_id == source
            )
            lines.append(f'- {names[source]} (`{source}`): {refs}')
        if concept.instructions:
            lines += ['Política:', concept.instructions.strip()]
        sections += lines
    if not sections:
        return ''
    return (
        '\n'.join([
            '# Conceitos em várias fontes',
            '',
            CONCEPTS_INTRO,
            *sections,
        ])
        + '\n'
    )


async def load_concept_labels(session: AsyncSession) -> dict[str, str]:
    concepts = await session.scalars(select(CatalogConcept))
    return {c.id: c.label for c in concepts}


async def load_concepts_context(
    session: AsyncSession, datasources: list[CatalogDataSource]
) -> str:
    """Seção de conceitos para as fontes incluídas no prompt."""
    concepts = list(await session.scalars(select(CatalogConcept)))
    if not concepts:
        return ''
    entities = list(
        await session.scalars(
            select(CatalogEntity).where(
                CatalogEntity.concept_id.is_not(None),
                CatalogEntity.datasource_id.in_([d.id for d in datasources]),
            )
        )
    )
    return render_concepts(concepts, entities, datasources)
