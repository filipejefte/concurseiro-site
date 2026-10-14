/*
  Comportamento do site, em JavaScript puro (sem framework e sem build).
  Funciona abrindo o index.html direto no navegador ou em qualquer hospedagem estática (GitHub Pages).

  - Lê window.CONCURSOS, MUNICIPIOS, AREAS e VARREDURA (assets/js/dados.js, gerado por
    `python -m varredura publicar`) e window.CONFIG (assets/js/config.js).
  - Os textos de exibição ("até R$ 9.312,40", "189 vagas + CR", "sex, 20/11") saem dos números e das datas.
  - A situação vem calculada da publicação; aqui só se refaz a contagem e se marca "Encerrado" pela data de hoje.
  - A cidade escolhida fica neste aparelho (localStorage). O GPS é opcional e só acha o município mais próximo.
  - Não coleta dado pessoal: o "Avise-me" leva ao canal do Telegram, ou diz "Alertas em breve".
*/
(function () {
  'use strict';

  var META = window.VARREDURA || { varredura: null, proxima_varredura: null, cobertura: [], exemplo: false };
  var CONFIG = window.CONFIG || {};
  var AREAS = window.AREAS || [];
  var BRUTOS = window.CONCURSOS || [];
  var MUNICIPIOS = (window.MUNICIPIOS || []).map(function (m) {
    return { ibge: m[0], nome: m[1], lat: m[2], lon: m[3], ficticio: !!m[4] };
  });
  var POR_IBGE = {};
  MUNICIPIOS.forEach(function (m) { POR_IBGE[m.ibge] = m; });

  var CHAVE_CIDADE = 'concurseiro:cidade';
  var CIDADE = cidadeGuardada();   // município escolhido pela pessoa, ou null
  var ORIGEM = CIDADE;             // de onde se medem as distâncias (a listagem aceita ?perto=)
  var HOJE = hojeISO();
  var DADOS = [];                  // concursos prontos para exibir (preparar), montados no início

  var NI = '<span class="cc-ni">Não informado no edital</span>';
  var NIVEIS = ['Fundamental', 'Médio', 'Técnico', 'Superior'];
  var SEMANA = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
  var FONTES = {
    'DOU': 'Diário Oficial da União',
    'AMP-PR': 'Diário Oficial dos Municípios do Paraná',
    'DIOE-PR': 'Diário Oficial do Paraná',
    'banca': 'Site da banca',
    'outra': 'Fonte oficial'
  };

  /* ---------- Utilidades ---------- */

  function $(sel, raiz) { return (raiz || document).querySelector(sel); }
  function $$(sel, raiz) { return Array.prototype.slice.call((raiz || document).querySelectorAll(sel)); }
  // Escapa HTML e mantém "R$" colado no valor (espaço inquebrável).
  // "$$" na troca vira um "$" literal; "$&" sozinho repetiria o texto achado ("RR$ nbsp;").
  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
    }).replace(/R\$ /g, 'R$$&nbsp;');
  }
  // Só aceita link http(s); o resto vira "#".
  function url(u) { return /^https?:\/\//.test(u || '') ? esc(u) : '#'; }
  function normalizar(t) { return String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function plural(n, um, varios) { return n === 1 ? um : varios; }
  function contar(n, um, varios) { return n.toLocaleString('pt-BR') + ' ' + plural(n, um, varios); }
  function reais(v) { return 'R$ ' + Number(v).toLocaleString('pt-BR'); }
  function dinheiro(v) { return 'R$ ' + Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function minuscula(t) { return t.charAt(0).toLowerCase() + t.slice(1); }
  function maiuscula(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
  function dois(n) { return (n < 10 ? '0' : '') + n; }
  function existe(v) { return v != null; }

  /* ---------- Datas (ISO AAAA-MM-DD; comparar como texto funciona) ---------- */

  function hojeISO() { var d = new Date(); return d.getFullYear() + '-' + dois(d.getMonth() + 1) + '-' + dois(d.getDate()); }
  function utc(iso) { var p = iso.split('-'); return Date.UTC(+p[0], p[1] - 1, +p[2]); }
  function diasAte(iso) { return Math.round((utc(iso) - utc(HOJE)) / 864e5); }
  function dataCurta(iso) { var d = new Date(utc(iso)); return SEMANA[d.getUTCDay()] + ', ' + dois(d.getUTCDate()) + '/' + dois(d.getUTCMonth() + 1); }
  function dataBR(iso) { return iso.slice(8, 10) + '/' + iso.slice(5, 7) + '/' + iso.slice(0, 4); }

  /* ---------- Cidade escolhida e distância ---------- */

  function cidadeGuardada() {
    try { return POR_IBGE[localStorage.getItem(CHAVE_CIDADE)] || null; } catch (e) { return null; }
  }
  function guardarCidade(ibge) {
    try {
      if (ibge) localStorage.setItem(CHAVE_CIDADE, ibge); else localStorage.removeItem(CHAVE_CIDADE);
      return true;
    } catch (e) { return false; }
  }
  // Haversine, em km.
  function distancia(a, b) {
    var r = Math.PI / 180;
    var dLat = (b.lat - a.lat) * r, dLon = (b.lon - a.lon) * r;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 12742 * Math.asin(Math.sqrt(h));
  }
  function maisProximo(ponto) {
    var melhor = null, menor = Infinity;
    MUNICIPIOS.forEach(function (m) {
      if (m.ficticio) return;
      var d = distancia(ponto, m);
      if (d < menor) { menor = d; melhor = m; }
    });
    return { municipio: melhor, km: menor };
  }

  /* ---------- Do dado ao texto de exibição ---------- */

  function situacaoHoje(c) {
    var fim = c.inscricao.fim;
    if (fim && fim < HOJE) return 'encerrado';
    if (c.situacao === 'aberto' || c.situacao === 'breve') return fim && diasAte(fim) <= 7 ? 'breve' : 'aberto';
    return c.situacao;
  }

  function textoSituacao(s, fim) {
    if (s !== 'breve') return { aberto: 'Aberto', previsto: 'Previsto', encerrado: 'Encerrado' }[s];
    var d = diasAte(fim);
    return d <= 0 ? 'Encerra hoje' : (d === 1 ? 'Encerra amanhã' : 'Encerra em ' + d + ' dias');
  }

  function porSalario(cargos) {
    return cargos.slice().sort(function (a, b) { return (b.salario || 0) - (a.salario || 0); });
  }

  // "189 vagas + CR"; curto: "189 + CR".
  function textoVagas(cargos, curto) {
    var conhecidas = cargos.filter(function (k) { return existe(k.vagas); });
    var cr = cargos.some(function (k) { return k.cadastro_reserva; });
    if (!conhecidas.length) return cr ? 'Cadastro reserva' : 'Vagas não informadas';
    var n = conhecidas.reduce(function (s, k) { return s + k.vagas; }, 0);
    if (n === 0) return 'Cadastro reserva';
    return (curto ? n.toLocaleString('pt-BR') : contar(n, 'vaga', 'vagas')) + (cr ? ' + CR' : '');
  }

  function textoVagasCargo(k) {
    if (!existe(k.vagas)) return k.cadastro_reserva ? 'cadastro reserva' : 'vagas não informadas';
    if (k.vagas === 0) return 'cadastro reserva';
    return contar(k.vagas, 'vaga', 'vagas') + (k.cadastro_reserva ? ' + CR' : '');
  }

  // "Superior", "Técnico e superior", "Fundamental a superior".
  function textoEscolaridade(niveis) {
    if (!niveis.length) return '';
    if (niveis.length === 1) return niveis[0];
    var ultimo = minuscula(niveis[niveis.length - 1]);
    return niveis[0] + (niveis.length === 2 ? ' e ' : ' a ') + ultimo;
  }

  function textoJornada(cargos) {
    var h = cargos.map(function (k) { return k.jornada_horas; }).filter(existe);
    if (!h.length) return null;
    var min = Math.min.apply(null, h), max = Math.max.apply(null, h);
    return min === max ? max + ' h semanais' : min + ' a ' + max + ' h semanais, conforme o cargo';
  }

  function editalDe(c) {
    return c.documentos.filter(function (d) { return d.tipo === 'edital'; })
      .sort(function (a, b) { return (b.publicado_em || '').localeCompare(a.publicado_em || ''); })[0] || null;
  }

  function preparar(c) {
    var cargos = porSalario(c.cargos);
    var principal = cargos[0];
    var salarios = c.cargos.map(function (k) { return k.salario; }).filter(existe);
    var max = salarios.length ? Math.max.apply(null, salarios) : null;
    var varios = salarios.some(function (v) { return v !== max; });
    var niveis = NIVEIS.filter(function (n) { return c.cargos.some(function (k) { return k.escolaridade === n; }); });
    var s = situacaoHoje(c);
    var insc = c.inscricao;
    var mun = POR_IBGE[c.municipio_ibge];
    var prazo = s === 'encerrado' ? dataCurta(insc.fim)
      : s === 'previsto' ? (insc.inicio ? 'a partir de ' + dataCurta(insc.inicio) : 'sem data ainda')
      : (insc.fim ? dataCurta(insc.fim) : 'não informado');
    var b = c.beneficios[0];
    return {
      id: c.id, orgao: c.orgao, cidade: c.cidade, uf: c.uf, area: c.area,
      nacional: c.nacional || c.uf !== 'PR',
      cargo: principal ? principal.nome + (cargos.length > 1 ? ' e mais ' + contar(cargos.length - 1, 'cargo', 'cargos') : '') : 'Cargos não informados',
      salario: max === null ? null : (varios ? 'até ' : '') + dinheiro(max),
      valor: max || 0,
      beneficio: b ? '+ ' + minuscula(b.nome) : '',
      vagas: textoVagas(c.cargos),
      escolaridade: textoEscolaridade(niveis),
      niveis: niveis,
      jornada: principal && principal.jornada_horas ? principal.jornada_horas + ' h' : '',
      banca: c.banca.nome || 'A definir',
      km: !c.nacional && ORIGEM && mun ? distancia(ORIGEM, mun) : null,
      situacao: s,
      situacaoTexto: textoSituacao(s, insc.fim),
      prazo: prazo,
      dias: (s === 'aberto' || s === 'breve') && insc.fim ? diasAte(insc.fim) : 999,
      bruto: c
    };
  }

  var ICONE = {
    aberto: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/></svg>',
    relogio: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    calendario: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M8 3v4M16 3v4M3.5 10h17"/></svg>',
    encerrado: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12h8"/></svg>',
    pino: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>',
    seta: '<svg class="pt-i pt-seta" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>',
    externo: '<svg class="pt-i2 pt-seta" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8"/></svg>',
    externo2: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8"/></svg>',
    voltar: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="m15 6-6 6 6 6"/></svg>',
    documento: '<svg class="pt-i pt-linha-icone" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></svg>',
    globo: '<svg class="pt-i pt-linha-icone" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
    atualizado: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v4.5h-4.5"/></svg>',
    escudo: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 6v5.5c0 4.3 3 7.8 7 9.5 4-1.7 7-5.2 7-9.5V6z"/><path d="m9 12 2 2 4-4"/></svg>',
    abaixo: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>',
    mira: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>',
    fechar: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>',
    aviao: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></svg>'
  };

  /* ---------- Regras de lista ---------- */

  function dentroDoRaio(c, raio) {
    if (c.nacional) return false;
    if (raio === 'estado') return true;
    return c.km !== null && c.km <= Number(raio);
  }
  function km(c) { return c.km === null ? 99999 : c.km; }

  function ordenar(lista, ordem) {
    var l = lista.slice();
    if (ordem === 'salario') l.sort(function (a, b) { return b.valor - a.valor; });
    else if (ordem === 'prazo') l.sort(function (a, b) { return a.dias - b.dias || km(a) - km(b); });
    else l.sort(function (a, b) { return km(a) - km(b) || a.dias - b.dias; });
    return l;
  }

  function ativos() { return DADOS.filter(function (c) { return c.situacao !== 'encerrado'; }); }

  var NOMES_ORDEM = { perto: 'mais perto primeiro', salario: 'maior salário primeiro', prazo: 'inscrição acabando primeiro' };
  var RAIOS = [['10', '10 km'], ['25', '25 km'], ['50', '50 km'], ['100', '100 km'], ['estado', 'Todo o Paraná']];

  function estadoPadrao() {
    return {
      q: '', raio: ORIGEM ? '50' : 'estado', nacionais: !ORIGEM, areas: [], niveis: [], salMin: 0, bancas: [],
      aberto: true, previsto: true, ordem: ORIGEM ? 'perto' : 'prazo'
    };
  }

  function copiar(o) { return JSON.parse(JSON.stringify(o)); }

  // Com busca por texto, procura em todo lugar: o raio só vale para quem navega sem buscar.
  function filtrar(estado) {
    var q = normalizar(estado.q).trim();
    return ativos().filter(function (c) {
      if (!q && !(dentroDoRaio(c, estado.raio) || (estado.nacionais && c.nacional))) return false;
      if (c.situacao === 'previsto' ? !estado.previsto : !estado.aberto) return false;
      if (estado.areas.length && estado.areas.indexOf(c.area) < 0) return false;
      if (estado.niveis.length && !c.niveis.some(function (n) { return estado.niveis.indexOf(n) >= 0; })) return false;
      if (estado.salMin > 0 && c.valor < estado.salMin) return false;
      if (estado.bancas.length && estado.bancas.indexOf(c.banca) < 0) return false;
      if (q && normalizar([c.orgao, c.cargo, c.cidade, c.area, c.banca].join(' ')).indexOf(q) < 0) return false;
      return true;
    });
  }

  function filtrosAtivos(e) {
    var p = estadoPadrao(), n = 0;
    if (e.raio !== p.raio) n++;
    if (e.nacionais !== p.nacionais) n++;
    if (e.areas.length) n++;
    if (e.niveis.length) n++;
    if (e.salMin > 0) n++;
    if (e.bancas.length) n++;
    if (!e.aberto || !e.previsto) n++;
    return n;
  }

  function bancasDisponiveis() {
    var vistas = {};
    ativos().forEach(function (c) { if (c.banca !== 'A definir') vistas[c.banca] = true; });
    return Object.keys(vistas).sort(function (a, b) { return a.localeCompare(b, 'pt-BR'); });
  }

  /* ---------- Peças de interface ---------- */

  function localDoCard(c) {
    if (c.bruto.nacional) return 'Nacional' + (c.bruto.abrangencia ? ' · ' + c.bruto.abrangencia : '');
    var lugar = (c.cidade || 'Cidade não informada') + ' (' + c.uf + ')';
    return c.km !== null && c.km >= 1 ? lugar + ' · a ' + Math.round(c.km) + ' km' : lugar;
  }

  function seloHTML(c) {
    if (c.situacao === 'breve') return '<span class="cc-status cc-status-breve">' + ICONE.relogio + esc(c.situacaoTexto) + '</span>';
    if (c.situacao === 'previsto') return '<span class="cc-status cc-status-previsto">' + ICONE.calendario + 'Previsto</span>';
    if (c.situacao === 'encerrado') return '<span class="cc-status cc-status-encerrado">' + ICONE.encerrado + 'Encerrado</span>';
    return '<span class="cc-status cc-status-aberto">' + ICONE.aberto + 'Aberto</span>';
  }

  function cardHTML(c) {
    var s = c.situacao;
    var salario = c.salario === null ? NI
      : (s === 'encerrado' ? '<span>' + esc(c.salario) + '</span>' : '<span class="cc-grifo">' + esc(c.salario) + '</span>');
    var beneficio = c.beneficio ? '<small>' + esc(c.beneficio) + '</small>' : '';
    var rotuloPrazo = s === 'previsto' ? 'Inscrições:' : (s === 'encerrado' ? 'Encerrou em' : 'Inscrições até');
    var corPrazo = s === 'breve' ? 'var(--prazo)' : (s === 'aberto' ? 'var(--tinta)' : 'var(--tinta-suave)');
    var dados = [c.vagas, c.escolaridade, c.jornada].filter(Boolean).map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('');
    return '' +
      '<a class="cc-card' + (s === 'encerrado' ? ' cc-card-encerrado' : '') + '" href="concurso.html?id=' + encodeURIComponent(c.id) + '">' +
        '<div class="cc-card-topo">' + seloHTML(c) +
          '<span class="cc-card-local">' + ICONE.pino + esc(localDoCard(c)) + '</span></div>' +
        '<div><h3 class="cc-card-orgao">' + esc(c.orgao) + '</h3><p class="cc-card-cargo">' + esc(c.cargo) + '</p></div>' +
        '<div><span class="cc-rotulo">Salário inicial</span><span class="cc-salario">' + salario + beneficio + '</span></div>' +
        '<ul class="cc-dados">' + dados + '</ul>' +
        '<div class="cc-card-rodape">' +
          '<span class="cc-fonte">' + rotuloPrazo + ' <b style="color:' + corPrazo + '">' + esc(c.prazo) + '</b></span>' +
          '<span class="cc-btn cc-btn-texto pt-ver-ficha" aria-hidden="true">Ver ficha</span>' +
        '</div>' +
      '</a>';
  }

  function linhaPrazoHTML(c) {
    return '<li><a class="pt-linha" href="concurso.html?id=' + encodeURIComponent(c.id) + '">' +
      '<span class="pt-linha-txt">' +
        '<span class="pt-linha-tit">' + esc(c.orgao) + '</span>' +
        '<span class="pt-linha-sub">' + esc(c.cargo) + ' · ' + esc(c.salario || 'salário não informado') + '</span>' +
        '<span class="pt-prazo">' + ICONE.relogio + esc(c.situacaoTexto) + ' · ' + esc(c.prazo) + '</span>' +
      '</span>' + ICONE.seta + '</a></li>';
  }

  function publicidadeHTML(formato) {
    return '<aside class="pt-pub" aria-label="Publicidade"><span class="cc-rotulo-pub">Publicidade</span>' +
      '<div class="pt-pub-caixa">Espaço do Google AdSense · ' + esc(formato) + '</div></aside>';
  }

  function textoCobertura() {
    var nomes = { federal: 'federais', PR: 'do Paraná' };
    return 'concursos ' + (META.cobertura || []).map(function (c) { return nomes[c] || c; }).join(' e ');
  }

  // Sem concursos publicados: diz a verdade em vez de mostrar uma lista vazia.
  function semDadosTexto() {
    return META.varredura
      ? '<p class="pt-texto" style="font-weight:600">Nenhum concurso com inscrição aberta agora.</p>'
      : '<p class="pt-texto" style="font-weight:600">A primeira varredura ainda não foi publicada.</p>' +
        '<p class="pt-apoio">Assim que ela sair, os ' + esc(textoCobertura()) + ' aparecem aqui, sempre com o link para o edital oficial.</p>';
  }
  function semDadosHTML() { return '<div class="pt-vazio">' + semDadosTexto() + '</div>'; }

  /* ---------- Em todas as páginas ---------- */

  function iniciarFaixa() {
    var texto;
    if (META.exemplo) texto = 'Dados de exemplo, fictícios · a primeira varredura ainda não foi publicada';
    else if (!META.varredura) texto = 'A primeira varredura ainda não foi publicada';
    else texto = 'Atualizado em ' + dataBR(META.varredura) +
      (META.proxima_varredura ? ' · próxima varredura em ' + dataBR(META.proxima_varredura) : '');
    var topo = $('.pt-topo');
    if (topo) topo.insertAdjacentHTML('afterend', '<div class="pt-faixa"><p class="pt-pagina">' + esc(texto + ' · ' + textoCobertura()) + '</p></div>');
    $$('[data-so-exemplo]').forEach(function (el) { el.hidden = !META.exemplo; });
  }

  function iniciarMenu() {
    var botao = $('[data-menu]');
    var menu = $('#menu-celular');
    if (!botao || !menu) return;
    botao.addEventListener('click', function () {
      var abrir = menu.hasAttribute('hidden');
      menu.toggleAttribute('hidden', !abrir);
      botao.setAttribute('aria-expanded', String(abrir));
      botao.setAttribute('aria-label', abrir ? 'Fechar menu' : 'Abrir menu');
    });
  }

  function fecharMenu() {
    var menu = $('#menu-celular');
    if (menu && !menu.hidden) $('[data-menu]').click();
  }

  // Botão flutuante: vira só o ícone ao rolar, para não cobrir os cards.
  function iniciarBotaoFlutuante() {
    var fab = $('.pt-fab');
    if (!fab) return;
    function ajustar() { fab.classList.toggle('pt-fab-icone', window.scrollY > 80); }
    window.addEventListener('scroll', ajustar, { passive: true });
    ajustar();
  }

  function criarFolha(id, titulo, corpo) {
    var dialogo = document.createElement('dialog');
    dialogo.id = id;
    dialogo.className = 'pt-dialogo';
    dialogo.setAttribute('aria-labelledby', id + '-titulo');
    dialogo.innerHTML = '' +
      '<div class="cc-folha">' +
        '<div class="pt-folha-alca" aria-hidden="true"></div>' +
        '<div class="pt-folha-cab"><div><h2 id="' + id + '-titulo">' + titulo + '</h2></div>' +
          '<button class="pt-icone-btn" type="button" data-fechar aria-label="Fechar">' + ICONE.fechar + '</button></div>' +
        corpo +
      '</div>';
    document.body.appendChild(dialogo);
    $$('[data-fechar]', dialogo).forEach(function (b) { b.addEventListener('click', function () { dialogo.close(); }); });
    dialogo.addEventListener('click', function (ev) { if (ev.target === dialogo) dialogo.close(); });
    return dialogo;
  }

  /* ---------- Folha "Avise-me": canal do Telegram, ou "em breve". Sem formulário, sem dado pessoal. ---------- */

  function iniciarAlerta() {
    var canal = /^https:\/\//.test(CONFIG.canalTelegram || '') ? CONFIG.canalTelegram : null;
    var corpo = canal
      ? '<p>Um canal no Telegram com os concursos novos de cada semana e as inscrições que estão acabando. Você entra e sai quando quiser; não pedimos telefone, e-mail nem cadastro.</p>' +
        '<a class="cc-btn cc-btn-primario cc-btn-bloco" href="' + url(canal) + '" target="_blank" rel="noopener">' + ICONE.aviao + 'Entrar no canal do Telegram</a>'
      : '<p>Ainda não mandamos alertas. Quando o canal do Telegram abrir, o link aparece aqui. Enquanto isso, esta lista é atualizada uma vez por semana.</p>' +
        '<button class="cc-btn cc-btn-primario cc-btn-bloco" type="button" data-fechar>Entendi</button>';
    var dialogo = criarFolha('alerta', canal ? 'Avisos pelo Telegram' : 'Alertas em breve', corpo);
    function abrir(ev) {
      if (ev) ev.preventDefault();
      fecharMenu();
      dialogo.showModal();
    }
    $$('[data-abrir-alerta]').forEach(function (el) { el.addEventListener('click', abrir); });
    if (location.hash === '#alerta') abrir();
  }

  /* ---------- Folha "Sua cidade": lista dos municípios do PR e GPS opcional ---------- */

  function iniciarCidade() {
    var opcoes = MUNICIPIOS.filter(function (m) { return !m.ficticio; })
      .map(function (m) { return '<option value="' + esc(m.nome) + '"></option>'; }).join('');
    var dialogo = criarFolha('cidade', 'Sua cidade', '' +
      '<p>Para mostrar primeiro os concursos perto de você. A escolha fica guardada só neste aparelho.</p>' +
      '<form class="pt-form-alerta" data-form-cidade novalidate>' +
        '<label class="cc-campo">Município do Paraná<input name="cidade" list="lista-municipios" autocomplete="off" placeholder="Comece a digitar" aria-describedby="cidade-erro"></label>' +
        '<datalist id="lista-municipios">' + opcoes + '</datalist>' +
        '<p id="cidade-erro" class="pt-erro-msg" role="alert" hidden>Escolha um município do Paraná da lista.</p>' +
        '<button class="cc-btn cc-btn-primario cc-btn-bloco" type="submit">Usar esta cidade</button>' +
        '<button class="cc-btn cc-btn-bloco" type="button" data-gps>' + ICONE.mira + 'Achar pela minha localização</button>' +
        '<p class="pt-apoio" data-aviso-gps aria-live="polite">Opcional. A localização só serve para achar o município mais próximo e não sai do seu aparelho.</p>' +
        (CIDADE ? '<button class="cc-btn cc-btn-texto" type="button" data-esquecer style="align-self:flex-start">Esquecer minha cidade</button>' : '') +
      '</form>');
    var campo = $('input[name="cidade"]', dialogo);
    var erro = $('#cidade-erro', dialogo);
    var aviso = $('[data-aviso-gps]', dialogo);

    function mostrarErro(texto) {
      erro.textContent = texto;
      erro.hidden = !texto;
      campo.setAttribute('aria-invalid', String(!!texto));
    }
    function escolher(ibge) {
      if (!guardarCidade(ibge)) { mostrarErro('Este navegador não deixou guardar a cidade. Confira se o site pode salvar dados.'); return; }
      location.reload();
    }

    campo.addEventListener('input', function () { mostrarErro(''); });
    $('[data-form-cidade]', dialogo).addEventListener('submit', function (ev) {
      ev.preventDefault();
      var alvo = normalizar(campo.value).trim();
      var m = MUNICIPIOS.filter(function (x) { return !x.ficticio && normalizar(x.nome) === alvo; })[0];
      if (!m) { mostrarErro('Escolha um município do Paraná da lista.'); campo.focus(); return; }
      escolher(m.ibge);
    });
    var esquecer = $('[data-esquecer]', dialogo);
    if (esquecer) esquecer.addEventListener('click', function () { escolher(null); });

    $('[data-gps]', dialogo).addEventListener('click', function () {
      if (!navigator.geolocation) { aviso.textContent = 'Seu navegador não permite usar a localização. Escolha a cidade na lista.'; return; }
      aviso.textContent = 'Procurando…';
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          var r = maisProximo({ lat: pos.coords.latitude, lon: pos.coords.longitude });
          campo.value = r.municipio.nome;
          mostrarErro('');
          aviso.textContent = r.km > 50
            ? 'Você parece estar fora do Paraná. O município do PR mais perto é ' + r.municipio.nome + ', a ' + Math.round(r.km) + ' km. Confira e toque em "Usar esta cidade".'
            : 'Mais perto de você: ' + r.municipio.nome + '. Confira e toque em "Usar esta cidade".';
        },
        function () { aviso.textContent = 'Sem permissão de localização. Escolha a cidade na lista.'; },
        { timeout: 10000, maximumAge: 600000 }
      );
    });

    function abrir(ev) {
      if (ev) ev.preventDefault();
      fecharMenu();
      var filtros = $('#filtros');
      if (filtros && filtros.open) filtros.close();
      campo.value = CIDADE ? CIDADE.nome : '';
      mostrarErro('');
      dialogo.showModal();
    }
    $$('[data-abrir-cidade]').forEach(function (el) { el.addEventListener('click', abrir); });
    if (location.hash === '#cidade') abrir();
  }

  /* ---------- Página inicial ---------- */

  function paginaInicio() {
    $('[data-local-texto]').textContent = CIDADE ? CIDADE.nome + ' (PR) · escolhida por você' : 'Nenhuma cidade escolhida';
    $('[data-rotulo-cidade]').textContent = CIDADE ? 'Alterar' : 'Escolher cidade';
    $('[data-titulo]').textContent = CIDADE ? 'Concursos abertos perto de você' : 'Concursos abertos no Paraná';
    $('[data-titulo-cta]').textContent = CIDADE ? 'Avise-me quando abrir concurso perto de ' + CIDADE.nome : 'Avise-me quando abrir concurso';

    if (!DADOS.length) {
      $$('[data-precisa-dados]').forEach(function (el) { el.hidden = true; });
      $('.pt-principal').insertAdjacentHTML('afterbegin', semDadosHTML());
      return;
    }

    var lista = ativos();
    var locais = CIDADE
      ? ordenar(lista.filter(function (c) { return dentroDoRaio(c, 50); }), 'perto')
      : ordenar(lista.filter(function (c) { return !c.nacional; }), 'prazo');
    $$('[data-n-perto]').forEach(function (el) { el.textContent = contar(locais.length, 'concurso', 'concursos'); });
    $('[data-capa-resto]').textContent = CIDADE ? ' com inscrição aberta ou prevista a até 50 km.' : ' com inscrição aberta ou prevista no Paraná.';
    $('[data-titulo-perto]').textContent = CIDADE ? 'Perto de você' : 'No Paraná';
    $$('[data-ver-perto]').forEach(function (el) { el.textContent = 'Ver ' + plural(locais.length, 'o', 'os') + ' ' + locais.length; });
    $('[data-ver-todos]').textContent = CIDADE ? 'Ver todos os concursos perto de você' : 'Ver todos os concursos do Paraná';
    $('[data-lista="perto"]').innerHTML = locais.slice(0, 4).map(cardHTML).join('') ||
      '<p class="pt-apoio">Nenhum concurso aberto ou previsto a até 50 km agora.</p>';

    var acabando = ordenar(lista.filter(function (c) {
      return c.situacao === 'breve' && (CIDADE ? dentroDoRaio(c, 50) : true);
    }), 'prazo');
    $('[data-lista="encerram"]').innerHTML = acabando.length
      ? acabando.map(linhaPrazoHTML).join('')
      : '<li class="pt-linha"><span class="pt-linha-sub">Nenhuma inscrição ' + (CIDADE ? 'perto de você ' : '') + 'acaba nos próximos 7 dias.</span></li>';

    $('[data-lista="areas"]').innerHTML = AREAS.map(function (a) {
      var n = locais.filter(function (c) { return c.area === a; }).length;
      return '<a class="pt-area" href="concursos.html?area=' + encodeURIComponent(a) + '"><span class="pt-area-nome">' + esc(a) +
        '</span><span class="pt-area-n">' + (n ? n + (CIDADE ? ' perto de você' : ' no Paraná') : (CIDADE ? 'Nenhum perto agora' : 'Nenhum agora')) + '</span></a>';
    }).join('');

    var nacionais = ordenar(lista.filter(function (c) { return c.nacional; }), 'prazo');
    $('[data-secao-nacionais]').hidden = !nacionais.length;
    $('[data-lista="nacionais"]').innerHTML = nacionais.slice(0, 4).map(cardHTML).join('');
    $$('[data-ver-nacionais]').forEach(function (el) { el.textContent = 'Ver ' + plural(nacionais.length, 'o', 'os') + ' ' + nacionais.length; });
  }

  /* ---------- Listagem com filtros ---------- */

  function lerEstadoDaURL() {
    var p = new URLSearchParams(location.search);
    var e = estadoPadrao();
    function lista(nome) { return p.get(nome) ? p.get(nome).split(',').filter(Boolean) : []; }
    e.q = p.get('q') || '';
    if (p.get('raio') && (ORIGEM || p.get('raio') === 'estado')) e.raio = p.get('raio');
    if (p.get('nacionais')) e.nacionais = p.get('nacionais') === '1';
    e.areas = lista('area');
    e.niveis = lista('nivel');
    e.bancas = lista('banca');
    e.salMin = Number(p.get('sal')) || 0;
    if (p.get('situacao') === 'aberto') e.previsto = false;
    if (p.get('situacao') === 'previsto') e.aberto = false;
    if (NOMES_ORDEM[p.get('ordem')]) e.ordem = p.get('ordem');
    return e;
  }

  function salvarEstadoNaURL(e) {
    var padrao = estadoPadrao();
    var p = new URLSearchParams();
    var perto = new URLSearchParams(location.search).get('perto');
    if (perto && POR_IBGE[perto]) p.set('perto', perto);
    if (e.q) p.set('q', e.q);
    if (e.raio !== padrao.raio) p.set('raio', e.raio);
    if (e.nacionais !== padrao.nacionais) p.set('nacionais', e.nacionais ? '1' : '0');
    if (e.areas.length) p.set('area', e.areas.join(','));
    if (e.niveis.length) p.set('nivel', e.niveis.join(','));
    if (e.bancas.length) p.set('banca', e.bancas.join(','));
    if (e.salMin > 0) p.set('sal', String(e.salMin));
    if (e.aberto && !e.previsto) p.set('situacao', 'aberto');
    if (!e.aberto && e.previsto) p.set('situacao', 'previsto');
    if (e.ordem !== padrao.ordem) p.set('ordem', e.ordem);
    var qs = p.toString();
    try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash.replace('#filtros', '')); } catch (err) { /* file:// em alguns navegadores */ }
  }

  function paginaConcursos() {
    var estado = lerEstadoDaURL();
    var lista = $('[data-lista="resultado"]');
    var vazio = $('[data-vazio]');
    var campoBusca = $('#busca-lista');
    if (campoBusca) campoBusca.value = estado.q;
    if (!DADOS.length) $('[data-vazio-texto]').outerHTML = semDadosTexto();

    function render() {
      var res = ordenar(filtrar(estado), estado.ordem);

      var titulo = ORIGEM ? 'Concursos perto de ' + ORIGEM.nome : 'Concursos no Paraná';
      if (estado.q) titulo = 'Resultados para “' + estado.q + '”';
      else if (estado.raio === 'estado') titulo = 'Concursos no Paraná';
      $('[data-titulo]').textContent = titulo;
      document.title = titulo + ' · concurseiro (protótipo)';

      var local = estado.q ? 'Em todos os concursos da lista' : (estado.raio === 'estado'
        ? 'Todo o Paraná'
        : ORIGEM.nome + ' (PR) · a até ' + estado.raio + ' km');
      if (!estado.q && estado.nacionais) local += ' · com nacionais';
      $('[data-resumo-local]').textContent = local;

      $('[data-chips-area]').innerHTML = ['Todas'].concat(AREAS).map(function (a) {
        var ativo = a === 'Todas' ? estado.areas.length === 0 : (estado.areas.length === 1 && estado.areas[0] === a);
        return '<button class="pt-chip" type="button" data-area="' + esc(a) + '" aria-pressed="' + ativo + '">' + esc(a) + '</button>';
      }).join('');

      $$('[data-ordem]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-ordem') === estado.ordem)); });

      var n = filtrosAtivos(estado);
      var selo = $('[data-n-filtros]');
      selo.hidden = n === 0;
      selo.textContent = String(n);

      $('[data-contagem]').textContent = contar(res.length, 'concurso', 'concursos') + ' · ' + NOMES_ORDEM[estado.ordem];

      var partes = res.map(cardHTML);
      if (partes.length > 3) partes.splice(3, 0, publicidadeHTML('320 × 100'));
      lista.innerHTML = partes.join('');
      lista.hidden = res.length === 0;
      vazio.hidden = res.length !== 0;

      salvarEstadoNaURL(estado);
    }

    $('[data-chips-area]').addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-area]');
      if (!b) return;
      var a = b.getAttribute('data-area');
      estado.areas = a === 'Todas' ? [] : [a];
      render();
    });
    $$('[data-ordem]').forEach(function (b) {
      b.addEventListener('click', function () { estado.ordem = b.getAttribute('data-ordem'); render(); });
    });
    var formBusca = $('[data-form-busca]');
    if (formBusca) {
      formBusca.addEventListener('submit', function (ev) {
        ev.preventDefault();
        estado.q = campoBusca.value.trim();
        render();
      });
    }

    iniciarFiltros(function () { return estado; }, function (novo) { estado = novo; render(); });
    render();
  }

  function iniciarFiltros(obterEstado, aplicar) {
    var dialogo = $('#filtros');
    if (!dialogo) return;
    var rascunho = null;
    var corpo = $('[data-filtros-corpo]', dialogo);
    var faixa = $('#faixa-salario', dialogo);

    $('[data-onde]', dialogo).textContent = ORIGEM ? ORIGEM.nome + ' (PR)' : 'Nenhuma cidade escolhida';
    $('[data-rotulo-cidade]', dialogo).textContent = CIDADE ? 'Trocar minha cidade' : 'Escolher minha cidade';

    function chips(lista, selecionados, grupo, unico) {
      return lista.map(function (item) {
        var valor = Array.isArray(item) ? item[0] : item;
        var nome = Array.isArray(item) ? item[1] : item;
        var ativo = unico ? selecionados === valor : selecionados.indexOf(valor) >= 0;
        return '<button class="pt-chip" type="button" data-grupo="' + grupo + '" data-valor="' + esc(valor) + '" aria-pressed="' + ativo + '">' + esc(nome) + '</button>';
      }).join('');
    }

    function render() {
      $('[data-grupo-raio]', dialogo).innerHTML = chips(ORIGEM ? RAIOS : RAIOS.slice(-1), rascunho.raio, 'raio', true);
      $('[data-grupo-areas]', dialogo).innerHTML = chips(AREAS, rascunho.areas, 'areas');
      $('[data-grupo-niveis]', dialogo).innerHTML = chips(NIVEIS, rascunho.niveis, 'niveis');
      $('[data-grupo-bancas]', dialogo).innerHTML = chips(bancasDisponiveis(), rascunho.bancas, 'bancas');
      $('[name="nacionais"]', dialogo).checked = rascunho.nacionais;
      $('[name="aberto"]', dialogo).checked = rascunho.aberto;
      $('[name="previsto"]', dialogo).checked = rascunho.previsto;
      faixa.value = String(rascunho.salMin);
      $('[data-valor-salario]', dialogo).textContent = rascunho.salMin > 0 ? reais(rascunho.salMin) : 'Qualquer salário';
      var n = filtrar(rascunho).length;
      $('[data-ver-resultado]', dialogo).textContent = n === 0 ? 'Nenhum concurso com esses filtros' : 'Ver ' + contar(n, 'concurso', 'concursos');
    }

    corpo.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-grupo]');
      if (!b) return;
      var grupo = b.getAttribute('data-grupo');
      var valor = b.getAttribute('data-valor');
      if (grupo === 'raio') {
        rascunho.raio = valor;
      } else {
        var lista = rascunho[grupo];
        var i = lista.indexOf(valor);
        if (i >= 0) lista.splice(i, 1); else lista.push(valor);
      }
      render();
    });
    ['nacionais', 'aberto', 'previsto'].forEach(function (nome) {
      $('[name="' + nome + '"]', dialogo).addEventListener('change', function (ev) { rascunho[nome] = ev.target.checked; render(); });
    });
    faixa.addEventListener('input', function () { rascunho.salMin = Number(faixa.value); render(); });

    $('[data-limpar]', dialogo).addEventListener('click', function () {
      var q = rascunho.q, ordem = rascunho.ordem;
      rascunho = estadoPadrao();
      rascunho.q = q;
      rascunho.ordem = ordem;
      render();
    });
    $('[data-fechar-filtros]', dialogo).addEventListener('click', function () { dialogo.close(); });
    dialogo.addEventListener('click', function (ev) { if (ev.target === dialogo) dialogo.close(); });
    $('[data-form-filtros]', dialogo).addEventListener('submit', function (ev) {
      ev.preventDefault();
      aplicar(copiar(rascunho));
      dialogo.close();
    });

    function abrir(ev) {
      if (ev) ev.preventDefault();
      rascunho = copiar(obterEstado());
      render();
      dialogo.showModal();
    }
    $$('[data-abrir-filtros]').forEach(function (el) { el.addEventListener('click', abrir); });
    if (location.hash === '#filtros') abrir();
  }

  /* ---------- Página da cidade (cidade.html?ibge=) ---------- */

  function paginaCidade() {
    var param = new URLSearchParams(location.search).get('ibge');
    var cid = POR_IBGE[param] || (!param && CIDADE) || null;
    if (!cid) {
      $('[data-titulo]').textContent = param ? 'Cidade não encontrada' : 'Concursos por cidade';
      $('[data-capa]').textContent = param
        ? 'Este endereço não aponta para um município do Paraná. Escolha a cidade na lista.'
        : 'Escolha uma cidade do Paraná para ver os concursos dela e da região.';
      $$('[data-precisa-cidade]').forEach(function (el) { el.hidden = true; });
      $('[data-escolher-cidade]').hidden = false;
      return;
    }

    $$('[data-nome-cidade]').forEach(function (el) { el.textContent = cid.nome; });
    document.title = 'Concursos abertos em ' + cid.nome + ' (PR) · concurseiro (protótipo)';
    var descricao = $('meta[name="description"]');
    if (descricao) descricao.setAttribute('content', 'Concursos com inscrição aberta em ' + cid.nome + ' (PR) e região: salário, vagas, prazo e link para o edital oficial.');
    $('[data-titulo]').textContent = 'Concursos abertos em ' + cid.nome + ' (PR)';
    $('[data-ver-regiao]').href = 'concursos.html?perto=' + cid.ibge;

    if (!DADOS.length) {
      $$('[data-precisa-dados]').forEach(function (el) { el.hidden = true; });
      $('[data-lista="cidade"]').outerHTML = semDadosHTML();
      return;
    }

    function kmDaCidade(c) { var m = POR_IBGE[c.bruto.municipio_ibge]; return m ? distancia(cid, m) : Infinity; }
    var lista = ativos().filter(function (c) { return !c.nacional; });
    var naCidade = ordenar(lista.filter(function (c) { return c.bruto.municipio_ibge === cid.ibge && c.situacao !== 'previsto'; }), 'prazo');
    var regiao = lista.filter(function (c) { return c.bruto.municipio_ibge !== cid.ibge && kmDaCidade(c) <= 50; });

    $$('[data-n-cidade]').forEach(function (el) { el.textContent = contar(naCidade.length, 'concurso', 'concursos'); });
    $$('[data-n-regiao]').forEach(function (el) { el.textContent = String(regiao.length); });
    $$('[data-n-total]').forEach(function (el) { el.textContent = String(naCidade.length + regiao.length); });
    $('[data-ver-regiao]').hidden = naCidade.length + regiao.length === 0;

    $('[data-lista="cidade"]').innerHTML = naCidade.map(cardHTML).join('') ||
      '<p class="pt-apoio">Nenhum concurso com inscrição aberta na cidade agora.</p>';

    var porCidade = {};
    regiao.forEach(function (c) {
      var g = porCidade[c.cidade] || (porCidade[c.cidade] = { nome: c.cidade, uf: c.uf, km: kmDaCidade(c), abertos: 0, previstos: 0 });
      if (c.situacao === 'previsto') g.previstos++; else g.abertos++;
    });
    $('[data-lista="proximas"]').innerHTML = Object.keys(porCidade).map(function (k) { return porCidade[k]; })
      .sort(function (a, b) { return a.km - b.km; })
      .map(function (g) {
        var partes = [];
        if (g.abertos) partes.push(contar(g.abertos, 'aberto', 'abertos'));
        if (g.previstos) partes.push(contar(g.previstos, 'previsto', 'previstos'));
        return '<li><a class="pt-linha" href="concursos.html?q=' + encodeURIComponent(g.nome) + '"><span class="pt-linha-txt">' +
          '<span class="pt-linha-tit">' + esc(g.nome) + ' (' + esc(g.uf) + ')</span>' +
          '<span class="pt-linha-sub">a ' + Math.round(g.km) + ' km · ' + partes.join(' e ') + '</span></span>' + ICONE.seta + '</a></li>';
      }).join('') || '<li class="pt-linha"><span class="pt-linha-sub">Nenhum concurso aberto nas cidades a até 50 km.</span></li>';

    var todos = naCidade.concat(regiao);
    function contagemPor(campo) {
      var m = {};
      todos.forEach(function (c) { if (c[campo] && c[campo] !== 'A definir') m[c[campo]] = (m[c[campo]] || 0) + 1; });
      return Object.keys(m).sort(function (a, b) { return m[b] - m[a] || a.localeCompare(b, 'pt-BR'); }).map(function (k) { return [k, m[k]]; });
    }
    function chipsDe(campo, param) {
      return contagemPor(campo).map(function (p) {
        return '<a class="pt-chip" href="concursos.html?perto=' + cid.ibge + '&amp;' + param + '=' + encodeURIComponent(p[0]) + '">' +
          esc(p[0]) + ' <span class="pt-chip-n">' + p[1] + '</span></a>';
      }).join('') || '<p class="pt-apoio">Nenhum por enquanto.</p>';
    }
    $('[data-lista="areas-cidade"]').innerHTML = chipsDe('area', 'area');
    $('[data-lista="bancas-cidade"]').innerHTML = chipsDe('banca', 'banca');
  }

  /* ---------- Ficha do concurso (concurso.html?id=) ---------- */

  function fichaHTML(v) {
    var c = v.bruto;
    var ed = editalDe(c);
    var ni = ed ? NI : '<span class="cc-ni">Ainda sem edital</span>';
    var atoPrincipal = ed || c.documentos.filter(function (d) { return d.tipo === 'autorizacao' || d.tipo === 'contratacao_banca'; })[0];
    var botao = atoPrincipal
      ? '<a class="cc-btn cc-btn-primario cc-btn-bloco" href="' + url(atoPrincipal.url) + '" rel="noopener">' + (ed ? 'Ver edital oficial' : 'Ver ato oficial') + ICONE.externo2 + '</a>'
      : '';
    var retif = c.documentos.filter(function (d) { return d.tipo === 'retificacao' && d.publicado_em; })
      .sort(function (a, b) { return b.publicado_em.localeCompare(a.publicado_em); })[0];
    var conferido = c.ficticio ? 'exemplo fictício'
      : (c.conferencia ? 'conferido em ' + dataBR(c.conferencia.conferido_em) : 'não conferido');
    var origem = atoPrincipal ? [atoPrincipal.titulo, conferido, FONTES[atoPrincipal.fonte]] : [conferido];
    if (retif) origem.splice(1, 0, 'retificado em ' + dataCurta(retif.publicado_em));
    var atualizacao = '<span class="cc-atualizacao">' + ICONE.atualizado + esc(origem.join(' · ')) + '</span>';

    var cargos = porSalario(c.cargos);
    var principal = cargos[0];
    var salarios = c.cargos.map(function (k) { return k.salario; }).filter(existe);
    var min = Math.min.apply(null, salarios), max = Math.max.apply(null, salarios);
    var faixaSalario = !salarios.length ? ni : esc(min === max ? dinheiro(max) : dinheiro(min) + ' a ' + dinheiro(max) + ', conforme o cargo');
    var b = c.beneficios[0];
    var detalhe = [principal && principal.nome, b && ('+ ' + minuscula(b.nome) + (b.valor ? ' de ' + dinheiro(b.valor) : ''))].filter(Boolean).join(' · ');

    var insc = c.inscricao;
    var inscricoes = insc.inicio && insc.fim ? dataCurta(insc.inicio) + ' a ' + dataCurta(insc.fim)
      : insc.fim ? 'até ' + dataCurta(insc.fim)
      : insc.inicio ? 'a partir de ' + dataCurta(insc.inicio) : null;
    var resumoInscricao = v.situacao === 'previsto' ? (insc.inicio ? 'a partir de ' + dataCurta(insc.inicio) : 'sem data ainda')
      : (insc.fim ? (v.situacao === 'encerrado' ? 'encerrou ' : 'até ') + dataCurta(insc.fim) : 'não informado');
    var t = c.taxa;
    var taxa = !existe(t.min) && !existe(t.max) ? null
      : (t.min === t.max || !existe(t.max) || !existe(t.min) ? dinheiro(existe(t.min) ? t.min : t.max) : dinheiro(t.min) + ' a ' + dinheiro(t.max) + ', conforme o cargo');
    function linha(rotulo, valor) { return '<dt>' + esc(rotulo) + '</dt><dd>' + (existe(valor) && valor !== '' ? esc(valor) : ni) + '</dd>'; }

    var comMaterias = cargos.filter(function (k) { return k.materias.length; });
    var conteudo = comMaterias.length ? '' +
      '<section id="conteudo-programatico" class="pt-secao">' +
        '<h2 class="pt-h2">Conteúdo programático</h2>' +
        '<details class="pt-acordeao" open>' +
          '<summary>Matérias por cargo' + ICONE.abaixo + '</summary>' +
          '<div class="pt-acordeao-corpo">' +
            '<div class="pt-chips" role="group" aria-label="Cargo">' +
              comMaterias.map(function (k, i) { return '<button class="pt-chip" type="button" data-cargo="' + i + '">' + esc(k.nome) + '</button>'; }).join('') +
            '</div>' +
            comMaterias.map(function (k, i) {
              return '<ul class="pt-materias" data-materias="' + i + '">' + k.materias.map(function (m) { return '<li>' + esc(m) + '</li>'; }).join('') + '</ul>';
            }).join('') +
            '<p class="pt-apoio">Lista completa de tópicos no edital.</p>' +
          '</div>' +
        '</details>' +
      '</section>' : '';

    var docs = c.documentos.map(function (d) {
      var sub = [d.resumo, FONTES[d.fonte], d.publicado_em ? 'publicado em ' + dataCurta(d.publicado_em) : null].filter(Boolean).join(' · ');
      return '<li><a class="pt-linha" href="' + url(d.url) + '" rel="noopener">' + ICONE.documento +
        '<span class="pt-linha-txt"><span class="pt-linha-tit">' + esc(d.titulo) + '</span><span class="pt-linha-sub">' + esc(sub) + '</span></span>' +
        ICONE.externo + '</a></li>';
    });
    var siteBanca = insc.url || c.banca.url;
    if (siteBanca && c.banca.nome) {
      docs.push('<li><a class="pt-linha" href="' + url(siteBanca) + '" rel="noopener">' + ICONE.globo +
        '<span class="pt-linha-txt"><span class="pt-linha-tit">Site da banca</span><span class="pt-linha-sub">' + esc(c.banca.nome) + ' · inscrição e pagamento da taxa</span></span>' +
        ICONE.externo + '</a></li>');
    }

    // Link de parceiro: só no exemplo fictício, até existir parceiro de verdade.
    var parceiro = c.ficticio ? '' +
      '<section class="pt-secao" aria-labelledby="titulo-cursos">' +
        '<div class="pt-secao-cab"><h2 class="pt-h2" id="titulo-cursos">Cursos para este concurso</h2><span class="cc-rotulo-pub">Link de parceiro</span></div>' +
        '<ul class="pt-lista">' +
          '<li><a class="pt-linha" href="#" rel="sponsored noopener"><span class="pt-linha-txt"><span class="pt-linha-tit">' + esc(principal ? principal.nome : c.orgao) + '</span>' +
          '<span class="pt-linha-sub">[Cursinho parceiro] · curso completo · [PREÇO]</span></span>' + ICONE.externo + '</a></li>' +
        '</ul>' +
        '<p class="pt-apoio">Indicação paga: se você comprar por esse link, recebemos uma comissão. O preço é o mesmo para você.</p>' +
      '</section>' : '';

    var voltar = ORIGEM ? 'Concursos perto de ' + ORIGEM.nome : 'Concursos no Paraná';

    return '' +
      '<div style="display:flex;flex-direction:column;gap:4px">' +
        '<a class="pt-voltar" href="concursos.html">' + ICONE.voltar + esc(voltar) + '</a>' +
        '<section class="pt-ficha-topo">' +
          '<div class="cc-card-topo" style="justify-content:flex-start;flex-wrap:wrap;gap:8px 12px">' + seloHTML(v) +
            '<span class="cc-card-local">' + ICONE.pino + esc(localDoCard(v)) + '</span></div>' +
          '<div><h1 class="pt-titulo">' + esc(c.orgao) + '</h1>' +
            '<p class="pt-texto" style="margin-top:4px;color:var(--tinta-suave)">' +
              esc([c.cargos.length ? contar(c.cargos.length, 'cargo', 'cargos') : null, 'banca ' + (c.banca.nome || 'a definir')].filter(Boolean).join(' · ')) + '</p></div>' +
          '<div class="pt-caixa-salario">' +
            '<div><span class="cc-rotulo">Salário inicial</span>' +
              '<span class="cc-salario">' + (v.salario ? '<span class="cc-grifo">' + esc(v.salario) + '</span>' : ni) +
              (detalhe ? '<small>' + esc(detalhe) + '</small>' : '') + '</span></div>' +
            '<dl class="pt-resumo">' +
              '<div><dt>Vagas</dt><dd>' + esc(textoVagas(c.cargos, true)) + '</dd></div>' +
              '<div><dt>Escolaridade</dt><dd>' + (v.escolaridade ? esc(v.escolaridade) : ni) + '</dd></div>' +
              '<div><dt>Inscrições</dt><dd>' + esc(resumoInscricao) + '</dd></div>' +
            '</dl>' +
          '</div>' +
          botao + atualizacao +
          '<nav class="pt-trilho" aria-label="Seções da ficha">' +
            '<a class="pt-chip" href="#salario">Salário</a><a class="pt-chip" href="#vagas">Vagas</a>' +
            '<a class="pt-chip" href="#inscricao">Inscrição e prova</a>' +
            (conteudo ? '<a class="pt-chip" href="#conteudo-programatico">Conteúdo</a>' : '') +
            '<a class="pt-chip" href="#documentos">Documentos</a>' +
          '</nav>' +
        '</section>' +
      '</div>' +

      '<section id="salario" class="pt-secao">' +
        '<h2 class="pt-h2">Salário e benefícios</h2>' +
        '<dl class="cc-ficha">' +
          '<dt>Salário inicial</dt><dd>' + faixaSalario + '</dd>' +
          c.beneficios.map(function (x) { return '<dt>' + esc(x.nome) + '</dt><dd>' + (x.valor ? esc(dinheiro(x.valor)) : '<span class="cc-ni">Valor não informado no edital</span>') + '</dd>'; }).join('') +
          linha('Jornada', textoJornada(c.cargos)) +
          linha('Regime', c.regime) +
        '</dl>' +
        '<p class="pt-apoio">Salário inicial bruto, antes dos descontos. Benefícios aparecem à parte.</p>' +
      '</section>' +

      '<section id="vagas" class="pt-secao">' +
        '<h2 class="pt-h2">Vagas e requisitos</h2>' +
        (cargos.length ? '<ul class="pt-cargos">' + cargos.map(function (k) {
          var info = [textoVagasCargo(k), k.requisitos || k.escolaridade, k.jornada_horas ? k.jornada_horas + ' h' : null].filter(Boolean).join(' · ');
          return '<li><span class="pt-cargo-nome">' + esc(k.nome) + '</span><span class="pt-cargo-sal">' + (existe(k.salario) ? esc(dinheiro(k.salario)) : ni) + '</span>' +
            '<span class="pt-cargo-info">' + esc(info) + '</span></li>';
        }).join('') + '</ul>' : '<p class="pt-texto">' + ni + '</p>') +
        '<p class="pt-apoio">CR é cadastro reserva: aprovados além das vagas, chamados se abrirem novas.</p>' +
      '</section>' +

      '<section id="inscricao" class="pt-secao">' +
        '<h2 class="pt-h2">Inscrição e prova</h2>' +
        '<dl class="cc-ficha">' +
          linha('Inscrições', inscricoes) +
          '<dt>Taxa</dt><dd>' + (taxa ? esc(taxa) : ni) + (c.isencao_regras ? ' · ' + esc(minuscula(c.isencao_regras)) : '') + '</dd>' +
          linha('Pedido de isenção', c.isencao_ate ? 'até ' + dataCurta(c.isencao_ate) : null) +
          linha('Prova objetiva', c.prova_objetiva ? dataCurta(c.prova_objetiva) : null) +
          linha('Local da prova', c.local_prova) +
          linha('O que levar', c.o_que_levar) +
          linha('Banca', c.banca.nome || (ed ? null : 'A definir')) +
        '</dl>' +
      '</section>' +

      conteudo +

      '<section id="documentos" class="pt-secao">' +
        '<h2 class="pt-h2">Documentos</h2>' +
        '<ul class="pt-lista">' + docs.join('') + '</ul>' +
        atualizacao + botao +
      '</section>' +

      publicidadeHTML('320 × 100') +
      parceiro +

      '<div class="cc-aviso" role="note" style="max-width:none">' + ICONE.escudo +
        '<div><strong>Não somos site oficial.</strong> A inscrição e o pagamento da taxa são feitos só no site da banca. Viu um erro nesta ficha? <a class="pt-link" href="#">Avise a gente</a>.</div>' +
      '</div>';
  }

  function paginaConcurso() {
    var id = new URLSearchParams(location.search).get('id');
    var v = DADOS.filter(function (c) { return c.id === id; })[0];
    var alvo = $('[data-ficha]');
    if (!v) {
      document.title = 'Concurso não encontrado · concurseiro (protótipo)';
      alvo.innerHTML = DADOS.length ? '' +
        '<div class="pt-vazio">' +
          '<h1 class="pt-titulo">Não achamos este concurso</h1>' +
          '<p class="pt-texto">' + (id ? 'Não há concurso com o código “' + esc(id) + '”. O link pode estar incompleto, ou o concurso saiu da lista.' : 'O link não diz qual concurso abrir.') + '</p>' +
          '<a class="cc-btn cc-btn-primario" href="concursos.html">Ver os concursos abertos</a>' +
        '</div>' : semDadosHTML();
      return;
    }
    document.title = v.orgao + ' · concurseiro (protótipo)';
    alvo.innerHTML = fichaHTML(v);

    var botoes = $$('[data-cargo]', alvo);
    var listas = $$('[data-materias]', alvo);
    if (!botoes.length) return;
    function mostrar(cargo) {
      botoes.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-cargo') === cargo)); });
      listas.forEach(function (l) { l.hidden = l.getAttribute('data-materias') !== cargo; });
    }
    botoes.forEach(function (b) { b.addEventListener('click', function () { mostrar(b.getAttribute('data-cargo')); }); });
    mostrar(botoes[0].getAttribute('data-cargo'));
  }

  /* ---------- Início ---------- */

  document.addEventListener('DOMContentLoaded', function () {
    var pagina = document.body.getAttribute('data-pagina');
    if (pagina === 'concursos') ORIGEM = POR_IBGE[new URLSearchParams(location.search).get('perto')] || CIDADE;
    DADOS = BRUTOS.map(preparar);

    iniciarFaixa();
    iniciarMenu();
    iniciarAlerta();
    iniciarCidade();
    iniciarBotaoFlutuante();
    if (pagina === 'inicio') paginaInicio();
    if (pagina === 'concursos') paginaConcursos();
    if (pagina === 'cidade') paginaCidade();
    if (pagina === 'concurso') paginaConcurso();
  });
})();
