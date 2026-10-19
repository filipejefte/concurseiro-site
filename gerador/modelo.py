"""Do dado ao que a página mostra: situação na data do build, textos de exibição, slugs, ordem e agrupamentos.

Tudo aqui sai de dados/concursos.json (e dos exemplos fictícios, só com --exemplo). Nada é estimado:
o que a ficha não traz vira "Não informado no edital" na página.
"""
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from varredura import dados as d

NI = "Não informado no edital"
NIVEIS = ["Fundamental", "Médio", "Técnico", "Superior"]
FONTES = {
    "DOU": "Diário Oficial da União",
    "AMP-PR": "Diário Oficial dos Municípios do Paraná",
    "DIOE-PR": "Diário Oficial do Paraná",
    "banca": "Site da banca",
    "outra": "Fonte oficial",
}
SIGLA_UF = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}
RAIO_KM = 50
DIAS_NO_SITEMAP = 90   # encerrado sai do sitemap 90 dias depois do fim da inscrição
ATIVAS = ("aberto", "breve", "previsto")
ABERTAS = ("aberto", "breve")


def slug(texto):
    texto = unicodedata.normalize("NFD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")


def distancia(a, b):
    """Haversine, em km (a mesma conta do app.js)."""
    r = math.pi / 180
    dlat, dlon = (b["lat"] - a["lat"]) * r, (b["lon"] - a["lon"]) * r
    h = math.sin(dlat / 2) ** 2 + math.cos(a["lat"] * r) * math.cos(b["lat"] * r) * math.sin(dlon / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def plural(n, um, varios):
    return f"{n:,}".replace(",", ".") + " " + (um if n == 1 else varios)


def minuscula(t):
    return t[:1].lower() + t[1:] if t else t


def banca_slug(nome):
    """Uma página por banca, mesmo com o nome escrito de jeitos diferentes nos atos.

    "Fundação de Apoio ao Campus de Paranavaí (FAFIPA)" e "Fundação FAFIPA" -> "fafipa": vale a sigla
    entre parênteses; sem ela, a primeira sigla do nome (3 letras ou mais, em maiúsculas); sem sigla, o nome.
    """
    if not nome:
        return None
    entre = re.search(r"\(([A-ZÀ-Ü0-9-]{2,})\)\s*$", nome)
    if entre:
        return slug(entre.group(1))
    sigla = re.search(r"\b([A-ZÀ-Ü]{3,}[0-9-]*)\b", nome)
    return slug(sigla.group(1) if sigla else nome)


def orgao_curto(orgao):
    """Nome para título: "Câmara Municipal de X (PR)" -> "Câmara de X (PR)"; órgão federal com sigla -> a sigla."""
    o = re.sub(r"^(Câmara|Prefeitura) Municipal d([eoa]s?) ", r"\1 d\2 ", orgao)
    sigla = re.search(r"\(([A-ZÀ-Ü][A-ZÀ-Ü0-9-]{2,})\)\s*$", o)
    return sigla.group(1) if sigla else o


def ano(c):
    ed = d.edital(c)
    for texto in [(ed or {}).get("publicado_em"), c["inscricao"]["fim"], c["inscricao"]["inicio"], c["id"]]:
        achado = re.search(r"20\d\d", texto or "")
        if achado:
            return achado.group(0)
    return ""


def dinheiro(v):
    return d.brl(v)


def texto_vagas(cargos, curto=False):
    conhecidas = [k["vagas"] for k in cargos if k["vagas"] is not None]
    cr = any(k["cadastro_reserva"] for k in cargos)
    if not conhecidas:
        return "Cadastro reserva" if cr else "Vagas não informadas"
    n = sum(conhecidas)
    if n == 0:
        return "Cadastro reserva"
    return (f"{n:,}".replace(",", ".") if curto else plural(n, "vaga", "vagas")) + (" + CR" if cr else "")


def texto_vagas_cargo(k):
    if k["vagas"] is None:
        return "cadastro reserva" if k["cadastro_reserva"] else "vagas não informadas"
    if k["vagas"] == 0:
        return "cadastro reserva"
    return plural(k["vagas"], "vaga", "vagas") + (" + CR" if k["cadastro_reserva"] else "")


def texto_escolaridade(niveis):
    if not niveis:
        return ""
    if len(niveis) == 1:
        return niveis[0]
    return niveis[0] + (" e " if len(niveis) == 2 else " a ") + minuscula(niveis[-1])


def texto_jornada(cargos):
    h = [k["jornada_horas"] for k in cargos if k["jornada_horas"]]
    if not h:
        return None
    a, b = min(h), max(h)
    fmt = lambda x: f"{x:g}"
    return f"{fmt(a)} h semanais" if a == b else f"{fmt(a)} a {fmt(b)} h semanais, conforme o cargo"


def texto_taxa(t):
    if t["min"] is None and t["max"] is None:
        return None
    if t["min"] is None or t["max"] is None or t["min"] == t["max"]:
        return dinheiro(t["min"] if t["min"] is not None else t["max"])
    return f"{dinheiro(t['min'])} a {dinheiro(t['max'])}, conforme o cargo"


def ato_principal(c):
    return d.edital(c) or next((x for x in c["documentos"] if x["tipo"] in ("autorizacao", "contratacao_banca")), None)


@dataclass
class Concurso:
    """Um concurso pronto para as páginas. `c` é a ficha original."""
    c: dict
    hoje: date
    municipio: dict = None          # linha da tabela de municípios (com lat e lon), quando a cidade é do PR
    cidade_slug: str = None         # só quando a cidade tem página
    parecidos: list = field(default_factory=list)

    def __post_init__(self):
        c = self.c
        self.id = c["id"]
        self.situacao = d.situacao(c, self.hoje)
        self.aberto = self.situacao in ABERTAS
        self.ativo = self.situacao in ATIVAS
        cargos = sorted(c["cargos"], key=lambda k: -(k["salario"] or 0))
        self.cargos = cargos
        salarios = [k["salario"] for k in cargos if k["salario"] is not None]
        self.sal_max = max(salarios) if salarios else None
        self.sal_min = min(salarios) if salarios else None
        varios = self.sal_max is not None and self.sal_min != self.sal_max
        self.salario = None if self.sal_max is None else ("até " if varios else "") + dinheiro(self.sal_max)
        self.faixa_salario = (None if self.sal_max is None else dinheiro(self.sal_max) if not varios
                              else f"{dinheiro(self.sal_min)} a {dinheiro(self.sal_max)}")
        principal = cargos[0] if cargos else None
        outros = len(cargos) - 1
        self.cargo = (principal["nome"] + (f" e mais {plural(outros, 'cargo', 'cargos')}" if outros > 0 else "")) if principal \
            else "Cargos não informados"
        self.niveis = [n for n in NIVEIS if any(k["escolaridade"] == n for k in cargos)]
        self.escolaridade = texto_escolaridade(self.niveis)
        self.vagas = texto_vagas(cargos)
        self.vagas_curto = texto_vagas(cargos, curto=True)
        self.jornada_card = f"{principal['jornada_horas']:g} h" if principal and principal["jornada_horas"] else ""
        self.jornada = texto_jornada(cargos)
        b = c["beneficios"][0] if c["beneficios"] else None
        self.beneficio = "+ " + minuscula(b["nome"]) if b else ""
        self.banca = c["banca"]["nome"]
        self.banca_slug = banca_slug(self.banca)
        self.area = c["area"]
        self.area_slug = slug(c["area"])
        self.federal = c["esfera"] == "federal"
        self.nacional = c["nacional"]
        self.no_pr = c["uf"] == "PR" and not c["nacional"]
        self.uf = c["uf"]
        insc = c["inscricao"]
        self.inicio, self.fim = insc["inicio"], insc["fim"]
        self.dias = (d.data(self.fim) - self.hoje).days if self.fim else None
        self.edital = d.edital(c)
        self.ato = ato_principal(c)
        self.botao = "Ver edital oficial" if self.edital else "Ver ato oficial"
        self.orgao = c["orgao"]
        self.orgao_curto = orgao_curto(c["orgao"])
        self.ano = ano(c)
        self.ficticio = c["ficticio"]
        self.path = f"/concurso/{self.id}/"
        self.og = f"/og/{self.id}.png"
        self.taxa = texto_taxa(c["taxa"])
        # Professor federal (magistério superior ou EBTT): o salário é vencimento + retribuição por titulação.
        self.magisterio = self.federal and bool(cargos) and all(
            re.search(r"magist[ée]rio|\bEBTT\b|ensino b[áa]sico,? t[ée]cnico", k["nome"], re.I) for k in cargos)
        self.rotulo_salario = ("Salário inicial bruto (vencimento + retribuição por titulação)" if self.magisterio
                               else "Salário inicial")
        self.tabelas_titulacao = [dict(t, linhas=[(d.TITULACOES[n], v) for n, v in t["linhas"]]) for t in d.tabelas_titulacao(c)]

    # ---------- textos ----------

    @property
    def selo(self):
        if self.situacao == "breve":
            n = self.dias
            return "Encerra hoje" if n <= 0 else "Encerra amanhã" if n == 1 else f"Encerra em {n} dias"
        return {"aberto": "Aberto", "previsto": "Previsto", "encerrado": "Encerrado"}[self.situacao]

    @property
    def local(self):
        c = self.c
        if c["nacional"]:
            return "Nacional" + (f" · {c['abrangencia']}" if c["abrangencia"] else "")
        return f"{c['cidade'] or 'Cidade não informada'} ({c['uf']})"

    @property
    def prazo_rotulo(self):
        return {"previsto": "Inscrições:", "encerrado": "Encerrou em"}.get(self.situacao, "Inscrições até")

    @property
    def prazo(self):
        if self.situacao == "encerrado":
            return d.data_curta(self.fim)
        if self.situacao == "previsto":
            return f"a partir de {d.data_curta(self.inicio)}" if self.inicio else "sem data ainda"
        return d.data_curta(self.fim) if self.fim else "não informado"

    @property
    def resumo_inscricao(self):
        if self.situacao == "previsto":
            return f"a partir de {d.data_curta(self.inicio)}" if self.inicio else "sem data ainda"
        if not self.fim:
            return "não informado"
        return ("encerrou " if self.situacao == "encerrado" else "até ") + d.data_curta(self.fim)

    @property
    def inscricoes(self):
        i, f = self.inicio, self.fim
        if i and f:
            return f"{d.data_curta(i)} a {d.data_curta(f)}"
        if f:
            return f"até {d.data_curta(f)}"
        return f"a partir de {d.data_curta(i)}" if i else None

    @property
    def fonte(self):
        return FONTES.get((self.ato or {}).get("fonte"), "Fonte oficial")

    @property
    def conferido(self):
        if self.ficticio:
            return "exemplo fictício"
        conf = self.c["conferencia"]
        return f"conferido em {d.data_br(conf['conferido_em'])}" if conf else "não conferido"

    @property
    def retificado(self):
        r = [x for x in self.c["documentos"] if x["tipo"] == "retificacao" and x["publicado_em"]]
        return max(r, key=lambda x: x["publicado_em"]) if r else None

    @property
    def title(self):
        base = f"Concurso {self.orgao_curto} {self.ano}".strip()
        if self.situacao == "encerrado":
            return f"{base}: inscrições encerradas em {d.data_br(self.fim)}"
        if self.situacao == "previsto":
            if self.banca and any(x["tipo"] == "contratacao_banca" for x in self.c["documentos"]):
                return f"{base} previsto: banca {self.banca} contratada"
            return f"{base} previsto: autorizado, sem edital ainda"
        partes = []
        if self.faixa_salario:
            partes.append(f"salário inicial de {self.faixa_salario}")
        if self.fim:
            partes.append(f"inscrições até {d.data_curta(self.fim)}")
        return base + (": " + ", ".join(partes) if partes else "")

    @property
    def description(self):
        n = len(self.cargos)
        partes = []
        if self.situacao == "previsto":
            partes.append(f"{self.orgao}: concurso previsto, com ato oficial de "
                          + ("contratação da banca" if any(x["tipo"] == "contratacao_banca" for x in self.c["documentos"]) else "autorização")
                          + ". Ainda sem edital, sem data de inscrição.")
        else:
            cargos = plural(n, "cargo", "cargos") if n else "cargos não informados"
            sal = f"salário inicial de {self.faixa_salario}" if self.faixa_salario else "salário não informado no edital"
            partes.append(f"{self.orgao}: {cargos}, {self.vagas.lower()}, {sal}.")
            if self.situacao == "encerrado":
                partes.append(f"Inscrições encerradas em {d.data_br(self.fim)}.")
            elif self.inscricoes:
                partes.append(f"Inscrições {self.inscricoes}" + (f" no site da banca {self.banca}." if self.banca else "."))
            if self.c["prova_objetiva"]:
                partes.append(f"Prova objetiva em {d.data_br(self.c['prova_objetiva'])}.")
        partes.append("Com o link do edital oficial." if self.edital else "Com o link do ato oficial.")
        return " ".join(partes)

    # ---------- ordem ----------

    def chave(self):
        """Abertos com salário primeiro, por prazo; depois abertos sem salário; previstos; encerrados (mais recentes antes)."""
        grupo = {"breve": 0, "aberto": 0, "previsto": 2, "encerrado": 3}[self.situacao]
        if grupo == 0 and self.sal_max is None:
            grupo = 1
        if self.situacao == "encerrado":
            return (grupo, -d.data(self.fim).toordinal(), self.orgao)   # o que encerrou por último vem antes
        return (grupo, d.data(self.fim or self.inicio or "9999-12-31").toordinal(), self.orgao)


def ordenar(lista):
    return sorted(lista, key=Concurso.chave)


@dataclass
class Grupo:
    """Uma página de lista: cidade, área, banca, estado e afins."""
    slug: str
    nome: str
    concursos: list
    extra: dict = field(default_factory=dict)

    @property
    def abertos(self):
        return [x for x in self.concursos if x.aberto]

    @property
    def previstos(self):
        return [x for x in self.concursos if x.situacao == "previsto"]

    @property
    def encerrados(self):
        return [x for x in self.concursos if x.situacao == "encerrado"]


class Base:
    """Todos os concursos e agrupamentos de um build."""

    def __init__(self, base, hoje, municipios, exemplo=False):
        self.hoje = hoje
        self.varredura = base.get("varredura")
        self.proxima = base.get("proxima_varredura")
        self.cobertura = base.get("cobertura") or ["federal", "PR"]
        self.municipios = municipios          # {ibge: {ibge, nome, lat, lon[, ficticio]}}
        self.exemplo = exemplo
        self.previa = None           # data da varredura quando o build é a prévia (--previa)
        self.concursos = ordenar(Concurso(c, hoje, municipio=municipios.get(c["municipio_ibge"])) for c in base["concursos"])
        self.por_id = {x.id: x for x in self.concursos}
        self.ativos = [x for x in self.concursos if x.ativo]
        self.abertos = [x for x in self.concursos if x.aberto]
        self.previstos = [x for x in self.concursos if x.situacao == "previsto"]
        self.breve = sorted((x for x in self.concursos if x.situacao == "breve"), key=lambda x: x.fim)
        self.tem_ficticio = any(x.ficticio for x in self.concursos)
        self._cidades()
        self._parecidos()

    # ---------- cidades: só as que têm concurso ativo na cidade ou a até 50 km ----------

    def _cidades(self):
        locais = [x for x in self.ativos if x.no_pr and x.municipio]
        self.cidades = {}
        for m in sorted(self.municipios.values(), key=lambda m: slug(m["nome"])):
            na = [x for x in locais if x.municipio["ibge"] == m["ibge"]]
            perto = [(distancia(m, x.municipio), x) for x in locais if x.municipio["ibge"] != m["ibge"]]
            perto = [(km, x) for km, x in perto if km <= RAIO_KM]
            if not na and not perto:
                continue
            g = Grupo(slug(m["nome"]), m["nome"], ordenar(na),
                      extra={"municipio": m, "regiao": sorted(perto, key=lambda p: (p[0], p[1].chave()))})
            self.cidades[g.slug] = g
        por_ibge = {g.extra["municipio"]["ibge"]: g.slug for g in self.cidades.values()}
        for x in self.concursos:
            if x.municipio:
                x.cidade_slug = por_ibge.get(x.municipio["ibge"])
        self.cidade_por_ibge = por_ibge

    # ---------- encerrados: abertos parecidos (mesma área; mais perto primeiro, quando dá para medir) ----------

    def _parecidos(self, n=4):
        for x in self.concursos:
            if x.situacao != "encerrado":
                continue
            cand = [y for y in self.abertos if y.area == x.area and y.id != x.id] or [y for y in self.abertos if y.id != x.id]
            if x.municipio:
                cand.sort(key=lambda y: (distancia(x.municipio, y.municipio) if y.municipio else 99999, y.chave()))
            x.parecidos = cand[:n]

    # ---------- agrupamentos ----------

    def areas(self, nomes):
        return [Grupo(slug(a), a, [x for x in self.concursos if x.area == a]) for a in nomes]

    def bancas(self):
        grupos = {}
        for x in self.concursos:
            if not x.banca_slug:
                continue
            g = grupos.setdefault(x.banca_slug, Grupo(x.banca_slug, x.banca, []))
            g.concursos.append(x)
            if len(x.banca) > len(g.nome):   # o nome mais completo que apareceu
                g.nome = x.banca
        return sorted(grupos.values(), key=lambda g: slug(g.nome))

    def estado_pr(self):
        return Grupo("pr", "Paraná", [x for x in self.concursos if x.no_pr])

    def federais(self):
        return Grupo("federais", "Federais", [x for x in self.concursos if x.federal])

    def no_sitemap(self, x):
        if x.situacao != "encerrado":
            return True
        return (self.hoje - d.data(x.fim)).days <= DIAS_NO_SITEMAP
