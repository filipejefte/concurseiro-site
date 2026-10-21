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
- custo zero: extração sempre aqui, no Claude Code, sem API paga;
- nada sobre quem cria o Concurseiro, em ficha, resumo ou legenda (regra 11).

Rode tudo no PowerShell, a partir da raiz do projeto. Nunca mostre o conteúdo do `.env`.

## 1. Preparar

1. Confira se o `.env` existe e tem `CONTATO_VARREDURA`, `INLABS_EMAIL` e `INLABS_SENHA` preenchidos. Confira só se existem, sem imprimir os valores. Se faltar algo, pare e peça ao Filipe.
2. `python -m pip install -r requirements.txt` (se o ambiente ainda não tiver os pacotes).
3. `python -m pytest -q` precisa passar.

## 2. Coletar

- **Inicial:** `python -m varredura coletar --inicial --desde <data>`
- **Semana:** `python -m varredura coletar --semana`

A coleta inicial demora. São um ZIP do DOU por dia e por seção, um PDF da AMP por dia útil (o texto de cada PDF leva cerca de 1 minuto para sair), no DIOE-PR umas 45 páginas por dia útil, a 1 por segundo, e as páginas de concursos abertos das bancas (FAFIPA, FAU, Quadrix, Omni, Unicampo, Consulplan e Consulpam), com o PDF do edital de cada uma. Rode em segundo plano e espere terminar. O cache em `.cache/` faz uma segunda tentativa não baixar de novo.

Ao terminar, leia `dados/varreduras/<data>/atos.json`:

- Em `fontes`, toda fonte com `falhou` vai para o relatório final, com o motivo. O `DIOE-PR` imprime, por edição, quantas matérias leu e quantas ficaram sem texto (PDF escaneado) ou fora do ar.
- Anote quantos atos estão na fila e quantos PSS ficaram em avaliação.
- O DOU vem do INLABS (login com exceção de robots.txt só para ele). Se o login for recusado, a coleta lê o cache e a fonte fica "parcial", com os dias úteis que faltam: diga isso no relatório e peça ao Filipe os ZIPs desses dias ou uma nova tentativa depois.
- Cada ato de banca entra na fila como `banca-<slug>` e é o edital completo (`python -m varredura previstos` e `dados/cobertura-municipios.csv` saem da mesma coleta).
- **Previstos:** rode `python -m varredura previstos`. Para cada previsto cuja banca já publicou o edital, extraia o edital da fila com o MESMO id do previsto (a ficha vira aberta, com o edital em `documentos`).

## 3. Extrair (aqui no Claude Code, sem custo de API)

`python -m varredura pendentes --resumo` lista os atos da fila que ainda não viraram ficha nem descarte, já na ordem de extração:

- **P1:** inscrição ainda aberta ou com data futura;
- **P2:** autorização ou contratação de banca dos últimos 120 dias (previstos);
- **P3:** o resto (por último, os que só citam datas de inscrição já passadas).

Ato com inscrição já encerrada vira descarte com motivo, sem ficha completa. Trabalhe em lotes de 20 a 30 e, entre um lote e outro, rode `python -m varredura pendentes` e `python -m varredura progresso`. O `progresso.md` da pasta da semana mostra o que falta por fonte e por prioridade; escreva na seção Notas o último lote feito e o que ficou para trás, e por quê. Se a sessão acabar no meio, pare num lote fechado com o `progresso.md` em dia: a próxima sessão retoma dali.

Para cada ato:

1. Leia o arquivo da fila: cabeçalho com fonte, data, classe, órgão, título e url; depois o texto.
2. Siga `varredura/instrucoes_extracao.md` à risca. Estas consultas ajudam:
   - **schema:** `dados/schema/concurso.schema.json`;
   - **códigos IBGE:** `dados/municipios-pr.json`;
   - **id e retificação:** antes de criar um id novo, procure em `dados/concursos.json` e em `fichas/` um concurso do mesmo órgão e edital. Retificação usa o mesmo id e devolve a ficha inteira, com o documento novo.
