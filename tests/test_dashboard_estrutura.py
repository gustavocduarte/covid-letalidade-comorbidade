"""Regras de estrutura do dashboard: o que ele pode ler e quais APIs do Streamlit evita."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"


def test_nenhum_modulo_usa_use_container_width():
    # parâmetro obsoleto do Streamlit: a largura vai por width="stretch"
    usam = [p.name for p in SRC.glob("*.py") if "use_container_width" in p.read_text(encoding="utf-8")]
    assert usam == []


def _modulos_do_dashboard() -> list[Path]:
    nomes = ["dashboard", "barra_lateral", "componentes", "css", "mapa", "qualidade"]
    return [SRC / f"{nome}.py" for nome in nomes] + sorted((SRC / "paginas").glob("*.py"))


def test_dashboard_so_le_os_dados_publicados_e_nao_roda_o_pipeline():
    # o dashboard publicado só tem os CSVs versionados, o relatório e o GeoJSON: nada de data/raw nem do ETL
    proibidos = {"duckdb", "pipeline", "consultas", "conversao", "extract", "validacao", "load", "geo", "cli", "estado"}
    importados = {}
    for caminho in _modulos_do_dashboard():
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados.setdefault(caminho.name, set()).update(a.name.split(".")[0] for a in no.names)
            elif isinstance(no, ast.ImportFrom) and no.module:
                importados.setdefault(caminho.name, set()).add(no.module.split(".")[0])

    assert {nome: sorted(mods & proibidos) for nome, mods in importados.items() if mods & proibidos} == {}
    fontes = " ".join(c.read_text(encoding="utf-8") for c in _modulos_do_dashboard())
    assert "PASTA_RAW" not in fontes and "data/raw" not in fontes
