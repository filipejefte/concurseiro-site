"""Diário Oficial do Estado do Paraná (DIOE-PR), https://www.dioe.pr.gov.br/ (plataforma IONEWS).

Verificação de 19/10/2026 (prompt 02 do lançamento):
  - acesso: o portal é público e gratuito, sem cadastro para ler as edições; o /robots.txt não existe (o
    servidor devolve a página inicial, sem regras) e o portal não publica termos de uso. Ato oficial não
    tem proteção de direito autoral (Lei 9.610/1998, art. 8º, IV). Lemos com o mesmo cliente educado das
    outras fontes: 1 requisição por segundo, User-Agent com contato e cache em .cache/;
  - cadernos por dia útil: "Diário Oficial Executivo" (tipo 3, ~300 páginas, ~400 matérias), "Suplemento de
    Concursos Públicos" (tipo 8, ~12 matérias), "Diário Oficial da Assembleia" (tipo 10) e "Com. Ind. e
    Serviços" (tipo 2, publicações de empresas, fora da varredura);
  - a lista de todas as edições sai num JSON (id, data, tipo); o sumário de cada edição é uma árvore HTML
    (órgão > tipo de ato > matéria, com o id da matéria) e cada matéria tem página própria, só com o texto
    do ato, que vira o link do ato. A página é HTML (exportado do Word) ou o próprio PDF que o órgão mandou;
    PDF escaneado não tem texto e fica de fora (o log conta). Algumas matérias respondem 400 ("não está
    vinculada a uma edição"): são puladas e contadas.

O que lemos: o Suplemento de Concursos inteiro; do Executivo e da Assembleia, só as matérias cujo título ou
pasta falam de concurso, edital, seleção, banca ou autorização, mais os decretos autônomos e os despachos do
governador (onde sai a autorização de concurso). Assim a semana custa umas 150 requisições, não 2.000.
Limite conhecido: extrato de contrato de banca com título genérico ("Extrato de Contrato 12/2026") não é lido.
"""
import json
import re
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from io import BytesIO

from .base import Ato, Fonte

URL = "https://www.dioe.pr.gov.br"
URL_EDICOES = URL + "/apifront/portal/edicoes/ultimas_edicoes.json?sem_limite=1&todos=1"
URL_SUMARIO = URL + "/portal/visualizacoes/view_html_diario/{}"
URL_MATERIA = URL + "/apifront/portal/edicoes/publicacoes_ver_conteudo/{}/{}"  # matéria, edição

EXECUTIVO, SUPLEMENTO_CONCURSOS, ASSEMBLEIA = 3, 8, 10
CADERNOS = {EXECUTIVO: "Executivo", SUPLEMENTO_CONCURSOS: "Suplemento de Concursos", ASSEMBLEIA: "Assembleia"}

CANDIDATA = re.compile(r"concurs|seletiv|\bpss\b|edital|banca|autoriz|\bvagas?\b|docente|provimento|inscri", re.I)
# Licenças e notificações ambientais (dezenas por dia) dizem "autorização" e "edital", mas nunca são concurso.
PASTAS_SEM_CONCURSO = re.compile(r"licen[çc]a|ambiental|outorga|notifica[çc][ãa]o", re.I)
PASTAS_DE_AUTORIZACAO = re.compile(r"^(decretos aut[ôo]nomos|despacho do governador)$", re.I)
# Pastas que não são órgão: a raiz do caderno e o tipo de ato ("Edital-EX", "Portaria - Meta4", "Decretos Pessoal").
PASTAS_GENERICAS = re.compile(r"^(poder executivo|atos do chefe do poder executivo)$", re.I)

_ITEM = re.compile(r'<span class="folder">([^<]*)</span>|<ul\b[^>]*>|</ul>|'
                   r'<a class="linkMateria" identificador="(\d+)"[^>]*>([^<]*)</a>')


@dataclass
class Materia:
    id: str
    pastas: tuple   # do caderno até o tipo de ato, ex.: ("Secretaria da Fazenda", "Edital-EX")
    titulo: str


def sumario(html):
    """Matérias do sumário de uma edição, com as pastas em que cada uma está."""
    pastas, pendente, materias = [], None, []
    for m in _ITEM.finditer(html):
        trecho = m.group(0)
        if m.group(1) is not None:
            pendente = unescape(m.group(1)).strip()
        elif trecho.startswith("<ul"):
            pastas.append(pendente or "")
            pendente = None
        elif trecho.startswith("</ul"):
            if pastas:
                pastas.pop()
        else:
            titulo = re.sub(r"^\s*#\S+\s*-\s*", "", unescape(m.group(3)))   # tira "#138677/2026 - "
            titulo = re.sub(r"\.docx?$", "", titulo.replace("_", " "), flags=re.I)
            materias.append(Materia(m.group(2), tuple(p for p in pastas if p), re.sub(r"\s+", " ", titulo).strip()))
    return materias


