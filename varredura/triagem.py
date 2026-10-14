"""Triagem: filtra os atos por palavra-chave e classifica cada um.

Classes: abertura | retificacao | autorizacao | contratacao_banca | resultado | outro.
Processo seletivo simplificado (PSS) ganha a marca pss=True e não é publicado (em avaliação).
Só abertura, retificação, autorização e contratação de banca vão para a fila de extração.
"""
import re

PARA_EXTRAIR = ("abertura", "retificacao", "autorizacao", "contratacao_banca")

_I = re.I
RELEVANTE = re.compile(r"concurso\s+p[uú]blico|processo\s+seletivo", _I)
PSS = re.compile(r"processo\s+seletivo\s+simplificado|\bPSS\b|contrata[çc][ãa]o\s+tempor[áa]ria", _I)
RETIFICACAO = re.compile(r"retifica|errata", _I)
RESULTADO = re.compile(
    r"homologa|reclassifica|resultado|classifica[çc][ãa]o\s+final|edital\s+de\s+(convoca|classifica)|convoca[çc][ãa]o|convoca\b|"
    r"nomea[çc][ãa]o|nomear|gabarito|aprovad[oa]s|prorroga[çc][ãa]o\s+(do\s+prazo\s+)?de\s+validade|prorroga\s+(a\s+)?validade", _I)
CONTRATACAO_BANCA = re.compile(
    r"(extrato\s+(de|do)\s+contrato|dispensa\s+de\s+licita[çc][ãa]o|inexigibilidade|homologa[çc][ãa]o\s+(de|da)\s+licita[çc][ãa]o|"
    r"contrata[çc][ãa]o\s+de\s+(empresa|institui[çc][ãa]o|banca))"
    r".{0,400}(organiza[çc][ãa]o|realiza[çc][ãa]o|execu[çc][ãa]o).{0,80}concurso", _I | re.S)
AUTORIZACAO = re.compile(
    r"autoriza(r|da|do|[çc][ãa]o)?\s+(a\s+)?(realiza[çc][ãa]o|abertura)\s+de\s+concurso|fica\s+autorizad[ao].{0,200}concurso\s+p[uú]blico", _I | re.S)
ABERTURA = re.compile(
    r"edital\s+(de\s+)?abertura|abertura\s+(de|das)\s+inscri[çc][õo]es|torna\s+p[uú]blic[ao].{0,120}(abertura|realiza[çc][ãa]o\s+(de|do)\s+concurso)|"
    r"inscri[çc][õo]es\s+(estar[ãa]o\s+)?abertas|per[íi]odo\s+de\s+inscri[çc][ãa]o", _I | re.S)


def classificar(ato):
    """(classe, pss) ou None quando o ato não fala de concurso nem de processo seletivo.

    O título decide primeiro; depois o começo do texto, com abertura antes de resultado:
    perder uma abertura custa mais que mandar um resultado à extração, que o descarta.
    """
    texto = ato.texto if hasattr(ato, "texto") else ato["texto"]
    titulo = ato.titulo if hasattr(ato, "titulo") else ato["titulo"]
    if not RELEVANTE.search(texto):
        return None
    inicio = titulo + "\n" + texto[:1500]
    pss = bool(PSS.search(inicio))
    regras = (
        ("contratacao_banca", CONTRATACAO_BANCA, inicio),  # antes do título: "homologação de licitação" não é resultado
        ("retificacao", RETIFICACAO, titulo),
        ("resultado", RESULTADO, titulo),
        ("abertura", ABERTURA, titulo),
        ("retificacao", RETIFICACAO, texto[:300]),
        ("autorizacao", AUTORIZACAO, inicio),
        ("abertura", ABERTURA, inicio),
        ("resultado", RESULTADO, inicio),
    )
    for classe, padrao, alvo in regras:
        if padrao.search(alvo):
            return classe, pss
    return "outro", pss
