"""Testes do gerador do site: páginas, conteúdo no HTML, links, canonical, sitemap e indexação."""
import json
import re
import xml.etree.ElementTree as ET
from datetime import date

import pytest

from gerador import config as configuracao
from gerador.build import construir
from gerador.links import verificar
from varredura import dados

DIA = date(2026, 10, 16)


def _cfg(**trocas):
    return configuracao.ler(**trocas)


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """Build com os dados publicados mais os exemplos fictícios (como no desenvolvimento)."""
    saida = tmp_path_factory.mktemp("public")
    return construir(saida, DIA, exemplo=True, cfg=_cfg())


@pytest.fixture(scope="module")
def site_publicado(tmp_path_factory):
    """Build só com o que está em dados/concursos.json, como vai ao ar."""
    saida = tmp_path_factory.mktemp("publicado")
    return construir(saida, DIA, exemplo=False, cfg=_cfg())


def _html(site, caminho):
    arquivo = site.saida / (caminho.strip("/") + "/index.html" if caminho != "/" else "index.html")
    return arquivo.read_text(encoding="utf-8")


def _todas(site):
    return {p: p.read_text(encoding="utf-8") for p in site.saida.rglob("*.html")}


def test_toda_ficha_publicada_vira_pagina(site_publicado):
    base = dados.ler_json(dados.CONCURSOS)
    for c in base["concursos"]:
        html = _html(site_publicado, f"/concurso/{c['id']}/")
        assert f"<h1 class=\"pt-titulo\">{c['orgao']}</h1>" in html


def test_salario_e_prazo_no_html_sem_javascript(site):
    x = site.base.por_id["prefeitura-vale-verde-pr-2026-edital-12"]
    html = _html(site, x.path)
    sem_script = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    assert "9.312,40" in sem_script                 # salário
    assert "sex, 20/11" in sem_script               # fim da inscrição
    assert "Ver edital oficial" in sem_script and x.edital["url"] in sem_script
    assert "189 + CR" in sem_script and "Instituto AOCP" in sem_script
    # o card da listagem também traz salário e prazo no HTML
    lista = re.sub(r"<script.*?</script>", "", _html(site, "/concursos/"), flags=re.S)
    assert "9.312,40" in lista and "sex, 20/11" in lista


def test_title_e_description_da_ficha(site):
    x = site.base.por_id["prefeitura-vale-verde-pr-2026-edital-12"]
    html = _html(site, x.path)
    assert "<title>Concurso Prefeitura de Vale Verde (PR) 2026: salário inicial de R$ 2.140,00 a R$ 9.312,40, " \
           "inscrições até sex, 20/11</title>" in html
    descricao = re.search(r'<meta name="description" content="([^"]+)"', html).group(1)
    assert "189 vagas + cr" in descricao.lower() and "edital oficial" in descricao


def test_previsto_nao_conta_como_aberto(site):
    b = site.base
    assert b.previstos and all(x.situacao == "previsto" for x in b.previstos)
    assert not set(x.id for x in b.previstos) & set(x.id for x in b.abertos)
    capa = re.search(r'<p class="pt-capa"><span class="cc-grifo">([^<]+)</span>', _html(site, "/")).group(1)
    assert capa == f"{len(b.abertos)} concursos"


def test_ordem_salario_e_aberto_primeiro(site):
    abertos = site.base.abertos
    com = [x for x in abertos if x.sal_max is not None]
    sem = [x for x in abertos if x.sal_max is None]
    assert abertos[:len(com)] == com and abertos[len(com):] == sem
    assert [x.fim for x in com] == sorted(x.fim for x in com)


def test_encerrado_mantem_pagina_com_parecidos_e_sai_do_sitemap_depois_de_90_dias(tmp_path):
    site = construir(tmp_path / "p", date(2027, 3, 1), exemplo=True, cfg=_cfg())
    x = site.base.por_id["prefeitura-vale-verde-pr-2026-edital-12"]   # inscrição até 20/11/2026
    assert x.situacao == "encerrado"
    html = _html(site, x.path)
    assert "Encerrado" in html and "Estes estão abertos" in html
    sitemap = (site.saida / "sitemap.xml").read_text(encoding="utf-8")
    assert x.path not in sitemap                     # mais de 90 dias depois do fim
    site2 = construir(tmp_path / "q", date(2026, 12, 1), exemplo=True, cfg=_cfg())
    assert x.path in (site2.saida / "sitemap.xml").read_text(encoding="utf-8")


