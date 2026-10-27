"""Séries semanais em grade completa: semanas sem casos entre duas com casos saem com casos = 0."""

import pandas as pd
import pytest

from config import COMORBIDADES, UFS_VALIDAS
from consultas import abrir_casos, serie_semanal_casos, serie_semanal_por_comorbidade, serie_semanal_por_estado
from indicadores_tempo import resumo_por_estado

# Segundas-feiras de 07/06 a 12/07/2021: casos só na primeira e na última, com 4 semanas vazias no meio.
SEMANAS = list(pd.date_range("2021-06-07", "2021-07-12", freq="7D"))


@pytest.fixture
def con(parquet_de_casos):
    parquet_de_casos(2021, [
        {"DT_SIN_PRI": "2021-06-10T00:00:00.000Z", "SG_UF": "SP"},
        {"DT_SIN_PRI": "2021-06-11T00:00:00.000Z", "SG_UF": "SP"},
        {"DT_SIN_PRI": "2021-06-12T00:00:00.000Z", "SG_UF": "SP"},
        {"DT_SIN_PRI": "2021-06-10T00:00:00.000Z", "SG_UF": "AP"},
        {"DT_SIN_PRI": "2021-07-14T00:00:00.000Z", "SG_UF": "SP"},
    ])
    with abrir_casos(parquet_de_casos.pasta, anos=[2021]) as conexao:
        yield conexao


def _por(serie, chave, valor):
    sub = serie[serie[chave] == valor]
    assert list(sub["semana"]) == SEMANAS  # nenhuma semana faltando, em ordem
    return list(sub["casos"])


def test_serie_nacional_traz_as_semanas_vazias_com_zero(con):
    serie = serie_semanal_casos(con)

    assert list(serie["semana"]) == SEMANAS
    assert list(serie["casos"]) == [4, 0, 0, 0, 0, 1]


def test_serie_por_estado_traz_toda_semana_para_as_27_ufs(con):
    serie = serie_semanal_por_estado(con)

    assert len(serie) == len(SEMANAS) * len(UFS_VALIDAS)
    assert _por(serie, "sigla", "SP") == [3, 0, 0, 0, 0, 1]
    assert _por(serie, "sigla", "AP") == [1, 0, 0, 0, 0, 0]
    assert _por(serie, "sigla", "AC") == [0] * 6  # UF sem nenhum caso também tem as linhas
    assert serie["casos"].sum() == 5


def test_serie_por_comorbidade_traz_toda_semana_para_as_11_comorbidades(con):
    serie = serie_semanal_por_comorbidade(con)

    assert len(serie) == len(SEMANAS) * len(COMORBIDADES)
    assert _por(serie, "comorbidade", "DIABETES") == [4, 0, 0, 0, 0, 1]
    assert _por(serie, "comorbidade", "ASMA") == [0] * 6
    assert serie["casos"].sum() == 5


def test_cauda_conta_as_semanas_vazias_depois_do_pico(con):
    nomes = {uf: uf for uf in UFS_VALIDAS}

    resumo = resumo_por_estado(serie_semanal_por_estado(con), nomes).set_index("sigla")

    # SP: pico de 3 casos em 07/06; na semana seguinte (zero, abaixo de 10% do pico) a cauda termina.
    assert resumo.loc["SP", "semanas_ate_cauda"] == 1
    assert resumo.loc["AP", "semanas_ate_cauda"] == 1
    assert resumo.loc["AC", "semana_pico"] == SEMANAS[0]  # sem casos: o pico é a primeira semana, com zero
