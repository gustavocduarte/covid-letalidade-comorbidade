"""Apoio ao mapa: orientação dos anéis do GeoJSON para o Plotly."""


def test_geojson_para_plotly_poe_o_anel_externo_no_sentido_horario_e_os_buracos_no_anti_horario():
    from mapa import _area_assinada, geojson_para_plotly

    externo_anti_horario = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
    buraco_horario = [[1, 1], [1, 2], [2, 2], [2, 1], [1, 1]]
    geojson = {"features": [
        {"properties": {"sigla": "AA"}, "geometry": {"type": "Polygon", "coordinates": [externo_anti_horario, buraco_horario]}},
        {"properties": {"sigla": "BB"}, "geometry": {"type": "MultiPolygon", "coordinates": [[externo_anti_horario]]}},
    ]}

    orientado = geojson_para_plotly(geojson)

    externo, buraco = orientado["features"][0]["geometry"]["coordinates"]
    assert _area_assinada(externo) < 0 < _area_assinada(buraco)
    assert _area_assinada(orientado["features"][1]["geometry"]["coordinates"][0][0]) < 0
    assert _area_assinada(geojson["features"][0]["geometry"]["coordinates"][0]) > 0  # a entrada não é alterada
