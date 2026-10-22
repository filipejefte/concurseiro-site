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
    residencia = [(n, u) for n, u, _ in itens if n.startswith("RESIDÊNCIA")]
    assert residencia and not B.dentro_da_cobertura(fau.concurso(ler("fau-concurso-apucarana.html"), residencia[0][1], residencia[0][0]))


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
    assert any("Prefeitura Municipal" in t or "Câmara Municipal" in t for t in dentro)         # municípios de MG, ES e GO: agora entram
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
            yield B.Concurso("fau", "PREFEITURA DE X", "PREFEITURA DE X", "u", "Concurso Público", "SP", None, None, "2026-11-09", None, [doc])   # outra UF: entra
            yield B.Concurso("fau", "PROCESSO SELETIVO DE W", "PREFEITURA DE W", "u", "Processo Seletivo", "SP", None, None, "2026-11-09", None, [doc])   # PSS: fora
            yield B.Concurso("fau", "PREFEITURA DE Y", "PREFEITURA DE Y", "u", "Concurso Público", "PR", None, None, "2026-10-01", None, [doc])   # encerrado
            yield B.Concurso("fau", "PREFEITURA DE Z", "PREFEITURA DE Z", "u", "Concurso Público", "PR", None, None, "2026-11-09", None, [])      # sem edital

    fonte = B.Bancas(Cliente(), [Leitor()])
    atos = list(fonte.listar_atos(date(2026, 6, 16), HOJE))
    assert len(atos) == 2 and pedidos == ["https://www.concursosfau.com.br//sistema/uploads/ed.pdf"] * 2
    a = atos[0]
    assert (a.fonte, a.data, a.orgao) == ("banca-fau", "2026-10-20", "PREFEITURA MUNICIPAL DE APUCARANA")
    assert a.titulo.startswith("Edital de abertura nº 01/2026") and fonte.por_banca == {"fau": 2} and fonte.aviso is None
    assert atos[1].orgao == "PREFEITURA DE X"
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


def test_consulpam_so_as_abertas_e_o_edital_com_nome_acentuado():
    consulpam = leitor("consulpam")
    itens = consulpam.itens_da_lista(ler("consulpam-concursos.html"))
    assert [i.orgao for i in itens if B.dentro_da_cobertura(i)] == ["CÂMARA MUNICIPAL DE QUATRO BARRAS"]     # as outras são PSS ou de outra UF (agora só PSS fica de fora)
    quatro = next(i for i in itens if "QUATRO BARRAS" in i.orgao)
    assert (quatro.uf, quatro.tipo, quatro.numero) == ("PR", "Concurso Público", "001/2026")
    consulpam.completar(quatro, ler("consulpam-quatro-barras.html").replace("Inscrição de Concurso", "<script>function validaDat(campo){}</script>Inscrição de Concurso", 1))
    assert (quatro.inscricao_inicio, quatro.inscricao_fim) == ("2026-10-09", "2026-11-03")
    assert quatro.edital.titulo == "EDITAL 001/2026" and quatro.edital.data == "2026-10-09"
    assert "%20" in quatro.edital.url and "C%C3%82MARA" in quatro.edital.url          # nome do arquivo com espaço e acento, pedível
    # o PDF fica em /arquivos/, que o robots.txt da Consulpam proíbe: a página traz cargos, salários e taxas
    assert "ADVOGADO" in quatro.texto and "R$ 5403,69" in quatro.texto and "Dados do Concurso" in quatro.texto and "ATENÇÃO" not in quatro.texto and "validaDat" not in quatro.texto


def test_consulpam_com_robots_proibindo_o_pdf_o_ato_e_o_texto_da_pagina():
    class Cliente:
        def baixar(self, url, **_):
            return (ler("consulpam-quatro-barras.html") if "acao=ver" in url else ler("consulpam-concursos.html")).encode("utf-8")

        def texto_pdf(self, url):
            raise PermissionError(f"robots.txt não permite: {url}")

    fonte = B.Bancas(Cliente(), leitores=[leitor("consulpam")])
    atos = list(fonte.listar_atos(HOJE, HOJE))
    assert len(atos) == 1 and fonte.por_banca == {"consulpam": 1} and fonte.aviso is None
    ato = atos[0]
    assert ato.fonte == "banca-consulpam" and ato.url.endswith("C%C3%82MARA.pdf")               # o link continua sendo o do PDF
    assert "robots.txt" in ato.texto and "SECRETÁRIO DA MESA DIRETIVA" in ato.texto and "R$ 5190,74" in ato.texto


def test_instituto_consulpam_nao_e_o_consulplan():
    from varredura.previstos import slug_da_banca
    assert slug_da_banca("Instituto Consulpam") == "consulpam" and slug_da_banca("Instituto Consulplan") == "consulplan"
    assert slug_da_banca("Fundação de Apoio ao Campus de Paranavaí (FAFIPA)") == "fafipa" == slug_da_banca("Fundação FAFIPA")
    assert slug_da_banca("Instituto Quadrix") == "quadrix" and slug_da_banca("Banca desconhecida") is None and slug_da_banca(None) is None


def test_previsto_com_banca_conhecida_vira_aberto_quando_a_banca_publica_o_edital():
    """Caso real de 21/10/2026: a Câmara de Quatro Barras estava "prevista" (contratação da Consulpam) e a banca já tinha o edital
    com inscrições de 09/10 a 03/11."""
    from varredura import dados
    from varredura.previstos import verificar

    base = dados.ler_json(dados.CONCURSOS)
    previsto = next(c for c in base["concursos"] if c["id"] == "camara-quatro-barras-pr-2026")
    assert dados.situacao(previsto, HOJE) == "previsto" and previsto["banca"]["nome"] == "Instituto Consulpam"

    class Cliente:
        def baixar(self, url, **_):
            return (ler("consulpam-quatro-barras.html") if "acao=ver" in url else ler("consulpam-concursos.html")).encode("utf-8")

    achados = verificar(base, Cliente(), HOJE, leitores=[leitor("consulpam")])
    assert [(c["id"], b.edital.titulo, b.inscricao_fim) for c, b in achados] == [("camara-quatro-barras-pr-2026", "EDITAL 001/2026", "2026-11-03")]
    assert verificar(base, Cliente(), date(2026, 11, 4), leitores=[leitor("consulpam")]) == []      # depois do prazo não é mais aberto
