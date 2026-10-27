"""Figuras do dashboard: o que cada gráfico mostra, sem abrir a tela."""

import json

import pandas as pd
import plotly.graph_objects as go
import pytest

from config import (
    CAMINHO_AGREGADO,
    CAMINHO_GEOJSON,
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


def test_dumbbell_rotulos_da_diferenca_ficam_fora_da_area_dos_pontos():
    figura = figura_dumbbell(_agregado())

    assert all(a.xref == "paper" and a.x == 1 and a.xanchor == "left" and a.xshift > 0 for a in figura.layout.annotations)
    assert figura.layout.margin.r >= 90  # espaço para o texto mais largo, "+16,4 p.p."


def test_template_usa_virgula_decimal_e_ponto_nos_milhares():
    from componentes import aplicar_template_grafico

    assert aplicar_template_grafico(go.Figure()).layout.separators == ",."


def test_eixo_de_datas_usa_meses_em_portugues():
    from componentes import aplicar_eixo_de_datas

    figura = aplicar_eixo_de_datas(go.Figure(), pd.Timestamp("2020-02-10"), pd.Timestamp("2026-08-24"))

    assert list(figura.layout.xaxis.ticktext)[:3] == ["jul/20", "jan/21", "jul/21"]
    assert figura.layout.xaxis.tickmode == "array"


def _semanal_e_comorbidades():
    semanas = pd.date_range("2021-01-04", periods=4, freq="7D")
    semanal = pd.DataFrame({"semana": semanas, "casos": [0, 100, 400, 50]})
    por_comorbidade = pd.DataFrame({
        "semana": list(semanas) * 2, "nome": ["Diabetes"] * 4 + ["Cardiovascular"] * 4,
        "casos": [0, 30, 120, 10, 0, 20, 90, 5],
    })
    return semanal, por_comorbidade


def test_serie_semanal_tem_brasil_comorbidades_com_nome_curto_e_marca_da_vacinacao():
    from graficos import ROTULO_VACINACAO, figura_serie_semanal

    semanal, por_comorbidade = _semanal_e_comorbidades()

    figura = figura_serie_semanal(semanal, por_comorbidade, pd.Timestamp("2021-01-17"))

    assert [t.name for t in figura.data] == ["Brasil", "Cardiovascular", "Diabetes"]
    assert list(figura.data[0].y) == [0, 100, 400, 50] and figura.layout.yaxis.type == "linear"
    assert figura.layout.shapes[0].x0 == pd.Timestamp("2021-01-17")
    assert figura.layout.annotations[0].text == ROTULO_VACINACAO


def test_serie_semanal_em_escala_logaritmica_tira_as_semanas_sem_caso_das_comorbidades():
    from graficos import figura_serie_semanal

    semanal, por_comorbidade = _semanal_e_comorbidades()

    figura = figura_serie_semanal(semanal, por_comorbidade, pd.Timestamp("2021-01-17"), "Logarítmica")

    assert figura.layout.yaxis.type == "log"
    assert all(0 not in list(t.y) for t in figura.data[1:])


def _estados():
    from config import CAMINHO_ESTADO, CAMINHO_GEOJSON
    from indicadores_tempo import preparar_estados

    with open(CAMINHO_GEOJSON, encoding="utf-8") as f:
        return preparar_estados(pd.read_csv(CAMINHO_ESTADO), json.load(f))


def test_blocos_tem_um_por_estado_na_posicao_da_grade_com_sigla_e_taxa():
    from config import GRADE_ESTADOS
    from graficos import figura_blocos_estados

    estados = _estados()

    figura = figura_blocos_estados(estados)

    assert len(figura.layout.annotations) == len(estados) == len(GRADE_ESTADOS) == 27
    z = figura.data[0].z
    sp = estados[estados["sigla"] == "SP"].iloc[0]
    coluna, linha = GRADE_ESTADOS["SP"]
    assert z[linha][coluna] == pytest.approx(sp["taxa_letalidade"])
    assert len({tuple(p) for p in GRADE_ESTADOS.values()}) == 27  # nenhum bloco sobre outro
    assert any(a.text.startswith("<b>SP</b>") for a in figura.layout.annotations)


def test_mapa_dos_estados_colore_os_27_estados_pela_letalidade():
    from graficos import figura_mapa_estados

    with open(CAMINHO_GEOJSON, encoding="utf-8") as f:
        figura = figura_mapa_estados(_estados(), json.load(f))

    assert figura.data[0].type == "choropleth" and len(figura.data[0].locations) == 27
    assert figura.layout.geo.fitbounds == "locations" and not figura.layout.geo.visible


def test_curvas_dos_estados_tem_uma_linha_por_estado_em_percentual_do_pico():
    from graficos import figura_curvas_estados
    from indicadores_tempo import normalizar_pelo_pico

    semanas = pd.date_range("2021-01-04", periods=3, freq="7D")
    semanal = pd.DataFrame({"semana": list(semanas) * 2, "sigla": ["SP"] * 3 + ["MG"] * 3, "casos": [10, 40, 20, 5, 5, 1]})

    figura = figura_curvas_estados(normalizar_pelo_pico(semanal), {"SP": "São Paulo", "MG": "Minas Gerais"})

    assert [t.name for t in figura.data] == ["Minas Gerais", "São Paulo"]
    assert list(figura.data[1].y) == [25, 100, 50]
    assert list(figura.layout.yaxis.ticktext) == ["0%", "25%", "50%", "75%", "100%"] and figura.layout.yaxis.automargin  # rótulos do eixo não cortam
