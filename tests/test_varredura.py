"""Testes da varredura: validação, comparação, situação, triagem e publicação, a partir dos exemplos."""
import copy
import csv
import json
from datetime import date

import pytest

from varredura import dados
from varredura.comparar import comparar
from varredura.conferir import normalizar, verificar
from varredura.dados import ler_json, situacao
from varredura.publicar import publicar_semana
from varredura.revisao import gerar, linhas_criticas
from varredura.triagem import classificar
from varredura.validar import validar_concurso

EXEMPLOS = ler_json(dados.EXEMPLO)["concursos"]
DIA = date(2026, 10, 14)


def exemplo(prefixo):
    return copy.deepcopy(next(c for c in EXEMPLOS if c["id"].startswith(prefixo)))


def real():
    """Um exemplo transformado em ficha "real" só para testar o caminho de publicação. Nunca vai ao ar."""
    c = exemplo("hospital-regional")
    c.update(ficticio=False, id="teste-hospital-maringa-pr-2026-edital-01")
    c["banca"]["url"] = "https://www.ibfc.org.br"
    c["documentos"][0].update(url="https://www.diariomunicipal.com.br/amp/materia/TESTE001", publicado_em="2026-10-01")
    return c


# ---------- validação ----------

def test_exemplos_passam_na_validacao():
    assert {c["id"]: validar_concurso(c, exemplo=True) for c in EXEMPLOS} == {c["id"]: [] for c in EXEMPLOS}


def test_ficha_real_valida():
    assert validar_concurso(real()) == []


def _fim_antes_do_inicio(c):
    c["inscricao"].update(inicio="2026-11-30", fim="2026-10-28")


def _salario_zero(c):
    c["cargos"][0]["salario"] = 0


def _agregador(c):
    c["documentos"][0]["url"] = "https://www.pciconcursos.com.br/noticias/edital"


def _fora_do_oficial(c):
    c["documentos"][0]["url"] = "https://blog-de-concursos.com.br/edital.pdf"


def _sem_edital(c):
    c["documentos"] = []


def _municipio_inexistente(c):
    c["municipio_ibge"] = "4199999"


def _cidade_errada(c):
    c["cidade"] = "Curitiba"


def _link_de_exemplo(c):
    c["documentos"][0]["url"] = "https://edital.example/1.pdf"


def _fora_da_cobertura(c):
    c.update(esfera="municipal", uf="SP", municipio_ibge=None, cidade="Campinas")


def _codigo_ibge_fora_do_pr(c):
    c.update(esfera="federal", uf="SP", municipio_ibge="3509502", cidade="Campinas")


@pytest.mark.parametrize("estragar, esperado", [
    (_fim_antes_do_inicio, "precisa ser depois"),
    (_salario_zero, "schema"),
    (_agregador, "agregador"),
    (_fora_do_oficial, "não é de diário oficial"),
    (_sem_edital, "sem link do edital"),
    (_municipio_inexistente, "não existe na tabela"),
    (_cidade_errada, "não bate"),
    (_link_de_exemplo, "link de exemplo"),
    (_fora_da_cobertura, "fora da cobertura"),
    (_codigo_ibge_fora_do_pr, "só para cidade do PR"),
])
def test_validacao_pega_erros(estragar, esperado):
    c = real()
    estragar(c)
    erros = validar_concurso(c)
    assert any(esperado in e for e in erros), erros


def test_federal_fora_do_pr_valido():
    """Federal com uma cidade só fora do PR: uf e cidade, sem código IBGE; nacional: abrangência."""
    c = real()
    c.update(esfera="federal", uf="RJ", municipio_ibge=None, cidade="Rio de Janeiro")
    assert validar_concurso(c) == []
    c.update(nacional=True, abrangencia="14 estados", uf="DF", cidade="Brasília")
    assert validar_concurso(c) == []


def test_ficticio_so_nos_exemplos():
    assert any("fictícia" in e for e in validar_concurso(exemplo("prefeitura-vale-verde"), exemplo=False))


def test_previsto_precisa_de_ato_de_autorizacao():
    previsto = exemplo("guarda-municipal")
    assert validar_concurso(previsto, exemplo=True) == []
    previsto["documentos"][0]["tipo"] = "outro"
    assert any("autorização" in e for e in validar_concurso(previsto, exemplo=True))


# ---------- situação ----------

@pytest.mark.parametrize("inicio, fim, esperado", [
    (None, None, "previsto"),
    ("2026-10-20", "2026-11-20", "previsto"),   # edital publicado, inscrição ainda não começou
    ("2026-10-01", "2026-10-13", "encerrado"),
    ("2026-10-01", "2026-10-14", "breve"),      # encerra hoje
    ("2026-10-01", "2026-10-21", "breve"),      # 7 dias
    ("2026-10-01", "2026-10-22", "aberto"),     # 8 dias
    ("2026-10-14", None, "aberto"),
])
def test_situacao(inicio, fim, esperado):
    assert situacao({"inscricao": {"inicio": inicio, "fim": fim}}, DIA) == esperado


# ---------- comparação ----------

