"""Bancas organizadoras lidas direto no site oficial (regra 2: o site da banca é fonte oficial do edital).

Cada leitor abre a página de concursos com inscrição aberta da banca e a página de cada concurso, acha o PDF do edital
(o mais atual: retificado ou consolidado, se houver) e devolve um `Concurso`. A fonte `Bancas` baixa o PDF, tira o texto
(cache em .cache/) e entrega um `Ato` por concurso aberto, com `fonte: "banca-<slug>"`: é o ato da ficha.

Respeitam o robots.txt, 1 requisição por segundo e o cache em .cache/ (tudo isso é do Cliente). Cobertura: só
federal (qualquer UF) e Paraná; processo seletivo simplificado fica de fora (regra do projeto).

Plataformas (as páginas mudam pouco, os testes usam trechos reais em tests/dados/bancas/):
  ProSeleta, página nova   FAFIPA     /concurso/<id>-<slug>, lista com JSON-LD
  ProSeleta, página antiga Quadrix, Omni   /index/abertos/ e /informacoes/<id>/
  próprios                 FAU (Unicentro), Instituto Unicampo, Instituto Consulplan
"""
import html
import json
import re
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from datetime import date

from ..dados import chave_nome
from .base import Ato, Fonte

DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
# Documento que não é o edital do concurso: retificação, resultado, convocação, cronograma, isenção...
NAO_E_EDITAL = re.compile(r"retifica|errata|resultado|gabarito|deferimento|convoca|homologa|cronograma|isen[çc]|locais|ensalamento|recurso|"
                          r"classifica|aviso|comunicado|corre[çc][ãa]o|divulga[çc][ãa]o|prorroga", re.I)
ATUALIZADO = re.compile(r"retificado|atualizado|consolidado", re.I)
PSS = re.compile(r"processo\s+seletivo|teste\s+seletivo|\bpss\b|sele[çc][ãa]o\s+simplificada|contrata[çc][ãa]o\s+tempor", re.I)
# Órgão federal (qualquer UF) entra mesmo sem "PR"; prefeitura, câmara e estado só entram no Paraná.
FEDERAL = re.compile(r"universidade federal|instituto federal|\bconselho (regional|federal)\b|tribunal (regional|superior)|minist[ée]rio|"
                     r"pol[ií]cia (federal|rodovi[áa]ria)|receita federal|banco (central|do brasil)|caixa econ|correios|defensoria p[úu]blica da uni|"
                     r"justi[çc]a federal|c[âa]mara dos deputados|senado federal|ebserh|hospital universit|fiocruz", re.I)
MUNICIPAL_OU_ESTADUAL = re.compile(r"prefeitura|munic[ií]pio|c[âa]mara municipal|secretaria (municipal|estadual)|cons[óo]rcio|governo d[eo] estado", re.I)
UF_NO_FIM = re.compile(r"(?:[-–/(]\s*|\s)([A-Za-z]{2})\.?\s*\)?\s*$")
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}


