"""Extração: da fila de atos para as fichas da semana.

Pasta da semana (dados/varreduras/AAAA-MM-DD/):
  fila/NNN-<fonte>-<data>.md   um ato por arquivo: cabeçalho chave: valor, linha "---", texto
  fichas/<id>.json             {"ato": <arquivo da fila>, "trechos": {...}, "concurso": {...}}
  descartes.json               [{"ato": <arquivo da fila>, "motivo": ...}]

Dois modos:
  claude-code (padrão, sem custo de API): só gera a fila; o /varredura do Claude Code lê cada
    arquivo e escreve a ficha seguindo varredura/instrucoes_extracao.md.
  api: chama o modelo claude-haiku-5-5 (chave em ANTHROPIC_API_KEY) para cada ato da fila.
"""
import json
import re
import unicodedata
from pathlib import Path

from .dados import CONCURSOS, SCHEMA, gravar_json, ler_json, municipios

MODELO = "claude-haiku-5-5"
INSTRUCOES = Path(__file__).with_name("instrucoes_extracao.md")
CAMPOS_FILA = ("fonte", "data", "classe", "pss", "orgao", "titulo", "url")


def _slug(texto, limite=50):
    texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")[:limite].strip("-")


def escrever_fila(pasta, atos_classificados):
    """Grava um arquivo por ato. Recebe [(ato, classe, pss)]; devolve os nomes dos arquivos."""
    fila = Path(pasta) / "fila"
    fila.mkdir(parents=True, exist_ok=True)
    nomes = []
    for n, (ato, classe, pss) in enumerate(atos_classificados, 1):
        meta = dict(ato.como_dict(), classe=classe, pss=pss)
        cabecalho = "\n".join(f"{k}: {str(meta[k]).replace(chr(10), ' ')}" for k in CAMPOS_FILA)
        nome = f"{n:03d}-{ato.fonte.lower()}-{ato.data}-{_slug(ato.orgao)}.md"
        (fila / nome).write_text(cabecalho + "\n---\n" + ato.texto + "\n", encoding="utf-8", newline="\n")
        nomes.append(nome)
    return nomes


def ler_fila(arquivo):
    cabecalho, texto = Path(arquivo).read_text(encoding="utf-8").split("\n---\n", 1)
    meta = dict(linha.split(": ", 1) for linha in cabecalho.splitlines() if ": " in linha)
    return meta, texto


def pendentes(pasta):
    """Arquivos da fila que ainda não viraram ficha nem descarte."""
    pasta = Path(pasta)
    feitos = {f["ato"] for f in (ler_json(p) for p in (pasta / "fichas").glob("*.json"))} if (pasta / "fichas").exists() else set()
    descartes = ler_json(pasta / "descartes.json") if (pasta / "descartes.json").exists() else []
    feitos |= {d["ato"] for d in descartes}
    return [p for p in sorted((pasta / "fila").glob("*.md")) if p.name not in feitos]


def registrar(pasta, nome_ato, resposta):
    """Guarda a resposta da extração: ficha em fichas/<id>.json ou motivo em descartes.json."""
    pasta = Path(pasta)
    if resposta.get("descartar"):
        caminho = pasta / "descartes.json"
        descartes = ler_json(caminho) if caminho.exists() else []
        descartes.append({"ato": nome_ato, "motivo": resposta["descartar"]})
        gravar_json(caminho, descartes)
        return None
    concurso = resposta["concurso"]
    gravar_json(pasta / "fichas" / f"{concurso['id']}.json",
                {"ato": nome_ato, "trechos": resposta.get("trechos") or {}, "concurso": concurso})
    return concurso["id"]


def _sistema():
    base = ler_json(CONCURSOS)
    existentes = "\n".join(f"{c['id']} | {c['orgao']}" for c in base["concursos"]) or "(nenhum ainda)"
    tabela = "\n".join(f"{m['ibge']} {m['nome']}" for m in municipios().values())
    return (
        INSTRUCOES.read_text(encoding="utf-8")
        + "\n\n## Schema da ficha\n\n" + SCHEMA.read_text(encoding="utf-8")
        + "\n\n## Concursos já publicados (id | órgão)\n\n" + existentes
        + "\n\n## Municípios do Paraná (código IBGE e nome)\n\n" + tabela
    )


def _json_da_resposta(texto):
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim < inicio:
        raise ValueError("a resposta não trouxe um objeto JSON")
    return json.loads(texto[inicio:fim + 1])


def extrair_api(pasta, data_varredura):
    """Modo api: uma chamada ao modelo por ato pendente. Devolve (fichas, descartes, falhas)."""
    import anthropic  # só o modo api precisa do SDK

    cliente = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY
    sistema = [{"type": "text", "text": _sistema(), "cache_control": {"type": "ephemeral"}}]
    fichas = descartes = 0
    falhas = []
    for arquivo in pendentes(pasta):
        meta, texto = ler_fila(arquivo)
        pedido = (f"Data da varredura: {data_varredura.isoformat()}\n"
                  + "\n".join(f"{k}: {meta.get(k, '')}" for k in CAMPOS_FILA)
                  + "\n\nTexto do ato:\n\n" + texto)
        try:
            resposta = cliente.messages.create(
                model=MODELO,
                max_tokens=16000,
                system=sistema,
                output_config={"effort": "medium"},
                messages=[{"role": "user", "content": pedido}],
            )
        except anthropic.RateLimitError as erro:
            falhas.append((arquivo.name, f"limite de uso da API: {erro}"))
            break
        except anthropic.APIStatusError as erro:
            falhas.append((arquivo.name, f"erro da API ({erro.status_code}): {erro.message}"))
            continue
        except anthropic.APIConnectionError as erro:
            falhas.append((arquivo.name, f"sem conexão com a API: {erro}"))
            break
        if resposta.stop_reason in ("refusal", "max_tokens"):
            falhas.append((arquivo.name, f"resposta interrompida ({resposta.stop_reason}); extraia à mão"))
            continue
        try:
            dados = _json_da_resposta("".join(b.text for b in resposta.content if b.type == "text"))
            if registrar(pasta, arquivo.name, dados):
                fichas += 1
            else:
                descartes += 1
        except (ValueError, KeyError, TypeError) as erro:
            falhas.append((arquivo.name, f"resposta fora do formato: {erro}"))
    return fichas, descartes, falhas
