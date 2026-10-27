"""Indicadores da tela, calculados dos CSVs versionados e de tabelas pequenas feitas à mão."""

import pandas as pd
import pytest

from config import (
    CAMINHO_AGREGADO,
    CAMINHO_RESUMO_GERAL,
    COR_COM_COMORBIDADE,
    COR_POSITIVO,
    COR_TEXTO_SECUNDARIO,
    FAIXA_NEUTRA_PP,
    LIMITE_AMOSTRA_PEQUENA,
)
from indicadores import (
    celulas_da_comorbidade,
    classe_da_diferenca,
    kpis_comorbidades,
    maior_risco,
    preparar_agregado,
    totais_do_resumo,
)


def _agregado_pequeno() -> pd.DataFrame:
    return pd.DataFrame({
        "comorbidade": ["ASMA", "RENAL", "SIND_DOWN"],
        "casos_com": [20000, 50000, LIMITE_AMOSTRA_PEQUENA - 1],
        "casos_sem": [800000, 760000, 810000],
        "taxa_letalidade_com": [0.25, 0.50, 0.40],
        "taxa_letalidade_sem": [0.35, 0.40, 0.40],
    })


def test_agregado_preparado_vem_do_maior_ao_menor_risco_com_diferenca_razao_e_amostra():
    df = preparar_agregado(_agregado_pequeno())

    assert list(df["comorbidade"]) == ["RENAL", "SIND_DOWN", "ASMA"]
    assert list(df["nome"]) == ["Doença Renal Crônica", "Síndrome de Down", "Asma"]
    assert df["diferenca_pp"].tolist() == pytest.approx([10.0, 0.0, -10.0])
    assert df["razao"].tolist() == pytest.approx([1.25, 1.0, 0.25 / 0.35])
    assert list(df["amostra_pequena"]) == [False, True, False]


def test_amostra_pequena_so_abaixo_do_limite():
    df = pd.DataFrame({
        "comorbidade": ["ASMA", "RENAL"], "casos_com": [LIMITE_AMOSTRA_PEQUENA, LIMITE_AMOSTRA_PEQUENA - 1],
        "taxa_letalidade_com": [0.3, 0.3], "taxa_letalidade_sem": [0.3, 0.3],
    })

    resultado = preparar_agregado(df).set_index("comorbidade")["amostra_pequena"].to_dict()
    assert resultado == {"ASMA": False, "RENAL": True}


@pytest.mark.parametrize(("pontos", "classe"), [
    (16.4, "alta"), (FAIXA_NEUTRA_PP, "alta"), (FAIXA_NEUTRA_PP - 0.01, "neutra"), (0.0, "neutra"),
    (-(FAIXA_NEUTRA_PP - 0.01), "neutra"), (-FAIXA_NEUTRA_PP, "baixa"), (-11.2, "baixa"),
])
def test_faixa_neutra_e_em_modulo(pontos, classe):
    assert classe_da_diferenca(pontos) == classe


def test_totais_do_resumo_somam_os_anos():
    resumo = pd.DataFrame({
        "ano": [2020, 2021], "casos": [100, 50], "obitos": [20, 5], "curas": [60, 35], "desfecho_conhecido": [80, 40],
    })

    totais = totais_do_resumo(resumo)

    assert totais == {
        "casos": 150, "obitos": 25, "desfecho_conhecido": 120, "taxa_letalidade": 25 / 120,
        "primeiro_ano": 2020, "ultimo_ano": 2021,
    }


def test_kpis_com_os_csvs_versionados():
    agregado = preparar_agregado(pd.read_csv(CAMINHO_AGREGADO))
    resumo = pd.read_csv(CAMINHO_RESUMO_GERAL)

    kpis = {k.rotulo: k for k in kpis_comorbidades(agregado, resumo)}

    assert list(kpis) == ["Casos com desfecho", "Letalidade geral", "Maior risco", "Comorbidades analisadas"]
    assert kpis["Casos com desfecho"].valor == "2.146.582"
    assert kpis["Casos com desfecho"].linha == "COVID confirmada, 2020–2026"
    assert kpis["Letalidade geral"].valor == "32,4%"  # 696.478 óbitos ÷ 2.146.582 desfechos
    assert kpis["Maior risco"].valor.endswith(" p.p.") and kpis["Maior risco"].valor.startswith("+")
    assert kpis["Maior risco"].linha.startswith(maior_risco(agregado)["nome"])
    assert kpis["Comorbidades analisadas"].valor == "11"
    assert kpis["Maior risco"].ajuda


def test_maior_risco_e_a_maior_diferenca():
    df = preparar_agregado(_agregado_pequeno())

    assert maior_risco(df)["comorbidade"] == "RENAL"


def test_celulas_da_comorbidade_mostram_com_sem_e_diferenca_com_a_cor_da_faixa():
    df = preparar_agregado(_agregado_pequeno()).set_index("comorbidade", drop=False)

    renal = {c.rotulo: c for c in celulas_da_comorbidade(df.loc["RENAL"])}
    asma = {c.rotulo: c for c in celulas_da_comorbidade(df.loc["ASMA"])}
    down = {c.rotulo: c for c in celulas_da_comorbidade(df.loc["SIND_DOWN"])}

    assert [renal[r].valor for r in ("Com a comorbidade", "Sem a comorbidade", "Diferença")] == ["50,0%", "40,0%", "+10,0 p.p."]
    assert renal["Com a comorbidade"].linha == "50.000 casos"
    assert renal["Diferença"].linha == "1,2 vez maior"
    assert renal["Diferença"].cor == COR_COM_COMORBIDADE
    assert asma["Diferença"].cor == COR_POSITIVO and asma["Diferença"].valor == "-10,0 p.p."
    assert down["Diferença"].cor == COR_TEXTO_SECUNDARIO
