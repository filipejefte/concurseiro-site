"""Gera o site estático em public/ a partir de dados/concursos.json e do site.toml.

python -m gerador build [--saida public] [--hoje AAAA-MM-DD] [--exemplo] [--plataforma github|cloudflare]
"""
import hashlib
import json
import re
import shutil
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

from varredura import dados as d

from . import config as configuracao
from . import imagens, modelo
from .modelo import ABERTAS, plural

RAIZ = configuracao.RAIZ
SAIDA = RAIZ / "public"
PREVIA = RAIZ / "previa"        # build --previa: fora do git e nunca publicado
MARCA = RAIZ / "docs" / "marca"
ASSETS = RAIZ / "assets"
MARCADOR = ".gerado-pelo-concurseiro"
FONTE = "assets/fonts/schibsted-grotesk-latin-wght-normal.woff2"
TEXTOS_ATUALIZADOS = "2026-10-16"   # data da última mudança nas páginas institucionais (lastmod do sitemap)
FUSO = timezone(timedelta(hours=-3))  # Brasília, sem horário de verão desde 2019

MENU = [("Concursos abertos", "/concursos/"), ("Federais", "/federais/"), ("Paraná", "/estado/pr/"), ("Previstos", "/previstos/")]
RODAPE = [("Sobre", "/sobre/"), ("Como conferimos os dados", "/como-conferimos/"), ("Alertas", "/alertas/"),
          ("Política de privacidade", "/privacidade/"), ("Termos de uso", "/termos/"), ("Contato", "/contato/"),
          ("Encerram esta semana", "/encerram-esta-semana/")]
NA_AREA = {"Administrativa": "na área administrativa", "Saúde": "na área da saúde", "Educação": "na área da educação",
           "Operacional": "na área operacional", "Policial e segurança": "na área policial e de segurança",
           "Jurídica": "na área jurídica", "Bancária": "na área bancária", "Outras": "em outras áreas"}
INSTITUCIONAIS = [
    ("/sobre/", "sobre.html", "Sobre o Concurseiro"),
    ("/como-conferimos/", "como-conferimos.html", "Como conferimos os dados"),
    ("/privacidade/", "privacidade.html", "Política de privacidade"),
    ("/termos/", "termos.html", "Termos de uso"),
    ("/contato/", "contato.html", "Contato"),
    ("/alertas/", "alertas.html", "Alertas de concurso"),
]


def hoje_brasilia():
    return datetime.now(FUSO).date()


@dataclass
class Pagina:
    path: str
    template: str
    title: str
    description: str
    tipo: str
    contexto: dict = field(default_factory=dict)
    trilha: list = field(default_factory=list)
    og_image: str = "/og/padrao.png"
    og_alt: str = "Concurseiro: concursos federais e do Paraná, com o salário na frente"
    og_type: str = "website"
    sitemap: bool = True
    indexavel: bool = True      # False: noindex mesmo com indexar = true (e fora do sitemap)
    lastmod: str = None
    h1: str = None
    alerta: str = None          # contexto da folha "Avise-me" ("em Maringá", "na área da saúde")
    canonical: str = None
    jsonld: list = field(default_factory=list)


