"""Rótulos de data em português para os eixos dos gráficos (o Plotly só traz os meses em inglês)."""

import pandas as pd

MESES_ABREVIADOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
LIMITE_MESES_TRIMESTRAL = 36
LIMITE_MESES_SEMESTRAL = 84


def passo_em_meses(inicio: pd.Timestamp, fim: pd.Timestamp) -> int:
    """Intervalo entre marcas do eixo: quanto mais longo o período, mais espaçadas (3, 6 ou 12 meses)."""
    meses = (fim.year - inicio.year) * 12 + fim.month - inicio.month
    if meses <= LIMITE_MESES_TRIMESTRAL:
        return 3
    return 6 if meses <= LIMITE_MESES_SEMESTRAL else 12


def marcas_de_data(inicio: pd.Timestamp, fim: pd.Timestamp) -> tuple[list[pd.Timestamp], list[str]]:
    """Posições (dia 1 de meses alinhados ao passo, de janeiro em diante) e textos "abr/21" para o eixo de datas."""
    passo = passo_em_meses(inicio, fim)
    posicoes, textos = [], []
    atual = pd.Timestamp(year=inicio.year, month=1, day=1)
    while atual <= fim:
        if atual >= inicio:
            posicoes.append(atual)
            textos.append(f"{MESES_ABREVIADOS[atual.month - 1]}/{atual:%y}")
        atual += pd.DateOffset(months=passo)
    return posicoes, textos
