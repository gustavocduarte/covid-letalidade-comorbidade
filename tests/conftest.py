"""Fixtures compartilhadas: Parquets da amostra sintética e travas de rede e de escrita."""

import os
import socket
from pathlib import Path

import pytest

from config import RAIZ
from conversao import csv_para_parquet

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CSVS_SINTETICOS = {2020: FIXTURES / "INFLUD20-sintetico.csv", 2021: FIXTURES / "INFLUD21-sintetico.csv"}


def foto_da_pasta(pasta: Path) -> dict[str, tuple[int, int]]:
    """Nome, tamanho e data de modificação de tudo que há na pasta (vazio se ela não existe)."""
    foto = {}
    for raiz, pastas, arquivos in os.walk(pasta):
        for nome in [*pastas, *arquivos]:
            caminho = Path(raiz) / nome
            info = caminho.lstat()
            foto[caminho.relative_to(pasta).as_posix()] = (info.st_size, info.st_mtime_ns)
    return foto


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    """Falha alto se um teste tentar resolver nome ou abrir conexão de rede."""

    def bloquear(*args, **kwargs):
        raise RuntimeError("teste tentou acessar a rede")

    monkeypatch.setattr(socket, "getaddrinfo", bloquear)
    monkeypatch.setattr(socket.socket, "connect", bloquear)
    monkeypatch.setattr(socket.socket, "connect_ex", bloquear)


@pytest.fixture(autouse=True)
def sem_escrita_em_data(request):
    """Falha se o teste criar, apagar ou alterar algo em data/ (o repositório real)."""
    pasta = RAIZ / "data"
    antes = foto_da_pasta(pasta)
    yield
    assert foto_da_pasta(pasta) == antes, f"{request.node.nodeid} alterou arquivos em {pasta}"


@pytest.fixture(autouse=True, scope="session")
def sem_escrita_em_data_na_sessao():
    """Mesma trava para a sessão toda: pega o que fixtures de escopo maior gravam antes do teste."""
    pasta = RAIZ / "data"
    antes = foto_da_pasta(pasta)
    yield
    assert foto_da_pasta(pasta) == antes, f"a sessão de testes alterou arquivos em {pasta}"


@pytest.fixture(scope="session")
def csvs_sinteticos() -> dict[int, Path]:
    return CSVS_SINTETICOS


@pytest.fixture(scope="session")
def pasta_parquets(tmp_path_factory, csvs_sinteticos) -> Path:
    """Pasta com ano=AAAA/casos.parquet das duas amostras sintéticas."""
    pasta = tmp_path_factory.mktemp("detalhado")
    for ano, csv in csvs_sinteticos.items():
        csv_para_parquet(csv, pasta / f"ano={ano}" / "casos.parquet")
    return pasta
