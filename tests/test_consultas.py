"""Agregações em SQL x versão pandas, sobre a amostra sintética (mesmos números e mesma ordem)."""

import pandas as pd
import pytest

from consultas import (
    abrir_casos,
    letalidade_por_comorbidade_agregado,
    letalidade_por_comorbidade_por_ano,
    letalidade_por_estado_agregado,
    letalidade_por_estado_por_ano,
)
from transform import (
    agregar_estados_todos_anos,
    agregar_todos_anos,
    carregar_casos_covid,
    letalidade_por_comorbidade,
    letalidade_por_estado,
)


@pytest.fixture(scope="module")
def con(pasta_parquets):
    with abrir_casos(pasta_parquets) as conexao:
        yield conexao


@pytest.fixture(scope="module")
def casos_pandas(csvs_sinteticos) -> dict[int, pd.DataFrame]:
    return {ano: carregar_casos_covid(csv) for ano, csv in csvs_sinteticos.items()}


@pytest.fixture(scope="module")
def tabelas_pandas(csvs_sinteticos) -> dict[int, pd.DataFrame]:
    return {ano: letalidade_por_comorbidade(carregar_casos_covid(csv)) for ano, csv in csvs_sinteticos.items()}


def test_letalidade_por_comorbidade_por_ano_igual_ao_pandas(con, tabelas_pandas, assert_iguais):
    esperado = pd.concat(
        [tabela.assign(ano=ano) for ano, tabela in tabelas_pandas.items()], ignore_index=True,
    )
    esperado = esperado[["ano", *[c for c in esperado.columns if c != "ano"]]]

    # inclui os empates de taxa indefinida (comorbidades nunca preenchidas): a ordem também é conferida
    assert_iguais(letalidade_por_comorbidade_por_ano(con), esperado)


def test_letalidade_por_comorbidade_agregado_igual_ao_pandas(con, tabelas_pandas, assert_iguais):
    esperado = agregar_todos_anos(list(tabelas_pandas.values()))

    assert_iguais(letalidade_por_comorbidade_agregado(con), esperado)


def test_letalidade_por_comorbidade_valores_calculados_a_mao(con):
    por_ano = letalidade_por_comorbidade_por_ano(con).set_index(["ano", "comorbidade"])

    # 2020, diabetes: com = 6 casos (3 óbitos, 1 cura); sem = 6 casos (2 óbitos, 3 curas)
    diabetes = por_ano.loc[(2020, "DIABETES")]
    assert (diabetes.casos_com, diabetes.obitos_com, diabetes.desfecho_conhecido_com) == (6, 3, 4)
    assert (diabetes.casos_sem, diabetes.obitos_sem, diabetes.desfecho_conhecido_sem) == (6, 2, 5)
    assert diabetes.taxa_letalidade_com == pytest.approx(3 / 4)
    # Comorbidade nunca preenchida: linha com zeros e taxas indefinidas, sem divisão por zero
    hematologica = por_ano.loc[(2021, "HEMATOLOGI")]
    assert hematologica.casos_com == 0
    assert pd.isna(hematologica.taxa_letalidade_com) and pd.isna(hematologica.taxa_letalidade_sem)
    assert len(por_ano) == 2 * 11


def test_letalidade_por_estado_por_ano_igual_ao_pandas(con, casos_pandas, assert_iguais):
    esperado = pd.concat(
        [letalidade_por_estado(covid).assign(ano=ano) for ano, covid in casos_pandas.items()], ignore_index=True,
    )
    esperado = esperado[["ano", *[c for c in esperado.columns if c != "ano"]]]

    assert_iguais(letalidade_por_estado_por_ano(con), esperado)


def test_letalidade_por_estado_agregado_igual_ao_pandas(con, casos_pandas, assert_iguais):
    esperado = agregar_estados_todos_anos([letalidade_por_estado(covid) for covid in casos_pandas.values()])

    assert_iguais(letalidade_por_estado_agregado(con), esperado)


def test_letalidade_por_estado_valores_calculados_a_mao(con):
    agregado = letalidade_por_estado_agregado(con)

    # (casos, óbitos, desfechos conhecidos); o caso sem UF (2020, linha 11) fica de fora.
    esperado = {
        "MG": (3, 1, 1), "XX": (1, 1, 1), "RJ": (6, 3, 5), "BA": (3, 1, 2), "SP": (7, 3, 6), "ZZ": (1, 0, 1),
    }
    # taxa decrescente; empates (MG/XX = 1,0 e BA/SP = 0,5) em ordem alfabética
    assert list(agregado["sigla"]) == list(esperado)
    for linha in agregado.itertuples():
        assert (linha.casos, linha.obitos, linha.desfecho_conhecido) == esperado[linha.sigla]
