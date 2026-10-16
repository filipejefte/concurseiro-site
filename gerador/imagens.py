"""Imagens geradas com Pillow: compartilhamento (1200×630), posts (1080×1350) e ícones do app.

Layout do PostSocial do design system: fundo papel (verde quando faltam 7 dias ou menos), salário grifado,
órgão, prazo e o logotipo. A fonte é a Schibsted Grotesk do site: o woff2 variável vira TTF estático
(fontTools) no .cache/, uma vez por peso.

O logotipo nunca é redigitado: com docs/marca/logotipo-concurseiro.png (ou o SVG e o cairosvg instalado),
ele é colado; sem os arquivos da marca, sai a versão provisória do protótipo (ícone + palavra grifada).
"""
import hashlib
import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
WOFF2 = RAIZ / "assets" / "fonts" / "schibsted-grotesk-latin-wght-normal.woff2"
CACHE = RAIZ / ".cache" / "fontes"
MARCA = RAIZ / "docs" / "marca"

PAPEL, TINTA, TINTA_SUAVE = "#f7f6f1", "#14211b", "#56625b"
VERDE, GRIFO, PRAZO, PREVISTO, LINHA = "#0b6b48", "#d6f26a", "#9c4308", "#4b5872", "#dedbd0"

_fontes = {}


def fonte(peso, tamanho):
    """ImageFont da Schibsted Grotesk no peso pedido (400 a 900)."""
    chave = (peso, tamanho)
    if chave not in _fontes:
        ttf = CACHE / f"schibsted-grotesk-{peso}.ttf"
        if not ttf.exists():
            from fontTools.ttLib import TTFont            # pip install fonttools brotli
            from fontTools.varLib.instancer import instantiateVariableFont
            CACHE.mkdir(parents=True, exist_ok=True)
            estatica = instantiateVariableFont(TTFont(WOFF2), {"wght": peso})
            estatica.flavor = None
            estatica.save(ttf)
        _fontes[chave] = ImageFont.truetype(str(ttf), tamanho)
    return _fontes[chave]


def _largura(desenho, texto, f):
    return desenho.textlength(texto, font=f)


