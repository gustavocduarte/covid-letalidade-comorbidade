"""Aviso de casos sem estado no dashboard: lógica de leitura do relatório e a tela renderizada."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import qualidade
from config import ALTURA_MAPA_PX, CAMINHO_GEOJSON, LARGURA_REFERENCIA_MAPA_PX, PAGINAS
from mapa import enquadramento, limites_do_geojson
from qualidade import aviso_casos_sem_estado

DASHBOARD = Path(__file__).resolve().parent.parent / "src" / "dashboard.py"


def _tela_de_tempo() -> AppTest:
    """A página "Linha do tempo e estados", onde ficam o mapa e o aviso dos casos sem estado."""
    pagina = next(p for p in PAGINAS if p.titulo == "Linha do tempo e estados")
    return AppTest.from_file(str(DASHBOARD), default_timeout=120).run().switch_page(pagina.arquivo).run()


def _relatorio(caminho: Path, *, aprovado: bool, sem_uf: int) -> Path:
    caminho.write_text(json.dumps({"aprovado": aprovado, "totais": {"sem_uf": sem_uf}}), encoding="utf-8")
    return caminho


@pytest.fixture
def relatorio_em(tmp_path, monkeypatch):
    """Aponta o dashboard para um relatório no tmp_path (None = arquivo ausente)."""

    def apontar(*, aprovado: bool | None = None, sem_uf: int = 0) -> None:
        caminho = tmp_path / "relatorio_qualidade.json"
        if aprovado is not None:
            _relatorio(caminho, aprovado=aprovado, sem_uf=sem_uf)
        monkeypatch.setattr(qualidade, "CAMINHO_RELATORIO", caminho)

    return apontar


@pytest.mark.parametrize(("aprovado", "sem_uf", "esperado"), [
    (None, 0, None),  # arquivo ausente
    (False, 333, None),  # reprovado: os CSVs exibidos são os da versão anterior
    (True, 0, None),
    (True, 333, "333 casos sem estado informado não entram no mapa."),
    (True, 1, "1 caso sem estado informado não entra no mapa."),
    (True, 1234, "1.234 casos sem estado informado não entram no mapa."),
])
def test_aviso_so_com_relatorio_aprovado_e_casos_sem_estado(relatorio_em, aprovado, sem_uf, esperado):
    relatorio_em(aprovado=aprovado, sem_uf=sem_uf)

    assert aviso_casos_sem_estado() == esperado


def test_aviso_soma_uf_vazia_e_uf_invalida(relatorio_em):
    relatorio_em(aprovado=True, sem_uf=3)
    qualidade.CAMINHO_RELATORIO.write_text(
        json.dumps({"aprovado": True, "totais": {"sem_uf": 3, "uf_invalida": 2}}), encoding="utf-8",
    )

    assert aviso_casos_sem_estado() == "5 casos sem estado informado não entram no mapa."


def test_relatorio_ilegivel_nao_gera_aviso(relatorio_em):
    relatorio_em(aprovado=True, sem_uf=5)
    qualidade.CAMINHO_RELATORIO.write_text("{ isto não é json", encoding="utf-8")
    assert aviso_casos_sem_estado() is None

    qualidade.CAMINHO_RELATORIO.write_text(json.dumps({"aprovado": True}), encoding="utf-8")
    assert aviso_casos_sem_estado() is None


def _avisos_na_tela() -> list[str]:
    tela = _tela_de_tempo()
    assert not tela.exception
    return [info.value for info in tela.info if "sem estado informado" in info.value]


@pytest.mark.parametrize(("aprovado", "sem_uf", "esperado"), [
    (None, 0, []),
    (False, 333, []),
    (True, 0, []),
    (True, 333, ["333 casos sem estado informado não entram no mapa."]),
])
def test_dashboard_mostra_o_aviso_so_quando_cabe(relatorio_em, aprovado, sem_uf, esperado):
    relatorio_em(aprovado=aprovado, sem_uf=sem_uf)

    assert _avisos_na_tela() == esperado


def test_dashboard_com_o_relatorio_versionado_avisa_dos_333_casos():
    assert _avisos_na_tela() == ["333 casos sem estado informado não entram no mapa."]


def test_mapa_de_estados_nao_depende_de_mapa_base_externo():
    tela = _tela_de_tempo()
    assert not tela.exception
    assert "Letalidade por estado" in " ".join(h.proto.body for h in tela.get("html"))
    # O gráfico do mapa é o que tem a camada choroplethmap; o estilo precisa ser embutido (sem rede).
    mapas = [json.loads(g.proto.spec) for g in tela.get("plotly_chart")]
    mapas = [m for m in mapas if any(t["type"] == "choroplethmap" for t in m["data"])]
    assert len(mapas) == 1
    estilo = mapas[0]["layout"]["map"]["style"]
    # estilo embutido: sem fonte de tiles (o antigo "carto-positron" baixava o mapa-base de um CDN)
    assert isinstance(estilo, dict) and estilo["sources"] == {}
    assert {camada["type"] for camada in estilo["layers"]} == {"background"}


def test_mapa_de_estados_usa_o_enquadramento_calculado_do_geojson():
    tela = _tela_de_tempo()
    mapas = [json.loads(g.proto.spec) for g in tela.get("plotly_chart")]
    mapa = next(m for m in mapas if any(t["type"] == "choroplethmap" for t in m["data"]))

    limites = limites_do_geojson(json.loads(CAMINHO_GEOJSON.read_text(encoding="utf-8")))
    centro, zoom = enquadramento(limites, LARGURA_REFERENCIA_MAPA_PX, ALTURA_MAPA_PX)
    assert mapa["layout"]["map"]["zoom"] == pytest.approx(zoom)
    assert mapa["layout"]["map"]["center"] == pytest.approx(centro)
