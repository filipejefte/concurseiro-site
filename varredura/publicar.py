"""Publicação.

publicar_semana: leva para dados/concursos.json só os concursos com todos os campos críticos conferidos
no revisao.csv e atualiza as datas da varredura. Escreve na pasta da semana:
  resumo-telegram.md    o que o comando `python -m varredura telegram` posta no canal;
  resumo-whatsapp.txt   o mesmo resumo, curto, para colar no canal do WhatsApp;
  posts/post-<id>.png   imagem 1080x1350 de cada concurso novo, com a legenda em post-<id>.txt (fora do git).
O site sai de dados/concursos.json no próximo `python -m gerador build` (o deploy roda sozinho no push).
"""
from datetime import date, timedelta
from pathlib import Path

from . import dados as d
from .comparar import comparar
from .revisao import ato_principal, ler_marcas, linhas_criticas
from .validar import validar_concurso

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


def publicar_semana(pasta, por, hoje=None, posts=True):
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
    novos, retificados, acabando = _grupos(base, aprovados, r.alterados, data_varredura)
    escrever_resumo(pasta, novos, retificados, acabando, anterior, data_varredura)
    escrever_whatsapp(pasta, novos, retificados, acabando, anterior, data_varredura)
    if posts and novos:
        escrever_posts(pasta, [publicados[c["id"]] for c in novos], data_varredura)
    return aprovados, recusados


def _grupos(base, aprovados, alterados, data_varredura):
    ids_alterados = {novo["id"] for novo, _ in alterados}
    novos = [c for c in aprovados if c["id"] not in ids_alterados]
    retificados = [c for c in aprovados if c["id"] in ids_alterados]
    acabando = sorted((c for c in base["concursos"] if d.situacao(c, data_varredura) == "breve"),
                      key=lambda c: c["inscricao"]["fim"])
    return novos, retificados, acabando


def ficha_url(c):
    return d.site_url(f"/concurso/{c['id']}/")


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


def _prazo(c):
    insc = c["inscricao"]
    return f"inscrições até {d.data_curta(insc['fim'])}" if insc["fim"] else "previsto, sem data de inscrição"


def _lugar(c):
    return f"Nacional ({c['abrangencia']})" if c["nacional"] else f"{c['cidade']} ({c['uf']})"


def _linha(c):
    ato = ato_principal(c) or {}
    return (f"• {c['orgao']} — {_cargo(c)}\n"
            f"  {_salario(c)} · {_prazo(c)} · {_lugar(c)}\n"
            f"  Ficha: {ficha_url(c)}\n"
            f"  {'Edital oficial' if ato.get('tipo') == 'edital' else 'Ato oficial'}: {ato.get('url', 'sem link')}")


def _periodo(anterior, data_varredura):
    return f"de {d.data(anterior):%d/%m} a {data_varredura:%d/%m}" if anterior else f"até {data_varredura:%d/%m}"


def escrever_resumo(pasta, novos, retificados, acabando, anterior, data_varredura):
    """resumo-telegram.md: texto puro, links completos (o comando telegram parte em mensagens)."""
    partes = [f"Concursos da semana ({_periodo(anterior, data_varredura)}) · federais e do Paraná", ""]
    partes += ["Novos", ""] + ([_linha(c) for c in novos] or ["• Nenhum concurso novo nesta semana."]) + [""]
    if retificados:
        partes += ["Retificados (o edital mudou)", ""] + [_linha(c) for c in retificados] + [""]
    if acabando:
        partes += ["Inscrições acabando nos próximos 7 dias", ""]
        partes += [f"• {c['orgao']} — até {d.data_curta(c['inscricao']['fim'])} — {ficha_url(c)}" for c in acabando]
        partes.append("")
    partes += [f"Todos os concursos: {d.site_url('/')}",
               "Inscrição e pagamento, só no site da banca. Não somos site oficial."]
    (Path(pasta) / "resumo-telegram.md").write_text("\n".join(partes) + "\n", encoding="utf-8", newline="\n")


def escrever_whatsapp(pasta, novos, retificados, acabando, anterior, data_varredura):
    """resumo-whatsapp.txt: curto, para colar no canal. Só *negrito*, que o WhatsApp lê; nada de outro markdown."""
    def item(c):
        return f"• {c['orgao']}: {_salario(c)}, {_prazo(c)}\n{ficha_url(c)}"
    partes = [f"*Concursos da semana* ({_periodo(anterior, data_varredura)})", "Federais e do Paraná", ""]
    partes += ["*Novos*"] + ([item(c) for c in novos] or ["Nenhum concurso novo nesta semana."]) + [""]
    if retificados:
        partes += ["*Edital retificado*"] + [item(c) for c in retificados] + [""]
    if acabando:
        partes += ["*Acabando em 7 dias*"] + [f"• {c['orgao']}: até {d.data_curta(c['inscricao']['fim'])}\n{ficha_url(c)}" for c in acabando] + [""]
    partes += [f"Todos: {d.site_url('/')}", "Inscrição e pagamento, só no site da banca."]
    (Path(pasta) / "resumo-whatsapp.txt").write_text("\n".join(partes) + "\n", encoding="utf-8", newline="\n")


def escrever_posts(pasta, concursos, data_varredura):
    """posts/post-<id>.png (1080x1350, layout do PostSocial) e a legenda em posts/post-<id>.txt."""
    from gerador import imagens, modelo   # Pillow e a fonte só para quem gera os posts

    saida = Path(pasta) / "posts"
    saida.mkdir(parents=True, exist_ok=True)
    rodape = d.site_url("/").split("://", 1)[1].rstrip("/")
    municipios = d.municipios()
    for c in concursos:
        x = modelo.Concurso(c, data_varredura, municipio=municipios.get(c["municipio_ibge"]))
        imagens.salvar_png(imagens.post_concurso(x, rodape), saida / f"post-{c['id']}.png")
        legenda = [f"{c['orgao']}", f"Salário inicial: {_salario(c)}", f"{_cargo(c)} · {x.vagas.lower()}",
                   f"{_prazo(c).capitalize()} · {_lugar(c)}", "", f"Ficha e edital oficial: {ficha_url(c)}",
                   "Inscrição e pagamento, só no site da banca."]
        (saida / f"post-{c['id']}.txt").write_text("\n".join(legenda) + "\n", encoding="utf-8", newline="\n")
