"""Coleta: lê as fontes, faz a triagem e monta a fila de extração da semana."""
import urllib.error

from .dados import VARREDURAS, gravar_json
from .extracao import escrever_fila, extrair_api
from .fontes import FONTES
from .fontes.base import Cliente
from .triagem import PARA_EXTRAIR, classificar


def coletar(desde, ate, inicial=False, modo="claude-code"):
    pasta = VARREDURAS / ate.isoformat()
    if (pasta / "atos.json").exists():
        # Refazer é seguro: o cache evita baixar de novo e os nomes da fila são estáveis,
        # então fichas e descartes já feitos continuam ligados aos seus atos.
        print(f"Refazendo a coleta de {ate} (fichas e descartes já feitos ficam).", flush=True)
    cliente = Cliente()
    estado_fontes, registro, para_fila = {}, [], []
    for Classe in FONTES:
        fonte = Classe(cliente)
        lidos = 0
        try:
            # A triagem roda ato a ato: só o que fala de concurso fica na memória.
            for ato in fonte.listar_atos(desde, ate):
                lidos += 1
                resultado = classificar(ato)
                if resultado is None:
                    continue
                classe, pss = resultado
                item = {k: v for k, v in ato.como_dict().items() if k != "texto"}
                item.update(classe=classe, pss=pss, fila=None)
                registro.append(item)
                if classe in PARA_EXTRAIR and not pss:
                    para_fila.append((ato, classe, pss, item))
        except NotImplementedError as erro:
            estado_fontes[fonte.nome] = f"pulada: {erro}"
        except (SystemExit, OSError, urllib.error.URLError, ValueError) as erro:
            # Uma fonte com problema não derruba as outras; a revisão mostra o que faltou.
            estado_fontes[fonte.nome] = f"falhou depois de {lidos} atos: {erro}"
        else:
            estado_fontes[fonte.nome] = "ok"
        print(f"{fonte.nome}: {estado_fontes[fonte.nome]} ({lidos} atos lidos)", flush=True)

    for nome, (_, _, _, item) in zip(escrever_fila(pasta, [(a, c, p) for a, c, p, _ in para_fila]), para_fila):
        item["fila"] = nome
    gravar_json(pasta / "atos.json", {
        "desde": desde.isoformat(), "ate": ate.isoformat(), "inicial": inicial,
        "fontes": estado_fontes, "atos": registro,
    })
    print(f"{len(registro)} atos sobre concurso; {len(para_fila)} na fila de extração; "
          f"{sum(1 for a in registro if a['pss'])} PSS em avaliação. Pasta: {pasta}")

    if modo == "api":
        fichas, descartes, falhas = extrair_api(pasta, ate)
        print(f"Extração pela API: {fichas} fichas, {descartes} descartes, {len(falhas)} falhas.")
        for nome, motivo in falhas:
            print(f"  {nome}: {motivo}")
    return pasta
