"""Publicação.

publicar_semana: leva para dados/concursos.json só os concursos com todos os campos críticos conferidos
no revisao.csv e atualiza as datas da varredura. Escreve na pasta da semana:
  resumo-telegram.md    o que o comando `python -m varredura telegram` posta no canal;
  resumo-whatsapp.txt   o mesmo resumo, curto, para colar no canal do WhatsApp;
  posts/post-<id>.png   imagem 1080x1350 de cada concurso novo, com a legenda em post-<id>.txt (fora do git).
O site sai de dados/concursos.json no próximo `python -m gerador build` (o deploy roda sozinho no push).
"""
import re
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
    d.ANO_REFERENCIA = data_varredura.year
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
    base["fontes"] = fontes_da_semana(pasta)
    d.gravar_json(d.CONCURSOS, base)
    novos, retificados, acabando = _grupos(base, aprovados, r.alterados, data_varredura)
    escrever_resumo(pasta, novos, retificados, acabando, anterior, data_varredura)
    abertos = [c for c in base["concursos"] if d.situacao(c, data_varredura) in ("aberto", "breve")]
    escrever_whatsapp(pasta, novos, acabando, abertos, data_varredura)
    if posts and novos:
        escrever_posts(pasta, [publicados[c["id"]] for c in novos], data_varredura)
    return aprovados, recusados


def fontes_da_semana(pasta):
    """O que a varredura leu, para a faixa de atualização e para /como-conferimos/ (vai em dados/concursos.json, chave "fontes").

    dou, amp, dioe: "ok", "parcial" (leu o que pôde, e o aviso diz o que faltou) ou "falhou"; bancas: as que foram lidas;
    dou_dias_sem_acesso: dias úteis do DOU que não vieram; municipios_sem_fonte: municípios do PR que nem a AMP nem
    uma banca trouxeram (dados/cobertura-municipios.csv)."""
    registro = d.ler_json(Path(pasta) / "atos.json") if (Path(pasta) / "atos.json").exists() else {}
    estados = registro.get("fontes", {})

    def estado(nome):
        e = estados.get(nome, "")
        return "ok" if e == "ok" else "parcial" if e.startswith("ok, mas") else "falhou" if e else "nao_lida"
    faltando = re.search(r"(\d+) dia\(s\)", estados.get("DOU", ""))
    saida = {"dou": estado("DOU"), "amp": estado("AMP-PR"), "dioe": estado("DIOE-PR"),
             "bancas": sorted(registro.get("bancas_lidas", {})), "dou_dias_sem_acesso": int(faltando.group(1)) if faltando else 0}
    cobertura = Path(d.DADOS) / "cobertura-municipios.csv"
    if cobertura.exists():
        import csv
        with cobertura.open(encoding="utf-8-sig", newline="") as f:
            saida["municipios_sem_fonte"] = sum(1 for linha in csv.DictReader(f, delimiter=";") if linha["fonte"] == "nenhuma")
    return saida


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
    """resumo-telegram.md: links completos; **negrito** só na linha de notícia e nos títulos (o comando telegram
    converte para a Bot API e parte em mensagens)."""
    partes = [f"**{len(novos)} concurso{'s' if len(novos) != 1 else ''} novo{'s' if len(novos) != 1 else ''} nesta semana** "
              f"({_periodo(anterior, data_varredura)}) · federais e do Paraná", ""]
    partes += ["**Novos**", ""] + ([_linha(c) for c in novos] or ["• Nenhum concurso novo nesta semana."]) + [""]
    if retificados:
        partes += ["**Edital retificado**", ""] + [_linha(c) for c in retificados] + [""]
    if acabando:
        partes += ["**Encerram em até 7 dias**", ""]
        partes += [f"• {c['orgao']} — até {d.data_curta(c['inscricao']['fim'])} — {ficha_url(c)}" for c in acabando]
        partes.append("")
    partes += [f"Todos os concursos: {d.site_url('/')}",
               "Inscrição e pagamento, só no site da banca. Não somos site oficial."]
    (Path(pasta) / "resumo-telegram.md").write_text("\n".join(partes) + "\n", encoding="utf-8", newline="\n")


LIMITE_WHATSAPP = 4000   # caracteres: o resumo cabe numa mensagem do canal
MAX_NOVOS_WHATSAPP = 10


