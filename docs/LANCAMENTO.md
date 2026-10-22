# Lançamento: o que o Filipe faz nos painéis

Tudo aqui é de graça. O site fica só no **Cloudflare Pages**, em `https://concurseiro.pages.dev` (não há GitHub Pages nem domínio próprio por enquanto). Siga na ordem. Cada passo diz onde clicar e o que copiar.

**Regra 11 (decisão de 19/10/2026): nada sobre quem cria o Concurseiro, em lugar nenhum.** Nome, cidade, e-mail e usuário de uma pessoa não entram no site, nas imagens, nos canais, nos posts nem nos e-mails. Em cada painel abaixo, ponha só nome de marca. O CI falha se o site gerado tiver o seu nome, o seu e-mail ou o usuário do repositório (`python -m gerador anonimato`).

Tempo total: umas 2 horas.

---

## 1. Conferir e publicar a varredura (com o Claude Code)

1. Abra `dados/varreduras/<data>/revisao.csv` no Excel e confira só as linhas com `conferido` vazio e as marcadas `amostra` (passo a passo em `docs/ROTINA-SEMANAL.md`). Certo: `ok`.
2. Peça ao Claude Code: `python -m varredura publicar --por "Nome"`. Ele recusa o que não foi conferido e diz por quê.
3. Depois do `publicar`, rode `python -m gerador build` e `python -m gerador servir` e olhe o site em http://localhost:8000/.

## 2. Cloudflare: conta e token (15 min)

1. Crie a conta grátis em https://dash.cloudflare.com/sign-up (plano **Free**). O e-mail da conta não aparece no site. Não precisa de domínio nem de cartão.
2. Pegue o **Account ID**: **Workers & Pages** (menu da esquerda), coluna da direita, "Account ID". Copie.
3. Crie o token: ícone da pessoa (canto de cima) → **My Profile** → **API Tokens** → **Create Token** → **Custom token** → **Get started**.
   - **Token name:** `github-actions-concurseiro`.
   - **Permissions:** `Account` · `Cloudflare Pages` · `Edit`.
   - **Account Resources:** `Include` · a sua conta.
   - **Continue to summary** → **Create Token** → **copie o token agora** (ele não aparece de novo).

Não crie o projeto no painel: o primeiro deploy cria o projeto sozinho.

## 3. Segredos no GitHub (10 min)

No repositório: **Settings** → **Secrets and variables** → **Actions** → aba **Secrets** → **New repository secret**, um de cada vez:

| Nome | Valor |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | o token do passo 2 |
| `CLOUDFLARE_ACCOUNT_ID` | o Account ID do passo 2 |
| `TELEGRAM_BOT_TOKEN` | o token do passo 6 (pode ficar para depois: sem ele o Telegram só avisa no log) |
| `TELEGRAM_CANAL` | o `@nome` do canal do passo 6 |

Sem os dois segredos da Cloudflare, o workflow **Site** testa e gera o site, mas não publica, e avisa no log com "NÃO foi publicado".

Aba **Variables** (opcional): `CLOUDFLARE_PROJETO` com o nome do projeto, **só** se `concurseiro` já estiver ocupado no pages.dev (o nome é global). Use outro nome de marca, sem nome de pessoa, e troque também o `site_url` no `site.toml` (`https://<nome>.pages.dev`).

## 4. Merge e primeiro deploy (10 min)

1. Faça o merge do PR da branch `lancamento` na `main`.
2. Aba **Actions** → workflow **Site**. Ele roda os testes, gera o site, confere links e anonimato, cria o projeto no Cloudflare Pages se ele não existir e publica. Quando ficar verde, abra https://concurseiro.pages.dev e confira a página inicial, uma ficha e `/como-conferimos/`.
3. Se o passo "Cria o projeto" ou "Publica" falhar dizendo que o projeto existe e não é da sua conta, o nome está ocupado: use a variável `CLOUDFLARE_PROJETO` (passo 3) e rode o workflow de novo (**Run workflow**).

O workflow roda sozinho todo dia às 06:00 (horário de Brasília), para a situação dos concursos e a contagem dos prazos virarem sem precisar de varredura.

## 5. Tornar o repositório privado (2 min, depois que o `pages.dev` estiver no ar)

**Settings** → **General** → no fim da página, **Danger Zone** → **Change repository visibility** → **Make private**.

O que muda: o histórico do código (com os autores dos commits) deixa de ser público; o `filipejefte.github.io` sai do ar; o GitHub Actions passa a ter **2.000 minutos grátis por mês** (veja "Minutos do GitHub Actions" abaixo). O site no `pages.dev` não depende disso: o deploy envia os arquivos direto para a Cloudflare.