def test_nenhum_link_vazio_e_links_internos_existem(site):
    for arquivo, html in _todas(site).items():
        assert 'href="#"' not in html, arquivo
    assert verificar(site.saida, site.cfg.base_path) == []


def test_canonical_e_sitemap_batem_com_site_url(site):
    cfg = site.cfg
    for p in site.paginas:
        if p.canonical:
            assert p.canonical.startswith(cfg.site_url + "/")
            html = _html(site, p.path) if p.path != "/404.html" else ""
            if html:
                assert f'<link rel="canonical" href="{p.canonical}">' in html
    raiz = ET.parse(site.saida / "sitemap.xml").getroot()
    locs = [u.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text for u in raiz]
    assert locs and all(loc.startswith(cfg.site_url + "/") for loc in locs)
    assert all(u.find("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod") is not None for u in raiz)


def test_trocar_dominio_e_so_mudar_site_url_e_base_path(tmp_path):
    cfg = _cfg(site_url="https://www.concurseiro.example", base_path="/")
    site = construir(tmp_path / "p", DIA, exemplo=True, cfg=cfg)
    html = _html(site, "/concursos/")
    assert '<link rel="canonical" href="https://www.concurseiro.example/concursos/">' in html
    assert "/concurseiro-site/" not in html
    assert verificar(site.saida, "/") == []


