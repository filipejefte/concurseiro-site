"""Anonimato (regra 11 do CLAUDE.md): nada do que o projeto publica leva dado de quem o cria.

python -m gerador anonimato [pasta]   (o CI roda depois do build)

Falha se a pasta (public/) tiver [A PREENCHER], github.io, o dono do repositório ou o nome ou o e-mail de quem fez
commit. Os nomes saem do git na hora (git log) e do remote origin; não ficam escritos no código nem no teste.
"""
import os
import re
import subprocess
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MARCADORES = [("marcador", "[A PREENCHER"), ("marcador", "github.io")]


def _git(*args):
    try:
        saida = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=True)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return saida.stdout


def dono_do_repositorio():
    """O dono no GitHub: GITHUB_REPOSITORY_OWNER no CI, ou o usuário na URL do remote origin."""
    dono = os.environ.get("GITHUB_REPOSITORY_OWNER", "").strip()
    if dono:
        return dono
    achado = re.search(r"github\.com[:/]+([^/\s]+)/", _git("remote", "get-url", "origin"))
    return achado.group(1) if achado else ""


def autores():
    """Nomes e e-mails de quem fez commit, sem repetir."""
    return sorted({linha.strip() for linha in _git("log", "--all", "--format=%an%n%ae").splitlines() if linha.strip()})


def proibidos():
    """[(rótulo, texto)] do que não pode aparecer: os marcadores fixos, o dono do repositório e os autores de commit."""
    lista = list(MARCADORES)
    dono = dono_do_repositorio()
    if dono:
        lista.append(("dono do repositório", dono))
    lista += [("autor de commit", a) for a in autores()]
    return lista


def _normalizar(texto):
    sem_acento = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower())


def achados(texto, lista=None):
    """Rótulos do que a lista tem e o texto cita (sem diferença de maiúscula, acento ou espaço repetido)."""
    alvo = _normalizar(texto)
    return [f"{rotulo}: {item}" for rotulo, item in (proibidos() if lista is None else lista)
            if _normalizar(item) and _normalizar(item) in alvo]


def verificar_arquivos(arquivos, raiz=None, lista=None):
    """[(arquivo, achado)] nos arquivos dados. Lê tudo como texto utf-8 (PNG e outros binários entram: os
    metadados de imagem e qualquer texto embutido aparecem igual)."""
    lista = proibidos() if lista is None else lista
    problemas = []
    for arquivo in arquivos:
        texto = Path(arquivo).read_bytes().decode("utf-8", errors="ignore")
        nome = Path(arquivo).relative_to(raiz).as_posix() if raiz else str(arquivo)
        problemas += [(nome, a) for a in achados(texto, lista)]
    return problemas


def verificar_pasta(pasta, lista=None):
    pasta = Path(pasta)
    return verificar_arquivos(sorted(p for p in pasta.rglob("*") if p.is_file()), pasta, lista)
