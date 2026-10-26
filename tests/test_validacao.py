"""Verificações de qualidade sobre os Parquets: valores à mão da amostra sintética e casos de erro."""

import json

import pytest

import load
import validacao
from consultas import (
    abrir_casos,
    letalidade_por_comorbidade_agregado,
    letalidade_por_comorbidade_por_ano,
    letalidade_por_estado_agregado,
    serie_semanal_casos,
    serie_semanal_por_comorbidade,
    serie_semanal_por_estado,
)
from conversao import csv_para_parquet
from validacao import AVISO, ERRO, estatisticas_por_ano, montar_relatorio, validar_casos, validar_saidas

CAMPOS_ZERADOS = {
    "linhas": 0, "sem_uf": 0, "uf_invalida": 0, "sem_data": 0, "data_fora_janela": 0, "sem_desfecho": 0,
    "evolucao_invalida": 0, "comorbidade_invalida": 0, "fora_da_serie_estado": 0,
}


@pytest.fixture
def parquet_de_casos(tmp_path, csvs_sinteticos):
    """Cria ano=AAAA/casos.parquet a partir de linhas (dicts com as colunas a mudar; o resto é um caso padrão)."""
    cabecalho = csvs_sinteticos[2021].read_text(encoding="utf-8").splitlines()[0]
    colunas = cabecalho.split(";")
    padrao = {c: "" for c in colunas} | {"DT_SIN_PRI": "{ano}-06-10T00:00:00.000Z", "SG_UF": "SP",
                                          "CLASSI_FIN": "5", "EVOLUCAO": "1", "DIABETES": "1"}
    pasta = tmp_path / "detalhado"

    def criar(ano: int, linhas: list[dict]) -> None:
        corpo = [";".join((padrao | linha)[c].replace("{ano}", str(ano)) for c in colunas) for linha in linhas]
        csv = tmp_path / f"INFLUD{ano}.csv"
        csv.write_text("\n".join([cabecalho, *corpo]) + "\n", encoding="utf-8")
        csv_para_parquet(csv, pasta / f"ano={ano}" / "casos.parquet")

    criar.pasta = pasta
    return criar


def _estatisticas(pasta, anos):
    with abrir_casos(pasta, anos=anos) as con:
        return estatisticas_por_ano(con)


def test_estatisticas_da_amostra_sintetica_a_mao(pasta_parquets):
    e = _estatisticas(pasta_parquets, [2020, 2021])

    # 2020: 14 casos. Sem UF: linha 11; UF inválida: XX; sem data: inválida e vazia; sem desfecho: EVOLUCAO 3, 9,
    # vazio e 3; fora da série por estado: sem UF (1) + sem data (2).
    assert e[2020] == CAMPOS_ZERADOS | {
        "linhas": 14, "sem_uf": 1, "uf_invalida": 1, "sem_data": 2, "sem_desfecho": 4, "fora_da_serie_estado": 3,
    }
    # 2021: 8 casos; UF inválida: ZZ; sem desfecho: EVOLUCAO 9.
    assert e[2021] == CAMPOS_ZERADOS | {"linhas": 8, "uf_invalida": 1, "sem_desfecho": 1}


def test_achados_da_amostra_sintetica(pasta_parquets):
    achados = validar_casos(_estatisticas(pasta_parquets, [2020, 2021]))

    obtido = {(a.nivel, a.codigo, a.ano): a.quantidade for a in achados}
    assert obtido == {
        (ERRO, "DATA_INVALIDA", 2020): 2,  # 2 de 14 passa de 1%
        (AVISO, "SEM_UF", 2020): 1,
        (AVISO, "UF_INVALIDA", 2020): 1,
        (AVISO, "SEM_DESFECHO_ACIMA_DO_LIMITE", 2020): 4,  # 4 de 14 = 28,6%
        (AVISO, "UF_INVALIDA", 2021): 1,
    }  # 2021 tem 1 de 8 (12,5%) sem desfecho: abaixo de 20%


def test_aviso_de_sem_desfecho_explica_ano_parcial(pasta_parquets):
    achados = validar_casos(_estatisticas(pasta_parquets, [2020, 2021]))

    mensagem = next(a.mensagem for a in achados if a.codigo == "SEM_DESFECHO_ACIMA_DO_LIMITE")
    assert "ano parcial e recente" in mensagem and "pode ser esperado" in mensagem


