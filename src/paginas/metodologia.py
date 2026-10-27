"""Página Metodologia: de onde vêm os dados, como cada número é calculado e o que eles não permitem concluir."""

import streamlit as st

from componentes import titulo_painel
from config import (
    DATA_INICIO_VACINACAO,
    FAIXA_NEUTRA_PP,
    FRACAO_PICO_DA_CAUDA,
    LIMITE_AMOSTRA_PEQUENA,
    SEMANAS_EM_NOTIFICACAO,
)
from formatacao import fmt_decimal, fmt_inteiro
from qualidade import casos_sem_estado

_sem_uf = casos_sem_estado()
_texto_sem_uf = (
    f"{fmt_inteiro(_sem_uf)} casos não têm estado informado (ou têm um código inválido)"
    if _sem_uf else "Os casos sem estado informado (ou com código inválido)"
)

with st.container(border=True, key="painel_metodologia_dados"):
    titulo_painel("Dados e pipeline")
    st.markdown(
        """
**Fonte.** SIVEP-Gripe (Sistema de Informação da Vigilância Epidemiológica da Gripe), que registra casos de
Síndrome Respiratória Aguda Grave (SRAG) no Brasil, disponibilizado pelo Ministério da Saúde no OpenDataSUS.
Só entram os casos classificados como COVID-19.

**Período.** 2020 a 2026. **2026 é um ano parcial**: os dados vão só até a data da última versão publicada.

**Pipeline, em uma frase.** CSV bruto do OpenDataSUS → Parquet por ano → consultas SQL (DuckDB) → validação →
CSVs pequenos e versionados, que são a única coisa que este dashboard lê.
        """
    )

with st.container(border=True, key="painel_metodologia_definicoes"):
    titulo_painel("Definições")
    st.markdown(
        f"""
**Letalidade.** Óbitos ÷ (óbitos + curas), considerando **apenas casos com desfecho conhecido**. Casos
ignorados, ainda em aberto (sem desfecho registrado) ou com óbito por outra causa ficam de fora, tanto do
numerador quanto do denominador. Não é a mortalidade da população nem o risco de morrer de COVID: é a fração
de óbitos entre os hospitalizados cujo desfecho já se conhece.

**Com e sem a comorbidade.** Cada comorbidade compara dois grupos separados: quem a tinha registrada e quem
não tinha. As taxas de uma linha não somam com as das outras, e o grupo "sem" não é de pessoas saudáveis.

**Diferença em pontos percentuais.** Letalidade com a comorbidade menos letalidade sem ela. Diferenças de
menos de {fmt_decimal(FAIXA_NEUTRA_PP, 0)} p.p. (em módulo) são tratadas como neutras: ficam em cinza e o
texto as descreve como "perto" da taxa de quem não tem.

**Amostra pequena.** Comorbidade com menos de {fmt_inteiro(LIMITE_AMOSTRA_PEQUENA)} casos tem taxa menos
estável: poucos casos a mais ou a menos mudam a taxa de forma desproporcional. Ela aparece marcada no
gráfico e na tabela, e os estados com poucos casos têm o mesmo problema no mapa.

**Cauda por estado.** Semanas entre o pico semanal do estado e a primeira semana em que os casos caem abaixo
de {FRACAO_PICO_DA_CAUDA:.0%} desse pico. Número maior significa queda mais lenta.
        """
    )

with st.container(border=True, key="painel_metodologia_limites"):
    titulo_painel("Limitações")
    st.markdown(
        f"""
**Casos sem estado.** {_texto_sem_uf}. Eles entram em todos os números nacionais, mas não aparecem no mapa,
nos blocos nem nas curvas por estado.

**Semanas recentes ainda em notificação.** Os registros chegam com atraso; o número das últimas semanas tende a
subir nas próximas atualizações e a queda no fim da série não é queda real. Por isso as últimas
{SEMANAS_EM_NOTIFICACAO} semanas antes da data da base aparecem sombreadas e marcadas "em notificação" nos gráficos
de série. O corte de {SEMANAS_EM_NOTIFICACAO} semanas é onde a série nacional quebra: cerca de 50 casos por semana
até 20/07/2026 e 21, 23, 14 e 3 nas quatro semanas seguintes (base de 24/08/2026). Só existe uma versão da base no
histórico do projeto, então não foi possível medir a defasagem comparando bases de datas diferentes; o número é
uma leitura da própria série, e a faixa é só um aviso: os números dessas semanas não foram alterados.

**Comorbidades múltiplas.** Muitos pacientes têm mais de uma comorbidade registrada, então os grupos "com" e
"sem" se sobrepõem. Por exemplo, parte do grupo "sem Diabetes" pode ter doença cardiovascular. As taxas não
isolam o efeito de uma comorbidade independente das demais.

**O que os dados não medem.** A idade não está nesta análise e pesa muito na letalidade. Quando uma comorbidade
aparece com letalidade menor que a de quem não a tem (a asma, por exemplo), isso pode refletir diferenças entre
os grupos que a base não mede; não indica proteção.

**Tabagismo fora.** O campo existe no formulário oficial, mas vem vazio em todos os anos na prática, então foi
excluído em vez de mostrar uma comorbidade sem dado por trás.

**Vacinação.** A linha tracejada na série semanal marca o início da vacinação no Brasil ({DATA_INICIO_VACINACAO:%d/%m/%Y}) apenas como
referência temporal, sem sugerir relação de causa e efeito com a curva de casos.
        """
    )
