"""Hidratação somente leitura de cards estruturados."""

import re
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from observatorio_maria.query.sanitization import sanitize_untrusted_text
from observatorio_maria.schemas import (
    ProductionAuthor,
    ProductionCard,
    ProductionDetails,
    ResearcherAffiliation,
    ResearcherCard,
    ResearcherMetrics,
)

MAX_CARDS = 20

RESEARCHER_ID_COLUMNS = ('id', 'researcher_id', 'lattes_id', 'lattes')
PRODUCTION_ID_COLUMNS = (
    'id',
    'canonical_id',
    'production_id',
    'bibliographic_production_id',
)

CNPQ_PHOTO_URL_TEMPLATE = (
    'http://servicosweb.cnpq.br/wsprest/sp/prest/padrao/obterFoto/{lattes_id}'
)


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _clean_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip()
        if re.match(r'^\d{4}$', s):
            return int(s)
        m = re.match(r'^(\d{4})', s)
        if m:
            return int(m.group(1))
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _parse_authors(
    authors_text: str | None, default_author: str | None = None
) -> list[ProductionAuthor]:
    authors: list[ProductionAuthor] = []
    if authors_text and authors_text.strip():
        parts = [
            p.strip()
            for p in re.split(r'[;\n]+', authors_text)
            if p and p.strip()
        ]
        if not parts:
            parts = [
                p.strip() for p in authors_text.split(',') if p and p.strip()
            ]
        for idx, part in enumerate(parts[:10], start=1):
            sanitized = sanitize_untrusted_text(part)
            if sanitized:
                authors.append(ProductionAuthor(name=sanitized, order=idx))
    if not authors and default_author:
        sanitized = sanitize_untrusted_text(default_author)
        if sanitized:
            authors.append(ProductionAuthor(name=sanitized, order=1))
    return authors


async def _fetch_researcher_records(
    conn: Any, prefix: str, ids: list[str]
) -> list[dict[str, Any]]:
    # Tenta com join completo, recuando defensivamente para esquemas menores
    queries = [
        f'''
        SELECT
            CAST(r.id AS TEXT) AS id,
            r.name,
            CAST(r.lattes_id AS TEXT) AS lattes_id,
            r.abstract,
            r.orcid,
            r.graduation,
            c.name AS city_name,
            s.abbreviation AS state_abbrev
        FROM {prefix}researcher r
        LEFT JOIN {prefix}city c ON c.id = r.city_id
        LEFT JOIN {prefix}state s ON s.id = c.state_id
        WHERE CAST(r.id AS TEXT) IN :ids OR CAST(r.lattes_id AS TEXT) IN :ids
        ''',
        f'''
        SELECT
            CAST(r.id AS TEXT) AS id,
            r.name,
            CAST(r.lattes_id AS TEXT) AS lattes_id,
            r.abstract,
            r.orcid
        FROM {prefix}researcher r
        WHERE CAST(r.id AS TEXT) IN :ids OR CAST(r.lattes_id AS TEXT) IN :ids
        ''',
        f'''
        SELECT
            CAST(r.id AS TEXT) AS id,
            r.name,
            CAST(r.lattes_id AS TEXT) AS lattes_id
        FROM {prefix}researcher r
        WHERE CAST(r.id AS TEXT) IN :ids OR CAST(r.lattes_id AS TEXT) IN :ids
        ''',
    ]
    for q_sql in queries:
        try:
            stmt = text(q_sql).bindparams(bindparam('ids', expanding=True))
            cursor = await conn.execute(stmt, {'ids': ids})
            return [dict(row) for row in cursor.mappings().all()]
        except (OperationalError, DBAPIError, SQLAlchemyError):
            continue
    return []


async def _fetch_affiliations(
    conn: Any, prefix: str, rids: list[str], target: dict[str, dict[str, Any]]
) -> None:
    try:
        sql = text(
            f'''
            SELECT
                CAST(ri.researcher_id AS TEXT) AS researcher_id,
                ri.identity_territory,
                CAST(i.id AS TEXT) AS institution_id,
                i.name AS institution_name,
                i.acronym AS institution_acronym,
                c.name AS city_name
            FROM {prefix}researcher_institution ri
            LEFT JOIN {prefix}institution i ON i.id = ri.institution_id
            LEFT JOIN {prefix}city c ON c.id = i.city_id
            WHERE CAST(ri.researcher_id AS TEXT) IN :rids
            '''
        ).bindparams(bindparam('rids', expanding=True))
        cursor = await conn.execute(sql, {'rids': rids})
        for row in cursor.mappings().all():
            rid = str(row['researcher_id'])
            if rid not in target:
                continue
            terr = _clean_str(row.get('identity_territory'))
            if terr and not target[rid]['territory']:
                target[rid]['territory'] = sanitize_untrusted_text(terr)
            name = _clean_str(row.get('institution_name'))
            acronym = _clean_str(row.get('institution_acronym'))
            if name or acronym:
                target[rid]['affiliations'].append(
                    ResearcherAffiliation(
                        institution_id=_clean_str(row.get('institution_id')),
                        institution_name=(
                            sanitize_untrusted_text(name) if name else None
                        ),
                        institution_acronym=(
                            sanitize_untrusted_text(acronym)
                            if acronym
                            else None
                        ),
                        city_name=(
                            sanitize_untrusted_text(
                                _clean_str(row.get('city_name'))
                            )
                            if row.get('city_name')
                            else None
                        ),
                    )
                )
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass


