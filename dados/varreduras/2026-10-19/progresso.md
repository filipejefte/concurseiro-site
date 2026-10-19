# Progresso da extração · varredura de 19/10/2026

Atualizado em 19/10/2026 05:40 por `python -m varredura progresso`. A parte de cima é refeita a cada vez; a seção Notas fica como está.

| Fonte | Na fila | Feitos (ficha ou descarte) | Faltam |
| --- | --- | --- | --- |
| AMP-PR | 176 | 176 | 0 |
| DIOE-PR | 50 | 50 | 0 |
| **Total** | **226** | **226** | **0** |

Faltam, por prioridade: P1 (inscrição aberta ou futura): 0 · P2 (previsto (autorização ou banca) dos últimos 120 dias): 0 · P3 (o resto): 0

Fichas: 22 · descartes: 207
PSS na coleta (fora da fila): AMP-PR 4705 · DIOE-PR 332
Fontes: DOU: falhou depois de 0 atos: Defina INLABS_EMAIL e INLABS_SENHA no .env para ler o DOU pelo INLABS. · AMP-PR: ok · DIOE-PR: ok

<!-- notas: daqui para baixo, escrito à mão -->

## Notas

- Sessão na nuvem de 19/10 (prompt 02). Fichas e descartes de 14/10 copiados para esta pasta; os nomes da fila casaram.
- Coleta oficial de 19/10 (`coletar --inicial --desde 2026-06-16`): AMP-PR ok, DIOE-PR ok (fonte nova), DOU falhou (sem credenciais do INLABS no ambiente).
- Lote 1: 31 atos da AMP de 16/06 a 30/06, todos descarte.
- Lote 2: 53 atos (50 do DIOE-PR, 3 da AMP de 15 a 19/10): 1 ficha nova (DETRAN-PR, previsto), 2 fichas atualizadas (Califórnia: nova licitação da banca; Tunas do Paraná: comissão organizadora) e 50 descartes. Os editais estaduais abertos no período (PCPR, AGEPAR, UNICENTRO, UENP) já tinham inscrição encerrada em 19/10.
- Ficou para trás, e por quê:
  - DOU: esta sessão não tem `INLABS_EMAIL` e `INLABS_SENHA`. Os atos federais (413 pendentes em 14/10, mais os de 15 a 19/10) ficam para o notebook ou para quando as credenciais entrarem no ambiente. Estimativa: 2 a 3 sessões de extração.
  - DIOE-PR: 17 matérias sem texto (PDF escaneado) ou fora do ar (HTTP 400) no período; ver o log da coleta.
