"""Conferência automática: cada campo crítico contra o texto do ato oficial, sem modelo de IA (custo zero).

Um valor só passa quando aparece no texto do ato no lugar certo:
  salario           o valor (5.543,88) com o nome do cargo logo antes, e nenhum outro cargo da ficha mais perto;
  inscricao.*       a data (30/09/2026, 30/09 ou 30 de setembro) logo depois de "inscri", com o início antes do fim;
  prova_objetiva    a data logo depois de "objetiva" (ou "prova escrita", "aplicação da prova");
  taxa              o valor logo depois de "taxa";
  banca, cidade     o nome no texto;
  edital            o link é o do próprio ato.
"Não informado" passa quando o texto não tem o dado perto da palavra-chave (sem data perto de "inscri", etc.).
O que não passa fica para a pessoa, com o motivo. Uma amostra fixa do que passou (1 em AMOSTRA) também
vai para a pessoa, para pegar erro do próprio verificador.
"""
import hashlib
import re
import unicodedata
from pathlib import Path

from .dados import data, edital
from .extracao import ler_fila

AMOSTRA = 20   # 1 em cada 20 linhas que passaram vai para a pessoa (5%)
MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
DINHEIRO = re.compile(r"(?<![\d.,])\d{1,3}(?:\.?\d{3})*,\d{2}(?!\d)")
VAZIAS = {"de", "da", "do", "das", "dos", "e", "em", "a", "o", "para", "com", "na", "no"}
# "inscricao", não "inscri": "inscrita no CNPJ" traria a data do contrato.
INSCRICAO = r"inscricao|inscricoes"
# Só a objetiva: "prova" sozinha casaria com a data da prova prática ou de títulos.
PROVA = r"objetiva|\bprovas? escritas?|aplicacao d[ao]s? provas?"
OUTRO_EVENTO = re.compile(r"gabarito|resultado|recurso|divulga|homologa|\bnotas?\b|classifica")


def normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", texto.replace("º", "").replace("ª", ""))


def texto_dos_atos(pasta, ficha):
    """Texto normalizado do ato da ficha e das retificações incorporadas, e os links deles."""
    partes, links = [], set()
    for nome in [ficha.get("ato")] + list(ficha.get("atos_extras") or []):
        arquivo = Path(pasta) / "fila" / str(nome)
        if nome and arquivo.exists():
            meta, texto = ler_fila(arquivo)
            partes.append(meta.get("titulo", "") + "\n" + texto)
            links.add(meta.get("url"))
    return normalizar("\n".join(partes)), links


def padrao_valor(v):
    inteiro, centavos = f"{v:.2f}".split(".")
    milhar = r"\.?".join([inteiro[:len(inteiro) % 3 or 3]] + [inteiro[i:i + 3] for i in range(len(inteiro) % 3 or 3, len(inteiro), 3)])
    return re.compile(rf"(?<![\d.,]){milhar},{centavos}(?!\d)")


def padrao_data(iso):
    d = data(iso)
    ano = rf"(?:{d.year}|{d.year % 100:02d})"
    # Com ponto ou hífen, só com o ano: "16.11" sozinho é número de item do edital, não data.
    numerica = (rf"(?<!\d)0?{d.day}\s*/\s*0?{d.month}(?:\s*/\s*{ano}(?!\d)|(?!\s*/?\s*\d))"
                rf"|(?<![\d.])0?{d.day}[.-]0?{d.month}[.-]{d.year}(?!\d)")
    extenso = rf"(?<!\d)0?{d.day}\s*(?:o\s+)?de\s+{MESES[d.month - 1]}(?:\s+de\s+{d.year}|(?!\s+de\s+\d))"
    return re.compile(rf"{numerica}|{extenso}")


QUALQUER_DATA = re.compile(r"(?<!\d)\d{1,2}\s*/\s*\d{1,2}(?:\s*/\s*\d{2,4})?(?!\d)|(?<![\d.])\d{1,2}[.-]\d{1,2}[.-]\d{4}(?!\d)"
                           r"|(?<!\d)\d{1,2}\s+de\s+(?:" + "|".join(MESES) + ")")


