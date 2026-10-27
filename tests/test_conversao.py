"""Testes da conversão CSV bruto -> Parquet (DuckDB) sobre a amostra sintética de tests/fixtures/."""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from config import COLUNAS_NECESSARIAS, COMORBIDADES
from conversao import csv_para_parquet

FIXTURE_2020 = Path(__file__).resolve().parent / "fixtures" / "INFLUD20-sintetico.csv"
COLUNAS_PARQUET = ["DT_SIN_PRI", "SG_UF", "EVOLUCAO", *COMORBIDADES]


def _ler(parquet: Path) -> pd.DataFrame:
    return duckdb.connect().execute("SELECT * FROM read_parquet(?, hive_partitioning=false)", [str(parquet)]).df()


def _escrever_csv(caminho: Path, colunas: list[str], linhas: list[list[str]], codificacao="utf-8") -> Path:
    texto = "\n".join(";".join(linha) for linha in [colunas, *linhas]) + "\n"
    caminho.write_bytes(texto.encode(codificacao))
    return caminho


def test_converte_so_casos_de_covid_na_ordem_original_e_com_tipos(tmp_path):
    destino = tmp_path / "ano=2020" / "casos.parquet"

    linhas = csv_para_parquet(FIXTURE_2020, destino)

    # a fixture tem 19 linhas de dados (uma com aspas tipográficas no município, não COVID)
    assert len(FIXTURE_2020.read_text(encoding="utf-8").splitlines()) == 20
    assert linhas == 14
    df = _ler(destino)
    assert list(df.columns) == COLUNAS_PARQUET
    tipos = duckdb.connect().execute("DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning=false)", [str(destino)]).fetchall()
    assert {nome: tipo for nome, tipo, *_ in tipos} == {
        "DT_SIN_PRI": "DATE", "SG_UF": "VARCHAR", **{c: "SMALLINT" for c in ["EVOLUCAO", *COMORBIDADES]},
    }
    # o layout ano=AAAA/ vira a coluna "ano" quando o DuckDB lê a pasta com particionamento hive
    anos = duckdb.connect().execute(
        "SELECT DISTINCT ano FROM read_parquet(?, hive_partitioning=true)", [str(destino)]
    ).fetchall()
    assert anos == [(2020,)]
    datas = [None if pd.isna(d) else d.strftime("%Y-%m-%d") for d in df["DT_SIN_PRI"]]
    assert datas == [
        "2020-03-02", "2020-03-04", "2020-03-09", "2020-03-10", "2020-03-11", "2020-03-12", "2020-03-13",
        "2020-03-16", "2020-03-17", "2020-03-18", "2020-03-19", None, None, "2020-12-30",
    ]


def test_casos_de_borda_sao_preservados_como_estao(tmp_path):
    destino = tmp_path / "casos.parquet"
    csv_para_parquet(FIXTURE_2020, destino)
    df = _ler(destino)

    assert df["EVOLUCAO"].value_counts(dropna=False).to_dict() == {1: 5, 2: 5, 3: 2, 9: 1, pd.NA: 1}
    assert "XX" in set(df["SG_UF"])  # UF inválida não é filtrada nesta etapa
    assert df["SG_UF"].isna().sum() == 1  # UF vazia
    assert df["DT_SIN_PRI"].isna().sum() == 2  # data inválida e data vazia
    assert (df["DIABETES"] == 9).sum() == 1  # comorbidade "ignorada" mantém o código 9


def test_coluna_ausente_no_csv_levanta_erro(tmp_path):
    colunas = [c for c in COLUNAS_NECESSARIAS if c != "SG_UF"]
    csv = _escrever_csv(tmp_path / "sem_uf.csv", colunas, [["5"] * len(colunas)])
    destino = tmp_path / "casos.parquet"

    with pytest.raises(duckdb.Error, match="SG_UF"):
        csv_para_parquet(csv, destino)

    assert not destino.exists()


def test_csv_fora_de_utf8_levanta_erro(tmp_path):
    csv = _escrever_csv(
        tmp_path / "latin1.csv", [*COLUNAS_NECESSARIAS, "ID_MUNICIP"],
        [["5"] * len(COLUNAS_NECESSARIAS) + ["SÃO PAULO"]], codificacao="latin-1",
    )
    destino = tmp_path / "casos.parquet"

    with pytest.raises(duckdb.Error, match="(?i)utf-8|unicode|encod"):
        csv_para_parquet(csv, destino)

    assert not destino.exists()


def test_escrita_atomica_nao_deixa_arquivo_parcial_nem_estraga_o_existente(tmp_path):
    destino = tmp_path / "ano=2020" / "casos.parquet"
    csv_para_parquet(FIXTURE_2020, destino)
    assert [p.name for p in destino.parent.iterdir()] == ["casos.parquet"]  # sem .parcial no sucesso

    original = destino.read_bytes()
    ruim = _escrever_csv(tmp_path / "ruim.csv", ["SO_UMA_COLUNA"], [["1"]])
    with pytest.raises(duckdb.Error):
        csv_para_parquet(ruim, destino)

    assert destino.read_bytes() == original  # o Parquet bom segue intacto
    assert [p.name for p in destino.parent.iterdir()] == ["casos.parquet"]  # e nada sobrou da falha


def test_conexao_da_conversao_sem_barra_de_progresso(tmp_path, monkeypatch):
    comandos = []
    conectar = duckdb.connect

    class Registro:
        def __init__(self):
            self._con = conectar()

        def execute(self, consulta, *args):
            comandos.append(consulta)
            return self._con.execute(consulta, *args)

        def close(self):
            self._con.close()

    monkeypatch.setattr(duckdb, "connect", Registro)

    csv_para_parquet(FIXTURE_2020, tmp_path / "casos.parquet")

    assert "SET enable_progress_bar = false" in comandos