async def _fetch_production_metrics(
    conn: Any, prefix: str, rids: list[str], target: dict[str, dict[str, Any]]
) -> None:
    try:
        sql = text(
            f'''
            SELECT
                CAST(rp.researcher_id AS TEXT) AS researcher_id,
                rp.articles,
                rp.book_chapters,
                rp.book,
                rp.patent,
                rp.software,
                rp.brand
            FROM {prefix}researcher_production rp
            WHERE CAST(rp.researcher_id AS TEXT) IN :rids
            '''
        ).bindparams(bindparam('rids', expanding=True))
        cursor = await conn.execute(sql, {'rids': rids})
        for row in cursor.mappings().all():
            rid = str(row['researcher_id'])
            if rid not in target:
                continue
            target[rid]['metrics'].update({
                'articles': _clean_int(row.get('articles')) or 0,
                'book_chapters': _clean_int(row.get('book_chapters')) or 0,
                'books': _clean_int(row.get('book')) or 0,
                'patents': _clean_int(row.get('patent')) or 0,
                'software': _clean_int(row.get('software')) or 0,
                'brand': _clean_int(row.get('brand')) or 0,
            })
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass


async def _fetch_openalex_metrics(
    conn: Any, prefix: str, rids: list[str], target: dict[str, dict[str, Any]]
) -> None:
    try:
        sql = text(
            f'''
            SELECT
                CAST(oa.researcher_id AS TEXT) AS researcher_id,
                oa.h_index,
                oa.i10_index,
                oa.cited_by_count,
                oa.openalex
            FROM {prefix}openalex_researcher oa
            WHERE CAST(oa.researcher_id AS TEXT) IN :rids
            '''
        ).bindparams(bindparam('rids', expanding=True))
        cursor = await conn.execute(sql, {'rids': rids})
        for row in cursor.mappings().all():
            rid = str(row['researcher_id'])
            if rid not in target:
                continue
            target[rid]['metrics'].update({
                'h_index': _clean_int(row.get('h_index')),
                'i10_index': _clean_int(row.get('i10_index')),
                'citations': _clean_int(row.get('cited_by_count')),
            })
            oa_id = _clean_str(row.get('openalex'))
            if oa_id:
                target[rid]['openalex_id'] = sanitize_untrusted_text(oa_id)
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass


def _build_researcher_card(data: dict[str, Any]) -> ResearcherCard:
    m = data['metrics']
    total_p = (
        m.get('articles', 0)
        + m.get('book_chapters', 0)
        + m.get('books', 0)
        + m.get('patents', 0)
        + m.get('software', 0)
        + m.get('brand', 0)
    )
    metrics_obj = ResearcherMetrics(
        articles=m.get('articles', 0),
        book_chapters=m.get('book_chapters', 0),
        books=m.get('books', 0),
        patents=m.get('patents', 0),
        software=m.get('software', 0),
        brand=m.get('brand', 0),
        total_productions=total_p,
        h_index=m.get('h_index'),
        i10_index=m.get('i10_index'),
        citations=m.get('citations'),
    )
    l_id = data.get('lattes_id')
    photo_url = (
        CNPQ_PHOTO_URL_TEMPLATE.format(lattes_id=l_id) if l_id else None
    )
    return ResearcherCard(
        id=data['id'],
        name=data['name'],
        lattes_id=l_id,
        abstract=data.get('abstract'),
        photo_url=photo_url,
        city=data.get('city'),
        state=data.get('state'),
        territory=data.get('territory'),
        graduation=data.get('graduation'),
        openalex_id=data.get('openalex_id'),
        orcid=data.get('orcid'),
        affiliations=data.get('affiliations') or [],
        metrics=metrics_obj,
    )


