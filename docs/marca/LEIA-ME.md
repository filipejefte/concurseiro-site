# Arquivos da marca

Descompacte aqui o pacote `marca-concurseiro.zip` (logotipos SVG, `bundle.css`, `tokens.json`, `voz.md`, `nome.md`). Eles são a fonte da verdade visual e de texto: o logotipo nunca é redigitado, e os textos seguem `voz.md` e `nome.md`.

O que o gerador usa, quando existir:

| Arquivo | Onde vai |
| --- | --- |
| `logotipo-concurseiro.svg` | `<img>` do cabeçalho (32 px de altura no computador, 28 px no celular) e logotipo das imagens de compartilhamento e dos posts* |
| `logotipo-concurseiro-palavra.svg` | rodapé |
| `favicon.svg` | ícone da aba (sem ele, vale `assets/img/favicon.svg`, o do protótipo) |
| `icone-app.svg` | `apple-touch-icon.png` (180 px) e os ícones do manifest (192 e 512 px)* |

\* Para virar PNG, o SVG precisa do `cairosvg` (`python -m pip install cairosvg`, que no Windows pede a biblioteca Cairo). Se o pacote trouxer `logotipo-concurseiro.png` e `icone-app.png`, o gerador usa os PNG direto e não precisa do `cairosvg`.

Sem estes arquivos, o build avisa e usa o logotipo provisório do protótipo.

Depois de pôr os arquivos aqui: `python -m gerador build`, conferir o site com `python -m gerador servir` e pedir ao Claude Code para sincronizar `assets/css/componentes.css` com o `bundle.css` e revisar os textos das páginas com `voz.md` e `nome.md`.
