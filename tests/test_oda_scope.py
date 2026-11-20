"""Regressões ODA com origem SQLite isolada, sem LLM ou banco externo."""

import asyncio
import sqlite3
import unittest
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlglot
from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect

from observatorio_maria.catalog.observed import _read_distinct  # noqa: PLC2701
from observatorio_maria.catalog.yaml_io import load_catalog_file
from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
)
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.execution import ResultStore
from observatorio_maria.query.federated_validator import (
    validate_federated_query,
)
from observatorio_maria.query.tool import QueryRunner
from observatorio_maria.query.validator import (
    build_query_schema,
    validate_query,
)


class OdaScopeTests(unittest.TestCase):
    def setUp(self):
        document = load_catalog_file(Path('catalog/oda.yaml'))
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute("ATTACH DATABASE ':memory:' AS public")
        self.db.create_function(
            'translate',
            3,
            lambda value, a, b: value.translate(str.maketrans(a, b)),
        )
        self.entities = []
        for item in document.entities:
            entity = CatalogEntity(
                datasource_id='oda',
                schema_name='public',
                name=item.name,
                visible=True,
                queryable=True,
                present=True,
            )
            for column in item.columns:
                entity.columns.append(
                    CatalogColumn(
                        entity_id=entity.id,
                        name=column.name,
                        visible=True,
                        present=True,
                        searchable=column.searchable,
                    )
                )
            self.entities.append(entity)
            columns = ', '.join(f'"{c.name}" TEXT' for c in item.columns)
            self.db.execute(f'CREATE TABLE public.{item.name} ({columns})')
        self.schema = build_query_schema(
            CatalogDataSource(
                id='oda', name='ODA', connection_env='ODA_DATABASE_URL'
            ),
            self.entities,
        )
        self.schema = replace(
            self.schema,
            enum_values={
                ('grupo_pesquisa', 'situacao'): ('certificado', 'excluido'),
                ('grupo_pesquisa_instituicao', 'tipo_relacao'): (
                    'sede',
                    'parceira',
                ),
                ('pesquisador', 'tipo'): ('pesquisador', 'estudante'),
                ('pesquisador', 'formacao_academica'): (
                    'doutorado',
                    'mestrado',
                ),
            },
        )
        self.db.executescript("""
            INSERT INTO public.instituicao(id,sigla,nome) VALUES
                ('i1','UNEB','Universidade do Estado da Bahia'),
                ('i2','OUTRA','Outra universidade'),
                ('i3','FEA/BA','Fundação da Universidade Federal da Bahia'),
                ('i4','FIOCRUZ','Fiocruz Rio de Janeiro'),
                ('i5','FIOCRUZ','Instituto Gonçalo Moniz'),
                ('i6','IFBA - Brumado','Campus Brumado');
            INSERT INTO public.grupo_pesquisa(id,nome,situacao) VALUES
                ('g1','NPAI','certificado'), ('g2','Fora','certificado'),
                ('g3','Só parceira','certificado'),
                ('g4','Fundação','excluido'),
                ('g5','Fiocruz fora','certificado'),
                ('g6','Moniz','certificado'), ('g7','Campus','certificado');
            INSERT INTO public.grupo_pesquisa_instituicao
                (grupo_id,instituicao_id,tipo_relacao) VALUES
                ('g1','i1','sede'), ('g2','i2','sede'),
                ('g3','i2','sede'), ('g3','i1','parceira'),
                ('g4','i3','sede'), ('g5','i4','sede'),
                ('g6','i5','sede'), ('g7','i6','sede');
            INSERT INTO public.pesquisador(id,nome,lattes_id) VALUES
                ('p1','Pessoa do grupo','0000000000000001'),
                ('p2','Pessoa externa','0000000000000002');
            INSERT INTO public.membro_grupo(grupo_id,pesquisador_id) VALUES
                ('g1','p1'), ('g2','p2');
            INSERT INTO public.linha_pesquisa(id,grupo_id,titulo) VALUES
                ('l1','g1','Computação'), ('l2','g2','Linha externa');
            INSERT INTO public.membro_linha_pesquisa
                (linha_pesquisa_id,pesquisador_id) VALUES
                ('l1','p1'), ('l2','p2');
            INSERT INTO public.setor_aplicacao(id,nome) VALUES
                ('s1','Educação'), ('s2','Setor externo');
            INSERT INTO public.linha_pesquisa_setor_aplicacao
                (linha_pesquisa_id,setor_aplicacao_id) VALUES
                ('l1','s1'), ('l2','s2');
        """)

    def query(self, sql):
        compiled = validate_query(sql, self.schema)
        sqlite_sql = sqlglot.transpile(
            compiled, read='postgres', write='sqlite'
        )[0]
        return self.db.execute(sqlite_sql).fetchall()

    def test_institutions_match_oda_policy_and_exclude_partners(self):
        rows = self.query('SELECT id FROM public.grupo_pesquisa ORDER BY id')
        assert rows == [('g1',), ('g6',), ('g7',)]

    def test_alias_collisions_and_quoted_aliases(self):
        for alias in ('scope_group', 'scope_inst', '_scope', 'Meu Grupo'):
            with self.subTest(alias=alias):
                rows = self.query(
                    f'SELECT "{alias}".grupo_id FROM public.membro_grupo '
                    f'AS "{alias}"'
                )
                assert rows == [('g1',)]

    def test_related_entities_are_scoped(self):
        for table, column, expected in (
            ('pesquisador', 'id', 'p1'),
            ('linha_pesquisa', 'id', 'l1'),
            ('membro_grupo', 'pesquisador_id', 'p1'),
            ('membro_linha_pesquisa', 'pesquisador_id', 'p1'),
            ('setor_aplicacao', 'id', 's1'),
            ('linha_pesquisa_setor_aplicacao', 'setor_aplicacao_id', 's1'),
        ):
            with self.subTest(table=table):
                assert self.query(f'SELECT {column} FROM public.{table}') == [
                    (expected,)
                ]

    def test_match_text_with_alias_and_renamed_cte_column(self):
        for sql in (
            'SELECT gp.nome FROM public.grupo_pesquisa gp '
            "WHERE MATCH_TEXT(gp.nome, 'npai')",
            'WITH g AS (SELECT nome AS title FROM public.grupo_pesquisa) '
            "SELECT g.title FROM g WHERE MATCH_TEXT(g.title, 'npai')",
        ):
            with self.subTest(sql=sql):
                assert self.query(sql) == [('NPAI',)]

    def test_left_join_keeps_groups_without_lines(self):
        rows = self.query(
            'SELECT gp.id, COUNT(lp.id) FROM public.grupo_pesquisa gp '
            'LEFT JOIN public.linha_pesquisa lp ON lp.grupo_id=gp.id '
            'GROUP BY gp.id ORDER BY gp.id'
        )
        assert rows == [('g1', 1), ('g6', 0), ('g7', 0)]

    def test_invalid_enum_literals_are_rejected_before_execution(self):
        for table, column, literal in (
            ('grupo_pesquisa', 'situacao', 'CERTIFICADO'),
            ('pesquisador', 'tipo', 'PESQUISADOR'),
            ('pesquisador', 'formacao_academica', 'DOUTORADO'),
            ('grupo_pesquisa_instituicao', 'tipo_relacao', 'SEDE'),
        ):
            with self.subTest(column=column):
                for condition in (
                    f"{column}='{literal}'",
                    f"{column} IN ('{literal}')",
                ):
                    with pytest.raises(
                        QueryValidationError, match='Valores aceitos'
                    ):
                        validate_query(
                            f'SELECT {column} FROM public.{table} '
                            f'WHERE {condition}',
                            self.schema,
                        )

    def test_hidden_and_non_searchable_columns_remain_blocked(self):
        for sql in (
            'SELECT email FROM public.grupo_pesquisa',
            'SELECT id FROM public.producao',
            'SELECT gp.id FROM public.grupo_pesquisa gp '
            "WHERE MATCH_TEXT(gp.id, 'g1')",
        ):
            with self.subTest(sql=sql):
                with pytest.raises(QueryValidationError):
                    validate_query(sql, self.schema)

    @staticmethod
    def test_federated_oda_queries_are_blocked_before_connection():
        with pytest.raises(QueryValidationError, match='recorte SIMCC'):
            validate_federated_query(
                'SELECT p.nome FROM oda.public.pesquisador p '
                'JOIN simcc.public.researcher r ON r.lattes_id=p.lattes_id',
                None,
            )

    def test_other_sources_do_not_receive_oda_enum_rules(self):
        schema = replace(self.schema, datasource_id='other')
        sql = validate_query(
            'SELECT id FROM public.grupo_pesquisa '
            "WHERE situacao='CERTIFICADO'",
            schema,
        )
        assert 'scope_gpi' not in sql

    def test_observed_values_include_only_scoped_sectors(self):
        database = self.db

        class Connection:
            dialect = sqlite_dialect()

            def __init__(self):
                self.database = database

            @asynccontextmanager
            async def begin(self):
                yield self

            async def execute(self, statement):
                sql = sqlglot.transpile(
                    str(statement), read='postgres', write='sqlite'
                )[0]
                rows = self.database.execute(sql).fetchall()
                return SimpleNamespace(all=lambda: rows)

        entity = next(e for e in self.entities if e.name == 'setor_aplicacao')
        column = next(c for c in entity.columns if c.name == 'nome')
        values = asyncio.run(
            _read_distinct(
                Connection(), entity, column, max_values=20, timeout_seconds=2
            )
        )
        assert values == ['Educação']

    @staticmethod
    def test_oda_researchers_use_result_without_opening_simcc():
        runner = object.__new__(QueryRunner)
        runner.result_store = ResultStore()
        runner.pending_blocks = []
        runner.session = AsyncMock()
        result = runner.result_store.add(
            'oda',
            '',
            ['id', 'nome', 'lattes_id'],
            [['p1', 'Pessoa do grupo', '0000000000000001']],
            truncated=False,
        )
        response = asyncio.run(runner.show_researchers(result.result_id))
        assert response['status'] == 'ok'
        runner.session.get.assert_not_called()
        block = runner.pending_blocks[0]
        assert block['type'] == 'table'
        assert block['rows'][0]['nome'] == 'Pessoa do grupo'
        assert 'id' not in block['rows'][0]
