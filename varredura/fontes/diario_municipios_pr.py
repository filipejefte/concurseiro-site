"""Diário Oficial dos Municípios do Paraná (AMP), https://www.diariomunicipal.com.br/amp/.

Uma edição por dia útil, num PDF de centenas de páginas. O formulário de calendário do site
devolve, em JSON, o arquivo da edição de cada data. Cada matéria do PDF termina em
"Código Identificador:XXXXXXXX" e tem página própria em /amp/materia/<código>, que vira o link do ato.
O PDF e o texto extraído ficam em .cache/ (o texto de uma edição leva cerca de 1 min para sair).
"""
import json
import re
from datetime import timedelta

from .base import Ato, Fonte

URL = "https://www.diariomunicipal.com.br/amp/"
URL_CALENDARIO = URL + "materia/calendario"
URL_MATERIA = URL + "materia/{}"

FIM_DA_MATERIA = re.compile(r"C[óo]digo\s+Identificador:\s*([0-9A-Z]{6,})")
CABECALHO_DA_PAGINA = re.compile(
    r"^.*Di[áa]rio Oficial dos Munic[íi]pios do Paran[áa]\s*•.*$|^\s*www\.diariomunicipal\.com\.br/amp\s+\d+\s*$", re.M)
PUBLICADO_POR = re.compile(r"Publicado por:\s*\n[^\n]*\s*$")
TIPOS_DE_TITULO = re.compile(r"^(EDITAL|AVISO|EXTRATO|PORTARIA|DECRETO|LEI |RESOLU|TERMO|HOMOLOGA|RETIFICA|ERRATA|ATO |CONCURSO|PROCESSO SELETIVO)", re.I)


def materias(texto, data_edicao, fonte="AMP-PR"):
    """Separa o texto de uma edição em atos, um por "Código Identificador"."""
    texto = CABECALHO_DA_PAGINA.sub("", texto)
    atos, inicio = [], 0
    for fim in FIM_DA_MATERIA.finditer(texto):
        bloco = PUBLICADO_POR.sub("", texto[inicio:fim.start()].strip()).strip()
        inicio = fim.end()
        linhas = [l.strip() for l in bloco.splitlines() if l.strip() and l.strip().upper() != "ESTADO DO PARANÁ"]
        if not linhas:
            continue
        orgao = linhas[0]
        if re.search(r"\b(DE|DO|DA|DOS|DAS|E)$", orgao) and len(linhas) > 1:  # nome quebrado em duas linhas
            orgao += " " + linhas[1]
        titulo = next((l for l in linhas[1:12] if TIPOS_DE_TITULO.match(l)), linhas[1] if len(linhas) > 1 else orgao)
        atos.append(Ato(fonte=fonte, data=data_edicao, titulo=titulo[:300], orgao=orgao[:200],
                        url=URL_MATERIA.format(fim.group(1)), texto=bloco))
    return atos


class DiarioMunicipiosPR(Fonte):
    nome = "AMP-PR"

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
        pdf = self.cliente.arquivo_cache(url, extensao=".pdf")
        self.cliente.baixar(url, extensao=".pdf")
        texto = "\n".join((pagina.extract_text() or "") for pagina in PdfReader(pdf).pages)
        arquivo_txt.write_text(texto, encoding="utf-8")
        return texto

    def listar_atos(self, desde, ate):
        token = self._token()
        atos = []
        dia = desde
        while dia <= ate:
            if dia.weekday() < 5:  # a AMP circula em dias úteis
                for url, data_edicao in self._edicoes(dia, token):
                    atos.extend(materias(self._texto_do_pdf(url), data_edicao))
            dia += timedelta(days=1)
        return atos
