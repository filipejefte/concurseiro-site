# Lançamento: o que o Filipe faz nos painéis

Tudo aqui é de graça, menos o domínio (cerca de R$ 40 por ano no Registro.br). Siga na ordem. Cada passo diz onde clicar e o que copiar. Onde aparece `concurseiro.com.br`, use o domínio que vocês registrarem.

Tempo total: umas 3 horas, em dias diferentes (a troca de DNS leva até 24 horas para valer).

> **Antes do merge da branch `lancamento`.** O site agora é gerado pelo GitHub Actions. Faça o passo 0 antes de juntar a branch na `main`, senão o endereço atual fica fora do ar até o primeiro deploy.

---

## 0. GitHub Pages pelo Actions (5 min, antes do merge)

1. No GitHub, abra o repositório `concurseiro-site` → **Settings** → **Pages** (menu da esquerda).
2. Em **Build and deployment** → **Source**, troque "Deploy from a branch" por **GitHub Actions**.
3. Pronto. Depois do merge, a aba **Actions** mostra o workflow **Site** rodando; quando ficar verde, o site novo está em https://filipejefte.github.io/concurseiro-site/.

O workflow roda sozinho todo dia às 06:00 (horário de Brasília), para a situação dos concursos e a contagem dos prazos virarem sem precisar de varredura.

---

## 1. Registrar o domínio (15 min)

1. Entre em https://registro.br com o CPF ou CNPJ de quem vai ser o dono.
2. Procure o nome (por exemplo `concurseiro.com.br`) → **Registrar** → pague (boleto, Pix ou cartão).
3. Ainda **não** mexa nos DNS: o passo 2 diz quais pôr.

## 2. Cloudflare: conta, domínio e DNS (20 min + espera)

1. Crie a conta em https://dash.cloudflare.com/sign-up (plano **Free**).
2. Na tela inicial: **Add a domain** (ou "Adicionar um domínio") → digite `concurseiro.com.br` → **Continue** → escolha o plano **Free** → **Continue**.
3. A Cloudflare mostra **dois nameservers**, parecidos com `ana.ns.cloudflare.com` e `bob.ns.cloudflare.com`. Copie os dois.
4. No Registro.br: **Painel** → clique no domínio → **DNS** → **Alterar servidores DNS** → apague os que estão lá → cole os dois da Cloudflare → **Salvar**.
5. Volte à Cloudflare e clique em **Check nameservers**. Pode levar de minutos a 24 horas; a Cloudflare manda um e-mail quando o domínio ficar **Active**.

## 3. Cloudflare Pages: o projeto do site (15 min)

1. Na Cloudflare: **Workers & Pages** (menu da esquerda) → **Create** → aba **Pages** → **Upload assets** (envio direto, sem ligar ao GitHub).
2. **Project name:** `concurseiro` (se usar outro nome, crie no GitHub a variável `CLOUDFLARE_PROJETO` com ele, passo 5).
3. Ele pede uma pasta para o primeiro envio. No notebook, no PowerShell, na pasta do projeto:
   ```powershell
   python -m gerador build
   ```
   e arraste a pasta `public` para a página → **Deploy site**. Depois disso, quem publica é o GitHub Actions.
4. No projeto: **Custom domains** → **Set up a custom domain** → `concurseiro.com.br` → **Continue** → **Activate domain**. Repita com `www.concurseiro.com.br` se quiser o "www".

## 4. Token da API da Cloudflare (10 min)

1. Na Cloudflare, clique no ícone da pessoa (canto de cima) → **My Profile** → **API Tokens** → **Create Token**.
2. Desça até **Custom token** → **Get started**.
3. **Token name:** `github-actions-concurseiro`.
4. **Permissions:** `Account` · `Cloudflare Pages` · `Edit`.
5. **Account Resources:** `Include` · a sua conta.
6. **Continue to summary** → **Create Token** → **copie o token agora** (ele não aparece de novo).
7. O **Account ID**: em **Workers & Pages**, na coluna da direita, "Account ID" → copie.

