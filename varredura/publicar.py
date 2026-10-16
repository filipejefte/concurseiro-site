"""Publicação.

gerar_js: escreve assets/js/dados.js, que o site lê (funciona até abrindo o HTML direto, sem servidor).
publicar_semana: leva para dados/concursos.json só os concursos com todos os campos críticos
conferidos no revisao.csv, atualiza as datas da varredura, gera o dados.js e escreve
resumo-telegram.md na pasta da semana.
"""
import json
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from . import dados as d
from .comparar import comparar
from .revisao import ato_principal, ler_marcas, linhas_criticas
from .validar import validar_concurso


def _linhas(itens):
    # Um item por linha: o diff semanal mostra só o que mudou.
    return "[\n" + ",\n".join(json.dumps(i, ensure_ascii=False, separators=(",", ":")) for i in itens) + "\n]"


def _sem_acento(texto):
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()


def gerar_js(base, exemplo=False, hoje=None):
    """Escreve dados.js a partir de um arquivo no formato de dados/concursos.json.

    A situação é calculada aqui, na data da varredura; o navegador só refaz a contagem
    regressiva e marca "Encerrado" pela data de hoje.
    """
    ref = d.data(base["varredura"]) or hoje or date.today()
    concursos = [dict(c, situacao=d.situacao(c, ref)) for c in base["concursos"]]
    meta = {k: base[k] for k in ("varredura", "proxima_varredura", "cobertura")}
    meta["exemplo"] = exemplo
    areas = d.ler_json(d.SCHEMA)["properties"]["area"]["enum"]
    tabela = sorted(d.municipios(exemplo).values(), key=lambda m: _sem_acento(m["nome"]))
    tabela = [[m["ibge"], m["nome"], m["lat"], m["lon"]] + ([1] if m.get("ficticio") else []) for m in tabela]

    aviso = "DADOS DE EXEMPLO, FICTÍCIOS. " if exemplo else ""
    texto = (
        f"/* {aviso}Gerado por `python -m varredura publicar{' --exemplo' if exemplo else ''}`. Não edite à mão.\n"
        "   MUNICIPIOS: [código IBGE, nome, latitude, longitude, 1 se fictício]. */\n"
        f"window.VARREDURA = {json.dumps(meta, ensure_ascii=False)};\n"
        f"window.AREAS = {json.dumps(areas, ensure_ascii=False)};\n"
        f"window.MUNICIPIOS = {_linhas(tabela)};\n"
        f"window.CONCURSOS = {_linhas(concursos)};\n"
    )
    d.DADOS_JS.write_text(texto, encoding="utf-8", newline="\n")
    return concursos


CONFERIDO = ("ok", "auto")   # ok = a pessoa; auto = achado no texto do ato pela conferência automática


def _faltando_conferir(c, marcas):
    """Campos críticos sem "ok" nem "auto" no revisao.csv (o valor tem de ser o mesmo da ficha atual)."""
    return [f"{campo} ({valor})" for campo, valor in linhas_criticas(c)
            if marcas.get((c["id"], campo, valor), ("", ""))[0] not in CONFERIDO]


def _quem_conferiu(c, marcas, por):
    tipos = {marcas[(c["id"], campo, valor)][0] for campo, valor in linhas_criticas(c)}
    if tipos == {"auto"}:
        return "conferência automática"
    return por + (" e conferência automática" if "auto" in tipos else "")


