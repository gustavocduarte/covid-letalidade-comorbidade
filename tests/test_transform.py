"""Testes automatizados para a lógica mais importante de transform.py."""

import math

import pandas as pd
import pytest

from transform import (
    COMORBIDADES,
    agregar_todos_anos,
    carregar_casos_covid,
    contar_desfechos,
    letalidade_por_comorbidade,
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