## 5. Segredos no GitHub (10 min)

No repositório: **Settings** → **Secrets and variables** → **Actions**.

Aba **Secrets** → **New repository secret**, um de cada vez:

| Nome | Valor |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | o token do passo 4 |
| `CLOUDFLARE_ACCOUNT_ID` | o Account ID do passo 4 |
| `TELEGRAM_BOT_TOKEN` | o token do passo 7 |
| `TELEGRAM_CANAL` | o `@nome` do canal do passo 7 |

Aba **Variables** (opcionais):

| Nome | Valor | Para quê |
| --- | --- | --- |
| `CLOUDFLARE_PROJETO` | nome do projeto, se não for `concurseiro` | o deploy acha o projeto |
| `REDIRECIONAR_GITHUB_PAGES` | `true` | só depois do passo 6: o endereço antigo no GitHub Pages passa a levar ao domínio novo |

Com os dois segredos da Cloudflare, o próximo deploy já vai para a Cloudflare. Por isso, faça o passo 6 logo em seguida, no mesmo dia: até lá, o site da Cloudflare ainda sai com os endereços do GitHub Pages.

## 6. Trocar o endereço no site.toml (5 min, com o Claude Code)

Peça ao Claude Code (ou edite à mão) o `site.toml`:

```toml
site_url = "https://concurseiro.com.br"
base_path = "/"
email_contato = "contato@concurseiro.com.br"
```

Faça commit e push. O deploy publica o site com os endereços novos. Confira https://concurseiro.com.br e depois crie a variável `REDIRECIONAR_GITHUB_PAGES = true` (passo 5) e rode o workflow **Site** à mão (**Actions** → **Site** → **Run workflow**).

`indexar` continua `false`: o site segue fora do Google até os sócios decidirem.

## 7. Telegram: bot e canal (15 min)

1. No Telegram, abra o **@BotFather** → `/newbot` → dê um nome ("Concurseiro") e um usuário terminado em `bot` (por exemplo `concurseiro_alertas_bot`).
2. Ele responde com o **token** (algo como `123456:ABC...`). Esse é o `TELEGRAM_BOT_TOKEN` do passo 5. Não mostre a ninguém.
3. Crie o canal: menu → **Novo canal** → nome "Concurseiro" → **Público** → link `t.me/concurseiro` (ou o que estiver livre).
4. No canal: **Administradores** → **Adicionar administrador** → procure o bot → deixe só **Publicar mensagens** ligado → salvar.
5. `TELEGRAM_CANAL` = `@concurseiro` (o nome público do canal, com @).
6. No `site.toml`: `canal_telegram = "https://t.me/concurseiro"`.
7. Teste: **Actions** → **Telegram** → **Run workflow** com "Só mostrar as mensagens" marcado; depois sem marcar.

## 8. Canal do WhatsApp (10 min)

1. No WhatsApp do celular: aba **Atualizações** → **+** (ou "Canais" → **Criar canal**) → siga as telas.
2. Nome "Concurseiro", descrição curta ("Concursos federais e do Paraná com inscrição aberta, toda semana. Não somos site oficial."), foto com o ícone da marca.
3. No canal: toque no nome → **Compartilhar link do canal** → copie.
4. No `site.toml`: `canal_whatsapp = "<o link>"`.

Toda semana, o `publicar` gera `resumo-whatsapp.txt`: copie e cole no canal.

## 9. E-mail de contato: Email Routing (10 min, depois do passo 2)

1. Na Cloudflare, clique no domínio → **Email** → **Email Routing** → **Get started**.
2. **Custom address:** `contato` → **Destination:** o seu Gmail → **Create and continue**.
3. Abra o Gmail e clique no link de verificação que a Cloudflare mandou.
4. Volte e clique em **Add records and enable** (a Cloudflare cria os registros de DNS sozinha).
5. Teste mandando um e-mail para `contato@concurseiro.com.br`.