def test_evolucao_e_comorbidade_fora_do_dominio_sao_erros(parquet_de_casos):
    parquet_de_casos(2022, [{}, {"EVOLUCAO": "7"}, {"ASMA": "5"}, {"RENAL": "0"}])

    achados = validar_casos(_estatisticas(parquet_de_casos.pasta, [2022]))

    obtido = {(a.nivel, a.codigo): a.quantidade for a in achados if a.nivel == ERRO}
    assert obtido == {("erro", "EVOLUCAO_FORA_DO_DOMINIO"): 1, ("erro", "COMORBIDADE_FORA_DO_DOMINIO"): 2}


def test_data_fora_da_janela_e_limite_de_erro(parquet_de_casos):
    # 200 casos, 2 fora da janela (2015 e 08/01/2023; 03/01/2023 ainda cabe nos 7 dias): 1,0% -> só aviso
    parquet_de_casos(2022, [{}] * 197 + [{"DT_SIN_PRI": "2015-01-01T00:00:00.000Z"},
                                          {"DT_SIN_PRI": "2023-01-03T00:00:00.000Z"},
                                          {"DT_SIN_PRI": "2023-01-08T00:00:00.000Z"}])
    parquet_de_casos(2023, [{}] * 98 + [{"DT_SIN_PRI": "2015-01-01T00:00:00.000Z"}] * 2)  # 2% -> erro

    e = _estatisticas(parquet_de_casos.pasta, [2022, 2023])
    achados = {(a.codigo, a.ano): (a.nivel, a.quantidade) for a in validar_casos(e)}

    assert e[2022]["data_fora_janela"] == 2 and e[2022]["sem_data"] == 0
    assert achados[("DATA_INVALIDA", 2022)] == (AVISO, 2)  # 1%: não passa de 1%, só aviso
    assert achados[("DATA_INVALIDA", 2023)] == (ERRO, 2)


def test_ano_sem_casos_gera_aviso_e_zeros(parquet_de_casos):
    parquet_de_casos(2022, [{"CLASSI_FIN": "4"}])

    e = _estatisticas(parquet_de_casos.pasta, [2022])

    assert e == {2022: CAMPOS_ZERADOS}
    assert [(a.nivel, a.codigo, a.ano) for a in validar_casos(e)] == [(AVISO, "ANO_SEM_CASOS", 2022)]


def test_limites_vem_do_modulo_de_validacao(parquet_de_casos, monkeypatch):
    parquet_de_casos(2022, [{}] * 199 + [{"DT_SIN_PRI": ""}])  # 0,5% sem data
    e = _estatisticas(parquet_de_casos.pasta, [2022])
    assert [(a.nivel, a.codigo) for a in validar_casos(e)] == [(AVISO, "DATA_INVALIDA")]

    monkeypatch.setattr(validacao, "LIMITE_DATA_INVALIDA", 0.0)
    assert [(a.nivel, a.codigo) for a in validar_casos(e)] == [(ERRO, "DATA_INVALIDA")]


@pytest.fixture(scope="module")
def saidas_validas(pasta_parquets):
    with abrir_casos(pasta_parquets, anos=[2020, 2021]) as con:
        return {
            "estatisticas": estatisticas_por_ano(con),
            "tabelas": {
                "por_ano": letalidade_por_comorbidade_por_ano(con),
                "agregado": letalidade_por_comorbidade_agregado(con),
                "estado": letalidade_por_estado_agregado(con),
                "serie_semanal": serie_semanal_casos(con),
                "serie_comorbidade": serie_semanal_por_comorbidade(con),
                "serie_estado": serie_semanal_por_estado(con),
            },
        }


def _validar(saidas, **alteradas):
    tabelas = {nome: df.copy() for nome, df in saidas["tabelas"].items()} | alteradas
    return validar_saidas(saidas["estatisticas"], **tabelas)


def test_saidas_corretas_nao_geram_achados(saidas_validas):
    assert _validar(saidas_validas) == []


def _com(df, mascara, coluna, valor):
    df = df.copy()
    df.loc[mascara(df), coluna] = valor
    return df


