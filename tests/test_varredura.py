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
])
def test_validacao_pega_erros(estragar, esperado):
    c = real()
    estragar(c)
    erros = validar_concurso(c)
    assert any(esperado in e for e in erros), erros


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


# ---------- revisão e publicação ----------

@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    base = tmp_path / "concursos.json"
    base.write_text(json.dumps({"varredura": None, "proxima_varredura": None, "cobertura": ["federal", "PR"], "concursos": []}),
                    encoding="utf-8")
    monkeypatch.setattr(dados, "CONCURSOS", base)
    monkeypatch.setattr(dados, "DADOS_JS", tmp_path / "dados.js")
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
    js = dados.DADOS_JS.read_text(encoding="utf-8")
    assert c["id"] in js and '"exemplo": false' in js
    assert c["orgao"] in (pasta / "resumo-telegram.md").read_text(encoding="utf-8")


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
