"""Teste de ponta a ponta do pipeline sobre uma amostra sintética do SIVEP-Gripe.

Os valores esperados foram calculados à mão a partir de tests/fixtures/ (2 anos, com casos
de borda: EVOLUCAO 1/2/3/9/vazio, CLASSI_FIN != 5, UF inválida ou vazia, data inválida ou vazia).
"""

import json
import os
from pathlib import Path

import duckdb
import pandas as pd
import pytest

import cli
import load
import pipeline
import validacao

FIXTURES = Path(__file__).resolve().parent / "fixtures"
URLS_SINTETICAS = {
    2020: "https://exemplo.invalid/SRAG/2020/INFLUD20-sintetico.csv",
    2021: "https://exemplo.invalid/SRAG/2021/INFLUD21-sintetico.csv",
}


@pytest.fixture(scope="module")
def pasta_detalhado(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("detalhado")


def _apontar_pipeline_para_amostra(
    mp: pytest.MonkeyPatch, processed: Path, detalhado: Path, raw: Path = FIXTURES
) -> None:
    def sem_rede(*_args, **_kwargs):
        raise AssertionError("o pipeline tentou baixar um arquivo")

    mp.setattr(pipeline, "URLS_SRAG", URLS_SINTETICAS)
    mp.setattr(pipeline, "PASTA_RAW", raw)
    mp.setattr(pipeline, "baixar_arquivo", sem_rede)
    mp.setattr(pipeline, "ANO_ATUAL", 2021)
    mp.setattr(pipeline, "PASTA_DETALHADO", detalhado)
    mp.setattr(load, "PROCESSED_DIR", processed)


@pytest.fixture(scope="module")
def saidas(tmp_path_factory, pasta_detalhado) -> Path:
    mp = pytest.MonkeyPatch()
    destino = tmp_path_factory.mktemp("processed")
    _apontar_pipeline_para_amostra(mp, destino, pasta_detalhado)
    # A amostra tem datas inválidas de propósito (2 de 14 casos em 2020), acima do limite de erro.
    mp.setattr(validacao, "LIMITE_DATA_INVALIDA", 1.0)
    try:
        assert cli.main(["pipeline"]) == 0
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
        "resumo_geral.csv", "relatorio_qualidade.json",
    }
    assert {p.name for p in saidas.iterdir()} == esperados


def test_resumo_geral_tem_uma_linha_por_ano_com_todos_os_casos(saidas):
    df = pd.read_csv(saidas / "resumo_geral.csv")

    assert list(df["ano"]) == [2020, 2021]
    assert list(df["ano_completo"]) == [True, False]  # o ano atual da amostra é 2021
    assert df["casos"].sum() == 22  # inclui o caso sem UF e os de UF inválida
    assert list(df["desfecho_conhecido"]) == list(df["obitos"] + df["curas"])


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


def _semanas_da_grade() -> list[str]:
    """Segundas-feiras seguidas da primeira (02/03/2020) à última (11/01/2021) semana com casos da amostra."""
    return list(pd.date_range("2020-03-02", "2021-01-11", freq="7D").strftime("%Y-%m-%d"))


def test_serie_semanal_junta_a_virada_do_ano_e_ignora_data_invalida(saidas):
    df = pd.read_csv(saidas / "casos_covid_por_semana.csv")
    esperado = {
        "2020-03-02": 2, "2020-03-09": 5, "2020-03-16": 4,
        "2020-12-28": 2,  # 30/dez/2020 (arquivo de 2020) + 01/jan/2021 (arquivo de 2021)
        "2021-01-04": 5, "2021-01-11": 2,
    }
    com_casos = df[df["casos"] > 0]
    assert dict(zip(com_casos["semana"], com_casos["casos"], strict=True)) == esperado
    assert df["casos"].sum() == 20  # 22 casos de COVID menos 2 sem data válida
    assert list(df["semana"]) == _semanas_da_grade()  # sem lacunas: as demais semanas têm casos = 0


