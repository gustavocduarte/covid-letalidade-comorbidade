"""Conversão do CSV bruto do SIVEP-Gripe em Parquet (um por ano) com DuckDB.

Lê o CSV em streaming (sem carregar o arquivo na RAM), mantém só os casos de COVID e as
colunas usadas, e grava com tipos reais (datas e inteiros pequenos).
"""

import os
import tempfile
from pathlib import Path

import duckdb

from config import (
    CLASSI_FIN_COVID,
    COMORBIDADES,
    DUCKDB_LIMITE_MEMORIA,
    ENCODING_CSV,
)

# Colunas do Parquet, na ordem de saída. CLASSI_FIN fica de fora: após o filtro é sempre 5.
COLUNAS_INTEIRAS = ["EVOLUCAO", *COMORBIDADES]


def csv_para_parquet(
    caminho_csv: Path, caminho_parquet: Path, limite_memoria: str = DUCKDB_LIMITE_MEMORIA
) -> int:
    """Converte o CSV bruto de um ano em Parquet só com os casos de COVID e devolve o nº de linhas.

    Coluna ausente no CSV ou arquivo fora de UTF-8 levantam erro do DuckDB. A escrita é
    atômica: um arquivo parcial nunca ocupa o lugar de um Parquet bom.
    """
    caminho_parquet.parent.mkdir(parents=True, exist_ok=True)
    parcial = caminho_parquet.with_name(caminho_parquet.name + ".parcial")

    inteiros = ", ".join(f"TRY_CAST({coluna} AS SMALLINT) AS {coluna}" for coluna in COLUNAS_INTEIRAS)
    # DT_SIN_PRI vem como "2020-03-02T00:00:00.000Z": usamos só os 10 primeiros caracteres para
    # não depender do fuso da sessão (um cast para TIMESTAMPTZ poderia recuar o dia).
    consulta = f"""
        COPY (
            SELECT TRY_CAST(left(DT_SIN_PRI, 10) AS DATE) AS DT_SIN_PRI, SG_UF, {inteiros}
            FROM read_csv(?, delim=';', quote='"', encoding='{ENCODING_CSV}', header=true, all_varchar=true)
            WHERE TRY_CAST(CLASSI_FIN AS SMALLINT) = {CLASSI_FIN_COVID}
        ) TO '{_literal(parcial)}' (FORMAT parquet, COMPRESSION zstd)
    """

    # O spill do DuckDB vai para uma pasta temporária do sistema, nunca para o repositório.
    with tempfile.TemporaryDirectory() as pasta_temp:
        con = duckdb.connect()
        try:
            con.execute(f"SET memory_limit = '{limite_memoria}'")
            con.execute("SET enable_progress_bar = false")  # a barra suja o stdout dos logs
            con.execute(f"SET temp_directory = '{_literal(Path(pasta_temp))}'")
            con.execute(consulta, [str(caminho_csv)])
            linhas = con.execute(f"SELECT count(*) FROM read_parquet('{_literal(parcial)}')").fetchone()[0]
        except Exception:
            parcial.unlink(missing_ok=True)
            raise
        finally:
            con.close()

    os.replace(parcial, caminho_parquet)
    return linhas


def _literal(caminho: Path) -> str:
    """Caminho com barras normais e aspas simples escapadas, para uso dentro de literal SQL."""
    return caminho.as_posix().replace("'", "''")
