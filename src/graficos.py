"""Figuras Plotly do dashboard: montam o gráfico a partir de tabelas já preparadas, sem tocar na tela."""

import math

import pandas as pd
import plotly.graph_objects as go

from componentes import aplicar_eixo_de_datas, aplicar_template_grafico
from config import (
    COR_ALERTA,
    COR_COM_COMORBIDADE,
    COR_EIXO,
    COR_PRINCIPAL,
    COR_SEM_COMORBIDADE,
    SEQUENCIA_CORES_SERIES,
)
from formatacao import fmt_inteiro, fmt_pontos
from indicadores import COR_DA_CLASSE, classe_da_diferenca

ALTURA_POR_LINHA_PX = 36
OPACIDADE_AMOSTRA_PEQUENA = 0.7
RECUO_ROTULO_PX = 10  # os rótulos da diferença ficam fora da área do gráfico, na margem direita
MARGEM_ROTULOS_PX = 100


def figura_dumbbell(agregado: pd.DataFrame) -> go.Figure:
    """Letalidade com e sem cada comorbidade: dois pontos por linha, ligados, e a diferença em p.p. à direita.

    `agregado` sai de `preparar_agregado` (já na ordem do maior ao menor risco, em fração).
    """
    nomes = agregado["nome"].tolist()
    com = (agregado["taxa_letalidade_com"] * 100).tolist()
    sem = (agregado["taxa_letalidade_sem"] * 100).tolist()

    ligacao_x, ligacao_y = [], []
    for nome, x_sem, x_com in zip(nomes, sem, com, strict=True):
        ligacao_x += [x_sem, x_com, None]
        ligacao_y += [nome, nome, None]

    figura = go.Figure()
    figura.add_trace(go.Scatter(
        x=ligacao_x, y=ligacao_y, mode="lines", line={"color": COR_EIXO, "width": 3},
        hoverinfo="skip", showlegend=False, name="Diferença",
    ))
    figura.add_trace(go.Scatter(
        x=sem, y=nomes, mode="markers", name="Sem a comorbidade", marker={"color": COR_SEM_COMORBIDADE, "size": 12},
        customdata=[fmt_inteiro(c) for c in agregado["casos_sem"]],
        hovertemplate="<b>%{y}</b><br>Sem a comorbidade: %{x:.1f}%<br>%{customdata} casos<extra></extra>",
    ))
    figura.add_trace(go.Scatter(
        x=com, y=nomes, mode="markers", name="Com a comorbidade",
        marker={
            "color": COR_COM_COMORBIDADE, "size": 14,
            "opacity": [OPACIDADE_AMOSTRA_PEQUENA if p else 1 for p in agregado["amostra_pequena"]],
        },
        customdata=[
            f"{fmt_inteiro(c)} casos" + (" (amostra pequena)" if p else "")
            for c, p in zip(agregado["casos_com"], agregado["amostra_pequena"], strict=True)
        ],
        hovertemplate="<b>%{y}</b><br>Com a comorbidade: %{x:.1f}%<br>%{customdata}<extra></extra>",
    ))
    for nome, pontos in zip(nomes, agregado["diferenca_pp"], strict=True):
        figura.add_annotation(
            x=1, xref="paper", y=nome, xanchor="left", xshift=RECUO_ROTULO_PX, showarrow=False, text=fmt_pontos(pontos),
            font={"color": COR_DA_CLASSE[classe_da_diferenca(pontos)], "size": 12, "family": "JetBrains Mono, monospace"},
        )

    aplicar_template_grafico(figura)
    menor, maior = min(com + sem), max(com + sem)
    figura.update_xaxes(
        range=[math.floor(menor / 5) * 5 - 2, math.ceil(maior / 5) * 5 + 2], dtick=5, ticksuffix="%",
        tickfont={"color": COR_EIXO, "size": 10},
    )
    figura.update_yaxes(autorange="reversed", showgrid=False, automargin=True, tickfont={"size": 12})
    figura.update_layout(
        height=len(nomes) * ALTURA_POR_LINHA_PX + 50, margin={"l": 10, "r": MARGEM_ROTULOS_PX, "t": 10, "b": 30}, showlegend=False,
    )
    return figura


