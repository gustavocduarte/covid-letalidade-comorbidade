"""Estado do pipeline incremental: leitura tolerante, gravação atômica e a decisão de pular um ano."""

import estado
from config import NOME_ESTADO_PIPELINE, VERSAO_CONVERSAO

URL = "https://exemplo.invalid/SRAG/2020/INFLUD20.csv"


def _preparar(tmp_path):
    csv = tmp_path / "INFLUD20.csv"
    csv.write_text("a;b\n1;2\n", encoding="utf-8")
    parquet = tmp_path / "ano=2020" / "casos.parquet"
    parquet.parent.mkdir()
    parquet.write_bytes(b"x")
    return csv, parquet, estado.assinatura_csv(csv, URL)


def test_grava_e_le_o_mesmo_estado(tmp_path):
    csv, _, assinatura = _preparar(tmp_path)
    registros = {"2020": estado.registro_do_ano(assinatura, 14)}

    estado.gravar_estado(tmp_path / "pasta_nova", registros)

    assert estado.ler_estado(tmp_path / "pasta_nova") == registros
    assert registros["2020"]["tamanho_csv"] == csv.stat().st_size
    assert sorted(p.name for p in (tmp_path / "pasta_nova").iterdir()) == [NOME_ESTADO_PIPELINE]  # sem .parcial


def test_estado_ausente_ilegivel_ou_de_outra_versao_vale_por_vazio(tmp_path):
    assert estado.ler_estado(tmp_path) == {}

    for conteudo in ("{não é json", '{"versao": 99, "anos": {"2020": {}}}', '{"versao": 1}', "[]"):
        (tmp_path / NOME_ESTADO_PIPELINE).write_text(conteudo, encoding="utf-8")
        assert estado.ler_estado(tmp_path) == {}, conteudo


def test_ano_em_dia_quando_tudo_confere(tmp_path):
    _, parquet, assinatura = _preparar(tmp_path)

    assert estado.ano_em_dia(estado.registro_do_ano(assinatura, 14), assinatura, parquet)


def test_ano_nao_esta_em_dia(tmp_path):
    csv, parquet, assinatura = _preparar(tmp_path)
    registro = estado.registro_do_ano(assinatura, 14)

    assert not estado.ano_em_dia(None, assinatura, parquet)
    assert not estado.ano_em_dia(registro, estado.assinatura_csv(csv, URL + "?novo"), parquet)  # URL mudou
    assert not estado.ano_em_dia({**registro, "versao_conversao": VERSAO_CONVERSAO + 1}, assinatura, parquet)
    csv.write_text("a;b\n1;2\n3;4\n", encoding="utf-8")  # tamanho e data mudaram
    assert not estado.ano_em_dia(registro, estado.assinatura_csv(csv, URL), parquet)
    parquet.unlink()  # o disco manda: sem Parquet, reconverte
    assert not estado.ano_em_dia(registro, assinatura, parquet)
