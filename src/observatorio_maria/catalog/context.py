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
)
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.validator import (
    build_query_schema,
    source_dialect,
    validate_query,
)

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


def _column_line(column: CatalogColumn) -> str:
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
    values = _known_values(column)
    if values:
        label = 'Valores'
        if column.enum_values is None and column.observed_values is not None:
            label = 'Valores existentes na origem (use exatamente como estão)'
        notes.append(f'{label}: {"; ".join(_value(v) for v in values)}')
    for note in notes:
        line = f'{line.rstrip(".")}. {note}'
    return line


def _entity_section(
    entity: CatalogEntity, concept_label: str | None = None
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
    lines.extend(_column_line(c) for c in columns)
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


def render_context(
    datasource: CatalogDataSource,
    entities: list[CatalogEntity],
    relationships: list[CatalogRelationship],
    concept_labels: dict[str, str] | None = None,
) -> str:
    if not datasource.enabled:
        return ''

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
    for entity in included:
        label = (concept_labels or {}).get(entity.concept_id)
        lines += ['', *_entity_section(entity, label)]

    links = []
    for r in relationships:
        source = by_id.get(r.from_entity_id)
        target = by_id.get(r.to_entity_id)
        if not (r.enabled and r.present and source and target):
            continue
        line = (
            f'- `{source.qualified_name}.{",".join(r.from_columns)}` -> '
            f'`{target.qualified_name}.{",".join(r.to_columns)}`'
        )
        if r.description:
            line += f': {r.description}'
        links.append(line)
    if links:
        lines += ['', '## Relacionamentos', *sorted(links)]

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