Confira que a aba **Actions** continua ligada e rode o workflow **Site** uma vez (**Run workflow**).

## 6. Canais: Telegram (15 min)

Nome e @ só da marca. Nada de nome, foto ou número de pessoa no canal, no bot ou na descrição.

1. No Telegram, abra o **@BotFather** → `/newbot`. **Nome do bot:** `Concurseiro`. **Usuário:** terminado em `bot`, só de marca (por exemplo `concurseiro_alertas_bot`).
2. Ele responde com o **token** (algo como `123456:ABC...`). Esse é o `TELEGRAM_BOT_TOKEN` do passo 3. Não mostre a ninguém.
3. Crie o canal: menu → **Novo canal** → nome `Concurseiro` → **Público** → link `t.me/concurseiro` (ou outro nome de marca livre).
4. No canal: **Administradores** → **Adicionar administrador** → procure o bot → deixe só **Publicar mensagens** ligado → salvar.
5. **Assinar mensagens** fica **desligado** (menu do canal → **Editar** → **Assinar mensagens**): com ele ligado, cada post leva o nome de quem publicou.
6. `TELEGRAM_CANAL` = `@concurseiro` (o nome público do canal, com @).
7. No `site.toml`: `canal_telegram = "https://t.me/concurseiro"`.
8. Teste: **Actions** → **Telegram** → **Run workflow** com "Só mostrar as mensagens" marcado; depois sem marcar.

## 7. Canais: WhatsApp (10 min)

1. No WhatsApp do celular: aba **Atualizações** → **+** (ou "Canais" → **Criar canal**) → siga as telas.
2. Nome `Concurseiro`, descrição curta ("Concursos públicos de todo o Brasil com inscrição aberta, toda semana. Não somos site oficial."), foto com o ícone da marca (`docs/marca/icone-app.png`).
3. No canal: toque no nome → **Compartilhar link do canal** → copie.
4. No `site.toml`: `canal_whatsapp = "<o link>"`.

Toda semana, o `publicar` gera `resumo-whatsapp.txt`: copie e cole no canal.

## 8. E-mail de contato (opcional, quando existir um endereço da marca)

Hoje o site não tem e-mail: a página Contato e o "Avise a gente" das fichas **não aparecem**. Quando houver um endereço só da marca, ponha no `site.toml`: `email_contato = "..."`. No próximo build, a página `/contato/`, o link do rodapé e o "Avise a gente" aparecem sozinhos. Nunca use um endereço pessoal.

## 9. Kit: alerta por e-mail com confirmação dupla (opcional, quando quiser ligar)

Sem `kit_form_id` no `site.toml`, o formulário não aparece.

1. Crie a conta grátis em https://kit.com (plano **Newsletter**, grátis até 10 mil inscritos), com o nome da marca no remetente.
2. **Grow** → **Landing Pages & Forms** → **Create new** → **Form** → **Inline** → escolha qualquer modelo (o site não usa o visual do Kit).
3. No editor do formulário → **Settings**:
   - **Incentive**: ligue **Send incentive email**. É o e-mail de confirmação (opt-in duplo): sem clicar nele, a pessoa não recebe nada.
   - Em **Incentive email**, escreva no assunto "Confirme para receber os alertas do Concurseiro" e, em **Redirect after confirming**, ponha `https://concurseiro.pages.dev/alertas/`.
   - **After subscribing**: escolha **Redirect to an external page** → `https://concurseiro.pages.dev/alertas/confirme/`.
4. **Save**. O número do formulário está no endereço da página do editor (`.../forms/1234567/edit`) ou no código de incorporação.
5. No `site.toml`: `kit_form_id = "1234567"`.
6. **Rodapé obrigatório dos e-mails:** todo e-mail em massa precisa de um endereço postal no rodapé. O Kit oferece um endereço postal próprio para isso; use o dele, nunca o de uma pessoa (nas configurações de e-mail da conta do Kit, onde ele pede o endereço do rodapé).

Os e-mails semanais saem pelo próprio Kit (**Send** → **Broadcasts**), colando o resumo da semana. A política de privacidade do site muda sozinha quando o `kit_form_id` é preenchido.

## 10. Cloudflare Web Analytics (opcional)

