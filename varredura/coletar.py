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
        raise SystemExit(f"A coleta de {ate} já existe em {pasta}. Para refazer, apague atos.json e fila/ dessa pasta.")
    cliente = Cliente()
    estado_fontes, atos = {}, []
    for Classe in FONTES:
        fonte = Classe(cliente)
        try:
            achados = fonte.listar_atos(desde, ate)
        except NotImplementedError as erro:
            estado_fontes[fonte.nome] = f"pulada: {erro}"
        except (SystemExit, OSError, urllib.error.URLError, ValueError) as erro:
            # Uma fonte com problema não derruba as outras; a revisão mostra o que faltou.
            estado_fontes[fonte.nome] = f"falhou: {erro}"
        else:
            estado_fontes[fonte.nome] = "ok"
            atos.extend(achados)
        print(f"{fonte.nome}: {estado_fontes[fonte.nome]}" + (f" ({len(achados)} atos)" if estado_fontes[fonte.nome] == "ok" else ""))

    registro, para_fila = [], []
    for ato in atos:
        resultado = classificar(ato)
        if resultado is None:
            continue
        classe, pss = resultado
        item = {k: v for k, v in ato.como_dict().items() if k != "texto"}
        item.update(classe=classe, pss=pss, fila=None)
        registro.append(item)
        if classe in PARA_EXTRAIR and not pss:
            para_fila.append((ato, classe, pss, item))
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