def _ordem_whatsapp(c, data_varredura):
    """Abertos com salário primeiro, por prazo; depois abertos sem salário; depois previstos."""
    sit = d.situacao(c, data_varredura)
    tem_salario = any(k["salario"] is not None for k in c["cargos"])
    grupo = 0 if sit in ("aberto", "breve") and tem_salario else 1 if sit in ("aberto", "breve") else 2
    return (grupo, c["inscricao"]["fim"] or "9999-12-31", c["orgao"])


def escrever_whatsapp(pasta, novos, acabando, abertos, data_varredura):
    """resumo-whatsapp.txt, para colar no canal. Só *negrito*, que o WhatsApp lê; nada de outro markdown.

    A primeira linha traz a contagem da semana e o link do site: é dela que o WhatsApp tira a prévia com a
    imagem da marca. Depois, até 10 concursos novos (abertos com salário primeiro, por prazo), os que encerram
    em 7 dias e o link de todos. Fica abaixo de 4.000 caracteres: o que não cabe vira "e mais N no site"."""
    site = d.site_url("/")
    n = len(novos)
    topo = (f"*{n} concurso{'s' if n != 1 else ''} novo{'s' if n != 1 else ''} nesta semana* · "
            f"{len(abertos)} com inscrição aberta: {site}")
    lista = sorted(novos, key=lambda c: _ordem_whatsapp(c, data_varredura))
    def item(c):
        return f"• {c['orgao']}: {_salario(c)}, {_prazo(c)}\n{ficha_url(c)}"
    def item_acabando(c):
        return f"• {c['orgao']}: até {d.data_curta(c['inscricao']['fim'])}\n{ficha_url(c)}"
    def montar(n_novos, n_acabando):
        partes = [topo, "Federais e do Paraná", ""]
        if lista:
            partes += ["*Novos*"] + [item(c) for c in lista[:n_novos]]
            if len(lista) > n_novos:
                partes.append(f"e mais {len(lista) - n_novos} no site")
            partes.append("")
        if acabando:
            partes += ["*Encerram em até 7 dias*"] + [item_acabando(c) for c in acabando[:n_acabando]]
            if len(acabando) > n_acabando:
                partes.append(f"e mais {len(acabando) - n_acabando} no site")
            partes.append("")
        partes += [f"Todos os concursos: {site}", "Inscrição e pagamento, só no site da banca."]
        return "\n".join(partes) + "\n"
    n_novos, n_acabando = min(MAX_NOVOS_WHATSAPP, len(lista)), len(acabando)
    texto = montar(n_novos, n_acabando)
    while len(texto) >= LIMITE_WHATSAPP and (n_acabando or n_novos):
        if n_acabando > 5 or not n_novos:
            n_acabando -= 1
        else:
            n_novos -= 1
        texto = montar(n_novos, n_acabando)
    (Path(pasta) / "resumo-whatsapp.txt").write_text(texto, encoding="utf-8", newline="\n")
    return texto


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
        (saida / f"post-{c['id']}.txt").write_text(legenda_post(c, x) + "\n", encoding="utf-8", newline="\n")


def legenda_post(c, x):
    """Legenda no formato do voz.md: "Prefeitura de Vale Verde (PR) abriu concurso para agente administrativo:
    R$ 4.218,50 iniciais, 120 vagas, nível médio. Inscrições até sex, 20/11, só no site da banca. ..." """
    cargos = x.cargos
    para = ""
    if cargos:
        para = " para " + cargos[0]["nome"][:1].lower() + cargos[0]["nome"][1:]
        if len(cargos) > 1:
            para += f" e mais {len(cargos) - 1} cargo{'s' if len(cargos) > 2 else ''}"
    dados_ = []
    if x.salario:
        dados_.append(f"{x.salario} iniciais")
    if cargos:
        dados_.append(x.vagas[:1].lower() + x.vagas[1:])
    if x.niveis:
        dados_.append(("nível " if len(x.niveis) == 1 else "níveis ") + x.escolaridade.lower())
    frase = f"{c['orgao']} abriu concurso{para}" + (": " + ", ".join(dados_) if dados_ else "") + "."
    if x.fim:
        frase += f" Inscrições até {d.data_curta(x.fim)}, só no site da banca."
    return frase + " Ficha completa e alerta grátis no link da bio.\n\n" + ficha_url(c)
