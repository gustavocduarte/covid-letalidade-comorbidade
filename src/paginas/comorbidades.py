"""Página Comorbidades: letalidade com e sem cada comorbidade."""


import pandas as pd
import streamlit as st

from componentes import exibir_grafico, html_kpi, html_titulo_painel
from config import (
    CAMINHO_AGREGADO,
    CAMINHO_RESUMO_GERAL,
    COR_COM_COMORBIDADE,
    COR_SEM_COMORBIDADE,
    COR_TEXTO,
    NOMES_COMORBIDADES,
)
from graficos import figura_dumbbell
from indicadores import kpis_comorbidades, preparar_agregado

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

df = pd.read_csv(CAMINHO_AGREGADO)
df["comorbidade"] = df["comorbidade"].map(NOMES_COMORBIDADES)

# O CSV guarda a taxa em fração (0.571). Convertemos pra porcentagem uma única vez,
# aqui na camada de apresentação — o arquivo em disco continua em fração.
df["taxa_letalidade_com"] = df["taxa_letalidade_com"] * 100
df["taxa_letalidade_sem"] = df["taxa_letalidade_sem"] * 100

df = df.sort_values("taxa_letalidade_com", ascending=False)

st.subheader("Tabela completa")
# Seleciona só as colunas de exibição — o df também carrega obitos_com/desfecho_conhecido_com
# etc., usados internamente pra agregar os anos com exatidão, mas que não aparecem na tela.
df_tabela = df[["comorbidade", "casos_com", "taxa_letalidade_com", "casos_sem", "taxa_letalidade_sem"]].copy()
df_tabela["casos_com"] = df_tabela["casos_com"].apply(lambda x: f"{x:,}".replace(",", "."))
df_tabela["casos_sem"] = df_tabela["casos_sem"].apply(lambda x: f"{x:,}".replace(",", "."))
st.dataframe(
    df_tabela,
    hide_index=True,
    column_config={
        "comorbidade": st.column_config.TextColumn("Comorbidade"),
        "casos_com": st.column_config.TextColumn("Casos (com)"),
        "taxa_letalidade_com": st.column_config.NumberColumn("Taxa de Letalidade % (com)", format="%.1f"),
        "casos_sem": st.column_config.TextColumn("Casos (sem)"),
        "taxa_letalidade_sem": st.column_config.NumberColumn("Taxa de Letalidade % (sem)", format="%.1f"),
    },
)

st.divider()

st.subheader("Explorar uma comorbidade")
comorbidade_escolhida = st.selectbox("Escolha uma comorbidade:", df["comorbidade"])
linha = df[df["comorbidade"] == comorbidade_escolhida].iloc[0]

