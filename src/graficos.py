"""Figuras Plotly do dashboard: montam o gráfico a partir de tabelas já preparadas, sem tocar na tela."""

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from componentes import aplicar_eixo_de_datas, aplicar_template_grafico
from config import (
    ALTURA_MAPA_PX,
    COR_ALERTA,
    COR_COM_COMORBIDADE,
    COR_EIXO,
    COR_FUNDO_PAGINA,
    COR_PRINCIPAL,
    COR_SEM_COMORBIDADE,
    ESCALA_LETALIDADE,
    ESTILO_MAPA,
    GRADE_ESTADOS,
    LARGURA_REFERENCIA_MAPA_PX,
    SEQUENCIA_CORES_SERIES,
)
from formatacao import fmt_decimal, fmt_inteiro, fmt_pontos
from indicadores import COR_DA_CLASSE, classe_da_diferenca
from mapa import enquadramento, limites_do_geojson, siglas_com_rotulo

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


TITULO_ESCALA_LETALIDADE = "Letalidade (%)"
TAMANHO_ROTULO_MAPA = 8


def figura_mapa_estados(estados: pd.DataFrame, geojson: dict) -> go.Figure:
    """Mapa dos estados coloridos pela letalidade, com o número de casos só onde cabe (os demais, no hover).

    `estados` sai de `preparar_estados`. Usa `choropleth_map` (WebGL/MapLibre): o `choropleth` em SVG desenhava
    todos os estados na mesma caixa nos navegadores testados.
    """
    centro, zoom = enquadramento(limites_do_geojson(geojson), LARGURA_REFERENCIA_MAPA_PX, ALTURA_MAPA_PX)
    mapa = px.choropleth_map(
        estados, geojson=geojson, locations="sigla", featureidkey="properties.sigla", color="taxa_letalidade",
        color_continuous_scale=list(ESCALA_LETALIDADE), hover_name="nome",
        hover_data={"sigla": False, "taxa_letalidade": ":.1f", "casos_fmt": True},
        labels={"taxa_letalidade": TITULO_ESCALA_LETALIDADE, "casos_fmt": "Casos de COVID"},
        map_style=ESTILO_MAPA, center=centro, zoom=zoom, opacity=1,
    )
    com_rotulo = siglas_com_rotulo(
        geojson, zoom, dict(zip(estados["sigla"], estados["casos_fmt"], strict=True)),
        dict(zip(estados["sigla"], zip(estados["lon_centro"], estados["lat_centro"], strict=True), strict=True)),
    )
    # textfont.color só aceita uma cor por camada: um grupo de rótulos para cada cor.
    for cor, grupo in estados[estados["sigla"].isin(com_rotulo)].groupby("cor_rotulo"):
        mapa.add_trace(go.Scattermap(
            lat=grupo["lat_centro"], lon=grupo["lon_centro"], mode="text", text=grupo["casos_fmt"],
            textfont={"size": TAMANHO_ROTULO_MAPA, "color": cor}, hoverinfo="skip", showlegend=False,
        ))
    aplicar_template_grafico(mapa)
    mapa.update_traces(marker_line_color=COR_FUNDO_PAGINA, marker_line_width=0.8, selector={"type": "choroplethmap"})
    mapa.update_layout(height=ALTURA_MAPA_PX, margin={"l": 0, "r": 0, "t": 0, "b": 0})
    return mapa


def figura_blocos_estados(estados: pd.DataFrame) -> go.Figure:
    """Um bloco do mesmo tamanho por estado, na posição de GRADE_ESTADOS, coloridos pela letalidade, com sigla e taxa."""
    colunas = max(c for c, _ in GRADE_ESTADOS.values()) + 1
    linhas = max(r for _, r in GRADE_ESTADOS.values()) + 1
    z = [[None] * colunas for _ in range(linhas)]
    detalhes = [[""] * colunas for _ in range(linhas)]
    figura = go.Figure()
    for estado in estados.itertuples():
        coluna, linha = GRADE_ESTADOS[estado.sigla]
        z[linha][coluna] = estado.taxa_letalidade
        detalhes[linha][coluna] = (
            f"<b>{estado.nome}</b><br>Letalidade: {fmt_decimal(estado.taxa_letalidade)}%<br>{estado.casos_fmt} casos"
        )
        figura.add_annotation(
            x=coluna, y=linha, text=f"<b>{estado.sigla}</b><br>{fmt_decimal(estado.taxa_letalidade)}%", showarrow=False,
            font={"color": estado.cor_rotulo, "size": 12},
        )
    figura.add_trace(go.Heatmap(
        z=z, customdata=detalhes, hovertemplate="%{customdata}<extra></extra>", xgap=4, ygap=4, hoverongaps=False,
        colorscale=list(ESCALA_LETALIDADE), colorbar={"title": {"text": TITULO_ESCALA_LETALIDADE}, "thickness": 10},
    ))
    aplicar_template_grafico(figura)
    figura.update_xaxes(visible=False, constrain="domain")
    figura.update_yaxes(visible=False, autorange="reversed", scaleanchor="x")
    figura.update_layout(height=ALTURA_MAPA_PX, margin={"l": 0, "r": 0, "t": 0, "b": 0})
    return figura


def figura_curvas_estados(curvas: pd.DataFrame, nomes_estados: dict[str, str]) -> go.Figure:
    """Uma linha por estado com os casos semanais em % do pico do próprio estado (de `normalizar_pelo_pico`).

    As cores seguem a ordem alfabética das siglas marcadas.
    """
    figura = go.Figure()
    for cor, (sigla, grupo) in zip(SEQUENCIA_CORES_SERIES, curvas.groupby("sigla"), strict=False):
        grupo = grupo.sort_values("semana")
        figura.add_trace(go.Scatter(
            x=grupo["semana"], y=grupo["pct_do_pico"], mode="lines", name=nomes_estados[sigla],
            line={"color": cor, "width": 2}, customdata=grupo["casos"],
            hovertemplate=(
                f"<b>{nomes_estados[sigla]}</b><br>%{{x|%d/%m/%Y}}<br>%{{y:.0f}}% do pico"
                "<br>%{customdata:,} casos<extra></extra>"
            ),
        ))
    aplicar_template_grafico(figura)
    aplicar_eixo_de_datas(figura, curvas["semana"].min(), curvas["semana"].max())
    figura.update_xaxes(showgrid=False, tickfont={"color": COR_EIXO, "size": 10})
    figura.update_yaxes(
        range=[0, 105], ticksuffix="%", tickvals=[0, 25, 50, 75, 100], tickfont={"color": COR_EIXO, "size": 10},
        automargin=True,
    )
    figura.update_layout(
        height=ALTURA_SERIE_PX, margin={"l": 10, "r": 10, "t": 10, "b": 30}, hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "font": {"size": 12}},
    )
    return figura
