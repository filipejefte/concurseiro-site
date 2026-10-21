# Concurseiro: instruções para o Claude Code

Site gratuito que reúne concursos públicos abertos, com o salário na frente, prazos e localização. Ele sempre leva ao edital oficial. "Concurseiro" é o nome definitivo (decisão de 16/10/2026): no texto corrido, "Concurseiro" com maiúscula; no logotipo, minúsculas. Os arquivos da marca (logotipos, `bundle.css`, `tokens.json`, `voz.md`, `nome.md`) ficam em `docs/marca/` e são a fonte da verdade visual e de texto.

## Contexto

- **Cobertura:** concursos federais, do Brasil todo, e do Paraná (estado, prefeituras, câmaras, autarquias). Federal de qualquer estado está na cobertura.
- **Atualização:** uma varredura por semana, rodada pelo Filipe com `/varredura`, no notebook (o `.env` e a rede para os diários oficiais estão lá). O site é gerado de novo todo dia às 06:00 pelo GitHub Actions (situação e prazos).
- **Custo:** o único custo é o domínio. Nada pode gerar cobrança (regra de 16/10/2026):
  - extração sempre pelo próprio Claude Code (`/varredura`); nada de chave de API paga;
  - só serviço com plano grátis que cubra o uso: GitHub (Actions nos runners padrão: 2.000 minutos grátis por mês em repositório privado, e o uso estimado fica bem abaixo), Cloudflare Pages, Web Analytics e Email Routing, Telegram Bot API, canal do WhatsApp (postagem manual), Kit (grátis até 10 mil inscritos). Outro serviço só se for grátis no uso previsto, com justificativa;
  - dependências só de código aberto, por `pip` ou `npx`; nada pago "com teste grátis";
  - o repositório é público só até o primeiro deploy; depois o Filipe o torna privado (e o github.io sai do ar). Segredos só nos GitHub Secrets ou no `.env`.
- **Dados:** `dados/concursos.json`, versionado. Sem banco nem servidor.
- **Site:** estático e gerado (`python -m gerador build` → `public/`, fora do git), publicado pelo GitHub Actions só no Cloudflare Pages, em https://concurseiro.pages.dev (o deploy cria o projeto se ele não existir; sem os segredos o workflow testa e gera, mas não publica). Não há GitHub Pages.
- **Fora dos buscadores:** `indexar = false` no `site.toml` (noindex em toda página, `robots.txt` bloqueando) até os sócios decidirem.
- **Ambiente:** Windows com PowerShell. Python 3.11 ou mais novo, caminhos com `pathlib`, nada que dependa de bash (os workflows do GitHub podem usar bash).

## Regras fixas (código, textos e dados)

1. O site nunca recebe inscrição nem pagamento. O botão principal da ficha é sempre "Ver edital oficial". Concurso previsto, sem edital, usa "Ver ato oficial". Nenhum texto diz "Inscreva-se" nem "imperdível".
2. Toda ficha vem de ato oficial (diário oficial ou site da banca), com link. PCI, Folha Dirigida e outros agregadores servem só para conferir cobertura; nunca copie texto ou dado deles.
3. O que o edital não traz fica `null` no JSON e aparece como "Não informado no edital" na tela. Nada de chute.
4. Nada vai ao ar sem conferir os campos críticos: salário de cada cargo, início e fim da inscrição, data da prova objetiva, taxa, banca, cidade e link do edital. A conferência automática (`varredura/conferir.py`, sem IA e sem custo) procura cada valor no texto do ato e marca `auto` o que acha no lugar certo; a pessoa confere o resto e uma amostra de 1 em 20 do que passou.
5. Sem dado pessoal no site: sem conta e sem cookie próprio; cidade e perfil só no `localStorage`; GPS opcional e só no aparelho. Sem e-mail por enquanto: o formulário do Kit (caixa de consentimento desmarcada, confirmação dupla) e a página Contato só aparecem com `kit_form_id` e `email_contato` preenchidos no `site.toml`. Vazios, não aparecem e não deixam link quebrado. Nenhum outro formulário ou campo de e-mail no site.
6. Anúncio leva "Publicidade", com espaço reservado e aviso de cookies com opção de recusar; nunca na folha de alerta, perto do "Ver edital oficial" ou com cara de botão do site. Indicação paga leva "Link de parceiro" e `rel="sponsored noopener"`. Os dois só aparecem com a configuração preenchida no `site.toml`.
7. "Previsto" só com ato oficial de autorização do concurso ou de contratação da banca. Previsto nunca entra na contagem de abertos.
8. Não guarde PDFs de editais no repositório. Ficam só os links e os fatos extraídos; os PDFs baixados vão para `.cache/`, ignorado pelo git.
9. Não invente concurso, órgão, salário ou data. Dado de exemplo fica marcado como fictício (`"ficticio": true`) e só entra no site com `--exemplo`.
10. Sem `JobPosting` no JSON-LD (o Google não aceita vaga que cobra taxa).
11. Nada sobre quem cria o Concurseiro (decisão do Filipe em 19/10/2026, permanente e válida para tudo o que o projeto publica: site, metadados, imagens, manifest, alertas, posts, e-mails, resumos e canais). Nenhum nome, cidade, e-mail, usuário ou dado de quem cria. O site fala só da proposta: o que é, o que faz, o que não faz, as fontes e a frequência. O `site.toml` não tem campo para isso. Nome e @ dos canais são só da marca. A verificação é automática: `python -m gerador anonimato` (roda no CI depois do build) e `tests/test_anonimato.py` falham se o site gerado, os resumos ou as legendas tiverem `[A PREENCHER]`, `github.io`, o dono do repositório ou o nome ou e-mail de quem fez commit (lidos do git na hora).

## Estrutura

