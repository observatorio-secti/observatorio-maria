"""Ranking de pesquisadores por relevância sobre o índice de busca do Simcc.

Lê as views materializadas mantidas pelo simcc-back (`mv_search_documents`,
`mv_researcher_search` e `mv_refresh_metadata`) com SQL fixo e
parametrizado, numa transação somente leitura. A fórmula é a mesma da busca
V2 do Simcc (`researcher_repo._relevance_score`): perfil × 1,5 + melhor
produção + ln(produções que casam + 1).

As views são do Simcc: a Maria nunca as cria, altera ou atualiza.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unicodedata import normalize

from sqlalchemy import (
    Float,
    Integer,
    Text,
    and_,
    bindparam,
    cast,
    column,
    func,
    literal,
    literal_column,
    null,
    or_,
    select,
    table,
    text,
    union_all,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import Select

from observatorio_maria.catalog.introspection import SourceUnavailableError
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.execution import QueryTimeoutError, _clean_error

DEFAULT_LIMIT = 10
MAX_LIMIT = 20
MAX_EVIDENCE_ITEMS = 3
# Com sigla ou nome exato, as unidades que citam a instituição no nome
# também contam; sem ele, um texto que casa com muitas é ambíguo.
MAX_INSTITUTIONS = 200
MAX_LOOSE_INSTITUTIONS = 20
PROFILE_WEIGHT = 1.5
PROFILE_TYPE = 'PROFILE'

DOCUMENTS_VIEW = 'mv_search_documents'
RESEARCHERS_VIEW = 'mv_researcher_search'
REFRESH_TABLE = 'mv_refresh_metadata'

SOURCE_TYPES = {
    'ARTICLE': 'artigo',
    'BOOK': 'livro',
    'BOOK_CHAPTER': 'capítulo de livro',
    'PATENT': 'patente',
    'SOFTWARE': 'software',
    'PARTICIPATION_EVENT': 'participação em evento',
    'AREA_SPECIALTY': 'área de atuação',
}

RANKING_CRITERION = (
    'Ordem por relevância do termo no resumo do currículo e nas produções, '
    'com o mesmo critério da busca do Simcc.'
)
RANKING_FIELDS = [
    'Títulos de artigos, livros, capítulos, patentes, softwares e eventos',
    'Palavras-chave e resumos dos artigos (OpenAlex)',
    'Áreas de atuação',
    'Nome e resumo do currículo',
]

TS_CONFIG = literal_column("'pt_unaccent'::regconfig")


class RankingUnavailableError(QueryValidationError):
    """O índice de busca do Simcc não existe ou está vazio."""

    def __init__(self) -> None:
        super().__init__(
            'A busca de pesquisadores por relevância está indisponível: o '
            'índice de busca do Simcc ainda não foi gerado. Diga ao usuário '
            'que não é possível ordenar pesquisadores por relevância agora.'
        )


@dataclass(frozen=True)
class RankingFilters:
    """Termo e filtros da busca, já validados."""

    term: str
    year_start: int | None = None
    year_end: int | None = None
    source_types: tuple[str, ...] = ()
    institution: str | None = None

    @property
    def profile_counts(self) -> bool:
        """O resumo do currículo só conta sem restrição de tipo de obra."""
        return not self.source_types


@dataclass(frozen=True)
class RankedResearcher:
    researcher_id: str
    name: str
    matches: int


@dataclass
class Evidence:
    total: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RankingOutcome:
    researchers: list[RankedResearcher]
    total: int
    evidence: dict[str, Evidence]
    data_as_of: datetime | None


def _views(schema: str | None):
    documents = table(
        DOCUMENTS_VIEW,
        column('researcher_id', PG_UUID(as_uuid=False)),
        column('source_id', PG_UUID(as_uuid=False)),
        column('source_type', Text),
        column('title', Text),
        column('year_', Integer),
        column('search_vector'),
        schema=schema,
    )
    researchers = table(
        RESEARCHERS_VIEW,
        column('researcher_id', PG_UUID(as_uuid=False)),
        column('name', Text),
        column('profile_vector'),
        column('institution_ids'),
        schema=schema,
    )
    return documents, researchers


def _tsquery():
    return func.websearch_to_tsquery(TS_CONFIG, bindparam('term', type_=Text))


def _document_conditions(documents, filters: RankingFilters, tsq) -> list:
    conds = [documents.c.search_vector.op('@@')(tsq)]
    if filters.year_start is not None:
        conds.append(
            documents.c.year_ >= bindparam('year_start', type_=Integer)
        )
    if filters.year_end is not None:
        conds.append(documents.c.year_ <= bindparam('year_end', type_=Integer))
    if filters.source_types:
        conds.append(
            documents.c.source_type.in_(
                bindparam('source_types', expanding=True)
            )
        )
    return conds


def ranking_statement(
    filters: RankingFilters,
    *,
    schema: str | None = 'public',
    with_institutions: bool = False,
) -> Select:
    """Pesquisadores que casam com o termo, do mais ao menos relevante.

    A agregação das produções roda uma vez e é juntada ao perfil: um
    subselect por pesquisador repetiria a varredura do índice GIN."""
    documents, researchers = _views(schema)
    tsq = _tsquery()
    docs = (
        select(
            documents.c.researcher_id,
            func.count().label('n'),
            func.max(func.ts_rank(documents.c.search_vector, tsq)).label(
                'best'
            ),
        )
        .where(*_document_conditions(documents, filters, tsq))
        .group_by(documents.c.researcher_id)
        .cte('docs')
    )
    matches = func.coalesce(docs.c.n, 0)
    doc_score = func.coalesce(docs.c.best, 0.0) + func.ln(
        cast(matches, Float) + 1.0
    )

    if filters.profile_counts:
        prof = (
            select(
                researchers.c.researcher_id,
                func.ts_rank(researchers.c.profile_vector, tsq).label('rk'),
            )
            .where(researchers.c.profile_vector.op('@@')(tsq))
            .cte('prof')
        )
        researcher_id = func.coalesce(
            docs.c.researcher_id, prof.c.researcher_id
        )
        base = docs.join(
            prof, docs.c.researcher_id == prof.c.researcher_id, full=True
        )
        score = func.coalesce(prof.c.rk, 0.0) * PROFILE_WEIGHT + doc_score
    else:
        researcher_id = docs.c.researcher_id
        base = docs
        score = doc_score

    r = researchers.alias('r')
    stmt = select(
        cast(r.c.researcher_id, Text).label('researcher_id'),
        r.c.name,
        matches.label('matches'),
        score.label('score'),
        func.count().over().label('total'),
    ).select_from(base.join(r, r.c.researcher_id == researcher_id))
    if with_institutions:
        stmt = stmt.where(
            r.c.institution_ids.op('&&')(
                cast(
                    bindparam('institution_ids', type_=ARRAY(Text)),
                    ARRAY(PG_UUID),
                )
            )
        )
    return stmt.order_by(
        score.desc(), r.c.name.asc(), r.c.researcher_id.asc()
    ).limit(bindparam('limit', type_=Integer))


def _page_condition(id_column):
    return id_column.in_(bindparam('page_ids', expanding=True))


def evidence_statement(
    filters: RankingFilters, *, schema: str | None = 'public'
) -> Select:
    """Até 3 evidências por pesquisador da página, pela maior relevância."""
    documents, researchers = _views(schema)
    tsq = _tsquery()
    candidates = select(
        cast(documents.c.researcher_id, Text).label('researcher_id'),
        documents.c.source_type,
        documents.c.title,
        documents.c.year_,
        cast(documents.c.source_id, Text).label('source_key'),
        func.ts_rank(documents.c.search_vector, tsq).label('rank'),
    ).where(
        _page_condition(documents.c.researcher_id),
        *_document_conditions(documents, filters, tsq),
    )
    if filters.profile_counts:
        candidates = union_all(
            candidates,
            select(
                cast(researchers.c.researcher_id, Text).label('researcher_id'),
                literal(PROFILE_TYPE, Text).label('source_type'),
                null().cast(Text).label('title'),
                null().cast(Integer).label('year_'),
                cast(researchers.c.researcher_id, Text).label('source_key'),
                func.ts_rank(researchers.c.profile_vector, tsq).label('rank'),
            ).where(
                _page_condition(researchers.c.researcher_id),
                researchers.c.profile_vector.op('@@')(tsq),
            ),
        )
    candidates = candidates.subquery('candidates')
    ranked = select(
        candidates,
        func.row_number()
        .over(
            partition_by=candidates.c.researcher_id,
            order_by=(candidates.c.rank.desc(), candidates.c.source_key),
        )
        .label('position'),
    ).subquery('ranked')
    return (
        select(
            ranked.c.researcher_id,
            ranked.c.source_type,
            ranked.c.title,
            ranked.c.year_,
        )
        .where(ranked.c.position <= MAX_EVIDENCE_ITEMS)
        .order_by(ranked.c.researcher_id, ranked.c.position)
    )


def evidence_counts_statement(
    filters: RankingFilters, *, schema: str | None = 'public'
) -> Select:
    """Produções que casam com o termo, por pesquisador da página e tipo."""
    documents, _ = _views(schema)
    tsq = _tsquery()
    return (
        select(
            cast(documents.c.researcher_id, Text).label('researcher_id'),
            documents.c.source_type,
            func.count().label('n'),
        )
        .where(
            _page_condition(documents.c.researcher_id),
            *_document_conditions(documents, filters, tsq),
        )
        .group_by(documents.c.researcher_id, documents.c.source_type)
    )


def normalize_institution(value: str) -> str:
    """Sigla ou nome sem acento, sem caixa e sem curingas do LIKE."""
    plain = normalize('NFKD', value).encode('ascii', 'ignore').decode()
    plain = re.sub(r'\s+', ' ', plain).strip().lower()
    return plain.replace('\\', '').replace('%', '').replace('_', ' ')


def institution_statement(*, schema: str | None = 'public') -> Select:
    """Instituições com sigla ou nome igual ao texto (`exact`) e unidades
    cujo nome contém o texto, como "Escola de Enfermagem - UFBA"."""
    institution = table(
        'institution',
        column('id', PG_UUID(as_uuid=False)),
        column('name', Text),
        column('acronym', Text),
        schema=schema,
    )

    def plain(col):
        return func.lower(func.public.f_unaccent(col))

    key = bindparam('institution', type_=Text)
    exact = or_(
        plain(institution.c.acronym) == key, plain(institution.c.name) == key
    )
    return (
        select(cast(institution.c.id, Text).label('id'), exact.label('exact'))
        .where(
            or_(
                exact,
                plain(institution.c.name).like(
                    literal('%', Text) + key + literal('%', Text)
                ),
            )
        )
        .order_by(exact.desc(), institution.c.id)
        .limit(MAX_INSTITUTIONS + 1)
    )


def availability_statement(schema: str | None = 'public') -> Select:
    """Existência das views do índice e da tabela de refresh."""
    prefix = f'{schema}.' if schema else ''

    def exists(name: str):
        return func.to_regclass(literal(f'{prefix}{name}', Text)).isnot(None)

    return select(
        and_(exists(DOCUMENTS_VIEW), exists(RESEARCHERS_VIEW)).label('views'),
        exists(REFRESH_TABLE).label('refresh'),
    )


def has_documents_statement(schema: str | None = 'public') -> Select:
    documents, _ = _views(schema)
    return select(literal(1)).select_from(documents).limit(1)


def data_as_of_statement(schema: str | None = 'public') -> Select:
    """Data do refresh mais antigo entre as duas views do ranking."""
    refresh = table(
        REFRESH_TABLE,
        column('view_name', Text),
        column('refreshed_at'),
        schema=schema,
    )
    return select(func.min(refresh.c.refreshed_at)).where(
        refresh.c.view_name.in_([DOCUMENTS_VIEW, RESEARCHERS_VIEW])
    )


def parse_timestamp(value: Any) -> datetime | None:
    """`refreshed_at` como datetime; texto vem de origens sem tipo de data."""
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


async def read_data_as_of(conn: Any, schema: str | None) -> datetime | None:
    """Data dos dados; nula se a tabela de refresh não tiver as views."""
    value = (await conn.execute(data_as_of_statement(schema))).scalar()
    return parse_timestamp(value)


def _params(filters: RankingFilters) -> dict[str, Any]:
    params: dict[str, Any] = {'term': filters.term}
    if filters.year_start is not None:
        params['year_start'] = filters.year_start
    if filters.year_end is not None:
        params['year_end'] = filters.year_end
    if filters.source_types:
        params['source_types'] = list(filters.source_types)
    return params


async def _check_available(conn: Any, schema: str | None) -> bool:
    """Levanta erro sem as views ou sem linhas; diz se há tabela de refresh."""
    row = (await conn.execute(availability_statement(schema))).one()
    if not row.views:
        raise RankingUnavailableError
    if (await conn.execute(has_documents_statement(schema))).first() is None:
        raise RankingUnavailableError
    return bool(row.refresh)


async def _resolve_institutions(
    conn: Any, schema: str | None, institution: str
) -> list[str]:
    key = normalize_institution(institution)
    rows = []
    if key:
        result = await conn.execute(
            institution_statement(schema=schema), {'institution': key}
        )
        rows = result.all()
    if not rows:
        raise QueryValidationError(
            f"Nenhuma instituição do Simcc corresponde a '{institution}'. "
            'Confira a sigla ou o nome, ou busque sem a instituição.'
        )
    has_exact = any(row.exact for row in rows)
    limit = MAX_INSTITUTIONS if has_exact else MAX_LOOSE_INSTITUTIONS
    if len(rows) > limit:
        raise QueryValidationError(
            f"'{institution}' corresponde a instituições demais no Simcc. "
            'Informe a sigla ou o nome completo da instituição.'
        )
    return [row.id for row in rows]


async def _collect_evidence(
    conn: Any,
    schema: str | None,
    filters: RankingFilters,
    params: dict[str, Any],
    page_ids: list[str],
) -> dict[str, Evidence]:
    evidence = {rid: Evidence() for rid in page_ids}
    page_params = {**params, 'page_ids': page_ids}
    counts = await conn.execute(
        evidence_counts_statement(filters, schema=schema), page_params
    )
    for row in counts:
        item = evidence[row.researcher_id]
        item.by_type[row.source_type] = row.n
        item.total += row.n
    items = await conn.execute(
        evidence_statement(filters, schema=schema), page_params
    )
    for row in items:
        evidence[row.researcher_id].items.append({
            'type': row.source_type,
            'title': row.title,
            'year': row.year_,
        })
    return evidence


async def _rank_on_connection(
    conn: Any,
    schema: str | None,
    filters: RankingFilters,
    limit: int,
) -> RankingOutcome:
    has_refresh = await _check_available(conn, schema)
    params = _params(filters)
    institution_ids = None
    if filters.institution:
        institution_ids = await _resolve_institutions(
            conn, schema, filters.institution
        )
    stmt = ranking_statement(
        filters, schema=schema, with_institutions=bool(institution_ids)
    )
    rank_params = {**params, 'limit': limit}
    if institution_ids:
        rank_params['institution_ids'] = institution_ids
    rows = (await conn.execute(stmt, rank_params)).all()
    researchers = [
        RankedResearcher(
            researcher_id=row.researcher_id,
            name=row.name,
            matches=int(row.matches),
        )
        for row in rows
    ]
    total = int(rows[0].total) if rows else 0
    evidence = (
        await _collect_evidence(
            conn,
            schema,
            filters,
            params,
            [r.researcher_id for r in researchers],
        )
        if researchers
        else {}
    )
    data_as_of = await read_data_as_of(conn, schema) if has_refresh else None
    return RankingOutcome(researchers, total, evidence, data_as_of)


async def rank_researchers(
    engine: AsyncEngine,
    schema: str | None,
    filters: RankingFilters,
    *,
    limit: int = DEFAULT_LIMIT,
    timeout_seconds: float = 15.0,
) -> RankingOutcome:
    """Executa o ranking numa transação somente leitura com tempo limite."""
    timeout_ms = int(timeout_seconds * 1000)
    try:
        async with asyncio.timeout(timeout_seconds):
            async with engine.connect() as conn, conn.begin():
                await conn.execute(text('SET TRANSACTION READ ONLY'))
                await conn.execute(
                    text(f'SET LOCAL statement_timeout = {timeout_ms}')
                )
                return await _rank_on_connection(conn, schema, filters, limit)
    except TimeoutError as exc:
        raise QueryTimeoutError from exc
    except QueryValidationError:
        raise
    except (OperationalError, DBAPIError, SQLAlchemyError) as exc:
        message = _clean_error(exc)
        low = message.lower()
        if 'canceling statement' in low or 'statement timeout' in low:
            raise QueryTimeoutError from exc
        if (
            'connection' in low
            or 'refused' in low
            or 'could not connect' in low
            or 'server closed' in low
        ):
            raise SourceUnavailableError(
                'Não foi possível conectar à fonte de dados'
            ) from exc
        raise QueryValidationError(
            f'Erro ao ordenar pesquisadores: {message}'
        ) from exc
