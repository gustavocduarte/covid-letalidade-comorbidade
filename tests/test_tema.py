"""Tema escuro: cores do config.toml iguais às do código, escala legível e peças de tela."""

import tomllib
from itertools import pairwise
from pathlib import Path

import plotly.graph_objects as go
import pytest

import config
from componentes import aplicar_template_grafico, html_kpi, html_titulo_painel
from mapa import _hex_para_rgb, cor_na_escala, cor_texto_contraste, luminancia_relativa

CONFIG_TOML = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"


def _tema() -> dict:
    return tomllib.loads(CONFIG_TOML.read_text(encoding="utf-8"))["theme"]


def test_tema_do_streamlit_e_escuro_e_usa_as_cores_do_codigo():
    tema = _tema()

    assert tema["base"] == "dark"
    assert tema["primaryColor"] == config.COR_PRINCIPAL
    assert tema["backgroundColor"] == config.COR_FUNDO_PAGINA
    assert tema["secondaryBackgroundColor"] == config.COR_FUNDO_PAINEL
    assert tema["textColor"] == config.COR_TEXTO
    assert tema["borderColor"] == config.COR_BORDA
    assert tema["sidebar"]["backgroundColor"] == config.COR_FUNDO_BARRA
    assert tuple(tema["chartCategoricalColors"]) == config.SEQUENCIA_CORES_SERIES


def _contraste(cor_a: str, cor_b: str) -> float:
    a, b = (luminancia_relativa(_hex_para_rgb(c)) for c in (cor_a, cor_b))
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def test_escala_da_letalidade_clareia_passo_a_passo_e_destaca_do_fundo():
    escala = config.ESCALA_LETALIDADE

    luminancias = [luminancia_relativa(_hex_para_rgb(c)) for c in escala]
    assert luminancias == sorted(luminancias)
    # cada degrau se distingue do anterior, e o mais escuro se distingue do fundo da página
    assert all(_contraste(a, b) >= 1.4 for a, b in pairwise(escala))
    assert _contraste(escala[0], config.COR_FUNDO_PAGINA) >= 1.8


def test_cor_na_escala_nas_pontas_e_no_meio():
    escala = ("#000000", "#FF0000", "#FFFFFF")

    assert cor_na_escala(0, escala) == (0, 0, 0)
    assert cor_na_escala(0.5, escala) == (255, 0, 0)
    assert cor_na_escala(1, escala) == (255, 255, 255)
    assert cor_na_escala(0.25, escala) == (127.5, 0, 0)
    assert cor_na_escala(2, escala) == (255, 255, 255)  # fora do intervalo vale a ponta


def test_texto_claro_sobre_fundo_escuro_e_escuro_sobre_fundo_claro():
    escala = config.ESCALA_LETALIDADE
    claro, escuro = "#FFFFFF", config.COR_FUNDO_PAGINA

    assert cor_texto_contraste(0, 0, 1, escala, claro, escuro) == claro
    assert cor_texto_contraste(1, 0, 1, escala, claro, escuro) == escuro
    assert cor_texto_contraste(5, 5, 5, escala, claro, escuro) in {claro, escuro}  # sem variação não quebra


def test_template_deixa_o_fundo_transparente_e_usa_as_cores_do_tema():
    figura = aplicar_template_grafico(go.Figure())

    assert figura.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert figura.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert figura.layout.font.color == config.COR_TEXTO
    assert tuple(figura.layout.colorway) == config.SEQUENCIA_CORES_SERIES


def test_kpi_escapa_o_texto_e_so_colore_quando_pedido():
    html = html_kpi("A <b>", "1.234", "casos & mais", cor=config.COR_PRINCIPAL, ajuda='diz "oi"')

    assert "A &lt;b&gt;" in html and "casos &amp; mais" in html and "&quot;oi&quot;" in html
    assert f'style="color:{config.COR_PRINCIPAL}"' in html
    assert "style=" not in html_kpi("Casos", "1", "")


def test_titulo_de_painel_com_e_sem_ajuda():
    assert 'class="cv-ajuda"' in html_titulo_painel("Tabela", "como ler")
    assert 'class="cv-ajuda"' not in html_titulo_painel("Tabela")


@pytest.mark.parametrize("nome", ["COR_PRINCIPAL", "COR_COM_COMORBIDADE", "COR_SEM_COMORBIDADE", "COR_POSITIVO", "COR_ALERTA"])
def test_cores_de_destaque_sao_hexadecimais_validos(nome):
    cor = getattr(config, nome)

    assert len(cor) == 7 and cor.startswith("#")
    int(cor[1:], 16)
