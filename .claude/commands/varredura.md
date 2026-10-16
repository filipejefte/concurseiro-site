---
description: Varredura semanal de concursos (federais e do Paraná), da coleta à revisão. Para antes de publicar.
argument-hint: "[inicial AAAA-MM-DD | semana]"
---

# Varredura semanal

Argumentos: `$ARGUMENTS` (vazio = `semana`; `inicial 2026-06-16` = varredura inicial desde a data; o INLABS guarda 4 meses).

Antes de tudo, leia o `CLAUDE.md` da raiz. As regras fixas valem para cada ficha, sobretudo estas:

- só ato oficial, com link;
- `null` no que o ato não traz;
- nada de agregador;
- nada vai ao ar sem conferência: a automática acha o valor no texto do ato, ou o Filipe confere;
- custo zero: extração sempre aqui, no Claude Code; nunca `--modo api`.

Rode tudo no PowerShell, a partir da raiz do projeto. Nunca mostre o conteúdo do `.env`.

## 1. Preparar

1. Confira se o `.env` existe e tem `CONTATO_VARREDURA`, `INLABS_EMAIL` e `INLABS_SENHA` preenchidos. Confira só se existem, sem imprimir os valores. Se faltar algo, pare e peça ao Filipe.
2. `python -m pip install -r requirements.txt` (se o ambiente ainda não tiver os pacotes).
3. `python -m pytest -q` precisa passar.

## 2. Coletar

- **Inicial:** `python -m varredura coletar --inicial --desde <data>`
- **Semana:** `python -m varredura coletar --semana`

A coleta inicial demora. São um ZIP do DOU por dia e por seção, e um PDF da AMP por dia útil, e o texto de cada PDF leva cerca de 1 minuto para sair. Rode em segundo plano e espere terminar. O cache em `.cache/` faz uma segunda tentativa não baixar de novo.

Ao terminar, leia `dados/varreduras/<data>/atos.json`:

- Em `fontes`, toda fonte com `falhou` vai para o relatório final, com o motivo. O `DIOE-PR` aparece como `pulada` até ser implementado; isso é esperado.
- Anote quantos atos estão na fila e quantos PSS ficaram em avaliação.

## 3. Extrair (modo claude-code, sem custo de API)

`python -m varredura pendentes` lista os atos da fila que ainda não viraram ficha nem descarte. Para cada um:

1. Leia o arquivo da fila: cabeçalho com fonte, data, classe, órgão, título e url; depois o texto.
2. Siga `varredura/instrucoes_extracao.md` à risca. Estas consultas ajudam:
   - **schema:** `dados/schema/concurso.schema.json`;
   - **códigos IBGE:** `dados/municipios-pr.json`;
   - **id e retificação:** antes de criar um id novo, procure em `dados/concursos.json` e em `fichas/` um concurso do mesmo órgão e edital. Retificação usa o mesmo id e devolve a ficha inteira, com o documento novo.
3. Se o texto do ato não traz o edital completo (anexo em PDF, edital só no site da banca ou do órgão):
   - pode abrir o link oficial (diário, órgão ou banca), uma requisição por vez;
   - PDFs baixados vão para `.cache/`, nunca para o repositório;
   - nunca use PCI, Folha Dirigida ou outro agregador;
   - grave o texto oficial que você usou e que não está no ato da fila (outras matérias do mesmo edital, anexo, edital da banca) em `fila/<nome do ato>-extra-<n>.md`, com o mesmo cabeçalho e a url de onde veio, e ponha o nome em `atos_extras`. Sem isso, a conferência automática não enxerga esse texto e a linha cai para o Filipe.
4. Escreva o resultado:
   - **Ficha:** `dados/varreduras/<data>/fichas/<id>.json` com `{"ato": "<nome do arquivo da fila>", "trechos": {...}, "concurso": {...}}`.
   - **Descarte:** acrescente `{"ato": "<nome do arquivo da fila>", "motivo": "..."}` à lista em `dados/varreduras/<data>/descartes.json`.

Com muitos atos, trabalhe em lotes e rode `python -m varredura pendentes` entre eles até zerar. Não pare nos atos do Paraná: concurso **federal de qualquer estado** está na cobertura (universidade, instituto federal, conselho, forças armadas, tribunal, ministério). Em 14/10, 413 atos federais de fora do PR ficaram pendentes por isso (ver `docs/DIAGNOSTICO-COBERTURA.md`). `pendentes --resumo` ajuda a descartar rápido o que já encerrou.

Não use `--modo api`: é pago, e a regra do projeto é custo zero.

## 4. Validar

`python -m varredura validar`

Corrija cada erro voltando ao ato. Se o ato não permite corrigir (por exemplo, falta o link do edital), apague a ficha e registre o descarte com o motivo. Nunca invente valor para passar na validação. Repita até dar "Tudo certo." ou até restarem só problemas que dependem do Filipe.

## 5. Revisão

`python -m varredura revisao`

Gera `revisao.md`, `revisao.csv` e `cobertura.csv` (para o Chico comparar à mão com o PCI) na pasta da semana. Termine com um resumo curto para o Filipe:

- quantos concursos são novos, alterados (retificações) e encerrados;
- fontes com problema e fichas com erro de validação;
- PSS em avaliação e atos ainda pendentes;
- os caminhos de `revisao.md` e `revisao.csv`;
- a linha **Conferência** do `revisao.md`: quantas linhas a automática achou no ato e quantas ficaram para o Filipe;
- o próximo passo: no `revisao.csv`, conferir só as linhas com **conferido** vazio e as `amostra` contra o ato e marcar `ok` (ou `corrigir`).

## 6. Pare aqui

**Não publique.** Espere o Filipe conferir.

Só quando ele pedir, rode `python -m varredura publicar --por "Filipe"`. O comando recusa o que não foi conferido e mostra o motivo; repasse ao Filipe cada concurso recusado. Ele escreve na pasta da semana `resumo-telegram.md`, `resumo-whatsapp.txt` e `posts/` (imagens e legendas, fora do git).

Depois:
1. `python -m gerador build` e `python -m gerador links`; ofereça `python -m gerador servir` para o Filipe ver o site.
2. Mostre o que mudou (`git status` e `git diff --stat`). Faça commit só se ele pedir, e nunca de `.env`, `.cache/`, `public/`, posts ou PDFs.
3. Push só com o ok dele: o push na `main` publica o site (workflow **Site**) e posta o resumo no Telegram (workflow **Telegram**).
4. Lembre o Filipe de colar o `resumo-whatsapp.txt` no canal do WhatsApp.
