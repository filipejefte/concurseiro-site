"""Linha de comando do gerador: python -m gerador <comando>.

  build [--exemplo] [--hoje AAAA-MM-DD] [--saida public] [--plataforma github|cloudflare]
        gera o site em public/ a partir de dados/concursos.json e do site.toml
  links [pasta]   confere os links internos do site gerado (o CI roda depois do build)
  redirecionar [--saida publicar-github] [--base-antiga /concurseiro-site/]
        site mínimo que leva o endereço antigo do GitHub Pages ao site_url novo
"""
import argparse
import sys
import time
from datetime import date
from pathlib import Path

from . import config as configuracao
from .build import SAIDA, construir
from .links import verificar


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m gerador", description="Gera o site estático do Concurseiro.")
    sub = p.add_subparsers(dest="comando", required=True)
    b = sub.add_parser("build", help="gera o site em public/")
    b.add_argument("--saida", type=Path, default=SAIDA)
    b.add_argument("--hoje", type=date.fromisoformat, help="data do build (padrão: hoje em Brasília)")
    b.add_argument("--exemplo", action="store_true", help="junta os concursos fictícios de dados/exemplo/ (marcados como exemplo)")
    b.add_argument("--plataforma", choices=["github", "cloudflare"], default="github",
                   help="cloudflare liga a sugestão de cidade pelo IP (Pages Function /api/local)")
    l = sub.add_parser("links", help="confere os links internos do site gerado")
    l.add_argument("pasta", nargs="?", type=Path, default=SAIDA)
    r = sub.add_parser("redirecionar", help="site mínimo que leva o endereço antigo do GitHub Pages ao site_url novo")
    r.add_argument("--saida", type=Path, default=Path("publicar-github"))
    r.add_argument("--base-antiga", default="/concurseiro-site/")
    args = p.parse_args(argv)

    cfg = configuracao.ler()
    if args.comando == "build":
        inicio = time.monotonic()
        site = construir(args.saida, args.hoje, args.exemplo, args.plataforma, cfg)
        tipos = {}
        for pagina in site.paginas:
            tipos[pagina.tipo] = tipos.get(pagina.tipo, 0) + 1
        print(f"{len(site.paginas)} páginas em {args.saida} ({', '.join(f'{n} {t}' for t, n in sorted(tipos.items()))}) "
              f"em {time.monotonic() - inicio:.1f} s. indexar = {str(cfg.indexar).lower()}.")
        if not site.marca["logotipo"]:
            print("Aviso: sem docs/marca/logotipo-concurseiro.svg; o cabeçalho usa o logotipo provisório do protótipo.")
        return 0
    if args.comando == "redirecionar":
        from .redirecionar import gerar
        if cfg.base_path == args.base_antiga:
            raise SystemExit("O site_url ainda é o do GitHub Pages: troque site_url e base_path no site.toml antes.")
        gerar(args.saida, cfg.site_url, args.base_antiga)
        print(f"Redirecionamento para {cfg.site_url} em {args.saida}")
        return 0
    if args.comando == "links":
        problemas = verificar(args.pasta, cfg.base_path)
        for pagina, link, motivo in problemas:
            print(f"{pagina}: {link} ({motivo})")
        n = sum(1 for _ in args.pasta.rglob("*.html"))
        print(f"{n} páginas conferidas; " + ("nenhum link quebrado." if not problemas else f"{len(problemas)} link(s) com problema."))
        return 1 if problemas else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