def test_comparar_separa_novos_alterados_e_encerrados():
    publicado = real()
    retificado = copy.deepcopy(publicado)
    retificado["taxa"] = {"min": 80.0, "max": 80.0}
    encerrado_publicado = real()
    encerrado_publicado.update(id="teste-encerrou", inscricao={"inicio": "2026-09-01", "fim": "2026-10-10", "url": None})
    novo = real()
    novo["id"] = "teste-novo-2026"
    ja_encerrado = real()
    ja_encerrado.update(id="teste-ja-encerrado", inscricao={"inicio": "2026-09-01", "fim": "2026-10-01", "url": None})
    base = {"varredura": "2026-10-07", "concursos": [publicado, encerrado_publicado]}

    r = comparar([{"concurso": c} for c in (retificado, novo, ja_encerrado)], base, DIA)
    assert [c["id"] for c in r.novos] == ["teste-novo-2026"]
    assert [n["id"] for n, _ in r.alterados] == [publicado["id"]]
    assert [c["id"] for c in r.ignorados] == ["teste-ja-encerrado"]
    assert [c["id"] for c in r.encerrados] == ["teste-encerrou"]

    igual = copy.deepcopy(publicado)
    igual["conferencia"] = {"conferido_em": "2026-10-07", "por": "Teste", "campos": ["taxa"]}  # controle não conta
    assert comparar([{"concurso": igual}], base, DIA).iguais == [igual]


# ---------- triagem ----------

@pytest.mark.parametrize("titulo, texto, esperado", [
    ("EDITAL DE ABERTURA Nº 01/2026", "O Prefeito torna pública a abertura das inscrições do Concurso Público", ("abertura", False)),
    ("EDITAL Nº 3/2026", "Torna pública a realização de Concurso Público para provimento de cargos", ("abertura", False)),
    ("RETIFICAÇÃO Nº 1 DO EDITAL 01/2026", "Retifica o Concurso Público", ("retificacao", False)),
    ("APOSTILA CCCPPD N 02-2026 - CORRIGE EDITAL 2026-608", "O Presidente da Comissão Coordenadora do Concurso Público "
     "[...] declara em correção ao EDITAL Nº 2026.608", ("retificacao", False)),
    ("TERMO DE APOSTILAMENTO Nº 2 AO CONTRATO 15/2026", "reajuste do contrato do concurso público", ("outro", False)),
    ("EDITAL Nº 9/2026", "Homologação do resultado final do Concurso Público 01/2025", ("resultado", False)),
    ("PROCESSO SELETIVO SIMPLIFICADO Nº 2/2026", "abertura das inscrições do processo seletivo simplificado", ("abertura", True)),
    ("EXTRATO DE CONTRATO Nº 10/2026", "Contratação de empresa para organização e realização de concurso público", ("contratacao_banca", False)),
    ("LEI Nº 100/2026", "Fica autorizada a realização de concurso público para 40 vagas", ("autorizacao", False)),
    ("PORTARIA Nº 5", "Concede férias ao servidor", None),
    ("EDITAL PPG Nº 1/2026", "Torna pública a abertura das inscrições do processo seletivo para o mestrado", ("outro", False)),
    ("EDITAL Nº 1/2026", "EDITAL Nº 1/2026 CONCURSO PÚBLICO O CONSELHO REGIONAL faz saber que realizará, através do INSTITUTO, "
     "Concurso Público destinado à contratação", ("abertura", False)),
    ("EDITAL Nº 276, DE 24 DE SETEMBRO DE 2026", "PROVIMENTO DE CARGOS DE PROFESSOR DA CARREIRA DO MAGISTÉRIO SUPERIOR "
     "A Pró-Reitora [...] concurso público de provas e títulos", ("abertura", False)),
    ("PORTARIA Nº 17336/2026","Nomeia candidato aprovado no Concurso Público, Edital de Abertura nº 1/2024", ("outro", False)),
    ("EDITAL DE CHAMAMENTO DO CONCURSO PÚBLICO", "Convoca aprovados no Concurso Público, Edital de Abertura nº 001/2024",
     ("resultado", False)),
])
def test_triagem(titulo, texto, esperado):
    assert classificar({"titulo": titulo, "texto": texto}) == esperado


def test_triagem_cobertura():
    ato = {"titulo": "EDITAL Nº 1/2026", "texto": "Torna pública a abertura das inscrições do concurso público",
           "orgao": "Prefeituras/Estado de Goiás/Prefeitura Municipal de Palmelo"}
    assert classificar(ato) == ("fora", False)
    ato["orgao"] = "Prefeituras/Estado do Paraná/Prefeitura Municipal de Maringá"
    assert classificar(ato) == ("abertura", False)


# ---------- leitores das fontes (textos sintéticos, sem rede) ----------