3. Se o texto do ato não traz o edital completo (anexo em PDF, edital só no site da banca ou do órgão):
   - pode abrir o link oficial (diário, órgão ou banca), uma requisição por vez;
   - PDFs baixados vão para `.cache/`, nunca para o repositório;
   - nunca use PCI, Folha Dirigida ou outro agregador;
   - grave o texto oficial que você usou e que não está no ato da fila (anexo, edital da banca ou do órgão) em `fila/<nome do ato>-extra-<n>.md`, com o mesmo cabeçalho e a url de onde veio, e ponha o nome em `atos_extras`. Sem isso, a conferência automática não enxerga esse texto e a linha cai para o Filipe. O DOU já traz na fila as partes do mesmo edital (`-1`, `-2`... do INLABS); e quando a banca é uma das lidas, o edital dela já está na fila como `banca-<slug>`: basta pôr esse nome em `atos_extras` da ficha feita pelo ato do DOU, em vez de copiar o texto.
4. **Ato que é só o extrato.** Aviso ou extrato no DOU sem os cargos, os salários ou as datas completas (por exemplo "o edital normativo está em www.quadrix.org.br"): a ficha só fica pronta depois de ler o edital completo no site da banca ou do órgão citado no ato. Complete cargos, vagas, salários, requisitos, jornada, taxa, datas e benefícios por ele, ponha o edital completo em `documentos` (primeiro, como `edital`; o extrato do DOU vem depois) e grave o texto como "texto extra" ligado à ficha. "Não informado no edital" só quando o edital completo realmente não traz o dado. Confirme a banca no edital, não só pelo site citado no ato.
4. Escreva o resultado:
   - **Ficha:** `dados/varreduras/<data>/fichas/<id>.json` com `{"ato": "<nome do arquivo da fila>", "trechos": {...}, "concurso": {...}}`.
   - **Descarte:** acrescente `{"ato": "<nome do arquivo da fila>", "motivo": "..."}` à lista em `dados/varreduras/<data>/descartes.json`.

Com muitos atos, trabalhe em lotes e rode `python -m varredura pendentes` entre eles até zerar. Não pare nos atos do Paraná: concurso **federal de qualquer estado** está na cobertura (universidade, instituto federal, conselho, forças armadas, tribunal, ministério). Em 14/10, 413 atos federais de fora do PR ficaram pendentes por isso (ver `docs/DIAGNOSTICO-COBERTURA.md`). `pendentes --resumo` ajuda a descartar rápido o que já encerrou.

## 4. Validar

`python -m varredura validar`

Corrija cada erro voltando ao ato. Se o ato não permite corrigir (por exemplo, falta o link do edital), apague a ficha e registre o descarte com o motivo. Nunca invente valor para passar na validação. Repita até dar "Tudo certo." ou até restarem só problemas que dependem do Filipe.

## 5. Revisão

`python -m varredura revisao`

Gera `revisao.md`, `revisao.csv` e `cobertura.csv` (para conferir à mão a cobertura contra uma listagem pública, só conferir e nunca copiar) na pasta da semana, e refaz `dados/cobertura-municipios.csv`. As matérias do DIOE que o diário não entregou e que têm título de concurso aparecem no `revisao.md` em "Ler à mão". Termine com um resumo curto para o Filipe:

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
1. `python -m gerador build`, `python -m gerador links` e `python -m gerador anonimato`; ofereça `python -m gerador servir` para o Filipe ver o site.
2. Mostre o que mudou (`git status` e `git diff --stat`). Faça commit só se ele pedir, e nunca de `.env`, `.cache/`, `public/`, posts ou PDFs.
3. Push só com o ok dele: o push na `main` publica o site (workflow **Site**) e posta o resumo no Telegram (workflow **Telegram**).
4. Lembre o Filipe de colar o `resumo-whatsapp.txt` no canal do WhatsApp.