def figura_por_ano(todos_anos: pd.DataFrame, comorbidade: str) -> go.Figure:
    """Letalidade com a comorbidade em cada ano; os anos parciais saem hachurados e mais claros."""
    df = todos_anos[todos_anos["comorbidade"] == comorbidade].sort_values("ano")
    completo = df["ano_completo"].tolist()
    figura = go.Figure(go.Bar(
        x=df["ano"].astype(str), y=(df["taxa_letalidade_com"] * 100).tolist(),
        marker={
            "color": COR_COM_COMORBIDADE,
            "opacity": [1 if c else 0.45 for c in completo],
            "pattern": {"shape": ["" if c else "/" for c in completo], "fgcolor": COR_COM_COMORBIDADE},
        },
        customdata=[f"{fmt_inteiro(c)} casos" + ("" if ok else " (ano parcial)") for c, ok in zip(df["casos_com"], completo, strict=True)],
        texttemplate="%{y:.1f}%", textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>Letalidade: %{y:.1f}%<br>%{customdata}<extra></extra>",
    ))
    aplicar_template_grafico(figura)
    maximo = max((df["taxa_letalidade_com"] * 100).max(), 1) if len(df) else 1
    figura.update_yaxes(range=[0, maximo * 1.2], showticklabels=False, showgrid=False)  # os rótulos das barras bastam
    figura.update_xaxes(showgrid=False, type="category")
    figura.update_layout(height=220, margin={"l": 10, "r": 10, "t": 20, "b": 30}, showlegend=False)
    return figura


ESCALAS_SERIE = ("Linear", "Logarítmica")
ROTULO_VACINACAO = "Início da vacinação"
ALTURA_SERIE_PX = 380


def figura_serie_semanal(
    semanal: pd.DataFrame, por_comorbidade: pd.DataFrame, inicio_vacinacao: pd.Timestamp, escala: str = "Linear",
) -> go.Figure:
    """Casos por semana no Brasil (área) com, por cima, as comorbidades escolhidas e a marca do início da vacinação.

    `por_comorbidade` já vem só com as comorbidades a mostrar, com a coluna `nome` (curto) e `casos` por `semana`.
    Na escala logarítmica as semanas sem caso saem do gráfico (o log de zero não existe).
    """
    logaritmica = escala == "Logarítmica"
    figura = go.Figure()
    total = semanal.sort_values("semana")
    figura.add_trace(go.Scatter(
        x=total["semana"], y=total["casos"], mode="lines", name="Brasil", fill="tozeroy" if not logaritmica else None,
        line={"color": COR_PRINCIPAL, "width": 2}, fillcolor="rgba(34,211,238,0.12)",
        hovertemplate="Brasil<br>%{x|%d/%m/%Y}: %{y:,} casos<extra></extra>",
    ))
    for cor, (nome, grupo) in zip(SEQUENCIA_CORES_SERIES, por_comorbidade.groupby("nome"), strict=False):
        grupo = grupo.sort_values("semana")
        if logaritmica:
            grupo = grupo[grupo["casos"] > 0]
        figura.add_trace(go.Scatter(
            x=grupo["semana"], y=grupo["casos"], mode="lines", name=nome, line={"color": cor, "width": 2},
            hovertemplate=nome + "<br>%{x|%d/%m/%Y}: %{y:,} casos<extra></extra>",
        ))
    figura.add_shape(
        type="line", x0=inicio_vacinacao, x1=inicio_vacinacao, y0=0, y1=1, yref="paper",
        line={"color": COR_ALERTA, "width": 2, "dash": "dash"},
    )
    figura.add_annotation(
        x=inicio_vacinacao, y=1, yref="paper", text=ROTULO_VACINACAO, showarrow=False, xanchor="left", xshift=6,
        yanchor="top", font={"color": COR_ALERTA, "size": 11},
    )
    aplicar_template_grafico(figura)
    aplicar_eixo_de_datas(figura, total["semana"].min(), total["semana"].max())
    figura.update_xaxes(showgrid=False, tickfont={"color": COR_EIXO, "size": 10})
    figura.update_yaxes(
        type="log" if logaritmica else "linear", tickfont={"color": COR_EIXO, "size": 10}, automargin=True,
        tickformat=",d",
    )
    figura.update_layout(
        height=ALTURA_SERIE_PX, margin={"l": 10, "r": 10, "t": 10, "b": 30}, hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "font": {"size": 12}},
    )
    return figura