def _perto(texto, chave, alvo, janela):
    """Posições do alvo que caem até `janela` caracteres depois de uma ocorrência da chave."""
    chaves = [m.start() for m in re.finditer(chave, texto)]
    return [m.start() for m in alvo.finditer(texto) if any(0 <= m.start() - k <= janela for k in chaves)]


def _padrao_cargo(nome):
    palavras = [p for p in re.findall(r"[a-z0-9]+", normalizar(nome)) if p not in VAZIAS]
    return re.compile(r"\b" + r"\W+(?:\w+\W+){0,3}?".join(re.escape(p) for p in palavras)) if palavras else None


def _cargo_mais_perto(texto, cargos, pos):
    """Índice do cargo cujo nome termina mais perto antes de `pos` (empate: o nome mais longo), e a distância."""
    melhor = (None, None, 0)
    for i, k in enumerate(cargos):
        p = _padrao_cargo(k["nome"])
        fins = [m.end() for m in p.finditer(texto[:pos])] if p else []
        if fins:
            chave = (fins[-1], len(k["nome"]))
            if melhor[1] is None or chave > melhor[1]:
                melhor = (i, chave, pos - fins[-1])
    return melhor[0], melhor[2]


def _salario(texto, cargos, k):
    nome = _padrao_cargo(k["nome"])
    if k["salario"] is None:
        if not nome or not nome.search(texto):
            return False, "cargo não achado no ato"
        tem = any(DINHEIRO.search(texto[m.end():m.end() + 300]) for m in nome.finditer(texto))
        return (False, "há valor em reais perto do cargo") if tem else (True, "sem valor em reais perto do cargo")
    achados = [m.start() for m in padrao_valor(k["salario"]).finditer(texto)]
    if not achados:
        return False, "valor não achado no ato"
    eu = cargos.index(k)
    for pos in achados:
        i, distancia = _cargo_mais_perto(texto, cargos, pos)
        if i == eu and distancia <= 300:
            return True, "valor achado logo depois do nome do cargo"
    return False, "valor achado, mas não logo depois do nome deste cargo"


def _datas(texto, chave, iso, outra=None, antes=True, conhecidas=()):
    if iso is None:
        # Datas que já são de outro campo da ficha (fim, prova, isenção) não contam como "falta esta".
        delas = {m.start() for d in conhecidas if d for m in padrao_data(d).finditer(texto)}
        tem = set(_perto(texto, chave, QUALQUER_DATA, 250)) - delas
        return (False, "há data perto da palavra-chave") if tem else (True, "sem data perto da palavra-chave")
    primeiras = _primeiras_datas(texto, chave)
    if not outra:
        if any(m.start() in primeiras for m in padrao_data(iso).finditer(texto)):
            return True, "é a primeira data depois da palavra-chave"
        return False, "não é a primeira data depois da palavra-chave"
    # Período: "inicio a fim" ou "inicio até fim", sem outra data no meio, logo depois da palavra-chave.
    inicio, fim = (iso, outra) if antes else (outra, iso)
    for a in padrao_data(inicio).finditer(texto):
        if a.start() not in primeiras:
            continue
        for b in padrao_data(fim).finditer(texto, a.end(), a.end() + 80):
            meio = texto[a.end():b.start()]
            if re.search(r"\b(a|ate|e|as|ao)\b", meio) and not QUALQUER_DATA.search(meio):
                return True, "período \"início a fim\" logo depois da palavra-chave"
    return False, "início e fim não aparecem como período (\"de X a Y\") logo depois da palavra-chave"


def _primeiras_datas(texto, chave, janela=250):
    """Posição da primeira data depois de cada ocorrência da palavra-chave (até `janela` caracteres)."""
    saida = set()
    for k in re.finditer(chave, texto):
        # "gabarito da prova objetiva 16/11", "inscrições deferidas 30/10": a data é de outro evento.
        if OUTRO_EVENTO.search(texto, max(0, k.start() - 60), k.start()) or re.match(r"\W*\w*\W*(in)?deferid", texto[k.end():k.end() + 25]):
            continue
        m = QUALQUER_DATA.search(texto, k.end(), k.end() + janela)
        if m:
            saida.add(m.start())
    return saida


