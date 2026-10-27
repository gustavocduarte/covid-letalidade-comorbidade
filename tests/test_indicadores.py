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
    COLUNAS_TABELA,
    MARCA_AMOSTRA_PEQUENA,
    achados_comorbidades,
    celulas_da_comorbidade,
    classe_da_diferenca,
    cor_da_celula_de_diferenca,
    juntar_nomes,
    kpis_comorbidades,
    maior_risco,
    preparar_agregado,
    tabela_para_exibir,
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


def test_achados_com_os_dados_versionados_descrevem_sem_afirmar_causa():
    agregado = preparar_agregado(pd.read_csv(CAMINHO_AGREGADO))

    renal, abaixo, atencao = achados_comorbidades(agregado)

    assert renal.destaque == "Doença Renal Crônica"
    assert "53% contra 37%" in renal.texto and "1,4 vez maior" in renal.texto
    assert "Doença Hepática Crônica e Doença Neurológica Crônica vêm logo atrás" in renal.texto
    assert abaixo.destaque == "Asma"
    assert "pode refletir" in abaixo.texto and "não indica proteção" in abaixo.texto
    assert "Síndrome de Down (amostra pequena)" in abaixo.texto  # dentro da faixa neutra e com amostra pequena
    assert atencao.atencao and atencao.destaque == "Atenção:" and "não é de pessoas saudáveis" in atencao.texto


def test_achados_sem_comorbidade_abaixo_da_taxa_de_quem_nao_tem_omitem_o_cartao():
    df = preparar_agregado(pd.DataFrame({
        "comorbidade": ["RENAL", "HEPATICA", "ASMA"], "casos_com": [50000] * 3, "casos_sem": [700000] * 3,
        "taxa_letalidade_com": [0.5, 0.45, 0.42], "taxa_letalidade_sem": [0.4, 0.4, 0.4],
    }))

    achados = achados_comorbidades(df)

    assert [a.destaque for a in achados] == ["Doença Renal Crônica", "Atenção:"]


def test_achados_mais_de_uma_abaixo_usam_o_plural():
    df = preparar_agregado(pd.DataFrame({
        "comorbidade": ["RENAL", "ASMA", "OBESIDADE"], "casos_com": [50000] * 3, "casos_sem": [700000] * 3,
        "taxa_letalidade_com": [0.5, 0.30, 0.31], "taxa_letalidade_sem": [0.4, 0.4, 0.4],
    }))

    abaixo = achados_comorbidades(df)[1]

    assert abaixo.destaque == "Obesidade e Asma" and abaixo.texto.startswith(" aparecem com letalidade menor")


def test_juntar_nomes():
    assert juntar_nomes([]) == "" and juntar_nomes(["A"]) == "A"
    assert juntar_nomes(["A", "B"]) == "A e B" and juntar_nomes(["A", "B", "C"]) == "A, B e C"


def test_tabela_para_exibir_tem_numeros_na_ordem_das_colunas_e_marca_a_amostra_pequena():
    tabela = tabela_para_exibir(preparar_agregado(_agregado_pequeno()))

    assert list(tabela.columns) == list(COLUNAS_TABELA)
    assert list(tabela["nome"]) == ["Doença Renal Crônica", "Síndrome de Down", "Asma"]
    assert tabela["taxa_com"].tolist() == pytest.approx([50.0, 40.0, 25.0])
    assert tabela["diferenca_pp"].tolist() == pytest.approx([10.0, 0.0, -10.0])
    assert pd.api.types.is_numeric_dtype(tabela["casos_com"]) and pd.api.types.is_numeric_dtype(tabela["taxa_sem"])
    assert tabela["amostra"].tolist() == ["", MARCA_AMOSTRA_PEQUENA, ""]


def test_cor_da_celula_de_diferenca_segue_a_faixa():
    assert cor_da_celula_de_diferenca(16.4) == f"color: {COR_COM_COMORBIDADE}"
    assert cor_da_celula_de_diferenca(FAIXA_NEUTRA_PP - 0.1) == f"color: {COR_TEXTO_SECUNDARIO}"
    assert cor_da_celula_de_diferenca(-11.2) == f"color: {COR_POSITIVO}"
