"""Deixa os módulos de src/ importáveis nos testes (ex: `from transform import ...`),
do mesmo jeito que já funciona quando os scripts se importam entre si dentro de src/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
