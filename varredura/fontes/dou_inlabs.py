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
from datetime import date, timedelta

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
            try:
                raiz = ET.fromstring(z.read(nome))
            except ET.ParseError:
                print(f"  XML ilegível no ZIP, pulado: {nome}", flush=True)
                continue
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

    def _zip(self, url, dia):
        """(corpo do ZIP, None) ou (None, motivo) quando não há arquivo.

        Um login só por coleta: em 14/10/2026 o INLABS parou de responder por 10 a 15 minutos logo
        depois de vários logins seguidos, então a coleta evita entrar de novo.
        Dia sem edição pode vir como 404 ou como a página inicial do INLABS (domingo); login
        inválido aparece como dias úteis seguidos sem arquivo (ver listar_atos).
        """
        cache = self.cliente.arquivo_cache(url, extensao=".zip")
        # Dia passado sem arquivo também fica marcado no cache: refazer a coleta não pergunta de novo.
        sem_arquivo = cache.with_suffix(".sem-arquivo")
        if sem_arquivo.exists():
            return None, "404"
        if not self._logado and not cache.exists():
            self._entrar()
        try:
            corpo = self.cliente.baixar(url, cabecalhos={"origem": "736372697074"}, extensao=".zip")
        except urllib.error.HTTPError as erro:
            if erro.code != 404:
                raise
            motivo = "404"
        else:
            if corpo.startswith(b"PK"):
                return corpo, None
            cache.unlink(missing_ok=True)  # página HTML não vai para o cache
            motivo = "resposta sem ZIP"
        # Só marca o que é certo: 404, ou página HTML em fim de semana. HTML em dia útil pode ser
        # sessão inválida, e marcar esconderia o DOU daquele dia para sempre.
        if dia < date.today() and (motivo == "404" or dia.weekday() >= 5):
            sem_arquivo.parent.mkdir(parents=True, exist_ok=True)
            sem_arquivo.touch()
        return None, motivo

    def listar_atos(self, desde, ate):
        uteis_sem_arquivo = 0
        dia = desde
        while dia <= ate:
            n, avisos = 0, []
            for secao in SECOES:
                corpo, motivo = self._zip(URL_DOWNLOAD.format(dia=dia.isoformat(), secao=secao), dia)
                if corpo is None:
                    if motivo != "404":
                        avisos.append(f"{secao}: {motivo}")
                    continue
                atos = atos_do_zip(corpo)
                n += len(atos)
                yield from atos
            print(f"DOU {dia}: {n} matérias" + (f" (sem arquivo: {'; '.join(avisos)})" if avisos else ""), flush=True)
            if dia.weekday() < 5:
                uteis_sem_arquivo = 0 if n else uteis_sem_arquivo + 1
                if uteis_sem_arquivo >= 3:
                    raise SystemExit("O INLABS não entregou arquivo em 3 dias úteis seguidos. Confira INLABS_EMAIL e "
                                     "INLABS_SENHA e se o INLABS está no ar. " + "; ".join(avisos))
            dia += timedelta(days=1)
