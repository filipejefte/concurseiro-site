# Concurseiro

Site gratuito que reúne os concursos públicos **federais (do Brasil todo) e do Paraná** com inscrição aberta: salário na frente, prazos, localização e sempre o caminho para o edital oficial. No ar em https://filipejefte.github.io/concurseiro-site/ (fora dos buscadores até os sócios decidirem).

Custo fixo: só o domínio. Não há banco, servidor, API paga nem serviço pago.

## Como funciona

1. Uma vez por semana, o Filipe roda `/varredura` no Claude Code. A varredura lê os diários oficiais, separa os atos de concurso, monta a ficha de cada um a partir do ato oficial (o próprio Claude Code extrai, sem API paga) e gera a planilha de revisão.
2. A conferência automática procura cada campo crítico no texto do ato; uma pessoa confere o resto e uma amostra de 1 em 20.
3. `python -m varredura publicar` leva para `dados/concursos.json` só o que foi conferido e escreve os resumos da semana (Telegram e WhatsApp) e os posts.
4. O push na `main` dispara o GitHub Actions: testes, `python -m gerador build`, verificador de links e deploy (Cloudflare Pages com os segredos; senão, GitHub Pages). O build também roda todo dia às 06:00, para a situação e os prazos virarem sem nova varredura. Um resumo novo na `main` é postado no canal do Telegram.

Passo a passo dos painéis (domínio, Cloudflare, segredos, Telegram, WhatsApp, Kit): [`docs/LANCAMENTO.md`](docs/LANCAMENTO.md). Rotina da semana: [`docs/ROTINA-SEMANAL.md`](docs/ROTINA-SEMANAL.md).

## Instalar

No PowerShell, na pasta do projeto (Python 3.11 ou mais novo):

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env      # preencha; o .env fica fora do git
python -m pytest
```

## O site

O site é gerado: páginas HTML prontas em `public/` (fora do git), a partir de `dados/concursos.json` e do `site.toml`.

```powershell
python -m gerador build              # gera public/ (só os concursos publicados)
python -m gerador build --exemplo    # junta os 12 concursos fictícios, marcados como exemplo
python -m gerador servir             # http://localhost:8000/concurseiro-site/
python -m gerador links              # confere os links internos (o CI roda)
```

| Endereço | O que é |
| --- | --- |
| `/` | Início: número de concursos abertos (grifado; previstos à parte), abertos com salário primeiro, encerram na semana, áreas, federais, previstos, cidades |
| `/concursos/` | Todos os abertos e os previstos no HTML; o JavaScript busca, filtra, ordena e mede a distância |
| `/concurso/<id>/` | Ficha: salário, vagas, escolaridade, inscrição e prova, taxa, banca, cidade, documentos, "Ver edital oficial", agenda (.ics) e "Mandar no WhatsApp". Encerrado mantém a página, com abertos parecidos |
| `/cidade/<slug>/` | Só cidades com concurso na cidade ou a até 50 km |
| `/area/<slug>/`, `/banca/<slug>/`, `/estado/pr/`, `/federais/`, `/previstos/`, `/encerram-esta-semana/` | Listas |
| `/sobre/`, `/como-conferimos/`, `/privacidade/`, `/termos/`, `/contato/`, `/alertas/` | Institucionais |
| `concurso.html?id=`, `cidade.html?ibge=`, `concursos.html`, `cidade-maringa.html` | Endereços do protótipo: levam ao endereço novo |

Com o JavaScript desligado, toda página continua útil. O JavaScript só acrescenta o que depende da pessoa:
- cidade escolhida, distância e GPS opcional, tudo no aparelho; sugestão de cidade pelo IP só no Cloudflare (`functions/api/local.js`, sem gravar nada);
- perfil de escolaridade (o card mostra o salário do cargo que a pessoa pode fazer);
- filtros, contagem até a prova e "Este concurso é pra você?".

SEO: `title` e `description` por página, `canonical`, `sitemap.xml` com `lastmod` (encerrado sai 90 dias depois do fim), Open Graph e Twitter Card com imagem 1200×630 por concurso, JSON-LD `WebSite` e `BreadcrumbList`. Sem `JobPosting` (o Google não aceita vaga que cobra taxa).

### site.toml

| Campo | Para quê |
| --- | --- |
| `site_url`, `base_path` | Endereço público. Trocar de domínio é mudar só estes dois |
| `indexar` | `false`: `noindex, nofollow` em toda página, `X-Robots-Tag` e `robots.txt` bloqueando tudo. `true`: o contrário, e o `robots.txt` aponta o sitemap. Só com decisão dos sócios |
| `canal_whatsapp`, `canal_telegram` | Links dos canais, na folha "Avise-me" e em `/alertas/` |
| `kit_form_id` | Liga o alerta por e-mail (formulário do Kit, confirmação dupla) |
| `email_contato` | `mailto:` do contato e do "Avise a gente" das fichas |
| `cloudflare_analytics_token` | Cloudflare Web Analytics, sem cookie |
| `adsense_client`, `adsense_slot` | Liga anúncio com rótulo "Publicidade", `ads.txt` e aviso de cookies com opção de recusar |
| `[[afiliados]]` | "Link de parceiro" por área ou banca, com `rel="sponsored noopener"` |

Campo vazio = a peça não aparece. A política de privacidade muda sozinha com o que estiver ligado.

### Marca

Os arquivos oficiais da marca ficam em `docs/marca/` (ver [`docs/marca/LEIA-ME.md`](docs/marca/LEIA-ME.md)). Sem eles, o build usa o logotipo provisório do protótipo e avisa.

## Varredura semanal

### `.env`

| Variável | Para quê |
| --- | --- |
| `CONTATO_VARREDURA` | Contato no User-Agent; obrigatório para coletar |
| `INLABS_EMAIL`, `INLABS_SENHA` | DOU pelo INLABS (cadastro gratuito em https://inlabs.in.gov.br) |
| `CONFERENTE` | Nome de quem confere |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CANAL` | Só para postar no Telegram do notebook (o CI usa os GitHub Secrets) |

