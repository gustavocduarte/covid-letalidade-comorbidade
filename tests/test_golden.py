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
    NOME_PARQUET_ANO,
    NOME_RELATORIO,
)
from extract import URLS_SRAG

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
PROCESSADOS = RAIZ / "data" / "processed"
RESUMO = Path(__file__).resolve().parent / "golden" / "detalhado_resumo.json"

# Gerados por `cli.py pipeline`; `cli.py serie-estado` roda em seguida e regrava o último a partir dos Parquets.
SAIDAS = [
    "letalidade_por_comorbidade_todos_anos.csv",
    "letalidade_por_comorbidade_agregado.csv",
    "casos_covid_por_semana.csv",
    "casos_covid_semanal_por_comorbidade.csv",
    "letalidade_por_estado_agregado.csv",
    "casos_covid_por_semana_estado.csv",
    "resumo_geral.csv",
]

# As 14 colunas do Parquet; a impressão digital de um ano usa todas elas.
COLUNAS_PARQUET = ["DT_SIN_PRI", "SG_UF", "EVOLUCAO", *COMORBIDADES]

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
                    "Rode `python src/cli.py pipeline` para baixá-los.")

    base = tmp_path_factory.mktemp("dourado")
    (base / "src").mkdir()
    for arquivo in (RAIZ / "src").glob("*.py"):
        (base / "src" / arquivo.name).write_bytes(arquivo.read_bytes())
    (base / "data").mkdir()
    _ligar_pasta(base / "data" / "raw", RAW)

    for comando in (["pipeline"], ["serie-estado"]):
        _rodar(base, [str(base / "src" / "cli.py"), *comando])
    return base / "data" / "processed"


def _rodar(base: Path, argumentos: list[str]) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(base / "src")}
    resultado = subprocess.run(
        [sys.executable, *argumentos],
        cwd=base, env=env, capture_output=True, text=True, encoding="utf-8", timeout=1800, check=False,
    )
    assert resultado.returncode == 0, f"{argumentos} falhou:\n{resultado.stdout[-2000:]}\n{resultado.stderr[-2000:]}"
    return resultado


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


def test_relatorio_de_qualidade_igual_ao_versionado(saidas_geradas):
    gerado = json.loads((saidas_geradas / NOME_RELATORIO).read_text(encoding="utf-8"))
    esperado = json.loads((PROCESSADOS / NOME_RELATORIO).read_text(encoding="utf-8"))

    assert gerado == esperado



def impressao_digital_sql(colunas: list[str]) -> str:
    """Soma, sobre as linhas, do MD5 de um texto canônico com as colunas (nulo = "<nulo>").

    Não depende da ordem das linhas. Usa MD5, que é estável entre versões do DuckDB (ao contrário de hash()).
    """
    texto = ", ".join(f"coalesce(CAST({c} AS VARCHAR), '<nulo>')" for c in colunas)
    return f"sum(md5_number_lower(concat_ws('|', {texto})))"


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
               count(*) FILTER (WHERE EVOLUCAO = {EVOLUCAO_CURA}), {impressao_digital_sql(COLUNAS_PARQUET)}
        FROM read_parquet('{glob}', hive_partitioning=true) GROUP BY ano ORDER BY ano
    """).fetchall()
    return {
        str(ano): {
            "linhas": linhas, "obitos": obitos, "curas": curas, "impressao_digital": str(impressao),
            "casos_por_uf": contar("SG_UF", ano),
            "valores_por_coluna": {c: contar(c, ano) for c in ["DT_SIN_PRI", "EVOLUCAO", *COMORBIDADES]},
        }
        for ano, linhas, obitos, curas, impressao in totais
    }


def test_parquets_iguais_ao_resumo_versionado(saidas_geradas):
    """Contagens por coluna e impressão digital por ano (soma de MD5 das 14 colunas, sem depender da ordem das linhas).

    O resumo foi conferido contra o cache CSV antigo linha a linha, e as impressões digitais bateram nos 7 anos.
    """
    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{DUCKDB_LIMITE_MEMORIA}'")
    glob = (saidas_geradas / "detalhado" / "ano=*" / NOME_PARQUET_ANO).as_posix()

    esperado = json.loads(RESUMO.read_text(encoding="utf-8"))

    assert _resumo_por_ano(con, glob) == esperado


def test_segunda_execucao_esta_em_dia_e_gera_as_mesmas_saidas(saidas_geradas):
    arquivos = [*SAIDAS, NOME_RELATORIO]
    antes = {nome: (saidas_geradas / nome).read_bytes() for nome in arquivos}
    base = saidas_geradas.parent.parent
    arquivo_status = base / "status.json"
    comando = "import json, sys, pipeline; open(sys.argv[1], 'w').write(json.dumps(pipeline.executar_pipeline()))"

    _rodar(base, ["-c", comando, str(arquivo_status)])

    status = json.loads(arquivo_status.read_text(encoding="utf-8"))
    assert status == {str(ano): "em_dia" for ano in URLS_SRAG}
    assert {nome: (saidas_geradas / nome).read_bytes() for nome in arquivos} == antes
