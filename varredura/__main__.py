"""Linha de comando da varredura: python -m varredura <comando>.

  coletar --inicial --desde 2026-07-01   primeira varredura: tudo desde a data, fica o que tem inscrição aberta
  coletar --semana                       desde a última varredura publicada até hoje
  pendentes                              atos da fila ainda sem ficha nem descarte
  validar                                schema e regras, na base publicada e nas fichas da semana
  revisao                                revisao.md e revisao.csv na pasta da semana
  publicar --por "Nome"                  publica só o que foi conferido; gera dados.js e o resumo do Telegram
  publicar --exemplo                     dados.js com os exemplos fictícios
  municipios                             refaz dados/municipios-pr.json
"""
import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from . import dados, municipios


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # acentos no console do Windows
        sys.stderr.reconfigure(encoding="utf-8")
    dados.carregar_env()

    p = argparse.ArgumentParser(prog="python -m varredura", description="Varredura semanal de concursos (federais e do Paraná).")
    sub = p.add_subparsers(dest="comando", required=True)

    col = sub.add_parser("coletar", help="lê as fontes, faz a triagem e monta a fila de extração")
    quando = col.add_mutually_exclusive_group(required=True)
    quando.add_argument("--inicial", action="store_true", help="primeira varredura (use com --desde)")
    quando.add_argument("--semana", action="store_true", help="desde a última varredura publicada")
    col.add_argument("--desde", type=date.fromisoformat, help="AAAA-MM-DD")
    col.add_argument("--ate", type=date.fromisoformat, default=date.today(), help="AAAA-MM-DD (padrão: hoje)")
    col.add_argument("--modo", choices=["claude-code", "api"], default="claude-code",
                     help="claude-code (padrão, sem custo de API) ou api (claude-haiku-5-5, ANTHROPIC_API_KEY)")

    val = sub.add_parser("validar", help="checa schema e regras")
    val.add_argument("--pasta", type=Path, help="pasta da varredura (padrão: a mais recente)")
    val.add_argument("--exemplo", action="store_true", help="valida os dados de exemplo")

    pen = sub.add_parser("pendentes", help="lista os atos da fila que ainda não viraram ficha nem descarte")
    pen.add_argument("--pasta", type=Path)

    rev = sub.add_parser("revisao", help="gera revisao.md e revisao.csv")
    rev.add_argument("--pasta", type=Path)

    pub = sub.add_parser("publicar", help="publica o que foi conferido e gera assets/js/dados.js")
    pub.add_argument("--exemplo", action="store_true", help="gera dados.js com os dados fictícios de dados/exemplo/")
    pub.add_argument("--pasta", type=Path)
    pub.add_argument("--por", default=os.environ.get("CONFERENTE"), help="quem conferiu (ou CONFERENTE no .env)")

    sub.add_parser("municipios", help="refaz dados/municipios-pr.json (IBGE + coordenadas)")

    args = p.parse_args(argv)

    if args.comando == "municipios":
        municipios.gerar()
        return 0

    if args.comando == "coletar":
        from .coletar import coletar
        if args.inicial:
            if not args.desde:
                p.error("--inicial precisa de --desde AAAA-MM-DD")
            desde = args.desde
        else:
            anterior = dados.data(dados.ler_json(dados.CONCURSOS)["varredura"])
            desde = args.desde or (anterior + timedelta(days=1) if anterior else args.ate - timedelta(days=7))
        coletar(desde, args.ate, inicial=args.inicial, modo=args.modo)
        return 0

    if args.comando == "validar":
        from .validar import validar_tudo
        pasta = None if args.exemplo else (args.pasta or (dados.ultima_pasta() if any(dados.VARREDURAS.glob("????-??-??")) else None))
        problemas = validar_tudo(pasta, exemplo=args.exemplo)
        for rotulo, erros in problemas.items():
            print(rotulo)
            for erro in erros:
                print(f"  - {erro}")
        print("Tudo certo." if not problemas else f"{len(problemas)} ficha(s) com problema.")
        return 1 if problemas else 0

    if args.comando == "pendentes":
        from .extracao import pendentes
        pasta = args.pasta or dados.ultima_pasta()
        faltam = pendentes(pasta)
        for arquivo in faltam:
            print(arquivo)
        print(f"{len(faltam)} ato(s) pendente(s) em {pasta / 'fila'}")
        return 0

    if args.comando == "revisao":
        from .revisao import gerar
        pasta = args.pasta or dados.ultima_pasta()
        r, problemas = gerar(pasta)
        print(f"{pasta / 'revisao.md'} e revisao.csv: {len(r.novos)} novos, {len(r.alterados)} alterados, "
              f"{len(r.encerrados)} encerrados, {len(problemas)} com problema de validação.")
        return 0

    if args.comando == "publicar":
        from .publicar import gerar_js, publicar_semana
        if args.exemplo:
            n = len(gerar_js(dados.ler_json(dados.EXEMPLO), exemplo=True))
            print(f"dados.js gerado com {n} concursos de exemplo (fictícios)")
            return 0
        if not args.por:
            p.error('diga quem conferiu: --por "Nome" (ou CONFERENTE no .env)')
        pasta = args.pasta or dados.ultima_pasta()
        aprovados, recusados = publicar_semana(pasta, args.por)
        print(f"Publicados {len(aprovados)} concursos. dados.js, concursos.json e {pasta / 'resumo-telegram.md'} atualizados.")
        for id_, motivo in recusados:
            print(f"  RECUSADO {id_}: {motivo}")
        return 1 if recusados else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