def test_zip_do_inlabs():
    import io
    import zipfile
    from varredura.fontes.dou_inlabs import atos_do_zip

    xml = ('<xml><article pubDate="06/10/2026" artCategory="Ministério X/Universidade Y" '
           'pdfPage="https://pesquisa.in.gov.br/imprensa/jsp/visualiza/index.jsp?data=06/10/2026&amp;jornal=530&amp;pagina=45">'
           '<body><Identifica><![CDATA[EDITAL Nº 1, DE 5 DE OUTUBRO DE 2026]]></Identifica>'
           '<Texto><![CDATA[<p>Torna pública a abertura das inscrições do concurso público.</p>]]></Texto></body></article></xml>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("materia.xml", xml)
    ato = atos_do_zip(buffer.getvalue())[0]
    assert (ato.data, ato.titulo, ato.orgao) == ("2026-10-06", "EDITAL Nº 1, DE 5 DE OUTUBRO DE 2026", "Ministério X/Universidade Y")
    assert ato.url.startswith("https://pesquisa.in.gov.br/") and "abertura das inscrições" in ato.texto


def test_cliente_tenta_de_novo_em_falha_de_rede(tmp_path, monkeypatch):
    import urllib.error
    from varredura.fontes.base import Cliente

    cliente = Cliente(contato="teste", intervalo=0, cache=tmp_path)
    monkeypatch.setattr(Cliente, "ESPERAS", (0, 0, 0))
    respostas = [urllib.error.URLError(TimeoutError("sem resposta")), TimeoutError("sem resposta"), b"ok"]

    class Resposta:
        def __init__(self, corpo): self.corpo = corpo
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self.corpo

    def abrir(pedido, timeout):
        r = respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return Resposta(r)

    monkeypatch.setattr(cliente._abridor, "open", abrir)
    assert cliente._pedir("https://exemplo.gov.br/x") == b"ok"

    respostas[:] = [urllib.error.HTTPError("https://exemplo.gov.br/y", 404, "não achado", {}, None)]
    with pytest.raises(urllib.error.HTTPError):  # 404 não é falha passageira: não tenta de novo
        cliente._pedir("https://exemplo.gov.br/y")


def test_nome_na_fila_e_estavel():
    from varredura.extracao import nome_na_fila
    from varredura.fontes.base import Ato

    a = Ato("DOU", "2026-10-13", "EDITAL Nº 1", "Universidade X", "http://pesquisa.in.gov.br/p45", "texto do edital 1")
    b = Ato("DOU", "2026-10-13", "EDITAL Nº 2", "Universidade X", "http://pesquisa.in.gov.br/p45", "texto do edital 2")
    assert nome_na_fila(a) == nome_na_fila(Ato(**a.como_dict()))  # refazer a coleta dá o mesmo nome
    assert nome_na_fila(a) != nome_na_fila(b)                      # mesma página do DOU, matérias diferentes


def test_materias_da_amp():
    from varredura.fontes.diario_municipios_pr import materias

    texto = ("Paraná , 06 de Outubro de 2026   •   Diário Oficial dos Municípios do Paraná   •    ANO XV | Nº 3631\n"
             "ESTADO DO PARANÁ\nPREFEITURA MUNICIPAL DE TESTE DO\nNORTE\nSECRETARIA DE ADMINISTRAÇÃO\n"
             "EDITAL DE ABERTURA Nº 01/2026\nTorna pública a abertura do concurso público.\n"
             "Publicado por:\nFulano de Tal\nCódigo Identificador:AB12CD34\n"
             "ESTADO DO PARANÁ\nCÂMARA MUNICIPAL DE OUTRO\nPORTARIA Nº 5\nConcede férias.\n"
             "Publicado por:\nBeltrano\nCódigo Identificador:EF56AB78\n")
    atos = materias(texto, "2026-10-06")
    assert [a.url[-8:] for a in atos] == ["AB12CD34", "EF56AB78"]
    assert atos[0].orgao == "PREFEITURA MUNICIPAL DE TESTE DO NORTE"
    assert atos[0].titulo == "EDITAL DE ABERTURA Nº 01/2026"
    assert "Publicado por" not in atos[0].texto and "Diário Oficial dos Municípios" not in atos[0].texto


# Sumário no formato real do DIOE-PR: as duas primeiras matérias são do Suplemento de Concursos de 15/10/2026
# (edição 17377); as duas últimas imitam pastas do Executivo do mesmo dia, com id e título ilustrativos.
SUMARIO_DIOE = """<ul id="tree" class="filetree" data-id="1792162842">
	<li><span class="folder">Secretaria da Administração e da Previdência</span>
		<ul>
			<li><span class="folder">Edital-EX</span>
				<ul>
					<li><span class="file"><a class="linkMateria" identificador="2134452" pagina="3"data-id="2176255" data-protocolo="138677/2026"data-materia-id="2134452"> #138677/2026 - EDITAL 246/2026</a></span>
					</li>
				</ul>
			</li>
		</ul>
	</li>
	<li><span class="folder">Secretaria da Segurança Pública</span>
		<ul>
			<li><span class="folder">PMPR</span>
				<ul>
					<li><span class="folder">Edital-EX</span>
						<ul>
							<li><span class="file"><a class="linkMateria" identificador="2134731" pagina="9"data-id="2176534" data-protocolo="138532/2026"data-materia-id="2134731"> #138532/2026 - Edital_nº_252_SOLDADO_PMPR_2025_-_Resultado_definitivo_da_Investigação_Social.docx</a></span>
							</li>
						</ul>
					</li>
				</ul>
			</li>
		</ul>
	</li>
	<li><span class="folder">Poder Executivo</span>
		<ul>
			<li><span class="folder">Despacho do Governador</span>
				<ul>
					<li><span class="file"><a class="linkMateria" identificador="2136200" pagina=""data-id="2178018" data-protocolo="140240/2026"data-materia-id="2136200"> #140240/2026 - Despacho 1234</a></span>
					</li>
				</ul>
			</li>
			<li><span class="folder">IAT</span>
				<ul>
					<li><span class="folder">Concessão de Autorização Ambiental</span>
						<ul>
							<li><span class="file"><a class="linkMateria" identificador="2133790" pagina=""data-id="2175590" data-protocolo="138077/2026"data-materia-id="2133790"> #138077/2026 - Autorização Ambiental 55</a></span>
							</li>
						</ul>
					</li>
				</ul>
			</li>
		</ul>
	</li>
</ul>"""

# Começo real da página da matéria 2134452 (HTML exportado do Word), encurtado.
MATERIA_DIOE = """<html><head><meta http-equiv=Content-Type content="text/html; charset=utf-8">
<style><!-- p.MsoNormal {margin:0cm;} --></style></head><body lang=PT-BR><div class=WordSection1>
<p class=tablepocp align=center style='text-align:center'><a name="_Hlk146525815"></a><b><span
lang=PT style='background:white'>EDITAL Nº 246/2026 - DRH/SEAP</span></b></p>
<p class=tablepocp style='text-align:justify'><span lang=PT>O CHEFE DO DEPARTAMENTO DE RECURSOS HUMANOS E
PREVIDÊNCIA, DA SECRETARIA</span><span lang=PT> DE ESTADO DA ADMINISTRAÇÃO E DA PREVIDÊNCIA - SEAP,</span></p>
<table class=MsoNormalTable border=1><tr><td><p class=tablepocp><span lang=PT>Inscrição</span></p></td>
<td><p class=tablepocp><span lang=PT>Prova</span></p><p class=tablepocp><span lang=PT>Objetiva</span></p></td></tr>
<tr><td><p class=tablepocp>002894-9</p></td><td><p class=tablepocp>61,00</p></td></tr></table>
<p class=tablepocp>Curitiba, datado&nbsp;e assinado eletronicamente.</p></div></body></html>"""


def test_sumario_do_dioe():
    from varredura.fontes.diario_estado_pr import candidata, orgao, sumario

    materias = sumario(SUMARIO_DIOE)
    assert [m.id for m in materias] == ["2134452", "2134731", "2136200", "2133790"]
    assert materias[0].titulo == "EDITAL 246/2026"
    assert materias[1].titulo == "Edital nº 252 SOLDADO PMPR 2025 - Resultado definitivo da Investigação Social"
    assert materias[1].pastas == ("Secretaria da Segurança Pública", "PMPR", "Edital-EX")
    assert orgao(materias[0].pastas) == "Secretaria da Administração e da Previdência"
    assert orgao(materias[1].pastas) == "Secretaria da Segurança Pública / PMPR"
    assert orgao(materias[2].pastas) == "Governo do Estado do Paraná"
    # No Executivo: edital e despacho do governador são lidos; licença ambiental nunca.
    assert [candidata(m) for m in materias] == [True, True, True, False]


def test_texto_da_materia_do_dioe():
    from varredura.fontes.diario_estado_pr import texto_do_html

    assert texto_do_html(MATERIA_DIOE).splitlines() == [
        "EDITAL Nº 246/2026 - DRH/SEAP",
        "O CHEFE DO DEPARTAMENTO DE RECURSOS HUMANOS E PREVIDÊNCIA, DA SECRETARIA DE ESTADO DA ADMINISTRAÇÃO E DA PREVIDÊNCIA - SEAP,",
        "Inscrição | Prova Objetiva",
        "002894-9 | 61,00",
        "Curitiba, datado e assinado eletronicamente.",
    ]


def test_dioe_le_o_suplemento_inteiro_e_so_candidatas_do_executivo():
    from datetime import date

    from varredura.fontes import diario_estado_pr as dioe

    edicoes = {"itens": [
        {"id": 17377, "data": "15/10/2026", "tipo_edicao_id": 8, "tipo_edicao_posicao": 4},
        {"id": 17376, "data": "15/10/2026", "tipo_edicao_id": 3, "tipo_edicao_posicao": 1},
        {"id": 17379, "data": "15/10/2026", "tipo_edicao_id": 2, "tipo_edicao_posicao": 2},   # comércio: fora
        {"id": 17300, "data": "01/10/2026", "tipo_edicao_id": 8, "tipo_edicao_posicao": 4},   # fora do período
    ]}
    pedidos = []

    class Cliente:
        def baixar(self, url, usar_cache=True, **_):
            pedidos.append(url)
            if url == dioe.URL_EDICOES:
                return json.dumps(edicoes).encode()
            if "view_html_diario" in url:
                return SUMARIO_DIOE.encode()
            return MATERIA_DIOE.encode()

    atos = list(dioe.DiarioEstadoPR(Cliente()).listar_atos(date(2026, 10, 14), date(2026, 10, 16)))
    sumarios = [u for u in pedidos if "view_html_diario" in u]
    assert sumarios == [dioe.URL_SUMARIO.format(17376), dioe.URL_SUMARIO.format(17377)]
    executivo = [a for a in atos if a.url.endswith("/17376")]
    suplemento = [a for a in atos if a.url.endswith("/17377")]
    assert len(executivo) == 3 and len(suplemento) == 4   # a licença ambiental só entra no Suplemento
    a = suplemento[0]
    assert (a.fonte, a.data, a.titulo) == ("DIOE-PR", "2026-10-15", "EDITAL 246/2026")
    assert a.url == "https://www.dioe.pr.gov.br/apifront/portal/edicoes/publicacoes_ver_conteudo/2134452/17377"
    assert a.texto.startswith("EDITAL Nº 246/2026 - DRH/SEAP\n")


# ---------- revisão e publicação ----------

@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    base = tmp_path / "concursos.json"
    base.write_text(json.dumps({"varredura": None, "proxima_varredura": None, "cobertura": ["federal", "PR"], "concursos": []}),
                    encoding="utf-8")
    monkeypatch.setattr(dados, "CONCURSOS", base)
    pasta = tmp_path / "varreduras" / "2026-10-14"
    c = real()
    trechos = {campo: "trecho de teste" for campo in dados.CAMPOS_CRITICOS}
    dados.gravar_json(pasta / "fichas" / f"{c['id']}.json", {"ato": "001-teste.md", "trechos": trechos, "concurso": c})
    return pasta, base, c


def _marcar(pasta, valor="ok"):
    arquivo = pasta / "revisao.csv"
    with arquivo.open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    for linha in linhas:
        linha["conferido"] = valor
    with arquivo.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=linhas[0].keys(), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)


