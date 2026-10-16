"""O endereço antigo (GitHub Pages) depois da mudança para o domínio próprio no Cloudflare.

python -m gerador redirecionar [--saida publicar-github] [--base-antiga /concurseiro-site/]
Gera um site mínimo: index.html e 404.html levam cada caminho antigo ao mesmo caminho no site_url novo
(o GitHub Pages serve o 404.html para qualquer endereço que não existe). Sempre com noindex.
"""
import json
from pathlib import Path

from markupsafe import escape

MODELO = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, follow">
<title>O Concurseiro mudou de endereço</title>
<link rel="canonical" href="{novo}/">
<meta http-equiv="refresh" content="0; url={novo}/">
<style>body{{font:16px/1.5 system-ui,sans-serif;background:#f7f6f1;color:#14211b;margin:0;padding:32px 16px}}a{{color:#0b6b48;font-weight:600}}</style>
</head>
<body>
<main>
<h1 style="font-size:22px">O Concurseiro mudou de endereço</h1>
<p>Agora estamos em <a href="{novo}/" data-destino>{novo_texto}</a>.</p>
</main>
<script>
(function () {{
  var antiga = {antiga}, novo = {novo_js};
  var caminho = location.pathname.indexOf(antiga) === 0 ? location.pathname.slice(antiga.length) : '';
  var destino = novo + '/' + caminho + location.search + location.hash;
  document.querySelector('[data-destino]').href = destino;
  location.replace(destino);
}})();
</script>
</body>
</html>
"""


def gerar(saida, site_url, base_antiga="/concurseiro-site/"):
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    base_antiga = "/" + base_antiga.strip("/") + "/" if base_antiga.strip("/") else "/"
    html = MODELO.format(novo=escape(site_url), novo_texto=escape(site_url.split("://", 1)[-1]),
                         antiga=json.dumps(base_antiga), novo_js=json.dumps(site_url))
    for nome in ("index.html", "404.html"):
        (saida / nome).write_text(html, encoding="utf-8", newline="\n")
    (saida / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8", newline="\n")
    return saida
