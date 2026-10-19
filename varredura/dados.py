"""Caminhos, leitura dos arquivos de dados e as regras que a varredura e o site compartilham."""
import json
import os
import re
import tomllib
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
CONCURSOS = DADOS / "concursos.json"
EXEMPLO = DADOS / "exemplo" / "concursos.json"
MUNICIPIOS = DADOS / "municipios-pr.json"
MUNICIPIOS_FICTICIOS = DADOS / "exemplo" / "municipios-ficticios.json"
SCHEMA = DADOS / "schema" / "concurso.schema.json"
VARREDURAS = DADOS / "varreduras"
CACHE = RAIZ / ".cache"
SITE_TOML = RAIZ / "site.toml"

# Campos que uma pessoa confere antes de qualquer concurso ir ao ar (regra 4).
CAMPOS_CRITICOS = ["salario", "inscricao.inicio", "inscricao.fim", "prova_objetiva", "taxa", "banca", "cidade", "edital"]

DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def site_url(caminho=""):
    """Endereço público do site (site_url do site.toml) mais o caminho: site_url("/concurso/x/")."""
    with open(SITE_TOML, "rb") as f:
        base = tomllib.load(f)["site_url"].rstrip("/")
    return base + "/" + caminho.lstrip("/")


def ler_json(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def gravar_json(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def carregar_env(caminho=RAIZ / ".env"):
    """Lê CHAVE=valor do .env para o ambiente (sem sobrescrever o que já existe)."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def ultima_pasta():
    """Pasta da varredura mais recente (dados/varreduras/AAAA-MM-DD)."""
    pastas = sorted(p for p in VARREDURAS.glob("????-??-??") if p.is_dir()) if VARREDURAS.exists() else []
    if not pastas:
        raise SystemExit("Nenhuma varredura em dados/varreduras/. Rode antes: python -m varredura coletar ...")
    return pastas[-1]


def carregar_fichas(pasta):
    """Fichas extraídas da semana: [{"ato", "trechos", "concurso"}], uma por arquivo em fichas/."""
    return [ler_json(f) for f in sorted((Path(pasta) / "fichas").glob("*.json"))]


def data(texto):
    return date.fromisoformat(texto) if texto else None


def municipios(exemplo=False):
    """Tabela {ibge: municipio}. Com exemplo=True inclui as cidades fictícias dos dados de exemplo."""
    lista = ler_json(MUNICIPIOS)["municipios"]
    if exemplo:
        lista = lista + ler_json(MUNICIPIOS_FICTICIOS)["municipios"]
    return {m["ibge"]: m for m in lista}


def situacao(c, hoje):
    """aberto | breve (encerra em até 7 dias) | previsto | encerrado, a partir das datas da inscrição."""
    insc = c.get("inscricao") or {}
    inicio, fim = data(insc.get("inicio")), data(insc.get("fim"))
    if fim and fim < hoje:
        return "encerrado"
    if (inicio is None and fim is None) or (inicio and inicio > hoje):
        return "previsto"
    if fim and (fim - hoje).days <= 7:
        return "breve"
    return "aberto"


def edital(c):
    """O edital mais recente da ficha, ou None (concurso previsto ainda não tem edital)."""
    editais = [d for d in c["documentos"] if d["tipo"] == "edital"]
    return max(editais, key=lambda d: d["publicado_em"] or "") if editais else None


def brl(valor):
    if valor is None:
        return "Não informado no edital"
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def data_br(d):
    d = data(d) if isinstance(d, str) else d
    return d.strftime("%d/%m/%Y") if d else "Não informado no edital"


def data_curta(d):
    """'sex, 20/11', como nos cards."""
    d = data(d) if isinstance(d, str) else d
    return f"{DIAS_SEMANA[d.weekday()]}, {d:%d/%m}" if d else "Não informado no edital"


TITULACOES = {"graduacao": "Graduação", "aperfeicoamento": "Aperfeiçoamento", "especializacao": "Especialização",
              "mestrado": "Mestrado", "doutorado": "Doutorado"}


def regime_do_cargo(k):
    """"dedicação exclusiva", "40 horas" ou "20 horas", pelo que a ficha diz do cargo; None quando não diz."""
    if re.search(r"dedica[çc][ãa]o exclusiva|\(DE\)", (k.get("requisitos") or "") + " " + k["nome"], re.I):
        return "dedicação exclusiva"
    return f"{k['jornada_horas']:g} horas" if k.get("jornada_horas") else None


def tabelas_titulacao(c):
    """Tabelas de remuneração por titulação dos cargos, sem repetir: [{"regime", "jornada", "linhas": [(titulacao, valor)]}].

    Só existe em professor federal quando o edital aceita titulação menor na falta de candidatos
    (campo remuneracao_por_titulacao do cargo)."""
    saida, vistas = [], set()
    for k in c["cargos"]:
        linhas = tuple((r["titulacao"], r["valor"]) for r in k.get("remuneracao_por_titulacao") or [])
        chave = (regime_do_cargo(k), k.get("jornada_horas"), linhas)
        if linhas and chave not in vistas:
            vistas.add(chave)
            saida.append({"regime": chave[0], "jornada": chave[1], "linhas": list(linhas)})
    return saida
