# Rotina semanal do Filipe

Uma vez por semana, de preferência no mesmo dia (a "próxima varredura" da faixa do site é a data da última mais 7 dias). Tempo total: de 1 a 2 horas, quase tudo na conferência.

| # | O que fazer | Onde | Tempo |
| --- | --- | --- | --- |
| 1 | Abrir o Claude Code na pasta do projeto e rodar `/varredura`. Ele coleta, extrai as fichas (sem custo de API), valida e gera a revisão. Para antes de publicar. | Claude Code | 5 min seu (a coleta roda sozinha por 20 a 60 min) |
| 2 | Ler o resumo que o Claude Code escreve no fim: novos, alterados, fontes com problema, linhas para conferir. | Claude Code | 5 min |
| 3 | Abrir `dados/varreduras/<data>/revisao.csv` no Excel. Conferir **só** as linhas com `conferido` vazio e as marcadas `amostra`, contra o ato oficial (link no `revisao.md`). Certo: escrever `ok`. Errado: pedir ao Claude Code para corrigir a ficha e rodar `python -m varredura revisao` de novo. | Excel | 30 a 60 min |
| 4 | (Chico) Comparar o `cobertura.csv` da semana com o PCI, só para ver se faltou concurso. Nunca copiar dado de lá. | Excel e navegador | 20 min |
| 5 | Pedir ao Claude Code: `python -m varredura publicar --por "Filipe"`. Ele mostra o que foi recusado e por quê. | Claude Code | 2 min |
| 6 | Ver o site no computador: `python -m gerador build` e depois `python -m gerador servir`, e abrir o endereço que ele mostra (http://localhost:8000/). Conferir a página inicial e uma ficha nova. | PowerShell e navegador | 5 min |
| 7 | Pedir ao Claude Code commit e push. O push na `main` publica o site sozinho (workflow **Site**) e posta no Telegram (workflow **Telegram**). | Claude Code | 2 min |
| 8 | Conferir no GitHub, aba **Actions**, que **Site** e **Telegram** ficaram verdes, e abrir https://concurseiro.pages.dev. | GitHub e navegador | 3 min |
| 9 | Abrir `dados/varreduras/<data>/resumo-whatsapp.txt`, copiar tudo e colar no canal do WhatsApp. | WhatsApp | 3 min |
| 10 | (Opcional) Postar no Instagram as imagens de `dados/varreduras/<data>/posts/`, com a legenda do `.txt` de cada uma. | Instagram | 10 min |

Fora da rotina:
- O site roda o build todo dia às 06:00: concurso que encerra sai dos abertos sozinho, sem varredura.
- Se o workflow **Site** ficar vermelho, peça ao Claude Code para olhar o log no GitHub e corrigir.
- E-mail pelo Kit (quando ligado): colar o mesmo resumo num **Broadcast** do Kit.