Responder como `contato@` pelo Gmail é opcional e fica para depois.

## 10. Kit: alerta por e-mail com confirmação dupla (20 min, quando quiser ligar)

1. Crie a conta grátis em https://kit.com (plano **Newsletter**, grátis até 10 mil inscritos).
2. **Grow** → **Landing Pages & Forms** → **Create new** → **Form** → **Inline** → escolha qualquer modelo (o site não usa o visual do Kit).
3. No editor do formulário → **Settings**:
   - **Incentive**: ligue **Send incentive email**. É o e-mail de confirmação (opt-in duplo): sem clicar nele, a pessoa não recebe nada.
   - Em **Incentive email**, escreva no assunto "Confirme para receber os alertas do Concurseiro" e, em **Redirect after confirming**, ponha `https://concurseiro.com.br/alertas/`.
   - **After subscribing**: escolha **Redirect to an external page** → `https://concurseiro.com.br/alertas/confirme/`.
4. **Save**. O número do formulário está no endereço da página do editor (`.../forms/1234567/edit`) ou no código de incorporação.
5. No `site.toml`: `kit_form_id = "1234567"`.

Os e-mails semanais saem pelo próprio Kit (**Send** → **Broadcasts**), colando o resumo da semana. A política de privacidade do site já muda sozinha quando o `kit_form_id` é preenchido.

## 11. Cloudflare Web Analytics (5 min, opcional)

1. Na Cloudflare: **Analytics & Logs** → **Web Analytics** → **Add a site** → `concurseiro.com.br`.
2. Copie só o **token** do trecho de código (o valor de `"token": "..."`).
3. No `site.toml`: `cloudflare_analytics_token = "<token>"`. Não usa cookie.

## 12. Search Console e Bing (só quando os sócios decidirem abrir o site)

1. No `site.toml`: `indexar = true`. O próximo build tira o `noindex` de todas as páginas e o `robots.txt` passa a apontar o `sitemap.xml`. Nada mais muda.
2. https://search.google.com/search-console → **Adicionar propriedade** → **Domínio** → `concurseiro.com.br` → copie o registro TXT → na Cloudflare, **DNS** → **Add record** → tipo `TXT`, nome `@`, conteúdo colado → **Save** → volte e **Verificar**.
3. No Search Console: **Sitemaps** → `https://concurseiro.com.br/sitemap.xml` → **Enviar**.
4. https://www.bing.com/webmasters → **Importar do Google Search Console** → autorize.

## 13. Para o Claude Code ler as fontes oficiais numa sessão na nuvem (opcional)

Se for rodar a varredura numa sessão do Claude Code na nuvem (e não no notebook), libere na configuração de rede do ambiente os domínios `inlabs.in.gov.br`, `www.in.gov.br`, `www.diariomunicipal.com.br`, `www-storage.voxtecnologia.com.br` (PDFs da AMP) e `www.dioe.pr.gov.br`. Passo a passo: https://code.claude.com/docs/en/cloud-environments#network-access. No notebook não precisa.

---

## O que fica de graça e por quê

| Serviço | Uso | Limite grátis |
| --- | --- | --- |
| GitHub (repositório público) | código, Actions, GitHub Pages | Actions sem custo nos runners padrão em repositório público |
| Cloudflare Pages | hospedagem | 500 builds por mês, 20 mil arquivos por site (usamos 1 build por dia e uns 300 arquivos) |
| Cloudflare DNS, Email Routing, Web Analytics | domínio, `contato@`, visitas | grátis |
| Telegram Bot API | canal | grátis |
| Canal do WhatsApp | canal | grátis (postagem manual) |
| Kit | e-mail | grátis até 10 mil inscritos |

Nada de API paga: a extração das fichas é feita pelo próprio Claude Code (`/varredura`), sem chave de API.