async def hydrate_researchers(
    engine: AsyncEngine,
    schema: str,
    identifiers: list[str],
) -> list[ResearcherCard]:
    """Hidrata até MAX_CARDS pesquisadores a partir de seus IDs."""
    clean_ids: list[str] = []
    for item in identifiers:
        s = _clean_str(item)
        if s and s not in clean_ids:
            clean_ids.append(s)
        if len(clean_ids) >= MAX_CARDS:
            break

    if not clean_ids:
        return []

    backend = engine.url.get_backend_name()
    prefix = f'"{schema}".' if backend == 'postgresql' and schema else ''

    target: dict[str, dict[str, Any]] = {}
    lattes_map: dict[str, str] = {}

    async with engine.connect() as conn:
        rows = await _fetch_researcher_records(conn, prefix, clean_ids)
        for row in rows:
            rid = str(row['id'])
            lid = _clean_str(row.get('lattes_id'))
            target[rid] = {
                'id': rid,
                'name': sanitize_untrusted_text(str(row['name'])),
                'lattes_id': sanitize_untrusted_text(lid) if lid else None,
                'abstract': (
                    sanitize_untrusted_text(str(row['abstract']))
                    if row.get('abstract')
                    else None
                ),
                'orcid': (
                    sanitize_untrusted_text(str(row['orcid']))
                    if row.get('orcid')
                    else None
                ),
                'graduation': (
                    sanitize_untrusted_text(str(row['graduation']))
                    if row.get('graduation')
                    else None
                ),
                'city': (
                    sanitize_untrusted_text(str(row['city_name']))
                    if row.get('city_name')
                    else None
                ),
                'state': (
                    sanitize_untrusted_text(str(row['state_abbrev']))
                    if row.get('state_abbrev')
                    else None
                ),
                'affiliations': [],
                'territory': None,
                'metrics': {},
                'openalex_id': None,
            }
            if lid:
                lattes_map[lid] = rid

        rids = list(target.keys())
        if not rids:
            return []

        await _fetch_affiliations(conn, prefix, rids, target)
        await _fetch_production_metrics(conn, prefix, rids, target)
        await _fetch_openalex_metrics(conn, prefix, rids, target)

    ordered: list[ResearcherCard] = []
    seen: set[str] = set()
    for ident in clean_ids:
        rid = ident if ident in target else lattes_map.get(ident)
        if not rid or rid in seen:
            continue
        seen.add(rid)
        ordered.append(_build_researcher_card(target[rid]))

    return ordered


async def _enrich_bibliographic_details(
    conn: Any,
    prefix: str,
    bp_ids: list[str],
    prods_map: dict[str, ProductionCard],
) -> None:
    # Artigo
    try:
        sql_art = text(
            f'''
            SELECT
                CAST(a.bibliographic_production_id AS TEXT) AS id,
                a.periodical_magazine_name,
                a.issn,
                a.qualis
            FROM {prefix}bibliographic_production_article a
            WHERE CAST(a.bibliographic_production_id AS TEXT) IN :ids
            '''
        ).bindparams(bindparam('ids', expanding=True))
        cursor_art = await conn.execute(sql_art, {'ids': bp_ids})
        for r in cursor_art.mappings().all():
            pid = str(r['id'])
            if pid in prods_map:
                prods_map[pid].details.magazine = _clean_str(
                    r.get('periodical_magazine_name')
                )
                prods_map[pid].details.issn = _clean_str(r.get('issn'))
                prods_map[pid].details.qualis = _clean_str(r.get('qualis'))
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass

    # Livro e capítulo
    try:
        sql_bk = text(
            f'''
            SELECT
                CAST(b.bibliographic_production_id AS TEXT) AS id,
                b.isbn
            FROM {prefix}bibliographic_production_book b
            WHERE CAST(b.bibliographic_production_id AS TEXT) IN :ids
            '''
        ).bindparams(bindparam('ids', expanding=True))
        cursor_bk = await conn.execute(sql_bk, {'ids': bp_ids})
        for r in cursor_bk.mappings().all():
            pid = str(r['id'])
            if pid in prods_map:
                prods_map[pid].details.isbn = _clean_str(r.get('isbn'))
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass

    try:
        sql_ch = text(
            f'''
            SELECT
                CAST(bc.bibliographic_production_id AS TEXT) AS id,
                bc.isbn
            FROM {prefix}bibliographic_production_book_chapter bc
            WHERE CAST(bc.bibliographic_production_id AS TEXT) IN :ids
            '''
        ).bindparams(bindparam('ids', expanding=True))
        cursor_ch = await conn.execute(sql_ch, {'ids': bp_ids})
        for r in cursor_ch.mappings().all():
            pid = str(r['id'])
            if pid in prods_map and not prods_map[pid].details.isbn:
                prods_map[pid].details.isbn = _clean_str(r.get('isbn'))
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass


