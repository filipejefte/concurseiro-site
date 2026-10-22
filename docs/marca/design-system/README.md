Concurseiro é o site gratuito que reúne todos os concursos públicos abertos do Brasil, com o salário na frente, o edital resumido e o caminho para o canal oficial. Como escrever e proteger o nome está na seção **Nome**.

## Essência

- **Promessa:** todo concurso aberto, com o salário na frente.
- **Para quem:** concurseiros de todo o Brasil, no celular, que hoje garimpam editais em sites antigos e PDFs de 80 páginas.
- **Posicionamento:** para quem procura concurso e perde tempo abrindo edital por edital, este é o buscador que mostra primeiro o que decide (salário, benefícios, prazo, local) e avisa quando abre um concurso perto. Diferente dos portais de notícia e dos cursinhos, a informação vem antes da oferta, e o caminho sempre termina no site oficial.
- **O conceito: o grifo.** Todo concurseiro grifa o edital com marca-texto. O site faz isso por ele: lê o edital e grifa o que importa. No direito, "grifo nosso" é o destaque de quem cita; aqui, é a assinatura da marca. O grifo verde-limão aparece no salário, no prazo, no logotipo e em nada mais.
- **Quatro provas da promessa:** salário na frente (na listagem, sem abrir o edital); perto de você (cidade e distância no topo); sempre atualizado (fonte e hora da última conferência em toda ficha); fonte oficial sempre (todo caminho termina no edital e no site da banca).

## Personalidade: útil e confiável

| É | Não é |
| --- | --- |
| Claro: diz o dado e para | Seco: responde sem contexto |
| Exato: número com fonte, "não informado" quando falta | Burocrático: copia o juridiquês do edital |
| Calmo: prazo é fato, não alarme | Alarmista: "Corre!", "Últimas vagas!!!" |
| Próximo: fala como gente, trata por você | Coach ou meme: frase motivacional, piada com reprovado |

Na dúvida, escreva como um amigo que trabalha num cartório e gosta de você: preciso, gentil, sem enrolar. A voz completa está na seção **Voz e tom**.

## Cor

