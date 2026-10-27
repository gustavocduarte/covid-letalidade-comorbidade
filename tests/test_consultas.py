"""Agregações em SQL sobre a amostra sintética de tests/fixtures/, com valores calculados à mão."""

import shutil

import pandas as pd
import pytest

from consultas import (
    abrir_casos,
    letalidade_por_comorbidade_agregado,
    letalidade_por_comorbidade_por_ano,
    letalidade_por_estado_agregado,
    letalidade_por_estado_por_ano,
    serie_semanal_casos,
    serie_semanal_por_comorbidade,
    serie_semanal_por_estado,
)
from conversao import csv_para_parquet


@pytest.fixture(scope="module")
def con(pasta_parquets):
    with abrir_casos(pasta_parquets) as conexao:
        yield conexao


def test_letalidade_por_comorbidade_valores_calculados_a_mao(con):
    por_ano = letalidade_por_comorbidade_por_ano(con).set_index(["ano", "comorbidade"])

    # 2020, diabetes: com = 6 casos (3 óbitos, 1 cura); sem = 6 casos (2 óbitos, 3 curas)
    diabetes = por_ano.loc[(2020, "DIABETES")]
    assert (diabetes.casos_com, diabetes.obitos_com, diabetes.desfecho_conhecido_com) == (6, 3, 4)
    assert (diabetes.casos_sem, diabetes.obitos_sem, diabetes.desfecho_conhecido_sem) == (6, 2, 5)
    assert diabetes.taxa_letalidade_com == pytest.approx(3 / 4)
    # Comorbidade nunca preenchida: linha com zeros e taxas indefinidas, sem divisão por zero
    hematologica = por_ano.loc[(2021, "HEMATOLOGI")]
    assert hematologica.casos_com == 0
    assert pd.isna(hematologica.taxa_letalidade_com) and pd.isna(hematologica.taxa_letalidade_sem)
    assert len(por_ano) == 2 * 11


def test_letalidade_por_estado_valores_calculados_a_mao(con):
    agregado = letalidade_por_estado_agregado(con)

    # (casos, óbitos, desfechos conhecidos); o caso sem UF (2020, linha 11) e os de UF inválida (XX, ZZ) ficam de fora.
    esperado = {"MG": (3, 1, 1), "RJ": (6, 3, 5), "BA": (3, 1, 2), "SP": (7, 3, 6)}
    # taxa decrescente; o empate (BA/SP = 0,5) em ordem alfabética
    assert list(agregado["sigla"]) == list(esperado)
    for linha in agregado.itertuples():
        assert (linha.casos, linha.obitos, linha.desfecho_conhecido) == esperado[linha.sigla]


def test_serie_semanal_casos_valores_calculados_a_mao(con):
    serie = serie_semanal_casos(con)

    esperado = {
        "2020-03-02": 2, "2020-03-09": 5, "2020-03-16": 4,
        "2020-12-28": 2,  # 30/dez/2020 (arquivo de 2020) + 01/jan/2021 (arquivo de 2021)
        "2021-01-04": 5, "2021-01-11": 2,
    }
    assert dict(zip(serie["semana"].dt.strftime("%Y-%m-%d"), serie["casos"], strict=True)) == esperado
    assert serie["casos"].sum() == 20  # 22 casos de COVID menos 2 sem data válida


def test_serie_semanal_por_comorbidade_valores_calculados_a_mao(con):
    serie = serie_semanal_por_comorbidade(con)

    def da(comorbidade):
        sub = serie[serie["comorbidade"] == comorbidade]
        return dict(zip(sub["semana"].dt.strftime("%Y-%m-%d"), sub["casos"], strict=True))

    assert da("DIABETES") == {"2020-03-02": 2, "2020-03-09": 2, "2020-03-16": 1, "2021-01-04": 3, "2021-01-11": 1}
    assert da("OBESIDADE") == {"2020-03-09": 1, "2020-03-16": 1, "2021-01-04": 2}
    assert da("CARDIOPATI") == {"2020-03-02": 1, "2020-03-09": 1}
    assert da("SIND_DOWN") == {"2020-12-28": 2, "2021-01-04": 1}  # a semana da virada soma os dois anos
    assert da("ASMA") == {}  # sem casos: nenhuma linha
    assert len(serie) == 12


def test_serie_semanal_por_estado_valores_calculados_a_mao(con):
    serie = serie_semanal_por_estado(con)

    obtido = list(zip(serie["semana"].dt.strftime("%Y-%m-%d"), serie["sigla"], serie["casos"], strict=True))
    assert obtido == [
        ("2020-03-02", "SP", 2), ("2020-03-09", "MG", 2), ("2020-03-09", "RJ", 3),
        ("2020-03-16", "MG", 1), ("2020-03-16", "SP", 1),
        ("2020-12-28", "SP", 2),  # 30/dez/2020 + 01/jan/2021
        ("2021-01-04", "BA", 2), ("2021-01-04", "RJ", 2), ("2021-01-04", "SP", 1),
        ("2021-01-11", "BA", 1),
    ]
    assert serie["casos"].sum() == 17  # 20 com data válida, menos 1 sem UF e 2 com UF inválida (XX, ZZ)


