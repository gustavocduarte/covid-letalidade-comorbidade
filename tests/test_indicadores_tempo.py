"""Números da página Linha do tempo e estados."""

from datetime import date

import pandas as pd

from config import DATA_INICIO_VACINACAO
from indicadores_tempo import kpis_tempo, normalizar_pelo_pico, resumo_por_estado

NOMES = {"AA": "Alfa", "BB": "Beta", "CC": "Gama"}


def _semanal_estado() -> pd.DataFrame:
    semanas = pd.date_range("2021-01-04", periods=6, freq="7D")
    return pd.DataFrame({
        "semana": list(semanas) * 3,
        "sigla": ["AA"] * 6 + ["BB"] * 6 + ["CC"] * 6,
        "casos": [10, 100, 50, 9, 5, 2,      # AA: pico na 2ª semana; abaixo de 10 na 4ª (2 semanas depois)
                  100, 60, 50, 40, 30, 20,   # BB: pico na 1ª; nunca cai abaixo de 10
                  5, 20, 100, 80, 9, 3],     # CC: pico na 3ª; abaixo de 10 na 5ª (2 semanas depois)
    })


def test_resumo_por_estado_acha_pico_e_cauda_e_deixa_sem_cauda_por_ultimo():
    resumo = resumo_por_estado(_semanal_estado(), NOMES)

    assert resumo["nome"].tolist() == ["Alfa", "Gama", "Beta"]  # empate de cauda desempata pelo nome
    assert resumo["semanas_ate_cauda"].tolist()[:2] == [2, 2] and pd.isna(resumo["semanas_ate_cauda"].iloc[2])
    alfa = resumo.iloc[0]
    assert alfa["semana_pico"] == pd.Timestamp("2021-01-11") and alfa["casos_pico"] == 100


def test_kpis_do_tempo_trazem_pico_vacinacao_cauda_e_semana_recente():
    semanal = pd.DataFrame({
        "semana": pd.to_datetime(["2021-03-15", "2021-03-08", "2026-08-17"]), "casos": [300, 65000, 1234],
    })
    resumo = resumo_por_estado(_semanal_estado(), NOMES)

    pico, vacina, cauda, recente = kpis_tempo(semanal, resumo, date(2026, 8, 24))

    assert (pico.valor, pico.linha) == ("65.000", "casos na semana de 08/03/2021")
    assert vacina.valor == f"{DATA_INICIO_VACINACAO:%d/%m/%Y}"
    assert (cauda.valor, cauda.linha) == ("2 semanas", "Alfa e Gama")
    assert (recente.valor, recente.linha) == ("1.234", "casos na semana de 17/08/2026 (base de 24/08/2026), ainda em notificação")


def test_kpi_da_cauda_resume_quando_muitos_estados_empatam():
    resumo = pd.DataFrame({"nome": list("ABCDE"), "semanas_ate_cauda": pd.array([7] * 5, dtype="Int64")})
    semanal = pd.DataFrame({"semana": pd.to_datetime(["2021-03-08"]), "casos": [1]})

    assert kpis_tempo(semanal, resumo)[2].linha == "5 estados empatados"


def test_normalizar_pelo_pico_poe_o_pico_de_cada_estado_em_100():
    curvas = normalizar_pelo_pico(_semanal_estado())

    por_estado = curvas.groupby("sigla")["pct_do_pico"]
    assert por_estado.max().tolist() == [100, 100, 100]
    assert curvas.loc[(curvas["sigla"] == "AA") & (curvas["casos"] == 50), "pct_do_pico"].iloc[0] == 50


def test_cartao_da_semana_recente_sem_data_da_base_nao_cita_a_base():
    resumo = pd.DataFrame({"nome": ["A"], "semanas_ate_cauda": pd.array([7], dtype="Int64")})
    semanal = pd.DataFrame({"semana": pd.to_datetime(["2026-08-17"]), "casos": [3]})

    assert kpis_tempo(semanal, resumo)[3].linha == "casos na semana de 17/08/2026, ainda em notificação"

