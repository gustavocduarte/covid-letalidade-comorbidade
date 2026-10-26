"""Teste de regressão "dourado": roda o pipeline completo sobre os CSVs brutos e compara as
saídas com as versionadas em data/processed/.

Precisa dos ~4,8 GB de data/raw/, então só roda localmente. Para pular: pytest -m "not golden".
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from config import (
    COMORBIDADES,
    DUCKDB_LIMITE_MEMORIA,
    EVOLUCAO_CURA,
    EVOLUCAO_OBITO,
    NOME_CACHE_DETALHADO,
    NOME_PARQUET_ANO,
)
from extract import URLS_SRAG

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
PROCESSADOS = RAIZ / "data" / "processed"
RESUMO = Path(__file__).resolve().parent / "golden" / "detalhado_resumo.json"

# Gerados por pipeline.py; gerar_serie_estado.py roda em seguida e regrava o último a partir dos Parquets.
SAIDAS = [
    "letalidade_por_comorbidade_todos_anos.csv",
    "letalidade_por_comorbidade_agregado.csv",
    "casos_covid_por_semana.csv",
    "casos_covid_semanal_por_comorbidade.csv",
    "letalidade_por_estado_agregado.csv",
    "casos_covid_por_semana_estado.csv",
]

# Só as taxas (razão de inteiros em float) têm tolerância; contagens são exatas.
TOLERANCIA_TAXA = 1e-12

pytestmark = pytest.mark.golden


def _brutos_faltando() -> list[str]:
    return [url.split("/")[-1] for url in URLS_SRAG.values() if not (RAW / url.split("/")[-1]).exists()]


@pytest.fixture(scope="module")
def saidas_geradas(tmp_path_factory) -> Path:
    if os.environ.get("CI"):
        pytest.skip("teste dourado precisa de data/raw (~4,8 GB); roda só localmente")
    faltando = _brutos_faltando()
    if faltando:
        pytest.skip(f"data/raw incompleto, faltam {len(faltando)} CSV(s): {', '.join(faltando)}. "
                    "Rode `python src/pipeline.py` para baixá-los.")

    base = tmp_path_factory.mktemp("dourado")
    (base / "src").mkdir()
    for arquivo in (RAIZ / "src").glob("*.py"):
        (base / "src" / arquivo.name).write_bytes(arquivo.read_bytes())
    (base / "data").mkdir()
    _ligar_pasta(base / "data" / "raw", RAW)

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for script in ("pipeline.py", "gerar_serie_estado.py"):
        resultado = subprocess.run(
            [sys.executable, str(base / "src" / script)],
            cwd=base, env=env, capture_output=True, text=True, encoding="utf-8", timeout=1800, check=False,
        )
        assert resultado.returncode == 0, f"{script} falhou:\n{resultado.stdout[-2000:]}\n{resultado.stderr[-2000:]}"
    return base / "data" / "processed"


def _ligar_pasta(link: Path, alvo: Path) -> None:
    """Junction no Windows (não exige privilégio de administrador); symlink nos demais."""
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(alvo)], check=True, capture_output=True)
    else:
        link.symlink_to(alvo, target_is_directory=True)


@pytest.mark.parametrize("nome", SAIDAS)
def test_saida_igual_a_versionada(saidas_geradas, nome):
    esperado_path = PROCESSADOS / nome
    if not esperado_path.exists():
        pytest.skip(f"{nome} não existe localmente (cache ignorado pelo git)")

    gerado = pd.read_csv(saidas_geradas / nome)
    esperado = pd.read_csv(esperado_path)

    assert list(gerado.columns) == list(esperado.columns)
    colunas_taxa = [c for c in esperado.columns if c.startswith("taxa_letalidade")]
    colunas_exatas = [c for c in esperado.columns if c not in colunas_taxa]

    assert_frame_equal(gerado[colunas_exatas], esperado[colunas_exatas], check_exact=True)
    if colunas_taxa:
        assert_frame_equal(gerado[colunas_taxa], esperado[colunas_taxa], check_exact=False, rtol=TOLERANCIA_TAXA)


def test_parquets_iguais_ao_cache_csv_anterior(saidas_geradas):
    """Cada linha dos Parquets é igual à linha do cache CSV que gerou os CSVs versionados (mesma posição)."""
    cache = PROCESSADOS / NOME_CACHE_DETALHADO
    if not cache.exists():
        pytest.skip(f"{NOME_CACHE_DETALHADO} não existe localmente (cache ignorado pelo git)")

    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{DUCKDB_LIMITE_MEMORIA}'")
    # No cache tudo era texto: datas com hora ("2020-03-02T00:00:00.000Z") e códigos como "2.0".
    conversao = {
        "DT_SIN_PRI": "TRY_CAST(left(DT_SIN_PRI, 10) AS DATE)",
        "SG_UF": "SG_UF",
        **{c: f"TRY_CAST(TRY_CAST({c} AS DOUBLE) AS SMALLINT)" for c in ["EVOLUCAO", *COMORBIDADES]},
    }
    anos = sorted(int(p.name.removeprefix("ano=")) for p in (saidas_geradas / "detalhado").glob("ano=*"))
    assert anos == sorted(URLS_SRAG)

    for ano in anos:
        parquet = (saidas_geradas / "detalhado" / f"ano={ano}" / NOME_PARQUET_ANO).as_posix()
        iguais = " AND ".join(f"c.{coluna} IS NOT DISTINCT FROM p.{coluna}" for coluna in conversao)
        # numeradas depois do filtro de ano, na ordem do arquivo
        linhas_csv, linhas_parquet, divergentes = con.execute(f"""
            WITH
            c AS (SELECT row_number() OVER () AS n, {", ".join(f"{expr} AS {c}" for c, expr in conversao.items())}
                  FROM read_csv('{cache.as_posix()}', delim=',', header=true, all_varchar=true) WHERE ano = '{ano}'),
            p AS (SELECT row_number() OVER () AS n, {", ".join(conversao)} FROM read_parquet('{parquet}'))
            SELECT (SELECT count(*) FROM c), (SELECT count(*) FROM p),
                   count(*) FILTER (WHERE c.n IS NULL OR p.n IS NULL OR NOT ({iguais}))
            FROM c FULL JOIN p ON c.n = p.n
        """).fetchone()
        assert (linhas_parquet, divergentes) == (linhas_csv, 0), f"{ano}: parquet difere do cache CSV"


def _resumo_por_ano(con: duckdb.DuckDBPyConnection, glob: str) -> dict:
    """Por ano: linhas, óbitos, curas, casos por UF e contagem de valores de cada coluna ("(vazio)" = nulo)."""

    def chave(valor):
        return "(vazio)" if valor is None else str(valor)

    def contar(coluna, ano):
        linhas = con.execute(f"""SELECT {coluna}, count(*) FROM read_parquet('{glob}', hive_partitioning=true)
                                 WHERE ano = {ano} GROUP BY 1 ORDER BY 1 NULLS LAST""").fetchall()
        return {chave(valor): n for valor, n in linhas}

    totais = con.execute(f"""
        SELECT ano, count(*), count(*) FILTER (WHERE EVOLUCAO = {EVOLUCAO_OBITO}),
               count(*) FILTER (WHERE EVOLUCAO = {EVOLUCAO_CURA})
        FROM read_parquet('{glob}', hive_partitioning=true) GROUP BY ano ORDER BY ano
    """).fetchall()
    return {
        str(ano): {
            "linhas": linhas, "obitos": obitos, "curas": curas, "casos_por_uf": contar("SG_UF", ano),
            "valores_por_coluna": {c: contar(c, ano) for c in ["DT_SIN_PRI", "EVOLUCAO", *COMORBIDADES]},
        }
        for ano, linhas, obitos, curas in totais
    }


def test_parquets_iguais_ao_resumo_versionado(saidas_geradas):
    """Não depende do cache CSV: o resumo versionado foi gerado dele quando ele ainda existia."""
    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{DUCKDB_LIMITE_MEMORIA}'")
    glob = (saidas_geradas / "detalhado" / "ano=*" / NOME_PARQUET_ANO).as_posix()

    esperado = json.loads(RESUMO.read_text(encoding="utf-8"))

    assert _resumo_por_ano(con, glob) == esperado