def test_publicar_recusa_sem_conferencia(ambiente):
    pasta, base, c = ambiente
    gerar(pasta)
    assert (pasta / "revisao.md").exists()
    with (pasta / "cobertura.csv").open(encoding="utf-8-sig", newline="") as f:
        cobertura = list(csv.DictReader(f, delimiter=";"))
    assert [(l["orgao"], l["uf"], l["link_edital"]) for l in cobertura] == [(c["orgao"], "PR", c["documentos"][0]["url"])]
    assert set(cobertura[0]) >= {"orgao", "cidade", "uf", "situacao", "fim_inscricao", "link_edital"}
    aprovados, recusados = publicar_semana(pasta, "Teste", hoje=DIA)
    assert aprovados == [] and recusados and "falta conferir" in recusados[0][1]
    assert ler_json(base)["concursos"] == []


def test_publicar_o_que_foi_conferido(ambiente):
    pasta, base, c = ambiente
    gerar(pasta)
    _marcar(pasta)
    aprovados, recusados = publicar_semana(pasta, "Teste", hoje=DIA)
    assert recusados == [] and [x["id"] for x in aprovados] == [c["id"]]

    publicado = ler_json(base)
    assert publicado["varredura"] == "2026-10-14" and publicado["proxima_varredura"] == "2026-10-21"
    ficha = publicado["concursos"][0]
    assert ficha["conferencia"]["por"] == "Teste"
    assert set(ficha["conferencia"]["campos"]) == set(dados.CAMPOS_CRITICOS)
    assert ficha["primeira_varredura"] == ficha["ultima_alteracao"] == "2026-10-14"
    resumo = (pasta / "resumo-telegram.md").read_text(encoding="utf-8")
    assert c["orgao"] in resumo and f"/concurso/{c['id']}/" in resumo and "concurso.html" not in resumo
    assert resumo.count(dados.site_url("/")) >= 2
    whatsapp = (pasta / "resumo-whatsapp.txt").read_text(encoding="utf-8")
    assert c["orgao"] in whatsapp and "*Novos*" in whatsapp and "##" not in whatsapp and "](" not in whatsapp
    assert dados.site_url("/") in whatsapp.splitlines()[0] and whatsapp.startswith("*1 concurso novo nesta semana*")
    from PIL import Image
    assert Image.open(pasta / "posts" / f"post-{c['id']}.png").size == (1080, 1350)
    assert ficha["orgao"] in (pasta / "posts" / f"post-{c['id']}.txt").read_text(encoding="utf-8")


