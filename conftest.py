"""Deixa os módulos de src/ importáveis nos testes (ex: `from transform import ...`),
do mesmo jeito que já funciona quando os scripts se importam entre si dentro de src/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "golden: roda o pipeline completo sobre data/raw (~4,8 GB, ~3 min); só sob demanda "
        "(pytest -m golden), pulado no CI e sem os CSVs brutos",
    )
    # Fora da execução padrão; `-m golden` (ou qualquer outro -m) sobrescreve.
    if not config.option.markexpr:
        config.option.markexpr = "not golden"
