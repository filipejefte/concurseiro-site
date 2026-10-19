# Arquivos da marca

Pacote `marca-concurseiro.zip`, copiado do design system em 16/10/2026 (veja `LEIA-ME.txt`). Estes arquivos são a fonte da verdade visual e de texto: o logotipo nunca é redigitado, e os textos seguem `design-system/voz.md` e `design-system/nome.md`.

| Arquivo | Onde o gerador usa |
| --- | --- |
| `logotipo-concurseiro.svg` | `<img>` do cabeçalho (32 px de altura no computador, 28 px no celular) |
| `logotipo-concurseiro-palavra.svg` | rodapé |
| `logotipo-concurseiro.png` | imagens de compartilhamento (1200×630) |
| `logotipo-concurseiro-palavra.png` | pé dos posts (1080×1350), também sobre o verde |
| `favicon.svg` | ícone da aba |
| `icone-app.png` | `apple-touch-icon.png` (180 px, cantos em verde para o iOS) e ícones do manifest (192 e 512 px) |
| `design-system/bundle.css` | `assets/css/componentes.css` é este arquivo mais o logotipo provisório (só usado se faltar arquivo aqui) |
| `design-system/tokens.json` | `assets/css/tokens.css` (tema claro; conferido em 19/10/2026) |
| `grifo.svg`, `icone-app.svg` | peças gráficas fora do site |

Quando o design system mudar: troque os arquivos aqui, rode `python -m gerador build`, confira com `python -m gerador servir` e peça ao Claude Code para sincronizar `componentes.css` e `tokens.css`.
