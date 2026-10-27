"""Enquadramento do mapa: limites do GeoJSON e zoom/centro que acomodam o Brasil no quadro."""

import json
import math

import pytest

from config import CAMINHO_GEOJSON
from mapa import TILE_PX, _y_mercator, enquadramento, limites_do_geojson


def _geojson(*geometrias: dict) -> dict:
    return {"features": [{"geometry": g} for g in geometrias]}


def test_limites_percorrem_polygon_e_multipolygon():
    poligono = {"type": "Polygon", "coordinates": [[[-50.0, -10.0], [-40.0, -10.0], [-40.0, 0.0], [-50.0, -10.0]]]}
    multi = {"type": "MultiPolygon", "coordinates": [[[[-60.0, 3.0], [-59.0, 3.0], [-59.0, 4.0], [-60.0, 3.0]]]]}

    assert limites_do_geojson(_geojson(poligono, multi)) == (-60.0, -40.0, -10.0, 4.0)


def test_limites_do_geojson_versionado_sao_os_do_brasil():
    limites = limites_do_geojson(json.loads(CAMINHO_GEOJSON.read_text(encoding="utf-8")))

    assert limites == pytest.approx((-73.99, -29.30, -33.75, 5.27), abs=0.01)


def _tamanho_em_px(limites, zoom):
    lon_min, lon_max, lat_min, lat_max = limites
    mundo = TILE_PX * 2**zoom
    return (
        math.radians(lon_max - lon_min) * mundo / (2 * math.pi),
        (_y_mercator(lat_max) - _y_mercator(lat_min)) * mundo / (2 * math.pi),
    )


@pytest.mark.parametrize(("largura", "altura"), [(1100, 600), (640, 600), (400, 600), (1100, 300)])
def test_o_quadro_acomoda_os_limites_e_o_eixo_mais_apertado_fica_cheio(largura, altura):
    limites = (-73.99, -29.30, -33.75, 5.27)

    _, zoom = enquadramento(limites, largura, altura, folga=0.94)

    largura_px, altura_px = _tamanho_em_px(limites, zoom)
    assert largura_px <= largura * 0.94 + 1e-6 and altura_px <= altura * 0.94 + 1e-6
    assert max(largura_px / largura, altura_px / altura) == pytest.approx(0.94)


def test_centro_fica_no_meio_dos_limites():
    centro, _ = enquadramento((-74.0, -29.0, -34.0, 6.0), 640, 600)

    assert centro["lon"] == pytest.approx(-51.5)
    # no Mercator o meio do quadro fica um pouco ao sul do meio das latitudes
    assert -34.0 < centro["lat"] < -14.0
    assert _y_mercator(centro["lat"]) == pytest.approx((_y_mercator(-34.0) + _y_mercator(6.0)) / 2)
