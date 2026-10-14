"""Gera dados/municipios-pr.json.

Códigos e nomes: API de localidades do IBGE.
Coordenadas: repositório kelvins/municipios-brasileiros (licença MIT).
"""
import csv
import gzip
import io
import json
import urllib.request
from datetime import date

from .dados import MUNICIPIOS, gravar_json

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/41/municipios"
URL_COORDENADAS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"


def _baixar(url):
    pedido = urllib.request.Request(url, headers={"User-Agent": "concurseiro-varredura (tabela de municipios)"})
    with urllib.request.urlopen(pedido, timeout=60) as resp:
        corpo = resp.read()
        # A API do IBGE manda gzip mesmo sem pedir.
        return (gzip.decompress(corpo) if resp.headers.get("Content-Encoding") == "gzip" else corpo).decode("utf-8")


def gerar():
    ibge = json.loads(_baixar(URL_IBGE))
    coords = {linha["codigo_ibge"]: linha for linha in csv.DictReader(io.StringIO(_baixar(URL_COORDENADAS)))}
    faltando = [m["nome"] for m in ibge if str(m["id"]) not in coords]
    if faltando:
        raise SystemExit(f"Sem coordenadas para: {', '.join(faltando)}")
    lista = [
        {"ibge": str(m["id"]), "nome": m["nome"],
         "lat": float(coords[str(m["id"])]["latitude"]), "lon": float(coords[str(m["id"])]["longitude"])}
        for m in ibge
    ]
    lista.sort(key=lambda m: m["ibge"])
    gravar_json(MUNICIPIOS, {
        "gerado_em": date.today().isoformat(),
        "fontes": {
            "codigos_e_nomes": URL_IBGE,
            "coordenadas": URL_COORDENADAS + " (licença MIT, Kelvin S. do Prado)",
        },
        "municipios": lista,
    })
    print(f"{len(lista)} municípios gravados em {MUNICIPIOS.relative_to(MUNICIPIOS.parents[1])}")
