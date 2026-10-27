"""Linha de comando: interpretação de --anos, repasse das opções e códigos de saída."""

import argparse

import pandas as pd
import pytest

import cli
import geo
import load
import pipeline


@pytest.mark.parametrize(("tokens", "esperado"), [
    (["2024"], [2024]),
    (["2022-2024"], [2022, 2023, 2024]),
    (["2026", "2020", "2021-2022", "2022"], [2020, 2021, 2022, 2026]),
])
def test_interpreta_anos_e_intervalos(tokens, esperado):
    assert cli.interpretar_anos(tokens) == esperado


@pytest.mark.parametrize("token", ["abc", "2020-", "2020-abc", ""])
def test_ano_mal_escrito_e_erro(token):
    with pytest.raises(argparse.ArgumentTypeError, match="inválido"):
        cli.interpretar_anos([token])


def test_ano_sem_url_e_erro_e_lista_os_validos():
    with pytest.raises(argparse.ArgumentTypeError, match=r"\[1999\].*2020, 2021"):
        cli.interpretar_anos(["1999"])


@pytest.fixture
def chamadas(monkeypatch):
    """Substitui os passos reais por registros das chamadas."""
    registro = []
    monkeypatch.setattr(pipeline, "executar_pipeline", lambda anos, **opcoes: registro.append(("pipeline", anos, opcoes)))
    monkeypatch.setattr(pipeline, "gerar_serie_estado", lambda: registro.append(("serie-estado",)))
    monkeypatch.setattr(geo, "baixar_geojson", lambda: registro.append(("geo",)))
    return registro


def test_pipeline_sem_opcoes_processa_todos_os_anos(chamadas):
    assert cli.main(["pipeline"]) == 0
    assert chamadas == [("pipeline", None, {"forcar": False, "rebaixar": False})]


def test_pipeline_repassa_anos_e_opcoes(chamadas):
    assert cli.main(["pipeline", "--anos", "2021-2022", "2026", "--forcar", "--rebaixar"]) == 0
    assert chamadas == [("pipeline", [2021, 2022, 2026], {"forcar": True, "rebaixar": True})]


def test_ano_desconhecido_e_uso_incorreto_com_saida_2(chamadas, capsys):
    with pytest.raises(SystemExit) as saida:
        cli.main(["pipeline", "--anos", "1999"])

    assert saida.value.code == 2
    assert "Anos válidos" in capsys.readouterr().err
    assert chamadas == []


def test_sem_subcomando_e_uso_incorreto(chamadas):
    with pytest.raises(SystemExit) as saida:
        cli.main([])
    assert saida.value.code == 2


def test_geo_e_serie_estado_chamam_o_passo_certo(chamadas):
    assert cli.main(["geo"]) == 0
    assert cli.main(["serie-estado"]) == 0
    assert chamadas == [("geo",), ("serie-estado",)]


def test_tudo_baixa_o_geojson_so_se_faltar(chamadas, tmp_path, monkeypatch):
    existente = tmp_path / "brasil.geojson"
    monkeypatch.setattr(cli, "CAMINHO_GEOJSON", existente)

    assert cli.main(["tudo", "--anos", "2020"]) == 0
    existente.write_text("{}", encoding="utf-8")
    assert cli.main(["tudo"]) == 0

    assert [c[0] for c in chamadas] == ["geo", "pipeline", "pipeline"]
    assert chamadas[1][1] == [2020]


def test_validacao_reprovada_sai_com_1_e_mensagem_no_stderr(monkeypatch, capsys):
    def reprovar(*_a, **_k):
        raise cli.ErroDeValidacao([cli_achado()])

    monkeypatch.setattr(pipeline, "executar_pipeline", reprovar)

    assert cli.main(["pipeline"]) == 1
    assert "Validação falhou" in capsys.readouterr().err


def cli_achado():
    from validacao import ERRO, Achado

    return Achado(ERRO, "DATA_INVALIDA", 2020, 1, "2020: datas ruins")


def test_parquets_faltando_sai_com_3_e_diz_o_comando(monkeypatch, capsys):
    def faltar(*_a, **_k):
        raise pipeline.ParquetsFaltando([2020, 2021])

    monkeypatch.setattr(pipeline, "executar_pipeline", faltar)

    assert cli.main(["pipeline", "--anos", "2026"]) == 3
    assert "python src/cli.py pipeline --anos 2020 2021" in capsys.readouterr().err


def _apontar_para_amostra(monkeypatch, pasta_parquets, processed):
    monkeypatch.setattr(pipeline, "URLS_SRAG", {2020: "x", 2021: "y"})
    monkeypatch.setattr(pipeline, "PASTA_DETALHADO", pasta_parquets)
    monkeypatch.setattr(load, "PROCESSED_DIR", processed)


def test_serie_estado_regrava_so_a_serie_a_partir_dos_parquets(monkeypatch, pasta_parquets, tmp_path):
    _apontar_para_amostra(monkeypatch, pasta_parquets, tmp_path / "processed")

    assert cli.main(["serie-estado"]) == 0

    assert [p.name for p in (tmp_path / "processed").iterdir()] == ["casos_covid_por_semana_estado.csv"]
    serie = pd.read_csv(tmp_path / "processed" / "casos_covid_por_semana_estado.csv")
    assert serie["casos"].sum() == 17  # mesma soma do e2e do pipeline sobre a amostra


def test_serie_estado_sem_parquet_sai_com_3_e_nao_grava(monkeypatch, tmp_path, capsys):
    _apontar_para_amostra(monkeypatch, tmp_path / "vazia", tmp_path / "processed")

    assert cli.main(["serie-estado"]) == 3
    assert "Faltam os Parquets dos anos: 2020 2021" in capsys.readouterr().err
    assert not (tmp_path / "processed").exists()
