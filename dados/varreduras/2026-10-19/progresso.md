# Progresso da extração · varredura de 19/10/2026

Atualizado em 21/10/2026 20:42 por `python -m varredura progresso`. A parte de cima é refeita a cada vez; a seção Notas fica como está.

| Fonte | Na fila | Feitos (ficha ou descarte) | Faltam |
| --- | --- | --- | --- |
| AMP-PR | 176 | 176 | 0 |
| DIOE-PR | 50 | 50 | 0 |
| DOU | 430 | 430 | 0 |
| banca-consulpam | 1 | 1 | 0 |
| banca-consulplan | 3 | 3 | 0 |
| banca-fafipa | 4 | 4 | 0 |
| banca-fau | 6 | 6 | 0 |
| banca-quadrix | 5 | 5 | 0 |
| **Total** | **675** | **675** | **0** |

Faltam, por prioridade: P1 (inscrição aberta ou futura): 0 · P2 (previsto (autorização ou banca) dos últimos 120 dias): 0 · P3 (o resto): 0

Fichas: 73 · descartes: 619 · textos extras juntados às fichas (fora da conta da fila): 18
PSS na coleta (fora da fila): AMP-PR 4705 · DIOE-PR 343 · DOU 1049
Fontes: DOU: ok, mas parcial: 12 dia(s) útil(eis) fora do cache sem acesso ao INLABS (2026-06-22 a 2026-06-30, 2026-09-07, 2026-10-12, 2026-10-15 a 2026-10-19): login recusado (403) · AMP-PR: ok · DIOE-PR: ok · BANCAS: ok

<!-- notas: daqui para baixo, escrito à mão -->

## Notas

- Sessão na nuvem de 19 e 20/10 (prompt 02). Fichas e descartes de 14/10 copiados para esta pasta; os nomes da fila casaram.
- Coleta: AMP-PR e DIOE-PR (fonte nova) em 19/10 de manhã; DOU à tarde. O INLABS prende a sessão ao IP e o proxy da nuvem troca de IP a cada conexão, então os ZIPs foram baixados numa conexão só (login e downloads juntos) para o cache e a coleta leu do disco. 16 a 19/06 já tinham saído dos 4 meses do INLABS.
- Lotes 1 e 2 (AMP e DIOE): 1 ficha nova (DETRAN-PR, previsto), Califórnia e Tunas do Paraná atualizadas, descartes do resto.
- DOU: P2 (autorizações do MGI e contratos de banca) feito à mão: 10 previstos e 17 descartes; autorização da CGU e contrato do IFPA juntados às fichas dos editais. P1 e P3 (449 atos) em 6 lotes por órgão, extraídos em paralelo: 34 fichas e 379 descartes. Dúvidas resolvidas lendo as páginas seguintes dos editais no DOU (o INLABS parte edital grande em várias matérias, e as continuações ficam fora da fila).
- Ficou para trás, e por quê:
  - IFMT, Edital 2/2026 (técnico-administrativo, 22 vagas): os 2 retificadores na fila (`dou-2026-07-23-...-dd134e12.md` e `dou-2026-08-20-...-e2508be5.md`) dependem do período de inscrição, que só está no Anexo I em seletivo.ifmt.edu.br, bloqueado na rede da nuvem. No notebook: abrir o Anexo I; se a inscrição já terminou, são descarte.
  - DIOE-PR: no período, 10 matérias lidas eram PDF escaneado (sem texto) e 51 responderam HTTP 400 ("não está vinculada a uma edição"); essas 61 não passaram pela triagem.
  - Pontos para o Filipe na conferência: salários da UFV (Editais 58, 59 e 60) com valores de outra classe no próprio ato (os editais 58 e 59 passam na automática, porque o ato traz o vencimento e a retribuição por extenso e a ficha tem a soma: abra os dois mesmo assim); IFSP sem a vaga de Humanidades (São João da Boa Vista) no quadro retificado; IFMG com divergência de vagas de Ciências Biológicas entre as retificações; bancas do CREMERJ e do CRO/SE identificadas pelo site citado no ato.
