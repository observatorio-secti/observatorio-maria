"""Texto que o modelo recebe sobre uma fonte de dados.

É a única porta entre o catálogo e o prompt: o que não sai daqui o modelo
não enxerga. Itens ocultos ou ausentes nunca entram.
"""

from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
    CatalogRelationship,
    ColumnAccess,
    EntityKind,
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
    """Valores que o modelo deve conhecer: os do enum da origem, na ordem
    dela, com as descrições editoriais (obsoletos ficam de fora); sem enum,
    os valores editoriais."""
    if column.enum_values is None:
        return column.values
    described = {str(item['value']): item for item in column.values}
    return [described.get(v, {'value': v}) for v in column.enum_values]


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
        notes.append(f'Valores: {"; ".join(_value(v) for v in values)}')
    for note in notes:
        line = f'{line.rstrip(".")}. {note}'
    return line


def _entity_section(entity: CatalogEntity) -> list[str]:
    kind = KIND_LABELS.get(entity.kind, entity.kind or 'entidade')
    title = f'### `{entity.qualified_name}` ({kind})'
    if entity.label:
        title += f': {entity.label}'
    lines = [title]
    if entity.description:
        lines.append(entity.description)
    if entity.synonyms:
        lines.append(f'Sinônimos: {", ".join(entity.synonyms)}.')
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


def render_context(
    datasource: CatalogDataSource,
    entities: list[CatalogEntity],
    relationships: list[CatalogRelationship],
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
        lines += ['', *_entity_section(entity)]

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

    lines.extend(_examples_section(datasource.examples))

    return '\n'.join(lines) + '\n'
