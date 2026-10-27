"""Figuras Plotly do dashboard: montam o gráfico a partir de tabelas já preparadas, sem tocar na tela."""

import math

import pandas as pd
import plotly.graph_objects as go

from componentes import aplicar_template_grafico
from config import (
    COR_COM_COMORBIDADE,
    COR_EIXO,
    COR_SEM_COMORBIDADE,
)
from formatacao import fmt_inteiro, fmt_pontos
from indicadores import COR_DA_CLASSE, classe_da_diferenca

ALTURA_POR_LINHA_PX = 36
OPACIDADE_AMOSTRA_PEQUENA = 0.7


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
            x=1, xref="paper", y=nome, xanchor="right", showarrow=False, text=fmt_pontos(pontos),
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
        height=len(nomes) * ALTURA_POR_LINHA_PX + 50, margin={"l": 10, "r": 90, "t": 10, "b": 30}, showlegend=False,
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
