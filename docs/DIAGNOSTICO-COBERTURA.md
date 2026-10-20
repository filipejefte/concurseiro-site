# Diagnóstico de cobertura (16/10/2026)

Feito sem mudar código, a partir do que está no repositório: `dados/varreduras/2026-10-14/revisao.md` (gerado em 16/10 com o `atos.json` do notebook), `descartes.json`, as fichas e o `revisao.csv`. O `atos.json` e o `.cache/` não estão no repositório, e a sessão que fez este diagnóstico rodou na nuvem, sem acesso às fontes (a rede do ambiente bloqueia `inlabs.in.gov.br`, `www.in.gov.br`, `www.diariomunicipal.com.br` e `*.pr.gov.br`) e sem as credenciais do INLABS.

## Por que só 3 órgãos federais entraram

**O DOU não falhou: a extração parou no Paraná.** A seção "Fila sem ficha nem descarte (extração pendente)" do `revisao.md` lista **413 atos, todos do DOU**, de órgãos federais do Brasil inteiro, que foram coletados e triados mas nunca viraram ficha nem descarte. Só os atos do DOU de órgãos do Paraná (UFPR, UNILA, CRQ-IX, CRM-PR, CREA-PR, TRF4) foram extraídos.

- Período da coleta de 14/10: **01/07/2026 a 14/10/2026** (fila e descartes começam em 01/07; a coleta inicial foi com `--desde 2026-07-01`).
- Fontes: DOU e AMP-PR sem falha registrada; DIOE-PR "pulada" (não implementado).
- O travamento do INLABS em 14/10 não derrubou a coleta: o `revisao.md` não lista o DOU entre as fontes com problema.

| Atos do DOU na fila de extração | n |
| --- | --- |
| Pendentes (sem ficha nem descarte) | 413 |
| Descartados | 11 |
| Viraram ficha (UFPR 276 com a retificação 288, UNILA 240, CRQ-IX) | 4 |
| **Total** | **428** |

Pendentes por órgão (primeiro nível do `artCategory`): universidades federais 150, institutos federais 72, conselhos profissionais 47, Ministério da Gestão e da Inovação 32, fundações universitárias 27, Marinha 24, TRTs 11, Exército 7, TRFs 7, Ministério do Desenvolvimento Agrário 7, Câmara dos Deputados 4, Ebserh 4, outros 21.
Por mês de publicação: julho 137, agosto 109, setembro 114, outubro (até 14) 53.

Provável causa: a regra 3 das instruções ("órgão fora da cobertura (só concursos federais e do Paraná)") foi lida como "federal no Paraná". As instruções agora dizem com todas as letras que concurso federal de qualquer estado está na cobertura.

Outros números da mesma coleta:
- **PSS em avaliação: 5.064** (1.049 do DOU, 4.015 da AMP), fora da fila de propósito. Numa amostra de 25 do DOU, todos eram processo seletivo de professor substituto, contratação temporária ou extrato de contrato: a marca de PSS parece certa.
- Descartes na extração: 126 (115 da AMP, 11 do DOU).
- Atos classificados como "fora" (prefeitura ou estado de outra UF no DOU): o número está no `atos.json` do notebook, que não está no repositório.

## Tamanho do trabalho de 16/06/2026 até hoje

O INLABS guarda 4 meses. Pelo ritmo de 01/07 a 14/10 (428 atos do DOU e uns 130 da AMP na fila em 106 dias):

| Fonte | 16/06 a 16/10 (123 dias), estimado |
| --- | --- |
| DOU (abertura, retificação, autorização, contratação de banca) | cerca de 500 |
| AMP-PR | cerca de 150 |
| **Total para extrair** | **cerca de 650** |

Boa parte dos atos de julho e agosto já tem inscrição encerrada e vira descarte rápido (`python -m varredura pendentes --resumo` mostra o trecho das inscrições de cada ato). Os editais de professor das universidades federais costumam trazer um período de inscrição por item e uma tabela única de remuneração; as duas regras novas da conferência automática (`varredura/conferir.py`) foram feitas para eles.

## DIOE-PR

Em 16/10 não deu para verificar: a rede da sessão bloqueava os domínios `.pr.gov.br`. Em 19/10 a rede abriu e a fonte foi implementada (`varredura/fontes/diario_estado_pr.py`, com testes):

- o portal (www.dioe.pr.gov.br, plataforma IONEWS) é público e gratuito. Não tem `robots.txt` (o endereço devolve a página inicial, sem regras) nem termos de uso publicados, e ato oficial não tem proteção de direito autoral (Lei 9.610/1998, art. 8º, IV). A leitura segue as regras das outras fontes: 1 requisição por segundo, contato no User-Agent e cache;
- há um caderno diário só de concursos, o **Suplemento de Concursos Públicos**, lido inteiro (cerca de 12 matérias por dia). Do **Executivo** (cerca de 400 matérias por dia) e da **Assembleia** saem só as matérias cujo título ou pasta falam de concurso, edital, seleção, banca ou autorização, mais os decretos autônomos e os despachos do governador. As licenças ambientais ficam de fora;
- cada matéria tem página própria, que vira o link do ato. Ela vem em HTML ou é o PDF que o órgão mandou. PDF escaneado fica sem texto, e a coleta conta quantos foram;
- limite conhecido: um extrato de contrato de banca com título genérico ("Extrato de Contrato 12/2026") não é lido.

## Para fechar a cobertura

Em 19 e 20/10, numa sessão na nuvem, as três fontes foram coletadas desde 16/06 (o DOU desde 22/06: os dias anteriores já tinham saído dos 4 meses do INLABS) e extraídas (`dados/varreduras/2026-10-19/`, com o `progresso.md`). A fila tem 725 atos (176 da AMP, 50 do DIOE, 499 do DOU); ficaram 66 fichas e 616 descartes. Faltam 2 atos: os retificadores do Edital 2/2026 do IFMT, cujo período de inscrição só está no Anexo I, em seletivo.ifmt.edu.br, bloqueado na rede da nuvem. No notebook, abra o Anexo I: se a inscrição já terminou, os dois são descarte; se não, faça a ficha no `/varredura`. Depois disso, a cobertura está fechada e o próximo passo é a conferência do `revisao.csv`.

Se precisar refazer a coleta numa pasta nova, as fichas e os descartes de 19/10 continuam valendo: a coleta grava na pasta do dia em que roda (`dados/varreduras/<hoje>/`) e os nomes dos atos na fila são estáveis. Só os atos novos aparecem como pendentes:

```powershell
python -m varredura coletar --inicial --desde 2026-06-16
$nova = (Get-ChildItem dados\varreduras -Directory | Sort-Object Name | Select-Object -Last 1).FullName
New-Item -ItemType Directory "$nova\fichas" -Force | Out-Null
Copy-Item dados\varreduras\2026-10-19\fichas\*.json "$nova\fichas\" -Force
Copy-Item dados\varreduras\2026-10-19\descartes.json "$nova\" -Force
python -m varredura pendentes --resumo        # triagem rápida
# extrair em lotes no /varredura até "0 ato(s) pendente(s)"
python -m varredura validar
python -m varredura revisao                   # revisao.csv e cobertura.csv
```
