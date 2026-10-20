# Progresso da extração · varredura de 19/10/2026

Atualizado em 20/10/2026 00:49 por `python -m varredura progresso`. A parte de cima é refeita a cada vez; a seção Notas fica como está.

| Fonte | Na fila | Feitos (ficha ou descarte) | Faltam |
| --- | --- | --- | --- |
| AMP-PR | 176 | 176 | 0 |
| DIOE-PR | 50 | 50 | 0 |
| DOU | 499 | 497 | 2 |
| **Total** | **725** | **723** | **2** |

Faltam, por prioridade: P1 (inscrição aberta ou futura): 0 · P2 (previsto (autorização ou banca) dos últimos 120 dias): 0 · P3 (o resto): 2

Fichas: 66 · descartes: 616 · textos extras juntados às fichas (fora da conta da fila): 44
PSS na coleta (fora da fila): AMP-PR 4705 · DIOE-PR 339 · DOU 1362
Fontes: DOU: ok · AMP-PR: ok · DIOE-PR: ok

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
