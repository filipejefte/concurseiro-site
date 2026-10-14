"""Linha de comando da varredura: python -m varredura <comando>."""
import argparse
import sys

from . import dados, municipios, publicar


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m varredura", description="Varredura semanal de concursos (federais e do Paraná).")
    sub = p.add_subparsers(dest="comando", required=True)

    pub = sub.add_parser("publicar", help="gera assets/js/dados.js")
    pub.add_argument("--exemplo", action="store_true", help="usa os dados fictícios de dados/exemplo/")

    sub.add_parser("municipios", help="refaz dados/municipios-pr.json (IBGE + coordenadas)")

    args = p.parse_args(argv)
    if args.comando == "municipios":
        municipios.gerar()
    elif args.comando == "publicar":
        base = dados.ler_json(dados.EXEMPLO if args.exemplo else dados.CONCURSOS)
        n = len(publicar.gerar_js(base, exemplo=args.exemplo))
        print(f"dados.js gerado com {n} concursos{' (exemplo)' if args.exemplo else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
