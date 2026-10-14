# concurseiro: MVP v0

Site gratuito que reúne os concursos públicos **federais e do Paraná** com inscrição aberta: salário na frente, prazos, localização e sempre o caminho para o edital oficial. "concurseiro" é nome provisório. No ar em https://filipejefte.github.io/concurseiro-site/ (fora do Google na v0).

> **Dados de exemplo até a primeira varredura.** Enquanto a primeira varredura real não for publicada, o site mostra 12 concursos fictícios (`dados/exemplo/`), com aviso em todas as páginas. Todas as páginas têm `noindex` e o `robots.txt` bloqueia buscadores até os sócios decidirem abrir o site.

## Como funciona

1. Uma vez por semana, o Filipe roda `/varredura` no Claude Code:
   - a varredura lê os diários oficiais;
   - separa os atos sobre concurso;
   - monta a ficha de cada um a partir do ato oficial;
   - gera uma planilha de revisão.
2. Uma pessoa confere os campos críticos de cada concurso novo ou alterado: salário de cada cargo, início e fim da inscrição, prova objetiva, taxa, banca, cidade e link do edital.
3. `python -m varredura publicar` leva para `dados/concursos.json` só o que foi conferido, gera `assets/js/dados.js` e escreve o resumo da semana para o Telegram.
4. O commit e o push publicam o site estático no GitHub Pages. Não há banco, servidor nem serviço pago.

## Rodar o site

No PowerShell, na pasta do projeto:

```powershell
python -m http.server 8000
```

Depois abra http://localhost:8000. Abrir o `index.html` com dois cliques também funciona (os dados vêm de `assets/js/dados.js`), mas aí o navegador bloqueia a fonte da marca e usa a do sistema.

| Página | Arquivo | O que faz |
| --- | --- | --- |
| Início | `index.html` | Concursos perto da cidade escolhida (ou do Paraná, por prazo), inscrições que encerram na semana, áreas e nacionais |
| Listagem | `concursos.html` | Busca, ordenação e filtros, com o estado na URL; `?perto=<IBGE>` mede a distância a partir de outra cidade |
| Ficha | `concurso.html?id=<id>` | Salário, vagas, inscrição e prova, conteúdo, documentos e "Ver edital oficial" |
| Cidade | `cidade.html?ibge=<código>` | Concursos na cidade e a até 50 km; `cidade-maringa.html` redireciona para cá |
| Avise-me | em todas | Com `canalTelegram: null` em `assets/js/config.js`, diz "Alertas em breve"; com a URL do canal, mostra "Entrar no canal do Telegram". Não há formulário nem coleta de dado pessoal |

**Cidade.**
- Não há cidade padrão: a pessoa escolhe entre os 399 municípios do PR.
- A escolha fica no aparelho (`localStorage`).
- O GPS é opcional e só acha o município mais próximo pela tabela.
- A distância é calculada por haversine.

**Faixa de atualização.** Toda página traz a data da varredura, a da próxima e a cobertura. Os dados vêm de `dados/concursos.json`.

## Varredura semanal

### Preparar (uma vez)

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Preencha o `.env`, que fica fora do git:

