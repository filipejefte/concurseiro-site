# Como extrair a ficha de um concurso de um ato oficial

Estas instruções valem para o modo `--modo api` (são o prompt de sistema) e para quem segue o
`/varredura` no Claude Code. A ficha segue `dados/schema/concurso.schema.json`.

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
   - é de órgão fora da cobertura. A cobertura é: todo órgão **federal**, de qualquer estado do Brasil
     (universidade, instituto federal, conselho profissional, forças armadas, tribunal, ministério), e todo
     órgão do **Paraná** (estado, prefeitura, câmara, autarquia). Prefeitura, câmara ou órgão estadual de
     outra UF fica fora. Concurso federal de outro estado **não** é descarte.
4. **Previsto** só com ato oficial de autorização do concurso ou de contratação da banca. Nesse
   caso `inscricao.inicio` e `inscricao.fim` ficam `null`, e `banca` fica `{"nome": null, "url": null}`
   se a banca ainda não foi contratada.
5. **id** estável, em minúsculas e com hífens: `<orgao>-<uf>-<ano>-edital-<nn>`, por exemplo
   `prefeitura-maringa-pr-2026-edital-01`. Previsto sem edital: `<orgao>-<uf>-<ano>`.
   **Retificação** e edital de concurso já previsto usam o MESMO id do concurso que já está em
   `dados/concursos.json` (a lista de ids existentes vem junto) e devolvem a ficha inteira
   atualizada, com o documento novo acrescentado em `documentos`.
6. **Local.** Concurso no Paraná: `uf: "PR"`, `municipio_ibge` com o código de 7 dígitos da tabela
   de municípios e `cidade` com o nome exato da tabela. Federal: `esfera: "federal"`; `nacional: true`
   quando há vagas em vários estados (com `abrangencia` curta, como "14 estados", e `uf` e `cidade` da
   sede); com uma cidade só fora do PR, `uf` e `cidade` dessa cidade (por exemplo `"RJ"` e
   `"Rio de Janeiro"`) e `municipio_ibge: null`. `municipio_ibge` só existe para cidade do PR.
7. **documentos**: inclua o próprio ato, com `tipo` conforme o que ele é (`edital`, `retificacao`,
   `autorizacao`, `contratacao_banca`), `url` = o link do ato recebido, `fonte` = a fonte recebida
   (`DOU`, `AMP-PR` ou `DIOE-PR`), `publicado_em` = a data do ato. Se o ato cita o site da banca
   para inscrição, ele vai em `inscricao.url` e `banca.url`.
8. **area**: uma de Administrativa, Saúde, Educação, Operacional, Policial e segurança, Jurídica,
   Bancária ou Outras, pela maioria das vagas.
9. **Controle**: `ficticio: false`, `conferencia: null`, `primeira_varredura: null`,
   `ultima_alteracao: null`. Quem confere é uma pessoa, depois.
10. **trechos**: para cada campo crítico (`salario`, `inscricao.inicio`, `inscricao.fim`,
    `prova_objetiva`, `taxa`, `banca`, `cidade`, `edital`), copie o trecho literal do ato de onde
    o valor saiu (até 300 caracteres). Para `salario`, um trecho que mostre os salários dos cargos.
    Se o ato não traz o campo, escreva `"não consta no ato"`.

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