def test_valor_mudado_depois_da_conferencia_volta_a_ser_recusado(ambiente):
    pasta, base, c = ambiente
    gerar(pasta)
    _marcar(pasta)
    ficha = ler_json(pasta / "fichas" / f"{c['id']}.json")
    ficha["concurso"]["cargos"][0]["salario"] = 9999.0
    dados.gravar_json(pasta / "fichas" / f"{c['id']}.json", ficha)
    aprovados, recusados = publicar_semana(pasta, "Teste", hoje=DIA)
    assert aprovados == [] and "salario" in recusados[0][1]


def test_revisao_mantem_marcas_das_linhas_que_nao_mudaram(ambiente):
    pasta, base, c = ambiente
    gerar(pasta)
    _marcar(pasta)
    gerar(pasta)
    with (pasta / "revisao.csv").open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    assert len(linhas) == len(linhas_criticas(c)) and all(l["conferido"] == "ok" for l in linhas)


# ---------- conferência automática ----------


ATO = normalizar("""EDITAL DE ABERTURA Nº 01/2026. 5.3 O período para a realização das inscrições será a partir das 12h00min
do dia 30 de setembro de 2026 às 23h59min do dia 29/10/2026. Divulgação das inscrições deferidas: 05/11/2026.
Valor da taxa de inscrição: R$ 130,00 (médio) e R$ 180,00 (superior).
201 Agente Administrativo 40h 01 R$ 2.689,59 130,00 202 Auxiliar de Serviços Gerais 40h 01 R$ 1.837,03 130,00
10.2 A prova objetiva será aplicada na data provável de 15 de novembro de 2026. 16.11 Gabarito da prova objetiva 16/11/2026.
Contratada: Fundação de Apoio ao Ensino (FAUEPG). Município de Nova Prata do Iguaçu.""")
LINK = "https://www.diariomunicipal.com.br/amp/materia/X1"


def _ficha_conferir(**mudar):
    c = {"inscricao": {"inicio": "2026-09-30", "fim": "2026-10-29"}, "prova_objetiva": "2026-11-15", "isencao_ate": None,
         "taxa": {"min": 130.0, "max": 180.0}, "banca": {"nome": "FAUEPG"}, "cidade": "Nova Prata do Iguaçu", "nacional": False,
         "cargos": [{"nome": "Agente Administrativo", "salario": 2689.59}, {"nome": "Auxiliar de Serviços Gerais", "salario": 1837.03}],
         "documentos": [{"tipo": "edital", "url": LINK, "publicado_em": "2026-09-23"}]}
    for chave, valor in mudar.items():
        alvo, campo = (c["inscricao"], chave[5:]) if chave.startswith("insc_") else (c, chave)
        alvo[campo] = valor
    return c


def _passa(campo, c, cargo=None):
    return verificar(campo, c, ATO, {LINK}, cargo)[0]


def test_conferencia_automatica_aceita_o_que_esta_no_ato():
    c = _ficha_conferir()
    assert all(_passa("salario", c, k) for k in c["cargos"])
    assert all(_passa(campo, c) for campo in ("inscricao.inicio", "inscricao.fim", "prova_objetiva", "taxa", "banca", "cidade", "edital"))


