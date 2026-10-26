"""Fixtures compartilhadas: Parquets da amostra sintética e comparação SQL x pandas."""

from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from conversao import csv_para_parquet

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CSVS_SINTETICOS = {2020: FIXTURES / "INFLUD20-sintetico.csv", 2021: FIXTURES / "INFLUD21-sintetico.csv"}


@pytest.fixture(scope="session")
def csvs_sinteticos() -> dict[int, Path]:
    return CSVS_SINTETICOS


@pytest.fixture(scope="session")
def pasta_parquets(tmp_path_factory, csvs_sinteticos) -> Path:
    """Pasta com ano=AAAA/casos.parquet das duas amostras sintéticas."""
    pasta = tmp_path_factory.mktemp("detalhado")
    for ano, csv in csvs_sinteticos.items():
        csv_para_parquet(csv, pasta / f"ano={ano}" / "casos.parquet")
    return pasta


@pytest.fixture
def assert_iguais():
    """Compara dois DataFrames na mesma ordem de linhas: contagens exatas, só as taxas com tolerância."""

    def comparar(obtido: pd.DataFrame, esperado: pd.DataFrame) -> None:
        assert list(obtido.columns) == list(esperado.columns)
        taxas = [c for c in esperado.columns if c.startswith("taxa_letalidade")]
        exatas = [c for c in esperado.columns if c not in taxas]
        assert_frame_equal(obtido[exatas], esperado[exatas], check_exact=True)
        if taxas:
            assert_frame_equal(obtido[taxas], esperado[taxas], check_exact=False, rtol=1e-12)

    return comparar
