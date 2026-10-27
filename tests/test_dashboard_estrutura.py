"""Regras de estrutura do dashboard: o que ele pode ler e quais APIs do Streamlit evita."""

from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"


def test_nenhum_modulo_usa_use_container_width():
    # parâmetro obsoleto do Streamlit: a largura vai por width="stretch"
    usam = [p.name for p in SRC.glob("*.py") if "use_container_width" in p.read_text(encoding="utf-8")]
    assert usam == []