@pytest.mark.parametrize("campo,mudar", [
    ("inscricao.inicio", {"insc_inicio": "2026-10-29", "insc_fim": "2026-09-30"}),   # início e fim trocados
    ("inscricao.fim", {"insc_fim": "2026-10-30"}),                                   # um dia depois
    ("prova_objetiva", {"prova_objetiva": "2026-11-16"}),                            # data do gabarito
    ("prova_objetiva", {"prova_objetiva": None}),                                    # o edital traz a data
    ("taxa", {"taxa": {"min": 130.0, "max": 190.0}}),
    ("banca", {"banca": {"nome": "Instituto Inventado"}}),
    ("cidade", {"cidade": "Maringá"}),
    ("edital", {"documentos": [{"tipo": "edital", "url": "https://outro.example/edital.pdf", "publicado_em": "2026-09-23"}]}),
])
def test_conferencia_automatica_recusa_valor_errado(campo, mudar):
    assert not _passa(campo, _ficha_conferir(**mudar))


def test_conferencia_automatica_recusa_salario_trocado_entre_cargos():
    c = _ficha_conferir()
    c["cargos"][1]["salario"] = 2689.59   # o auxiliar com o salário do agente
    assert not _passa("salario", c, c["cargos"][1])


def test_previsto_sem_edital_passa_nos_campos_vazios():
    c = _ficha_conferir(insc_inicio=None, insc_fim=None, prova_objetiva=None, taxa={"min": None, "max": None},
                        documentos=[{"tipo": "autorizacao", "url": LINK, "publicado_em": "2026-09-23"}])
    assert all(_passa(campo, c) for campo in ("inscricao.inicio", "inscricao.fim", "prova_objetiva", "taxa", "edital"))


def test_publicar_aceita_auto_e_recusa_amostra(ambiente):
    pasta, base, c = ambiente
    gerar(pasta)
    _marcar(pasta, "amostra")
    assert publicar_semana(pasta, "Teste", hoje=DIA)[0] == []
    _marcar(pasta, "auto")
    aprovados, _ = publicar_semana(pasta, "Teste", hoje=DIA)
    assert [x["id"] for x in aprovados] == [c["id"]]
    assert ler_json(base)["concursos"][0]["conferencia"]["por"] == "conferência automática"


# ---------- conferência automática: tabela do magistério e inscrição por item ----------

# Edital de professor federal: uma tabela de remuneração para todos os cargos (regime x titulação) e um período
# de inscrição por item. Modelado nos editais da UFPR (276/2026) e da UNILA (240/2026).
ATO_MAGISTERIO = normalizar("""EDITAL Nº 276/2026. 1.1 Dos cargos: os itens constam do Anexo 01.
2. DA REMUNERAÇÃO. Tabela de remuneração, Classe A.
20 (VINTE) HORAS: PROFESSOR ASSISTENTE (COM GRADUAÇÃO) VB R$ 2.500,00 RT R$ 698,59 R$ 3.198,59
(COM MESTRADO) R$ 3.998,24 (COM DOUTORADO) R$ 5.037,78
DEDICAÇÃO EXCLUSIVA (DE): (COM GRADUAÇÃO) R$ 6.397,19 (COM MESTRADO) R$ 9.595,78 (COM DOUTORADO) VB R$ 7.107,99 R$ 13.753,96
ANEXO 02. ITEM PERÍODO DE INSCRIÇÕES TAXA DE INSCRIÇÃO 1.2 22/03/2027 a 20/04/2027 R$ 240,00
1.3 18/01/2027 a 17/02/2027 R$ 88,00 1.28 21/12/2026 a 20/01/2027 R$ 240,00""")


def _professor(salario, requisitos, jornada=40):
    return {"nome": "Professor do Magistério Superior – Genética", "salario": salario, "requisitos": requisitos, "jornada_horas": jornada}


def _ficha_magisterio(cargo, inicio="2027-03-22", fim="2027-04-20"):
    return {"inscricao": {"inicio": inicio, "fim": fim}, "prova_objetiva": None, "isencao_ate": None, "cargos": [cargo],
            "taxa": {"min": None, "max": None}, "banca": {"nome": "UFPR"}, "cidade": "Curitiba", "nacional": False,
            "documentos": [{"tipo": "edital", "url": LINK, "publicado_em": "2026-09-25"}]}


def _passa_magisterio(campo, c, cargo=None):
    return verificar(campo, c, ATO_MAGISTERIO, {LINK}, cargo)[0]


@pytest.mark.parametrize("salario,requisitos,jornada", [
    (13753.96, "Item 1.2; dedicação exclusiva; titulação mínima: doutorado", 40),
    (5037.78, "Item 1.2; 20 horas; titulação mínima: doutorado", 20),
    (3198.59, "Item 1.2; 20 horas; graduação em Medicina", 20),
    (13753.96, "40 h com dedicação exclusiva; graduação na área da saúde ou ciências biológicas e doutorado em Anatomia", 40),
])
def test_conferencia_aceita_salario_da_tabela_do_magisterio(salario, requisitos, jornada):
    cargo = _professor(salario, requisitos, jornada)
    assert _passa_magisterio("salario", _ficha_magisterio(cargo), cargo)


@pytest.mark.parametrize("salario,requisitos,jornada", [
    (5037.78, "Item 1.2; dedicação exclusiva; titulação mínima: doutorado", 40),     # valor do regime de 20 h
    (9595.78, "Item 1.2; dedicação exclusiva; titulação mínima: doutorado", 40),     # valor do mestrado
    (7107.99, "Item 1.2; dedicação exclusiva; titulação mínima: doutorado", 40),     # vencimento básico, não o total
    (13753.96, "Item 1.2; 20 horas; titulação mínima: doutorado", 20),               # valor da dedicação exclusiva
    (3198.59, "Item 1.6; 20 horas; graduação em Medicina com residência ou especialização", 20),   # titulação em dúvida
])
def test_conferencia_recusa_salario_errado_na_tabela_do_magisterio(salario, requisitos, jornada):
    cargo = _professor(salario, requisitos, jornada)
    assert not _passa_magisterio("salario", _ficha_magisterio(cargo), cargo)


