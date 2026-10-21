"""Leitores das bancas: páginas reais (trechos salvos em tests/dados/bancas/, sem rede) e as regras de cobertura."""
from datetime import date
from pathlib import Path

import pytest

from varredura.fontes import bancas as B

PASTA = Path(__file__).parent / "dados" / "bancas"
HOJE = date(2026, 10, 21)


def ler(nome):
    return (PASTA / nome).read_text(encoding="utf-8")


def leitor(slug):
    return next(l for l in B.LEITORES if l.slug == slug)


def test_fafipa_lista_e_pagina_do_concurso():
    fafipa = leitor("fafipa")
    nomes = [n for n, _ in fafipa.urls_da_lista(ler("fafipa-abertas.html"))]
    assert len(nomes) == 10 and nomes[0] == "Concurso Público do Município de Curitiba - PR (PGM)"
    c = fafipa.concurso(ler("fafipa-concurso-curitiba-pgm.html"), "https://www.fundacaofafipa.org.br/concurso/4216")
    assert (c.orgao, c.uf, c.tipo, c.numero) == ("Município de Curitiba - PR", "PR", "Concurso Público", "6/2026")
    assert (c.inscricao_inicio, c.inscricao_fim, c.prova) == ("2026-10-07", "2026-11-05", "2026-12-13")
    # o edital é o retificado mais recente; o edital de deferimento da isenção não é o edital do concurso
    assert (c.edital.titulo, c.edital.data) == ("Edital Normativo n.º 6/2026 - PM Curitiba - PR - Retificado", "2026-10-16")
    assert c.edital.url.endswith("6167b00f-2ebb-4514-9076-0b2074787714.pdf")
    assert B.dentro_da_cobertura(c) and B.aberto(c, HOJE) and not B.aberto(c, date(2026, 11, 6))


def test_fau_so_os_concursos_em_aberto_e_o_edital_de_abertura():
    fau = leitor("fau")
    itens = fau.itens_da_lista(ler("fau-concursos.html"))
    assert [n for n, _, _ in itens][-1] == "PREFEITURA MUNICIPAL DE APUCARANA - 2026" and len(itens) == 6
    assert all("IMBITUVA" not in n for n, _, _ in itens)          # em andamento, não aberto
    c = fau.concurso(ler("fau-concurso-apucarana.html"), "https://www.concursosfau.com.br/novo/concurso/pma2026", itens[-1][0])
    assert (c.inscricao_inicio, c.inscricao_fim, c.prova, c.uf) == ("2026-10-21", "2026-11-09", "2026-12-06", "PR")
    assert c.edital.titulo == "EDITAL DE ABERTURA" and c.edital.url.endswith("EDITAL_CONCURSO_PUBLICO_APUCARANA-ok.pdf")
    assert B.dentro_da_cobertura(c)


def test_quadrix_e_omni_mesma_plataforma_cobertura_federal_e_parana():
    quadrix = leitor("quadrix")
    itens = quadrix.itens_da_lista(ler("quadrix-abertos.html"))
    assert [i.numero for i in itens] == ["01/2026"] * 5
    assert itens[0].inscricao_inicio == "2026-10-05" and itens[0].inscricao_fim == "2026-11-10"
    assert all(B.dentro_da_cobertura(i) for i in itens)             # conselhos regionais são autarquias federais, em qualquer UF
    crecis = quadrix.completar(itens[0], ler("quadrix-informacoes-3049.html"))
    # o edital atualizado conforme as retificações vale mais que o original e que a "retificação" avulsa
    assert crecis.edital.titulo == "Edital nº 1 (Abertura) - atualizado conforme retificações" and crecis.edital.data == "2026-10-02"
    omni = leitor("omni")
    pss = omni.itens_da_lista(ler("omni-abertos.html"))
    assert len(pss) == 2 and not any(B.dentro_da_cobertura(i) for i in pss)   # processo seletivo de prefeitura de SC
    completo = omni.completar(pss[0], ler("omni-informacoes-52.html"))
    assert completo.edital.titulo == "Edital HSLMV 001/2026 de Abertura" and completo.edital.data == "2026-10-05"   # data do cabeçalho


def test_unicampo_edital_de_abertura_e_prazo():
    unicampo = leitor("unicampo")
    itens = unicampo.itens_da_lista(ler("unicampo-home.html"))
    assert len(itens) == 11 and itens[0].uf == "PR" and itens[0].tipo == "Concurso Público"
    assert (itens[0].inscricao_inicio, itens[0].inscricao_fim, itens[0].prova) == ("2026-09-16", "2026-10-13", "2026-11-08")
    assert not B.aberto(itens[0], HOJE) and B.aberto(itens[0], date(2026, 10, 13))
    assert not B.dentro_da_cobertura(itens[2])                       # "Processo Seletivo de Pessoal PSP - Regime Celetista"
    vere = unicampo.completar(itens[3], ler("unicampo-concurso-vere.html"))
    assert vere.edital.titulo.startswith("Edital Nº 001 - 2026 - Edital de Abertura")      # os editais de correção e de deferimento ficam de fora
    assert ";jsessionid" not in vere.edital.url and vere.edital.url.endswith("edital-n-001-2026-edital-de-abertura-completo-com-anexo")


