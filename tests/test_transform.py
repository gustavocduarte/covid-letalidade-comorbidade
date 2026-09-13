"""Testes automatizados para a lógica mais importante de transform.py."""

import math

import pandas as pd
import pytest

from transform import (
    COMORBIDADES,
    agregar_estados_todos_anos,
    agregar_todos_anos,
    carregar_casos_covid,
    contar_desfechos,
    letalidade_por_comorbidade,
    letalidade_por_estado,
    serie_semanal_casos_covid,
    serie_semanal_por_comorbidade,
    serie_semanal_por_estado,
)


def _linha_base(**overrides) -> dict:
    """Uma linha de caso de COVID com todas as comorbidades = 2 (Não), sobrescrevendo
    só o que o teste precisar (ex: EVOLUCAO, ou uma comorbidade específica = 1)."""
    linha = {"EVOLUCAO": None}
    linha.update({comorbidade: 2 for comorbidade in COMORBIDADES})
    linha.update(overrides)
    return linha


def test_taxa_letalidade_nunca_passa_de_100_por_cento():
    """A taxa de letalidade (óbitos / (óbitos + curas)) não pode nunca passar de 1.0
    (100%), nem em casos extremos como "todo mundo com RENAL morreu"."""
    linhas = (
        [_linha_base(RENAL=1, EVOLUCAO=2) for _ in range(5)]  # RENAL: 100% óbito
        + [_linha_base(RENAL=2, EVOLUCAO=1) for _ in range(5)]  # sem RENAL: 100% cura
        + [_linha_base(ASMA=1, EVOLUCAO=1) for _ in range(3)]
        + [_linha_base(ASMA=1, EVOLUCAO=2) for _ in range(2)]
    )
    covid = pd.DataFrame(linhas)

    tabela = letalidade_por_comorbidade(covid)

    taxas = pd.concat([tabela["taxa_letalidade_com"], tabela["taxa_letalidade_sem"]]).dropna()
    assert (taxas <= 1.0).all()
    assert (taxas >= 0.0).all()

    # E o caso extremo deve realmente bater no teto: RENAL com 100% de óbito == 1.0.
    taxa_renal_com = tabela.loc[tabela["comorbidade"] == "RENAL", "taxa_letalidade_com"].iloc[0]
    assert taxa_renal_com == 1.0


def test_letalidade_por_comorbidade_protege_divisao_por_zero():
    """Quando uma comorbidade não tem NENHUM caso com desfecho conhecido (só ignorados),
    a taxa deve virar NaN, não travar o programa com ZeroDivisionError — foi exatamente
    isso que aconteceu de verdade com TABAG (ver histórico do projeto)."""
    linhas = (
        [_linha_base(SIND_DOWN=1, EVOLUCAO=9) for _ in range(4)]  # só ignorado, 0 conhecido
        + [_linha_base(SIND_DOWN=2, EVOLUCAO=1) for _ in range(4)]
    )
    covid = pd.DataFrame(linhas)

    tabela = letalidade_por_comorbidade(covid)

    taxa_sind_down_com = tabela.loc[tabela["comorbidade"] == "SIND_DOWN", "taxa_letalidade_com"].iloc[0]
    assert math.isnan(taxa_sind_down_com)


def test_contar_desfechos_conta_certo():
    """Contagem simples e direta de óbitos (EVOLUCAO=2) e curas (EVOLUCAO=1)."""
    df = pd.DataFrame({"EVOLUCAO": [1, 1, 2, 2, 2, 9, None]})
    obitos, curas = contar_desfechos(df)
    assert obitos == 3
    assert curas == 2


def test_agregar_todos_anos_soma_antes_de_dividir():
    """A taxa agregada de vários anos deve ser (soma de óbitos) / (soma de desfechos
    conhecidos) — não a média simples das taxas anuais, que trataria um ano pequeno
    igual a um ano grande."""
    ano_pequeno = pd.DataFrame([{
        "comorbidade": "RENAL", "casos_com": 10, "obitos_com": 9, "desfecho_conhecido_com": 10,
        "taxa_letalidade_com": 0.9,
        "casos_sem": 10, "obitos_sem": 1, "desfecho_conhecido_sem": 10, "taxa_letalidade_sem": 0.1,
    }])
    ano_grande = pd.DataFrame([{
        "comorbidade": "RENAL", "casos_com": 1000, "obitos_com": 100, "desfecho_conhecido_com": 1000,
        "taxa_letalidade_com": 0.1,
        "casos_sem": 1000, "obitos_sem": 100, "desfecho_conhecido_sem": 1000, "taxa_letalidade_sem": 0.1,
    }])

    agregado = agregar_todos_anos([ano_pequeno, ano_grande])
    taxa_com = agregado.loc[agregado["comorbidade"] == "RENAL", "taxa_letalidade_com"].iloc[0]

    media_simples = (0.9 + 0.1) / 2  # o jeito ERRADO de agregar, só pra comparação
    taxa_correta = (9 + 100) / (10 + 1000)  # soma de óbitos / soma de desfechos

    assert taxa_com == pytest.approx(taxa_correta)
    assert taxa_com != pytest.approx(media_simples)