1. Na Cloudflare: **Analytics & Logs** → **Web Analytics** → **Add a site** → `concurseiro.pages.dev`. Se a Cloudflare não aceitar o hostname do pages.dev, deixe para quando houver domínio próprio.
2. Copie só o **token** do trecho de código (o valor de `"token": "..."`).
3. No `site.toml`: `cloudflare_analytics_token = "<token>"`. Não usa cookie.

## 11. Search Console e Bing (só quando os sócios decidirem abrir o site)

1. No `site.toml`: `indexar = true`. O próximo build tira o `noindex` de todas as páginas e o `robots.txt` passa a apontar o `sitemap.xml`. Nada mais muda.
2. https://search.google.com/search-console → **Adicionar propriedade** → **Prefixo do URL** → `https://concurseiro.pages.dev/` (propriedade de domínio exige DNS próprio) → verifique pela tag HTML ou por arquivo.
3. **Sitemaps** → `https://concurseiro.pages.dev/sitemap.xml` → **Enviar**.
4. https://www.bing.com/webmasters → **Importar do Google Search Console** → autorize.

## 12. Domínio próprio (se um dia existir)

Troque `site_url` e `base_path` no `site.toml`, adicione o domínio em **Workers & Pages** → o projeto → **Custom domains**. Cuidado com a regra 11: o registro de um domínio pode mostrar o titular em consulta pública (whois). Só registre de um jeito que não mostre o nome de uma pessoa (CNPJ de uma empresa da marca, ou com a privacidade do registro ligada), e confira a consulta antes de publicar o endereço.

## 13. Para o Claude Code ler as fontes oficiais numa sessão na nuvem (opcional)

Se for rodar a varredura numa sessão do Claude Code na nuvem (e não no notebook), libere na configuração de rede do ambiente os domínios `inlabs.in.gov.br`, `www.in.gov.br`, `www.diariomunicipal.com.br`, `www-storage.voxtecnologia.com.br` (PDFs da AMP), `www.dioe.pr.gov.br` e os sites das bancas (`docs/DIAGNOSTICO-COBERTURA.md`). Passo a passo: https://code.claude.com/docs/en/cloud-environments#network-access. No notebook não precisa.

O INLABS prende a sessão ao IP de quem fez o login. Na nuvem, o proxy de saída troca de IP a cada conexão: o login entra, mas o pedido seguinte cai na página de login (`acessar.php`) e a coleta do DOU para com "não entregou arquivo em 3 dias úteis seguidos". No notebook o IP é um só e nada disso é preciso.

---

## Minutos do GitHub Actions

Com o repositório privado, o plano grátis dá 2.000 minutos por mês em runners Linux. O GitHub cobra por job, arredondando cada job para cima, em minutos inteiros. Medido nas execuções reais do workflow **Site** em pull request (testes, build e links): o job leva de 24 a 28 segundos, ou seja, **1 minuto cobrado**. Uma execução que publica soma o `npx wrangler` (instalar, criar o projeto se faltar, enviar uns 300 arquivos): fica entre 1 e 2 minutos, e contamos **2**. O workflow **Telegram** leva menos de um minuto (**1**). O passo final do workflow **Site** escreve a duração real no resumo da execução, para conferir esta conta nas primeiras semanas.

| O que roda | Vezes por mês | Minutos cada | Total |
| --- | --- | --- | --- |
| Build diário às 06:00 (publica) | 30 | 2 | 60 |
| Push na `main` (varredura semanal e ajustes) | 15 | 2 | 30 |
| Pull request e pushes de branch (só testes) | 40 | 1 | 40 |
| Execuções à mão | 5 | 2 | 10 |
| Telegram (resumo da semana e testes) | 10 | 1 | 10 |
| **Estimativa do mês** | | | **150** |

Mesmo dobrando o número de execuções e contando 4 minutos para cada uma que publica, o mês fica perto de 400. A meta é ficar abaixo de 600; o limite grátis é 2.000.

## O que fica de graça e por quê

| Serviço | Uso | Limite grátis |
| --- | --- | --- |
| GitHub (repositório privado) | código e Actions | 2.000 minutos de Actions por mês; usamos uns 150 |
| Cloudflare Pages | hospedagem | 500 builds por mês, 20 mil arquivos por site (usamos 1 deploy por dia e uns 300 arquivos) |
| Cloudflare Web Analytics | visitas, sem cookie | grátis |
| Telegram Bot API | canal | grátis |
| Canal do WhatsApp | canal | grátis (postagem manual) |
| Kit | e-mail | grátis até 10 mil inscritos |

Nada de API paga: a extração das fichas é feita pelo próprio Claude Code (`/varredura`), sem chave de API.