```
site.toml                     site_url, base_path, indexar, canais, kit_form_id, email_contato,
                              cloudflare_analytics_token, adsense_client, adsense_slot, [[afiliados]]
gerador/                      python -m gerador build | links | anonimato | servir
  modelo.py                   situação na data do build, textos, ordem, cidades a até 50 km
  build.py                    páginas, sitemap, robots.txt, _headers, imagens OG, dados para o JS
  anonimato.py                regra 11: o que não pode aparecer em nada que o projeto publica
  imagens.py                  OG 1200x630, posts 1080x1350, ícones (Pillow + fonte da marca via fontTools)
  templates/                  Jinja2 com autoescape
assets/css/                   tokens.css, componentes.css (cc-), site.css (pt-)
assets/js/app.js              só o que depende da pessoa (cidade, perfil, filtros, contagem, folhas)
functions/api/local.js        Cloudflare Pages Function: região pelo IP, sem gravar nada
dados/
  schema/concurso.schema.json
  concursos.json              o que está publicado
  municipios-pr.json          399 municípios (IBGE + coordenadas)
  exemplo/                    12 concursos e 4 cidades fictícios (só com --exemplo)
  varreduras/AAAA-MM-DD/      atos.json, fila/ (fora do git), fichas/, descartes.json, revisao.md,
                              revisao.csv, cobertura.csv, resumo-telegram.md, resumo-whatsapp.txt,
                              posts/ (fora do git)
varredura/                    pacote Python (fontes, triagem, extração, validação, conferência, revisão,
                              publicação, telegram)
  instrucoes_extracao.md      como extrair a ficha de um ato
docs/                         LANCAMENTO.md (painéis), ROTINA-SEMANAL.md, DIAGNOSTICO-COBERTURA.md, marca/
tests/                        pytest (varredura e gerador)
.github/workflows/            deploy.yml (testes, build, links, anonimato, deploy diário no Cloudflare Pages) e telegram.yml
.claude/commands/varredura.md passo a passo semanal
```

A situação (aberto, encerra em até 7 dias, previsto, encerrado) não fica no JSON: o gerador calcula na data do build, e o navegador só refaz "Encerrado" e "Encerra em N dias" pela data de hoje.

## Comandos (PowerShell, na raiz)

```powershell
python -m pip install -r requirements.txt
python -m pytest
python -m gerador build                                     # site em public/ (só o publicado)
python -m gerador build --exemplo                           # com os exemplos fictícios marcados
python -m gerador build --previa                            # previa/: com as fichas da semana, sem conferência
python -m gerador servir                                    # http://localhost:8000/
python -m gerador links                                     # verificador de links internos
python -m gerador anonimato                                 # regra 11 no site gerado (public/)
python -m varredura coletar --inicial --desde 2026-06-16    # coleta inicial (o INLABS guarda 4 meses)
python -m varredura coletar --semana                        # semanal (desde a última publicada)
python -m varredura pendentes [--resumo]                    # atos da fila sem ficha
python -m varredura validar
python -m varredura revisao                                 # revisao.md, revisao.csv e cobertura.csv
python -m varredura publicar --por "Filipe"                 # só depois da conferência
python -m varredura telegram --teste                        # mostra o resumo do Telegram sem postar
python -m varredura municipios                              # refaz a tabela de municípios
```

## O que nunca fazer

- Publicar (`python -m varredura publicar`), fazer merge na `main`, publicar em produção, fazer commit ou dar push sem o pedido do Filipe. Push na `main` publica o site e posta no Telegram.
- Criar chave de API paga, extrair por API ou contratar serviço pago.
- Fazer commit de `.env`, chaves, `.cache/`, `public/`, `previa/`, PDFs, posts ou da fila de extração.
- Publicar a prévia (`build --previa`): ela tem fichas sem conferência e serve só para olhar.
- Pôr no site, no `site.toml`, nas imagens, nos posts, nos resumos ou nos canais qualquer nome, cidade, e-mail, usuário ou dado de quem cria o Concurseiro (regra 11). Vale também para o nome do canal, do bot e da conta do Cloudflare Pages: só nome de marca.
- Mexer em configuração do GitHub ou do Cloudflare (visibilidade do repositório, Pages, segredos, painéis): é com o Filipe, passo a passo no `docs/LANCAMENTO.md`.
- Escrever credencial no código ou mostrar o conteúdo do `.env`. Elas vêm de `CONTATO_VARREDURA`, `INLABS_EMAIL`, `INLABS_SENHA`, `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CANAL` (ver `.env.example`); no CI, dos GitHub Secrets.
- Ler dados de agregador, preencher campo por dedução ou inventar valor para passar na validação.
- Marcar `ok` ou `auto` à mão no `revisao.csv`: `ok` é do Filipe, `auto` só a conferência automática escreve.
- Afrouxar a conferência automática sem que os testes de valor errado (`tests/test_varredura.py`) continuem passando; regra nova vem com teste de valor certo e de valor errado.
- Mudar `indexar` para `true` (ou tirar o `noindex` de outro jeito) sem decisão dos sócios.
- Pôr campo de e-mail ou formulário fora do fluxo do Kit (opt-in duplo).
- Redigitar o logotipo: use os arquivos de `docs/marca/`.
- Passar de 1 requisição por segundo nas fontes, ignorar o `robots.txt` ou fazer a coleta completa fora do `/varredura`. Única exceção, decisão do Filipe em 21/10/2026: o login e os downloads do INLABS (`inlabs.in.gov.br`, serviço oficial de download do DOU, com cadastro), porque o `robots.txt` dele só redireciona para o do portal (`Disallow: /`). Está em `Cliente.SEM_ROBOTS` e vale só para esse host.
- Usar API não oficial do WhatsApp: o resumo do canal é colado à mão.