# Acento de cor nos dois primeiros cartões, ecoando a paleta do gráfico.
# `key=` no container gera uma classe CSS "st-key-<nome>" exclusiva, que dá
# pra mirar com CSS customizado sem afetar o cartão "Casos" (sem key/cor).
st.markdown(
    f"""
    <style>
    div[class*="st-key-card_com"] {{
        border-color: {COR_COM_COMORBIDADE} !important;
        border-width: 2px !important;
    }}
    div[class*="st-key-card_sem"] {{
        border-color: {COR_SEM_COMORBIDADE} !important;
        border-width: 2px !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns(3)
with c1.container(border=True, key="card_com"):
    st.metric(
        "Letalidade COM a comorbidade", f"{linha['taxa_letalidade_com']:.1f}%",
        delta=f"{linha['taxa_letalidade_com'] - linha['taxa_letalidade_sem']:.1f} p.p.", delta_color="inverse",
    )
with c2.container(border=True, key="card_sem"):
    st.metric("Letalidade SEM a comorbidade", f"{linha['taxa_letalidade_sem']:.1f}%")
with c3.container(border=True):
    st.metric("Casos com essa comorbidade", f"{linha['casos_com']:,}".replace(",", "."))

st.divider()

st.markdown(
    f"""
    <div style="background:{COR_SEM_COMORBIDADE}26; border-left:4px solid {COR_COM_COMORBIDADE};
                border-radius:6px; padding:1rem 1.25rem; margin-bottom:1.25rem;">
        <div style="font-weight:600; font-size:1.05rem; margin-bottom:0.6rem; color:{COR_TEXTO};">
            Principais achados
        </div>
        <p style="color:{COR_TEXTO}; margin:0 0 0.75rem 0; line-height:1.55;">
            Das 11 comorbidades analisadas, a <strong>Doença Renal Crônica</strong> aparece com o
            maior risco: pacientes com essa condição têm uma taxa de letalidade de COVID-19
            quase <strong>1,5 vez maior</strong> do que pacientes sem ela (53% contra 37%, somando
            os 7 anos de dados). <strong>Doença Hepática Crônica</strong> aparece logo atrás (51%),
            seguida por Doença Neurológica e Pneumopatia, numa faixa de risco também alta.
        </p>
        <p style="color:{COR_TEXTO}; margin:0 0 0.75rem 0; line-height:1.55;">
            O número de casos caiu de forma acentuada depois do início da vacinação no Brasil
            (17/01/2021), como fica visível no gráfico de linha do tempo mais abaixo. É importante
            não interpretar isso como uma prova direta de causa e efeito: no mesmo período, outros
            fatores — como isolamento social e a evolução natural da pandemia — também
            influenciaram essa queda. A vacinação está marcada no gráfico só como referência
            temporal.
        </p>
        <p style="color:{COR_TEXTO}; margin:0; line-height:1.55;">
            Um ponto de atenção importante: como muitos pacientes têm mais de uma comorbidade ao
            mesmo tempo, o grupo "sem" determinada condição não representa pessoas saudáveis — só
            pessoas sem aquela condição específica, que podem ter outras. É por isso, por exemplo,
            que <strong>Asma</strong> e <strong>Obesidade</strong> aparecem com letalidade menor que
            a média geral: não é porque essas condições protegem contra COVID-19, e sim,
            provavelmente, porque pacientes com essas comorbidades tendem a ser mais jovens em
            média — e a idade em si é um forte fator de risco separado.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Sobre este projeto / Metodologia"):
    st.markdown(
        """
**Fonte dos dados**
SIVEP-Gripe (Sistema de Informação da Vigilância Epidemiológica da Gripe), que registra
casos de Síndrome Respiratória Aguda Grave (SRAG) no Brasil. Dado bruto disponibilizado
pelo Ministério da Saúde através do OpenDataSUS.

**Período coberto**
2020 a 2026. **2026 é um ano parcial** — os dados só vão até o mês mais recente
disponibilizado pelo Ministério da Saúde no momento da extração, não um ano fechado.

**Definição da taxa de letalidade**
Óbitos ÷ (óbitos + curas), considerando **apenas casos com desfecho conhecido**. Casos
ignorados, em aberto (sem desfecho registrado ainda) ou óbito por outra causa são
excluídos do cálculo — tanto do numerador quanto do denominador.

**Limitações metodológicas identificadas**
- *Confundimento por comorbidades múltiplas*: pacientes podem ter mais de uma comorbidade
  registrada ao mesmo tempo. Isso faz os grupos de comparação "com" e "sem" cada condição
  se sobreporem parcialmente entre si — por exemplo, parte do grupo "sem Diabetes" pode ter
  Doença Cardiovascular Crônica, e vice-versa. As taxas aqui não isolam o efeito de uma
  única comorbidade de forma independente das demais.
- *Comorbidades raras têm amostra pequena*: condições com poucos casos registrados na base
  (como Síndrome de Down) têm taxas de letalidade estatisticamente menos confiáveis — um
  punhado de casos a mais ou a menos muda a taxa de forma desproporcional. O mapa por
  estado tem o mesmo problema para estados com poucos casos.
- *Tabagismo (TABAG) não incluído*: esse campo existe no formulário oficial do SIVEP-Gripe,
  mas checamos e ele não é preenchido na prática pelos postos de saúde (100% vazio em
  todos os 7 anos) — por isso foi excluído da análise, em vez de mostrar uma comorbidade
  sem dado real por trás.
        """
    )
