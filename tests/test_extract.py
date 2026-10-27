"""Download do CSV bruto: o arquivo final só aparece quando o download termina."""

import pytest

import extract


class _Resposta:
    def __init__(self, pedacos, falha_no_meio=False):
        self.headers = {"content-length": str(sum(len(p) for p in pedacos))}
        self._pedacos, self._falha = pedacos, falha_no_meio

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield from self._pedacos
        if self._falha:
            raise ConnectionError("conexão caiu")


def test_baixa_o_arquivo_inteiro_sem_deixar_parcial(tmp_path, monkeypatch):
    monkeypatch.setattr(extract.requests, "get", lambda *_a, **_k: _Resposta([b"abc", b"def"]))

    caminho = extract.baixar_arquivo("https://exemplo.invalid/SRAG/2020/INFLUD20.csv", tmp_path)

    assert caminho.read_bytes() == b"abcdef"
    assert [p.name for p in tmp_path.iterdir()] == ["INFLUD20.csv"]


def test_download_interrompido_nao_deixa_arquivo_nem_estraga_o_existente(tmp_path, monkeypatch):
    existente = tmp_path / "INFLUD20.csv"
    existente.write_bytes(b"bom")
    monkeypatch.setattr(extract.requests, "get", lambda *_a, **_k: _Resposta([b"abc"], falha_no_meio=True))

    with pytest.raises(ConnectionError):
        extract.baixar_arquivo("https://exemplo.invalid/SRAG/2020/INFLUD20.csv", tmp_path)

    assert [p.name for p in tmp_path.iterdir()] == ["INFLUD20.csv"]
    assert existente.read_bytes() == b"bom"
