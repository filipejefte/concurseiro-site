"""Linha de comando da varredura: python -m varredura <comando>.

  coletar --inicial --desde 2026-07-01   primeira varredura: tudo desde a data, fica o que tem inscrição aberta
  coletar --semana                       desde a última varredura publicada até hoje
  pendentes [--resumo]                   atos da fila ainda sem ficha nem descarte (--resumo: por prioridade)
  progresso                              atualiza progresso.md: o que falta extrair, por fonte e prioridade
  validar                                schema e regras, na base publicada e nas fichas da semana
  revisao                                revisao.md e revisao.csv na pasta da semana
  publicar --por "Nome"                  publica só o que foi conferido; resumos do Telegram e do WhatsApp e posts
  telegram [--teste]                     posta o resumo da semana no canal do Telegram (--teste só imprime)
  municipios                             refaz dados/municipios-pr.json

O site sai de dados/concursos.json com `python -m gerador build`.
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

    val = sub.add_parser("validar", help="checa schema e regras")
    val.add_argument("--pasta", type=Path, help="pasta da varredura (padrão: a mais recente)")
    val.add_argument("--exemplo", action="store_true", help="valida os dados de exemplo")

    pen = sub.add_parser("pendentes", help="lista os atos da fila que ainda não viraram ficha nem descarte")
    pen.add_argument("--pasta", type=Path)
    pen.add_argument("--resumo", action="store_true",
                     help="em ordem de prioridade (P1 inscrição aberta ou futura, P2 previsto recente, P3 o resto), "
                          "com classe, órgão, título e o trecho das inscrições")

    pro = sub.add_parser("progresso", help="atualiza progresso.md na pasta da semana (o que falta extrair, por fonte)")
    pro.add_argument("--pasta", type=Path)

    rev = sub.add_parser("revisao", help="gera revisao.md e revisao.csv")
    rev.add_argument("--pasta", type=Path)

    pub = sub.add_parser("publicar", help="publica o que foi conferido em dados/concursos.json")
    pub.add_argument("--pasta", type=Path)
    pub.add_argument("--por", default=os.environ.get("CONFERENTE"), help="quem conferiu (ou CONFERENTE no .env)")
    pub.add_argument("--sem-posts", action="store_true", help="não gera as imagens dos posts")

    tel = sub.add_parser("telegram", help="posta resumo-telegram.md no canal (TELEGRAM_BOT_TOKEN e TELEGRAM_CANAL)")
    tel.add_argument("--pasta", type=Path)
    tel.add_argument("--teste", action="store_true", help="só imprime as mensagens, sem postar")
    tel.add_argument("--se-configurado", action="store_true", help="sem as variáveis, avisa e sai sem erro (para o CI)")

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
        coletar(desde, args.ate, inicial=args.inicial)
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
        if args.resumo:
            from .extracao import prioridade, resumo_do_ato
            hoje = date.today()
            faltam.sort(key=lambda a: prioridade(a, hoje))   # extrair nesta ordem: P1, P2, P3
            for arquivo in faltam:
                print(resumo_do_ato(arquivo, hoje))
        else:
            for arquivo in faltam:
                print(arquivo)
        print(f"{len(faltam)} ato(s) pendente(s) em {pasta / 'fila'}")
        return 0

    if args.comando == "progresso":
        from .progresso import escrever
        arquivo, faltam = escrever(args.pasta or dados.ultima_pasta())
        print(f"{arquivo}: faltam {faltam} ato(s).")
        return 0

    if args.comando == "revisao":
        from .revisao import gerar
        pasta = args.pasta or dados.ultima_pasta()
        r, problemas = gerar(pasta)
        print(f"{pasta / 'revisao.md'} e revisao.csv: {len(r.novos)} novos, {len(r.alterados)} alterados, "
              f"{len(r.encerrados)} encerrados, {len(problemas)} com problema de validação.")
        return 0

    if args.comando == "publicar":
        from .publicar import publicar_semana
        if not args.por:
            p.error('diga quem conferiu: --por "Nome" (ou CONFERENTE no .env)')
        pasta = args.pasta or dados.ultima_pasta()
        aprovados, recusados = publicar_semana(pasta, args.por, posts=not args.sem_posts)
        print(f"Publicados {len(aprovados)} concursos em dados/concursos.json. Na pasta {pasta}: resumo-telegram.md, "
              "resumo-whatsapp.txt e posts/. Para ver o site: python -m gerador build")
        for id_, motivo in recusados:
            print(f"  RECUSADO {id_}: {motivo}")
        return 1 if recusados else 0

    if args.comando == "telegram":
        from .telegram import postar
        return postar(args.pasta or dados.ultima_pasta(), teste=args.teste, se_configurado=args.se_configurado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
