"""Página Comorbidades: letalidade com e sem cada comorbidade."""


import altair as alt
import pandas as pd
import streamlit as st

from componentes import html_kpi
from config import (
    CAMINHO_AGREGADO,
    CAMINHO_RESUMO_GERAL,
    COR_COM_COMORBIDADE,
    COR_GRADE,
    COR_SEM_COMORBIDADE,
    COR_TEXTO,
    NOMES_COMORBIDADES,
)
from indicadores import kpis_comorbidades, preparar_agregado

_agregado = preparar_agregado(pd.read_csv(CAMINHO_AGREGADO))
_resumo = pd.read_csv(CAMINHO_RESUMO_GERAL)
st.html('<div class="cv-kpis">' + "".join(
    html_kpi(k.rotulo, k.valor, k.linha, k.cor, k.ajuda) for k in kpis_comorbidades(_agregado, _resumo)
) + "</div>")

st.info(
    "**Fonte:** SIVEP-Gripe (SRAG) / Ministério da Saúde, via OpenDataSUS. "
    "Taxa de letalidade = óbitos / (óbitos + curas), entre casos com desfecho conhecido.\n\n"
    "Cada par de barras compara dois grupos separados de pacientes — quem tinha a comorbidade "
    "e quem não tinha. As duas taxas não somam entre si; são percentuais independentes.\n\n"
    "Os números abaixo somam os 7 anos (2020–2026). **2026 é um ano parcial** (dados só até o "
    "mês mais recente coletado pelo Ministério da Saúde), mas já está incluído nesse total."
)

st.markdown(
    f'<div style="height:4px;border-radius:2px;margin:1.5rem 0 1rem 0;'
    f'background:linear-gradient(to right, {COR_COM_COMORBIDADE}, {COR_SEM_COMORBIDADE});"></div>',
    unsafe_allow_html=True,
)

df = pd.read_csv(CAMINHO_AGREGADO)
df["comorbidade"] = df["comorbidade"].map(NOMES_COMORBIDADES)

# O CSV guarda a taxa em fração (0.571). Convertemos pra porcentagem uma única vez,
# aqui na camada de apresentação — o arquivo em disco continua em fração.
df["taxa_letalidade_com"] = df["taxa_letalidade_com"] * 100
df["taxa_letalidade_sem"] = df["taxa_letalidade_sem"] * 100

df = df.sort_values("taxa_letalidade_com", ascending=False)

with st.container(border=True):
    st.subheader("Taxa de letalidade: com a comorbidade vs. sem")

    # Ordem das comorbidades no eixo (mesma ordem em que o DataFrame já está: maior -> menor).
    ordem_comorbidades = df["comorbidade"].tolist()

    # st.bar_chart não dá controle suficiente sobre orientação horizontal + rótulos de valor
    # + cores de eixo/grade ao mesmo tempo, então aqui usamos o Altair diretamente (biblioteca
    # que o próprio Streamlit usa por baixo dos panos). Isso exige os dados em formato "longo":
    # uma linha por combinação de comorbidade + grupo (com/sem), em vez de uma coluna por grupo.
    df_grafico = df.melt(
        id_vars="comorbidade",
        value_vars=["taxa_letalidade_com", "taxa_letalidade_sem"],
        var_name="grupo",
        value_name="taxa",
    )
    df_grafico["grupo"] = df_grafico["grupo"].map({
        "taxa_letalidade_com": "Com a comorbidade",
        "taxa_letalidade_sem": "Sem a comorbidade",
    })

    base = alt.Chart(df_grafico).encode(
        y=alt.Y("comorbidade:N", sort=ordem_comorbidades, title=None,
                axis=alt.Axis(labelColor=COR_TEXTO, labelLimit=280, labelFontSize=12)),
        yOffset=alt.YOffset("grupo:N", sort=["Com a comorbidade", "Sem a comorbidade"]),
        x=alt.X("taxa:Q", title="Taxa de letalidade (%)",
                axis=alt.Axis(labelColor=COR_TEXTO, titleColor=COR_TEXTO, gridColor=COR_GRADE)),
        color=alt.Color(
            "grupo:N",
            scale=alt.Scale(domain=["Com a comorbidade", "Sem a comorbidade"],
                             range=[COR_COM_COMORBIDADE, COR_SEM_COMORBIDADE]),
            legend=alt.Legend(title=None, labelColor=COR_TEXTO, orient="top"),
        ),
    )
    barras = base.mark_bar()
    rotulos = base.mark_text(align="left", dx=4, color=COR_TEXTO, fontSize=11).encode(
        text=alt.Text("taxa:Q", format=".1f")
    )

    grafico_final = (
        (barras + rotulos)
        .properties(height=480, background="transparent")
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(grafico_final, width="stretch")

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
