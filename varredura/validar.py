"""Validação: o schema e as regras que o schema sozinho não pega."""
import urllib.parse

import jsonschema

from .dados import SCHEMA, carregar_fichas, data, edital, ler_json, municipios

# Domínios aceitos para o link do edital e dos documentos: diário oficial, órgão público ou banca.
SUFIXOS_OFICIAIS = (".gov.br", ".leg.br", ".jus.br", ".mp.br", ".def.br", ".mil.br", ".edu.br")
DOMINIOS_OFICIAIS = (
    "diariomunicipal.com.br",    # AMP-PR (matérias)
    "voxtecnologia.com.br",      # AMP-PR (PDF das edições)
    "atende.net",                # portais e diários de muitas prefeituras do PR
)
# Agregadores servem só para conferir cobertura: nunca como link nem como fonte.
AGREGADORES = (
    "pciconcursos.com.br", "folhadirigida.com.br", "qconcursos.com", "estrategiaconcursos.com.br",
    "grancursosonline.com.br", "jcconcursos.com.br", "concursosnobrasil.com", "acheconcursos.com.br",
)

_validador = None


def _schema():
    global _validador
    if _validador is None:
        _validador = jsonschema.Draft202012Validator(ler_json(SCHEMA))
    return _validador


def _host(url):
    return (urllib.parse.urlsplit(url or "").hostname or "").lower()


def _no_dominio(host, dominios):
    return any(host == d or host.endswith("." + d) for d in dominios)


def _oficial(url, c):
    host = _host(url)
    if c.get("ficticio") and (host == "example" or host.endswith(".example")):
        return True
    banca = _host(c["banca"]["url"])
    return host.endswith(SUFIXOS_OFICIAIS) or _no_dominio(host, DOMINIOS_OFICIAIS) or (banca and host == banca)


def validar_concurso(c, tabela=None, exemplo=False):
    """Lista de problemas (vazia quando a ficha está certa)."""
    erros = [f"schema: {'/'.join(map(str, e.absolute_path)) or '(raiz)'}: {e.message}" for e in _schema().iter_errors(c)]
    if erros:
        return erros  # as regras abaixo supõem o formato certo
    tabela = tabela if tabela is not None else municipios(exemplo)

    if c["ficticio"] and not exemplo:
        erros.append("ficha fictícia fora dos dados de exemplo")
    for campo in ("isencao_ate", "prova_objetiva", "primeira_varredura", "ultima_alteracao"):
        try:
            data(c[campo])
        except ValueError:
            erros.append(f"{campo}: data inválida ({c[campo]})")
    try:
        inicio, fim = data(c["inscricao"]["inicio"]), data(c["inscricao"]["fim"])
    except ValueError:
        erros.append("inscricao: data inválida")
        inicio = fim = None
    if inicio and fim and fim <= inicio:
        erros.append(f"inscricao: o fim ({fim}) precisa ser depois do início ({inicio})")
    t = c["taxa"]
    if t["min"] is not None and t["max"] is not None and t["min"] > t["max"]:
        erros.append("taxa: mínimo maior que o máximo")
    # Salário: o schema já exige > 0 ou null.

    ed = edital(c)
    if ed is None:
        if not any(d["tipo"] in ("autorizacao", "contratacao_banca") for d in c["documentos"]):
            erros.append("edital: sem link do edital (e sem ato de autorização ou contratação de banca para ser previsto)")
        elif inicio or fim:
            erros.append("edital: tem datas de inscrição mas não tem o edital")
    for nome, url in [("banca.url", c["banca"]["url"]), ("inscricao.url", c["inscricao"]["url"])] + \
            [(f"documentos[{i}]", d["url"]) for i, d in enumerate(c["documentos"])]:
        if url is None:
            continue
        host = _host(url)
        if _no_dominio(host, AGREGADORES):
            erros.append(f"{nome}: {host} é agregador, não fonte oficial")
        elif host.endswith(".example") and not c["ficticio"]:
            erros.append(f"{nome}: link de exemplo ({host}) em ficha real")
    if ed and not _oficial(ed["url"], c):
        erros.append(f"edital: o link ({_host(ed['url'])}) não é de diário oficial, órgão público nem da banca")

    if c["municipio_ibge"] is not None and c["uf"] != "PR":
        erros.append("cidade: municipio_ibge só para cidade do PR; fora do PR, deixe null e preencha uf e cidade")
    elif c["municipio_ibge"] is not None:
        m = tabela.get(c["municipio_ibge"])
        if c["uf"] == "PR" and m is None:
            erros.append(f"cidade: município {c['municipio_ibge']} não existe na tabela do PR")
        elif m and c["cidade"] != m["nome"]:
            erros.append(f"cidade: '{c['cidade']}' não bate com o nome da tabela ('{m['nome']}')")
    elif c["uf"] == "PR" and not c["nacional"]:
        erros.append("cidade: concurso no PR sem municipio_ibge")
    if c["esfera"] != "federal" and c["uf"] != "PR":
        erros.append(f"cobertura: {c['esfera']} de {c['uf']} está fora da cobertura (federais e PR)")
    if c["nacional"] and c["esfera"] != "federal":
        erros.append("nacional: só concurso federal pode ser nacional")
    return erros


def validar_tudo(pasta=None, exemplo=False):
    """{rótulo: [erros]} da base publicada (ou de exemplo) e das fichas da semana."""
    from .dados import CONCURSOS, EXEMPLO

    tabela = municipios(exemplo)
    resultado = {}
    base = ler_json(EXEMPLO if exemplo else CONCURSOS)
    for c in base["concursos"]:
        erros = validar_concurso(c, tabela, exemplo)
        if erros:
            resultado[f"{'exemplo' if exemplo else 'concursos.json'}: {c.get('id')}"] = erros
    if pasta is not None:
        for f in carregar_fichas(pasta):
            c = f.get("concurso") or {}
            erros = validar_concurso(c, tabela)
            if not f.get("trechos"):
                erros.append("trechos: a ficha não traz os trechos do ato")
            if erros:
                resultado[f"{pasta.name}/fichas: {c.get('id')}"] = erros
    return resultado
