"""Diário Oficial dos Municípios do Paraná (AMP), https://www.diariomunicipal.com.br/amp/.

Uma edição por dia útil, num PDF de centenas de páginas. O formulário de calendário do site
devolve, em JSON, o arquivo da edição de cada data. Cada matéria do PDF termina em
"Código Identificador:XXXXXXXX" e tem página própria em /amp/materia/<código>, que vira o link do ato.
O PDF e o texto extraído ficam em .cache/ (o texto de uma edição leva cerca de 1 min para sair).
"""
import json
import re
from datetime import timedelta

from ..dados import chave_nome, municipio_pelo_inicio
from .base import Ato, Fonte

URL = "https://www.diariomunicipal.com.br/amp/"
URL_CALENDARIO = URL + "materia/calendario"
URL_MATERIA = URL + "materia/{}"

FIM_DA_MATERIA = re.compile(r"C[óo]digo\s+Identificador:\s*([0-9A-Z]{6,})")
CABECALHO_DA_PAGINA = re.compile(
    r"^.*Di[áa]rio Oficial dos Munic[íi]pios do Paran[áa]\s*•.*$|^\s*www\.diariomunicipal\.com\.br/amp\s+\d+\s*$", re.M)
PUBLICADO_POR = re.compile(r"Publicado por:\s*\n[^\n]*\s*$")
TIPOS_DE_TITULO = re.compile(r"^(EDITAL|AVISO|EXTRATO|PORTARIA|DECRETO|LEI |RESOLU|TERMO|HOMOLOGA|RETIFICA|ERRATA|ATO |CONCURSO|PROCESSO SELETIVO)", re.I)


# A edição vem agrupada por município: a primeira matéria de cada um abre com "ESTADO DO PARANÁ / MUNICÍPIO DE X" (ou
# "PREFEITURA MUNICIPAL DE X", "CÂMARA MUNICIPAL DE X"); as seguintes, do mesmo município, vêm sem esse cabeçalho.
LINHA_DO_MUNICIPIO = re.compile(r"^(?:munic[ií]pio|prefeitura(?:\s+municipal)?|c[âa]mara(?:\s+municipal)?)\s+d[eoa]s?\s+(.+)$", re.I)
TIPO_DA_ENTIDADE = (("camara", re.compile(r"^c[âa]mara\b", re.I)), ("prefeitura", re.compile(r"^prefeitura\b", re.I)),
                    # consórcio, fundo e autarquia saem na conta do município que os publica, mas não são a prefeitura
                    ("outro", re.compile(r"^(?:cons[óo]rcio|consamu|associa[çc][ãa]o|instituto|fundo|autarquia|funda[çc][ãa]o|"
                                         r"previd[êe]ncia|saae|samae|servi[çc]o aut[ôo]nomo)\b", re.I)))


def _tipo(linhas):
    """"camara", "prefeitura" ou "outro" (consórcio, fundo, autarquia) pela primeira linha que começa assim; None se nenhuma."""
    return next((tipo for linha in linhas for tipo, padrao in TIPO_DA_ENTIDADE if padrao.search(linha)), None)


def entidade_do_bloco(linhas):
    """((município, ibge), tipo) de uma matéria que abre com "ESTADO DO PARANÁ"; None se o bloco não tem esse cabeçalho.

    município: o nome da tabela do IBGE (o PDF quebra o nome em linhas e até em palavras: "CAPITÃO LEÔNIDAS" /
    "MARQUES", "CHOPINZ INHO"), ou "" quando a entidade não é município (consórcio, associação).
    tipo: "prefeitura", "camara" ou None quando o cabeçalho não diz."""
    if not linhas or chave_nome(linhas[0]) != "estado do parana":
        return None
    resto = linhas[1:5]
    achado = LINHA_DO_MUNICIPIO.match(resto[0]) if resto else None
    if not achado:
        return ("", ""), _tipo(resto[:1])
    m = municipio_pelo_inicio(achado.group(1) + " " + " ".join(resto[1:3]))
    return (m["nome"], m["ibge"]) if m else (achado.group(1).strip(), ""), _tipo(resto)


