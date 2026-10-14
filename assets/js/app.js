/*
  Comportamento do protótipo, em JavaScript puro (sem framework e sem build).
  Funciona abrindo o index.html direto no navegador ou em qualquer hospedagem estática (GitHub Pages).

  - Renderiza os cards a partir de window.CONCURSOS (assets/js/dados.js).
  - Listagem: busca, ordenação, chips de área e a folha de filtros, com o estado na URL.
  - Folha "Avise-me": canal, e-mail, consentimento obrigatório (LGPD) e confirmação.
    Não envia nem guarda nada: a integração (e-mail com opt-in duplo, robô do Telegram) é da próxima etapa.
*/
(function () {
  'use strict';

  var DADOS = window.CONCURSOS || [];
  var AREAS = window.AREAS || [];
  var LOCAL = window.LOCAL_PADRAO || { cidade: 'Maringá', uf: 'PR' };

  /* ---------- Utilidades ---------- */

  function $(sel, raiz) { return (raiz || document).querySelector(sel); }
  function $$(sel, raiz) { return Array.prototype.slice.call((raiz || document).querySelectorAll(sel)); }
  // Escapa HTML e mantém "R$" colado no valor (espaço inquebrável).
  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
    }).replace(/R\$ /g, 'R$&nbsp;');
  }
  function normalizar(t) { return String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function plural(n, um, varios) { return n === 1 ? um : varios; }
  function contar(n, um, varios) { return n + ' ' + plural(n, um, varios); }
  function reais(v) { return 'R$ ' + Number(v).toLocaleString('pt-BR'); }

  var ICONE = {
    aberto: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/></svg>',
    relogio: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    calendario: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M8 3v4M16 3v4M3.5 10h17"/></svg>',
    encerrado: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12h8"/></svg>',
    pino: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>',
    seta: '<svg class="pt-i pt-seta" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>',
    sino: '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16v-5a6 6 0 1 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2.2 2.2 0 0 0 4 0"/></svg>',
    fechar: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>',
    aviao: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></svg>',
    check: '<svg class="pt-i" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/></svg>'
  };

  /* ---------- Regras sobre os dados ---------- */

  function dentroDoRaio(c, raio) {
    if (c.nacional) return false;
    if (raio === 'estado') return c.uf === LOCAL.uf;
    return c.km <= Number(raio);
  }
  function km(c) { return c.nacional ? 99999 : c.km; }

  function ordenar(lista, ordem) {
    var l = lista.slice();
    if (ordem === 'salario') l.sort(function (a, b) { return b.valor - a.valor; });
    else if (ordem === 'prazo') l.sort(function (a, b) { return a.dias - b.dias || km(a) - km(b); });
    else l.sort(function (a, b) { return km(a) - km(b); });
    return l;
  }

  var ESTADO_PADRAO = {
    q: '', raio: '50', nacionais: false, areas: [], niveis: [], salMin: 0, bancas: [],
    aberto: true, previsto: true, ordem: 'perto'
  };
  var NOMES_ORDEM = { perto: 'mais perto primeiro', salario: 'maior salário primeiro', prazo: 'inscrição acabando primeiro' };
  var NIVEIS = ['Fundamental', 'Médio', 'Técnico', 'Superior'];
  var RAIOS = [['10', '10 km'], ['25', '25 km'], ['50', '50 km'], ['100', '100 km'], ['estado', 'Todo o Paraná']];

  function copiar(o) { return JSON.parse(JSON.stringify(o)); }

  // Com busca por texto, procura em todo lugar: o raio só vale para quem navega sem buscar.
  function filtrar(estado) {
    var q = normalizar(estado.q).trim();
    return DADOS.filter(function (c) {
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
    var n = 0;
    if (e.raio !== ESTADO_PADRAO.raio) n++;
    if (e.nacionais) n++;
    if (e.areas.length) n++;
    if (e.niveis.length) n++;
    if (e.salMin > 0) n++;
    if (e.bancas.length) n++;
    if (!e.aberto || !e.previsto) n++;
    return n;
  }

  function bancasDisponiveis() {
    var vistas = {};
    DADOS.forEach(function (c) { if (c.banca && c.banca !== 'A definir') vistas[c.banca] = true; });
    return Object.keys(vistas).sort(function (a, b) { return a.localeCompare(b, 'pt-BR'); });
  }

  /* ---------- Peças de interface ---------- */

  function localDoCard(c) {
    return c.nacional ? 'Nacional · ' + c.abrangencia : c.cidade + ' (' + c.uf + ') · a ' + Math.round(c.km) + ' km';
  }

  function seloHTML(c) {
    if (c.situacao === 'breve') return '<span class="cc-status cc-status-breve">' + ICONE.relogio + esc(c.situacaoTexto) + '</span>';
    if (c.situacao === 'previsto') return '<span class="cc-status cc-status-previsto">' + ICONE.calendario + 'Previsto</span>';
    if (c.situacao === 'encerrado') return '<span class="cc-status cc-status-encerrado">' + ICONE.encerrado + 'Encerrado</span>';
    return '<span class="cc-status cc-status-aberto">' + ICONE.aberto + 'Aberto</span>';
  }

  function cardHTML(c) {
    var s = c.situacao;
    var salario = s === 'encerrado'
      ? '<span>' + esc(c.salario) + '</span>'
      : '<span class="cc-grifo">' + esc(c.salario) + '</span>';
    var beneficio = c.beneficio ? '<small>' + esc(c.beneficio) + '</small>' : '';
    var rotuloPrazo = s === 'previsto' ? 'Inscrições:' : (s === 'encerrado' ? 'Encerrou em' : 'Inscrições até');
    var corPrazo = s === 'breve' ? 'var(--prazo)' : (s === 'aberto' ? 'var(--tinta)' : 'var(--tinta-suave)');
    return '' +
      '<a class="cc-card' + (s === 'encerrado' ? ' cc-card-encerrado' : '') + '" href="concurso.html?id=' + encodeURIComponent(c.id) + '">' +
        '<div class="cc-card-topo">' + seloHTML(c) +
          '<span class="cc-card-local">' + ICONE.pino + esc(localDoCard(c)) + '</span></div>' +
        '<div><h3 class="cc-card-orgao">' + esc(c.orgao) + '</h3><p class="cc-card-cargo">' + esc(c.cargo) + '</p></div>' +
        '<div><span class="cc-rotulo">Salário inicial</span><span class="cc-salario">' + salario + beneficio + '</span></div>' +
        '<ul class="cc-dados"><li>' + esc(c.vagas) + '</li><li>' + esc(c.escolaridade) + '</li><li>' + esc(c.jornada) + '</li></ul>' +
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
        '<span class="pt-linha-sub">' + esc(c.cargo) + ' · ' + esc(c.salario) + '</span>' +
        '<span class="pt-prazo">' + ICONE.relogio + esc(c.situacaoTexto) + ' · ' + esc(c.prazo) + '</span>' +
      '</span>' + ICONE.seta + '</a></li>';
  }

  function publicidadeHTML(formato) {
    return '<aside class="pt-pub" aria-label="Publicidade"><span class="cc-rotulo-pub">Publicidade</span>' +
      '<div class="pt-pub-caixa">Espaço do Google AdSense · ' + esc(formato) + '</div></aside>';
  }

  /* ---------- Cabeçalho: menu do celular ---------- */

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

  /* ---------- Folha "Avise-me" ---------- */

  function iniciarAlerta() {
    var regiao = document.body.getAttribute('data-regiao') || (LOCAL.cidade + ' (' + LOCAL.uf + ') e região');
    var dialogo = document.createElement('dialog');
    dialogo.id = 'alerta';
    dialogo.className = 'pt-dialogo';
    dialogo.setAttribute('aria-labelledby', 'alerta-titulo');
    dialogo.innerHTML = '' +
      '<div class="cc-folha">' +
        '<div class="pt-folha-alca" aria-hidden="true"></div>' +
        '<div class="pt-folha-cab">' +
          '<div><h2 id="alerta-titulo">Avise-me quando abrir concurso</h2>' +
          '<p>Só quando abrir concurso do seu interesse ou quando a inscrição estiver acabando.</p></div>' +
          '<button class="pt-icone-btn" type="button" data-fechar aria-label="Fechar">' + ICONE.fechar + '</button>' +
        '</div>' +
        '<form class="pt-form-alerta" data-form-alerta novalidate>' +
          '<div class="pt-caixa"><span>' + esc(regiao) + ' · todas as áreas</span><a class="pt-link" href="concursos.html#filtros" style="font-size:14px">Alterar</a></div>' +
          '<div class="cc-abas" role="group" aria-label="Canal do alerta">' +
            '<button type="button" data-canal="email" aria-pressed="true">E-mail</button>' +
            '<button type="button" data-canal="telegram" aria-pressed="false">Telegram</button>' +
          '</div>' +
          '<div data-so-email style="display:flex;flex-direction:column;gap:8px">' +
            '<label class="cc-campo">Seu e-mail<input type="email" name="email" placeholder="nome@email.com" autocomplete="email" aria-describedby="alerta-erro"></label>' +
            '<p id="alerta-erro" class="pt-erro-msg" role="alert" hidden>Digite um e-mail válido, como nome@email.com.</p>' +
          '</div>' +
          '<div class="pt-caixa pt-caixa-info" data-so-telegram hidden>' + ICONE.aviao +
            '<span>Você abre o Telegram e toca em Iniciar na conversa com o nosso robô. Não pedimos seu telefone.</span></div>' +
          '<label class="cc-check"><input type="checkbox" name="consentimento">' +
            '<span><span data-texto-consentimento>Quero receber alertas de concursos por e-mail. Posso sair quando quiser.</span> ' +
            '<a href="#" style="color:var(--link)">Política de privacidade</a></span></label>' +
          '<button class="cc-btn cc-btn-primario cc-btn-bloco" type="submit" data-enviar disabled>Ativar alertas</button>' +
          '<span class="cc-letra-miuda">Não vendemos nem repassamos seu contato. Todo alerta tem um link para sair.</span>' +
        '</form>' +
        '<div class="pt-sucesso" data-sucesso hidden>' + ICONE.check +
          '<p class="pt-sucesso-tit">Pronto.</p>' +
          '<p data-texto-sucesso></p>' +
          '<button class="cc-btn cc-btn-primario cc-btn-bloco" type="button" data-fechar>Fechar</button>' +
          '<button class="cc-btn cc-btn-texto" type="button" data-refazer>Usar outro contato</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(dialogo);

    var form = $('[data-form-alerta]', dialogo);
    var email = $('input[name="email"]', dialogo);
    var erro = $('#alerta-erro', dialogo);
    var consentimento = $('input[name="consentimento"]', dialogo);
    var enviar = $('[data-enviar]', dialogo);
    var sucesso = $('[data-sucesso]', dialogo);
    var canal = 'email';

    function mostrarErro(sim) {
      erro.hidden = !sim;
      email.setAttribute('aria-invalid', String(sim));
    }

    function trocarCanal(novo) {
      canal = novo;
      $$('[data-canal]', dialogo).forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-canal') === canal)); });
      $('[data-so-email]', dialogo).hidden = canal !== 'email';
      $('[data-so-telegram]', dialogo).hidden = canal !== 'telegram';
      $('[data-texto-consentimento]', dialogo).textContent = canal === 'email'
        ? 'Quero receber alertas de concursos por e-mail. Posso sair quando quiser.'
        : 'Quero receber alertas de concursos pelo Telegram. Posso sair quando quiser.';
      enviar.textContent = canal === 'email' ? 'Ativar alertas' : 'Abrir o Telegram';
      mostrarErro(false);
    }

    function reiniciar() {
      form.reset();
      form.hidden = false;
      sucesso.hidden = true;
      enviar.disabled = true;
      trocarCanal('email');
    }

    $$('[data-canal]', dialogo).forEach(function (b) {
      b.addEventListener('click', function () { trocarCanal(b.getAttribute('data-canal')); });
    });
    consentimento.addEventListener('change', function () { enviar.disabled = !consentimento.checked; });
    email.addEventListener('input', function () { mostrarErro(false); });

    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      if (!consentimento.checked) return;
      if (canal === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
        mostrarErro(true);
        email.focus();
        return;
      }
      // TODO (integração): e-mail com confirmação (opt-in duplo) ou link do robô do Telegram.
      // O protótipo não envia nem guarda o contato.
      $('[data-texto-sucesso]', dialogo).textContent = canal === 'email'
        ? 'Mandamos um e-mail para você confirmar. Os alertas começam depois disso.'
        : 'Toque em Iniciar na conversa que abriu no Telegram. Os alertas começam depois disso.';
      form.hidden = true;
      sucesso.hidden = false;
    });

    $('[data-refazer]', dialogo).addEventListener('click', reiniciar);
    $$('[data-fechar]', dialogo).forEach(function (b) { b.addEventListener('click', function () { dialogo.close(); }); });
    dialogo.addEventListener('click', function (ev) { if (ev.target === dialogo) dialogo.close(); });
    dialogo.addEventListener('close', function () { if (!sucesso.hidden) reiniciar(); });

    function abrir(ev) {
      if (ev) ev.preventDefault();
      var menu = $('#menu-celular');
      if (menu && !menu.hidden) $('[data-menu]').click();
      dialogo.showModal();
    }
    $$('[data-abrir-alerta]').forEach(function (el) { el.addEventListener('click', abrir); });
    if (location.hash === '#alerta') abrir();
  }

  /* ---------- Página inicial ---------- */

  function paginaInicio() {
    var perto = ordenar(DADOS.filter(function (c) { return dentroDoRaio(c, 50); }), 'perto');
    $$('[data-n-perto]').forEach(function (el) { el.textContent = contar(perto.length, 'concurso', 'concursos'); });
    $$('[data-ver-perto]').forEach(function (el) { el.textContent = 'Ver ' + plural(perto.length, 'o', 'os') + ' ' + perto.length; });

    $('[data-lista="perto"]').innerHTML = perto.slice(0, 4).map(cardHTML).join('');

    var acabando = ordenar(DADOS.filter(function (c) { return dentroDoRaio(c, 50) && c.dias <= 7; }), 'prazo');
    $('[data-lista="encerram"]').innerHTML = acabando.length
      ? acabando.map(linhaPrazoHTML).join('')
      : '<li class="pt-linha"><span class="pt-linha-sub">Nenhuma inscrição perto de você acaba nos próximos 7 dias.</span></li>';

    $('[data-lista="areas"]').innerHTML = AREAS.map(function (a) {
      var n = perto.filter(function (c) { return c.area === a; }).length;
      return '<a class="pt-area" href="concursos.html?area=' + encodeURIComponent(a) + '"><span class="pt-area-nome">' + esc(a) +
        '</span><span class="pt-area-n">' + (n ? n + ' perto de você' : 'Nenhum perto agora') + '</span></a>';
    }).join('');

    var nacionais = DADOS.filter(function (c) { return c.nacional; });
    $('[data-lista="nacionais"]').innerHTML = nacionais.map(cardHTML).join('');
    $$('[data-ver-nacionais]').forEach(function (el) { el.textContent = 'Ver ' + plural(nacionais.length, 'o', 'os') + ' ' + nacionais.length; });
  }

  /* ---------- Listagem com filtros ---------- */

  function lerEstadoDaURL() {
    var p = new URLSearchParams(location.search);
    var e = copiar(ESTADO_PADRAO);
    function lista(nome) { return p.get(nome) ? p.get(nome).split(',').filter(Boolean) : []; }
    e.q = p.get('q') || '';
    if (p.get('raio')) e.raio = p.get('raio');
    e.nacionais = p.get('nacionais') === '1';
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
    var p = new URLSearchParams();
    if (e.q) p.set('q', e.q);
    if (e.raio !== ESTADO_PADRAO.raio) p.set('raio', e.raio);
    if (e.nacionais) p.set('nacionais', '1');
    if (e.areas.length) p.set('area', e.areas.join(','));
    if (e.niveis.length) p.set('nivel', e.niveis.join(','));
    if (e.bancas.length) p.set('banca', e.bancas.join(','));
    if (e.salMin > 0) p.set('sal', String(e.salMin));
    if (e.aberto && !e.previsto) p.set('situacao', 'aberto');
    if (!e.aberto && e.previsto) p.set('situacao', 'previsto');
    if (e.ordem !== ESTADO_PADRAO.ordem) p.set('ordem', e.ordem);
    var qs = p.toString();
    try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash.replace('#filtros', '')); } catch (err) { /* file:// em alguns navegadores */ }
  }

  function paginaConcursos() {
    var estado = lerEstadoDaURL();
    var lista = $('[data-lista="resultado"]');
    var vazio = $('[data-vazio]');
    var campoBusca = $('#busca-lista');
    if (campoBusca) campoBusca.value = estado.q;

    function render() {
      var res = ordenar(filtrar(estado), estado.ordem);

      var titulo = 'Concursos perto de ' + LOCAL.cidade;
      if (estado.q) titulo = 'Resultados para “' + estado.q + '”';
      else if (estado.raio === 'estado') titulo = 'Concursos no Paraná';
      $('[data-titulo]').textContent = titulo;
      document.title = titulo + ' · concurseiro (protótipo)';

      var local = estado.q ? 'Em todo o Brasil' : (estado.raio === 'estado'
        ? 'Todo o Paraná'
        : LOCAL.cidade + ' (' + LOCAL.uf + ') · a até ' + estado.raio + ' km');
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

    function chips(lista, selecionados, grupo, unico) {
      return lista.map(function (item) {
        var valor = Array.isArray(item) ? item[0] : item;
        var nome = Array.isArray(item) ? item[1] : item;
        var ativo = unico ? selecionados === valor : selecionados.indexOf(valor) >= 0;
        return '<button class="pt-chip" type="button" data-grupo="' + grupo + '" data-valor="' + esc(valor) + '" aria-pressed="' + ativo + '">' + esc(nome) + '</button>';
      }).join('');
    }

    function render() {
      $('[data-grupo-raio]', dialogo).innerHTML = chips(RAIOS, rascunho.raio, 'raio', true);
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

    $('[data-localizacao]', dialogo).addEventListener('click', function () {
      var aviso = $('[data-aviso-localizacao]', dialogo);
      if (!navigator.geolocation) { aviso.textContent = 'Seu navegador não permite usar a localização.'; return; }
      navigator.geolocation.getCurrentPosition(
        function () { aviso.textContent = 'Localização recebida. No protótipo, as distâncias continuam calculadas a partir de Maringá.'; },
        function () { aviso.textContent = 'Sem permissão de localização. Seguimos com a cidade da sua conexão.'; },
        { timeout: 8000 }
      );
    });

    $('[data-limpar]', dialogo).addEventListener('click', function () {
      var q = rascunho.q, ordem = rascunho.ordem;
      rascunho = copiar(ESTADO_PADRAO);
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

  /* ---------- Página da cidade ---------- */

  function paginaCidade() {
    var cidade = document.body.getAttribute('data-cidade') || LOCAL.cidade;
    var naCidade = ordenar(DADOS.filter(function (c) { return !c.nacional && c.cidade === cidade && c.situacao !== 'previsto'; }), 'perto');
    var regiao = DADOS.filter(function (c) { return dentroDoRaio(c, 50) && c.cidade !== cidade; });

    $$('[data-n-cidade]').forEach(function (el) { el.textContent = contar(naCidade.length, 'concurso', 'concursos'); });
    $$('[data-n-regiao]').forEach(function (el) { el.textContent = String(regiao.length); });
    $$('[data-n-total]').forEach(function (el) { el.textContent = String(naCidade.length + regiao.length); });

    $('[data-lista="cidade"]').innerHTML = naCidade.map(cardHTML).join('');

    var porCidade = {};
    regiao.forEach(function (c) {
      var g = porCidade[c.cidade] || (porCidade[c.cidade] = { nome: c.cidade, uf: c.uf, km: c.km, abertos: 0, previstos: 0 });
      g.km = Math.min(g.km, c.km);
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
      }).join('');

    var todos = naCidade.concat(regiao);
    function contagemPor(campo) {
      var m = {};
      todos.forEach(function (c) { if (c[campo] && c[campo] !== 'A definir') m[c[campo]] = (m[c[campo]] || 0) + 1; });
      return Object.keys(m).sort(function (a, b) { return m[b] - m[a] || a.localeCompare(b, 'pt-BR'); }).map(function (k) { return [k, m[k]]; });
    }
    $('[data-lista="areas-cidade"]').innerHTML = contagemPor('area').map(function (p) {
      return '<a class="pt-chip" href="concursos.html?area=' + encodeURIComponent(p[0]) + '">' + esc(p[0]) + ' <span class="pt-chip-n">' + p[1] + '</span></a>';
    }).join('');
    $('[data-lista="bancas-cidade"]').innerHTML = contagemPor('banca').map(function (p) {
      return '<a class="pt-chip" href="concursos.html?banca=' + encodeURIComponent(p[0]) + '">' + esc(p[0]) + ' <span class="pt-chip-n">' + p[1] + '</span></a>';
    }).join('');
  }

  /* ---------- Ficha do concurso ---------- */

  function paginaConcurso() {
    var botoes = $$('[data-cargo]');
    var listas = $$('[data-materias]');
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
    iniciarMenu();
    iniciarAlerta();
    var pagina = document.body.getAttribute('data-pagina');
    if (pagina === 'inicio') paginaInicio();
    if (pagina === 'concursos') paginaConcursos();
    if (pagina === 'cidade') paginaCidade();
    if (pagina === 'concurso') paginaConcurso();
  });
})();
