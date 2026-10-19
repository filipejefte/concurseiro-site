# Progresso da extração · varredura de 19/10/2026

Atualizado em 19/10/2026 13:19 por `python -m varredura progresso`. A parte de cima é refeita a cada vez; a seção Notas fica como está.

| Fonte | Na fila | Feitos (ficha ou descarte) | Faltam |
| --- | --- | --- | --- |
| AMP-PR | 176 | 176 | 0 |
| DIOE-PR | 50 | 50 | 0 |
| DOU | 499 | 46 | 453 |
| **Total** | **725** | **272** | **453** |

Faltam, por prioridade: P1 (inscrição aberta ou futura): 31 · P2 (previsto (autorização ou banca) dos últimos 120 dias): 4 · P3 (o resto): 418

Fichas: 32 · descartes: 224
PSS na coleta (fora da fila): AMP-PR 4705 · DIOE-PR 339 · DOU 1362
Fontes: DOU: ok · AMP-PR: ok · DIOE-PR: ok

<!-- notas: daqui para baixo, escrito à mão -->

## Notas

- Sessão na nuvem de 19/10 (prompt 02). Fichas e descartes de 14/10 copiados para esta pasta; os nomes da fila casaram.
- Coleta oficial de 19/10 (`coletar --inicial --desde 2026-06-16`): AMP-PR ok, DIOE-PR ok (fonte nova), DOU falhou (sem credenciais do INLABS no ambiente; à tarde, com elas, o login foi recusado). A coleta da tarde trouxe 23 matérias do DIOE de 19/10, nenhuma para a fila.
- Lote 1: 31 atos da AMP de 16/06 a 30/06, todos descarte.
- Lote 2: 53 atos (50 do DIOE-PR, 3 da AMP de 15 a 19/10): 1 ficha nova (DETRAN-PR, previsto), 2 fichas atualizadas (Califórnia: nova licitação da banca; Tunas do Paraná: comissão organizadora) e 50 descartes. Os editais estaduais abertos no período (PCPR, AGEPAR, UNICENTRO, UENP) já tinham inscrição encerrada em 19/10.
- Ficou para trás, e por quê:
  - DOU, nova tentativa em 19/10 à tarde, com as credenciais no ambiente: o INLABS recusou o login. O `logar.php` manda para `acessar.php`, que devolve o formulário de entrada, e nenhum ZIP veio, nem o de 16/10. Conferir no navegador se o e-mail e a senha entram em inlabs.in.gov.br e se o cadastro está confirmado.
  - Os atos federais (413 pendentes em 14/10, mais os de 16/06 a 30/06 e de 15 a 19/10) ficam para quando o login no INLABS funcionar. O INLABS guarda só 4 meses, então os primeiros dias de junho podem já ter saído. Estimativa: 2 a 3 sessões de extração.
  - DIOE-PR: no período, 10 matérias lidas eram PDF escaneado (sem texto) e 51 responderam HTTP 400 ("não está vinculada a uma edição"); essas 61 não passaram pela triagem.
