"""Teste de ponta a ponta do pipeline sobre uma amostra sintética do SIVEP-Gripe.

Os valores esperados foram calculados à mão a partir de tests/fixtures/ (2 anos, com casos
de borda: EVOLUCAO 1/2/3/9/vazio, CLASSI_FIN != 5, UF inválida ou vazia, data inválida ou vazia).
"""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

import load
import pipeline

FIXTURES = Path(__file__).resolve().parent / "fixtures"
URLS_SINTETICAS = {
    2020: "https://exemplo.invalid/SRAG/2020/INFLUD20-sintetico.csv",
    2021: "https://exemplo.invalid/SRAG/2021/INFLUD21-sintetico.csv",
}


@pytest.fixture(scope="module")
def pasta_detalhado(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("detalhado")


@pytest.fixture(scope="module")
def saidas(tmp_path_factory, pasta_detalhado) -> Path:
    mp = pytest.MonkeyPatch()
    destino = tmp_path_factory.mktemp("processed")

    def sem_rede(*_args, **_kwargs):
        raise AssertionError("o pipeline tentou baixar um arquivo")

    mp.setattr(pipeline, "URLS_SRAG", URLS_SINTETICAS)
    mp.setattr(pipeline, "PASTA_RAW", FIXTURES)
    mp.setattr(pipeline, "baixar_arquivo", sem_rede)
    mp.setattr(pipeline, "ANO_ATUAL", 2021)
    mp.setattr(pipeline, "PASTA_DETALHADO", pasta_detalhado)
    mp.setattr(load, "PROCESSED_DIR", destino)
    try:
        pipeline.executar_pipeline()
    finally:
        mp.undo()
    return destino


def _linha(df: pd.DataFrame, **filtro) -> pd.Series:
    mascara = pd.Series(True, index=df.index)
    for coluna, valor in filtro.items():
        mascara &= df[coluna] == valor
    assert mascara.sum() == 1, f"esperava 1 linha para {filtro}, vieram {mascara.sum()}"
    return df[mascara].iloc[0]


def test_gera_todos_os_arquivos(saidas):
    esperados = {
        "letalidade_por_comorbidade_todos_anos.csv", "letalidade_por_comorbidade_agregado.csv",
        "casos_covid_por_semana.csv", "casos_covid_semanal_por_comorbidade.csv",
        "letalidade_por_estado_agregado.csv", "casos_covid_por_semana_estado.csv",
    }
    assert {p.name for p in saidas.iterdir()} == esperados


def test_todos_anos_tem_uma_linha_por_ano_e_comorbidade(saidas):
    df = pd.read_csv(saidas / "letalidade_por_comorbidade_todos_anos.csv")
    assert len(df) == 2 * 11
    assert set(df.loc[df["ano"] == 2020, "ano_completo"]) == {True}
    assert set(df.loc[df["ano"] == 2021, "ano_completo"]) == {False}


def test_letalidade_por_comorbidade_por_ano(saidas):
    df = pd.read_csv(saidas / "letalidade_por_comorbidade_todos_anos.csv")

    # 2020, diabetes: com = linhas 1,2,5,6,10,12 (óbitos 3, cura 1; 3 e 9 não contam no desfecho)
    d = _linha(df, ano=2020, comorbidade="DIABETES")
    assert (d.casos_com, d.obitos_com, d.desfecho_conhecido_com) == (6, 3, 4)
    assert d.taxa_letalidade_com == pytest.approx(3 / 4)
    # sem = linhas 3,4,7,8,11,13 (o diabetes "ignorado" = 9 da linha 9 fica fora dos dois grupos)
    assert (d.casos_sem, d.obitos_sem, d.desfecho_conhecido_sem) == (6, 2, 5)
    assert d.taxa_letalidade_sem == pytest.approx(2 / 5)

    # Síndrome de Down 2020: 1 caso, mas com EVOLUCAO 3 (sem desfecho conhecido) -> taxa indefinida
    d = _linha(df, ano=2020, comorbidade="SIND_DOWN")
    assert (d.casos_com, d.obitos_com, d.desfecho_conhecido_com) == (1, 0, 0)
    assert pd.isna(d.taxa_letalidade_com)

    # comorbidade nunca preenchida: tudo zero e taxas indefinidas, sem erro de divisão por zero
    d = _linha(df, ano=2021, comorbidade="HEMATOLOGI")
    assert (d.casos_com, d.casos_sem, d.desfecho_conhecido_com, d.desfecho_conhecido_sem) == (0, 0, 0, 0)
    assert pd.isna(d.taxa_letalidade_com) and pd.isna(d.taxa_letalidade_sem)

    d = _linha(df, ano=2021, comorbidade="DIABETES")
    assert (d.casos_com, d.obitos_com, d.desfecho_conhecido_com) == (4, 3, 3)
    assert (d.casos_sem, d.obitos_sem, d.desfecho_conhecido_sem) == (3, 1, 3)


def test_agregado_soma_antes_de_dividir(saidas):
    df = pd.read_csv(saidas / "letalidade_por_comorbidade_agregado.csv")
    assert len(df) == 11

    d = _linha(df, comorbidade="DIABETES")
    assert (d.casos_com, d.obitos_com, d.desfecho_conhecido_com) == (10, 6, 7)
    assert d.taxa_letalidade_com == pytest.approx(6 / 7)
    assert (d.casos_sem, d.obitos_sem, d.desfecho_conhecido_sem) == (9, 3, 8)
    assert d.taxa_letalidade_sem == pytest.approx(3 / 8)

    d = _linha(df, comorbidade="OBESIDADE")
    assert (d.casos_com, d.obitos_com, d.desfecho_conhecido_com) == (4, 3, 4)
    assert (d.casos_sem, d.obitos_sem, d.desfecho_conhecido_sem) == (4, 2, 3)

    d = _linha(df, comorbidade="SIND_DOWN")
    assert (d.casos_com, d.obitos_com, d.desfecho_conhecido_com) == (3, 1, 2)
    assert d.taxa_letalidade_com == pytest.approx(1 / 2)
    assert pd.isna(d.taxa_letalidade_sem)


def test_serie_semanal_junta_a_virada_do_ano_e_ignora_data_invalida(saidas):
    df = pd.read_csv(saidas / "casos_covid_por_semana.csv")
    esperado = {
        "2020-03-02": 2, "2020-03-09": 5, "2020-03-16": 4,
        "2020-12-28": 2,  # 30/dez/2020 (arquivo de 2020) + 01/jan/2021 (arquivo de 2021)
        "2021-01-04": 5, "2021-01-11": 2,
    }
    assert dict(zip(df["semana"], df["casos"], strict=True)) == esperado
    assert df["casos"].sum() == 20  # 22 casos de COVID menos 2 sem data válida


def test_serie_semanal_por_comorbidade(saidas):
    df = pd.read_csv(saidas / "casos_covid_semanal_por_comorbidade.csv")
    assert len(df) == 12

    def serie(comorbidade):
        sub = df[df["comorbidade"] == comorbidade]
        return dict(zip(sub["semana"], sub["casos"], strict=True))

    assert serie("DIABETES") == {"2020-03-02": 2, "2020-03-09": 2, "2020-03-16": 1,
                                 "2021-01-04": 3, "2021-01-11": 1}
    assert serie("OBESIDADE") == {"2020-03-09": 1, "2020-03-16": 1, "2021-01-04": 2}
    assert serie("CARDIOPATI") == {"2020-03-02": 1, "2020-03-09": 1}
    assert serie("SIND_DOWN") == {"2020-12-28": 2, "2021-01-04": 1}
    assert serie("ASMA") == {}


def test_serie_semanal_por_estado_ignora_data_invalida_e_uf_vazia(saidas):
    df = pd.read_csv(saidas / "casos_covid_por_semana_estado.csv")
    assert len(df) == 12
    assert df["casos"].sum() == 19  # 20 com data válida, menos 1 sem UF
    assert _linha(df, semana="2020-12-28", sigla="SP").casos == 2  # a virada do ano soma os dois arquivos


# Decisão para a etapa de validação: casos sem UF continuam fora da tabela por estado; o pipeline
# registra a contagem e o dashboard avisa ("N casos sem estado informado não entram no mapa").
# Nos dados reais só há UF vazia (333 casos), não inválida; revisar este teste nessa etapa.
@pytest.mark.xfail(
    strict=True,
    reason="UF inválida ou vazia não é validada nem filtrada; resolver na validação de dados",
)
def test_letalidade_por_estado_so_com_ufs_validas(saidas):
    df = pd.read_csv(saidas / "letalidade_por_estado_agregado.csv")

    esperado = {"SP": (7, 3, 6), "RJ": (6, 3, 5), "MG": (3, 1, 1), "BA": (3, 1, 2)}
    for sigla, (casos, obitos, desfecho) in esperado.items():
        linha = _linha(df, sigla=sigla)
        assert (linha.casos, linha.obitos, linha.desfecho_conhecido) == (casos, obitos, desfecho)
    # UF inválida ("XX", "ZZ") ou vazia não deve virar um "estado" na tabela
    assert set(df["sigla"]) == set(esperado)


def test_parquets_guardam_so_covid_sem_classi_fin(saidas, pasta_detalhado):
    arquivos = sorted(p.relative_to(pasta_detalhado).as_posix() for p in pasta_detalhado.rglob("*.parquet"))
    assert arquivos == ["ano=2020/casos.parquet", "ano=2021/casos.parquet"]
    con = duckdb.connect()
    glob = (pasta_detalhado / "ano=*" / "casos.parquet").as_posix()
    df = con.execute(f"SELECT * FROM read_parquet('{glob}', hive_partitioning=true)").df()
    assert len(df) == 22  # 14 casos de COVID em 2020 + 8 em 2021
    assert "CLASSI_FIN" not in df.columns
    assert {"DT_SIN_PRI", "SG_UF", "EVOLUCAO", "ano", "DIABETES"} <= set(df.columns)
    assert df["ano"].value_counts().to_dict() == {2020: 14, 2021: 8}