### Comandos

```powershell
python -m varredura coletar --inicial --desde 2026-06-16   # primeira vez (o INLABS guarda 4 meses)
python -m varredura coletar --semana                       # semanal
python -m varredura pendentes [--resumo]                   # atos da fila sem ficha nem descarte
python -m varredura validar
python -m varredura revisao                                # revisao.md, revisao.csv e cobertura.csv
python -m varredura publicar --por "Filipe"                # só depois da conferência
python -m varredura telegram --teste                       # mostra as mensagens do resumo sem postar
python -m varredura municipios                             # refaz a tabela de municípios
```

- **coletar** lê as fontes, faz a triagem (abertura, retificação, autorização, contratação de banca, resultado, outro; PSS marcado e fora) e põe um arquivo por ato em `dados/varreduras/AAAA-MM-DD/fila/`.
- **Extração:** sempre no modo `claude-code` (padrão): o `/varredura` lê cada ato e escreve a ficha seguindo `varredura/instrucoes_extracao.md`. O `--modo api` existe no código, mas é pago e não se usa.
- **validar:** schema, datas, salário maior que zero, link oficial (agregador é recusado), município da tabela, código IBGE só para cidade do PR.
- **revisao:** compara com o publicado e gera `revisao.md`, `revisao.csv` (conferência) e `cobertura.csv` (órgão, cidade, UF, situação, fim da inscrição e link do edital, para comparar à mão com os agregadores).
- **publicar:** recusa campo crítico sem `ok` ou `auto`; atualiza `dados/concursos.json`; escreve `resumo-telegram.md`, `resumo-whatsapp.txt` e `posts/` (imagens 1080×1350 e legendas, fora do git).

| Fonte | Como é lida |
| --- | --- |
| Diário Oficial da União | INLABS: um ZIP de XML por dia e seção (DO1 e DO3), últimos 4 meses |
| Diário Oficial dos Municípios do PR (AMP) | Um PDF por dia útil; cada matéria vira um ato com link próprio |
| Diário Oficial do Estado do PR (DIOE) | Ainda não: ver `varredura/fontes/diario_estado_pr.py` |

As fontes são lidas com boas maneiras: `robots.txt`, no máximo 1 requisição por segundo, User-Agent com contato, cache em `.cache/` (fora do git).

### Conferência automática

`varredura/conferir.py` não usa IA nem custa nada: procura cada valor crítico no texto do ato, no lugar certo, e marca `auto`.

| Campo | Passa quando |
| --- | --- |
| Salário | o valor aparece logo depois do nome do cargo, sem outro cargo mais perto; professor do magistério: último valor da linha da titulação exigida, no bloco do regime do cargo, na tabela de remuneração |
| Inscrição | início e fim como período ("de X a Y") logo depois de "inscrição"; em tabela por item, logo depois do número do item do cargo |
| Prova objetiva | a primeira data depois de "objetiva" (sem gabarito, resultado, recurso) |
| Taxa | o valor depois de "taxa" |
| Banca e cidade | o nome está no ato |
| Link do edital | é o link do próprio ato |

O que não passa fica para a pessoa, com o motivo. Uma amostra fixa de 1 em 20 do que passou vem marcada `amostra`. Os testes estragam fichas de propósito (salário trocado, data deslocada, vencimento básico no lugar do total, período de outro item) e exigem que nada disso passe.

## Testes e CI

```powershell
python -m pytest
```

`.github/workflows/deploy.yml` roda os testes, o build e o verificador de links em todo push e pull request; publica só a partir da `main`. `.github/workflows/telegram.yml` posta o resumo novo.

## Estrutura

```
site.toml                    configuração do site (domínio, indexar, canais, Kit, anúncios)
gerador/                     python -m gerador: build, links, servir, redirecionar
  templates/                 Jinja2 (autoescape): base, início, listas, ficha, institucionais
assets/css/                  tokens.css, componentes.css (cc-), site.css (pt-): juntados no build
assets/js/app.js             só o que depende da pessoa
assets/fonts/, assets/img/   Schibsted Grotesk (SIL OFL 1.1) e o favicon do protótipo
functions/api/local.js       Cloudflare Pages Function: região pelo IP, sem gravar nada
dados/                       schema, concursos.json (publicado), municipios-pr.json, exemplo/, varreduras/
varredura/                   pacote da varredura semanal
docs/                        LANCAMENTO.md, ROTINA-SEMANAL.md, DIAGNOSTICO-COBERTURA.md, marca/
tests/                       pytest
.claude/commands/varredura.md   passo a passo semanal para o Claude Code
.github/workflows/           deploy.yml e telegram.yml
```

## Tabela de municípios

`dados/municipios-pr.json`: os 399 municípios do Paraná com código IBGE, nome e coordenadas, gerada em 14/10/2026 por `python -m varredura municipios`. Códigos e nomes: API de localidades do IBGE. Coordenadas: [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) (MIT). As cidades dos exemplos são fictícias (códigos 41999xx) e ficam em `dados/exemplo/`.
