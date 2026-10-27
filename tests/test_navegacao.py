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


def _html(tela: AppTest) -> str:
    return " ".join(h.proto.body for h in tela.get("html"))


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
    assert "Explorar uma comorbidade" in _html(tela_inicial)
    legendas = [c.value for c in tela_inicial.caption]
    assert all(descricao in legendas for descricao in _pagina("Comorbidades").descricoes)


def test_pagina_linha_do_tempo_e_estados_abre_sem_erro_e_com_sua_descricao(tela_inicial):
    pagina = _pagina("Linha do tempo e estados")

    tela = tela_inicial.switch_page(pagina.arquivo).run()

    assert not tela.exception
    assert "Letalidade de COVID por estado" in [s.value for s in tela.subheader]
    assert pagina.descricoes[0] in [c.value for c in tela.caption]
    assert "Explorar uma comorbidade" not in _html(tela)


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


def test_explorar_uma_comorbidade_acompanha_a_escolha():
    tela_nova = AppTest.from_file(str(DASHBOARD), default_timeout=120).run()
    seletor = next(s for s in tela_nova.selectbox if s.label == "Comorbidade")
    assert seletor.value == "Doença Renal Crônica"  # a de maior risco abre escolhida
    assert "53,3%" in _html(tela_nova)

    tela = seletor.select("Asma").run()

    html = _html(tela)
    assert not tela.exception
    assert "27,1%" in html and "-11,2 p.p." in html


def test_tabela_completa_tem_onze_linhas_numericas_e_botao_de_baixar_o_csv():
    tela = AppTest.from_file(str(DASHBOARD), default_timeout=120).run()

    assert not tela.exception
    tabela = tela.dataframe[0].value
    assert len(tabela) == 11 and tabela["taxa_com"].is_monotonic_decreasing
    assert tabela["casos_com"].iloc[0] == 78513  # número, não texto: a ordenação por coluna fica numérica
    assert [b.proto.label for b in tela.get("download_button")] == ["Baixar CSV"]