@pytest.mark.parametrize(("codigo", "tabela", "alteracao"), [
    ("COMORBIDADES_INCOMPLETAS", "por_ano", lambda df: df[~((df["ano"] == 2020) & (df["comorbidade"] == "ASMA"))]),
    ("CONTAGENS_INCONSISTENTES", "por_ano",
     lambda df: _com(df, lambda d: (d["ano"] == 2020) & (d["comorbidade"] == "DIABETES"), "obitos_com", 99)),
    ("CASOS_MAIORES_QUE_LINHAS", "por_ano",
     lambda df: _com(df, lambda d: (d["ano"] == 2021) & (d["comorbidade"] == "DIABETES"), "casos_com", 99)),
    ("TAXA_FORA_DO_INTERVALO", "agregado",
     lambda df: _com(df, lambda d: d["comorbidade"] == "DIABETES", "taxa_letalidade_com", 1.5)),
    ("AGREGADO_DIFERE_DA_SOMA", "agregado",
     lambda df: _com(df, lambda d: d["comorbidade"] == "DIABETES", "casos_sem", 100)),
    ("ESTADO_DIFERE_DOS_CASOS", "estado", lambda df: df.iloc[1:]),
    ("SERIE_SEMANAL_DIFERE_DOS_CASOS", "serie_semanal", lambda df: _com(df, lambda d: d.index == 0, "casos", 50)),
    ("SERIE_ESTADO_DIFERE_DOS_CASOS", "serie_estado", lambda df: df.iloc[:-1]),
    ("SERIE_COMORBIDADE_MAIOR_QUE_CASOS", "serie_comorbidade", lambda df: _com(df, lambda d: d.index >= 0, "casos", 1000)),
])
def test_cada_invariante_violado_vira_erro(saidas_validas, codigo, tabela, alteracao):
    achados = _validar(saidas_validas, **{tabela: alteracao(saidas_validas["tabelas"][tabela])})

    assert codigo in {a.codigo for a in achados}
    assert {a.nivel for a in achados} == {ERRO}


def test_relatorio_da_amostra_sintetica(pasta_parquets):
    e = _estatisticas(pasta_parquets, [2020, 2021])
    achados = validar_casos(e)

    relatorio = montar_relatorio(e, achados)

    assert relatorio["versao"] == 1
    assert relatorio["aprovado"] is False  # 2020 tem 2 de 14 datas inválidas (> 1%)
    assert list(relatorio["anos"]) == ["2020", "2021"]
    assert relatorio["anos"]["2020"]["sem_uf"] == 1
    assert relatorio["totais"] == CAMPOS_ZERADOS | {
        "linhas": 22, "sem_uf": 1, "uf_invalida": 2, "sem_data": 2, "sem_desfecho": 5, "fora_da_serie_estado": 3,
    }
    # erros primeiro; depois por código e ano
    assert [(a["nivel"], a["codigo"], a["ano"]) for a in relatorio["achados"]] == [
        ("erro", "DATA_INVALIDA", 2020),
        ("aviso", "SEM_DESFECHO_ACIMA_DO_LIMITE", 2020),
        ("aviso", "SEM_UF", 2020),
        ("aviso", "UF_INVALIDA", 2020),
        ("aviso", "UF_INVALIDA", 2021),
    ]
    assert montar_relatorio(e, list(reversed(achados))) == relatorio


def test_relatorio_sem_erros_esta_aprovado(parquet_de_casos):
    parquet_de_casos(2022, [{}] * 10)

    relatorio = montar_relatorio(_estatisticas(parquet_de_casos.pasta, [2022]), [])

    assert relatorio["aprovado"] is True and relatorio["achados"] == []


def test_salvar_json_grava_utf8_com_lf_e_ida_e_volta(tmp_path, monkeypatch):
    monkeypatch.setattr(load, "PROCESSED_DIR", tmp_path)
    dados = {"mensagem": "ano parcial e recente — já em andamento", "n": 3}

    caminho = load.salvar_json(dados, "teste.json")

    assert caminho == tmp_path / "teste.json"
    assert b"\r" not in caminho.read_bytes()
    assert json.loads(caminho.read_text(encoding="utf-8")) == dados
