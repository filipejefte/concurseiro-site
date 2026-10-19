"""Linha de comando do gerador: python -m gerador <comando>.

  build [--exemplo] [--hoje AAAA-MM-DD] [--saida public] [--plataforma github|cloudflare] [--previa [PASTA]]
        gera o site em public/ a partir de dados/concursos.json e do site.toml
        --previa junta as fichas da varredura (a mais recente, ou PASTA) sem conferência, em previa/: só para olhar
  links [pasta]   confere os links internos do site gerado (o CI roda depois do build)
  redirecionar [--saida publicar-github] [--base-antiga /concurseiro-site/]
        site mínimo que leva o endereço antigo do GitHub Pages ao site_url novo
  servir [--porta 8000]   serve o public/ no computador, no mesmo caminho do site no ar
"""
import argparse
import sys
import time
from datetime import date
from pathlib import Path

from . import config as configuracao
from .build import PREVIA, SAIDA, construir
from .links import verificar


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m gerador", description="Gera o site estático do Concurseiro.")
    sub = p.add_subparsers(dest="comando", required=True)
    b = sub.add_parser("build", help="gera o site em public/")
    b.add_argument("--saida", type=Path, default=None)
    b.add_argument("--hoje", type=date.fromisoformat, help="data do build (padrão: hoje em Brasília)")
    b.add_argument("--exemplo", action="store_true", help="junta os concursos fictícios de dados/exemplo/ (marcados como exemplo)")
    b.add_argument("--plataforma", choices=["github", "cloudflare"], default="github",
                   help="cloudflare liga a sugestão de cidade pelo IP (Pages Function /api/local)")
    b.add_argument("--previa", nargs="?", const="ultima", type=str, default=None, metavar="PASTA",
                   help="junta as fichas da varredura (sem conferência) para olhar o site com o volume real; sai em previa/")
    l = sub.add_parser("links", help="confere os links internos do site gerado")
    l.add_argument("pasta", nargs="?", type=Path, default=SAIDA)
    r = sub.add_parser("redirecionar", help="site mínimo que leva o endereço antigo do GitHub Pages ao site_url novo")
    r.add_argument("--saida", type=Path, default=Path("publicar-github"))
    r.add_argument("--base-antiga", default="/concurseiro-site/")
    s = sub.add_parser("servir", help="serve o public/ em http://localhost:8000 com o base_path")
    s.add_argument("--porta", type=int, default=8000)
    s.add_argument("pasta", nargs="?", type=Path, default=SAIDA)
    args = p.parse_args(argv)

    cfg = configuracao.ler()
    if args.comando == "build":
        inicio = time.monotonic()
        previa = None
        if args.previa:
            from varredura import dados
            previa = dados.ultima_pasta() if args.previa == "ultima" else Path(args.previa)
        saida = args.saida or (PREVIA if previa else SAIDA)
        if previa and saida.resolve() == SAIDA.resolve():
            raise SystemExit("A prévia não vai para public/ (é a pasta que o deploy publica). Use outra --saida.")
        args.saida = saida
        site = construir(saida, args.hoje, args.exemplo, args.plataforma, cfg, previa=previa)
        tipos = {}
        for pagina in site.paginas:
            tipos[pagina.tipo] = tipos.get(pagina.tipo, 0) + 1
        print(f"{len(site.paginas)} páginas em {args.saida} ({', '.join(f'{n} {t}' for t, n in sorted(tipos.items()))}) "
              f"em {time.monotonic() - inicio:.1f} s. indexar = {str(cfg.indexar).lower()}.")
        if not site.marca["logotipo"]:
            print("Aviso: sem docs/marca/logotipo-concurseiro.svg (nem .png); o cabeçalho usa o logotipo provisório do protótipo.")
        if cfg.pendentes():
            print("[A PREENCHER] no site.toml: " + ", ".join(cfg.pendentes()))
        return 0
    if args.comando == "redirecionar":
        from .redirecionar import gerar
        if cfg.base_path == args.base_antiga:
            raise SystemExit("O site_url ainda é o do GitHub Pages: troque site_url e base_path no site.toml antes.")
        gerar(args.saida, cfg.site_url, args.base_antiga)
        print(f"Redirecionamento para {cfg.site_url} em {args.saida}")
        return 0
    if args.comando == "servir":
        from .servir import servir
        if not (args.pasta / "index.html").exists():
            raise SystemExit("Gere o site antes: python -m gerador build")
        servir(args.pasta, cfg.base_path, args.porta)
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
