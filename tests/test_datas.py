"""Rótulos de data em português para os eixos."""

import pandas as pd

from datas import marcas_de_data, passo_em_meses


def test_passo_cresce_com_o_periodo():
    assert passo_em_meses(pd.Timestamp("2021-01-01"), pd.Timestamp("2022-06-01")) == 3
    assert passo_em_meses(pd.Timestamp("2020-02-10"), pd.Timestamp("2026-08-24")) == 6
    assert passo_em_meses(pd.Timestamp("2000-01-01"), pd.Timestamp("2026-01-01")) == 12


def test_marcas_usam_meses_em_portugues_e_comecam_dentro_do_periodo():
    posicoes, textos = marcas_de_data(pd.Timestamp("2020-02-10"), pd.Timestamp("2022-01-03"))

    assert textos == ["abr/20", "jul/20", "out/20", "jan/21", "abr/21", "jul/21", "out/21", "jan/22"][:len(textos)]
    assert posicoes[0] == pd.Timestamp("2020-04-01") and len(posicoes) == len(textos)
    assert all(pd.Timestamp("2020-02-10") <= p <= pd.Timestamp("2022-01-03") for p in posicoes)


def test_periodo_longo_tem_marcas_semestrais_sem_nomes_em_ingles():
    _, textos = marcas_de_data(pd.Timestamp("2020-02-10"), pd.Timestamp("2026-08-24"))

    assert textos[:3] == ["jul/20", "jan/21", "jul/21"]
    assert not any(m in " ".join(textos) for m in ("Apr", "Oct", "Aug", "Dec"))
