"""Interface das fontes e o cliente HTTP educado que todas usam.

Boas maneiras: respeita robots.txt, no máximo 1 requisição por segundo, User-Agent com o
projeto e um contato (CONTATO_VARREDURA no .env) e cache em .cache/ (fora do git).
"""
import hashlib
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass
from http.cookiejar import CookieJar

from ..dados import CACHE, SITE


@dataclass
class Ato:
    fonte: str      # DOU | AMP-PR | DIOE-PR
    data: str       # AAAA-MM-DD da publicação
    titulo: str
    orgao: str
    url: str        # link oficial do ato (ou da edição)
    texto: str

    def como_dict(self):
        return asdict(self)


class Fonte:
    """Uma fonte oficial. listar_atos devolve os atos publicados entre as datas (inclusive)."""
    nome = ""

    def __init__(self, cliente):
        self.cliente = cliente

    def listar_atos(self, desde, ate):
        raise NotImplementedError


class Cliente:
    def __init__(self, contato=None, intervalo=1.0, cache=CACHE):
        contato = contato or os.environ.get("CONTATO_VARREDURA")
        if not contato:
            raise SystemExit("Defina CONTATO_VARREDURA no .env (e-mail ou página de contato do projeto) antes de coletar.")
        texto = f"concurseiro-varredura/0.1 (+{SITE}; contato: {contato})"
        self.user_agent = texto.encode("ascii", "ignore").decode()  # cabeçalho HTTP só aceita ASCII
        self.intervalo = intervalo
        self.cache = cache
        self._ultimo = 0.0
        self._robots = {}
        self._abridor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def _esperar(self):
        falta = self.intervalo - (time.monotonic() - self._ultimo)
        if falta > 0:
            time.sleep(falta)
        self._ultimo = time.monotonic()

    def _pedir(self, url, dados=None, cabecalhos=None):
        self._esperar()
        corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
        pedido = urllib.request.Request(url, data=corpo, headers={"User-Agent": self.user_agent, **(cabecalhos or {})})
        with self._abridor.open(pedido, timeout=180) as resp:
            return resp.read()

    def permitido(self, url):
        partes = urllib.parse.urlsplit(url)
        base = f"{partes.scheme}://{partes.netloc}"
        if base not in self._robots:
            regras = urllib.robotparser.RobotFileParser()
            try:
                regras.parse(self._pedir(base + "/robots.txt").decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as erro:
                # Sem robots.txt (404) = sem restrição; 401/403 = tudo proibido, como no robotparser.
                regras.disallow_all = erro.code in (401, 403)
                regras.allow_all = not regras.disallow_all
            self._robots[base] = regras
        return self._robots[base].can_fetch(self.user_agent, url)

    def arquivo_cache(self, url, dados=None, extensao=""):
        chave = hashlib.sha256((url + repr(sorted((dados or {}).items()))).encode()).hexdigest()[:24]
        return self.cache / urllib.parse.urlsplit(url).netloc / (chave + extensao)

    def baixar(self, url, dados=None, cabecalhos=None, usar_cache=True, extensao=""):
        """Corpo da resposta em bytes. Com usar_cache, o arquivo fica em .cache/<host>/ e não é pedido de novo."""
        arquivo = self.arquivo_cache(url, dados, extensao)
        if usar_cache and arquivo.exists():
            return arquivo.read_bytes()
        if not self.permitido(url):
            raise PermissionError(f"robots.txt não permite: {url}")
        corpo = self._pedir(url, dados, cabecalhos)
        if usar_cache:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_bytes(corpo)
        return corpo