def quebrar(desenho, texto, f, largura, linhas=2):
    """Quebra em até `linhas` linhas; corta com reticências o que sobrar."""
    palavras, saida, atual = texto.split(), [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if _largura(desenho, teste, f) <= largura or not atual:
            atual = teste
        else:
            saida.append(atual)
            atual = p
    saida.append(atual)
    if len(saida) > linhas:
        saida = saida[:linhas]
        ultima = saida[-1]
        while ultima and _largura(desenho, ultima + "…", f) > largura:
            ultima = ultima[:-1].rstrip()
        saida[-1] = ultima + "…"
    return saida


def grifo(desenho, caixa, cor=GRIFO):
    """O marca-texto da marca: paralelogramo inclinado (-12°) e levemente girado (-1,5°) atrás do texto."""
    x0, y0, x1, y1 = caixa
    s = (y1 - y0) / 2 * math.tan(math.radians(12))
    pontos = [(x0 + s, y0), (x1 + s, y0), (x1 - s, y1), (x0 - s, y1)]
    cx, cy, a = (x0 + x1) / 2, (y0 + y1) / 2, math.radians(-1.5)
    girar = lambda px, py: (cx + (px - cx) * math.cos(a) - (py - cy) * math.sin(a), cy + (px - cx) * math.sin(a) + (py - cy) * math.cos(a))
    desenho.polygon([girar(*p) for p in pontos], fill=cor)


def texto_grifado(desenho, xy, texto, f, cor_texto=TINTA, cor_grifo=GRIFO):
    x, y = xy
    esq, topo, dir_, base = desenho.textbbox((x, y), texto, font=f)
    sobra = (base - topo) * 0.16
    grifo(desenho, (esq - sobra, topo - sobra * 0.6, dir_ + sobra, base + sobra * 0.7), cor_grifo)
    desenho.text((x, y), texto, font=f, fill=cor_texto)
    return dir_ + sobra


def _icone(lado):
    """O ícone do protótipo (favicon.svg): quadrado verde arredondado e o grifo. Desenhado em 4× e reduzido."""
    g = lado * 4
    img = Image.new("RGBA", (g, g), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = g / 64
    d.rounded_rectangle((0, 0, g - 1, g - 1), radius=15 * k, fill=VERDE)
    d.polygon([(15 * k, 25 * k), (53 * k, 22 * k), (49 * k, 41 * k), (11 * k, 44 * k)], fill=GRIFO)
    return img.resize((lado, lado), Image.LANCZOS)


def _svg_para_png(svg, largura):
    try:
        import cairosvg  # opcional: só para rasterizar os SVG da marca
    except ImportError:
        return None
    return Image.open(io.BytesIO(cairosvg.svg2png(url=str(svg), output_width=largura))).convert("RGBA")


def logotipo(altura, claro=False):
    """Imagem do logotipo na altura pedida: o arquivo da marca, se existir; senão o provisório."""
    for png in (MARCA / "logotipo-concurseiro.png",):
        if png.exists():
            img = Image.open(png).convert("RGBA")
            return img.resize((round(img.width * altura / img.height), altura), Image.LANCZOS)
    svg = MARCA / "logotipo-concurseiro.svg"
    if svg.exists():
        img = _svg_para_png(svg, altura * 8)
        if img is not None:
            return img.resize((round(img.width * altura / img.height), altura), Image.LANCZOS)
    f = fonte(800, round(altura * 0.78))
    medida = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    largura = round(altura * 1.35 + medida.textlength("concurseiro", font=f) + altura * 0.4)
    img = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    img.alpha_composite(_icone(altura), (0, 0))
    d = ImageDraw.Draw(img)
    texto_grifado(d, (round(altura * 1.35), round(altura * 0.04)), "concurseiro", f, TINTA)
    return img


def icone_app(lado):
    """PNG quadrado para apple-touch-icon e manifest: icone-app.svg da marca, ou o ícone do protótipo."""
    for png in (MARCA / "icone-app.png",):
        if png.exists():
            return Image.open(png).convert("RGBA").resize((lado, lado), Image.LANCZOS)
    svg = MARCA / "icone-app.svg"
    if svg.exists():
        img = _svg_para_png(svg, lado)
        if img is not None:
            return img
    fundo = Image.new("RGBA", (lado, lado), PAPEL)   # o iOS não aceita transparência no apple-touch-icon
    fundo.alpha_composite(_icone(lado))
    return fundo


def cartao(largura, altura, *, tag, orgao, salario, linhas, rodape, verde=False, cor_tag=VERDE,
           sem_salario="Salário: não informado no edital"):
    """Desenha o cartão (OG 1200x630 e post 1080x1350) e devolve a imagem RGB.

    O bloco de texto é desenhado numa camada à parte: no OG fica no topo; no post (retrato), letras maiores
    e o bloco centrado na altura que sobra acima do rodapé.
    """
    fundo, tinta, suave = (VERDE, "#ffffff", "#e5f1ea") if verde else (PAPEL, TINTA, TINTA_SUAVE)
    retrato = altura > largura
    img = Image.new("RGB", (largura, altura), fundo)
    camada = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    m = round(largura * (0.074 if retrato else 0.06))
    escala = largura / (860 if retrato else 1200)
    y = 0
    d.text((m, y), tag.upper(), font=fonte(700, round(26 * escala)), fill="#ffffff" if verde else cor_tag)
    y += round(56 * escala)
    tamanho_orgao = round(54 * escala)
    for linha in quebrar(d, orgao, fonte(800, tamanho_orgao), largura - 2 * m, linhas=3 if retrato else 2):
        d.text((m, y), linha, font=fonte(800, tamanho_orgao), fill=tinta)
        y += round(tamanho_orgao * 1.12)
    y += round(28 * escala)
    if salario:
        d.text((m, y), "Salário inicial", font=fonte(600, round(26 * escala)), fill=suave)
        y += round(40 * escala)
        f = fonte(800, round(92 * escala))
        while d.textlength(salario, font=f) > largura - 2 * m - 16 and f.size > 40:
            f = fonte(800, f.size - 4)
        texto_grifado(d, (m + round(8 * escala), y), salario, f, TINTA)
        y += round(f.size * 1.45)
    else:
        d.text((m, y), sem_salario, font=fonte(700, round(40 * escala)), fill=tinta)
        y += round(64 * escala)
    for linha in linhas:
        for parte in quebrar(d, linha, fonte(600, round(32 * escala)), largura - 2 * m, linhas=2):
            d.text((m, y), parte, font=fonte(600, round(32 * escala)), fill=tinta)
            y += round(44 * escala)
    # Rodapé: logotipo à esquerda, endereço à direita.
    alt_logo = round(48 * (escala if not retrato else escala * 0.9))
    logo = logotipo(alt_logo)
    if verde:
        placa = Image.new("RGBA", (logo.width + round(24 * escala), alt_logo + round(16 * escala)), PAPEL)
        placa.alpha_composite(logo, (round(12 * escala), round(8 * escala)))
        logo = placa
    base_y = altura - m - logo.height
    topo = m if not retrato else max(m, (base_y - y) // 2)
    img.paste(camada, (0, topo), camada)
    img.paste(logo, (m, base_y), logo)
    d = ImageDraw.Draw(img)
    f_rod = fonte(600, round(24 * min(escala, 1.15)))
    w = d.textlength(rodape, font=f_rod)
    d.text((largura - m - w, base_y + (logo.height - f_rod.size) / 2), rodape, font=f_rod, fill=suave)
    return img


def dados_do_cartao(x):
    """Tag, salário e linhas de um modelo.Concurso (OG e post usam os mesmos dados)."""
    tag = {"aberto": "Inscrições abertas", "breve": x.selo, "previsto": "Concurso previsto", "encerrado": "Inscrições encerradas"}[x.situacao]
    cor = {"breve": PRAZO, "previsto": PREVISTO, "encerrado": TINTA_SUAVE}.get(x.situacao, VERDE)
    linhas = []
    if x.situacao in ("aberto", "breve") and x.fim:
        linhas.append(f"Inscrições até {x.prazo}")
    elif x.situacao == "previsto":
        linhas.append(f"Banca {x.banca}" if x.banca else "Banca a definir")
    linhas.append(" · ".join(t for t in [x.local, x.vagas if x.cargos else ""] if t))
    return tag, cor, linhas


def assinatura(*partes):
    return hashlib.sha1(repr(partes).encode()).hexdigest()[:16]


def _sem_salario(x):
    return "Salário: ainda sem edital" if x.edital is None else "Salário: não informado no edital"


def og_concurso(x, rodape):
    tag, cor, linhas = dados_do_cartao(x)
    return cartao(1200, 630, tag=tag, orgao=x.orgao, salario=x.salario, linhas=linhas, rodape=rodape, cor_tag=cor,
                  sem_salario=_sem_salario(x))


def post_concurso(x, rodape):
    tag, cor, linhas = dados_do_cartao(x)
    verde = x.situacao == "breve"
    return cartao(1080, 1350, tag=tag, orgao=x.orgao, salario=x.salario, linhas=linhas, rodape=rodape, verde=verde, cor_tag=cor,
                  sem_salario=_sem_salario(x))


def og_padrao(titulo, subtitulo, rodape):
    img = Image.new("RGB", (1200, 630), PAPEL)
    d = ImageDraw.Draw(img)
    logo = logotipo(96)
    img.paste(logo, (72, 72), logo)
    y = 250
    for linha in quebrar(d, titulo, fonte(800, 64), 1056, linhas=2):
        d.text((72, y), linha, font=fonte(800, 64), fill=TINTA)
        y += 74
    for linha in quebrar(d, subtitulo, fonte(600, 34), 1056, linhas=2):
        d.text((72, y + 16), linha, font=fonte(600, 34), fill=TINTA_SUAVE)
        y += 46
    f = fonte(600, 24)
    d.text((1128 - d.textlength(rodape, font=f), 558 - 24), rodape, font=f, fill=TINTA_SUAVE)
    return img


def salvar_png(img, caminho):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    img.save(caminho, "PNG", optimize=True)