- Conferência (20/10): 912 linhas. A primeira revisão deixou 279 para o Filipe fora a amostra (30,6%). Cinco regras novas no `conferir.py`, cada uma com teste de valor certo e de valor errado, para os formatos dos editais do DOU: remuneração no bloco do cargo (Câmara), vencimento de professor que só exige graduação (IFSP, UFC, UFRN), vencimento + retribuição em parcelas (UFMS, UFRN, UFV), valor por classe de técnico-administrativo (IFPA, UFBA) e salário por carreira (TRT8). Agora 788 passam, 82 ficam para o Filipe (9,0%) e 42 são amostra: 124 linhas no total. Conferi por amostragem as linhas que as regras novas aprovaram (UFMS, UFRN, UFV, UFSJ, IFMG, IFPA, UFBA, Câmara, TRT8): todas batem com o ato.

## Prompt 04 (21/10): onde parou

- Feito: regra 11 e hospedagem só no Cloudflare Pages; conferência da soma por classe e titulação (buraco da UFV fechado, com teste de valor errado); os 8 abertos sem salário completos pelo edital cheio; IFMT descartado (inscrição de 20/07 a 10/08); leitores de 7 bancas (FAFIPA, FAU, Quadrix, Omni, Unicampo, Consulplan, Consulpam); `previstos` (Quatro Barras virou aberto); `cobertura` por município; faixa do site e `/como-conferimos/` com as fontes lidas.
- Fichas novas desta sessão: Apucarana, Siqueira Campos (prefeitura e câmara), Curitiba (editais 4, 5 e 6), CRA-AM, Quatro Barras (câmara, de previsto para aberto). Fila sem pendentes; `validar`: tudo certo; 169 testes passando.
- Quatro Barras: o robots.txt da Consulpam proíbe `/arquivos/` (os PDFs). A ficha sai da tabela da página do concurso no site da banca; vagas ficam em branco nos cargos 002, 004 e 006 porque o total da página não fecha com as colunas. O Filipe precisa abrir o PDF do edital.
- Curitiba 5 (nível superior): o edital dá o vencimento e "+ 30% de Gratificação Técnica", sem o total; o campo salário traz só o vencimento e o aviso está nos requisitos.
- Conferência: 171 linhas para o Filipe (82 antes). Perto de metade vem de atos do DOU que não estão na fila (INLABS recusou o login por WAF; faltam 12 dias úteis) e de editais de professor da UFG/UFC. Nenhuma marca `ok` do Filipe existia no HEAD; as 7 `ok` que aparecem são "igual ao publicado".
- Cobertura de bancas (PR municipal, AMP em 4 meses): 20 de 26 municípios com banca identificada usam banca que lemos (77%). Fora: Unioeste/COGEPS (4, portal recusa leitura automática), Legalle (robots.txt proíbe tudo), Instituto UniFil/Filadélfia e Império (sem leitura possível/sem site achado).
- Falta fazer: (a) Câmara de Cantagalo (Unioeste/COGEPS), Pref. de Florestópolis (GAMA) e Pref. de São Jorge do Patrocínio (Instituto UniFil) ficam sem ficha: as três bancas não têm leitura honesta possível hoje (portal da Unioeste recusa robô, UniFil tem desafio de robô, GAMA sem site achado); a banca foi identificada em notícias, só para conferir cobertura, sem copiar dado; (b) decidir Querido Diário e diário próprio de Curitiba (Curitiba já entra pela FAFIPA, então provavelmente dispensável); (c) as 61 matérias do DIOE sem triagem como "ler à mão" (o código existe, conferir a lista na revisão); (d) `gerador build`, verificador de links, Lighthouse mobile e axe nas 4 páginas da prévia; (e) descrição do PR #1 com os passos do Filipe em ordem; (f) push da `lancamento`; (g) relatório final no formato do prompt 04.
