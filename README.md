# concurseiro — protótipo do site

Protótipo navegável do site que reúne os concursos públicos abertos no Brasil, com o salário na frente, o prazo e o caminho para o edital oficial. "concurseiro" é nome provisório.

> **Dados de exemplo.** Órgãos, cidades, salários, datas e bancas associadas em `assets/js/dados.js` são fictícios, criados só para testar o layout. Por isso todas as páginas têm `noindex` e o `robots.txt` bloqueia buscadores. Tire os dois só quando o site tiver dados reais.

## O que tem

| Página | Arquivo | O que faz |
| --- | --- | --- |
| Início | `index.html` | Concursos perto de você, inscrições que encerram na semana, áreas, nacionais e chamada para o alerta |
| Listagem | `concursos.html` | Busca, ordenação (mais perto, maior salário, prazo), chips de área e folha de filtros (distância, nacionais, área, escolaridade, salário mínimo, banca, situação). O estado fica na URL, então dá para compartilhar o link de uma busca |
| Ficha | `concurso.html` | Resumo do edital: salário e benefícios, vagas e requisitos, inscrição e prova, conteúdo por cargo, documentos, publicidade e link de parceiro |
| Cidade | `cidade-maringa.html` | Modelo de página por cidade para o Google: concursos na cidade, cidades próximas, áreas, bancas e perguntas frequentes |
| Avise-me | em todas | Folha de captura de alerta por e-mail ou Telegram, com consentimento obrigatório |

Todas as páginas funcionam no celular e no computador. No protótipo, toda ficha abre o exemplo da Prefeitura de Vale Verde.

## Rodar no seu computador

Não precisa instalar nada além do Python. No PowerShell, dentro da pasta do projeto:

```powershell
python -m http.server 8000
```

(No Mac ou Linux, `python3` no lugar de `python`.) Depois abra http://localhost:8000. Abrir o `index.html` com dois cliques também funciona, mas aí o navegador bloqueia a fonte da marca e usa a fonte do sistema.

## Subir no GitHub e publicar

Crie antes um repositório vazio no GitHub (sem README, sem .gitignore e sem licença) chamado `concurseiro-site`. Depois, no PowerShell:

```powershell
cd $HOME\dev\concurseiro-site
git init
git add .
git commit -m "Protótipo do site"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/concurseiro-site.git
git push -u origin main
```

Para ver no ar: no repositório, **Settings › Pages › Build and deployment**, escolha **Deploy from a branch**, branch `main`, pasta `/ (root)`. Em um ou dois minutos o site abre em `https://SEU-USUARIO.github.io/concurseiro-site/`.

## Estrutura

```
index.html, concursos.html, concurso.html, cidade-maringa.html
assets/
  css/tokens.css        cores, espaços, raios e fonte do design system (tema Claro)
  css/componentes.css   componentes da marca (prefixo cc-), copiados do design system
  css/site.css          layout das telas (prefixo pt-)
  js/dados.js           concursos de exemplo
  js/app.js             cards, busca, filtros, ordenação e folha do Avise-me
  fonts/                Schibsted Grotesk (licença SIL Open Font License 1.1)
  img/favicon.svg
robots.txt              bloqueia buscadores enquanto os dados forem de exemplo
```

HTML, CSS e JavaScript puro, sem framework e sem etapa de build. A escolha de stack do site de verdade continua em aberto no documento do projeto; este código serve de referência visual e de comportamento para quem for implementar.

## Regras que o código já segue

- O site nunca recebe inscrição nem pagamento. O botão principal da ficha é sempre "Ver edital oficial".
- Aviso "Não somos site oficial" em todas as páginas.
- Anúncio leva "Publicidade"; indicação paga leva "Link de parceiro" e `rel="sponsored"`.
- Alerta só com consentimento marcado pela pessoa, por canal. O formulário não envia nem guarda nada.
- Dado que o edital não traz aparece como "Não informado no edital".

## O que falta para virar site de verdade

- Ligar a listagem ao motor de dados (robôs do DOU, diários estaduais e municipais, sites das bancas) no lugar de `dados.js`.
- Gerar a ficha de cada concurso a partir do `id` e as páginas de cidade, área e banca no servidor, para o Google ler.
- Integrar o Avise-me: e-mail com confirmação (opt-in duplo) e robô do Telegram, com descadastro em um clique.
- Política de privacidade, página "Como conferimos os dados" e links reais de edital, banca e parceiros (hoje estão como `#`).
- Calcular a distância pela localização real da pessoa (hoje é sempre a partir de Maringá).
- Trocar o nome provisório no logotipo quando o nome for decidido.
