"""Teste de regressão "dourado": roda o pipeline completo sobre os CSVs brutos e compara as
saídas com as versionadas em data/processed/.

Precisa dos ~4,8 GB de data/raw/, então só roda localmente. Para pular: pytest -m "not golden".
"""

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from extract import URLS_SRAG

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
PROCESSADOS = RAIZ / "data" / "processed"

# Gerados por pipeline.py (os dois últimos, em passo separado, a partir do cache detalhado).
SAIDAS = [
    "letalidade_por_comorbidade_todos_anos.csv",
    "letalidade_por_comorbidade_agregado.csv",
    "casos_covid_por_semana.csv",
    "casos_covid_semanal_por_comorbidade.csv",
    "letalidade_por_estado_agregado.csv",
    "casos_covid_detalhado.csv",
    "casos_covid_por_semana_estado.csv",
]

# Só as taxas (razão de inteiros em float) têm tolerância; contagens são exatas.
TOLERANCIA_TAXA = 1e-12

pytestmark = pytest.mark.golden


def _brutos_faltando() -> list[str]:
    return [url.split("/")[-1] for url in URLS_SRAG.values() if not (RAW / url.split("/")[-1]).exists()]


@pytest.fixture(scope="module")
def saidas_geradas(tmp_path_factory) -> Path:
    if os.environ.get("CI"):
        pytest.skip("teste dourado precisa de data/raw (~4,8 GB); roda só localmente")
    faltando = _brutos_faltando()
    if faltando:
        pytest.skip(f"data/raw incompleto, faltam {len(faltando)} CSV(s): {', '.join(faltando)}. "
                    "Rode `python src/pipeline.py` para baixá-los.")

    base = tmp_path_factory.mktemp("dourado")
    (base / "src").mkdir()
    for arquivo in (RAIZ / "src").glob("*.py"):
        (base / "src" / arquivo.name).write_bytes(arquivo.read_bytes())
    (base / "data").mkdir()
    _ligar_pasta(base / "data" / "raw", RAW)

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for script in ("pipeline.py", "gerar_serie_estado.py"):
        resultado = subprocess.run(
            [sys.executable, str(base / "src" / script)],
            cwd=base, env=env, capture_output=True, text=True, encoding="utf-8", timeout=1800, check=False,
        )
        assert resultado.returncode == 0, f"{script} falhou:\n{resultado.stdout[-2000:]}\n{resultado.stderr[-2000:]}"
    return base / "data" / "processed"


def _ligar_pasta(link: Path, alvo: Path) -> None:
    """Junction no Windows (não exige privilégio de administrador); symlink nos demais."""
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(alvo)], check=True, capture_output=True)
    else:
        link.symlink_to(alvo, target_is_directory=True)


@pytest.mark.parametrize("nome", SAIDAS)
def test_saida_igual_a_versionada(saidas_geradas, nome):
    esperado_path = PROCESSADOS / nome
    if not esperado_path.exists():
        pytest.skip(f"{nome} não existe localmente (cache ignorado pelo git)")

    gerado = pd.read_csv(saidas_geradas / nome)
    esperado = pd.read_csv(esperado_path)

    assert list(gerado.columns) == list(esperado.columns)
    colunas_taxa = [c for c in esperado.columns if c.startswith("taxa_letalidade")]
    colunas_exatas = [c for c in esperado.columns if c not in colunas_taxa]

    assert_frame_equal(gerado[colunas_exatas], esperado[colunas_exatas], check_exact=True)
    if colunas_taxa:
        assert_frame_equal(gerado[colunas_taxa], esperado[colunas_taxa], check_exact=False, rtol=TOLERANCIA_TAXA)
