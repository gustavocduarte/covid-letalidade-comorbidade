"""Agregações em SQL (DuckDB) sobre os Parquets por ano de casos de COVID.

Cada função devolve um DataFrame já na ordem de saída dos CSVs de data/processed/.
"""

import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd

from config import (
    COMORBIDADE_NAO,
    COMORBIDADE_SIM,
    COMORBIDADES,
    DUCKDB_LIMITE_MEMORIA,
    EVOLUCAO_CURA,
    EVOLUCAO_OBITO,
    NOME_PARQUET_ANO,
    UFS_VALIDAS,
)

# Lista SQL das 27 siglas: casos sem UF ou com UF fora dela ficam fora das tabelas por estado.
_UFS_SQL = ", ".join(f"'{uf}'" for uf in UFS_VALIDAS)


@contextmanager
def abrir_casos(
    pasta_detalhado: Path, anos: Iterable[int] | None = None, limite_memoria: str = DUCKDB_LIMITE_MEMORIA,
) -> Iterator[duckdb.DuckDBPyConnection]:
    """Conexão com a view `casos` sobre os Parquets de ano=*/ (a pasta do ano vira a coluna `ano`).

    O caminho e os anos vêm sempre por argumento, para quem chama poder apontá-los para outro lugar.
    `anos` restringe as consultas a esses anos (ano=* fora da lista é ignorado); None usa todos.
    """
    filtro = "" if anos is None else f"WHERE ano IN ({', '.join(str(int(a)) for a in anos) or 'NULL'})"
    glob = (pasta_detalhado / "ano=*" / NOME_PARQUET_ANO).as_posix().replace("'", "''")
    # O spill do DuckDB vai para uma pasta temporária do sistema, nunca para o repositório.
    with tempfile.TemporaryDirectory() as pasta_temp:
        con = duckdb.connect()
        try:
            con.execute(f"SET memory_limit = '{limite_memoria}'")
            con.execute("SET enable_progress_bar = false")  # a barra suja o stdout dos logs
            con.execute(f"SET temp_directory = '{Path(pasta_temp).as_posix()}'")
            con.execute(f"CREATE VIEW casos AS SELECT * FROM read_parquet('{glob}', hive_partitioning=true) {filtro}")
            # Anos pelos arquivos, não pelas linhas: um ano sem nenhum caso de COVID tem Parquet vazio.
            con.execute(f"""CREATE VIEW anos AS SELECT ano FROM (
                SELECT regexp_extract(file, 'ano=([0-9]+)', 1)::BIGINT AS ano FROM glob('{glob}')) {filtro}""")
            yield con
        finally:
            con.close()


def _sql_letalidade_por_comorbidade(por_ano: bool) -> str:
    colunas = ", ".join(COMORBIDADES)
    lista = ", ".join(f"'{c}'" for c in COMORBIDADES)
    chave = "ano, " if por_ano else ""
    # Empate de taxa: vale a ordem de COMORBIDADES, por ano e no agregado.
    desempate = f"list_position([{lista}], comorbidade)"

    def contagens(sufixo: str, codigo: int) -> str:
        return f"""
            count(*) FILTER (WHERE valor = {codigo}) AS casos_{sufixo},
            count(*) FILTER (WHERE valor = {codigo} AND EVOLUCAO = {EVOLUCAO_OBITO}) AS obitos_{sufixo},
            count(*) FILTER (WHERE valor = {codigo} AND EVOLUCAO IN ({EVOLUCAO_CURA}, {EVOLUCAO_OBITO}))
                AS desfecho_conhecido_{sufixo}"""

    def taxa(sufixo: str) -> str:
        return (f"CASE WHEN desfecho_conhecido_{sufixo} = 0 THEN NULL "
                f"ELSE obitos_{sufixo}::DOUBLE / desfecho_conhecido_{sufixo} END AS taxa_letalidade_{sufixo}")

    # A tabela por ano intercala cada taxa com suas contagens; o agregado deixa as duas no fim.
    if por_ano:
        selecao = (f'casos_com, obitos_com, desfecho_conhecido_com, {taxa("com")}, '
                   f'casos_sem, obitos_sem, desfecho_conhecido_sem, {taxa("sem")}')
    else:
        selecao = ("casos_com, obitos_com, desfecho_conhecido_com, casos_sem, obitos_sem, desfecho_conhecido_sem, "
                   f'{taxa("com")}, {taxa("sem")}')

    # INCLUDE NULLS mantém as comorbidades nunca preenchidas (linha com zeros).
    # Por ano, a grade ano x comorbidade também devolve as 11 linhas de zeros de um ano sem casos.
    nomes = ("casos_com", "obitos_com", "desfecho_conhecido_com", "casos_sem", "obitos_sem", "desfecho_conhecido_sem")
    if por_ano:
        zeros = ", ".join(f"coalesce(b.{n}, 0) AS {n}" for n in nomes)
        completo = f"""SELECT g.ano, g.comorbidade, {zeros}
            FROM (SELECT ano, unnest([{lista}]) AS comorbidade FROM anos) g
                LEFT JOIN base b ON b.ano = g.ano AND b.comorbidade = g.comorbidade"""
    else:
        completo = "SELECT * FROM base"
    return f"""
        WITH base AS (
            SELECT {chave}comorbidade,{contagens("com", COMORBIDADE_SIM)},{contagens("sem", COMORBIDADE_NAO)}
            FROM (SELECT ano, EVOLUCAO, {colunas} FROM casos)
                UNPIVOT INCLUDE NULLS (valor FOR comorbidade IN ({colunas}))
            GROUP BY {chave}comorbidade
        ), completo AS (
            {completo}
        )
        SELECT {chave}comorbidade, {selecao}
        FROM completo
        ORDER BY {chave}taxa_letalidade_com DESC NULLS LAST, {desempate}
    """


