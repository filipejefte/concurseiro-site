"""Verificador de links internos do site gerado: todo href e src que aponta para dentro do site precisa existir.

python -m gerador links [public]
Também recusa link "#" sozinho e âncora (#id) que não existe na página de destino.
"""
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path


class _Coletor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        for nome in ("href", "src", "action"):
            if nome in a:
                self.links.append((tag, a[nome]))


def _ler(arquivo):
    c = _Coletor()
    c.feed(arquivo.read_text(encoding="utf-8"))
    return c


def verificar(pasta, base_path="/"):
    """Lista de problemas: (página, link, motivo)."""
    pasta = Path(pasta)
    problemas, cache = [], {}

    def destino(caminho):
        alvo = pasta / caminho.lstrip("/")
        if caminho.endswith("/") or alvo.is_dir():
            alvo = alvo / "index.html"
        return alvo

    for pagina in sorted(pasta.rglob("*.html")):
        coletor = cache.setdefault(pagina, _ler(pagina))
        relativa = "/" + pagina.relative_to(pasta).as_posix()
        for tag, link in coletor.links:
            if link is None:
                continue
            if link == "#" or link.strip() == "":
                problemas.append((relativa, link, 'link vazio ou "#"'))
                continue
            partes = urllib.parse.urlsplit(link)
            if partes.scheme in ("http", "https", "mailto", "data", "tel") or partes.netloc:
                continue
            if partes.scheme:
                problemas.append((relativa, link, f"esquema estranho ({partes.scheme})"))
                continue
            if not partes.path:   # âncora na própria página
                if partes.fragment and partes.fragment not in coletor.ids:
                    problemas.append((relativa, link, "âncora não existe na página"))
                continue
            if not partes.path.startswith(base_path):
                problemas.append((relativa, link, f"link interno fora do base_path ({base_path})"))
                continue
            alvo = destino(urllib.parse.unquote(partes.path[len(base_path) - 1:]))
            if not alvo.exists():
                problemas.append((relativa, link, "destino não existe"))
            elif partes.fragment and alvo.suffix == ".html":
                ids = cache.setdefault(alvo, _ler(alvo)).ids
                if partes.fragment not in ids:
                    problemas.append((relativa, link, "âncora não existe no destino"))
    return problemas