def orgao(pastas):
    """O órgão é o caminho sem a raiz do caderno e sem a última pasta (o tipo de ato)."""
    nomes = [p for p in pastas[:-1] if not PASTAS_GENERICAS.match(p)]
    return " / ".join(nomes) or "Governo do Estado do Paraná"


def candidata(materia):
    """Matéria do Executivo ou da Assembleia que vale ler por inteiro."""
    if any(PASTAS_SEM_CONCURSO.search(p) for p in materia.pastas):
        return False
    return bool(CANDIDATA.search(materia.titulo + " " + " ".join(materia.pastas))
                or any(PASTAS_DE_AUTORIZACAO.match(p) for p in materia.pastas))


class _Texto(HTMLParser):
    """Como o navegador: espaço e quebra dentro do parágrafo viram um espaço; cada parágrafo, uma linha;
    cada linha de tabela, uma linha, com as células separadas por " | "."""
    BLOCOS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "title"}
    IGNORAR = {"script", "style", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes, self._fora, self._celula = [], 0, 0

    def _quebra(self, tag):
        self.partes.append(" " if self._celula and tag not in ("tr", "table") else "\n")

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORAR:
            self._fora += 1
        elif tag in ("td", "th"):
            self._celula += 1
            self.partes.append(" | ")
        elif tag in self.BLOCOS:
            self._quebra(tag)

    def handle_endtag(self, tag):
        if tag in self.IGNORAR:
            self._fora = max(0, self._fora - 1)
        elif tag in ("td", "th"):
            self._celula = max(0, self._celula - 1)
        elif tag in self.BLOCOS:
            if tag in ("tr", "table"):
                self._celula = 0
            self._quebra(tag)

    def handle_data(self, data):
        if not self._fora:
            self.partes.append(re.sub(r"\s+", " ", data))


def texto_do_html(html):
    """Texto corrido da página de uma matéria (HTML exportado do Word), uma linha por parágrafo."""
    leitor = _Texto()
    leitor.feed(html)
    linhas = (re.sub(r" {2,}", " ", l).strip(" |") for l in "".join(leitor.partes).split("\n"))
    return "\n".join(l for l in linhas if l)


def texto_da_materia(corpo):
    """Texto de uma matéria: HTML ou PDF (o portal devolve o arquivo do jeito que o órgão publicou)."""
    if corpo.lstrip()[:5] == b"%PDF-":
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            return "\n".join((pagina.extract_text() or "") for pagina in PdfReader(BytesIO(corpo)).pages).strip()
        except (PyPdfError, ValueError):
            return ""
    return texto_do_html(corpo.decode("utf-8", "replace"))


class DiarioEstadoPR(Fonte):
    nome = "DIOE-PR"

    def _edicoes(self, desde, ate):
        resposta = json.loads(self.cliente.baixar(URL_EDICOES, usar_cache=False))
        edicoes = []
        for e in resposta.get("itens") or []:
            if e.get("tipo_edicao_id") not in CADERNOS:
                continue
            dia = datetime.strptime(e["data"], "%d/%m/%Y").date()
            if desde <= dia <= ate:
                edicoes.append((dia, e.get("tipo_edicao_posicao") or 0, e["id"], e["tipo_edicao_id"]))
        return sorted(edicoes)

    def listar_atos(self, desde, ate):
        for dia, _, edicao, tipo in self._edicoes(desde, ate):
            # O sumário e as matérias de uma edição já fechada não mudam: ficam no cache.
            materias = sumario(self.cliente.baixar(URL_SUMARIO.format(edicao)).decode("utf-8", "replace"))
            lidas = [m for m in materias if tipo == SUPLEMENTO_CONCURSOS or candidata(m)]
            sem_texto = sem_edicao = 0
            for m in lidas:
                url = URL_MATERIA.format(m.id, edicao)
                try:
                    texto = texto_da_materia(self.cliente.baixar(url))
                except urllib.error.HTTPError as erro:
                    if erro.code not in (400, 404):
                        raise
                    sem_edicao += 1
                    continue
                if not texto:
                    sem_texto += 1
                yield Ato(fonte=self.nome, data=dia.isoformat(), titulo=m.titulo[:300], orgao=orgao(m.pastas)[:200],
                          url=url, texto=texto)
            avisos = "".join(f"; {n} {o}" for n, o in ((sem_texto, "sem texto (PDF escaneado)"),
                                                        (sem_edicao, "fora do ar (HTTP 400/404)")) if n)
            print(f"DIOE-PR {dia} {CADERNOS[tipo]}: {len(materias)} matérias, {len(lidas)} lidas{avisos}", flush=True)