def letalidade_por_comorbidade_por_ano(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Letalidade por comorbidade em cada ano (colunas de `letalidade_por_comorbidade`, mais `ano`)."""
    return con.execute(_sql_letalidade_por_comorbidade(por_ano=True)).df()


def letalidade_por_comorbidade_agregado(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Letalidade por comorbidade somando todos os anos (soma óbitos e desfechos antes de dividir)."""
    return con.execute(_sql_letalidade_por_comorbidade(por_ano=False)).df()


def _sql_letalidade_por_estado(por_ano: bool) -> str:
    chave = "ano, " if por_ano else ""
    # Casos sem UF ou com UF inválida ficam de fora. Empate de taxa: desempata pela sigla.
    ordem = "ano, sigla" if por_ano else "taxa_letalidade DESC NULLS LAST, sigla"
    return f"""
        WITH base AS (
            SELECT {chave}SG_UF AS sigla,
                count(*) AS casos,
                count(*) FILTER (WHERE EVOLUCAO = {EVOLUCAO_OBITO}) AS obitos,
                count(*) FILTER (WHERE EVOLUCAO IN ({EVOLUCAO_CURA}, {EVOLUCAO_OBITO})) AS desfecho_conhecido
            FROM casos
            WHERE SG_UF IN ({_UFS_SQL})
            GROUP BY {chave}SG_UF
        )
        SELECT {chave}sigla, casos, obitos, desfecho_conhecido,
            CASE WHEN desfecho_conhecido = 0 THEN NULL ELSE obitos::DOUBLE / desfecho_conhecido END
                AS taxa_letalidade
        FROM base
        ORDER BY {ordem}
    """


def letalidade_por_estado_por_ano(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Casos, óbitos e letalidade por UF de residência em cada ano (colunas de `letalidade_por_estado`, mais `ano`)."""
    return con.execute(_sql_letalidade_por_estado(por_ano=True)).df()


def letalidade_por_estado_agregado(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Letalidade por UF somando todos os anos (soma óbitos e desfechos antes de dividir)."""
    return con.execute(_sql_letalidade_por_estado(por_ano=False)).df()


def serie_semanal_casos(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Casos de COVID por semana de início dos sintomas (semana começa na segunda-feira).

    Soma os anos direto, então os dois pedaços de uma semana na virada do ano já saem juntos.
    Casos sem data válida ficam de fora.
    """
    return con.execute("""
        SELECT date_trunc('week', DT_SIN_PRI) AS semana, count(*) AS casos
        FROM casos
        WHERE DT_SIN_PRI IS NOT NULL
        GROUP BY semana
        ORDER BY semana
    """).df()


def serie_semanal_por_comorbidade(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Casos por semana e comorbidade (só quem tem a condição); um caso com duas entra nas duas."""
    colunas = ", ".join(COMORBIDADES)
    return con.execute(f"""
        SELECT date_trunc('week', DT_SIN_PRI) AS semana, comorbidade, count(*) AS casos
        FROM (SELECT DT_SIN_PRI, {colunas} FROM casos)
            UNPIVOT (valor FOR comorbidade IN ({colunas}))
        WHERE valor = {COMORBIDADE_SIM} AND DT_SIN_PRI IS NOT NULL
        GROUP BY comorbidade, semana
        ORDER BY comorbidade, semana
    """).df()


def serie_semanal_por_estado(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Casos por semana e UF de residência; casos sem data válida, sem UF ou com UF inválida ficam de fora."""
    return con.execute(f"""
        SELECT date_trunc('week', DT_SIN_PRI) AS semana, SG_UF AS sigla, count(*) AS casos
        FROM casos
        WHERE DT_SIN_PRI IS NOT NULL AND SG_UF IN ({_UFS_SQL})
        GROUP BY semana, sigla
        ORDER BY semana, sigla
    """).df()
