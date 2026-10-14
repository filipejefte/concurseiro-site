/*
  DADOS DE EXEMPLO. Órgãos, cidades, salários, datas e bancas associadas são fictícios,
  criados só para testar o layout. Não publique este arquivo como se fosse informação real.

  Datas e "dias" estão congelados em 13/10/2026 (terça-feira).
  No site de verdade, esta lista vem do motor de dados (robôs dos diários oficiais e das bancas).

  Campos:
    id            identificador da ficha
    orgao, cargo  como aparecem no card ("e mais N cargos" quando há vários)
    cidade, uf    local principal; km = distância a partir de Maringá (PR)
    nacional      true para concurso federal com vagas em vários estados (sem km)
    situacao      "aberto" | "breve" (encerra em 7 dias ou menos) | "previsto" | "encerrado"
    salario       texto do maior salário inicial; valor = o mesmo em número, para ordenar e filtrar
    niveis        escolaridades exigidas, para o filtro
    dias          dias até o fim da inscrição (999 = sem data)
*/
window.LOCAL_PADRAO = { cidade: 'Maringá', uf: 'PR' };

window.AREAS = ['Administrativa', 'Saúde', 'Educação', 'Operacional', 'Policial e segurança', 'Jurídica', 'Bancária'];

window.CONCURSOS = [
  {
    id: 'uev-2026', orgao: 'Universidade Estadual do Vale', cargo: 'Técnico de laboratório e mais 2 cargos',
    cidade: 'Maringá', uf: 'PR', km: 3, nacional: false,
    situacao: 'aberto', situacaoTexto: 'Aberto',
    salario: 'até R$ 5.870,20', valor: 5870.20, beneficio: '+ auxílio-transporte',
    vagas: '18 vagas', escolaridade: 'Técnico e superior', niveis: ['Técnico', 'Superior'], jornada: '40 h',
    prazo: 'seg, 09/11', dias: 27, area: 'Educação', banca: 'Vunesp'
  },
  {
    id: 'hrv-2026', orgao: 'Hospital Regional do Vale', cargo: 'Técnico em radiologia',
    cidade: 'Maringá', uf: 'PR', km: 5, nacional: false,
    situacao: 'aberto', situacaoTexto: 'Aberto',
    salario: 'R$ 3.760,00', valor: 3760.00, beneficio: '+ insalubridade',
    vagas: '12 vagas + CR', escolaridade: 'Técnico', niveis: ['Técnico'], jornada: '24 h',
    prazo: 'qua, 28/10', dias: 15, area: 'Saúde', banca: 'IBFC'
  },
  {
    id: 'ifv-2026', orgao: 'Instituto Federal do Vale', cargo: 'Professor de matemática',
    cidade: 'Maringá', uf: 'PR', km: 6, nacional: false,
    situacao: 'aberto', situacaoTexto: 'Aberto',
    salario: 'até R$ 10.481,64', valor: 10481.64, beneficio: '+ auxílio-alimentação',
    vagas: '2 vagas', escolaridade: 'Superior', niveis: ['Superior'], jornada: '40 h',
    prazo: 'seg, 23/11', dias: 41, area: 'Educação', banca: 'Quadrix'
  },
  {
    id: 'pvv-2026', orgao: 'Prefeitura de Vale Verde (PR)', cargo: 'Engenheiro civil e mais 4 cargos',
    cidade: 'Vale Verde', uf: 'PR', km: 12, nacional: false,
    situacao: 'aberto', situacaoTexto: 'Aberto',
    salario: 'até R$ 9.312,40', valor: 9312.40, beneficio: '+ vale-alimentação',
    vagas: '189 vagas + CR', escolaridade: 'Fundamental a superior', niveis: ['Fundamental', 'Médio', 'Técnico', 'Superior'], jornada: '40 h',
    prazo: 'sex, 20/11', dias: 38, area: 'Administrativa', banca: 'Instituto AOCP'
  },
  {
    id: 'cvv-2026', orgao: 'Câmara de Vale Verde (PR)', cargo: 'Assistente legislativo',
    cidade: 'Vale Verde', uf: 'PR', km: 12.1, nacional: false,
    situacao: 'breve', situacaoTexto: 'Encerra em 3 dias',
    salario: 'R$ 3.120,00', valor: 3120.00, beneficio: '',
    vagas: '4 vagas + CR', escolaridade: 'Médio', niveis: ['Médio'], jornada: '30 h',
    prazo: 'sex, 16/10', dias: 3, area: 'Administrativa', banca: 'Instituto AOCP'
  },
  {
    id: 'csn-2026', orgao: 'Consórcio de Saúde do Norte (PR)', cargo: 'Enfermeiro',
    cidade: 'Campo Alto', uf: 'PR', km: 28, nacional: false,
    situacao: 'aberto', situacaoTexto: 'Aberto',
    salario: 'R$ 6.274,60', valor: 6274.60, beneficio: '+ insalubridade',
    vagas: '32 vagas + CR', escolaridade: 'Superior', niveis: ['Superior'], jornada: '36 h',
    prazo: 'qui, 05/11', dias: 23, area: 'Saúde', banca: 'Instituto AOCP'
  },
  {
    id: 'gmca-2026', orgao: 'Guarda Municipal de Campo Alto (PR)', cargo: 'Guarda municipal',
    cidade: 'Campo Alto', uf: 'PR', km: 28.1, nacional: false,
    situacao: 'previsto', situacaoTexto: 'Previsto',
    salario: 'R$ 3.480,00', valor: 3480.00, beneficio: '+ adicional de risco',
    vagas: '40 vagas', escolaridade: 'Médio', niveis: ['Médio'], jornada: '40 h',
    prazo: 'sem data ainda', dias: 999, area: 'Policial e segurança', banca: 'A definir'
  },
  {
    id: 'samae-2026', orgao: 'SAMAE de Serra Azul (PR)', cargo: 'Operador de estação de tratamento',
    cidade: 'Serra Azul', uf: 'PR', km: 41, nacional: false,
    situacao: 'breve', situacaoTexto: 'Encerra amanhã',
    salario: 'R$ 2.960,40', valor: 2960.40, beneficio: '',
    vagas: '6 vagas', escolaridade: 'Fundamental', niveis: ['Fundamental'], jornada: '44 h',
    prazo: 'qua, 14/10', dias: 1, area: 'Operacional', banca: 'IBFC'
  },
  {
    id: 'prc-2026', orgao: 'Prefeitura de Rio do Campo (PR)', cargo: 'Professor de educação básica',
    cidade: 'Rio do Campo', uf: 'PR', km: 64, nacional: false,
    situacao: 'aberto', situacaoTexto: 'Aberto',
    salario: 'R$ 4.420,55', valor: 4420.55, beneficio: '+ vale-alimentação',
    vagas: '30 vagas + CR', escolaridade: 'Superior', niveis: ['Superior'], jornada: '30 h',
    prazo: 'sex, 06/11', dias: 24, area: 'Educação', banca: 'Vunesp'
  },
  {
    id: 'crc-2026', orgao: 'Câmara de Rio do Campo (PR)', cargo: 'Procurador jurídico',
    cidade: 'Rio do Campo', uf: 'PR', km: 64.1, nacional: false,
    situacao: 'aberto', situacaoTexto: 'Aberto',
    salario: 'R$ 8.950,00', valor: 8950.00, beneficio: '',
    vagas: '1 vaga', escolaridade: 'Superior', niveis: ['Superior'], jornada: '20 h',
    prazo: 'ter, 10/11', dias: 28, area: 'Jurídica', banca: 'Quadrix'
  },
  {
    id: 'fnp-2026', orgao: 'Fundação Nacional de Pesquisa', cargo: 'Analista de pesquisa e mais 6 cargos',
    cidade: 'Brasília', uf: 'DF', km: null, nacional: true, abrangencia: '14 estados',
    situacao: 'aberto', situacaoTexto: 'Aberto',
    salario: 'até R$ 8.480,22', valor: 8480.22, beneficio: '+ auxílio-alimentação',
    vagas: '220 vagas + CR', escolaridade: 'Médio e superior', niveis: ['Médio', 'Superior'], jornada: '40 h',
    prazo: 'sex, 27/11', dias: 45, area: 'Administrativa', banca: 'Cebraspe'
  },
  {
    id: 'bpd-2026', orgao: 'Banco Público de Desenvolvimento', cargo: 'Escriturário',
    cidade: 'Brasília', uf: 'DF', km: null, nacional: true, abrangencia: 'todos os estados',
    situacao: 'aberto', situacaoTexto: 'Aberto',
    salario: 'R$ 4.105,90', valor: 4105.90, beneficio: '+ vale-refeição',
    vagas: '600 vagas + CR', escolaridade: 'Médio', niveis: ['Médio'], jornada: '30 h',
    prazo: 'qua, 18/11', dias: 36, area: 'Bancária', banca: 'FGV'
  }
];