def test_tabela_do_magisterio_nao_vale_para_outro_cargo():
    cargo = {"nome": "Técnico de Laboratório", "salario": 13753.96, "requisitos": "dedicação exclusiva; doutorado", "jornada_horas": 40}
    assert not _passa_magisterio("salario", _ficha_magisterio(cargo), cargo)


def test_conferencia_aceita_periodo_do_item_do_cargo():
    cargo = _professor(13753.96, "Item 1.2; dedicação exclusiva; titulação mínima: doutorado")
    c = _ficha_magisterio(cargo)
    assert _passa_magisterio("inscricao.inicio", c) and _passa_magisterio("inscricao.fim", c)
    cargo128 = _professor(13753.96, "Item 1.28; dedicação exclusiva; titulação mínima: doutorado")
    c = _ficha_magisterio(cargo128, "2026-12-21", "2027-01-20")
    assert _passa_magisterio("inscricao.inicio", c) and _passa_magisterio("inscricao.fim", c)


@pytest.mark.parametrize("item,inicio,fim", [
    ("1.2", "2027-01-18", "2027-02-17"),    # período do item 1.3
    ("1.2", "2027-04-20", "2027-03-22"),    # início e fim trocados
    ("1.2", "2027-03-23", "2027-04-20"),    # um dia depois
    ("1.2", "2026-12-21", "2027-01-20"),    # período do 1.28: "1.2" não casa com "1.28"
    ("1.4", "2027-03-22", "2027-04-20"),    # item que não está na tabela
])
def test_conferencia_recusa_periodo_de_outro_item(item, inicio, fim):
    cargo = _professor(13753.96, f"Item {item}; dedicação exclusiva; titulação mínima: doutorado")
    c = _ficha_magisterio(cargo, inicio, fim)
    assert not (_passa_magisterio("inscricao.inicio", c) and _passa_magisterio("inscricao.fim", c))


# ---------- Telegram ----------

def test_telegram_parte_mensagens_abaixo_do_limite():
    from varredura.telegram import mensagens
    blocos = [f"• Concurso {i}\n  até R$ 1.000,00 · inscrições até sex, 20/11\n  Ficha: https://x.example/concurso/{i}/" for i in range(200)]
    texto = "Concursos da semana\n\nNovos\n\n" + "\n".join(blocos) + "\n\nTodos os concursos: https://x.example/"
    partes = mensagens(texto)
    assert len(partes) > 1 and all(len(p) <= 4096 for p in partes)
    assert "\n".join(partes).replace("\n\n", "\n").count("• Concurso") == 200
    assert mensagens("curto") == ["curto"]
    assert all(len(p) <= 4096 for p in mensagens("x" * 10000))


def test_telegram_teste_so_imprime(tmp_path, capsys, monkeypatch):
    from varredura.telegram import postar
    (tmp_path / "resumo-telegram.md").write_text("Concursos da semana\n\n• Um\n", encoding="utf-8")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert postar(tmp_path, teste=True) == 0
    assert "mensagem 1 de 1" in capsys.readouterr().out
    assert postar(tmp_path, se_configurado=True) == 0
    with pytest.raises(SystemExit):
        postar(tmp_path)


def _professor_com_tabela():
    """Ficha de professor federal com a tabela por titulação (o edital aceita titulação menor)."""
    cargo = _professor(13753.96, "Item 1.2; dedicação exclusiva; titulação mínima: doutorado")
    cargo["remuneracao_por_titulacao"] = [{"titulacao": "doutorado", "valor": 13753.96},
                                          {"titulacao": "mestrado", "valor": 9595.78},
                                          {"titulacao": "graduacao", "valor": 6397.19}]
    return _ficha_magisterio(cargo), cargo


def test_tabela_por_titulacao_vira_linhas_de_conferencia():
    from varredura.revisao import linhas_titulacao
    c, _ = _professor_com_tabela()
    linhas = [campo for campo, _ in linhas_criticas(dict(c, cargos=c["cargos"], banca={"nome": "UFPR", "url": None}, nacional=False,
                                                         cidade="Curitiba", uf="PR", municipio_ibge="4106902"))]
    assert linhas.count("salario_titulacao") == 3
    for texto, referencia in linhas_titulacao(c):
        assert verificar("salario_titulacao", c, ATO_MAGISTERIO, {LINK}, referencia)[0], texto


def test_tabela_por_titulacao_recusa_valor_trocado():
    from varredura.revisao import linhas_titulacao
    c, cargo = _professor_com_tabela()
    cargo["remuneracao_por_titulacao"][1]["valor"] = 3998.24   # mestrado com o valor do regime de 20 h
    resultados = {texto: verificar("salario_titulacao", c, ATO_MAGISTERIO, {LINK}, r)[0] for texto, r in linhas_titulacao(c)}
    assert [t for t, ok in resultados.items() if not ok] == ["Tabela por titulação, dedicação exclusiva: Mestrado R$ 3.998,24"]


def test_schema_aceita_tabela_por_titulacao():
    c = real()
    c["cargos"][0]["remuneracao_por_titulacao"] = [{"titulacao": "mestrado", "valor": 9595.78}]
    assert validar_concurso(c) == []
    c["cargos"][0]["remuneracao_por_titulacao"] = [{"titulacao": "pos-doutorado", "valor": 1.0}]
    assert any("schema" in e for e in validar_concurso(c))