def materias(texto, data_edicao, fonte="AMP-PR"):
    """Separa o texto de uma edição em atos, um por "Código Identificador".

    Cada ato leva o município (nome e código IBGE) e o tipo da entidade (prefeitura ou câmara) que publicou. O município
    vem do último cabeçalho "ESTADO DO PARANÁ / MUNICÍPIO DE X" antes da matéria; o tipo, do cabeçalho ou do início
    da matéria, e fica vazio quando o diário não diz."""
    texto = CABECALHO_DA_PAGINA.sub("", texto)
    atos, inicio = [], 0
    municipio = ("", "")
    for fim in FIM_DA_MATERIA.finditer(texto):
        bloco = PUBLICADO_POR.sub("", texto[inicio:fim.start()].strip()).strip()
        inicio = fim.end()
        todas = [l.strip() for l in bloco.splitlines() if l.strip()]
        cabecalho = entidade_do_bloco(todas)
        if cabecalho is not None:
            municipio, tipo = cabecalho
        else:
            tipo = _tipo(todas[:1])
        linhas = [l.strip() for l in bloco.splitlines() if l.strip() and l.strip().upper() != "ESTADO DO PARANÁ"]
        if not linhas:
            continue
        orgao = linhas[0]
        if re.search(r"\b(DE|DO|DA|DOS|DAS|E)$", orgao) and len(linhas) > 1:  # nome quebrado em duas linhas
            orgao += " " + linhas[1]
        titulo = next((l for l in linhas[1:12] if TIPOS_DE_TITULO.match(l)), linhas[1] if len(linhas) > 1 else orgao)
        atos.append(Ato(fonte=fonte, data=data_edicao, titulo=titulo[:300], orgao=orgao[:200],
                        url=URL_MATERIA.format(fim.group(1)), texto=bloco, municipio=municipio[0], municipio_ibge=municipio[1],
                        entidade=tipo or ""))
    return atos


class DiarioMunicipiosPR(Fonte):
    nome = "AMP-PR"

    def __init__(self, cliente):
        super().__init__(cliente)
        # {ibge: {"materias": n, "ultima": "AAAA-MM-DD"}}: quem publicou algo na AMP no período, concurso ou não
        # (o diário de um município que nunca aparece aqui não está sendo lido).
        self.publicacoes = {}

    def _token(self):
        pagina = self.cliente.baixar(URL, usar_cache=False).decode("utf-8", "replace")
        achado = re.search(r'name="calendar\[_token\]"[^>]*value="([^"]+)"', pagina)
        if not achado:
            raise SystemExit("O formato da página da AMP mudou: não achei o formulário de calendário.")
        return achado.group(1)

    def _edicoes(self, dia, token):
        corpo = self.cliente.baixar(URL_CALENDARIO, usar_cache=False, dados={
            "calendar[day]": dia.day, "calendar[month]": dia.month, "calendar[year]": dia.year, "calendar[_token]": token})
        resposta = json.loads(corpo)
        return [(e["url_arquivo"] + e["link_diario"] + ".pdf", e["data_circulacao"])
                for e in resposta.get("edicao") or [] if e.get("data_circulacao") == dia.isoformat()]

    def _texto_do_pdf(self, url):
        arquivo_txt = self.cliente.arquivo_cache(url, extensao=".txt")
        if arquivo_txt.exists():
            return arquivo_txt.read_text(encoding="utf-8")
        from pypdf import PdfReader  # só quem lê a AMP precisa do pypdf
        from pypdf.errors import PdfReadError
        pdf = self.cliente.arquivo_cache(url, extensao=".pdf")
        self.cliente.baixar(url, extensao=".pdf")
        try:
            texto = "\n".join((pagina.extract_text() or "") for pagina in PdfReader(pdf).pages)
        except PdfReadError:
            # PDF cortado no cache (download interrompido): baixa de novo uma vez.
            pdf.unlink(missing_ok=True)
            self.cliente.baixar(url, extensao=".pdf")
            texto = "\n".join((pagina.extract_text() or "") for pagina in PdfReader(pdf).pages)
        arquivo_txt.write_text(texto, encoding="utf-8")
        return texto

    def listar_atos(self, desde, ate):
        token = self._token()
        dia = desde
        while dia <= ate:
            if dia.weekday() < 5:  # a AMP circula em dias úteis
                for url, data_edicao in self._edicoes(dia, token):
                    atos = materias(self._texto_do_pdf(url), data_edicao)
                    for ato in atos:
                        if ato.municipio_ibge:
                            m = self.publicacoes.setdefault(ato.municipio_ibge, {"materias": 0, "ultima": data_edicao})
                            m["materias"] += 1
                            m["ultima"] = max(m["ultima"], data_edicao)
                    print(f"AMP-PR {data_edicao}: {len(atos)} matérias", flush=True)
                    yield from atos
            dia += timedelta(days=1)
