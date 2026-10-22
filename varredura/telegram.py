"""Posta o resumo da semana (resumo-telegram.md) no canal do Telegram, pela Bot API (gratuita).

Credenciais no ambiente (GitHub Secrets ou .env), nunca no código: TELEGRAM_BOT_TOKEN e TELEGRAM_CANAL
(o @nome do canal ou o id numérico; o bot precisa ser administrador do canal).
O Telegram aceita até 4.096 caracteres por mensagem: o resumo é partido entre blocos, sem cortar um concurso.
"""
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

LIMITE = 4096
API = "https://api.telegram.org/bot{token}/sendMessage"


def para_html(texto):
    """Texto do resumo para o parse_mode HTML da Bot API: escapa &, < e > e troca **negrito** por <b>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(texto, quote=False))


def mensagens(texto, limite=LIMITE):
    """Parte o texto em mensagens de até `limite` caracteres, por bloco (linha em branco), depois por linha."""
    blocos = [b.strip("\n") for b in texto.strip().split("\n\n") if b.strip()]
    pedacos = []
    for bloco in blocos:
        if len(bloco) <= limite:
            pedacos.append(bloco)
            continue
        atual = ""
        for linha in bloco.split("\n"):
            while len(linha) > limite:   # linha sozinha maior que o limite: corta seco
                pedacos.append(linha[:limite])
                linha = linha[limite:]
            if atual and len(atual) + 1 + len(linha) > limite:
                pedacos.append(atual)
                atual = linha
            else:
                atual = f"{atual}\n{linha}" if atual else linha
        if atual:
            pedacos.append(atual)
    saida, atual = [], ""
    for p in pedacos:
        if atual and len(atual) + 2 + len(p) > limite:
            saida.append(atual)
            atual = p
        else:
            atual = f"{atual}\n\n{p}" if atual else p
    if atual:
        saida.append(atual)
    return saida


def enviar(token, canal, textos, pausa=1.0):
    """Manda as mensagens em ordem, uma por segundo. Devolve quantas foram."""
    for i, texto in enumerate(textos):
        if i:
            time.sleep(pausa)
        corpo = urllib.parse.urlencode({"chat_id": canal, "text": texto, "parse_mode": "HTML",
                                        "link_preview_options": json.dumps({"is_disabled": True})}).encode()
        pedido = urllib.request.Request(API.format(token=token), data=corpo)
        with urllib.request.urlopen(pedido, timeout=30) as resp:
            resposta = json.loads(resp.read())
        if not resposta.get("ok"):
            raise SystemExit(f"O Telegram recusou a mensagem {i + 1}: {resposta.get('description')}")
    return len(textos)


def postar(pasta, teste=False, se_configurado=False):
    arquivo = Path(pasta) / "resumo-telegram.md"
    if not arquivo.exists():
        raise SystemExit(f"Sem {arquivo}. Rode antes: python -m varredura publicar --por \"Nome\"")
    resumo = arquivo.read_text(encoding="utf-8")
    from gerador.anonimato import achados   # regra 11: o canal não recebe nada de quem faz o Concurseiro
    if achados(resumo):
        raise SystemExit(f"{arquivo} tem dado que não pode ir ao canal ({'; '.join(achados(resumo))}). Nada foi postado.")
    textos = mensagens(para_html(resumo))
    if teste:
        for i, t in enumerate(textos, 1):
            print(f"----- mensagem {i} de {len(textos)} ({len(t)} caracteres) -----\n{t}")
        return 0
    token, canal = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CANAL")
    if not (token and canal):
        if se_configurado:
            print("TELEGRAM_BOT_TOKEN ou TELEGRAM_CANAL não definidos: nada foi postado.")
            return 0
        raise SystemExit("Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CANAL (no .env ou nos GitHub Secrets).")
    n = enviar(token, canal, textos)
    print(f"{n} mensagem(ns) postada(s) no canal.")
    return 0
