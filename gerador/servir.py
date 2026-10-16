"""Serve o site gerado no computador, no mesmo caminho do site no ar (base_path do site.toml).

python -m gerador servir [--porta 8000]   ->   http://localhost:8000/concurseiro-site/
"""
import functools
import http.server
import posixpath


class _Handler(http.server.SimpleHTTPRequestHandler):
    base = "/"

    def translate_path(self, path):
        caminho = path.split("?", 1)[0].split("#", 1)[0]
        if caminho.startswith(self.base):
            caminho = "/" + caminho[len(self.base):]
        elif self.base != "/":
            caminho = "/404.html"
        return super().translate_path(posixpath.normpath(caminho) + ("/" if caminho.endswith("/") else ""))

    def send_error(self, code, message=None, explain=None):
        if code == 404:   # como no GitHub Pages e no Cloudflare: a página 404 do site
            self.path = self.base + "404.html"
            arquivo = self.translate_path(self.path)
            try:
                with open(arquivo, "rb") as f:
                    corpo = f.read()
            except OSError:
                return super().send_error(code, message, explain)
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        super().send_error(code, message, explain)


def servir(pasta, base_path, porta=8000):
    handler = functools.partial(type("Handler", (_Handler,), {"base": base_path}), directory=str(pasta))
    with http.server.ThreadingHTTPServer(("127.0.0.1", porta), handler) as servidor:
        print(f"Site em http://localhost:{porta}{base_path} (Ctrl+C para parar)")
        servidor.serve_forever()
