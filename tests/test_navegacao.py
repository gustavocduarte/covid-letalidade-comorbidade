"""Navegação por barra lateral: as duas páginas, a padrão, o cabeçalho de cada uma e o rodapé."""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from barra_lateral import data_da_base
from config import PAGINAS, URL_REPOSITORIO

SRC = Path(__file__).resolve().parent.parent / "src"
DASHBOARD = SRC / "dashboard.py"


@pytest.fixture(scope="module")
def tela_inicial() -> AppTest:
    return AppTest.from_file(str(DASHBOARD), default_timeout=120).run()


def _pagina(titulo: str):
    return next(p for p in PAGINAS if p.titulo == titulo)


def test_paginas_tem_titulos_arquivos_e_enderecos_unicos_e_uma_padrao():
    assert len({p.titulo for p in PAGINAS}) == len(PAGINAS)
    assert len({p.url for p in PAGINAS}) == len(PAGINAS)
    assert all((SRC / p.arquivo).is_file() for p in PAGINAS)
    assert [p.titulo for p in PAGINAS if p.padrao] == ["Comorbidades"]


def test_barra_lateral_lista_as_paginas_na_ordem(tela_inicial):
    assert not tela_inicial.exception
    assert [link.proto.label for link in tela_inicial.sidebar.get("page_link")] == [
        "Comorbidades", "Linha do tempo e estados",
    ]


def test_abre_na_pagina_comorbidades_com_a_descricao(tela_inicial):
    assert "Explorar uma comorbidade" in [s.value for s in tela_inicial.subheader]
    legendas = [c.value for c in tela_inicial.caption]
    assert all(descricao in legendas for descricao in _pagina("Comorbidades").descricoes)


def test_pagina_linha_do_tempo_e_estados_abre_sem_erro_e_com_sua_descricao(tela_inicial):
    pagina = _pagina("Linha do tempo e estados")

    tela = tela_inicial.switch_page(pagina.arquivo).run()

    assert not tela.exception
    assert "Letalidade de COVID por estado" in [s.value for s in tela.subheader]
    assert pagina.descricoes[0] in [c.value for c in tela.caption]
    assert "Explorar uma comorbidade" not in [s.value for s in tela.subheader]


def test_rodape_traz_a_fonte_a_data_da_base_e_o_link_do_codigo(tela_inicial):
    legendas = [c.value for c in tela_inicial.sidebar.caption]

    assert "Fonte: SIVEP-Gripe (OpenDataSUS)" in legendas
    assert "Base do OpenDataSUS de 24/08/2026" in legendas
    assert any(URL_REPOSITORIO in m.value for m in tela_inicial.sidebar.markdown)


def test_data_da_base_e_a_mais_recente_dos_nomes_dos_arquivos():
    urls = {
        2020: "https://exemplo.invalid/SRAG/2020/INFLUD20-23-03-2026.csv",
        2021: "https://exemplo.invalid/SRAG/2021/INFLUD21-24-08-2026.csv",
        2022: "https://exemplo.invalid/SRAG/2022/INFLUD22-01-12-2025.csv",
    }

    assert data_da_base(urls) == date(2026, 8, 24)
    assert data_da_base({2020: "https://exemplo.invalid/sem-data.csv"}) is None
    assert data_da_base({}) is None
