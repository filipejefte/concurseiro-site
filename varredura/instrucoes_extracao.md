# Como extrair a ficha de um concurso de um ato oficial

Estas instruções valem para quem segue o `/varredura` no Claude Code. A ficha segue
`dados/schema/concurso.schema.json`.

## Regras

1. **Só o que está no ato.** O que o texto não traz fica `null`. Não deduza salário, data, banca,
   cidade nem link de outra fonte, e nunca use agregadores (PCI Concursos, Folha Dirigida e
   parecidos), nem para completar campo.
2. **Formato.** Datas em `AAAA-MM-DD`. Valores em número: "R$ 1.234,56" vira `1234.56`.
   Jornada em horas por semana (`40`). Vagas em número inteiro; só cadastro reserva = `0` com
   `cadastro_reserva: true`.
3. **Descarte** (não gere ficha) quando o ato:
   - não abre concurso público, não autoriza concurso, não contrata banca e não retifica concurso
     aberto (resultado, convocação, nomeação, prorrogação de validade e parecidos);
   - é processo seletivo simplificado ou contratação temporária;
   - tem inscrição que terminou antes da data da varredura;
   - não é concurso público do Brasil: a cobertura é **todo concurso público do país**, de qualquer UF e
     esfera (federal, estadual, prefeitura, câmara, autarquia, conselho, universidade). Só ficam de fora o
     que não é concurso público (processo seletivo, residência, estágio, vestibular).
4. **Previsto** só com ato oficial de autorização do concurso ou de contratação da banca. Nesse
   caso `inscricao.inicio` e `inscricao.fim` ficam `null`, e `banca` fica `{"nome": null, "url": null}`
   se a banca ainda não foi contratada.
5. **id** estável, em minúsculas e com hífens: `<orgao>-<uf>-<ano>-edital-<nn>`, por exemplo
   `prefeitura-maringa-pr-2026-edital-01`. Previsto sem edital: `<orgao>-<uf>-<ano>`.
   **Retificação** e edital de concurso já previsto usam o MESMO id do concurso que já está em
   `dados/concursos.json` (a lista de ids existentes vem junto) e devolvem a ficha inteira
   atualizada, com o documento novo acrescentado em `documentos`.
6. **Local.** Concurso numa cidade: `uf` da cidade, `municipio_ibge` com o código de 7 dígitos de
   `dados/municipios.json` (todos os municípios do Brasil; `python -c "from varredura.dados import
   municipio_por_nome as m; print(m('SP', 'Campinas'))"` acha o código) e `cidade` com o nome exato da
   tabela. Prefeitura, câmara e órgão estadual precisam do `municipio_ibge`. Federal: `esfera: "federal"`;
   `nacional: true` quando há vagas em vários estados (com `abrangencia` curta, como "14 estados", e `uf` e
   `cidade` da sede); com uma cidade só, a `uf` e a `cidade` dela, e o `municipio_ibge` quando souber.
7. **documentos**: inclua o próprio ato, com `tipo` conforme o que ele é (`edital`, `retificacao`,
   `autorizacao`, `contratacao_banca`), `url` = o link do ato recebido, `fonte` = a fonte recebida
   (`DOU`, `AMP-PR`, `DIOE-PR`; ato de banca é `banca`, e edital que o próprio órgão publica é `outra`), `publicado_em` = a data do ato. Se o ato cita o site da banca
   para inscrição, ele vai em `inscricao.url` e `banca.url`.
8. **area**: uma de Administrativa, Saúde, Educação, Operacional, Policial e segurança, Jurídica,
   Bancária ou Outras, pela maioria das vagas.
9. **Controle**: `ficticio: false`, `conferencia: null`, `primeira_varredura: null`,
   `ultima_alteracao: null`. Quem confere é uma pessoa, depois.
10. **trechos**: para cada campo crítico (`salario`, `inscricao.inicio`, `inscricao.fim`,
    `prova_objetiva`, `taxa`, `banca`, `cidade`, `edital`), copie o trecho literal do ato de onde
    o valor saiu (até 300 caracteres). Para `salario`, um trecho que mostre os salários dos cargos.
    Se o ato não traz o campo, escreva `"não consta no ato"`.

11. **Professor federal** (magistério superior ou EBTT): o `salario` de cada cargo é a remuneração
    total (vencimento básico + retribuição por titulação) da titulação exigida no requisito principal
    do cargo, no regime do cargo (20 h, 40 h ou dedicação exclusiva): o último valor da linha da tabela
    de remuneração. Escreva o regime nos `requisitos` ("dedicação exclusiva" ou "20 horas") e a
    titulação como "titulação mínima: doutorado". Se o edital aceita titulação menor na falta de
    candidatos, preencha `remuneracao_por_titulacao` com a tabela do regime do cargo, uma linha por
    titulação, sempre com o total (`[{"titulacao": "doutorado", "valor": 13753.96}, ...]`); se não
    aceita, deixe `null`. Auxílio-alimentação e outros benefícios vão em `beneficios`.

12. **Ato que é só o extrato.** Quando o ato do DOU é um aviso ou extrato sem os cargos, salários e datas (ele manda ler o edital
    normativo no site da banca ou do órgão), a ficha só fica pronta depois de ler o edital completo: complete cargos, vagas
    (soma das vagas imediatas de todos os códigos do mesmo cargo; só cadastro reserva = `0` com `cadastro_reserva: true`),
    salário, escolaridade, requisitos, jornada, taxa, datas de inscrição e de isenção, prova e benefícios. Ponha o edital
    completo em `documentos` (primeiro, `tipo: "edital"`, `fonte: "banca"` ou `"outra"` quando o órgão mesmo publica; o extrato do
    DOU depois) e o texto em `atos_extras`. `null` ("Não informado no edital") só quando o edital completo não traz o dado.
    Confirme a banca no edital. Não confunda Instituto Consulplan com Instituto Consulpam: são bancas diferentes.
13. **Ato de banca** (`fonte: banca-<slug>`, na fila): é o próprio edital completo, lido da página oficial da banca. Se o concurso
    já tem ficha (feita pelo DOU ou pelo AMP), use o mesmo id e não crie outra: ponha o nome do arquivo em `atos_extras`.
    Residência, programa de estágio, vestibular seriado e processo seletivo simplificado viram descarte.

## Saída

Um único objeto JSON, sem texto antes nem depois:

```json
{
  "descartar": null,
  "trechos": {"salario": "...", "inscricao.inicio": "...", "inscricao.fim": "...", "prova_objetiva": "...",
               "taxa": "...", "banca": "...", "cidade": "...", "edital": "..."},
  "concurso": { "...": "ficha completa no schema" }
}
```

Para descartar: `{"descartar": "motivo curto", "trechos": null, "concurso": null}`.
