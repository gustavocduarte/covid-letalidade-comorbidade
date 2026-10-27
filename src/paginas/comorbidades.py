"""Página Comorbidades: letalidade com e sem cada comorbidade."""


import pandas as pd
import streamlit as st

from componentes import exibir_grafico, html_achados, html_celulas, html_kpi, html_titulo_painel, titulo_painel
from config import (
    CAMINHO_AGREGADO,
    CAMINHO_RESUMO_GERAL,
    CAMINHO_TODOS_ANOS,
    COR_COM_COMORBIDADE,
    COR_SEM_COMORBIDADE,
    LIMITE_AMOSTRA_PEQUENA,
)
from formatacao import fmt_inteiro, fmt_percentual, fmt_pontos
from graficos import figura_dumbbell, figura_por_ano
from indicadores import (
    COLUNAS_TABELA,
    MARCA_AMOSTRA_PEQUENA,
    achados_comorbidades,
    celulas_da_comorbidade,
    cor_da_celula_de_diferenca,
    kpis_comorbidades,
    preparar_agregado,
    tabela_para_exibir,
)

_agregado = preparar_agregado(pd.read_csv(CAMINHO_AGREGADO))
_resumo = pd.read_csv(CAMINHO_RESUMO_GERAL)
st.html('<div class="cv-kpis">' + "".join(
    html_kpi(k.rotulo, k.valor, k.linha, k.cor, k.ajuda) for k in kpis_comorbidades(_agregado, _resumo)
) + "</div>")

with st.container(border=True, key="painel_dumbbell"):
    st.html(
        html_titulo_painel(
            "Letalidade com e sem a comorbidade",
            "Cada linha compara dois grupos separados: quem tinha a comorbidade e quem não tinha. "
            "As taxas não somam entre si.",
        )
        + '<div class="cv-legenda">'
        f'<span><i style="background:{COR_COM_COMORBIDADE}"></i>Com a comorbidade</span>'
        f'<span><i style="background:{COR_SEM_COMORBIDADE}"></i>Sem a comorbidade</span></div>'
    )
    exibir_grafico(figura_dumbbell(_agregado))
    st.caption("Valores ao passar o mouse: taxa com, taxa sem e número de casos de cada grupo.")

_todos_anos = pd.read_csv(CAMINHO_TODOS_ANOS)
col_a, col_b = st.columns(2)
with col_a.container(border=True, key="painel_explorar"):
    titulo_painel("Explorar uma comorbidade")
    nome_escolhido = st.selectbox(
        "Comorbidade", _agregado["nome"].tolist(), key="comorbidade_explorada", label_visibility="collapsed",
    )
    _linha = _agregado[_agregado["nome"] == nome_escolhido].iloc[0]
    st.html(html_celulas(celulas_da_comorbidade(_linha)))
    st.html('<div class="cv-linha">Letalidade com a comorbidade, por ano</div>')
    exibir_grafico(figura_por_ano(_todos_anos, _linha["comorbidade"]))
    _parciais = ", ".join(str(a) for a in sorted(_todos_anos.loc[~_todos_anos["ano_completo"], "ano"].unique()))
    if _parciais:
        st.caption(f"Ano parcial (hachurado): {_parciais}.")

with col_b.container(border=True, key="painel_achados"):
    titulo_painel("Principais achados")
    st.html(html_achados(achados_comorbidades(_agregado)))

_tabela = tabela_para_exibir(_agregado)
# Estilo por célula só colore o texto; os valores continuam números e a ordenação por coluna segue numérica.
_estilo = (
    _tabela.style
    .map(cor_da_celula_de_diferenca, subset=["diferenca_pp"])
    .map(lambda _: f"color: {COR_COM_COMORBIDADE}", subset=["taxa_com"])
    .format(fmt_inteiro, subset=["casos_com", "casos_sem"])
    .format(lambda v: fmt_percentual(v / 100), subset=["taxa_com", "taxa_sem"])
    .format(fmt_pontos, subset=["diferenca_pp"])
)
with st.container(border=True, key="painel_tabela"):
    _cabecalho, _botao = st.columns([4, 1])
    with _cabecalho:
        titulo_painel("Tabela completa")
    _botao.download_button(
        "Baixar CSV", data=CAMINHO_AGREGADO.read_bytes(), file_name=CAMINHO_AGREGADO.name, mime="text/csv",
        key="baixar_agregado",
    )
    st.dataframe(
        _estilo,
        hide_index=True,
        height="content",
        column_config={
            "nome": st.column_config.TextColumn(COLUNAS_TABELA["nome"]),
            "casos_com": st.column_config.NumberColumn(COLUNAS_TABELA["casos_com"]),
            "taxa_com": st.column_config.NumberColumn(COLUNAS_TABELA["taxa_com"]),
            "casos_sem": st.column_config.NumberColumn(COLUNAS_TABELA["casos_sem"]),
            "taxa_sem": st.column_config.NumberColumn(COLUNAS_TABELA["taxa_sem"]),
            "diferenca_pp": st.column_config.NumberColumn(COLUNAS_TABELA["diferenca_pp"]),
            "amostra": st.column_config.TextColumn(
                COLUNAS_TABELA["amostra"], help=f"Menos de {fmt_inteiro(LIMITE_AMOSTRA_PEQUENA)} casos com a comorbidade",
            ),
        },
    )
    st.caption(
        f"{MARCA_AMOSTRA_PEQUENA} amostra pequena (menos de {fmt_inteiro(LIMITE_AMOSTRA_PEQUENA)} casos com a "
        "comorbidade): a taxa é menos estável."
    )
