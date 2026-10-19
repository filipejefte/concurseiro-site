"""Testes do gerador do site: páginas, conteúdo no HTML, links, canonical, sitemap e indexação."""
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
        if "Endereço novo" in html:
            continue   # páginas de redirecionamento: sempre noindex
        assert '<meta name="robots" content="noindex, nofollow">' in html, arquivo
    assert "Disallow: /" in (fechado.saida / "robots.txt").read_text(encoding="utf-8")
    assert "X-Robots-Tag: noindex" in (fechado.saida / "_headers").read_text(encoding="utf-8")
    for arquivo, html in _todas(aberto).items():
        assert "noindex, nofollow" not in html or "Endereço novo" in html, arquivo
    robots = (aberto.saida / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow" not in robots and "Sitemap: https://filipejefte.github.io/concurseiro-site/sitemap.xml" in robots


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
    assert {"/estado/pr/", "/federais/", "/previstos/", "/encerram-esta-semana/", "/concursos/", "/"} <= caminhos
    assert {"/sobre/", "/como-conferimos/", "/privacidade/", "/termos/", "/contato/", "/alertas/"} <= caminhos
    assert (site.saida / "404.html").exists()


def test_cidade_so_com_concurso_na_cidade_ou_a_50_km(site):
    from gerador.modelo import distancia
    b = site.base
    locais = [x for x in b.ativos if x.no_pr and x.municipio]
    for g in b.cidades.values():
        m = g.extra["municipio"]
        assert any(x.municipio["ibge"] == m["ibge"] or distancia(m, x.municipio) <= 50 for x in locais)
    assert "curitiba" in b.cidades or not any(x.municipio and x.municipio["nome"] == "Curitiba" for x in locais)


def test_enderecos_antigos_redirecionam(site):
    for antigo in ("concurso.html", "cidade.html", "concursos.html", "cidade-maringa.html"):
        html = (site.saida / antigo).read_text(encoding="utf-8")
        assert 'content="noindex' in html and "location.replace" in html and "Ir para o endereço novo" in html


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
    fora = [x for x in site.base.concursos if x.federal and not x.no_pr]
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


def test_redirecionamento_do_github_pages(tmp_path):
    from gerador.redirecionar import gerar
    pasta = gerar(tmp_path / "r", "https://concurseiro.example", "/concurseiro-site/")
    html = (pasta / "404.html").read_text(encoding="utf-8")
    assert '"/concurseiro-site/"' in html and '"https://concurseiro.example"' in html and "noindex" in html
    assert (pasta / "index.html").read_text(encoding="utf-8") == html


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
