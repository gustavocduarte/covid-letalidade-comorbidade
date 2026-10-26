"""As travas automáticas do conftest (sem rede, sem escrita em data/) disparam quando deveriam."""

import socket

import pytest
from conftest import foto_da_pasta


def test_trava_de_rede_bloqueia_resolucao_de_nome_e_conexao():
    with pytest.raises(RuntimeError, match="rede"):
        socket.getaddrinfo("example.com", 80)
    with pytest.raises(RuntimeError, match="rede"):
        socket.create_connection(("127.0.0.1", 9))


def test_foto_da_pasta_detecta_criacao_alteracao_e_remocao(tmp_path):
    (tmp_path / "a.csv").write_text("1")
    antes = foto_da_pasta(tmp_path)

    (tmp_path / "b.csv").write_text("2")
    assert foto_da_pasta(tmp_path) != antes
    (tmp_path / "b.csv").unlink()
    assert foto_da_pasta(tmp_path) == antes

    (tmp_path / "a.csv").write_text("12")
    assert foto_da_pasta(tmp_path) != antes
    (tmp_path / "a.csv").unlink()
    assert foto_da_pasta(tmp_path) != antes


def test_foto_de_pasta_inexistente_e_vazia(tmp_path):
    assert foto_da_pasta(tmp_path / "nao_existe") == {}
