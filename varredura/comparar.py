"""Comparação: fichas da semana contra dados/concursos.json."""
from dataclasses import dataclass, field

from .dados import data, situacao

# Campos que mudam na publicação, não no edital: não contam como alteração.
CONTROLE = ("conferencia", "primeira_varredura", "ultima_alteracao")


def sem_controle(c):
    return {k: v for k, v in c.items() if k not in CONTROLE}


@dataclass
class Comparacao:
    novos: list = field(default_factory=list)       # concursos que não estão publicados
    alterados: list = field(default_factory=list)   # (ficha nova, versão publicada): retificações
    iguais: list = field(default_factory=list)
    ignorados: list = field(default_factory=list)   # inscrição já encerrada na data da varredura
    encerrados: list = field(default_factory=list)  # publicados que encerraram desde a varredura anterior


def comparar(fichas, base, data_varredura):
    publicados = {c["id"]: c for c in base["concursos"]}
    r = Comparacao()
    for ficha in fichas:
        c = ficha["concurso"]
        if situacao(c, data_varredura) == "encerrado":
            r.ignorados.append(c)
            continue
        antigo = publicados.get(c["id"])
        if antigo is None:
            r.novos.append(c)
        elif sem_controle(antigo) != sem_controle(c):
            r.alterados.append((c, antigo))
        else:
            r.iguais.append(c)
    anterior = data(base["varredura"])
    for c in base["concursos"]:
        if situacao(c, data_varredura) == "encerrado" and (anterior is None or situacao(c, anterior) != "encerrado"):
            r.encerrados.append(c)
    return r
