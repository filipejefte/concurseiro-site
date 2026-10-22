"""Triagem: filtra os atos por palavra-chave e classifica cada um.

Classes: abertura | retificacao | autorizacao | contratacao_banca | resultado | fora | outro.
Processo seletivo simplificado (PSS) ganha a marca pss=True e não é publicado (em avaliação).
"fora" = órgão fora da cobertura (prefeitura ou estado de outra UF publicando no DOU).
Só abertura, retificação, autorização e contratação de banca vão para a fila de extração.
"""
import re

PARA_EXTRAIR = ("abertura", "retificacao", "autorizacao", "contratacao_banca")

_I = re.I
RELEVANTE = re.compile(r"concurso\s+p[uú]blico|processo\s+seletivo", _I)
CONCURSO = re.compile(r"concurso\s+p[uú]blico", _I)
PSS = re.compile(r"processo\s+seletivo\s+simplificado|\bPSS\b|contrata[çc][ãa]o\s+tempor[áa]ria", _I)
# No DOU, prefeituras e estados aparecem como "Prefeituras/Estado de X/..." e "Estados/...".
FORA_DA_COBERTURA = re.compile(r"^(Prefeituras|Estados?|Governo\s+do\s+Estado)\b(?!.*Paran[áa])", _I)
# "Apostila" é como a UEPG (no DIOE-PR) corrige edital; "apostilamento" de contrato não é retificação.
# Ampliação de vagas muda o concurso como uma retificação (se as inscrições já fecharam, vira descarte).
RETIFICACAO = re.compile(r"retifica|errata|\bapostila\b|\bcorrige\b|amplia[çc][ãa]o\s+(d[eo]\s+n[uú]mero\s+)?de\s+vagas?", _I)
RESULTADO = re.compile(
    r"homologa|reclassifica|resultado|classifica[çc][ãa]o|chamamento|convoca|nomea|nomear|posse|exonera|gabarito|"
    r"aprovad[oa]s|deferi|indeferi|desist|prorroga[çc][ãa]o\s+(do\s+prazo\s+)?de\s+validade|prorroga\s+(a\s+)?validade", _I)
# Título de ato que não abre concurso (a abertura sai em edital). Autorização e contratação são vistas antes.
NAO_ABRE = re.compile(r"^\s*(portaria|extrato|ata\b|termo|resolu|despacho|aviso\s+de\s+licita|contrato)", _I)
CONTRATACAO_BANCA = re.compile(
    r"(extrato\s+(de|do)\s+contrato|dispensa\s+de\s+licita[çc][ãa]o|inexigibilidade|homologa[çc][ãa]o\s+(de|da)\s+licita[çc][ãa]o|"
    r"contrata[çc][ãa]o\s+de\s+(empresa|institui[çc][ãa]o|banca))"
    r".{0,400}(organiza[çc][ãa]o|realiza[çc][ãa]o|execu[çc][ãa]o).{0,80}concurso", _I | re.S)
AUTORIZACAO = re.compile(
    r"autoriza(r|da|do|[çc][ãa]o)?\s+(a\s+)?(realiza[çc][ãa]o|abertura)\s+de\s+concurso|fica\s+autorizad[ao].{0,200}concurso\s+p[uú]blico", _I | re.S)
# No título, só quando o título É o edital de abertura (não quando cita "Edital de Abertura nº X").
# Aceita uma palavra antes, com travessão: "Publicação - Edital de Abertura..." (UNICENTRO, no DIOE-PR).
ABERTURA_TITULO = re.compile(r"^\s*(\w+\s*[-–:]\s*)?(edital\s+(de\s+)?abertura|abertura\s+de\s+(inscri|concurso))", _I)
# No texto, só frases de quem abre inscrição; citar o edital de abertura não basta.
ABERTURA_TEXTO = re.compile(
    r"abertura\s+(de|das)\s+inscri[çc][õo]es|torna(-se)?\s+p[uú]blic[ao].{0,160}(abertura|realiza[çc][ãa]o)\s+d[eo]s?\s+"
    r"(inscri|concurso|processo)|inscri[çc][õo]es\s+estar[ãa]o\s+abertas|reabertura\s+(do\s+per[íi]odo\s+)?d[ea]s?\s+inscri|"
    r"(faz\s+saber|torna\s+p[uú]blic[ao])\s+que\s+(realizar[áa]|estar[ãa]o\s+abertas)|realizar-se-[áa]\s+concurso|"
    r"provimento\s+de\s+cargos?\s+(de|da\s+carreira\s+de)\s+professor", _I | re.S)


def classificar(ato):
    """(classe, pss) ou None quando o ato não fala de concurso nem de processo seletivo."""
    texto = ato.texto if hasattr(ato, "texto") else ato["texto"]
    titulo = ato.titulo if hasattr(ato, "titulo") else ato["titulo"]
    orgao = (ato.orgao if hasattr(ato, "orgao") else ato.get("orgao")) or ""
    if not RELEVANTE.search(texto):
        return None
    inicio = titulo + "\n" + texto[:1500]
    pss = bool(PSS.search(inicio))
    if not pss and not CONCURSO.search(texto):
        return "outro", False  # processo seletivo que não é concurso: pós-graduação, residência, bolsa
    if FORA_DA_COBERTURA.search(orgao):
        return "fora", pss
    regras = (
        ("contratacao_banca", CONTRATACAO_BANCA, inicio),  # antes do título: "homologação de licitação" não é resultado
        ("autorizacao", AUTORIZACAO, inicio),              # autorização sai em portaria, decreto ou lei
        ("retificacao", RETIFICACAO, titulo),
        ("resultado", RESULTADO, titulo),
        ("outro", NAO_ABRE, titulo),
        ("abertura", ABERTURA_TITULO, titulo),
        ("retificacao", RETIFICACAO, texto[:300]),
        ("abertura", ABERTURA_TEXTO, inicio),
        ("resultado", RESULTADO, inicio),
    )
    for classe, padrao, alvo in regras:
        if padrao.search(alvo):
            return classe, pss
    return "outro", pss
