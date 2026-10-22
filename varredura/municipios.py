"""Gera dados/municipios.json (todos os municípios do Brasil) e dados/municipios-pr.json (só os do Paraná).

Códigos e nomes: API de localidades do IBGE.
Coordenadas: repositório kelvins/municipios-brasileiros (licença MIT).
"""
import csv
import gzip
import io
import json
import urllib.request
from datetime import date

from .dados import MUNICIPIOS, MUNICIPIOS_PR, gravar_json

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
URL_COORDENADAS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
# Os dois primeiros dígitos do código IBGE dizem a UF.
UF_DO_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI", "23": "CE",
    "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


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
        {"ibge": str(m["id"]), "nome": m["nome"], "uf": UF_DO_CODIGO[str(m["id"])[:2]],
         "lat": float(coords[str(m["id"])]["latitude"]), "lon": float(coords[str(m["id"])]["longitude"])}
        for m in ibge
    ]
    lista.sort(key=lambda m: m["ibge"])
    fontes = {"codigos_e_nomes": URL_IBGE, "coordenadas": URL_COORDENADAS + " (licença MIT, Kelvin S. do Prado)"}
    hoje = date.today().isoformat()
    gravar_json(MUNICIPIOS, {"gerado_em": hoje, "fontes": fontes, "municipios": lista})
    # Só o Paraná: a AMP e a cobertura casam o nome do município dentro do estado, sem confundir "São José" de outro estado.
    pr = [m for m in lista if m["uf"] == "PR"]
    gravar_json(MUNICIPIOS_PR, {"gerado_em": hoje, "fontes": fontes, "municipios": pr})
    print(f"{len(lista)} municípios gravados em {MUNICIPIOS.relative_to(MUNICIPIOS.parents[1])}; "
          f"{len(pr)} do Paraná em {MUNICIPIOS_PR.relative_to(MUNICIPIOS_PR.parents[1])}")