def test_serie_semanal_por_comorbidade(saidas):
    df = pd.read_csv(saidas / "casos_covid_semanal_por_comorbidade.csv")
    assert df["casos"].sum() == 18 and len(df[df["casos"] > 0]) == 12 and len(df) == 11 * len(_semanas_da_grade())  # grade completa, soma igual

    def serie(comorbidade):
        sub = df[(df["comorbidade"] == comorbidade) & (df["casos"] > 0)]
        return dict(zip(sub["semana"], sub["casos"], strict=True))

    assert serie("DIABETES") == {"2020-03-02": 2, "2020-03-09": 2, "2020-03-16": 1,
                                 "2021-01-04": 3, "2021-01-11": 1}
    assert serie("OBESIDADE") == {"2020-03-09": 1, "2020-03-16": 1, "2021-01-04": 2}
    assert serie("CARDIOPATI") == {"2020-03-02": 1, "2020-03-09": 1}
    assert serie("SIND_DOWN") == {"2020-12-28": 2, "2021-01-04": 1}
    assert serie("ASMA") == {}  # sem casos: só linhas com casos = 0


def test_serie_semanal_por_estado_ignora_data_invalida_e_uf_vazia(saidas):
    df = pd.read_csv(saidas / "casos_covid_por_semana_estado.csv")
    assert len(df) == 27 * len(_semanas_da_grade())  # grade completa: as demais linhas têm casos = 0
    assert len(df[df["casos"] > 0]) == 10
    assert df["casos"].sum() == 17  # 20 com data válida, menos 1 sem UF e 2 com UF inválida (XX, ZZ)
    assert _linha(df, semana="2020-12-28", sigla="SP").casos == 2  # a virada do ano soma os dois arquivos


# Casos sem UF ou com UF inválida ficam fora da tabela por estado; o relatório conta os dois
# e o dashboard avisa ("N casos sem estado informado não entram no mapa").
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


def test_relatorio_de_qualidade_da_amostra(saidas):
    relatorio = json.loads((saidas / "relatorio_qualidade.json").read_text(encoding="utf-8"))

    assert relatorio["aprovado"] is True  # com o limite de data afrouxado pela fixture
    assert relatorio["totais"]["linhas"] == 22
    assert relatorio["totais"]["sem_uf"] == 1  # o caso sem UF fica fora da tabela por estado
    assert relatorio["anos"]["2020"]["uf_invalida"] == 1 and relatorio["anos"]["2021"]["uf_invalida"] == 1
    assert {a["codigo"] for a in relatorio["achados"]} == {
        "DATA_INVALIDA", "SEM_UF", "UF_INVALIDA", "SEM_DESFECHO_ACIMA_DO_LIMITE",
    }


def test_erro_de_validacao_grava_o_relatorio_e_nenhum_csv(tmp_path, monkeypatch, capsys):
    processed, detalhado = tmp_path / "processed", tmp_path / "detalhado"
    _apontar_pipeline_para_amostra(monkeypatch, processed, detalhado)  # limite padrão: 2 de 14 datas inválidas é erro

    assert cli.main(["pipeline"]) == 1

    assert "DATA_INVALIDA" in capsys.readouterr().err
    assert [p.name for p in processed.iterdir()] == ["relatorio_qualidade.json"]
    relatorio = json.loads((processed / "relatorio_qualidade.json").read_text(encoding="utf-8"))
    assert relatorio["aprovado"] is False
    primeiro = relatorio["achados"][0]
    assert (primeiro["nivel"], primeiro["codigo"], primeiro["ano"]) == ("erro", "DATA_INVALIDA", 2020)


