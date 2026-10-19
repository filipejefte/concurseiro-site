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
from datetime import date
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


def resumo_do_ato(arquivo, hoje=None):
    """Uma linha por ato, para separar rápido o que vale ler inteiro. Começa pela prioridade (1, 2 ou 3)."""
    meta, texto = ler_fila(arquivo)
    plano = " ".join(texto.split())
    achado = _INSCRICAO.search(plano)
    trecho = achado.group(0)[:160] if achado else "(sem trecho de inscrição)"
    grupo, _ = prioridade(arquivo, hoje or date.today())
    return (f"P{grupo} | {Path(arquivo).name} | {meta.get('classe')} | {meta.get('orgao', '')[:70]} | "
            f"{meta.get('titulo', '')[:70]} | {len(plano)} car. | {trecho}")


_MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
_DATA = re.compile(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})(?!\d)|(?<!\d)(\d{1,2})\s*(?:o\s+)?de\s+(" + "|".join(_MESES)
                   + r")\s+de\s+(\d{4})")
PRIORIDADES = {1: "inscrição aberta ou futura", 2: "previsto (autorização ou banca) dos últimos 120 dias", 3: "o resto"}


def _datas_de_inscricao(texto):
    """Datas que aparecem até 250 caracteres depois de "inscrição" (texto normalizado, sem acento)."""
    texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()
    datas = []
    for k in re.finditer(r"inscric", texto):
        for m in _DATA.finditer(texto, k.end(), k.end() + 250):
            try:
                if m.group(1):
                    datas.append(date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
                else:
                    datas.append(date(int(m.group(6)), _MESES.index(m.group(5)) + 1, int(m.group(4))))
            except ValueError:
                continue
    return datas


def prioridade(arquivo, hoje):
    """(grupo, ordem) para extrair primeiro o que importa: 1 inscrição aberta ou futura; 2 previsto recente; 3 o resto
    (dentro do 3, por último o que só tem datas de inscrição já passadas: provável descarte)."""
    meta, texto = ler_fila(arquivo)
    datas = _datas_de_inscricao(meta.get("titulo", "") + "\n" + texto)
    publicado = date.fromisoformat(meta["data"]) if meta.get("data") else hoje
    if any(dt >= hoje for dt in datas):
        return 1, 0
    if meta.get("classe") in ("autorizacao", "contratacao_banca") and (hoje - publicado).days <= 120:
        return 2, 0
    return 3, 1 if datas else 0


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
