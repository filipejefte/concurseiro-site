"""Revisão: revisao.md e revisao.csv na pasta da semana.

Para cada concurso novo ou alterado vêm os campos críticos, o trecho do ato de onde saíram e a
coluna "conferido":
  auto      a conferência automática achou o valor no texto do ato (conferir.py);
  amostra   passou na automática, mas caiu na amostra semanal: a pessoa confere e troca por ok;
  (vazio)   a automática não achou: a pessoa confere (o motivo vai em "observacao");
  ok | corrigir   marcas da pessoa, que valem sobre as automáticas.
Rodar de novo mantém as marcas da pessoa nas linhas que não mudaram e refaz as automáticas.
"""
import csv
from datetime import date
from pathlib import Path

from .comparar import comparar
from .conferir import na_amostra, texto_dos_atos, verificar
from . import dados
from .dados import brl, carregar_fichas, data_br, edital, ler_json, situacao
from .extracao import ler_fila, pendentes
from .validar import validar_concurso

CSV = "revisao.csv"
MD = "revisao.md"
COBERTURA = "cobertura.csv"   # para conferir à mão a cobertura contra os agregadores (só conferir, nunca copiar)
COLUNAS = ["id", "situacao", "campo", "valor", "trecho", "conferido", "observacao"]
MARCAS_DA_PESSOA = ("ok", "corrigir")
ORDEM = {"corrigir": 0, "": 0, "amostra": 1}   # o que a pessoa precisa olhar vem primeiro no CSV
NI = "Não informado no edital"


def texto_taxa(t):
    if t["min"] is None and t["max"] is None:
        return NI
    if t["min"] is None or t["max"] is None or t["min"] == t["max"]:
        return brl(t["min"] if t["min"] is not None else t["max"])
    return f"{brl(t['min'])} a {brl(t['max'])}"


def texto_cidade(c):
    if c["nacional"]:
        return f"Nacional ({c['abrangencia'] or 'vários estados'}) · sede {c['cidade'] or NI}/{c['uf']}"
    return f"{c['cidade'] or NI} ({c['uf']}) · IBGE {c['municipio_ibge'] or 'sem código'}"


def ato_principal(c):
    """O edital; sem edital (previsto), o ato de autorização ou de contratação da banca."""
    return edital(c) or next((d for d in c["documentos"] if d["tipo"] in ("autorizacao", "contratacao_banca")), None)


def linhas_criticas(c):
    """[(campo, valor em texto)]: o que uma pessoa confere antes de publicar (regra 4)."""
    linhas = [("salario", f"{k['nome']}: {brl(k['salario'])}") for k in c["cargos"]]
    return linhas + [
        ("inscricao.inicio", data_br(c["inscricao"]["inicio"])),
        ("inscricao.fim", data_br(c["inscricao"]["fim"])),
        ("prova_objetiva", data_br(c["prova_objetiva"])),
        ("taxa", texto_taxa(c["taxa"])),
        ("banca", c["banca"]["nome"] or NI),
        ("cidade", texto_cidade(c)),
        ("edital", (ato_principal(c) or {}).get("url") or "sem link"),
    ]


def ler_marcas(pasta):
    """{(id, campo, valor): (conferido, observacao)} do revisao.csv, se existir."""
    arquivo = Path(pasta) / CSV
    if not arquivo.exists():
        return {}
    with arquivo.open(encoding="utf-8-sig", newline="") as f:
        return {(l["id"], l["campo"], l["valor"]): ((l.get("conferido") or "").strip().lower(), l.get("observacao") or "")
                for l in csv.DictReader(f, delimiter=";")}


def _celula(texto):
    return str(texto or "").replace("|", "\\|").replace("\n", " ").strip()