def test_carregar_casos_covid_filtra_so_covid(tmp_path):
    """carregar_casos_covid deve manter só as linhas com CLASSI_FIN == 5 (SRAG por
    COVID-19) — os outros valores (1-4) são outras causas de SRAG, não COVID."""
    colunas = ["CLASSI_FIN", "EVOLUCAO", "DT_SIN_PRI", "SG_UF"] + COMORBIDADES
    linhas = []
    for classi_fin in [1, 2, 3, 4, 5, 5, 5]:
        linha = {"CLASSI_FIN": classi_fin, "EVOLUCAO": 1, "DT_SIN_PRI": "2020-05-01", "SG_UF": "SP"}
        linha.update({comorbidade: 2 for comorbidade in COMORBIDADES})
        linhas.append(linha)
    df_bruto = pd.DataFrame(linhas, columns=colunas)

    caminho_csv = tmp_path / "sivep_teste.csv"
    df_bruto.to_csv(caminho_csv, sep=";", encoding="latin1", index=False)

    covid = carregar_casos_covid(caminho_csv)

    assert len(covid) == 3
    assert (covid["CLASSI_FIN"] == 5).all()


def test_serie_semanal_casos_covid_conta_por_semana_e_ignora_data_invalida():
    """Casos na mesma semana civil (baseada em DT_SIN_PRI) somam juntos; casos com
    data ausente/inválida são excluídos da série, não travam o programa."""
    linhas = (
        [_linha_base(DT_SIN_PRI="2020-01-06") for _ in range(3)]  # segunda-feira
        + [_linha_base(DT_SIN_PRI="2020-01-08") for _ in range(2)]  # mesma semana (quarta)
        + [_linha_base(DT_SIN_PRI="2020-01-13") for _ in range(1)]  # semana seguinte
        + [_linha_base(DT_SIN_PRI=None) for _ in range(4)]  # data ausente, deve ser ignorado
    )
    covid = pd.DataFrame(linhas)

    serie = serie_semanal_casos_covid(covid)

    assert serie["casos"].sum() == 6  # os 4 com data ausente não entram
    assert len(serie) == 2  # duas semanas distintas
    assert serie.loc[serie["semana"] == pd.Timestamp("2020-01-06"), "casos"].iloc[0] == 5


def test_serie_semanal_por_comorbidade_conta_cada_uma_de_forma_independente():
    """Um caso com duas comorbidades marcadas deve entrar na contagem semanal de
    cada uma delas, de forma independente (não é mutuamente exclusivo)."""
    linhas = [
        _linha_base(RENAL=1, ASMA=1, DT_SIN_PRI="2020-01-06"),
        _linha_base(RENAL=1, DT_SIN_PRI="2020-01-06"),
    ]
    covid = pd.DataFrame(linhas)

    serie = serie_semanal_por_comorbidade(covid)

    casos_renal = serie.loc[serie["comorbidade"] == "RENAL", "casos"].sum()
    casos_asma = serie.loc[serie["comorbidade"] == "ASMA", "casos"].sum()
    assert casos_renal == 2  # os dois casos têm RENAL
    assert casos_asma == 1  # só o primeiro também tem ASMA


def test_serie_semanal_por_estado_agrupa_por_sigla():
    """Casos da mesma semana e mesmo estado somam juntos; estados diferentes
    ficam em linhas separadas."""
    linhas = (
        [_linha_base(SG_UF="SP", DT_SIN_PRI="2020-01-06") for _ in range(3)]
        + [_linha_base(SG_UF="RJ", DT_SIN_PRI="2020-01-06") for _ in range(2)]
    )
    covid = pd.DataFrame(linhas)

    serie = serie_semanal_por_estado(covid)

    assert len(serie) == 2  # uma linha por (semana, estado)
    assert serie.loc[serie["sigla"] == "SP", "casos"].iloc[0] == 3
    assert serie.loc[serie["sigla"] == "RJ", "casos"].iloc[0] == 2


def test_letalidade_por_estado_protege_divisao_por_zero():
    """Mesma proteção de letalidade_por_comorbidade, agora por estado: um estado
    sem nenhum desfecho conhecido (só ignorados) deve gerar NaN, não travar."""
    linhas = (
        [_linha_base(SG_UF="AC", EVOLUCAO=9) for _ in range(3)]  # só ignorado
        + [_linha_base(SG_UF="SP", EVOLUCAO=2) for _ in range(2)]
        + [_linha_base(SG_UF="SP", EVOLUCAO=1) for _ in range(2)]
    )
    covid = pd.DataFrame(linhas)

    tabela = letalidade_por_estado(covid)

    taxa_ac = tabela.loc[tabela["sigla"] == "AC", "taxa_letalidade"].iloc[0]
    taxa_sp = tabela.loc[tabela["sigla"] == "SP", "taxa_letalidade"].iloc[0]
    assert math.isnan(taxa_ac)
    assert taxa_sp == pytest.approx(0.5)


def test_agregar_estados_todos_anos_soma_antes_de_dividir():
    """Mesmo raciocínio de agregar_todos_anos, mas por estado: soma óbitos e
    desfechos conhecidos de vários anos antes de dividir, em vez de tirar a
    média das taxas anuais (que trataria um ano pequeno igual a um ano grande)."""
    ano_pequeno = pd.DataFrame([{
        "sigla": "SP", "casos": 10, "obitos": 9, "desfecho_conhecido": 10, "taxa_letalidade": 0.9,
    }])
    ano_grande = pd.DataFrame([{
        "sigla": "SP", "casos": 1000, "obitos": 100, "desfecho_conhecido": 1000, "taxa_letalidade": 0.1,
    }])

    agregado = agregar_estados_todos_anos([ano_pequeno, ano_grande])
    taxa = agregado.loc[agregado["sigla"] == "SP", "taxa_letalidade"].iloc[0]

    taxa_correta = (9 + 100) / (10 + 1000)  # soma de óbitos / soma de desfechos
    assert taxa == pytest.approx(taxa_correta)
