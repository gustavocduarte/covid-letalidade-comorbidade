"""Publicação dos CSVs: ou todos trocados no fim, ou nenhum alterado."""

import pandas as pd
import pytest

import load


@pytest.fixture
def processed(tmp_path, monkeypatch):
    monkeypatch.setattr(load, "PROCESSED_DIR", tmp_path)
    return tmp_path


def _tabelas(valor: int) -> dict[str, pd.DataFrame]:
    return {nome: pd.DataFrame({"x": [valor]}) for nome in ("a.csv", "b.csv", "c.csv")}


def test_publicar_csvs_grava_todos_sem_deixar_temporarios(processed):
    caminhos = load.publicar_csvs(_tabelas(2))

    assert sorted(p.name for p in processed.iterdir()) == ["a.csv", "b.csv", "c.csv"]
    assert all(c.read_text(encoding="utf-8") == "x\n2\n" for c in caminhos.values())


def test_falha_no_meio_da_gravacao_dos_temporarios_nao_altera_nenhum_csv_publicado(processed, monkeypatch):
    load.publicar_csvs(_tabelas(1))
    antes = {p.name: p.read_bytes() for p in processed.iterdir()}
    original = pd.DataFrame.to_csv
    chamadas = []

    def falha_na_terceira(self, *args, **kwargs):
        chamadas.append(1)
        if len(chamadas) == 3:
            raise OSError("disco cheio (simulado)")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_csv", falha_na_terceira)

    with pytest.raises(OSError, match="disco cheio"):
        load.publicar_csvs(_tabelas(2))

    assert {p.name: p.read_bytes() for p in processed.iterdir()} == antes  # nada mudou, nem sobrou temporário
