"""progresso.md na pasta da semana: o que falta extrair, para a próxima sessão do Claude Code retomar dali.

A parte de cima é refeita a cada `python -m varredura progresso`; a seção "Notas" (último lote, o que ficou
para trás e por quê) é escrita por quem extrai e fica como está.
"""
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from .dados import carregar_fichas, data_br, ler_json
from .extracao import PRIORIDADES, ler_fila, pendentes, prioridade

ARQUIVO = "progresso.md"
MARCA = "<!-- notas: daqui para baixo, escrito à mão -->"
NOTAS_INICIAIS = """## Notas

- Último lote: (nenhum ainda)
- Ficou para trás, e por quê: (nada)
"""


def escrever(pasta, hoje=None):
    pasta = Path(pasta)
    hoje = hoje or date.today()
    fila = sorted((pasta / "fila").glob("*.md")) if (pasta / "fila").exists() else []
    faltam = pendentes(pasta) if fila else []
    fonte = lambda a: ler_fila(a)[0].get("fonte", "?")
    na_fila, por_fazer = Counter(fonte(a) for a in fila), Counter(fonte(a) for a in faltam)
    grupos = Counter(prioridade(a, hoje)[0] for a in faltam)
    fichas = carregar_fichas(pasta) if (pasta / "fichas").exists() else []
    descartes = ler_json(pasta / "descartes.json") if (pasta / "descartes.json").exists() else []
    atos = ler_json(pasta / "atos.json") if (pasta / "atos.json").exists() else {"atos": [], "fontes": {}}
    pss = Counter(a["fonte"] for a in atos.get("atos", []) if a.get("pss"))

    linhas = [f"# Progresso da extração · varredura de {data_br(pasta.name)}", "",
              f"Atualizado em {datetime.now():%d/%m/%Y %H:%M} por `python -m varredura progresso`. "
              "A parte de cima é refeita a cada vez; a seção Notas fica como está.", "",
              "| Fonte | Na fila | Feitos (ficha ou descarte) | Faltam |", "| --- | --- | --- | --- |"]
    for f in sorted(na_fila):
        linhas.append(f"| {f} | {na_fila[f]} | {na_fila[f] - por_fazer[f]} | {por_fazer[f]} |")
    linhas.append(f"| **Total** | **{len(fila)}** | **{len(fila) - len(faltam)}** | **{len(faltam)}** |")
    linhas += ["", "Faltam, por prioridade: " + " · ".join(f"P{g} ({PRIORIDADES[g]}): {grupos[g]}" for g in sorted(PRIORIDADES)),
               "", f"Fichas: {len(fichas)} · descartes: {len(descartes)}",
               "PSS na coleta (fora da fila): " + (" · ".join(f"{f} {n}" for f, n in sorted(pss.items())) or "nenhum"),
               "Fontes: " + (" · ".join(f"{f}: {e}" for f, e in atos.get("fontes", {}).items()) or "sem atos.json"), ""]
    alvo = pasta / ARQUIVO
    notas = alvo.read_text(encoding="utf-8").split(MARCA, 1)[1].lstrip("\n") if alvo.exists() and MARCA in alvo.read_text(encoding="utf-8") \
        else NOTAS_INICIAIS
    alvo.write_text("\n".join(linhas) + "\n" + MARCA + "\n\n" + notas, encoding="utf-8", newline="\n")
    return alvo, len(faltam)