def test_indexar_liga_e_desliga_o_noindex(tmp_path):
    fechado = construir(tmp_path / "f", DIA, cfg=_cfg(indexar=False))
    aberto = construir(tmp_path / "a", DIA, cfg=_cfg(indexar=True))
    for arquivo, html in _todas(fechado).items():
        assert '<meta name="robots" content="noindex, nofollow">' in html, arquivo
    assert "Disallow: /" in (fechado.saida / "robots.txt").read_text(encoding="utf-8")
    assert "X-Robots-Tag: noindex" in (fechado.saida / "_headers").read_text(encoding="utf-8")
    for arquivo, html in _todas(aberto).items():
        assert "noindex, nofollow" not in html, arquivo
    robots = (aberto.saida / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow" not in robots and f"Sitemap: {_cfg().site_url}/sitemap.xml" in robots


def test_nenhuma_pagina_tem_inscreva_se(site):
    for arquivo, html in _todas(site).items():
        assert not re.search(r"inscreva-se|imperd[ií]vel", html, re.I), arquivo


def test_paginas_por_cidade_area_banca_e_estado(site):
    b = site.base
    caminhos = {p.path for p in site.paginas}
    for g in b.cidades.values():
        assert f"/cidade/{g.slug}/" in caminhos
    for x in b.ativos:
        assert f"/area/{x.area_slug}/" in caminhos
        if x.banca_slug:
            assert f"/banca/{x.banca_slug}/" in caminhos
    assert {"/estado/pr/", "/estados/", "/federais/", "/previstos/", "/encerram-esta-semana/", "/concursos/", "/"} <= caminhos
    for e in b.estados():
        assert f"/estado/{e.slug}/" in caminhos and e.extra["uf"] == e.slug.upper()
    assert {"/sobre/", "/como-conferimos/", "/privacidade/", "/termos/", "/alertas/"} <= caminhos
    assert "/contato/" not in caminhos   # sem email_contato no site.toml, não há página de contato
    assert (site.saida / "404.html").exists()


def test_cidade_so_com_concurso_na_cidade_ou_a_50_km(site):
    from gerador.modelo import distancia
    b = site.base
    locais = [x for x in b.ativos if not x.nacional and x.municipio]
    for g in b.cidades.values():
        m = g.extra["municipio"]
        assert any(x.municipio["ibge"] == m["ibge"] or distancia(m, x.municipio) <= 50 for x in locais)
    assert "curitiba-pr" in b.cidades or not any(x.municipio and x.municipio["nome"] == "Curitiba" for x in locais)


def test_imagens_de_compartilhamento(site):
    from PIL import Image
    for x in site.base.concursos:
        img = Image.open(site.saida / x.og.lstrip("/"))
        assert img.size == (1200, 630)
        assert f'content="{site.cfg.absoluta(x.og)}"' in _html(site, x.path)
    assert Image.open(site.saida / "apple-touch-icon.png").size == (180, 180)


def test_jsonld_sem_jobposting(site):
    for arquivo, html in _todas(site).items():
        assert "JobPosting" not in html, arquivo
    assert '"@type": "WebSite"' in _html(site, "/")
    assert '"@type": "BreadcrumbList"' in _html(site, "/concursos/")


def test_sem_ficticio_publicado_nao_tem_aviso_de_exemplo(site_publicado):
    assert not site_publicado.base.tem_ficticio
    for arquivo, html in _todas(site_publicado).items():
        assert "fictício" not in html, arquivo


def test_federal_fora_do_pr_aparece_nos_federais(site):
    fora = [x for x in site.base.concursos if x.federal and x.uf != "PR"]
    assert fora
    html = _html(site, "/federais/")
    assert all(x.orgao in html for x in fora if x.aberto)


def test_anuncio_e_parceiro_so_com_configuracao(tmp_path, site):
    assert not (site.saida / "ads.txt").exists()
    assert "adsbygoogle" not in _html(site, "/concursos/")
    assert "sponsored" not in _html(site, "/area/saude/")
    cfg = _cfg(adsense_client="ca-pub-123", adsense_slot="456",
               afiliados=[{"area": "Saúde", "nome": "Curso X", "url": "https://parceiro.example/x", "descricao": "curso"}])
    com = construir(tmp_path / "c", DIA, exemplo=True, cfg=cfg)
    assert (com.saida / "ads.txt").read_text() == "google.com, pub-123, DIRECT, f08c47fec0942fa0\n"
    area = _html(com, "/area/saude/")
    assert "Link de parceiro" in area and 'rel="sponsored noopener"' in area
    ficha = _html(com, "/concurso/prefeitura-vale-verde-pr-2026-edital-12/")
    assert "Publicidade" in ficha and "data-cookies" in ficha
    # nenhum anúncio colado no botão do edital nem dentro da folha de alerta
    topo = ficha.split('id="salario"')[0]
    assert "adsbygoogle" not in topo
    folha = ficha.split('<dialog id="alerta"')[1].split("</dialog>")[0]
    assert "adsbygoogle" not in folha and "Publicidade" not in folha


def test_email_do_kit_so_com_formulario_configurado(tmp_path, site):
    assert "app.kit.com" not in _html(site, "/alertas/")
    com = construir(tmp_path / "k", DIA, cfg=_cfg(kit_form_id="1234567", canal_telegram="https://t.me/concurseiro_teste"))
    html = _html(com, "/alertas/")
    assert 'action="https://app.kit.com/forms/1234567/subscriptions"' in html
    caixa = re.search(r'<input type="checkbox" name="consentimento"[^>]*>', html).group(0)
    assert "checked" not in caixa and "required" in caixa
    assert "Pronto. Mandamos um e-mail para você confirmar. Os alertas começam depois disso." in html
    assert "https://t.me/concurseiro_teste" in html


def test_cidade_so_com_previstos_vizinhos_fica_fora_do_google(tmp_path):
    from gerador.build import cidade_indexavel
    site = construir(tmp_path / "p", DIA, exemplo=True, cfg=_cfg(indexar=True))
    sitemap = (site.saida / "sitemap.xml").read_text(encoding="utf-8")
    fechadas = [g for g in site.base.cidades.values() if not cidade_indexavel(g)]
    abertas = [g for g in site.base.cidades.values() if g.concursos]
    vizinhas = [g for g in site.base.cidades.values() if not g.concursos and cidade_indexavel(g)]
    assert fechadas and abertas and vizinhas
    for g in fechadas:   # só previstos a até 50 km: a página existe, mas noindex e fora do sitemap
        assert all(x.situacao == "previsto" for _, x in g.extra["regiao"])
        html = _html(site, f"/cidade/{g.slug}/")
        assert '<meta name="robots" content="noindex, follow">' in html
        assert f"/cidade/{g.slug}/<" not in sitemap
    for g in abertas + vizinhas:   # concurso na cidade, ou aberto a até 50 km: indexável
        assert '<meta name="robots" content="index, follow">' in _html(site, f"/cidade/{g.slug}/")
        assert f"/cidade/{g.slug}/<" in sitemap


def test_ficha_de_professor_federal_mostra_rotulo_e_tabela(tmp_path):
    base = dados.ler_json(dados.EXEMPLO)
    c = next(x for x in base["concursos"] if x["id"].startswith("instituto-federal-do-vale"))
    for k in c["cargos"]:
        k["nome"] = "Professor do Magistério Superior – " + k["nome"]
        k["requisitos"] = "dedicação exclusiva; titulação mínima: doutorado"
        k["remuneracao_por_titulacao"] = [{"titulacao": "doutorado", "valor": 13753.96}, {"titulacao": "mestrado", "valor": 9595.78}]
    arquivo = tmp_path / "concursos.json"
    dados.gravar_json(arquivo, dict(base, varredura="2026-10-14", proxima_varredura="2026-10-21", concursos=[c]))
    site = construir(tmp_path / "p", DIA, exemplo=False, cfg=_cfg(), concursos=arquivo)
    html = _html(site, f"/concurso/{c['id']}/")
    assert "Salário inicial bruto (vencimento + retribuição por titulação)" in html
    assert "Remuneração por titulação · dedicação exclusiva" in html and "9.595,78" in html
    assert html.count("Remuneração por titulação ·") == 1   # cargos com a mesma tabela: uma tabela só


def test_contato_e_avise_a_gente_so_com_email_contato(tmp_path, site):
    """Sem email_contato nada de contato aparece, e nada fica como [A PREENCHER] nem como link quebrado."""
    ficha = _html(site, "/concurso/prefeitura-vale-verde-pr-2026-edital-12/")
    assert "Avise a gente" not in ficha and "mailto:" not in ficha
    for arquivo, html in _todas(site).items():
        assert "[A PREENCHER" not in html and 'href="/contato/"' not in html, arquivo
    assert not (site.saida / "contato").exists()
    assert verificar(site.saida, site.cfg.base_path) == []
    com = construir(tmp_path / "c", DIA, exemplo=True, cfg=_cfg(email_contato="contato@exemplo.example"))
    assert (com.saida / "contato" / "index.html").exists()
    assert 'href="/contato/"' in _html(com, "/")
    assert "mailto:contato@exemplo.example?subject=" in _html(com, "/contato/")
    assert "Avise a gente" in _html(com, "/concurso/prefeitura-vale-verde-pr-2026-edital-12/")
    assert verificar(com.saida, com.cfg.base_path) == []
    with pytest.raises(SystemExit):
        _cfg(email_contato="isto não é e-mail")


def test_site_toml_nao_tem_campo_de_pessoa():
    """Regra 11: o site não fala de quem o faz; o site.toml não tem onde pôr isso."""
    for campo in ("responsavel", "quem_faz", "foro", "razao_social", "cnpj"):
        assert campo not in configuracao.Config.__dataclass_fields__
        with pytest.raises(SystemExit):
            _cfg(**{campo: "x"})


def test_privacidade_e_termos_sem_controlador_nem_foro_nem_promessa(site):
    privacidade = _html(site, "/privacidade/")
    for frase in ("controlador", "Respondemos em", "representada por", "pessoa física responsável"):
        assert frase not in privacidade, frase
    assert "limpe os dados do site" in privacidade and "Cloudflare" in privacidade
    assert "GitHub" not in privacidade and ">Anúncios</h2>" not in privacidade   # sem AdSense ligado
    assert "foro" not in _html(site, "/termos/").lower()


def test_previa_junta_fichas_da_semana_e_nunca_indexa(tmp_path):
    pasta = tmp_path / "varreduras" / "2026-10-14"
    base = dados.ler_json(dados.EXEMPLO)
    c = dict(next(x for x in base["concursos"] if x["id"].startswith("prefeitura-vale-verde")), id="previa-teste-pr-2026-edital-01")
    dados.gravar_json(pasta / "fichas" / f"{c['id']}.json", {"ato": "x.md", "trechos": {}, "concurso": c})
    site = construir(tmp_path / "p", DIA, exemplo=True, cfg=_cfg(indexar=True), previa=pasta)
    html = _html(site, f"/concurso/{c['id']}/")
    assert "Prévia, não publicada" in html and '<meta name="robots" content="noindex, nofollow">' in html
    assert "Prévia, não publicada" in _html(site, "/")


def test_previa_nao_vai_para_public(monkeypatch):
    from gerador.__main__ import main
    from gerador import build
    with pytest.raises(SystemExit):
        main(["build", "--previa", "dados/varreduras/2026-10-14", "--saida", str(build.SAIDA)])


def test_faixa_e_como_conferimos_trazem_as_fontes_lidas_e_o_que_falta(tmp_path):
    """A faixa de atualização lista o que a varredura leu; /como-conferimos/ diz o que cada fonte cobre e o que ainda não lemos."""
    base = dados.ler_json(dados.CONCURSOS)
    fontes = {"dou": "parcial", "amp": "ok", "dioe": "ok", "bancas": ["fafipa", "fau", "quadrix"], "dou_dias_sem_acesso": 12,
              "municipios_sem_fonte": 87}
    arquivo = tmp_path / "concursos.json"
    dados.gravar_json(arquivo, dict(base, varredura="2026-10-19", proxima_varredura="2026-10-26", fontes=fontes))
    site = construir(tmp_path / "p", DIA, cfg=_cfg(), concursos=arquivo)
    assert ("Atualizado em seg, 19/10 · lemos o Diário Oficial da União (parcial), o do Paraná, o Diário dos Municípios do PR "
            "e os sites de 3 bancas · próxima varredura em seg, 26/10") in _html(site, "/")
    como = _html(site, "/como-conferimos/")
    assert "faltaram 12 dias úteis do Diário Oficial da União" in como
    assert "Fundação FAFIPA" in como and "Instituto Quadrix" in como and "Instituto Omni" not in como      # só as bancas lidas
    inicio = como.index("O que ainda não lemos")
    assert "87 municípios do Paraná sem nenhuma fonte lida" in como[inicio:] and "Unioeste" in como[inicio:]


def test_sem_a_chave_fontes_o_site_diz_so_o_que_dizia_antes(site_publicado):
    """Varredura publicada antes de existir a chave: DOU e AMP lidos; o diário do Estado e as bancas ficam em "ainda não lemos"."""
    assert "lemos o Diário Oficial da União e o Diário dos Municípios do PR" in _html(site_publicado, "/")
    como = _html(site_publicado, "/como-conferimos/")
    inicio = como.index("O que ainda não lemos")
    assert "Diário Oficial do Estado do Paraná" in como[inicio:] and "Sites das bancas" in como[inicio:]


def test_slug_da_cidade_leva_a_uf_e_o_js_recebe_a_uf(site):
    """São José existe em vários estados: o slug da cidade leva a UF, e a tabela que o JS baixa também."""
    from gerador.modelo import cidade_slug
    assert cidade_slug({"nome": "São José", "uf": "SC"}) == "sao-jose-sc" != cidade_slug({"nome": "São José", "uf": "SP"})
    linhas = json.loads((site.saida / "assets/dados/municipios.json").read_text(encoding="utf-8"))
    assert all(len(l[5]) == 2 and l[5].isupper() for l in linhas)
    assert len({l[0] for l in linhas}) == len(linhas) > 5000       # o Brasil todo, um código por município


def test_pagina_de_estado_so_para_uf_com_concurso(site):
    b = site.base
    ufs = {x.uf for x in b.concursos if not x.nacional}
    assert {e.extra["uf"] for e in b.estados()} == ufs
    html = _html(site, "/estados/")
    assert all(f'/estado/{uf.lower()}/' in html for uf in ufs)
