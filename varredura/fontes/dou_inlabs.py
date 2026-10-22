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
JANELA_DIAS = 120   # o INLABS guarda 4 meses; pedir dia mais antigo só gera "sem ZIP" e derruba a coleta (3 dias úteis seguidos)
# DO1: atos normativos (autorização de concurso sai em portaria); DO3: editais e avisos. "E" = edição extra.
SECOES = ["DO1", "DO3", "DO1E", "DO3E"]


def _texto(trecho_html):
    trecho = re.sub(r"</(p|div|tr|li|h\d)>|<br\s*/?>", "\n", trecho_html or "", flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", trecho)).replace("\xa0", " ")


PARTE_DA_MATERIA = re.compile(r"_(\d+)-(\d+)\.xml$", re.I)   # 530_20261005_24450707-2.xml: parte 2 da matéria 24450707


def atos_do_zip(corpo, fonte="DOU"):
    """Lê as matérias de um ZIP do INLABS (um XML por matéria).

    Edital grande vem partido em vários XMLs da mesma matéria (nome terminado em -1, -2, -3...); a primeira parte
    leva o título e é a que a triagem lê. O texto das outras partes vai em `continuacao` da primeira, para a fila
    trazer o edital inteiro (o nome do arquivo da fila continua saindo só da primeira parte)."""
    atos = []
    primeiras, partes = {}, {}
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
            ato = Ato(
                fonte=fonte,
                data=f"{ano}-{mes}-{dia}",
                titulo=(_texto(identifica).strip() or artigo.get("name", ""))[:300],
                orgao=artigo.get("artCategory", ""),
                url=artigo.get("pdfPage", ""),
                texto=(_texto(identifica) + "\n" + texto).strip(),
            )
            atos.append(ato)
            parte = PARTE_DA_MATERIA.search(nome)
            if parte:
                materia, n = parte.group(1), int(parte.group(2))
                if n == 1:
                    primeiras[materia] = ato
                else:
                    partes.setdefault(materia, {})[n] = ato.texto
    for materia, ato in primeiras.items():
        ato.continuacao = "\n".join(texto for _, texto in sorted(partes.get(materia, {}).items()))
    return atos


def _faixas(dias):
    """Dias seguidos viram "AAAA-MM-DD a AAAA-MM-DD"; fim de semana no meio não quebra a faixa."""
    faixas, ini, fim = [], None, None
    for d in sorted(dias):
        if ini is not None and all((fim + timedelta(days=i)).weekday() >= 5 for i in range(1, (d - fim).days)):
            fim = d
            continue
        if ini is not None:
            faixas.append((ini, fim))
        ini = fim = d
    if ini is not None:
        faixas.append((ini, fim))
    return ", ".join(str(a) if a == b else f"{a} a {b}" for a, b in faixas)


class DouInlabs(Fonte):
    nome = "DOU"

    def __init__(self, cliente):
        super().__init__(cliente)
        self._logado = False
        self._sem_acesso = None    # motivo, depois de um login recusado: a coleta segue só com o que está no cache
        self.dias_sem_acesso = []  # dias úteis que não estavam no cache e não puderam ser baixados

    @property
    def aviso(self):
        """None, ou o que ficou de fora porque o INLABS recusou o login (a coleta de 21/10/2026 levou 403 do WAF
        do in.gov.br, para onde o inlabs.in.gov.br passou a redirecionar). O coletar põe isto no estado da fonte."""
        if not self.dias_sem_acesso:
            return None
        return (f"parcial: {len(self.dias_sem_acesso)} dia(s) útil(eis) fora do cache sem acesso ao INLABS "
                f"({_faixas(self.dias_sem_acesso)}): {self._sem_acesso}")

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
            if self._sem_acesso:
                return None, "sem acesso"
            try:
                self._entrar()
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError) as erro:
                self._sem_acesso = f"login recusado ({getattr(erro, 'code', None) or erro})"
                print(f"  INLABS: {self._sem_acesso}; só o cache será lido.", flush=True)
                return None, "sem acesso"
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
        primeiro = ate - timedelta(days=JANELA_DIAS)
        if desde < primeiro:
            print(f"DOU: o INLABS guarda 4 meses; a leitura começa em {primeiro}, não em {desde}.", flush=True)
            desde = primeiro
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
            if avisos and all(a.endswith("sem acesso") for a in avisos) and len(avisos) == len(SECOES):
                if dia.weekday() < 5:
                    self.dias_sem_acesso.append(dia)
                dia += timedelta(days=1)
                continue   # sem acesso não é login inválido: não entra na conta dos 3 dias úteis seguidos
            if dia.weekday() < 5:
                # Login inválido aparece como página no lugar do ZIP. 404 é dia sem edição (feriado) ou que já
                # saiu dos 4 meses do INLABS: não conta, senão a coleta inicial para logo nos primeiros dias.
                if n:
                    uteis_sem_arquivo = 0
                elif avisos:
                    uteis_sem_arquivo += 1
                if uteis_sem_arquivo >= 3:
                    raise SystemExit("O INLABS não entregou arquivo em 3 dias úteis seguidos. Confira INLABS_EMAIL e "
                                     "INLABS_SENHA e se o INLABS está no ar. " + "; ".join(avisos))
            dia += timedelta(days=1)
