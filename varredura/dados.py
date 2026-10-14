"""Caminhos, leitura dos arquivos de dados e as regras que a varredura e o site compartilham."""
import json
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
DADOS_JS = RAIZ / "assets" / "js" / "dados.js"
CACHE = RAIZ / ".cache"

# Campos que uma pessoa confere antes de qualquer concurso ir ao ar (regra 4).
CAMPOS_CRITICOS = ["salario", "inscricao.inicio", "inscricao.fim", "prova_objetiva", "taxa", "banca", "cidade", "edital"]

DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def ler_json(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def gravar_json(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


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
