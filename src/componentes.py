"""Peças de tela compartilhadas pelas páginas: template dos gráficos, cartões de número e títulos de painel."""

from html import escape

import plotly.graph_objects as go
import streamlit as st

from config import (
    CONFIG_PLOTLY,
    COR_BORDA,
    COR_FUNDO_PAINEL,
    COR_GRADE,
    COR_TEXTO,
    SEQUENCIA_CORES_SERIES,
)


def aplicar_template_grafico(figura: go.Figure) -> go.Figure:
    """Template único dos gráficos: fundo transparente (o painel aparece por trás), grade discreta,
    fonte e sequência de cores do tema."""
    figura.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COR_TEXTO},
        colorway=list(SEQUENCIA_CORES_SERIES),
        hoverlabel={"bgcolor": COR_FUNDO_PAINEL, "bordercolor": COR_BORDA},
        separators=",.",
    )
    figura.update_xaxes(gridcolor=COR_GRADE, zerolinecolor=COR_GRADE, linecolor=COR_BORDA)
    figura.update_yaxes(gridcolor=COR_GRADE, zerolinecolor=COR_GRADE, linecolor=COR_BORDA)
    return figura


def exibir_grafico(figura: go.Figure) -> None:
    """Único ponto de `st.plotly_chart` do app: tema do Plotly (não o do Streamlit), largura total e sem
    a barra de ferramentas."""
    st.plotly_chart(figura, width="stretch", theme=None, config=CONFIG_PLOTLY)


def _marca_ajuda(ajuda: str | None) -> str:
    return f'<span class="cv-ajuda" title="{escape(ajuda)}">?</span>' if ajuda else ""


def html_kpi(rotulo: str, valor: str, linha: str = "", cor: str | None = None, ajuda: str | None = None) -> str:
    """Cartão de número de destaque; `st.metric` não deixa colorir o número. `ajuda` vira o "?" com dica."""
    estilo = f' style="color:{escape(cor)}"' if cor else ""
    return (
        '<div class="cv-kpi">'
        f'<p class="cv-secao">{escape(rotulo)}{_marca_ajuda(ajuda)}</p>'
        f'<div class="cv-valor"{estilo}>{escape(valor)}</div>'
        f'<div class="cv-linha">{escape(linha)}</div>'
        "</div>"
    )


def html_celulas(celulas: list) -> str:
    """Grade de células lado a lado (rótulo, valor e linha de apoio), como `Kpi`, mas dentro de um painel."""
    partes = []
    for c in celulas:
        estilo = f' style="color:{escape(c.cor)}"' if c.cor else ""
        partes.append(
            f'<div class="cv-celula"><span class="cv-linha">{escape(c.rotulo)}</span>'
            f'<span class="cv-valor-medio"{estilo}>{escape(c.valor)}</span>'
            f'<span class="cv-linha">{escape(c.linha)}</span></div>'
        )
    return '<div class="cv-celulas">' + "".join(partes) + "</div>"


def html_titulo_painel(titulo: str, ajuda: str | None = None) -> str:
    """Título pequeno de painel, em caixa alta, com "?" opcional."""
    return f'<div class="cv-cabecalho"><p class="cv-secao">{escape(titulo)}{_marca_ajuda(ajuda)}</p></div>'


def titulo_painel(titulo: str, ajuda: str | None = None) -> None:
    st.html(html_titulo_painel(titulo, ajuda))
