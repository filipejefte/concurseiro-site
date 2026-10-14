"""Publicação: gera assets/js/dados.js, que o site lê (funciona até abrindo o HTML direto, sem servidor)."""
import json
import unicodedata
from datetime import date

from .dados import DADOS_JS, SCHEMA, data, ler_json, municipios, situacao


def _linhas(itens):
    # Um item por linha: o diff semanal mostra só o que mudou.
    return "[\n" + ",\n".join(json.dumps(i, ensure_ascii=False, separators=(",", ":")) for i in itens) + "\n]"


def _sem_acento(texto):
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()


def gerar_js(base, exemplo=False, hoje=None):
    """Escreve dados.js a partir de um arquivo no formato de dados/concursos.json.

    A situação é calculada aqui, na data da varredura; o navegador só refaz a contagem
    regressiva e marca "Encerrado" pela data de hoje.
    """
    ref = data(base["varredura"]) or hoje or date.today()
    concursos = [dict(c, situacao=situacao(c, ref)) for c in base["concursos"]]
    meta = {k: base[k] for k in ("varredura", "proxima_varredura", "cobertura")}
    meta["exemplo"] = exemplo
    areas = ler_json(SCHEMA)["properties"]["area"]["enum"]
    tabela = sorted(municipios(exemplo).values(), key=lambda m: _sem_acento(m["nome"]))
    tabela = [[m["ibge"], m["nome"], m["lat"], m["lon"]] + ([1] if m.get("ficticio") else []) for m in tabela]

    aviso = "DADOS DE EXEMPLO, FICTÍCIOS. " if exemplo else ""
    texto = (
        f"/* {aviso}Gerado por `python -m varredura publicar{' --exemplo' if exemplo else ''}`. Não edite à mão.\n"
        "   MUNICIPIOS: [código IBGE, nome, latitude, longitude, 1 se fictício]. */\n"
        f"window.VARREDURA = {json.dumps(meta, ensure_ascii=False)};\n"
        f"window.AREAS = {json.dumps(areas, ensure_ascii=False)};\n"
        f"window.MUNICIPIOS = {_linhas(tabela)};\n"
        f"window.CONCURSOS = {_linhas(concursos)};\n"
    )
    DADOS_JS.write_text(texto, encoding="utf-8", newline="\n")
    return concursos
