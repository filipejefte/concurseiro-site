"""Diário Oficial da União pelo INLABS (Imprensa Nacional).

Como o download funciona (repositório Imprensa-Nacional/inlabs): login em logar.php com e-mail e
senha, que deixa o cookie inlabs_session_cookie, e um ZIP de XML por dia e seção em
index.php?p=AAAA-MM-DD&dl=AAAA-MM-DD-DO3.zip. O INLABS guarda só os últimos 4 meses.
Credenciais: INLABS_EMAIL e INLABS_SENHA no .env (cadastro gratuito em inlabs.in.gov.br).
"""
import html
import io
import os
import re
import urllib.error
import zipfile
import xml.etree.ElementTree as ET
from datetime import timedelta

from .base import Ato, Fonte

URL_LOGIN = "https://inlabs.in.gov.br/logar.php"
URL_DOWNLOAD = "https://inlabs.in.gov.br/index.php?p={dia}&dl={dia}-{secao}.zip"
# DO1: atos normativos (autorização de concurso sai em portaria); DO3: editais e avisos. "E" = edição extra.
SECOES = ["DO1", "DO3", "DO1E", "DO3E"]


def _texto(trecho_html):
    trecho = re.sub(r"</(p|div|tr|li|h\d)>|<br\s*/?>", "\n", trecho_html or "", flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", trecho)).replace("\xa0", " ")


def atos_do_zip(corpo, fonte="DOU"):
    """Lê as matérias de um ZIP do INLABS (um XML por matéria)."""
    atos = []
    with zipfile.ZipFile(io.BytesIO(corpo)) as z:
        for nome in z.namelist():
            if not nome.lower().endswith(".xml"):
                continue
            raiz = ET.fromstring(z.read(nome))
            artigo = raiz if raiz.tag == "article" else raiz.find(".//article")
            if artigo is None:
                continue
            dia, mes, ano = (artigo.get("pubDate") or "01/01/1900").split("/")
            corpo_xml = artigo.find("body")
            identifica = corpo_xml.findtext("Identifica", "") if corpo_xml is not None else ""
            texto = _texto(corpo_xml.findtext("Texto", "")) if corpo_xml is not None else ""
            atos.append(Ato(
                fonte=fonte,
                data=f"{ano}-{mes}-{dia}",
                titulo=(_texto(identifica).strip() or artigo.get("name", ""))[:300],
                orgao=artigo.get("artCategory", ""),
                url=artigo.get("pdfPage", ""),
                texto=(_texto(identifica) + "\n" + texto).strip(),
            ))
    return atos


class DouInlabs(Fonte):
    nome = "DOU"

    def __init__(self, cliente):
        super().__init__(cliente)
        self._logado = False

    def _entrar(self):
        email, senha = os.environ.get("INLABS_EMAIL"), os.environ.get("INLABS_SENHA")
        if not (email and senha):
            raise SystemExit("Defina INLABS_EMAIL e INLABS_SENHA no .env para ler o DOU pelo INLABS.")
        self.cliente.baixar(URL_LOGIN, dados={"email": email, "password": senha}, usar_cache=False,
                            cabecalhos={"Content-Type": "application/x-www-form-urlencoded"})
        self._logado = True

    def listar_atos(self, desde, ate):
        atos = []
        dia = desde
        while dia <= ate:
            for secao in SECOES:
                url = URL_DOWNLOAD.format(dia=dia.isoformat(), secao=secao)
                if not self._logado and not self.cliente.arquivo_cache(url, extensao=".zip").exists():
                    self._entrar()
                try:
                    corpo = self.cliente.baixar(url, cabecalhos={"origem": "736372697074"}, extensao=".zip")
                except urllib.error.HTTPError as erro:
                    if erro.code == 404:  # dia sem edição (ou sem edição extra)
                        continue
                    raise
                if not corpo.startswith(b"PK"):
                    # Sem login válido o INLABS devolve uma página HTML: não guardar isso como ZIP.
                    self.cliente.arquivo_cache(url, extensao=".zip").unlink(missing_ok=True)
                    raise SystemExit(f"O INLABS não devolveu um ZIP para {dia} {secao}. Confira INLABS_EMAIL e INLABS_SENHA.")
                atos.extend(atos_do_zip(corpo))
            dia += timedelta(days=1)
        return atos