def test_ano_sem_casos_de_covid_gera_as_linhas_de_zero(tmp_path, csvs_sinteticos):
    cabecalho = csvs_sinteticos[2021].read_text(encoding="utf-8").splitlines()[0]
    # só um caso que não é COVID (CLASSI_FIN = 4): o Parquet do ano sai com 0 linhas
    csv_vazio = tmp_path / "INFLUD22-sintetico.csv"
    csv_vazio.write_text(cabecalho + "\n0001;2022-01-03;2022-01-03;F;SP;X;;;1;;;2;;;;;;4;1\n", encoding="utf-8")
    csvs = {**csvs_sinteticos, 2022: csv_vazio}
    pasta = tmp_path / "detalhado"
    for ano, csv in csvs.items():
        csv_para_parquet(csv, pasta / f"ano={ano}" / "casos.parquet")

    with abrir_casos(pasta) as conexao:
        obtido = letalidade_por_comorbidade_por_ano(conexao)

    assert len(obtido) == 3 * 11
    do_ano_vazio = obtido[obtido["ano"] == 2022]
    assert len(do_ano_vazio) == 11
    assert (do_ano_vazio.filter(like="casos").sum().sum(), do_ano_vazio.filter(like="obitos").sum().sum()) == (0, 0)
    assert do_ano_vazio["taxa_letalidade_com"].isna().all()


def test_ano_fora_da_lista_nao_entra_nas_consultas(tmp_path, pasta_parquets, con):
    pasta = tmp_path / "detalhado"
    shutil.copytree(pasta_parquets, pasta)
    shutil.copytree(pasta / "ano=2021", pasta / "ano=1999")  # resto de uma execução antiga

    with abrir_casos(pasta, anos=[2020, 2021]) as conexao:
        assert conexao.execute("SELECT DISTINCT ano FROM casos ORDER BY ano").fetchall() == [(2020,), (2021,)]
        assert conexao.execute("SELECT ano FROM anos ORDER BY ano").fetchall() == [(2020,), (2021,)]
        filtrado = letalidade_por_comorbidade_por_ano(conexao)
        semanal = serie_semanal_casos(conexao)

    assert set(filtrado["ano"]) == {2020, 2021}
    assert filtrado.equals(letalidade_por_comorbidade_por_ano(con))
    assert semanal.equals(serie_semanal_casos(con))
    with abrir_casos(pasta) as todos:  # sem lista, vale a pasta inteira
        assert todos.execute("SELECT DISTINCT ano FROM casos ORDER BY ano").fetchall() == [(1999,), (2020,), (2021,)]


def test_estado_sem_desfecho_conhecido_tem_taxa_indefinida(tmp_path, csvs_sinteticos):
    cabecalho = csvs_sinteticos[2021].read_text(encoding="utf-8").splitlines()[0]
    # AC: 2 casos sem desfecho (EVOLUCAO 9 e 3); AL: 1 óbito
    linhas = [
        "0001;2022-01-03;2022-01-03;F;AC;X;;;1;;;2;;;;;;5;9",
        "0002;2022-01-04;2022-01-04;F;AC;X;;;1;;;2;;;;;;5;3",
        "0003;2022-01-05;2022-01-05;F;AL;X;;;1;;;2;;;;;;5;2",
    ]
    csv = tmp_path / "INFLUD22-sintetico.csv"
    csv.write_text("\n".join([cabecalho, *linhas]) + "\n", encoding="utf-8")
    pasta = tmp_path / "detalhado"
    csv_para_parquet(csv, pasta / "ano=2022" / "casos.parquet")

    with abrir_casos(pasta) as conexao:
        agregado = letalidade_por_estado_agregado(conexao).set_index("sigla")
        por_ano = letalidade_por_estado_por_ano(conexao).set_index("sigla")

    for tabela in (agregado, por_ano):
        ac, al = tabela.loc["AC"], tabela.loc["AL"]
        assert (ac.casos, ac.obitos, ac.desfecho_conhecido) == (2, 0, 0)
        assert pd.isna(ac.taxa_letalidade)
        assert (al.casos, al.obitos, al.desfecho_conhecido, al.taxa_letalidade) == (1, 1, 1, 1.0)


def test_empate_de_taxa_segue_a_ordem_de_comorbidades_no_agregado_e_por_ano(tmp_path, csvs_sinteticos):
    colunas = csvs_sinteticos[2021].read_text(encoding="utf-8").splitlines()[0].split(";")
    # um óbito com SIND_DOWN e ASMA: as duas empatam em 100%; na ordem alfabética ASMA viria antes
    caso = {"NU_NOTIFIC": "1", "DT_SIN_PRI": "2022-01-03", "SG_UF": "SP", "SIND_DOWN": "1", "ASMA": "1",
            "CLASSI_FIN": "5", "EVOLUCAO": "2"}
    csv = tmp_path / "INFLUD22-sintetico.csv"
    csv.write_text(";".join(colunas) + "\n" + ";".join(caso.get(c, "") for c in colunas) + "\n", encoding="utf-8")
    pasta = tmp_path / "detalhado"
    csv_para_parquet(csv, pasta / "ano=2022" / "casos.parquet")

    with abrir_casos(pasta) as conexao:
        agregado = letalidade_por_comorbidade_agregado(conexao)
        por_ano = letalidade_por_comorbidade_por_ano(conexao)

    for tabela in (agregado, por_ano):
        assert list(tabela["comorbidade"][:2]) == ["SIND_DOWN", "ASMA"]