def _atualizar_data(caminho: Path) -> None:
    """Como se o arquivo tivesse sido baixado de novo: mesma coisa, data de modificação mais recente."""
    info = caminho.stat()
    os.utime(caminho, ns=(info.st_atime_ns, info.st_mtime_ns + 10**9))


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Pipeline sobre cópias dos CSVs sintéticos em tmp_path (os dados brutos podem ser alterados)."""
    raw = tmp_path / "raw"
    raw.mkdir()
    for url in URLS_SINTETICAS.values():
        nome = url.split("/")[-1]
        (raw / nome).write_bytes((FIXTURES / nome).read_bytes())
    _apontar_pipeline_para_amostra(monkeypatch, tmp_path / "processed", tmp_path / "detalhado", raw)
    monkeypatch.setattr(validacao, "LIMITE_DATA_INVALIDA", 1.0)
    return raw


def test_primeira_execucao_converte_e_a_segunda_esta_em_dia(ambiente):
    assert pipeline.executar_pipeline() == {2020: pipeline.CONVERTIDO, 2021: pipeline.CONVERTIDO}

    assert pipeline.executar_pipeline() == {2020: pipeline.EM_DIA, 2021: pipeline.EM_DIA}


def test_csv_alterado_reconverte_so_aquele_ano(ambiente):
    pipeline.executar_pipeline()
    csv_2021 = ambiente / "INFLUD21-sintetico.csv"
    _atualizar_data(csv_2021)

    assert pipeline.executar_pipeline() == {2020: pipeline.EM_DIA, 2021: pipeline.CONVERTIDO}


def test_parquet_apagado_e_reconvertido(ambiente, tmp_path):
    pipeline.executar_pipeline()
    (tmp_path / "detalhado" / "ano=2020" / "casos.parquet").unlink()

    assert pipeline.executar_pipeline() == {2020: pipeline.CONVERTIDO, 2021: pipeline.EM_DIA}


def test_estado_ilegivel_reconverte_tudo(ambiente, tmp_path):
    pipeline.executar_pipeline()
    (tmp_path / "detalhado" / "estado.json").write_text("{quebrado", encoding="utf-8")

    assert pipeline.executar_pipeline() == {2020: pipeline.CONVERTIDO, 2021: pipeline.CONVERTIDO}


def test_forcar_reconverte_os_anos_pedidos_sem_baixar(ambiente):
    pipeline.executar_pipeline()

    assert pipeline.executar_pipeline([2021], forcar=True) == {2021: pipeline.CONVERTIDO}
    assert pipeline.executar_pipeline() == {2020: pipeline.EM_DIA, 2021: pipeline.EM_DIA}


def test_rebaixar_baixa_de_novo_e_converte(ambiente, monkeypatch):
    pipeline.executar_pipeline()
    baixados = []

    def baixar_falso(url, pasta):
        baixados.append(url)
        return pasta / url.split("/")[-1]  # o CSV já está na pasta

    monkeypatch.setattr(pipeline, "baixar_arquivo", baixar_falso)

    assert pipeline.executar_pipeline([2020], rebaixar=True) == {2020: pipeline.BAIXADO}
    assert baixados == [URLS_SINTETICAS[2020]]


def test_csv_ausente_e_baixado(ambiente, monkeypatch):
    (ambiente / "INFLUD20-sintetico.csv").rename(ambiente.parent / "guardado.csv")

    def baixar_falso(url, pasta):
        (ambiente.parent / "guardado.csv").rename(pasta / url.split("/")[-1])
        return pasta / url.split("/")[-1]

    monkeypatch.setattr(pipeline, "baixar_arquivo", baixar_falso)

    assert pipeline.executar_pipeline() == {2020: pipeline.BAIXADO, 2021: pipeline.CONVERTIDO}


def test_so_alguns_anos_atualiza_so_eles_mas_as_saidas_cobrem_todos(ambiente, tmp_path):
    pipeline.executar_pipeline()
    csv_2021 = ambiente / "INFLUD21-sintetico.csv"
    _atualizar_data(csv_2021)

    assert pipeline.executar_pipeline([2021]) == {2021: pipeline.CONVERTIDO}

    todos = pd.read_csv(tmp_path / "processed" / "letalidade_por_comorbidade_todos_anos.csv")
    assert sorted(todos["ano"].unique()) == [2020, 2021]


def test_parquet_de_ano_nao_processado_aborta_sem_gravar_csvs(ambiente, tmp_path):
    with pytest.raises(pipeline.ParquetsFaltando) as erro:
        pipeline.executar_pipeline([2021])

    assert erro.value.anos == [2020]
    assert "python src/cli.py pipeline --anos 2020" in str(erro.value)
    assert not (tmp_path / "processed").exists()


def test_ano_sem_url_e_recusado(ambiente):
    with pytest.raises(ValueError, match="1999"):
        pipeline.executar_pipeline([1999])
