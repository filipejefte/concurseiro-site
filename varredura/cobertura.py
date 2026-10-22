"""Cobertura dos 399 municípios do Paraná: o que cada um trouxe de concurso na AMP em 4 meses, e o que as bancas têm aberto.

python -m varredura cobertura  ->  dados/cobertura-municipios.csv

Fontes: o atos.json da semana (publicações da AMP por município, atos sobre concurso com município e tipo de entidade, e
os editais abertos lidos nas bancas) e as fichas. Serve para achar o furo: município que nunca aparece na AMP não está
sendo lido, e a ajuda vem das bancas ou de um diário próprio.
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import dados
from .dados import ler_json, municipio_pelo_inicio

DESTINO = dados.DADOS / "cobertura-municipios.csv"
SOBRE_CONCURSO = ("abertura", "retificacao", "autorizacao", "contratacao_banca", "resultado")
EDITAL = ("abertura", "retificacao", "autorizacao", "contratacao_banca")
COLUNAS = ["ibge", "municipio", "materias_na_amp", "ultima_materia_na_amp", "atos_sobre_concurso", "atos_de_edital_ou_previsto", "pss",
           "ultimo_ato_sobre_concurso", "da_prefeitura", "da_camara", "de_outra_entidade", "entidade_nao_dita", "abertos_em_bancas",
           "bancas", "fichas", "fonte"]
NOME_NO_ORGAO = re.compile(r"(?:munic[ií]pio|prefeitura(?: municipal)?|c[âa]mara(?: municipal)?)\s+d[eoa]s?\s+(.+)", re.I)


def municipio_do_orgao(orgao):
    """Município de um órgão como a banca o escreve ("PREFEITURA MUNICIPAL DE APUCARANA - 2026"); None se não for do PR."""
    achado = NOME_NO_ORGAO.search(orgao or "")
    municipio = municipio_pelo_inicio(achado.group(1)) if achado else None
    return municipio["ibge"] if municipio else None


def gerar(pasta, destino=DESTINO):
    pasta = Path(pasta)
    registro = ler_json(pasta / "atos.json")
    tabela = dados.municipios_pr()
    publicou = registro.get("publicacoes", {}).get("AMP-PR", {})
    atos = defaultdict(list)
    abertos = defaultdict(set)
    for a in registro["atos"]:
        if a["fonte"] == "AMP-PR" and a.get("municipio_ibge"):
            atos[a["municipio_ibge"]].append(a)
        elif a["fonte"].startswith("banca-") and a["classe"] == "abertura":
            ibge = municipio_do_orgao(a["orgao"])
            if ibge:
                abertos[ibge].add(a["fonte"].removeprefix("banca-"))
    fichas = Counter(f["concurso"].get("municipio_ibge") for f in dados.carregar_fichas(pasta) if f.get("concurso"))
    fichas.update(c.get("municipio_ibge") for c in ler_json(dados.CONCURSOS)["concursos"] if c["id"] not in
                  {f["concurso"]["id"] for f in dados.carregar_fichas(pasta) if f.get("concurso")})
    linhas = []
    for ibge, m in sorted(tabela.items(), key=lambda par: par[1]["nome"]):
        meus = [a for a in atos[ibge] if a["classe"] in SOBRE_CONCURSO and not a["pss"]]
        tipos = Counter(a.get("entidade") or "" for a in meus)
        fonte = "AMP" if ibge in publicou else ""
        if abertos[ibge]:
            fonte = (fonte + " + " if fonte else "") + "banca"
        linhas.append({
            "ibge": ibge, "municipio": m["nome"], "materias_na_amp": publicou.get(ibge, {}).get("materias", 0),
            "ultima_materia_na_amp": publicou.get(ibge, {}).get("ultima", ""), "atos_sobre_concurso": len(meus),
            "atos_de_edital_ou_previsto": sum(1 for a in meus if a["classe"] in EDITAL),
            "pss": sum(1 for a in atos[ibge] if a["pss"]), "ultimo_ato_sobre_concurso": max((a["data"] for a in meus), default=""),
            "da_prefeitura": tipos["prefeitura"], "da_camara": tipos["camara"], "de_outra_entidade": tipos["outro"],
            "entidade_nao_dita": tipos[""], "abertos_em_bancas": len(abertos[ibge]), "bancas": " ".join(sorted(abertos[ibge])),
            "fichas": fichas[ibge], "fonte": fonte or "nenhuma",
        })
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    n = lambda cond: sum(1 for l in linhas if cond(l))
    resumo = (f"{len(linhas)} municípios · {n(lambda l: l['materias_na_amp'])} publicaram na AMP · "
              f"{n(lambda l: l['atos_sobre_concurso'])} tiveram ato sobre concurso · {n(lambda l: l['abertos_em_bancas'])} com concurso aberto em banca · "
              f"{n(lambda l: l['fonte'] == 'nenhuma')} sem nenhuma fonte lida")
    return destino, resumo