def iso(texto):
    m = DATA.search(texto or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def limpar(trecho):
    """Texto de um pedaço de HTML: sem tags, com entidades resolvidas e espaços simples."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", trecho or ""))).strip()


def decodificar(corpo):
    try:
        return corpo.decode("utf-8")
    except UnicodeDecodeError:
        return corpo.decode("latin-1")


def uf_do_nome(nome):
    achado = UF_NO_FIM.search((nome or "").strip())
    if not achado:
        return None
    uf = achado.group(1)
    # minúscula só vale depois de hífen, barra ou parêntese ("Altônia -Pr."): "de" e "da" no fim do nome não são UF
    return uf.upper() if uf.upper() in UFS and (uf.isupper() or re.search(r"[-–/(]\s*"+uf, nome or "")) else None


@dataclass
class Documento:
    titulo: str
    url: str
    data: str = None   # AAAA-MM-DD


@dataclass
class Concurso:
    banca: str
    titulo: str
    orgao: str
    pagina: str
    tipo: str = ""
    uf: str = None
    numero: str = None
    inscricao_inicio: str = None
    inscricao_fim: str = None
    prova: str = None
    documentos: list = field(default_factory=list)

    @property
    def edital(self):
        """O PDF do edital: entre os documentos que começam por "Edital" e não são retificação, resultado ou convocação, o
        retificado, atualizado ou consolidado mais recente; sem esse, o primeiro da página."""
        editais = [d for d in self.documentos if re.match(r"\s*edital", d.titulo, re.I)]
        atualizados = [d for d in editais if ATUALIZADO.search(d.titulo)]
        if atualizados:
            return max(atualizados, key=lambda d: d.data or "")
        return next((d for d in editais if not NAO_E_EDITAL.search(d.titulo)), None)


def dentro_da_cobertura(c):
    """Federal de qualquer UF, ou qualquer órgão do Paraná. Processo seletivo simplificado fica de fora. UF desconhecida e
    órgão que não é federal: fora (só entra com a UF PR)."""
    if PSS.search(c.titulo) or PSS.search(c.tipo) or (c.tipo and "concurso" not in c.tipo.lower()):
        return False
    if c.uf == "PR":
        return True
    return bool(FEDERAL.search(c.orgao) or FEDERAL.search(c.titulo)) and not MUNICIPAL_OU_ESTADUAL.search(c.orgao)


def aberto(c, hoje):
    """Aberto: a inscrição ainda não terminou. Sem data de fim na página, vale como aberto (o edital diz o resto)."""
    return not c.inscricao_fim or c.inscricao_fim >= hoje.isoformat()


# ---------- ProSeleta (FAFIPA, Quadrix, Omni) ----------

class ProSeletaNova:
    """Página nova da ProSeleta (FAFIPA): a lista traz JSON-LD e a página do concurso traz as linhas "det-row"."""
    def __init__(self, slug, nome, base, lista="?situacao=abertas"):
        self.slug, self.nome, self.base, self.lista = slug, nome, base, lista

    def urls_da_lista(self, pagina):
        achados = []
        for bloco in re.findall(r'<script type="application/ld\+json">(.*?)</script>', pagina, re.S):
            try:
                dados = json.loads(bloco)
            except ValueError:
                continue
            if dados.get("@type") == "ItemList":
                achados += [(i["name"], i["url"]) for i in dados.get("itemListElement", [])]
        return achados

    def concurso(self, pagina, url):
        linhas = {limpar(k): limpar(v) for k, v in re.findall(r'<div class="det-row"><span>(.*?)</span><b>(.*?)</b></div>', pagina, re.S)}
        titulo = limpar((re.search(r'<h1 id="det-titulo">(.*?)</h1>', pagina, re.S) or [None, ""])[1])
        local = linhas.get("Local", "")
        uf = local.rsplit("·", 1)[-1].strip() if "·" in local else uf_do_nome(titulo)
        inscricao = linhas.get("Inscrições", "")
        datas = DATA.findall(inscricao)
        alerta = re.search(r'class="det-alerta">(.*?)</div>', pagina, re.S)
        docs, secao = [], ""
        for m in re.finditer(r"<h3>(.*?)</h3>|<a href=\"([^\"]+\.pdf)\"[^>]*>(.*?)</a>", pagina, re.S):
            if m.group(1) is not None:
                secao = limpar(m.group(1))
            elif secao.lower().startswith("editai"):
                data = DATA.search(m.group(3) or "")
                texto = limpar(re.sub(r'<span class="txt-meta".*?</span>', "", m.group(3), flags=re.S))
                docs.append(Documento(texto, m.group(2), f"{data.group(3)}-{data.group(2)}-{data.group(1)}" if data else None))
        return Concurso(self.slug, titulo, linhas.get("Órgão", titulo), url, linhas.get("Tipo", ""), uf,
                        (re.search(r"n[º°.]*\s*([\d./]+)", linhas.get("Edital", "")) or [None, None])[1],
                        f"{datas[0][2]}-{datas[0][1]}-{datas[0][0]}" if datas else None,
                        f"{datas[1][2]}-{datas[1][1]}-{datas[1][0]}" if len(datas) > 1 else None,
                        iso(alerta.group(1)) if alerta and "prova" in alerta.group(1).lower() else None, docs)

    def listar(self, cliente):
        pagina = decodificar(cliente.baixar(self.base + self.lista, usar_cache=False))
        for _, url in self.urls_da_lista(pagina):
            yield self.concurso(decodificar(cliente.baixar(url)), url)


class ProSeletaAntiga:
    """Página antiga da ProSeleta (Quadrix, Omni): /index/abertos/ e /informacoes/<id>/."""
    def __init__(self, slug, nome, base):
        self.slug, self.nome, self.base = slug, nome, base

    def itens_da_lista(self, pagina):
        itens = []
        for bloco in pagina.split('<li class="item">')[1:]:
            link = re.search(r'<h3><a href="(/informacoes/\d+/)"\s*>(.*?)</a>', bloco, re.S)
            if not link:
                continue
            tipo = limpar((re.search(r'<p class="tipo">(.*?)</p>', bloco, re.S) or [None, ""])[1])
            numero = limpar((re.search(r'<span class="editaln">.*?</span>(.*?)</p>', bloco, re.S) or [None, ""])[1])
            insc = re.search(r"Inscri.{1,3}es de\s*<b>(.*?)</b>\s*a\s*<b>(.*?)</b>", bloco, re.S)
            itens.append(Concurso(self.slug, limpar(link.group(2)), limpar(link.group(2)), self.base + link.group(1), tipo,
                                  uf_do_nome(limpar(link.group(2))), numero or None, iso(insc.group(1)) if insc else None,
                                  iso(insc.group(2)) if insc else None))
        return itens

    def documentos(self, pagina):
        docs = []
        for m in re.finditer(r'<li class="pdf".*?<a [^>]*data-astv="([^"]*)"\s*href="([^"]+\.pdf)".*?<span>\s*([\d/]*)\s*</span>', pagina, re.S):
            docs.append(Documento(html.unescape(m.group(1)).strip(), m.group(2), iso(m.group(3))))
        return docs

    def completar(self, c, pagina):
        c.documentos = self.documentos(pagina)
        if not c.inscricao_fim:
            datas = DATA.findall(limpar((re.search(r'<p class="insc">(.*?)</p>', pagina, re.S) or [None, ""])[1]))
            if len(datas) > 1:
                c.inscricao_inicio, c.inscricao_fim = f"{datas[0][2]}-{datas[0][1]}-{datas[0][0]}", f"{datas[1][2]}-{datas[1][1]}-{datas[1][0]}"
        cabeca = limpar((re.search(r"Edital:</b>(.*?)</p>", pagina, re.S) or [None, ""])[1])
        data_edital = iso(cabeca)
        for d in c.documentos:
            if not d.data and re.match(r"\s*edital", d.titulo, re.I) and not NAO_E_EDITAL.search(d.titulo):
                d.data = data_edital   # o edital de abertura vem sem data própria: vale a do cabeçalho "Edital: 001/2026 de 05/10/2026"
        return c

    def listar(self, cliente):
        for c in self.itens_da_lista(decodificar(cliente.baixar(self.base + "/index/abertos/", usar_cache=False))):
            yield self.completar(c, decodificar(cliente.baixar(c.pagina)))


# ---------- FAU (Fundação de Apoio da Unicentro) ----------

class Fau:
    slug, nome, base = "fau", "FAU (Fundação de Apoio ao Desenvolvimento da UNICENTRO)", "https://www.concursosfau.com.br"

    def itens_da_lista(self, pagina):
        """Só a seção "Concursos em Aberto": cada cartão traz o nome, a data da prova e o link da página."""
        inicio = pagina.find("Concursos em Aberto")
        fim = pagina.find("Concursos em Andamento", inicio)
        itens = []
        for bloco in pagina[inicio:fim if fim > 0 else None].split("portal-card-concurso")[1:]:
            link = re.search(r'href="(https://www\.concursosfau\.com\.br/novo/concurso/[\w-]+)"', bloco)
            nome = limpar((re.search(r"<h3[^>]*>(.*?)</h3>", bloco, re.S) or [None, ""])[1])
            if link and nome:
                itens.append((nome, link.group(1), iso(limpar(bloco))))
        return itens

    def concurso(self, pagina, url, nome):
        resumo = limpar(pagina[pagina.find("Resumo"):])
        inicio = re.search(r"In[ií]cio das inscri[çc][õo]es\s*([\d/]+)", resumo)
        fim = re.search(r"Fim das inscri[çc][õo]es\s*([\d/]+)", resumo)
        prova = re.search(r"Data do concurso\s*([\d/]+)", resumo)
        docs = []
        for m in re.finditer(r'<a href="([^"]+\.pdf)"[^>]*>.*?<div class="fw-semibold">(.*?)</div>', pagina, re.S):
            docs.append(Documento(limpar(m.group(2)), m.group(1)))
        return Concurso(self.slug, nome, nome, url, "Concurso Público", "PR", None, iso(inicio.group(1)) if inicio else None,
                        iso(fim.group(1)) if fim else None, iso(prova.group(1)) if prova else None, docs)

    def listar(self, cliente):
        for nome, url, _ in self.itens_da_lista(decodificar(cliente.baixar(self.base + "/novo/concursos", usar_cache=False))):
            yield self.concurso(decodificar(cliente.baixar(url)), url, nome)


# ---------- Instituto Unicampo ----------

class Unicampo:
    slug, nome, base = "unicampo", "Instituto Unicampo", "https://institutounicampo.com.br"

    def itens_da_lista(self, pagina):
        aba = pagina[pagina.find('id="tab-andamento"'):]
        aba = aba[:aba.find('id="tab-homologados"')] if 'id="tab-homologados"' in aba else aba
        itens = []
        for bloco in aba.split('<div class="concurso-card"')[1:]:
            link = re.search(r'<a href="(https://institutounicampo\.com\.br/concurso/[^"]+)"', bloco)
            titulo = limpar((re.search(r"<h3>(.*?)</h3>", bloco, re.S) or [None, ""])[1])
            campos = {limpar(k).rstrip(":"): limpar(v) for k, v in re.findall(r"<strong>(.*?)</strong>\s*<span[^>]*>(.*?)</span>", bloco, re.S)}
            if link:
                itens.append(Concurso(self.slug, titulo, titulo, link.group(1), "Concurso Público" if "Concurso P" in titulo else "Processo Seletivo",
                                      uf_do_nome(titulo), campos.get("Edital nº"), iso(campos.get("Início Inscrições")),
                                      iso(campos.get("Término Inscrições")), iso(campos.get("Data da Prova"))))
        return itens

    def completar(self, c, pagina):
        for m in re.finditer(r'<a href="(/concurso/[^"]+/edital-[^";]+)[^"]*"[^>]*>(.*?)</a>', pagina, re.S):
            c.documentos.append(Documento(limpar(m.group(2)).replace("PDF", "", 1).strip(), self.base + m.group(1)))   # sem o ;jsessionid: o link devolve o PDF
        return c

    def listar(self, cliente):
        for c in self.itens_da_lista(decodificar(cliente.baixar(self.base + "/", usar_cache=False))):
            yield self.completar(c, decodificar(cliente.baixar(c.pagina)))


# ---------- Instituto Consulplan ----------

class Consulplan:
    slug, nome, base = "consulplan", "Instituto Consulplan", "https://www.institutoconsulplan.org.br"

    def itens_da_lista(self, pagina):
        """Os cartões de "Inscrições abertas / Novos": órgão, tipo e o link "Mais Informações"."""
        itens = []
        inicio = pagina.find("Inscrições abertas")
        fim = pagina.find('<div class="title-s">', inicio + 20) if inicio >= 0 else -1   # a página segue com os concursos em andamento e os encerrados
        for bloco in pagina[max(inicio, 0):fim if fim > 0 else None].split('<div class="card custom-card')[1:]:
            orgao = limpar((re.search(r'card-title[^>]*>(.*?)</h5>', bloco, re.S) or [None, ""])[1])
            tipo = limpar((re.search(r'card-subtitle[^>]*>(.*?)</h6>', bloco, re.S) or [None, ""])[1])
            mais = re.search(r'href="(/[\w-]+)"\s*class="btn btn-primary', bloco)
            if orgao and mais:
                itens.append(Concurso(self.slug, orgao, orgao, self.base + mais.group(1), tipo, uf_do_nome(orgao.split(" - ")[0]) or uf_do_nome(orgao)))
        return itens

    def completar(self, c, pagina):
        for m in re.finditer(r'<a href="(https://cdnsite\.institutoconsulplan\.org\.br/[^"]+\.pdf)"[^>]*>\s*(.*?)</a>', pagina, re.S):
            titulo = limpar(m.group(2))
            if titulo and not titulo.startswith("http") and not DATA.fullmatch(titulo) and not any(d.url == m.group(1) for d in c.documentos):
                c.documentos.append(Documento(titulo, m.group(1)))
        # a data de cada documento vem logo depois do título: "Edital nº 1/2026 - Abertura 18/09/2026"
        texto = limpar(pagina)
        for d in c.documentos:
            achado = re.search(re.escape(d.titulo) + r"\s*(\d{2}/\d{2}/\d{4})", texto)
            d.data = iso(achado.group(1)) if achado else d.data
        return c

    def listar(self, cliente):
        for c in self.itens_da_lista(decodificar(cliente.baixar(self.base + "/Concursos", usar_cache=False))):
            yield self.completar(c, decodificar(cliente.baixar(c.pagina)))


LEITORES = [
    ProSeletaNova("fafipa", "Fundação FAFIPA", "https://www.fundacaofafipa.org.br"),
    Fau(),
    ProSeletaAntiga("quadrix", "Instituto Quadrix", "https://www.quadrix.org.br"),
    ProSeletaAntiga("omni", "Instituto Omni", "https://omniinstituto.org.br"),
    Unicampo(),
    Consulplan(),
]
# Domínios dos editais de cada banca (o validar aceita como link de edital).
DOMINIOS = {
    "fafipa": ("fundacaofafipa.org.br", "selecao.net.br"), "fau": ("concursosfau.com.br",), "quadrix": ("quadrix.org.br", "selecao.net.br"),
    "omni": ("omniinstituto.org.br", "selecao.net.br"), "unicampo": ("institutounicampo.com.br",),
    "consulplan": ("institutoconsulplan.org.br",),
}
TODOS_OS_DOMINIOS = tuple(sorted({d for ds in DOMINIOS.values() for d in ds}))


class Bancas(Fonte):
    """Um Ato por concurso aberto nas páginas das bancas, com o texto do PDF do edital."""
    nome = "BANCAS"

    def __init__(self, cliente, leitores=None):
        super().__init__(cliente)
        self.leitores = LEITORES if leitores is None else leitores
        self.avisos = []
        self.por_banca = {}   # slug -> quantos concursos abertos dentro da cobertura

    @property
    def aviso(self):
        return ("parcial: " + "; ".join(self.avisos)) if self.avisos else None

    def listar_atos(self, desde, ate):
        for leitor in self.leitores:
            lidos = 0
            try:
                for c in leitor.listar(self.cliente):
                    edital = c.edital
                    if not (edital and aberto(c, ate) and dentro_da_cobertura(c)):
                        continue
                    texto = self.cliente.texto_pdf(edital.url)
                    if not texto:
                        self.avisos.append(f"{leitor.slug}: PDF sem texto em {edital.url}")
                        continue
                    lidos += 1
                    numero = f" nº {c.numero}" if c.numero else ""
                    yield Ato(fonte=f"banca-{leitor.slug}", data=edital.data or ate.isoformat(),
                              titulo=f"Edital de abertura{numero} – {c.orgao}"[:300], orgao=c.orgao[:200], url=edital.url, texto=texto)
            except (urllib.error.URLError, OSError, ValueError) as erro:
                self.avisos.append(f"{leitor.slug}: {erro}")
            self.por_banca[leitor.slug] = lidos
            print(f"BANCA {leitor.slug}: {lidos} concurso(s) aberto(s) dentro da cobertura", flush=True)
