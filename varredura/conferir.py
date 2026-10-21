"""Conferência automática: cada campo crítico contra o texto do ato oficial, sem modelo de IA (custo zero).

Um valor só passa quando aparece no texto do ato no lugar certo:
  salario           o valor (5.543,88) com o nome do cargo logo antes, e nenhum outro cargo da ficha mais perto
                    (ou, no bloco do próprio cargo, logo depois de "remuneração:");
                    professor do magistério (tabela única de remuneração): o último valor da linha da titulação
                    exigida, dentro do bloco do regime do cargo (20 h, 40 h ou dedicação exclusiva); com graduação,
                    o vencimento da linha do regime; ou vencimento + retribuição, duas parcelas seguidas que somam o valor;
                    técnico-administrativo: o valor logo depois de "classe D" (ou "nível D"), a classe do cargo no ato;
                    carreira com um salário só ("Analista ... remuneração inicial: R$ 16.040,88"): vale para os cargos
                    que começam pela mesma palavra, se todos eles têm esse salário;
  inscricao.*       a data (30/09/2026, 30/09 ou 30 de setembro) logo depois de "inscri", com o início antes do fim;
                    tabela de inscrições por item: o período logo depois do número do item do cargo;
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
# Tabela de remuneração do magistério federal: regime (bloco) e titulação (linha).
REGIMES = {"20": r"\b20\s*(?:\(\s*vinte\s*\)\s*)?(?:horas|h)\b", "40": r"\b40\s*(?:\(\s*quarenta\s*\)\s*)?(?:horas|h)\b",
           "de": r"dedicacao exclusiva|\(de\)"}
TITULACOES = [("graduacao", r"graduac|graduad"), ("aperfeicoamento", r"aperfeicoamento"),
              ("especializacao", r"especializ|especialista"), ("mestrado", r"mestrad|mestre\b"), ("doutorado", r"doutor")]
QUALQUER_TITULACAO = re.compile("|".join(p for _, p in TITULACOES))
QUALQUER_REGIME = re.compile("|".join(REGIMES.values()))
REMUNERACAO = re.compile(r"remunerac|vencimento|retribuicao|subsidio|tabela")
# Rótulo logo antes do valor: "remuneração inicial: R$", "vencimento básico de R$", "subsídio: R$".
ROTULO_SALARIO = re.compile(r"(?:remunerac\w*|vencimento\w*|subsidio|salario)(?:\s+(?:inicial|mensal|basico|basica|de))*\s*:?\s*(?:r\$)?\s*$")
# Linha de dedicação exclusiva em tabela de magistério: "DE A1 6.397,19" ou "DE D I 6.397,19".
LINHA_DE = re.compile(r"\bde\s+[a-d]\s?(?:1|i)\b")
CLASSE = re.compile(r"\b(?:classe|nivel)(?:\s+de\s+classificacao)?\s+([a-e])\b")


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
        # A soma não aparece escrita no ato: só as parcelas.
        if _soma_vencimento_retribuicao(texto, k):
            return True, "vencimento + retribuição por titulação: duas parcelas seguidas do ato que somam o valor"
        return False, "valor não achado no ato"
    eu = cargos.index(k)
    for pos in achados:
        i, distancia = _cargo_mais_perto(texto, cargos, pos)
        if i == eu and distancia <= 300:
            return True, "valor achado logo depois do nome do cargo"
        if i == eu and distancia <= 2500 and ROTULO_SALARIO.search(texto[max(0, pos - 60):pos]):
            return True, "valor logo depois de \"remuneração\", no bloco do próprio cargo"
    if _tabela_do_magisterio(texto, k, achados):
        return True, "valor da linha da titulação do cargo, no bloco do regime dele, na tabela de remuneração"
    if _vencimento_da_graduacao(texto, k, achados):
        return True, "vencimento da linha do regime do cargo (titulação exigida: graduação), na tabela de remuneração"
    if _soma_vencimento_retribuicao(texto, k):
        return True, "vencimento + retribuição por titulação: duas parcelas seguidas do ato que somam o valor"
    if _tabela_por_classe(texto, k, achados):
        return True, "valor logo depois da classe do cargo (técnico-administrativo), e a classe aparece com o cargo no ato"
    if _carreira(texto, cargos, k, achados):
        return True, "salário da carreira, logo depois da primeira palavra do cargo; os cargos da carreira têm o mesmo valor"
    return False, "valor achado, mas não logo depois do nome deste cargo"


def _professor(k):
    return bool(re.search(r"magisterio|professor|\bebtt\b", normalizar(k["nome"])))


def _regime_antes(texto, pos, janela=1500):
    """O regime mais perto antes de `pos` (20, 40 ou de), contando a linha "DE A1" das tabelas, ou None."""
    antes = texto[max(0, pos - janela):pos]
    achados = [(m.end(), nome) for nome, p in REGIMES.items() for m in re.finditer(p, antes)]
    achados += [(m.end(), "de") for m in LINHA_DE.finditer(antes)]
    return max(achados)[1] if achados else None


def _vencimento_da_graduacao(texto, k, achados):
    """Professor que só exige graduação: o salário é o vencimento, o primeiro valor da linha do regime dele."""
    if not _professor(k) or _titulacao(k) != "graduacao" or not _regime(k):
        return False
    for pos in achados:
        antes = texto[max(0, pos - 1500):pos]
        if not re.search(r"vencimento", antes):
            continue
        marcas = [(m.end(), nome) for nome, p in REGIMES.items() for m in re.finditer(p, antes)]
        marcas += [(m.end(), "de") for m in LINHA_DE.finditer(antes)]
        if not marcas:
            continue
        fim, nome = max(marcas)
        meio = antes[fim:]
        if nome == _regime(k) and len(meio) <= 40 and not DINHEIRO.search(meio) and not QUALQUER_TITULACAO.search(meio):
            return True
    return False


DENOMINACAO = re.compile(r"\b(?:professor\s+)?(assistente|adjunto|associado|titular)\b[\s-]*(livre|[a-d])?\b")


def _denominacao(texto):
    """(denominação, letra) do professor na redação do ato ou da ficha: ('assistente', 'a'), ('titular', 'livre')."""
    achado = None
    for m in DENOMINACAO.finditer(texto):
        if m.group(0).startswith("professor") or m.group(2):   # "assistente" sozinho é outro cargo (assistente em administração)
            achado = (m.group(1), m.group(2) or "")
    return achado


def _soma_vencimento_retribuicao(texto, k):
    """Professor: o ato dá o vencimento e a retribuição por titulação, e a ficha tem a soma (regra 11).

    Passa quando duas parcelas seguidas (até 160 caracteres entre elas) somam o salário ao centavo, perto de uma
    palavra de remuneração, e as três coisas que mudam o valor são as do cargo:
      titulação  o ato cita a titulação (até 400 caracteres antes das parcelas, ou logo depois) e é a que o cargo exige;
      regime     o regime mais perto antes delas (20 h, 40 h ou dedicação exclusiva), quando o ato o traz ali;
      classe     a denominação do professor (Assistente A, Adjunto A, Titular-Livre...) mais perto antes das parcelas
                 é a que a ficha traz para o cargo. O vencimento muda com a classe: valor de outra classe (o caso dos
                 editais 58 e 59 da UFV, de 15/10/2026) não passa.
    Titulação em dúvida, ou ausente perto das parcelas, não passa."""
    titulacao = _titulacao(k)
    if not _professor(k) or not titulacao:
        return False
    alvo = round(k["salario"] * 100)
    valores = [(m.start(), m.end(), round(float(m.group(0).replace(".", "").replace(",", ".")) * 100))
               for m in DINHEIRO.finditer(texto)]
    classe_do_cargo = _denominacao(normalizar(k.get("requisitos") or ""))
    for (ini, fim, a), (ini2, fim2, b) in zip(valores, valores[1:]):
        if a + b != alvo or ini2 - fim > 160 or not REMUNERACAO.search(texto, max(0, ini - 3000), ini):
            continue
        regime = _regime_antes(texto, ini)
        antes = list(QUALQUER_TITULACAO.finditer(texto, max(0, ini - 400), ini))
        depois = QUALQUER_TITULACAO.search(texto, fim2, fim2 + 120)
        citada = antes[-1] if antes else depois
        titulo_ok = citada is not None and re.match(dict(TITULACOES)[titulacao], citada.group(0))
        classe_ok = classe_do_cargo is None or _denominacao(texto[max(0, ini - 1200):ini]) == classe_do_cargo
        if titulo_ok and classe_ok and (regime is None or _regime(k) is None or regime == _regime(k)):
            return True
    return False


def _classe_do_cargo(k):
    m = CLASSE.search(normalizar(k.get("requisitos") or ""))
    return m.group(1) if m else None


def _tabela_por_classe(texto, k, achados):
    """Técnico-administrativo: vencimento por classe ("classe D R$ 3.181,39"). A classe do cargo tem de aparecer
    com o nome dele no ato: logo depois do nome ("assistente de aluno C 40 h") ou no título do bloco antes dele."""
    classe = _classe_do_cargo(k)
    nome = _padrao_cargo(k["nome"])
    if not classe or not nome:
        return False
    confirmada = False
    for m in nome.finditer(texto):
        if re.match(rf"\s+{classe}\s+\d", texto[m.end():m.end() + 8]):
            confirmada = True
            break
        blocos = list(CLASSE.finditer(texto, max(0, m.start() - 400), m.start()))
        if blocos and blocos[-1].group(1) == classe:
            confirmada = True
            break
    if not confirmada:
        return False
    for pos in achados:
        antes = texto[max(0, pos - 40):pos]
        rotulos = list(CLASSE.finditer(antes))
        if rotulos and rotulos[-1].group(1) == classe and not DINHEIRO.search(antes[rotulos[-1].end():]) \
                and REMUNERACAO.search(texto, max(0, pos - 1500), pos):
            return True
    return False


def _carreira(texto, cargos, k, achados):
    """Um salário por carreira ("Analista ... remuneração inicial: R$ 16.040,88"): vale para o cargo se a primeira
    palavra do nome dele vem antes do valor, sem a primeira palavra de outra carreira no meio, e se todos os cargos
    que começam por essa palavra têm o mesmo salário."""
    def primeira(c):
        palavras = [p for p in re.findall(r"[a-z0-9]+", normalizar(c["nome"])) if p not in VAZIAS]
        return palavras[0] if palavras else None
    minha = primeira(k)
    if not minha or any(primeira(c) == minha and c["salario"] != k["salario"] for c in cargos):
        return False
    outras = {primeira(c) for c in cargos} - {minha, None}
    for pos in achados:
        if not ROTULO_SALARIO.search(texto[max(0, pos - 60):pos]):
            continue
        antes = texto[max(0, pos - 200):pos]
        minhas = [m.end() for m in re.finditer(rf"\b{re.escape(minha)}\b", antes)]
        if not minhas:
            continue
        depois = antes[minhas[-1]:]
        if not any(re.search(rf"\b{re.escape(o)}\b", depois) for o in outras):
            return True
    return False


def _regime(k):
    alvo = normalizar((k.get("requisitos") or "") + " " + k["nome"])
    if re.search(REGIMES["de"], alvo):
        return "de"
    return {20: "20", 40: "40"}.get(k.get("jornada_horas"))


def _titulacao(k):
    """A titulação que o cargo exige (a mínima), ou None quando o texto deixa dúvida ("graduação ou especialização")."""
    alvo = normalizar(k.get("requisitos") or "")
    minima = re.search(r"titulacao minima\W+(\w+)", alvo)
    if minima:
        return next((nome for nome, p in TITULACOES if re.match(p, minima.group(1))), None)
    if re.search(rf"(?:{QUALQUER_TITULACAO.pattern})\w*[^;.]{{0,40}}\bou\b[^;.]{{0,10}}(?:{QUALQUER_TITULACAO.pattern})", alvo):
        return None
    achadas = [nome for nome, p in TITULACOES if re.search(p, alvo)]
    if not achadas and re.search(r"licenciatura|licenciad|bacharel", alvo):
        return "graduacao"   # licenciatura e bacharelado são graduação
    return achadas[-1] if achadas else None   # a mais alta citada: doutorado pressupõe a graduação


def _tabela_do_magisterio(texto, k, achados):
    """Professor do magistério: o salário vem de uma tabela única, por regime (bloco) e titulação (linha).

    Passa só quando, olhando para trás a partir do valor, o regime mais perto é o do cargo, a titulação mais perto
    (depois desse regime) é a exigida pelo cargo e o valor é o último da linha (o total, não o vencimento básico).
    """
    if not re.search(r"magisterio|professor", normalizar(k["nome"])):
        return False
    regime, titulacao = _regime(k), _titulacao(k)
    if not regime or not titulacao:
        return False
    padrao_titulacao = dict(TITULACOES)[titulacao]
    for pos in achados:
        antes = texto[max(0, pos - 1500):pos]
        regimes = [(m.end(), nome) for nome, p in REGIMES.items() for m in re.finditer(p, antes)]
        titulos = list(QUALQUER_TITULACAO.finditer(antes))
        if not regimes or not titulos or not REMUNERACAO.search(texto, max(0, pos - 3000), pos):
            continue
        fim_regime, nome_regime = max(regimes)
        ultimo = titulos[-1]
        if nome_regime != regime or ultimo.start() < fim_regime or not re.match(padrao_titulacao, ultimo.group(0)):
            continue
        # Último valor da linha: nenhum outro valor logo depois (até 60 caracteres), antes da próxima titulação ou regime.
        valor = DINHEIRO.search(texto, pos)
        seguintes = [m.start() for m in (QUALQUER_TITULACAO.search(texto, valor.end()), QUALQUER_REGIME.search(texto, valor.end())) if m]
        if not DINHEIRO.search(texto, valor.end(), min(seguintes + [valor.end() + 60])):
            return True
    return False


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


def _itens(c):
    """Números de item que a ficha cita nos cargos ("Item 1.4", "itens 1.4 e 1.5")."""
    itens = set()
    for k in c["cargos"]:
        for m in re.finditer(r"\bite(?:m|ns)\s+((?:\d+(?:\.\d+)+[\s,e]*)+)", normalizar(k.get("requisitos") or "")):
            itens |= set(re.findall(r"\d+(?:\.\d+)+", m.group(1)))
    return itens


def _item_antes(texto, pos):
    """Número de item ("1.4") logo antes da posição, sem outro número no meio, ou None."""
    achado = re.search(r"(\d+(?:\.\d+)+)[^\d]{0,45}$", texto[max(0, pos - 60):pos])
    return achado.group(1) if achado else None


def _de_outro_item(texto, c, inicio):
    """A data de início só aparece logo depois de números de item que não são os do cargo."""
    itens = _itens(c)
    antes = [_item_antes(texto, a.start()) for a in padrao_data(inicio).finditer(texto)]
    return any(i and i not in itens for i in antes) and not any(i in itens for i in antes if i)


def _periodo_do_item(texto, c, inicio, fim):
    """Tabela de inscrições por item (um período por item do edital): o período "início a fim" vem logo depois
    do número de um item do cargo, sem outro número no meio, e há "inscrição" antes da tabela."""
    itens = _itens(c)
    if not itens:
        return False
    for a in padrao_data(inicio).finditer(texto):
        if _item_antes(texto, a.start()) not in itens or not re.search(INSCRICAO, texto[max(0, a.start() - 3000):a.start()]):
            continue
        for b in padrao_data(fim).finditer(texto, a.end(), a.end() + 80):
            meio = texto[a.end():b.start()]
            if re.search(r"\b(a|ate|e|as|ao)\b", meio) and not QUALQUER_DATA.search(meio):
                return True
    return False


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
    if campo == "salario_titulacao":
        achados = [m.start() for m in padrao_valor(cargo["salario"]).finditer(texto)]
        if not achados:
            return False, "valor não achado no ato"
        if _tabela_do_magisterio(texto, cargo, achados):
            return True, "valor da linha desta titulação, no bloco do regime, na tabela de remuneração"
        return False, "valor achado, mas não na linha desta titulação e regime da tabela"
    if campo in ("inscricao.inicio", "inscricao.fim"):
        if campo == "inscricao.inicio":
            passou, motivo = _datas(texto, INSCRICAO, insc["inicio"], insc["fim"], antes=True, conhecidas=datas)
        else:
            passou, motivo = _datas(texto, INSCRICAO, insc["fim"], insc["inicio"], antes=False, conhecidas=datas)
        if insc["inicio"] and insc["fim"] and _itens(c):
            # Tabela com um período por item: vale só o período do item do cargo, não o primeiro da tabela.
            if _periodo_do_item(texto, c, insc["inicio"], insc["fim"]):
                return True, "período logo depois do número do item do cargo, na tabela de inscrições"
            if passou and _de_outro_item(texto, c, insc["inicio"]):
                return False, "o período é de outro item da tabela de inscrições"
        return passou, motivo
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