def gerar(pasta, data_varredura=None):
    pasta = Path(pasta)
    data_varredura = data_varredura or date.fromisoformat(pasta.name)
    base = ler_json(dados.CONCURSOS)
    fichas = carregar_fichas(pasta)
    por_id = {f["concurso"]["id"]: f for f in fichas if f.get("concurso")}
    r = comparar([f for f in fichas if f.get("concurso")], base, data_varredura)
    marcas = ler_marcas(pasta)

    linhas_csv, md = [], []
    registro = ler_json(pasta / "atos.json") if (pasta / "atos.json").exists() else {"atos": [], "fontes": {}}
    atos_por_fila = {a["fila"]: a for a in registro.get("atos", []) if a.get("fila")}
    md.append(f"# Revisão da varredura de {data_varredura:%d/%m/%Y}\n")
    md.append(f"Fichas: {len(fichas)} · novos: {len(r.novos)} · alterados: {len(r.alterados)} · iguais ao publicado: "
              f"{len(r.iguais)} · encerrados desde a última varredura: {len(r.encerrados)}\n")
    md.append("Como conferir: abra `revisao.csv` (Excel ou LibreOffice). As linhas `auto` a conferência automática já "
              "achou no texto do ato. Confira só as linhas com **conferido** vazio (o motivo está em `observacao`) e as "
              "marcadas `amostra`, comparando com o ato oficial, e escreva `ok`. Valor errado: corrija "
              "`fichas/<id>.json`, rode `python -m varredura revisao` de novo (as suas marcas nas linhas que não "
              "mudaram ficam) e marque `ok`. `corrigir` segura o concurso fora da publicação.\n")
    resumo_pos = len(md)

    falhas = {nome: estado for nome, estado in registro.get("fontes", {}).items() if estado != "ok"}
    if falhas:
        md.append("## Fontes com problema nesta coleta\n")
        md += [f"- **{nome}**: {estado}" for nome, estado in falhas.items()]
        md.append("")

    problemas = {c["id"]: validar_concurso(c) for c in r.novos + [n for n, _ in r.alterados]}
    problemas = {k: v for k, v in problemas.items() if v}
    if problemas:
        md.append("## Problemas de validação (não publica enquanto houver)\n")
        for id_, erros in problemas.items():
            md += [f"- `{id_}`: {e}" for e in erros]
        md.append("")

    def bloco(c, situacao, antigo=None):
        ficha = por_id[c["id"]]
        trechos = ficha.get("trechos") or {}
        ato = ficha.get("ato", "")
        meta = atos_por_fila.get(ato)
        if meta is None:
            try:
                meta, _ = ler_fila(pasta / "fila" / ato)
            except (OSError, ValueError):
                meta = None
        origem = (f"[{_celula(meta.get('titulo'))}]({meta.get('url')}) · {meta.get('fonte')} · {meta.get('data')}"
                  if meta else ato or "ato não identificado")
        antes = dict(linhas_criticas(antigo)) if antigo else {}
        texto, links = texto_dos_atos(pasta, ficha)
        cargos = iter(c["cargos"])
        md.append(f"### {c['orgao']} · `{c['id']}`\n")
        md.append(f"Ato: {origem}\n")
        md.append("| Campo | Valor | Trecho do ato |\n| --- | --- | --- |")
        for campo, valor in linhas_criticas(c):
            mudou = antigo is not None and antes.get(campo) != valor and campo != "salario"
            valor_md = f"**{_celula(valor)}** (antes: {_celula(antes.get(campo, '—'))})" if mudou else _celula(valor)
            md.append(f"| {campo} | {valor_md} | {_celula(trechos.get(campo))} |")
            cargo = next(cargos) if campo == "salario" else None
            conferido, obs = marcas.get((c["id"], campo, valor), ("", ""))
            if conferido not in MARCAS_DA_PESSOA:
                conferido, obs = "", ""
            if not conferido and antigo is not None and (campo, valor) in linhas_criticas(antigo) and antigo.get("conferencia"):
                conf = antigo["conferencia"]
                conferido, obs = "ok", f"igual ao publicado (conferido em {conf['conferido_em']} por {conf['por']})"
            if not conferido:
                passou, motivo = verificar(campo, c, texto, links, cargo)
                if not passou:
                    obs = "conferir: " + motivo
                elif na_amostra(pasta.name, c["id"], campo, valor):
                    conferido, obs = "amostra", f"amostra semanal ({motivo}): confira e troque por ok"
                else:
                    conferido, obs = "auto", motivo
            linhas_csv.append({"id": c["id"], "situacao": situacao, "campo": campo, "valor": valor,
                               "trecho": trechos.get(campo, ""), "conferido": conferido, "observacao": obs})
        md.append("")

    if r.novos:
        md.append("## Novos\n")
        for c in r.novos:
            bloco(c, "novo")
    if r.alterados:
        md.append("## Alterados (retificações)\n")
        for c, antigo in r.alterados:
            bloco(c, "alterado", antigo)
    if r.encerrados:
        md.append("## Encerrados desde a última varredura\n")
        md += [f"- {c['orgao']} (`{c['id']}`): inscrição até {data_br(c['inscricao']['fim'])}" for c in r.encerrados]
        md.append("")
    if r.ignorados:
        md.append("## Ignorados: inscrição já encerrada na data da varredura\n")
        md += [f"- {c['orgao']} (`{c['id']}`): inscrição até {data_br(c['inscricao']['fim'])}" for c in r.ignorados]
        md.append("")
    pss = [a for a in registro.get("atos", []) if a.get("pss")]
    if pss:
        md.append("## Em avaliação: processos seletivos simplificados (não publicados)\n")
        md += [f"- {_celula(a['orgao'])} · [{_celula(a['titulo'])}]({a['url']}) · {a['data']}" for a in pss]
        md.append("")
    faltam = pendentes(pasta) if (pasta / "fila").exists() else []
    if faltam:
        md.append("## Fila sem ficha nem descarte (extração pendente)\n")
        md += [f"- `fila/{p.name}`" for p in faltam]
        md.append("")
    if (pasta / "descartes.json").exists():
        md.append("## Descartados na extração\n")
        md += [f"- `{d['ato']}`: {d['motivo']}" for d in ler_json(pasta / "descartes.json")]
        md.append("")

    n = {k: sum(1 for l in linhas_csv if l["conferido"] == k) for k in ("", "amostra", "auto", "ok", "corrigir")}
    md.insert(resumo_pos, f"**Conferência:** {len(linhas_csv)} linhas · {n['auto']} achadas no ato pela automática · "
                          f"**{n[''] + n['amostra']} para você** ({n['']} que a automática não achou e {n['amostra']} "
                          f"da amostra) · {n['ok']} ok · {n['corrigir']} corrigir\n")
    linhas_csv.sort(key=lambda l: ORDEM.get(l["conferido"], 2))   # estável: dentro de cada grupo, a ordem dos concursos
    (pasta / MD).write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    # utf-8 com BOM e ";" para o Excel em português abrir certo.
    with (pasta / CSV).open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas_csv)
    escrever_cobertura(pasta, base, [f["concurso"] for f in fichas if f.get("concurso")], data_varredura)
    return r, problemas


def escrever_cobertura(pasta, base, novos, data_varredura):
    """cobertura.csv: todo concurso conhecido (publicado ou ficha da semana), para comparar à mão com os agregadores."""
    todos = {c["id"]: (c, "sim") for c in base["concursos"]}
    todos.update({c["id"]: (c, "não (ficha da semana)") for c in novos})
    ordem = {"aberto": 0, "breve": 0, "previsto": 1, "encerrado": 2}
    linhas = []
    for c, publicado in todos.values():
        sit = situacao(c, data_varredura)
        linhas.append({
            "orgao": c["orgao"], "cidade": "Nacional" if c["nacional"] else (c["cidade"] or ""), "uf": c["uf"],
            "situacao": {"breve": "aberto (encerra em até 7 dias)"}.get(sit, sit), "fim_inscricao": data_br(c["inscricao"]["fim"]),
            "link_edital": (ato_principal(c) or {}).get("url", ""), "esfera": c["esfera"], "publicado": publicado, "id": c["id"],
        })
    linhas.sort(key=lambda l: (ordem[situacao(todos[l["id"]][0], data_varredura)], l["uf"] != "PR", l["orgao"]))
    with (Path(pasta) / COBERTURA).open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]) if linhas else ["orgao"], delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