def publicar_semana(pasta, por, hoje=None):
    """Devolve (aprovados, recusados). Recusado = ficha inválida, fictícia ou com campo crítico não conferido."""
    pasta = Path(pasta)
    hoje = hoje or date.today()
    data_varredura = date.fromisoformat(pasta.name)
    base = d.ler_json(d.CONCURSOS)
    fichas = [f for f in d.carregar_fichas(pasta) if f.get("concurso")]
    r = comparar(fichas, base, data_varredura)
    marcas = ler_marcas(pasta)
    tabela = d.municipios()

    aprovados, recusados = [], []
    for c in r.novos + [novo for novo, _ in r.alterados]:
        erros = validar_concurso(c, tabela)
        faltam = _faltando_conferir(c, marcas)
        if erros:
            recusados.append((c["id"], "ficha inválida: " + "; ".join(erros)))
        elif faltam:
            recusados.append((c["id"], "falta conferir: " + ", ".join(faltam)))
        else:
            aprovados.append(c)

    publicados = {c["id"]: c for c in base["concursos"]}
    for c in aprovados:
        antigo = publicados.get(c["id"]) or {}
        publicados[c["id"]] = dict(
            c,
            conferencia={"conferido_em": hoje.isoformat(), "por": _quem_conferiu(c, marcas, por),
                         "campos": [campo for campo in d.CAMPOS_CRITICOS if any(k == campo for k, _ in linhas_criticas(c))]},
            primeira_varredura=antigo.get("primeira_varredura") or data_varredura.isoformat(),
            ultima_alteracao=data_varredura.isoformat(),
        )
    anterior = base["varredura"]
    base["concursos"] = sorted(publicados.values(), key=lambda c: c["id"])
    base["varredura"] = data_varredura.isoformat()
    base["proxima_varredura"] = (data_varredura + timedelta(days=7)).isoformat()
    d.gravar_json(d.CONCURSOS, base)
    gerar_js(base)
    escrever_resumo(pasta, base, aprovados, r.alterados, anterior, data_varredura)
    return aprovados, recusados


def _cargo(c):
    cargos = sorted(c["cargos"], key=lambda k: -(k["salario"] or 0))
    if not cargos:
        return "cargos não informados"
    return cargos[0]["nome"] + (f" e mais {len(cargos) - 1} cargo{'s' if len(cargos) > 2 else ''}" if len(cargos) > 1 else "")


def _salario(c):
    salarios = [k["salario"] for k in c["cargos"] if k["salario"] is not None]
    if not salarios:
        return "salário não informado"
    return ("até " if len(set(salarios)) > 1 else "") + d.brl(max(salarios))


def _linha(c):
    insc = c["inscricao"]
    prazo = f"inscrições até {d.data_curta(insc['fim'])}" if insc["fim"] else "previsto, sem data de inscrição"
    lugar = f"Nacional ({c['abrangencia']})" if c["nacional"] else f"{c['cidade']} ({c['uf']})"
    ato = ato_principal(c) or {}
    return (f"• {c['orgao']} — {_cargo(c)}\n"
            f"  {_salario(c)} · {prazo} · {lugar}\n"
            f"  Ficha: {d.SITE}concurso.html?id={c['id']}\n"
            f"  {'Edital oficial' if ato.get('tipo') == 'edital' else 'Ato oficial'}: {ato.get('url', 'sem link')}")


def escrever_resumo(pasta, base, aprovados, alterados, anterior, data_varredura):
    ids_alterados = {novo["id"] for novo, _ in alterados}
    novos = [c for c in aprovados if c["id"] not in ids_alterados]
    retificados = [c for c in aprovados if c["id"] in ids_alterados]
    acabando = sorted((c for c in base["concursos"] if d.situacao(c, data_varredura) == "breve"),
                      key=lambda c: c["inscricao"]["fim"])
    periodo = f"de {d.data(anterior):%d/%m} a {data_varredura:%d/%m}" if anterior else f"até {data_varredura:%d/%m}"
    partes = [f"Concursos da semana ({periodo}) · federais e do Paraná", ""]
    partes += ["Novos", ""] + ([_linha(c) for c in novos] or ["• Nenhum concurso novo nesta semana."]) + [""]
    if retificados:
        partes += ["Retificados (o edital mudou)", ""] + [_linha(c) for c in retificados] + [""]
    if acabando:
        partes += ["Inscrições acabando nos próximos 7 dias", ""]
        partes += [f"• {c['orgao']} — até {d.data_curta(c['inscricao']['fim'])} — {d.SITE}concurso.html?id={c['id']}" for c in acabando]
        partes.append("")
    partes += [f"Todos os concursos: {d.SITE}",
               "Inscrição e pagamento, só no site da banca. Não somos site oficial."]
    (Path(pasta) / "resumo-telegram.md").write_text("\n".join(partes) + "\n", encoding="utf-8", newline="\n")
