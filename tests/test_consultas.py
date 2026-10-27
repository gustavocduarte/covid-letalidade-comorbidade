"""Agregações em SQL x versão pandas, sobre a amostra sintética (mesmos números e mesma ordem)."""

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
from transform import (
    agregar_estados_todos_anos,
    agregar_todos_anos,
    carregar_casos_covid,
    letalidade_por_comorbidade,
    letalidade_por_estado,
    serie_semanal_casos_covid,
)
from transform import (
    serie_semanal_por_comorbidade as serie_semanal_por_comorbidade_pandas,
)
from transform import (
    serie_semanal_por_estado as serie_semanal_por_estado_pandas,
)


@pytest.fixture(scope="module")
def con(pasta_parquets):
    with abrir_casos(pasta_parquets) as conexao:
        yield conexao


@pytest.fixture(scope="module")
def casos_pandas(csvs_sinteticos) -> dict[int, pd.DataFrame]:
    return {ano: carregar_casos_covid(csv) for ano, csv in csvs_sinteticos.items()}


@pytest.fixture(scope="module")
def tabelas_pandas(csvs_sinteticos) -> dict[int, pd.DataFrame]:
    return {ano: letalidade_por_comorbidade(carregar_casos_covid(csv)) for ano, csv in csvs_sinteticos.items()}


def test_letalidade_por_comorbidade_por_ano_igual_ao_pandas(con, tabelas_pandas, assert_iguais):
    esperado = pd.concat(
        [tabela.assign(ano=ano) for ano, tabela in tabelas_pandas.items()], ignore_index=True,
    )
    esperado = esperado[["ano", *[c for c in esperado.columns if c != "ano"]]]

    # inclui os empates de taxa indefinida (comorbidades nunca preenchidas): a ordem também é conferida
    assert_iguais(letalidade_por_comorbidade_por_ano(con), esperado)


def test_letalidade_por_comorbidade_agregado_igual_ao_pandas(con, tabelas_pandas, assert_iguais):
    esperado = agregar_todos_anos(list(tabelas_pandas.values()))

    assert_iguais(letalidade_por_comorbidade_agregado(con), esperado)


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


def test_letalidade_por_estado_por_ano_igual_ao_pandas(con, casos_pandas, assert_iguais):
    esperado = pd.concat(
        [letalidade_por_estado(covid).assign(ano=ano) for ano, covid in casos_pandas.items()], ignore_index=True,
    )
    esperado = esperado[["ano", *[c for c in esperado.columns if c != "ano"]]]

    assert_iguais(letalidade_por_estado_por_ano(con), esperado)


def test_letalidade_por_estado_agregado_igual_ao_pandas(con, casos_pandas, assert_iguais):
    esperado = agregar_estados_todos_anos([letalidade_por_estado(covid) for covid in casos_pandas.values()])

    assert_iguais(letalidade_por_estado_agregado(con), esperado)


def test_letalidade_por_estado_valores_calculados_a_mao(con):
    agregado = letalidade_por_estado_agregado(con)

    # (casos, óbitos, desfechos conhecidos); o caso sem UF (2020, linha 11) fica de fora.
    esperado = {
        "MG": (3, 1, 1), "XX": (1, 1, 1), "RJ": (6, 3, 5), "BA": (3, 1, 2), "SP": (7, 3, 6), "ZZ": (1, 0, 1),
    }
    # taxa decrescente; empates (MG/XX = 1,0 e BA/SP = 0,5) em ordem alfabética
    assert list(agregado["sigla"]) == list(esperado)
    for linha in agregado.itertuples():
        assert (linha.casos, linha.obitos, linha.desfecho_conhecido) == esperado[linha.sigla]


def test_serie_semanal_casos_igual_ao_pandas(con, casos_pandas, assert_iguais):
    # o pipeline soma os pedaços de cada semana que caem em dois arquivos anuais
    esperado = (
        pd.concat([serie_semanal_casos_covid(covid) for covid in casos_pandas.values()], ignore_index=True)
        .groupby("semana", as_index=False)["casos"].sum()
        .sort_values("semana").reset_index(drop=True)
    )

    assert_iguais(serie_semanal_casos(con), esperado)


def test_serie_semanal_casos_valores_calculados_a_mao(con):
    serie = serie_semanal_casos(con)

    esperado = {
        "2020-03-02": 2, "2020-03-09": 5, "2020-03-16": 4,
        "2020-12-28": 2,  # 30/dez/2020 (arquivo de 2020) + 01/jan/2021 (arquivo de 2021)
        "2021-01-04": 5, "2021-01-11": 2,
    }
    assert dict(zip(serie["semana"].dt.strftime("%Y-%m-%d"), serie["casos"], strict=True)) == esperado
    assert serie["casos"].sum() == 20  # 22 casos de COVID menos 2 sem data válida


def test_serie_semanal_por_comorbidade_igual_ao_pandas(con, casos_pandas, assert_iguais):
    esperado = (
        pd.concat([serie_semanal_por_comorbidade_pandas(covid) for covid in casos_pandas.values()], ignore_index=True)
        .groupby(["semana", "comorbidade"], as_index=False)["casos"].sum()
        .sort_values(["comorbidade", "semana"]).reset_index(drop=True)
    )

    assert_iguais(serie_semanal_por_comorbidade(con), esperado)


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


def test_serie_semanal_por_estado_igual_ao_pandas(con, casos_pandas, assert_iguais):
    # a versão pandas roda a função sobre os casos de todos os anos juntos
    esperado = serie_semanal_por_estado_pandas(pd.concat(list(casos_pandas.values()), ignore_index=True))

    assert_iguais(serie_semanal_por_estado(con), esperado)


def test_serie_semanal_por_estado_valores_calculados_a_mao(con):
    serie = serie_semanal_por_estado(con)

    obtido = list(zip(serie["semana"].dt.strftime("%Y-%m-%d"), serie["sigla"], serie["casos"], strict=True))
    assert obtido == [
        ("2020-03-02", "SP", 2), ("2020-03-09", "MG", 2), ("2020-03-09", "RJ", 3),
        ("2020-03-16", "MG", 1), ("2020-03-16", "SP", 1), ("2020-03-16", "XX", 1),
        ("2020-12-28", "SP", 2),  # 30/dez/2020 + 01/jan/2021
        ("2021-01-04", "BA", 2), ("2021-01-04", "RJ", 2), ("2021-01-04", "SP", 1),
        ("2021-01-11", "BA", 1), ("2021-01-11", "ZZ", 1),
    ]
    assert serie["casos"].sum() == 19  # 20 com data válida, menos 1 sem UF


def test_ano_sem_casos_de_covid_gera_as_linhas_de_zero_como_o_pandas(tmp_path, csvs_sinteticos, assert_iguais):
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

    esperado = pd.concat(
        [letalidade_por_comorbidade(carregar_casos_covid(csv)).assign(ano=ano) for ano, csv in csvs.items()],
        ignore_index=True,
    )
    esperado = esperado[["ano", *[c for c in esperado.columns if c != "ano"]]]
    assert_iguais(obtido, esperado)
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