def _taxa(texto, t):
    valores = {v for v in (t["min"], t["max"]) if v is not None}
    if not valores:
        tem = _perto(texto, r"\btaxa", DINHEIRO, 300)
        return (False, "há valor em reais perto de \"taxa\"") if tem else (True, "sem valor perto de \"taxa\"")
    faltam = [v for v in valores if not _perto(texto, r"\btaxa", padrao_valor(v), 3000)]
    return (False, "valor não achado depois de \"taxa\"") if faltam else (True, "valores achados depois de \"taxa\"")


def _nome(texto, nome):
    """O nome inteiro, a sigla entre parênteses ou o nome sem a sigla."""
    if not nome:
        return False
    sigla = re.search(r"\(([^)]+)\)", nome)
    opcoes = [nome, re.sub(r"\s*\([^)]*\)", "", nome)] + ([sigla.group(1)] if sigla else [])
    return any(re.search(r"\b" + re.escape(normalizar(o).strip()) + r"\b", texto) for o in opcoes if normalizar(o).strip())


def _vazio(campo, c, cargo):
    if campo == "salario":
        return cargo["salario"] is None
    if campo == "taxa":
        return c["taxa"]["min"] is None and c["taxa"]["max"] is None
    return {"inscricao.inicio": c["inscricao"]["inicio"], "inscricao.fim": c["inscricao"]["fim"],
            "prova_objetiva": c["prova_objetiva"]}.get(campo) is None


def verificar(campo, c, texto, links, cargo=None):
    """(passou, motivo) para uma linha da revisão."""
    if not texto:
        return False, "texto do ato não está na fila"
    insc = c["inscricao"]
    datas = (insc["inicio"], insc["fim"], c["prova_objetiva"], c["isencao_ate"])
    # Previsto não tem edital: o que é do edital fica "Não informado" por natureza. Valor preenchido segue a regra normal.
    if edital(c) is None and campo not in ("banca", "cidade", "edital") and _vazio(campo, c, cargo):
        return True, "previsto: sem edital, nada a achar"
    if campo == "salario":
        return _salario(texto, c["cargos"], cargo)
    if campo == "inscricao.inicio":
        return _datas(texto, INSCRICAO, insc["inicio"], insc["fim"], antes=True, conhecidas=datas)
    if campo == "inscricao.fim":
        return _datas(texto, INSCRICAO, insc["fim"], insc["inicio"], antes=False, conhecidas=datas)
    if campo == "prova_objetiva":
        return _datas(texto, PROVA, c["prova_objetiva"], conhecidas=datas)
    if campo == "taxa":
        return _taxa(texto, c["taxa"])
    if campo == "banca":
        if c["banca"]["nome"] is None:
            tem = re.search(r"contratad[ao]\s*:", texto)
            return (False, "o ato tem \"contratada:\"; a banca pode estar nele") if tem else (True, "o ato não cita banca contratada")
        return (True, "nome da banca achado no ato") if _nome(texto, c["banca"]["nome"]) else (False, "nome da banca não achado no ato")
    if campo == "cidade":
        if c["nacional"] or not c["cidade"]:
            return False, "concurso nacional ou sem cidade: confira à mão"
        return (True, "cidade achada no ato") if _nome(texto, c["cidade"]) else (False, "cidade não achada no ato")
    if campo == "edital":
        from .revisao import ato_principal
        url = (ato_principal(c) or {}).get("url")
        return (True, "é o link do próprio ato") if url in links else (False, "o link não é o do ato da fila")
    return False, "campo sem verificação automática"


def na_amostra(semana, id_, campo, valor):
    """Escolha fixa por linha: a mesma linha cai (ou não) na amostra a cada vez que a revisão roda."""
    return int(hashlib.sha1(f"{semana}|{id_}|{campo}|{valor}".encode()).hexdigest(), 16) % AMOSTRA == 0