async def _fetch_bibliographic(
    conn: Any,
    prefix: str,
    ids: list[str],
    prods_map: dict[str, ProductionCard],
) -> None:
    queries = [
        f'''
        SELECT
            CAST(bp.id AS TEXT) AS id,
            bp.title,
            bp.type,
            bp.year_,
            bp.doi,
            bp.nature,
            bp.authors,
            r.name AS researcher_name
        FROM {prefix}bibliographic_production bp
        LEFT JOIN {prefix}researcher r ON r.id = bp.researcher_id
        WHERE CAST(bp.id AS TEXT) IN :ids
        ''',
        f'''
        SELECT
            CAST(bp.id AS TEXT) AS id,
            bp.title,
            bp.type,
            bp.year_
        FROM {prefix}bibliographic_production bp
        WHERE CAST(bp.id AS TEXT) IN :ids
        ''',
    ]
    bp_ids: list[str] = []
    for q_sql in queries:
        try:
            stmt = text(q_sql).bindparams(bindparam('ids', expanding=True))
            cursor = await conn.execute(stmt, {'ids': ids})
            for row in cursor.mappings().all():
                pid = str(row['id'])
                if pid in prods_map:
                    continue
                raw_t = (row.get('type') or '').upper()
                if 'CHAPTER' in raw_t or 'CAPITULO' in raw_t:
                    p_type, lbl = 'book_chapter', 'Capítulo de Livro'
                elif 'BOOK' in raw_t or 'LIVRO' in raw_t:
                    p_type, lbl = 'book', 'Livro'
                else:
                    p_type, lbl = 'article', 'Artigo em Periódico'

                authors = _parse_authors(
                    _clean_str(row.get('authors')),
                    _clean_str(row.get('researcher_name')),
                )
                details = ProductionDetails(
                    doi=_clean_str(row.get('doi')),
                    nature=_clean_str(row.get('nature')),
                )
                prods_map[pid] = ProductionCard(
                    id=pid,
                    title=sanitize_untrusted_text(str(row['title'])),
                    type=p_type,
                    type_label=lbl,
                    year=_clean_int(row.get('year_')),
                    authors=authors,
                    details=details,
                )
                bp_ids.append(pid)
            break
        except (OperationalError, DBAPIError, SQLAlchemyError):
            continue

    if bp_ids:
        await _enrich_bibliographic_details(conn, prefix, bp_ids, prods_map)


async def _fetch_patents(
    conn: Any,
    prefix: str,
    ids: list[str],
    prods_map: dict[str, ProductionCard],
) -> None:
    try:
        sql = text(
            f'''
            SELECT
                CAST(p.id AS TEXT) AS id,
                p.title,
                p.category,
                p.code,
                p.development_year,
                p.deposit_date,
                p.grant_date,
                r.name AS researcher_name
            FROM {prefix}patent p
            LEFT JOIN {prefix}researcher r ON r.id = p.researcher_id
            WHERE CAST(p.id AS TEXT) IN :ids
            '''
        ).bindparams(bindparam('ids', expanding=True))
        cursor = await conn.execute(sql, {'ids': ids})
        for row in cursor.mappings().all():
            pid = str(row['id'])
            if pid in prods_map:
                continue
            year = _clean_int(row.get('development_year')) or _clean_int(
                row.get('deposit_date')
            )
            authors = _parse_authors(
                None, _clean_str(row.get('researcher_name'))
            )
            details = ProductionDetails(
                status=_clean_str(row.get('category') or row.get('code')),
                grant_date=_clean_str(row.get('grant_date')),
            )
            prods_map[pid] = ProductionCard(
                id=pid,
                title=sanitize_untrusted_text(str(row['title'])),
                type='patent',
                type_label='Patente',
                year=year,
                authors=authors,
                details=details,
            )
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass


async def _fetch_software(
    conn: Any,
    prefix: str,
    ids: list[str],
    prods_map: dict[str, ProductionCard],
) -> None:
    try:
        sql = text(
            f'''
            SELECT
                CAST(s.id AS TEXT) AS id,
                s.title,
                s.year,
                s.platform,
                s.environment,
                s.availability,
                r.name AS researcher_name
            FROM {prefix}software s
            LEFT JOIN {prefix}researcher r ON r.id = s.researcher_id
            WHERE CAST(s.id AS TEXT) IN :ids
            '''
        ).bindparams(bindparam('ids', expanding=True))
        cursor = await conn.execute(sql, {'ids': ids})
        for row in cursor.mappings().all():
            pid = str(row['id'])
            if pid in prods_map:
                continue
            authors = _parse_authors(
                None, _clean_str(row.get('researcher_name'))
            )
            details = ProductionDetails(
                status=_clean_str(
                    row.get('platform') or row.get('availability')
                ),
            )
            prods_map[pid] = ProductionCard(
                id=pid,
                title=sanitize_untrusted_text(str(row['title'])),
                type='software',
                type_label='Software',
                year=_clean_int(row.get('year')),
                authors=authors,
                details=details,
            )
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass


