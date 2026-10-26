"""Agregações em SQL (DuckDB) sobre os Parquets por ano de casos de COVID.

Cada função devolve um DataFrame com as mesmas colunas e a mesma ordem de linhas da versão
pandas equivalente em transform.py.
"""

import tempfile
from collections.abc import Iterator
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
)


@contextmanager
def abrir_casos(pasta_detalhado: Path, limite_memoria: str = DUCKDB_LIMITE_MEMORIA) -> Iterator[duckdb.DuckDBPyConnection]:
    """Conexão com a view `casos` sobre os Parquets de ano=*/ (a pasta do ano vira a coluna `ano`).

    O caminho vem sempre por argumento, para quem chama poder apontá-lo para outro lugar.
    """
    glob = (pasta_detalhado / "ano=*" / NOME_PARQUET_ANO).as_posix().replace("'", "''")
    # O spill do DuckDB vai para uma pasta temporária do sistema, nunca para o repositório.
    with tempfile.TemporaryDirectory() as pasta_temp:
        con = duckdb.connect()
        try:
            con.execute(f"SET memory_limit = '{limite_memoria}'")
            con.execute(f"SET temp_directory = '{Path(pasta_temp).as_posix()}'")
            con.execute(f"CREATE VIEW casos AS SELECT * FROM read_parquet('{glob}', hive_partitioning=true)")
            yield con
        finally:
            con.close()


def _sql_letalidade_por_comorbidade(por_ano: bool) -> str:
    colunas = ", ".join(COMORBIDADES)
    lista = ", ".join(f"'{c}'" for c in COMORBIDADES)
    chave = "ano, " if por_ano else ""
    # Empate de taxa: a versão pandas mantém a ordem de COMORBIDADES por ano e a ordem alfabética
    # no agregado (o groupby ordena por nome antes do sort_values).
    desempate = f"list_position([{lista}], comorbidade)" if por_ano else "comorbidade"

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

    # INCLUDE NULLS mantém as comorbidades nunca preenchidas (linha com zeros, como no pandas).
    return f"""
        WITH base AS (
            SELECT {chave}comorbidade,{contagens("com", COMORBIDADE_SIM)},{contagens("sem", COMORBIDADE_NAO)}
            FROM (SELECT ano, EVOLUCAO, {colunas} FROM casos)
                UNPIVOT INCLUDE NULLS (valor FOR comorbidade IN ({colunas}))
            GROUP BY {chave}comorbidade
        )
        SELECT {chave}comorbidade, {selecao}
        FROM base
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
    # Casos sem UF ficam de fora (o groupby do pandas também os descarta). Empate de taxa: a versão
    # pandas ordena por sigla por ano e, no agregado, pela ordem alfabética do groupby.
    ordem = "ano, sigla" if por_ano else "taxa_letalidade DESC NULLS LAST, sigla"
    return f"""
        WITH base AS (
            SELECT {chave}SG_UF AS sigla,
                count(*) AS casos,
                count(*) FILTER (WHERE EVOLUCAO = {EVOLUCAO_OBITO}) AS obitos,
                count(*) FILTER (WHERE EVOLUCAO IN ({EVOLUCAO_CURA}, {EVOLUCAO_OBITO})) AS desfecho_conhecido
            FROM casos
            WHERE SG_UF IS NOT NULL
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
