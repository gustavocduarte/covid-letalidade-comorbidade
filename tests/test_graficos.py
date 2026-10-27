"""Figuras do dashboard: o que cada gráfico mostra, sem abrir a tela."""

import pandas as pd
import pytest

from config import (
    CAMINHO_AGREGADO,
    COR_COM_COMORBIDADE,
    COR_POSITIVO,
    COR_SEM_COMORBIDADE,
    COR_TEXTO_SECUNDARIO,
    LIMITE_AMOSTRA_PEQUENA,
)
from graficos import OPACIDADE_AMOSTRA_PEQUENA, figura_dumbbell, figura_por_ano
from indicadores import preparar_agregado


def _agregado() -> pd.DataFrame:
    return preparar_agregado(pd.DataFrame({
        "comorbidade": ["RENAL", "ASMA", "SIND_DOWN", "OBESIDADE"],
        "casos_com": [78513, 40000, LIMITE_AMOSTRA_PEQUENA - 1, 30000],
        "casos_sem": [767370, 800000, 819268, 810000],
        "taxa_letalidade_com": [0.5332, 0.271, 0.379, 0.39],
        "taxa_letalidade_sem": [0.3692, 0.383, 0.379, 0.377],
    }))


def test_dumbbell_tem_ligacao_e_dois_grupos_na_ordem_do_maior_risco():
    figura = figura_dumbbell(_agregado())

    ligacao, sem, com = figura.data
    ordem = ["Doença Renal Crônica", "Obesidade", "Síndrome de Down", "Asma"]
    assert list(com.y) == ordem and list(sem.y) == ordem
    assert list(com.x) == pytest.approx([53.32, 39.0, 37.9, 27.1])
    assert list(sem.x) == pytest.approx([36.92, 37.7, 37.9, 38.3])
    assert sem.marker.color == COR_SEM_COMORBIDADE and com.marker.color == COR_COM_COMORBIDADE
    # cada linha vira um segmento sem -> com, separado do próximo por um vazio
    assert list(ligacao.x[:2]) == pytest.approx([36.92, 53.32]) and ligacao.x[2] is None
    assert len(ligacao.x) == 3 * len(ordem)


def test_dumbbell_mostra_a_diferenca_em_pontos_com_a_cor_da_faixa():
    figura = figura_dumbbell(_agregado())

    textos = {a.y: (a.text, a.font.color) for a in figura.layout.annotations}
    assert textos["Doença Renal Crônica"] == ("+16,4 p.p.", COR_COM_COMORBIDADE)
    assert textos["Obesidade"] == ("+1,3 p.p.", COR_TEXTO_SECUNDARIO)  # dentro da faixa neutra
    assert textos["Síndrome de Down"] == ("0,0 p.p.", COR_TEXTO_SECUNDARIO)
    assert textos["Asma"] == ("-11,2 p.p.", COR_POSITIVO)


def test_dumbbell_destaca_amostra_pequena_so_no_ponto_com():
    com = figura_dumbbell(_agregado()).data[2]

    opacidades = dict(zip(com.y, com.marker.opacity, strict=True))
    assert opacidades["Síndrome de Down"] == OPACIDADE_AMOSTRA_PEQUENA
    assert opacidades["Doença Renal Crônica"] == 1
    assert dict(zip(com.y, com.customdata, strict=True))["Síndrome de Down"].endswith("(amostra pequena)")


def test_dumbbell_eixo_cobre_todos_os_pontos_e_o_fundo_e_transparente():
    figura = figura_dumbbell(_agregado())

    minimo, maximo = figura.layout.xaxis.range
    assert minimo < 27.1 and maximo > 53.32
    assert figura.layout.yaxis.autorange == "reversed"  # a primeira linha fica no topo
    assert figura.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert not figura.layout.showlegend


def test_dumbbell_com_o_agregado_versionado_tem_onze_linhas_e_a_renal_no_topo():
    figura = figura_dumbbell(preparar_agregado(pd.read_csv(CAMINHO_AGREGADO)))

    assert len(figura.data[2].y) == 11
    assert figura.data[2].y[0] == "Doença Renal Crônica"


def _todos_anos() -> pd.DataFrame:
    return pd.DataFrame({
        "ano": [2020, 2021, 2022, 2020],
        "ano_completo": [True, True, False, True],
        "comorbidade": ["RENAL", "RENAL", "RENAL", "ASMA"],
        "casos_com": [28296, 30000, 1200, 10],
        "taxa_letalidade_com": [0.5707, 0.55, 0.40, 0.2],
    })


def test_figura_por_ano_tem_uma_barra_por_ano_e_hachura_o_ano_parcial():
    figura = figura_por_ano(_todos_anos(), "RENAL")

    barras = figura.data[0]
    assert list(barras.x) == ["2020", "2021", "2022"]
    assert list(barras.y) == pytest.approx([57.07, 55.0, 40.0])
    assert list(barras.marker.opacity) == [1, 1, 0.45]
    assert list(barras.marker.pattern.shape) == ["", "", "/"]
    assert barras.customdata[2] == "1.200 casos (ano parcial)" and barras.customdata[0] == "28.296 casos"


def test_figura_por_ano_so_da_comorbidade_pedida_e_comeca_do_zero():
    figura = figura_por_ano(_todos_anos(), "ASMA")

    assert list(figura.data[0].x) == ["2020"]
    assert figura.layout.yaxis.range[0] == 0 and figura.layout.yaxis.range[1] > 20
    assert figura.layout.paper_bgcolor == "rgba(0,0,0,0)"
