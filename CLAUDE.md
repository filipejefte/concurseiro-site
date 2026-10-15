# concurseiro: instruções para o Claude Code

Site gratuito que reúne concursos públicos abertos, com o salário na frente, prazos e localização. Ele sempre leva ao edital oficial. "concurseiro" é nome provisório.

## Contexto (decisão de 14/10/2026)

- **MVP parcial:** concursos federais e do Paraná.
- **Atualização:** uma varredura por semana, rodada pelo Filipe com `/varredura`. A primeira (inicial) traz todo concurso com inscrição ainda aberta.
- **Custo fixo zero:**
  - sem banco, servidor ou serviço pago;
  - os dados ficam em `dados/concursos.json`, versionado;
  - o site é estático, no GitHub Pages (https://filipejefte.github.io/concurseiro-site/).
- **Fora do Google:** a v0 mantém o `noindex` em todas as páginas e o `robots.txt` bloqueando buscadores, até os sócios decidirem abrir o site.
- **Ambiente:** Windows com PowerShell. Python 3.11 ou mais novo, caminhos com `pathlib`, nada que dependa de bash.

## Regras fixas (código, textos e dados)

1. O site nunca recebe inscrição nem pagamento. O botão principal da ficha é sempre "Ver edital oficial". Concurso previsto, sem edital, usa "Ver ato oficial".
2. Toda ficha vem de ato oficial (diário oficial ou site da banca), com link. PCI, Folha Dirigida e outros agregadores servem só para conferir cobertura; nunca copie texto ou dado deles.
3. O que o edital não traz fica `null` no JSON e aparece como "Não informado no edital" na tela. Nada de chute.
4. Nada vai ao ar sem uma pessoa conferir os campos críticos: salário de cada cargo, início e fim da inscrição, data da prova objetiva, taxa, banca, cidade e link do edital.
5. A v0 não coleta dado pessoal. Alerta, quando existir, só com opt-in (LGPD).
6. Anúncio leva "Publicidade". Indicação paga leva "Link de parceiro" e `rel="sponsored"`.
7. "Previsto" só com ato oficial de autorização do concurso ou de contratação da banca.
8. Não guarde PDFs de editais no repositório. Ficam só os links e os fatos extraídos; os PDFs baixados vão para `.cache/`, ignorado pelo git.
9. Não invente concurso, órgão, salário ou data. Dado de exemplo fica marcado como fictício (`"ficticio": true`).

## Estrutura

```
index.html, concursos.html, concurso.html (?id=), cidade.html (?ibge=)
cidade-maringa.html          redireciona para cidade.html?ibge=4115200
robots.txt                   bloqueia buscadores (v0)
assets/
  css/                       tokens.css (design system), componentes.css (cc-), site.css (pt-)
  js/config.js               canalWhatsApp e canalTelegram: null ou a URL do canal
  js/dados.js                GERADO por `python -m varredura publicar`; não edite à mão
  js/app.js                  cards, filtros, ficha, cidade, faixa de atualização, folhas
dados/
  schema/concurso.schema.json
  concursos.json             o que está publicado (vazio até a primeira varredura)
  municipios-pr.json         399 municípios (IBGE + coordenadas)
  exemplo/                   12 concursos e 4 cidades fictícios (só com --exemplo)
  varreduras/AAAA-MM-DD/     atos.json, fila/ (fora do git), fichas/, descartes.json,
                             revisao.md, revisao.csv, resumo-telegram.md
varredura/                   pacote Python (fontes, triagem, extração, validação, revisão, publicação)
  instrucoes_extracao.md     como extrair a ficha de um ato (vale para o modo api e para o /varredura)
tests/                       pytest
.claude/commands/varredura.md  passo a passo semanal
```

A situação (aberto, encerra em até 7 dias, previsto, encerrado) não fica no JSON. O `publicar` a calcula na data da varredura; o navegador só refaz a contagem regressiva e marca "Encerrado" pela data de hoje.

## Comandos (PowerShell, na raiz)

```powershell
python -m pip install -r requirements.txt
python -m pytest
python -m http.server 8000                                  # site em http://localhost:8000
python -m varredura coletar --inicial --desde 2026-07-01    # primeira varredura
python -m varredura coletar --semana                        # semanal (desde a última publicada)
python -m varredura pendentes                               # atos da fila sem ficha
python -m varredura validar
python -m varredura revisao
python -m varredura publicar --por "Filipe"                 # só depois da conferência
python -m varredura publicar --exemplo                      # volta o dados.js aos exemplos
python -m varredura municipios                              # refaz a tabela de municípios
```

## O que nunca fazer

- Publicar (`publicar` sem `--exemplo`), fazer commit ou dar push sem o pedido do Filipe. O push publica no GitHub Pages.
- Fazer commit de `.env`, chaves, `.cache/`, PDFs ou da fila de extração.
- Escrever credencial no código ou mostrar o conteúdo do `.env`. Elas vêm de `CONTATO_VARREDURA`, `INLABS_EMAIL`, `INLABS_SENHA` e `ANTHROPIC_API_KEY` (ver `.env.example`).
- Ler dados de agregador, preencher campo por dedução ou inventar valor para passar na validação.
- Marcar `ok` no `revisao.csv` no lugar do Filipe: a conferência é humana.
- Tirar o `noindex` ou mudar o `robots.txt` sem decisão dos sócios.
- Pôr campo de e-mail ou formulário de cadastro no site da v0.
- Passar de 1 requisição por segundo nas fontes, ignorar o `robots.txt` ou fazer a coleta completa fora do `/varredura`.
- Editar `assets/js/dados.js` à mão.