def test_resumo_whatsapp_ate_10_novos_com_salario_primeiro_e_abaixo_de_4000(tmp_path):
    from varredura.publicar import escrever_whatsapp
    base = real()
    novos = []
    for i in range(30):
        c = copy.deepcopy(base)
        c.update(id=f"teste-{i:02d}", orgao=f"Prefeitura de Teste Número {i:02d} com Nome Bem Comprido (PR)")
        c["inscricao"].update(inicio="2026-10-01", fim=f"2026-11-{10 + (30 - i) % 18:02d}")
        if i % 3 == 0:
            for k in c["cargos"]:
                k["salario"] = None
        novos.append(c)
    acabando = [dict(copy.deepcopy(base), id=f"fim-{i}", orgao=f"Câmara de Encerra {i} (PR)") for i in range(40)]
    texto = escrever_whatsapp(tmp_path, novos, acabando, novos, DIA)
    assert len(texto) < 4000
    linhas = texto.splitlines()
    assert dados.site_url("/") in linhas[0] and linhas[0].startswith("*30 concursos novos nesta semana*")
    itens = [l for l in linhas if l.startswith("• Prefeitura de Teste")]
    assert 0 < len(itens) <= 10
    primeiros = [n for n in novos if any(n["orgao"] in l for l in itens)]
    assert all(any(k["salario"] for k in n["cargos"]) for n in primeiros)   # com salário antes dos sem salário
    fins = [n["inscricao"]["fim"] for n in sorted(primeiros, key=lambda n: next(i for i, l in enumerate(itens) if n["orgao"] in l))]
    assert fins == sorted(fins)
    assert f"e mais {30 - len(itens)} no site" in texto
    assert linhas[-2].startswith("Todos os concursos: ")


# ---------- prioridade de extração e progresso.md ----------

def _fila(pasta, nome, classe, data_ato, texto, fonte="DOU"):
    (pasta / "fila").mkdir(parents=True, exist_ok=True)
    (pasta / "fila" / nome).write_text(
        f"fonte: {fonte}\ndata: {data_ato}\nclasse: {classe}\npss: False\norgao: Órgão\ntitulo: Edital\nurl: https://x.gov.br/{nome}\n---\n{texto}\n",
        encoding="utf-8")
    return pasta / "fila" / nome


def test_prioridade_de_extracao(tmp_path):
    from varredura.extracao import prioridade
    hoje = date(2026, 10, 19)
    aberto = _fila(tmp_path, "a.md", "abertura", "2026-09-30", "As inscrições serão de 01/10/2026 a 30/10/2026.")
    futuro = _fila(tmp_path, "b.md", "abertura", "2026-10-15", "Período de inscrições: 3 de novembro de 2026 a 3 de dezembro de 2026.")
    previsto = _fila(tmp_path, "c.md", "contratacao_banca", "2026-08-01", "Contratação de banca para concurso público.")
    velho = _fila(tmp_path, "d.md", "autorizacao", "2026-05-01", "Autoriza concurso público.")
    encerrado = _fila(tmp_path, "e.md", "abertura", "2026-07-01", "Inscrições de 01/07/2026 a 31/07/2026.")
    assert prioridade(aberto, hoje)[0] == 1 and prioridade(futuro, hoje)[0] == 1
    assert prioridade(previsto, hoje)[0] == 2
    assert prioridade(velho, hoje) == (3, 0) and prioridade(encerrado, hoje) == (3, 1)   # encerrado por último


def test_progresso_conta_o_que_falta_e_guarda_as_notas(tmp_path):
    from varredura.progresso import MARCA, escrever
    pasta = tmp_path / "2026-10-19"
    _fila(pasta, "a.md", "abertura", "2026-10-01", "Inscrições de 01/10/2026 a 30/10/2026.")
    _fila(pasta, "b.md", "abertura", "2026-07-01", "Inscrições de 01/07/2026 a 31/07/2026.", fonte="AMP-PR")
    dados.gravar_json(pasta / "descartes.json", [{"ato": "b.md", "motivo": "inscrição encerrada"}])
    arquivo, faltam = escrever(pasta, hoje=date(2026, 10, 19))
    texto = arquivo.read_text(encoding="utf-8")
    assert faltam == 1 and "| DOU | 1 | 0 | 1 |" in texto and "| AMP-PR | 1 | 1 | 0 |" in texto and "P1 (inscrição aberta ou futura): 1" in texto
    arquivo.write_text(texto.split(MARCA)[0] + MARCA + "\n\n## Notas\n\n- Último lote: 1 a 30\n", encoding="utf-8")
    escrever(pasta, hoje=date(2026, 10, 19))
    assert "- Último lote: 1 a 30" in arquivo.read_text(encoding="utf-8")


# ---------- voz.md: datas, legenda e negrito do Telegram ----------

def test_data_curta_so_mostra_o_ano_quando_e_outro_ano(monkeypatch):
    monkeypatch.setattr(dados, "ANO_REFERENCIA", 2026)
    assert dados.data_curta("2026-11-20") == "sex, 20/11"
    assert dados.data_curta("2027-03-22") == "seg, 22/03/2027"


def test_legenda_do_post_no_formato_da_voz(monkeypatch):
    from gerador.modelo import Concurso
    from varredura.publicar import legenda_post
    monkeypatch.setattr(dados, "ANO_REFERENCIA", 2026)
    c = exemplo("prefeitura-vale-verde")
    texto = legenda_post(c, Concurso(c, DIA))
    assert texto.startswith("Prefeitura de Vale Verde (PR) abriu concurso para engenheiro civil e mais 4 cargos: "
                            "até R$ 9.312,40 iniciais, 189 vagas + CR, níveis fundamental a superior. "
                            "Inscrições até sex, 20/11, só no site da banca. Ficha completa e alerta grátis no link da bio.")


def test_telegram_negrito_e_escape():
    from varredura.telegram import para_html
    assert para_html("**3 concursos novos** · R&D <x>") == "<b>3 concursos novos</b> · R&amp;D &lt;x&gt;"