class Site:
    def __init__(self, cfg, base, hoje, saida=SAIDA, plataforma="github", exemplo=False):
        self.cfg, self.hoje, self.saida, self.plataforma = cfg, hoje, Path(saida), plataforma
        d.ANO_REFERENCIA = hoje.year   # "sex, 20/11" sem ano; data de outro ano leva o ano
        self.base = base
        self.exemplo = exemplo
        self.paginas = []
        self.env = Environment(loader=FileSystemLoader(Path(__file__).with_name("templates")),
                               autoescape=select_autoescape(["html", "xml"]), undefined=StrictUndefined,
                               trim_blocks=False, lstrip_blocks=False)
        self.anuncios = bool(cfg.adsense_client)
        self.env.globals.update(u=cfg.url, cfg=cfg, anuncios=self.anuncios, dinheiro=modelo.dinheiro,
                                data_curta=d.data_curta, plataforma=plataforma)

    # ---------- arquivos estáticos ----------

    def limpar(self):
        if self.saida.exists():
            if not (self.saida / MARCADOR).exists() and any(self.saida.iterdir()):
                raise SystemExit(f"{self.saida} existe e não foi gerada pelo gerador; apague à mão se for o caso.")
            shutil.rmtree(self.saida)
        self.saida.mkdir(parents=True)
        (self.saida / MARCADOR).write_text("public/ é apagada e refeita a cada build.\n", encoding="utf-8")
        (self.saida / ".nojekyll").write_text("", encoding="utf-8")   # GitHub Pages: publica _headers e afins como estão

    def _com_hash(self, destino, conteudo):
        """Grava assets/<nome>-<hash>.<ext> (cache longo no Cloudflare) e devolve o caminho público."""
        h = hashlib.sha1(conteudo.encode() if isinstance(conteudo, str) else conteudo).hexdigest()[:10]
        nome = Path(destino)
        final = nome.with_name(f"{nome.stem}-{h}{nome.suffix}")
        alvo = self.saida / final
        alvo.parent.mkdir(parents=True, exist_ok=True)
        (alvo.write_text(conteudo, encoding="utf-8", newline="\n") if isinstance(conteudo, str) else alvo.write_bytes(conteudo))
        return "/" + final.as_posix()

    def estaticos(self):
        css = "\n".join((ASSETS / "css" / n).read_text(encoding="utf-8") for n in ("tokens.css", "componentes.css", "site.css"))
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)            # sem comentários
        css = re.sub(r"\s*\n\s*", "\n", css).strip() + "\n"        # sem linhas em branco nem recuo
        # O tokens.css aponta a fonte por caminho relativo à pasta css/; no arquivo único continua valendo.
        self.ativos = {
            "css": self._com_hash("assets/css/concurseiro.css", css),
            "js": self._com_hash("assets/js/app.js", (ASSETS / "js" / "app.js").read_text(encoding="utf-8")),
            "fonte": "/" + FONTE,
        }
        (self.saida / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / FONTE, self.saida / FONTE)
        favicon = MARCA / "favicon.svg" if (MARCA / "favicon.svg").exists() else ASSETS / "img" / "favicon.svg"
        shutil.copy2(favicon, self.saida / "favicon.svg")
        for lado, nome in ((180, "apple-touch-icon.png"), (192, "icone-192.png"), (512, "icone-512.png")):
            imagens.salvar_png(imagens.icone_app(lado, opaco=nome.startswith("apple")), self.saida / nome)
        self.marca = {"logotipo": None, "palavra": None}
        for chave, nome in (("logotipo", "logotipo-concurseiro"), ("palavra", "logotipo-concurseiro-palavra")):
            origem = next((MARCA / f"{nome}{ext}" for ext in (".svg", ".png") if (MARCA / f"{nome}{ext}").exists()), None)
            if origem:
                arquivo = origem.name
                destino = self.saida / "assets" / "marca" / arquivo
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origem, destino)
                largura, altura = _medidas_svg(origem) if origem.suffix == ".svg" else imagens.Image.open(origem).size
                alvo = 32 if chave == "logotipo" else 24
                self.marca[chave] = f"/assets/marca/{arquivo}"
                self.marca[chave + "_largura"] = round(largura * alvo / altura)
                self.marca[chave + "_altura"] = alvo
        manifest = {
            "name": "Concurseiro", "short_name": "Concurseiro", "lang": "pt-BR",
            "description": "Concursos federais e do Paraná com inscrição aberta, com o salário na frente.",
            "start_url": self.cfg.base_path, "scope": self.cfg.base_path, "display": "standalone",
            "background_color": "#f7f6f1", "theme_color": "#f7f6f1",
            "icons": [{"src": self.cfg.url(f"/icone-{n}.png"), "sizes": f"{n}x{n}", "type": "image/png"} for n in (192, 512)],
        }
        self._gravar("site.webmanifest", json.dumps(manifest, ensure_ascii=False, indent=2))

    def _gravar(self, relativo, texto):
        alvo = self.saida / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8", newline="\n")

    # ---------- contexto comum ----------

    def faixa(self):
        b = self.base
        cobertura = "concursos federais e do Paraná"
        if b.previa:
            return (f"Prévia, não publicada: inclui as fichas da varredura de {d.data_br(b.previa)} ainda sem conferência. "
                    "Só para olhar; o site no ar sai do python -m gerador build sem --previa.")
        if not b.varredura:
            return f"A primeira varredura ainda não foi publicada · {cobertura}"
        texto = f"Atualizado em {d.data_br(b.varredura)}"
        if b.proxima:
            texto += f" · próxima varredura em {d.data_br(b.proxima)}"
        return texto + f" · {cobertura}"

    def canais(self):
        c = self.cfg
        lista = []
        if c.canal_whatsapp:
            lista.append({"nome": "WhatsApp", "url": c.canal_whatsapp, "icone": "conversa"})
        if c.canal_telegram:
            lista.append({"nome": "Telegram", "url": c.canal_telegram, "icone": "aviao"})
        return lista

    def alerta(self, contexto):
        canais = self.canais()
        alvo = f"concurso {contexto}" if contexto else "concurso"
        titulo = f"Avise-me de {alvo}" if canais or self.cfg.kit_form_id else "Alertas em breve"
        nomes = " ou ".join(k["nome"] for k in canais)
        texto = (f"Os concursos novos de cada semana e as inscrições que estão acabando{', ' + contexto if contexto else ''}"
                 + (f", pelo canal do {nomes}" if nomes else "") + ". Sem cadastro no site.")
        if contexto and canais:
            texto += f" O canal traz todos os concursos da semana; os {contexto} vêm marcados com a cidade e a área."
        return {"titulo": titulo, "texto": texto}

    def render(self, p: Pagina):
        p.canonical = p.canonical if p.canonical is not None else self.cfg.absoluta(p.path)
        if p.trilha and p.tipo not in ("inicio",):
            p.jsonld = p.jsonld + [{
                "@context": "https://schema.org", "@type": "BreadcrumbList",
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": nome, "item": self.cfg.absoluta(caminho)}
                                    for i, (nome, caminho) in enumerate(p.trilha)],
            }]
        contexto = dict(
            pagina=p, base=self.base, faixa=self.faixa(), menu=MENU, rodape=RODAPE, ativos=self.ativos, marca=self.marca,
            robots=("noindex, nofollow" if not self.cfg.indexar or self.base.previa
                    else "index, follow" if p.indexavel else "noindex, follow"),
            canais=self.canais(), alerta=self.alerta(p.alerta),
            config_js={"base": self.cfg.base_path, "hoje": self.hoje.isoformat(), "localIP": self.plataforma == "cloudflare",
                       "adsense": self.cfg.adsense_client or None},
            **p.contexto,
        )
        html = self.env.get_template(p.template).render(**contexto)
        html = re.sub(r"\n\s*\n+", "\n", html)   # sem linhas em branco: HTML menor, mesmo conteúdo
        arquivo = "404.html" if p.path == "/404.html" else p.path.strip("/") + "/index.html" if p.path != "/" else "index.html"
        self._gravar(arquivo, html)
        self.paginas.append(p)

    # ---------- páginas ----------

    def gerar(self):
        self.limpar()
        self.estaticos()
        b = self.base
        areas_nomes = d.ler_json(d.SCHEMA)["properties"]["area"]["enum"]
        self.areas = b.areas(areas_nomes)
        self.bancas = b.bancas()
        self.slugs_banca = {g.slug for g in self.bancas}
        self.pagina_inicio()
        self.pagina_concursos(areas_nomes)
        for x in b.concursos:
            self.pagina_ficha(x)
        self.paginas_listas()
        self.paginas_institucionais()
        self.redirecionamentos()
        self.dados_js()
        self.imagens_og()
        self.sitemap_robots()
        return self.paginas

    def _ano(self):
        return str(self.hoje.year)

    def pagina_inicio(self):
        b = self.base
        n = len(b.abertos)
        destaque = [x for x in b.abertos][:6]
        cidades = sorted(b.cidades.values(), key=lambda g: (-len(g.concursos), g.slug))
        self.render(Pagina(
            "/", "inicio.html",
            title="Concursos abertos federais e do Paraná, com o salário na frente · Concurseiro",
            description=(f"{plural(n, 'concurso', 'concursos')} com inscrição aberta: federais de todo o Brasil e do Paraná, "
                         f"com salário, prazo e o link do edital oficial."
                         + (f" Atualizado em {d.data_br(b.varredura)}." if b.varredura else "")),
            tipo="inicio",
            jsonld=[{"@context": "https://schema.org", "@type": "WebSite", "name": "Concurseiro", "inLanguage": "pt-BR",
                     "url": self.cfg.absoluta("/"),
                     "potentialAction": {"@type": "SearchAction",
                                         "target": {"@type": "EntryPoint", "urlTemplate": self.cfg.absoluta("/concursos/") + "?q={search_term_string}"},
                                         "query-input": "required name=search_term_string"}}],
            contexto=dict(n_abertos=plural(n, "concurso", "concursos"), n_previstos=len(b.previstos), destaque=destaque,
                          areas=self.areas, federais=b.federais(), cidades_destaque=[g for g in cidades if g.concursos][:12]),
            lastmod=b.varredura,
        ))

    def pagina_concursos(self, areas_nomes):
        b = self.base
        n = len(b.abertos)
        rotulos = {"areas": {modelo.slug(a): a for a in areas_nomes},
                   "bancas": {g.slug: g.nome for g in self.bancas if any(x.ativo for x in g.concursos)},
                   "niveis": modelo.NIVEIS}
        self.render(Pagina(
            "/concursos/", "concursos.html",
            title=f"Concursos abertos em {self._ano()}: {plural(n, 'concurso', 'concursos')} federais e do Paraná · Concurseiro",
            description=(f"Lista de {plural(n, 'concurso', 'concursos')} com inscrição aberta, federais e do Paraná, com salário inicial, "
                         "vagas, prazo e o link do edital oficial. Busque por cargo, órgão ou cidade."),
            tipo="concursos", trilha=[("Início", "/"), ("Concursos abertos", "/concursos/")],
            contexto=dict(n_abertos=plural(n, "concurso", "concursos"), areas=self.areas, rotulos=rotulos),
            lastmod=b.varredura,
        ))

    def pagina_ficha(self, x):
        b, cfg = self.base, self.cfg
        c = x.c
        endereco = cfg.absoluta(x.path)
        principal = x.cargos[0] if x.cargos else None
        ben = c["beneficios"][0] if c["beneficios"] else None
        detalhe = " · ".join(t for t in [
            principal and principal["nome"],
            ben and ("+ " + modelo.minuscula(ben["nome"]) + (f" de {modelo.dinheiro(ben['valor'])}" if ben["valor"] else "")),
        ] if t)
        origem = [x.ato["titulo"]] if x.ato else []
        if x.retificado:
            origem.append(f"retificado em {d.data_curta(x.retificado['publicado_em'])}")
        origem += [x.conferido] + ([x.fonte] if x.ato else [])
        mensagem = " · ".join(t for t in [
            f"Olha esse concurso: {x.orgao}",
            ("até " if x.sal_min != x.sal_max else "") + modelo.dinheiro(x.sal_max) if x.sal_max else None,
            f"inscrições {x.resumo_inscricao}",
        ] if t) + "\n" + endereco
        prazos = self._prazos(x)
        avise = (f' Viu um erro nesta ficha? <a class="pt-link" href="{escape(_mailto(cfg.email_contato, x.id, endereco))}">Avise a gente</a>.'
                 if cfg.email_contato else " Viu um erro nesta ficha? Avise a gente: [A PREENCHER: e-mail de contato].")
        trilha = [("Início", "/")]
        if x.no_pr:
            trilha.append(("Paraná", "/estado/pr/"))
            if x.cidade_slug:
                trilha.append((x.c["cidade"], f"/cidade/{x.cidade_slug}/"))
        elif x.federal:
            trilha.append(("Federais", "/federais/"))
        trilha.append((x.orgao_curto, x.path))
        self.render(Pagina(
            x.path, "ficha.html", title=x.title, description=x.description, tipo="concurso", trilha=trilha,
            og_image=x.og, og_alt=f"{x.orgao}: {x.salario or 'salário não informado'}", og_type="article",
            sitemap=b.no_sitemap(x), lastmod=c.get("ultima_alteracao") or b.varredura,
            alerta=(f"em {c['cidade']}" if x.no_pr and c["cidade"] else NA_AREA.get(x.area)),
            contexto=dict(
                x=x, detalhe=detalhe, origem=" · ".join(origem), prazos=prazos, ics=_ics(x, prazos, endereco) if prazos else None,
                whatsapp="https://wa.me/?text=" + urllib.parse.quote(mensagem),
                materias=[k for k in x.cargos if k["materias"]], parceiros=self._parceiros(x.area, x.banca_slug),
                site_banca=(c["inscricao"]["url"] or c["banca"]["url"]) if x.banca else None,
                avise=avise, fim_br=d.data_br(x.fim), tem_banca=x.banca_slug in self.slugs_banca,
                info_cargo=_info_cargo, sub_documento=_sub_documento,
                ficha_js={"id": x.id, "orgao": x.orgao, "prova": c["prova_objetiva"], "fim": x.fim,
                          "cargos": [[k["nome"], k["escolaridade"], k["requisitos"]] for k in x.cargos]},
            ),
        ))

    def _prazos(self, x):
        c, hoje = x.c, self.hoje.isoformat()
        p = []
        if x.inicio and x.inicio > hoje:
            p.append(("inicio", x.inicio, "Abrem as inscrições"))
        if c["isencao_ate"] and c["isencao_ate"] >= hoje:
            p.append(("isencao", c["isencao_ate"], "Último dia para pedir isenção da taxa"))
        if x.fim and x.fim >= hoje:
            p.append(("fim", x.fim, "Último dia de inscrição"))
        if c["prova_objetiva"] and c["prova_objetiva"] >= hoje:
            p.append(("prova", c["prova_objetiva"], "Prova objetiva"))
        saida = []
        for chave, dia, nome in p:
            inicio = dia.replace("-", "")
            fim = (d.data(dia) + timedelta(days=1)).strftime("%Y%m%d")
            detalhes = (f"Edital oficial: {x.ato['url']}\n" if x.ato else "") + \
                f"Ficha: {self.cfg.absoluta(x.path)}\nConfira sempre o edital: as datas mudam com retificação."
            google = ("https://calendar.google.com/calendar/render?action=TEMPLATE&text=" + urllib.parse.quote(f"{nome}: {x.orgao}")
                      + f"&dates={inicio}/{fim}&details=" + urllib.parse.quote(detalhes))
            saida.append({"chave": chave, "data": dia, "nome": nome, "google": google, "detalhes": detalhes})
        return saida

    def _parceiros(self, area=None, banca=None):
        return [a for a in self.cfg.afiliados if (area and a.get("area") == area) or (banca and a.get("banca") == banca)]

    def lista(self, path, title, description, h1, capa, secoes, trilha, intro=None, chips=(), parceiros=(), alerta=None,
              template="lista.html", tipo="lista", sitemap=True, indexavel=True, **extra):
        membros = [x for s in secoes for x in s["concursos"]]
        lastmod = max([x.c.get("ultima_alteracao") or "" for x in membros] + [self.base.varredura or ""]) or None
        self.render(Pagina(path, template, title=title, description=description, tipo=tipo, trilha=trilha, alerta=alerta,
                           sitemap=sitemap and indexavel, indexavel=indexavel, lastmod=lastmod,
                           contexto=dict(lista=dict(h1=h1, capa=Markup(capa), intro=intro, secoes=secoes, chips=list(chips),
                                                    parceiros=list(parceiros)), **extra)))

    @staticmethod
    def _capa(n, resto):
        return f'<span class="cc-grifo">{escape(plural(n, "concurso", "concursos"))}</span> {escape(resto)}'

    def paginas_listas(self):
        b, ano = self.base, self._ano()
        inicio = ("Início", "/")
        # Paraná
        pr = b.estado_pr()
        cidades = sorted(b.cidades.values(), key=lambda g: (-len(g.concursos), g.slug))
        self.lista(
            "/estado/pr/", f"Concursos abertos no Paraná (PR) em {ano}: {plural(len(pr.abertos), 'concurso', 'concursos')} · Concurseiro",
            f"{plural(len(pr.abertos), 'concurso', 'concursos')} com inscrição aberta no Paraná, entre órgãos federais, estaduais e "
            "municipais, com salário, prazo e o link do edital oficial.",
            "Concursos abertos no Paraná", self._capa(len(pr.abertos), "com inscrição aberta no Paraná."),
            [dict(titulo="Inscrições abertas", concursos=pr.abertos, vazio="Nenhum concurso com inscrição aberta no Paraná agora."),
             dict(titulo="Previstos", concursos=pr.previstos, apoio="Autorização ou banca contratada em ato oficial, sem edital ainda.")],
            [inicio, ("Paraná", "/estado/pr/")], alerta="no Paraná",
            chips=[dict(titulo="Cidades com concurso", itens=[(g.nome, f"/cidade/{g.slug}/", len(g.concursos) or None) for g in cidades]),
                   dict(titulo="Por área", itens=[(g.nome, f"/area/{g.slug}/", None) for g in self.areas if g.abertos])],
        )
        # Federais
        fed = b.federais()
        self.lista(
            "/federais/", f"Concursos federais abertos em {ano}: {plural(len(fed.abertos), 'concurso', 'concursos')} · Concurseiro",
            f"{plural(len(fed.abertos), 'concurso federal', 'concursos federais')} com inscrição aberta em todo o Brasil, "
            "com salário, prazo e o link do edital oficial.",
            "Concursos federais abertos", self._capa(len(fed.abertos), "federais com inscrição aberta, em todo o Brasil."),
            [dict(titulo="Inscrições abertas", concursos=fed.abertos, vazio="Nenhum concurso federal com inscrição aberta agora."),
             dict(titulo="Previstos", concursos=fed.previstos, apoio="Autorização ou banca contratada em ato oficial, sem edital ainda.")],
            [inicio, ("Federais", "/federais/")], alerta="federal",
        )
        # Previstos
        self.lista(
            "/previstos/", f"Concursos previstos: {plural(len(b.previstos), 'concurso', 'concursos')} com ato oficial · Concurseiro",
            "Concursos federais e do Paraná com autorização publicada ou banca contratada em ato oficial, ainda sem edital.",
            "Concursos previstos", self._capa(len(b.previstos), "previstos, com ato oficial."),
            [dict(titulo="Previstos", concursos=b.previstos, vazio="Nenhum concurso previsto agora.")],
            [inicio, ("Previstos", "/previstos/")],
            intro=("Previsto quer dizer que há ato oficial de autorização do concurso ou de contratação da banca, mas o edital ainda "
                   "não saiu. Não há data de inscrição nem salário confirmado. Previstos não entram na conta dos concursos abertos."),
        )
        # Encerram esta semana
        self.lista(
            "/encerram-esta-semana/", f"Inscrições que encerram esta semana: {plural(len(b.breve), 'concurso', 'concursos')} · Concurseiro",
            "Concursos federais e do Paraná com inscrição terminando nos próximos 7 dias, com salário e o link do edital oficial.",
            "Inscrições que encerram esta semana", self._capa(len(b.breve), "com inscrição terminando nos próximos 7 dias."),
            [dict(titulo="Encerram nos próximos 7 dias", concursos=b.breve, vazio="Nenhuma inscrição acaba nos próximos 7 dias.")],
            [inicio, ("Encerram esta semana", "/encerram-esta-semana/")],
        )
        # Áreas
        for g in self.areas:
            frase = NA_AREA[g.nome]
            self.lista(
                f"/area/{g.slug}/", f"Concursos abertos {frase}: {plural(len(g.abertos), 'concurso', 'concursos')} · Concurseiro",
                f"Concursos {frase} com inscrição aberta, federais e do Paraná, com salário, vagas, prazo e o link do edital oficial.",
                f"Concursos abertos {frase}", self._capa(len(g.abertos), f"com inscrição aberta {frase}."),
                [dict(titulo="Inscrições abertas", concursos=g.abertos, vazio=f"Nenhum concurso aberto {frase} agora."),
                 dict(titulo="Previstos", concursos=g.previstos)],
                [inicio, ("Concursos abertos", "/concursos/"), (g.nome, f"/area/{g.slug}/")],
                parceiros=self._parceiros(area=g.nome), alerta=frase, sitemap=bool(g.abertos or g.previstos),
            )
        # Bancas
        for g in self.bancas:
            recentes = [x for x in g.encerrados if self.base.no_sitemap(x)]
            self.lista(
                f"/banca/{g.slug}/", f"Concursos da banca {g.nome}: abertos e previstos · Concurseiro",
                f"Concursos organizados por {g.nome}: {plural(len(g.abertos), 'aberto', 'abertos')} e "
                f"{plural(len(g.previstos), 'previsto', 'previstos')}, com salário, prazo e o link do edital oficial.",
                f"Concursos da banca {g.nome}", self._capa(len(g.abertos), "com inscrição aberta."),
                [dict(titulo="Inscrições abertas", concursos=g.abertos, vazio="Nenhum concurso desta banca com inscrição aberta agora."),
                 dict(titulo="Previstos", concursos=g.previstos),
                 dict(titulo="Encerrados há pouco", concursos=recentes)],
                [inicio, ("Concursos abertos", "/concursos/"), (g.nome, f"/banca/{g.slug}/")],
                parceiros=self._parceiros(banca=g.slug), sitemap=bool(g.abertos or g.previstos or recentes),
            )
        # Cidades: todas as que têm concurso ativo a até 50 km (servem ao alerta local). Indexável só com concurso
        # na própria cidade (aberto ou previsto) ou com pelo menos 1 aberto a até 50 km; só previstos vizinhos = noindex.
        for g in b.cidades.values():
            regiao_n = len(g.extra["regiao"])
            proximos = [x for _, x in g.extra["regiao"]]
            areas = {}
            bancas = {}
            for x in g.concursos + proximos:
                areas[x.area] = areas.get(x.area, 0) + 1
                if x.banca_slug:
                    bancas[(x.banca_slug, x.banca)] = bancas.get((x.banca_slug, x.banca), 0) + 1
            self.lista(
                f"/cidade/{g.slug}/",
                f"Concursos abertos em {g.nome} (PR) {self._ano()}: {plural(len(g.abertos), 'concurso', 'concursos')} na cidade e "
                f"{regiao_n} na região · Concurseiro",
                f"Concursos com inscrição aberta em {g.nome} (PR) e a até 50 km: salário, vagas, prazo e o link do edital oficial.",
                f"Concursos em {g.nome} (PR)",
                self._capa(len(g.abertos), f"com inscrição aberta na cidade e mais {regiao_n} abertos ou previstos a até 50 km."),
                [dict(titulo=f"Abertos em {g.nome}", concursos=g.abertos,
                      vazio=f"Não achamos concurso aberto em {g.nome} hoje. Os da região, a até 50 km, estão logo abaixo."),
                 dict(titulo=f"Previstos em {g.nome}", concursos=g.previstos)],
                [inicio, ("Paraná", "/estado/pr/"), (g.nome, f"/cidade/{g.slug}/")],
                chips=[dict(titulo=f"Por área em {g.nome} e região",
                            itens=[(a, f"/area/{modelo.slug(a)}/", n) for a, n in sorted(areas.items(), key=lambda p: -p[1])]),
                       dict(titulo="Bancas com concurso na região",
                            itens=[(nome, f"/banca/{s}/", n) for (s, nome), n in sorted(bancas.items(), key=lambda p: -p[1])])],
                alerta=f"em {g.nome}", template="cidade.html", tipo="cidade", g=g, indexavel=cidade_indexavel(g),
                varredura_br=d.data_br(b.varredura) if b.varredura else d.data_br(self.hoje),
            )

    def paginas_institucionais(self):
        for path, template, h1 in INSTITUCIONAIS:
            self.render(Pagina(path, template, title=f"{h1} · Concurseiro", description=DESCRICOES[path], tipo="texto",
                               trilha=[("Início", "/"), (h1, path)], h1=h1, lastmod=TEXTOS_ATUALIZADOS,
                               contexto=dict(email=self.cfg.email_contato, n_abertos=len(self.base.abertos),
                                             versao_privacidade=d.data_br(TEXTOS_ATUALIZADOS))))
        self.render(Pagina("/alertas/confirme/", "alertas-confirme.html", title="Confirme o seu e-mail · Concurseiro",
                           description="Falta confirmar o e-mail para começar a receber os alertas de concurso.", tipo="texto",
                           h1="Falta só confirmar", sitemap=False, trilha=[("Início", "/"), ("Alertas", "/alertas/"), ("Confirme", "/alertas/confirme/")]))
        self.render(Pagina("/404.html", "404.html", title="Página não encontrada · Concurseiro",
                           description="Esta página não existe ou saiu do ar.", tipo="texto", h1="Página não encontrada",
                           sitemap=False, canonical=""))

    def redirecionamentos(self):
        """Os endereços do protótipo viram páginas pequenas que levam ao endereço novo."""
        b = self.base
        maringa = "/cidade/maringa/" if "maringa" in b.cidades else "/concursos/?perto=4115200"
        regras = {
            "concurso.html": ("/concursos/", "var id = p.get('id'); if (id && /^[a-z0-9-]+$/.test(id)) destino = '/concurso/' + id + '/';", {}),
            "cidade.html": ("/estado/pr/", "var ibge = p.get('ibge'); if (ibge && mapa[ibge]) destino = '/cidade/' + mapa[ibge] + '/';"
                                           " else if (/^[0-9]{7}$/.test(ibge || '')) destino = '/concursos/?perto=' + ibge;",
                            b.cidade_por_ibge),
            "concursos.html": ("/concursos/", "destino = '/concursos/' + location.search;", {}),
            "cidade-maringa.html": (maringa, "", {}),
        }
        modelo_html = self.env.get_template("redireciona.html")
        for arquivo, (padrao, regra, mapa) in regras.items():
            self._gravar(arquivo, modelo_html.render(destino_padrao=padrao, regra=Markup(regra), mapa=mapa))

    def dados_js(self):
        """Dados que o JavaScript busca só quando a pessoa precisa: municípios (cidade, GPS) e cargos (perfil)."""
        b = self.base
        municipios = [[m["ibge"], m["nome"], m["lat"], m["lon"], b.cidade_por_ibge.get(m["ibge"])] + ([1] if m.get("ficticio") else [])
                      for m in sorted(b.municipios.values(), key=lambda m: modelo.slug(m["nome"]))]
        self._gravar("assets/dados/municipios.json", json.dumps(municipios, ensure_ascii=False, separators=(",", ":")))
        cargos = {x.id: [[k["nome"], k["salario"], k["escolaridade"], k["requisitos"]] for k in x.cargos] for x in b.ativos}
        self._gravar("assets/dados/cargos.json", json.dumps(cargos, ensure_ascii=False, separators=(",", ":")))

    def imagens_og(self):
        rodape = self.cfg.site_url.split("://", 1)[1]
        cache = RAIZ / ".cache" / "og"
        cache.mkdir(parents=True, exist_ok=True)
        tarefas = [(x.og, ("concurso", x.id, x.situacao, x.selo, x.orgao, x.salario, x.prazo, x.local, x.vagas, x.banca, rodape),
                    lambda x=x: imagens.og_concurso(x, rodape)) for x in self.base.concursos]
        tarefas.append(("/og/padrao.png", ("padrao", rodape),
                        lambda: imagens.og_padrao("Concursos abertos federais e do Paraná, com o salário na frente",
                                                  "Prazos, vagas e sempre o link do edital oficial.", rodape)))
        for destino, chave, desenhar in tarefas:
            guardada = cache / (imagens.assinatura(*chave, _versao_imagens()) + ".png")
            if not guardada.exists():
                imagens.salvar_png(desenhar(), guardada)
            alvo = self.saida / destino.lstrip("/")
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(guardada, alvo)

    def sitemap_robots(self):
        cfg = self.cfg
        linhas = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for p in self.paginas:
            if not p.sitemap or p.canonical == "":
                continue
            linhas.append(f"  <url><loc>{escape(p.canonical)}</loc>" + (f"<lastmod>{p.lastmod}</lastmod>" if p.lastmod else "") + "</url>")
        linhas.append("</urlset>")
        self._gravar("sitemap.xml", "\n".join(linhas) + "\n")
        if cfg.indexar:
            robots = f"User-agent: *\nAllow: /\n\nSitemap: {cfg.absoluta('/sitemap.xml')}\n"
        else:
            robots = ("# indexar = false no site.toml: fora dos buscadores até os sócios decidirem.\n"
                      "User-agent: *\nDisallow: /\n")
        self._gravar("robots.txt", robots)
        cabecalhos = ["/*", "  X-Content-Type-Options: nosniff", "  Referrer-Policy: strict-origin-when-cross-origin"]
        if not cfg.indexar:
            cabecalhos.append("  X-Robots-Tag: noindex, nofollow")
        for pasta in ("assets/css/*", "assets/js/*", "assets/fonts/*"):
            cabecalhos += [cfg.url("/" + pasta), "  Cache-Control: public, max-age=31536000, immutable"]
        self._gravar("_headers", "\n".join(cabecalhos) + "\n")
        if cfg.adsense_client:
            pub = cfg.adsense_client.replace("ca-", "")
            self._gravar("ads.txt", f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")


def cidade_indexavel(g):
    return bool(g.concursos) or any(x.aberto for _, x in g.extra["regiao"])


DESCRICOES = {
    "/sobre/": "O que é o Concurseiro, o que ele faz e o que não faz: reúne concursos federais e do Paraná a partir de atos oficiais, sem inscrição nem pagamento.",
    "/como-conferimos/": "De onde vêm os dados do Concurseiro, como cada ficha é extraída do ato oficial e conferida antes de ir ao ar, e como pedir correção.",
    "/privacidade/": "Como o Concurseiro trata dados pessoais, conforme a LGPD: sem conta e sem cookie próprio; cidade e perfil ficam só no seu aparelho.",
    "/termos/": "Termos de uso do Concurseiro: como usar a informação, por que vale sempre o edital oficial e como avisar um erro.",
    "/contato/": "Fale com o Concurseiro: correções de ficha, dúvidas e sugestões.",
    "/alertas/": "Receba os concursos novos de cada semana e as inscrições que estão acabando, pelos canais do Concurseiro.",
}


def _versao_imagens():
    """Muda quando o desenho ou a marca mudam: as imagens guardadas no .cache/ deixam de valer."""
    partes = [Path(imagens.__file__).read_bytes()]
    partes += [p.read_bytes() for p in sorted(MARCA.glob("*")) if p.is_file()] if MARCA.exists() else []
    return hashlib.sha1(b"".join(partes)).hexdigest()[:10]


def _medidas_svg(arquivo):
    texto = arquivo.read_text(encoding="utf-8", errors="replace")
    caixa = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', texto)
    if caixa:
        return float(caixa.group(1)), float(caixa.group(2))
    w, h = re.search(r'width="([\d.]+)', texto), re.search(r'height="([\d.]+)', texto)
    return (float(w.group(1)), float(h.group(1))) if w and h else (160.0, 32.0)


def _mailto(email, id_, endereco):
    return f"mailto:{email}?subject=" + urllib.parse.quote(f"Erro na ficha {id_}") + "&body=" + urllib.parse.quote(
        f"Página: {endereco}\n\nO que está errado:\n")


def _info_cargo(k):
    partes = [modelo.texto_vagas_cargo(k), k["requisitos"] or k["escolaridade"], f"{k['jornada_horas']:g} h" if k["jornada_horas"] else None]
    return " · ".join(p for p in partes if p)


def _sub_documento(doc):
    partes = [doc["resumo"], modelo.FONTES.get(doc["fonte"]), f"publicado em {d.data_curta(doc['publicado_em'])}" if doc["publicado_em"] else None]
    return " · ".join(p for p in partes if p)


def _ics(x, prazos, endereco):
    """Prazos em .ics (eventos de dia inteiro), como data: URI no botão de baixar."""
    def txt(t):
        return re.sub(r"([\\;,])", r"\\\1", t).replace("\n", "\\n")
    agora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//concurseiro//prazos//PT", "CALSCALE:GREGORIAN"]
    for p in prazos:
        fim = (d.data(p["data"]) + timedelta(days=1)).strftime("%Y%m%d")
        linhas += ["BEGIN:VEVENT", f"UID:{x.id}-{p['chave']}@concurseiro", f"DTSTAMP:{agora}",
                   f"DTSTART;VALUE=DATE:{p['data'].replace('-', '')}", f"DTEND;VALUE=DATE:{fim}",
                   "SUMMARY:" + txt(f"{p['nome']}: {x.orgao}"), "DESCRIPTION:" + txt(p["detalhes"]), "END:VEVENT"]
    corpo = "\r\n".join(linhas + ["END:VCALENDAR"]) + "\r\n"
    return "data:text/calendar;charset=utf-8," + urllib.parse.quote(corpo)


def carregar_base(exemplo=False, hoje=None, concursos=None, previa=None):
    """Base publicada (e os exemplos fictícios, com --exemplo) já como modelo.Base.

    previa: pasta de uma varredura; as fichas novas e alteradas dela entram por cima do publicado, sem conferência,
    só para olhar o site com o volume real (nunca para publicar)."""
    base = d.ler_json(concursos or d.CONCURSOS)
    if exemplo:
        ex = d.ler_json(d.EXEMPLO)
        base = dict(base, concursos=base["concursos"] + ex["concursos"])
    if previa:
        from varredura.comparar import comparar
        pasta = Path(previa)
        r = comparar([f for f in d.carregar_fichas(pasta) if f.get("concurso")], base, date.fromisoformat(pasta.name))
        por_id = {c["id"]: c for c in base["concursos"]}
        por_id.update({c["id"]: c for c in r.novos + [novo for novo, _ in r.alterados]})
        base = dict(base, concursos=list(por_id.values()))
    resultado = modelo.Base(base, hoje or hoje_brasilia(), d.municipios(exemplo), exemplo=exemplo)
    resultado.previa = Path(previa).name if previa else None
    return resultado


def construir(saida=SAIDA, hoje=None, exemplo=False, plataforma="github", cfg=None, concursos=None, previa=None):
    cfg = cfg or configuracao.ler()
    hoje = hoje or hoje_brasilia()
    site = Site(cfg, carregar_base(exemplo, hoje, concursos, previa), hoje, saida, plataforma, exemplo)
    site.gerar()
    return site
