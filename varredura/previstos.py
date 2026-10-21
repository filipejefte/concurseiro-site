"""Previstos: toda semana, cada concurso previsto com banca conhecida é reconferido no site dessa banca.

Previsto é o concurso com ato de autorização ou de contratação da banca, mas sem edital (regra 7). Quando a banca já
publicou o edital, a ficha vira aberta: a extração usa o MESMO id do previsto e acrescenta o edital aos documentos.
A fonte Bancas já põe o edital na fila; este comando acha a ligação entre o previsto e o concurso aberto da banca.

python -m varredura previstos
"""
import re
from datetime import date

from . import dados
from .dados import chave_nome
from .fontes.bancas import LEITORES, aberto

# Como o nome da banca aparece nos atos e nas fichas -> o leitor dela. Instituto Consulpam não é o Instituto Consulplan.
ALIAS = {
    "fafipa": ("fafipa", "fundacao fafipa", "fundacao de apoio ao campus de paranavai"),
    "fau": ("fau", "fundacao de apoio ao desenvolvimento da unicentro", "fundacao de apoio ao desenvolvimento unicentro"),
    "quadrix": ("quadrix", "instituto quadrix"),
    "omni": ("omni", "instituto omni"),
    "unicampo": ("unicampo", "instituto unicampo"),
    "consulplan": ("consulplan", "instituto consulplan"),
    "consulpam": ("consulpam", "instituto consulpam", "instituto consulpam consultoria", "consulpam consultoria"),
}


def slug_da_banca(nome):
    """O leitor da banca com esse nome, ou None. Compara o nome inteiro, sem acento, e a sigla entre parênteses."""
    chave = chave_nome(re.sub(r"\([^)]*\)", " ", nome or ""))
    siglas = [chave_nome(s) for s in re.findall(r"\(([^)]+)\)", nome or "")]
    for slug, nomes in ALIAS.items():
        if any(chave == n or chave.startswith(n + " ") or n in siglas or chave_nome(nome) == n for n in nomes):
            return slug
    return None


def entidade(orgao):
    """"Câmara Municipal de Quatro Barras (PR)" e "CÂMARA MUNICIPAL DE QUATRO BARRAS" viram a mesma chave."""
    return chave_nome(re.sub(r"\([^)]*\)", " ", orgao or "").replace("Município de", "Prefeitura Municipal de"))


def previstos(base, hoje):
    return [c for c in base["concursos"] if dados.situacao(c, hoje) == "previsto" and (c["banca"] or {}).get("nome")]


def verificar(base, cliente, hoje=None, leitores=None):
    """[(previsto, concurso da banca)] dos previstos que a banca já abriu, com o PDF do edital. Um leitor com problema não derruba."""
    hoje = hoje or date.today()
    leitores = {l.slug: l for l in (LEITORES if leitores is None else leitores)}
    achados, cache = [], {}
    for c in previstos(base, hoje):
        slug = slug_da_banca(c["banca"]["nome"])
        if slug not in leitores:
            continue
        if slug not in cache:
            try:
                cache[slug] = list(leitores[slug].listar(cliente))
            except OSError:
                cache[slug] = []
        for aberto_na_banca in cache[slug]:
            if entidade(aberto_na_banca.orgao) == entidade(c["orgao"]) and aberto_na_banca.edital and aberto(aberto_na_banca, hoje):
                achados.append((c, aberto_na_banca))
                break
    return achados