def test_consulplan_cartoes_cobertura_e_datas_dos_documentos():
    consulplan = leitor("consulplan")
    itens = consulplan.itens_da_lista(ler("consulplan-concursos.html"))
    dentro = [i.titulo for i in itens if B.dentro_da_cobertura(i)]
    assert any(t.startswith("CREMERJ") for t in dentro) and any("CRO/SE" in t for t in dentro)
    assert not any("Prefeitura Municipal" in t or "Câmara Municipal" in t for t in dentro)     # municípios de MG, ES e GO: fora
    assert not any("PASES" in i.tipo for i in itens if B.dentro_da_cobertura(i))              # vestibular seriado da UFV não é concurso
    cremerj = consulplan.completar(next(i for i in itens if "cremerj" in i.pagina), ler("consulplan-cremerj2026.html"))
    assert (cremerj.edital.titulo, cremerj.edital.data) == ("Edital nº 1/2026 - Abertura", "2026-09-18")


@pytest.mark.parametrize("nome,uf", [
    ("Prefeitura Municipal de Verê - Pr.", "PR"), ("Conselho Regional de Química da 9ª Região (CRQ-PR)", "PR"),
    ("Município de Curitiba - PR", "PR"), ("Câmara Municipal de Unaí/MG", "MG"), ("Prefeitura de Altônia -Pr.", "PR"),
    ("Secretaria de Educação do Município", None), ("Conselho de Contabilidade da Bahia", None), ("Caixa de Assistência", None),
])
def test_uf_do_nome(nome, uf):
    assert B.uf_do_nome(nome) == uf


def test_dominios_das_bancas_valem_como_link_de_edital():
    from varredura.validar import _oficial
    c = {"ficticio": False, "banca": {"url": None}}
    for dominio in B.TODOS_OS_DOMINIOS:
        assert _oficial(f"https://anexos.{dominio}/edital.pdf", c), dominio
    assert not _oficial("https://www.pciconcursos.com.br/edital.pdf", c)


def test_fonte_entrega_um_ato_por_concurso_aberto_dentro_da_cobertura(tmp_path):
    """A fonte baixa o PDF do edital, tira o texto e devolve um Ato "banca-<slug>"; fora da cobertura ou encerrado, nada."""
    pedidos = []

    class Cliente:
        def texto_pdf(self, url):
            pedidos.append(url)
            return "EDITAL DE ABERTURA. Torna pública a realização de concurso público."

    class Leitor:
        slug = "fau"

        def listar(self, cliente):
            doc = B.Documento("EDITAL DE ABERTURA", "https://www.concursosfau.com.br//sistema/uploads/ed.pdf", "2026-10-20")
            yield B.Concurso("fau", "PREFEITURA MUNICIPAL DE APUCARANA", "PREFEITURA MUNICIPAL DE APUCARANA", "u", "Concurso Público", "PR",
                             "01/2026", "2026-10-21", "2026-11-09", None, [doc])
            yield B.Concurso("fau", "PREFEITURA DE X", "PREFEITURA DE X", "u", "Concurso Público", "SP", None, None, "2026-11-09", None, [doc])   # fora
            yield B.Concurso("fau", "PREFEITURA DE Y", "PREFEITURA DE Y", "u", "Concurso Público", "PR", None, None, "2026-10-01", None, [doc])   # encerrado
            yield B.Concurso("fau", "PREFEITURA DE Z", "PREFEITURA DE Z", "u", "Concurso Público", "PR", None, None, "2026-11-09", None, [])      # sem edital

    fonte = B.Bancas(Cliente(), [Leitor()])
    atos = list(fonte.listar_atos(date(2026, 6, 16), HOJE))
    assert len(atos) == 1 and pedidos == ["https://www.concursosfau.com.br//sistema/uploads/ed.pdf"]
    a = atos[0]
    assert (a.fonte, a.data, a.orgao) == ("banca-fau", "2026-10-20", "PREFEITURA MUNICIPAL DE APUCARANA")
    assert a.titulo.startswith("Edital de abertura nº 01/2026") and fonte.por_banca == {"fau": 1} and fonte.aviso is None
    from varredura.triagem import classificar
    assert classificar(a) == ("abertura", False)


def test_banca_que_falha_nao_derruba_as_outras():
    import urllib.error

    class Quebrada:
        slug = "quebrada"

        def listar(self, cliente):
            raise urllib.error.URLError("fora do ar")
            yield

    class Boa:
        slug = "boa"

        def listar(self, cliente):
            return iter(())

    fonte = B.Bancas(object(), [Quebrada(), Boa()])
    assert list(fonte.listar_atos(HOJE, HOJE)) == []
    assert "quebrada: <urlopen error fora do ar>" in fonte.aviso and fonte.por_banca == {"quebrada": 0, "boa": 0}
