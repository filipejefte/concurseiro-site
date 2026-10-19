# Arquivos da marca

Descompacte aqui o pacote `marca-concurseiro.zip` (logotipos SVG, `bundle.css`, `tokens.json`, `voz.md`, `nome.md`). Eles são a fonte da verdade visual e de texto: o logotipo nunca é redigitado, e os textos seguem `voz.md` e `nome.md`.

O que o gerador usa, quando existir:

| Arquivo | Onde vai |
| --- | --- |
| `logotipo-concurseiro.svg` ou `.png` | `<img>` do cabeçalho (32 px de altura no computador, 28 px no celular); o `.png` também vai nas imagens de compartilhamento e nos posts |
| `logotipo-concurseiro-palavra.svg` ou `.png` | rodapé |
| `favicon.svg` | ícone da aba (sem ele, vale `assets/img/favicon.svg`, o do protótipo) |
| `icone-app.png` | `apple-touch-icon.png` (180 px) e os ícones do manifest (192 e 512 px) |
| `design-system/bundle.css` | referência para sincronizar `assets/css/componentes.css` |

O pacote novo já traz os PNG, então o gerador não precisa do `cairosvg`.

Sem estes arquivos, o build avisa e usa o logotipo provisório do protótipo.

Depois de pôr os arquivos aqui: `python -m gerador build`, conferir o site com `python -m gerador servir` e pedir ao Claude Code para sincronizar `assets/css/componentes.css` com o `bundle.css` e revisar os textos das páginas com `voz.md` e `nome.md`.
