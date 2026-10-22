"""Anonimato (regra 11 do CLAUDE.md): nada do que o projeto publica leva dado de quem o cria.

Os nomes saem do git na hora do teste; nenhum fica escrito aqui."""
from datetime import date

import pytest

from gerador import anonimato, config as configuracao
from gerador.build import construir
from varredura.dados import VARREDURAS

DIA = date(2026, 10, 16)
tem_historico = pytest.mark.skipif(not anonimato.autores(), reason="sem histórico do git (cópia sem .git)")


@tem_historico
def test_a_lista_de_proibidos_vem_do_git_e_nao_vem_vazia():
    rotulos = [r for r, _ in anonimato.proibidos()]
    assert "autor de commit" in rotulos and "marcador" in rotulos
    assert anonimato.dono_do_repositorio() or "GITHUB_REPOSITORY_OWNER" not in __import__("os").environ


@tem_historico
def test_o_verificador_acha_o_que_deve_e_deixa_passar_o_resto(tmp_path):
    """Controle positivo (autor real do git, dono do repositório, marcadores) e negativo (página limpa)."""
    (tmp_path / "limpa.html").write_text("<p>Concursos federais e do Paraná. Inscrição só no site da banca.</p>", encoding="utf-8")
    assert anonimato.verificar_pasta(tmp_path) == []
    nome = next(a for r, a in anonimato.proibidos() if r == "autor de commit" and "@" not in a)
    email = next(a for r, a in anonimato.proibidos() if r == "autor de commit" and "@" in a)
    (tmp_path / "nome.html").write_text(f"<footer>Feito por {nome.upper()}</footer>", encoding="utf-8")
    (tmp_path / "email.txt").write_text(f"contato: {email}", encoding="utf-8")
    (tmp_path / "marcador.html").write_text("<p>[A PREENCHER: e-mail] em https://x.github.io/y/</p>", encoding="utf-8")
    achados = {(arquivo, a.split(":")[0]) for arquivo, a in anonimato.verificar_pasta(tmp_path)}
    assert ("nome.html", "autor de commit") in achados and ("email.txt", "autor de commit") in achados
    assert ("marcador.html", "marcador") in achados and not any(arquivo == "limpa.html" for arquivo, _ in achados)
    dono = anonimato.dono_do_repositorio()
    if dono:
        (tmp_path / "dono.xml").write_text(f"https://github.com/{dono}/repo", encoding="utf-8")
        assert any(a.startswith("dono do repositório") for _, a in anonimato.verificar_pasta(tmp_path))


def test_acento_e_maiuscula_nao_escondem_o_achado():
    assert anonimato.achados("FILIPE JEFTÉ", [("autor", "Filipe Jefte")]) == ["autor: Filipe Jefte"]
    assert anonimato.achados("tudo certo", [("autor", "Filipe Jefte")]) == []


def test_o_site_publicado_nao_leva_nada_de_quem_faz(tmp_path):
    """O build como vai ao ar, e outro com todo recurso opcional ligado (contato, Kit, canais, anúncio, estatística)."""
    cfg = configuracao.ler()
    simples = construir(tmp_path / "simples", DIA, cfg=cfg, plataforma="cloudflare")
    assert anonimato.verificar_pasta(simples.saida) == []
    cheio = construir(tmp_path / "cheio", DIA, exemplo=True, plataforma="cloudflare", cfg=configuracao.ler(
        email_contato="contato@exemplo.example", kit_form_id="1234567", canal_telegram="https://t.me/exemplo",
        canal_whatsapp="https://whatsapp.com/channel/exemplo", adsense_client="ca-pub-0000000000000000",
        adsense_slot="123", cloudflare_analytics_token="abc"))
    assert anonimato.verificar_pasta(cheio.saida) == []


def test_resumos_e_legendas_das_varreduras_nao_levam_nada_de_quem_faz():
    arquivos = [p for pasta in VARREDURAS.glob("????-??-??")
                for p in [*pasta.glob("resumo-*"), *pasta.glob("posts/*.txt")]]
    assert anonimato.verificar_arquivos(arquivos, VARREDURAS) == []