- Página em `papel`, cards e folhas em `papel-alto`, bordas em `linha`. Campos, checkbox e botão secundário com borda `linha-forte`.
- Texto em `tinta`; metadados e "não informado" em `tinta-suave`.
- `verde` é a marca e a ação: botão principal (rótulo em `on-verde`), links (`link`), ícones ativos, anel de foco. Um verde só; não crie tons intermediários.
- `grifo` só atrás do dado que decide e no logotipo, sempre com texto `on-grifo`. Máximo de dois por card.
- Estados: `prazo` (sobre `prazo-suave`) para inscrição que acaba em 7 dias ou menos; `previsto` para edital anunciado sem inscrição aberta; `encerrado` para inscrição fechada; `erro` só em formulário e falha de carregamento. Todo estado leva palavra e ícone, nunca só cor.
- Proporção numa tela: muito `papel`, `tinta` no texto, `verde` em uma ação, `grifo` em um ou dois números.
- **Nunca pareça governo.** Não use azul como cor principal, não junte verde com amarelo-ouro, não use as cores do Governo Federal (verde #00D000, amarelo #FFD000, azul #183EFF) nem a fonte Rawline, brasão, bandeira ou selo gov.br. Já houve sites falsos de inscrição no CNU; o site precisa ser reconhecível como não oficial à primeira vista.
- Tema escuro: os mesmos nomes de token, valores do tema "Escuro". O verde clareia e o texto sobre ele escurece (`on-verde`); o grifo continua com texto escuro.

## Tipografia

- Uma família: **Schibsted Grotesk**, variável de 400 a 900, licença OFL (uso comercial livre), arquivo em `fonts/`. Uma família só deixa o site leve no celular: carregue o arquivo latino com `font-display: swap`.
- Títulos: `display` (uma vez por tela), `titulo`, `subtitulo`, `orgao` (nome do órgão no card). Texto: `corpo` (16px, nunca menos no celular), `corpo-forte`, `apoio`, `legenda`.
- Dados: `dado-grande` para o salário (dentro do grifo) e `dado` para a linha de vagas, escolaridade e prazo. Algarismos tabulares (`font-variant-numeric: tabular-nums`, classe `cc-num`) só em colunas de números que precisam alinhar, como tabela de cargos e salários. No resto, os algarismos normais da fonte: nela o tabular abre demais o ponto e a vírgula ("R$ 4.218,50", "sex, 20/11").
- Caixa alta só em `legenda` (rótulos como SALÁRIO INICIAL) e em siglas.

## Espaço, forma e profundidade

- Base de 4px: `space-4` de margem lateral no celular e padding de card, `space-6` entre cards, `space-8` entre blocos.
- Raios: `radius-sm` em campos, `radius-md` em botões, `radius-lg` em cards, folhas e posts, `radius-full` só no selo de situação.
- Borda antes de sombra. Sombra só no que flutua: `sombra-folha` e `sombra-botao-flutuante`.
- Foco de teclado: `foco` (2px de papel e 2px de verde sólido), em todo elemento interativo.
- Alvo de toque mínimo de 44px; botões com 48px.

## O grifo

- Forma de marca-texto com pontas chanfradas: `grifo-inclinacao` (-12°), `grifo-giro` (-1,5°) e `grifo-sobra` (passa um pouco das letras). Cobre a altura inteira do texto.
- Use em: salário no card, na ficha, no alerta e no post; prazo final quando é a notícia; número de capa ("N concursos abertos esta semana"); logotipo.
- Não use em: frases, títulos, botões, links, fundos, ilustração decorativa.

## Iconografia

- Ícones de linha no estilo do Lucide (licença ISC, gratuito): traço de 1,75px (2px abaixo de 16px), cantos e pontas arredondados, 20px no texto e 16px nos metadados, cor `tinta-suave`, ou `verde` quando ativos.
- Ícones fixos: pino (local), relógio (prazo), calendário (data e previsto), círculo com check (aberto), seta diagonal (link externo, sempre ao lado de "Ver edital oficial"), sino (alerta), escudo (aviso de confiança), seta circular (atualização).
- Interface sem emoji. Em alerta e legenda de post, emoji só como marcador de dado (💰 📅 📍), até três.

## Imagens

- Sem banco de imagem de gente comemorando aprovação, sem foto de prédio público, sem brasão. A imagem da marca é o dado: card, número grifado, mapa de cidades.
- Ilustração, se um dia houver, em formas planas com as cores dos tokens.

## Componentes

Componentes em CSS puro (`components/bundle.css`, prefixo `cc-`), sem depender da stack que for escolhida: Logotipo, Grifo, CardConcurso, Situacao, Botao, FichaEdital, AvisoOficial, CapturaAlerta, MensagemAlerta e PostSocial. Cada um tem prévia e regras próprias.

## Regras de confiança

- Toda ficha mostra o número do edital, a fonte e há quanto tempo foi conferida.
- O botão principal da ficha é sempre "Ver edital oficial" e leva ao site da banca ou do órgão.
- Dado que o edital não traz aparece como "Não informado no edital", nunca estimado.
- O site não usa "Inscreva-se", "inscrição aqui" ou qualquer verbo que sugira que a inscrição acontece nele.
- Anúncio leva "Publicidade"; link de afiliado leva "Link de parceiro".
- Captura de contato só com consentimento marcado pela pessoa, canal a canal, e saída em um clique.

## Logotipo

"concurseiro" em minúsculas, Schibsted Grotesk 800 convertida em curvas, dentro de um grifo, com o ícone à esquerda. Use sempre os arquivos do grupo Marca, nunca o nome redigitado: `logotipo-concurseiro.svg` (com ícone, sobre papel e fundos escuros) e `logotipo-concurseiro-palavra.svg` (só a palavra, sobre verde e em espaços estreitos). O ícone (`icone-app.svg`) é um trecho de edital com uma linha grifada e serve de avatar; o `favicon.svg` guarda só o grifo. A palavra nunca aparece sem o grifo: é o grifo que torna a marca distinta (seção **Nome**).