| Variável | Para quê |
| --- | --- |
| `CONTATO_VARREDURA` | Contato que vai no User-Agent; obrigatório para coletar |
| `INLABS_EMAIL`, `INLABS_SENHA` | Acesso ao DOU pelo INLABS (cadastro gratuito em https://inlabs.in.gov.br) |
| `CONFERENTE` | Nome de quem confere |
| `ANTHROPIC_API_KEY` | Só para `--modo api` |

### Rodar

O caminho normal é o comando `/varredura` no Claude Code: `/varredura inicial 2026-07-01` na primeira vez, `/varredura` nas seguintes. Ele faz as etapas abaixo e para antes de publicar. À mão:

```powershell
python -m varredura coletar --inicial --desde 2026-07-01   # primeira vez
python -m varredura coletar --semana                       # semanal
python -m varredura pendentes                              # atos da fila ainda sem ficha
python -m varredura validar
python -m varredura revisao
```

- **coletar** lê as fontes, faz a triagem e põe em `dados/varreduras/AAAA-MM-DD/fila/` um arquivo por ato.
  - **Triagem:** classifica cada ato em abertura, retificação, autorização, contratação de banca, resultado ou outro. Processo seletivo simplificado fica marcado e não é publicado.
  - **Extração `--modo claude-code`** (padrão, sem custo de API): o Claude Code lê cada arquivo e escreve a ficha seguindo `varredura/instrucoes_extracao.md`.
  - **Extração `--modo api`:** usa `claude-haiku-5-5` com a `ANTHROPIC_API_KEY`.
- **validar** checa:
  - o schema (`dados/schema/concurso.schema.json`);
  - fim da inscrição depois do início;
  - salário maior que zero ou `null`;
  - link do edital de diário oficial, órgão ou banca (agregador é recusado);
  - município existente na tabela.
- **revisao** compara com o que está publicado (novos, alterados e encerrados) e gera `revisao.md` e `revisao.csv` na pasta da semana.

As fontes são lidas com boas maneiras:
- respeito ao `robots.txt`;
- no máximo 1 requisição por segundo;
- User-Agent com contato;
- cache em `.cache/`, fora do git, com PDFs incluídos.

| Fonte | Como é lida |
| --- | --- |
| Diário Oficial da União | INLABS: um ZIP de XML por dia e por seção (DO1 e DO3), últimos 4 meses |
| Diário Oficial dos Municípios do PR (AMP) | Um PDF por dia útil; cada matéria vira um ato com link próprio (`/amp/materia/<código>`). O texto de cada edição leva cerca de 1 min para sair |
| Diário Oficial do Paraná (DIOE) | Ainda não: esboço com TODO em `varredura/fontes/diario_estado_pr.py` |

### Conferir e publicar

1. Abra `dados/varreduras/AAAA-MM-DD/revisao.csv` no Excel ou no LibreOffice. Ele vem em UTF-8 e separado por `;`.
2. Para cada linha, compare o valor com o trecho e com o ato oficial (link em `revisao.md`) e escreva `ok` na coluna **conferido**.
3. Se o valor estiver errado, corrija `fichas/<id>.json`, rode `python -m varredura revisao` de novo (as marcas das linhas que não mudaram ficam) e marque `ok`. `corrigir` segura o concurso.
4. Publique:

```powershell
python -m varredura publicar --por "Filipe"
```

O `publicar`:
- recusa concurso com campo crítico sem `ok`, ou com valor mudado depois da conferência, e diz o motivo;
- atualiza `dados/concursos.json` com a data da varredura e da próxima (+7 dias);
- gera `assets/js/dados.js`;
- escreve `resumo-telegram.md` na pasta da semana.

Confira o site local e, se estiver tudo certo, faça commit e push.

Para voltar o site aos exemplos fictícios: `python -m varredura publicar --exemplo`.

### Testes

```powershell
python -m pytest
```

## Estrutura

```
index.html, concursos.html, concurso.html, cidade.html, cidade-maringa.html (redireciona)
assets/css/       tokens.css, componentes.css (cc-), site.css (pt-)
assets/js/        config.js, dados.js (gerado), app.js
assets/fonts/     Schibsted Grotesk (licença SIL Open Font License 1.1)
dados/            schema, concursos.json, municipios-pr.json, exemplo/, varreduras/
varredura/        pacote Python da varredura (fontes/, triagem, extração, validação, revisão, publicação)
tests/            pytest
.claude/commands/varredura.md   passo a passo semanal para o Claude Code
CLAUDE.md         regras fixas e o que nunca fazer
```

HTML, CSS e JavaScript puro, sem framework e sem etapa de build.

## Tabela de municípios

`dados/municipios-pr.json` tem os 399 municípios do Paraná com código IBGE, nome e coordenadas. Foi gerada em **14/10/2026** com `python -m varredura municipios`:

| Dado | Fonte | Licença |
| --- | --- | --- |
| Códigos e nomes | API de localidades do IBGE: `https://servicodados.ibge.gov.br/api/v1/localidades/estados/41/municipios` | Dado público oficial |
| Coordenadas | Repositório [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros), arquivo `csv/municipios.csv` | MIT (Copyright 2016 Kelvin S. do Prado) |

Os 399 códigos do IBGE batem com os do repositório, e os nomes também. As cidades dos exemplos (Vale Verde, Campo Alto, Serra Azul e Rio do Campo) são fictícias. Elas ficam em `dados/exemplo/municipios-ficticios.json`, com códigos na faixa 41999xx, que o IBGE não usa, e nunca entram na tabela real.

## Regras que o código segue

- O site nunca recebe inscrição nem pagamento. O botão principal da ficha é "Ver edital oficial".
- Toda ficha vem de ato oficial, com link. Agregadores não são fonte.
- O que o edital não traz aparece como "Não informado no edital".
- Nada vai ao ar sem conferência humana dos campos críticos.
- Nenhum dado pessoal é coletado na v0. Alerta, quando existir, só com opt-in.
- Anúncio leva "Publicidade"; indicação paga leva "Link de parceiro" e `rel="sponsored"`.
- "Previsto" só com ato oficial de autorização do concurso ou de contratação da banca.
- PDFs de editais não entram no repositório.

## Pendente

- Implementar a fonte do Diário Oficial do Paraná (formato e acesso ainda não verificados).
- Política de privacidade, página "Como conferimos os dados" e o canal do Telegram (`assets/js/config.js`).
- Trocar o nome provisório no logotipo quando o nome for decidido.
- Decisão dos sócios sobre abrir o site aos buscadores (tirar `noindex` e mudar o `robots.txt`).