async def _fetch_events(
    conn: Any,
    prefix: str,
    ids: list[str],
    prods_map: dict[str, ProductionCard],
) -> None:
    try:
        sql = text(
            f'''
            SELECT
                CAST(e.id AS TEXT) AS id,
                e.title,
                e.event_name,
                e.year,
                e.nature,
                e.form_participation,
                r.name AS researcher_name
            FROM {prefix}participation_events e
            LEFT JOIN {prefix}researcher r ON r.id = e.researcher_id
            WHERE CAST(e.id AS TEXT) IN :ids
            '''
        ).bindparams(bindparam('ids', expanding=True))
        cursor = await conn.execute(sql, {'ids': ids})
        for row in cursor.mappings().all():
            pid = str(row['id'])
            if pid in prods_map:
                continue
            authors = _parse_authors(
                None, _clean_str(row.get('researcher_name'))
            )
            details = ProductionDetails(
                event_name=_clean_str(row.get('event_name')),
                nature=_clean_str(row.get('nature')),
                status=_clean_str(row.get('form_participation')),
            )
            prods_map[pid] = ProductionCard(
                id=pid,
                title=sanitize_untrusted_text(str(row['title'])),
                type='event',
                type_label='Participação em Evento',
                year=_clean_int(row.get('year')),
                authors=authors,
                details=details,
            )
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass


async def _fetch_canonical_views(
    conn: Any,
    prefix: str,
    ids: list[str],
    prods_map: dict[str, ProductionCard],
) -> None:
    try:
        sql = text(
            f'''
            SELECT
                CAST(ca.canonical_id AS TEXT) AS id,
                ca.title,
                ca.year,
                ca.doi,
                ca.qualis,
                ca.magazine_name,
                ca.issn
            FROM {prefix}mv_canonical_articles ca
            WHERE CAST(ca.canonical_id AS TEXT) IN :ids
            '''
        ).bindparams(bindparam('ids', expanding=True))
        cursor = await conn.execute(sql, {'ids': ids})
        for row in cursor.mappings().all():
            pid = str(row['id'])
            if pid in prods_map:
                continue
            details = ProductionDetails(
                qualis=_clean_str(row.get('qualis')),
                doi=_clean_str(row.get('doi')),
                issn=_clean_str(row.get('issn')),
                magazine=_clean_str(row.get('magazine_name')),
            )
            prods_map[pid] = ProductionCard(
                id=pid,
                title=sanitize_untrusted_text(str(row['title'])),
                type='article',
                type_label='Artigo em Periódico',
                year=_clean_int(row.get('year')),
                authors=[],
                details=details,
            )
    except (OperationalError, DBAPIError, SQLAlchemyError):
        pass


async def hydrate_productions(
    engine: AsyncEngine,
    schema: str,
    identifiers: list[str],
) -> list[ProductionCard]:
    """Hidrata até MAX_CARDS produções a partir de seus IDs."""
    clean_ids: list[str] = []
    for item in identifiers:
        s = _clean_str(item)
        if s and s not in clean_ids:
            clean_ids.append(s)
        if len(clean_ids) >= MAX_CARDS:
            break

    if not clean_ids:
        return []

    backend = engine.url.get_backend_name()
    prefix = f'"{schema}".' if backend == 'postgresql' and schema else ''

    prods_map: dict[str, ProductionCard] = {}

    async with engine.connect() as conn:
        await _fetch_bibliographic(conn, prefix, clean_ids, prods_map)
        await _fetch_patents(conn, prefix, clean_ids, prods_map)
        await _fetch_software(conn, prefix, clean_ids, prods_map)
        await _fetch_events(conn, prefix, clean_ids, prods_map)

        missing = [i for i in clean_ids if i not in prods_map]
        if missing:
            await _fetch_canonical_views(conn, prefix, missing, prods_map)

    ordered: list[ProductionCard] = []
    seen: set[str] = set()
    for ident in clean_ids:
        if ident in prods_map and ident not in seen:
            seen.add(ident)
            ordered.append(prods_map[ident])

    return ordered
