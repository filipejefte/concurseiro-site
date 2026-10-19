"""Extração: da fila de atos para as fichas da semana.

Pasta da semana (dados/varreduras/AAAA-MM-DD/):
  fila/<fonte>-<data>-<órgão>-<hash>.md   um ato por arquivo (nome estável entre coletas): cabeçalho chave: valor, linha "---", texto
  fichas/<id>.json             {"ato": <arquivo da fila>, "atos_extras": [retificações já incorporadas],
                               "trechos": {...}, "concurso": {...}}
  descartes.json               [{"ato": <arquivo da fila>, "motivo": ...}]

A coleta só gera a fila; o /varredura do Claude Code lê cada arquivo e escreve a ficha seguindo
varredura/instrucoes_extracao.md (sem custo de API).
"""
import hashlib
import re
import unicodedata
from pathlib import Path

from .dados import ler_json

CAMPOS_FILA = ("fonte", "data", "classe", "pss", "orgao", "titulo", "url")


def _slug(texto, limite=50):
    texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")[:limite].strip("-")


def nome_na_fila(ato):
    """Nome estável: o mesmo ato gera o mesmo arquivo se a coleta for refeita (fichas e descartes continuam valendo).
    O hash inclui o texto porque no DOU várias matérias dividem o link da mesma página."""
    marca = hashlib.sha1((ato.url + "\n" + ato.titulo + "\n" + ato.texto).encode("utf-8")).hexdigest()[:8]
    return f"{ato.fonte.lower()}-{ato.data}-{_slug(ato.orgao, 40)}-{marca}.md"


def escrever_fila(pasta, atos_classificados):
    """Grava um arquivo por ato. Recebe [(ato, classe, pss)]; devolve os nomes dos arquivos."""
    fila = Path(pasta) / "fila"
    fila.mkdir(parents=True, exist_ok=True)
    nomes = []
    for ato, classe, pss in atos_classificados:
        meta = dict(ato.como_dict(), classe=classe, pss=pss)
        cabecalho = "\n".join(f"{k}: {str(meta[k]).replace(chr(10), ' ')}" for k in CAMPOS_FILA)
        nome = nome_na_fila(ato)
        (fila / nome).write_text(cabecalho + "\n---\n" + ato.texto + "\n", encoding="utf-8", newline="\n")
        nomes.append(nome)
    return nomes


def ler_fila(arquivo):
    cabecalho, texto = Path(arquivo).read_text(encoding="utf-8").split("\n---\n", 1)
    meta = dict(linha.split(": ", 1) for linha in cabecalho.splitlines() if ": " in linha)
    return meta, texto


_INSCRICAO = re.compile(r"inscri[çc][õo]es[^.\n]{0,40}(de|a partir de|até|no per[íi]odo|entre)[^.\n]{0,120}", re.I)


def resumo_do_ato(arquivo):
    """Uma linha por ato, para separar rápido o que vale ler inteiro."""
    meta, texto = ler_fila(arquivo)
    plano = " ".join(texto.split())
    achado = _INSCRICAO.search(plano)
    trecho = achado.group(0)[:160] if achado else "(sem trecho de inscrição)"
    return (f"{Path(arquivo).name} | {meta.get('classe')} | {meta.get('orgao', '')[:70]} | "
            f"{meta.get('titulo', '')[:70]} | {len(plano)} car. | {trecho}")


def pendentes(pasta):
    """Arquivos da fila que ainda não viraram ficha nem descarte."""
    pasta = Path(pasta)
    feitos = set()
    for ficha in (ler_json(p) for p in (pasta / "fichas").glob("*.json")):
        # atos_extras: retificações e anexos já incorporados à ficha de outro ato
        feitos |= {ficha["ato"], *ficha.get("atos_extras", [])}
    descartes = ler_json(pasta / "descartes.json") if (pasta / "descartes.json").exists() else []
    feitos |= {d["ato"] for d in descartes}
    return [p for p in sorted((pasta / "fila").glob("*.md")) if p.name not in feitos]
