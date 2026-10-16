/*
  O que depende da pessoa, em JavaScript puro (sem framework e sem build). O resto já vem no HTML gerado
  por `python -m gerador build`: com o JavaScript desligado, toda página continua útil.

  - Cidade escolhida (localStorage) e distância até cada concurso; GPS opcional; sugestão pelo IP só no Cloudflare.
  - Perfil (escolaridade, curso técnico, formação), só no aparelho: o card mostra o salário do cargo da pessoa.
  - Listagem: busca, filtros e ordem, com o estado na URL.
  - Ficha: "Este concurso é pra você?" e a contagem até a prova.
  - Situação do dia: o build roda todo dia, mas a página pode ter sido aberta depois; "Encerrado" e "Encerra em N dias" seguem a data de hoje.
  - Folhas (dialog nativo): Avise-me, cidade, perfil, filtros. E-mail pelo Kit só com consentimento marcado.
*/
(function () {
  'use strict';

  var CONFIG = lerJSON('config') || {};
  var BASE = CONFIG.base || '/';
  var HOJE = hojeISO();
  var CHAVE_CIDADE = 'concurseiro:cidade';
  var CHAVE_PERFIL = 'concurseiro:perfil';
  var CHAVE_ANUNCIOS = 'concurseiro:anuncios';
  var ESTUDO = ['Fundamental', 'Médio', 'Superior'];   // "até onde estudou"; técnico é marcado à parte
  var NIVEIS = ['Fundamental', 'Médio', 'Técnico', 'Superior'];
  var NOME_NIVEL = { 'Fundamental': 'Ensino fundamental completo', 'Médio': 'Ensino médio completo', 'Técnico': 'Curso técnico completo', 'Superior': 'Curso superior completo' };
  var CIDADE = cidadeGuardada();   // { ibge, nome, lat, lon, slug } ou null
  var PERFIL = perfilGuardado();   // { escolaridade, tecnico, formacao } ou null

  /* ---------- Utilidades ---------- */

  function $(sel, raiz) { return (raiz || document).querySelector(sel); }
  function $$(sel, raiz) { return Array.prototype.slice.call((raiz || document).querySelectorAll(sel)); }
  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (ch) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]; });
  }
  function lerJSON(id) { var el = document.getElementById(id); try { return el ? JSON.parse(el.textContent) : null; } catch (e) { return null; } }
  function normalizar(t) { return String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function plural(n, um, varios) { return n === 1 ? um : varios; }
  function contar(n, um, varios) { return n.toLocaleString('pt-BR') + ' ' + plural(n, um, varios); }
  function dinheiro(v) { return 'R$ ' + Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function minuscula(t) { return t.charAt(0).toLowerCase() + t.slice(1); }
  function maiuscula(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
  function dois(n) { return (n < 10 ? '0' : '') + n; }
  function hojeISO() { var d = new Date(); return d.getFullYear() + '-' + dois(d.getMonth() + 1) + '-' + dois(d.getDate()); }
  function utc(iso) { var p = iso.split('-'); return Date.UTC(+p[0], p[1] - 1, +p[2]); }
  function diasAte(iso) { return Math.round((utc(iso) - utc(HOJE)) / 864e5); }
  function caminho(c) { return BASE + c.replace(/^\//, ''); }
  function guardar(chave, valor) {
    try { if (valor) localStorage.setItem(chave, JSON.stringify(valor)); else localStorage.removeItem(chave); return true; } catch (e) { return false; }
  }
  function ler(chave) { try { return JSON.parse(localStorage.getItem(chave)); } catch (e) { return null; } }

  // Haversine, em km (a mesma conta do gerador).
  function distancia(a, b) {
    var r = Math.PI / 180;
    var dLat = (b.lat - a.lat) * r, dLon = (b.lon - a.lon) * r;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 12742 * Math.asin(Math.sqrt(h));
  }

  // Dados que só valem para quem usa cidade, GPS ou perfil: baixados uma vez, quando precisa.
  var buscas = {};
  function buscar(nome) {
    if (!buscas[nome]) {
      buscas[nome] = fetch(caminho('/assets/dados/' + nome + '.json')).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      });
    }
    return buscas[nome];
  }
  function municipios() {
    return buscar('municipios').then(function (lista) {
      return lista.map(function (m) { return { ibge: m[0], nome: m[1], lat: m[2], lon: m[3], slug: m[4] || null, ficticio: !!m[5] }; });
    });
  }
  function maisProximo(lista, ponto) {
    var melhor = null, menor = Infinity;
    lista.forEach(function (m) {
      if (m.ficticio) return;
      var d = distancia(ponto, m);
      if (d < menor) { menor = d; melhor = m; }
    });
    return { municipio: melhor, km: menor };
  }

  /* ---------- Cidade e perfil guardados no aparelho ---------- */

  function cidadeGuardada() {
    var c = null;
    try { c = localStorage.getItem(CHAVE_CIDADE); } catch (e) { return null; }
    if (!c) return null;
    if (/^"?\d{7}"?$/.test(c)) return { ibge: c.replace(/"/g, ''), antiga: true };   // protótipo guardava só o código
    try { c = JSON.parse(c); } catch (e) { return null; }
    return c && c.ibge && typeof c.lat === 'number' ? c : null;
  }
  function perfilGuardado() {
    var p = ler(CHAVE_PERFIL);
    return p && ESTUDO.indexOf(p.escolaridade) >= 0 ? p : null;
  }
  function niveisDoPerfil() {
    var n = ESTUDO.slice(0, ESTUDO.indexOf(PERFIL.escolaridade) + 1);
    return PERFIL.tecnico ? n.concat('Técnico') : n;
  }
  // Formação contra o nome e os requisitos do cargo, pelas 5 primeiras letras de cada palavra
  // ("pedagogia" acha "pedagogo"). Cargo de fundamental ou médio não pede formação.
  var GENERICAS = ['tecnico', 'tecnica', 'curso', 'bacharel', 'bacharelado', 'licenciatura', 'graduacao', 'superior', 'completo'];
  function radicais(t) {
    return normalizar(t).split(/[^a-z]+/).filter(function (w) { return w.length >= 4 && GENERICAS.indexOf(w) < 0; })
      .map(function (w) { return w.slice(0, 5); });
  }
  function serveFormacao(nome, escolaridade, requisitos) {
    var r = radicais(PERFIL.formacao);
    if (!r.length || (escolaridade !== 'Superior' && escolaridade !== 'Técnico')) return true;
    var alvo = normalizar(nome + ' ' + (requisitos || ''));
    return alvo.indexOf('qualquer') >= 0 || r.some(function (x) { return alvo.indexOf(x) >= 0; });
  }
  function resumoPerfil() {
    return [NOME_NIVEL[PERFIL.escolaridade], PERFIL.tecnico ? 'curso técnico' : null, PERFIL.formacao || null].filter(Boolean).join(' · ');
  }

  /* ---------- Folhas (dialog nativo) ---------- */

  function fecharMenu() { $$('details.pt-menu[open]').forEach(function (d) { d.open = false; }); }
  function abrirFolha(id) {
    var d = document.getElementById(id);
    if (!d || typeof d.showModal !== 'function') return false;
    fecharMenu();
    $$('dialog[open]').forEach(function (x) { if (x !== d) x.close(); });
    if (!d.open) d.showModal();
    return true;
  }
  function iniciarFolhas() {
    $$('dialog').forEach(function (d) {
      $$('[data-fechar]', d).forEach(function (b) { b.addEventListener('click', function () { d.close(); }); });
      d.addEventListener('click', function (ev) { if (ev.target === d) d.close(); });
    });
    document.addEventListener('click', function (ev) {
      var alvo = ev.target.closest('[data-abrir-alerta], [data-abrir-cidade], [data-abrir-perfil], [data-abrir-filtros]');
      if (!alvo) return;
      var id = alvo.hasAttribute('data-abrir-alerta') ? 'alerta' : alvo.hasAttribute('data-abrir-cidade') ? 'cidade'
        : alvo.hasAttribute('data-abrir-perfil') ? 'perfil' : 'filtros';
      if (abrirFolha(id)) ev.preventDefault();
    });
    var hash = location.hash.slice(1);
    if (['alerta', 'cidade', 'perfil', 'filtros'].indexOf(hash) >= 0) abrirFolha(hash);
  }

  /* ---------- Avise-me: e-mail pelo Kit, só com a caixa de consentimento marcada ---------- */

  function iniciarKit() {
    $$('[data-form-kit]').forEach(function (form) {
      var caixa = $('[data-consentimento]', form);
      var botao = $('[data-enviar]', form);
      var sucesso = form.parentNode.querySelector('[data-sucesso-kit]');
      botao.disabled = !caixa.checked;
      caixa.addEventListener('change', function () { botao.disabled = !caixa.checked; });
      form.addEventListener('submit', function (ev) {
        if (!caixa.checked) { ev.preventDefault(); return; }
        if (!window.fetch) return;   // sem fetch, o formulário vai direto ao Kit
        ev.preventDefault();
        botao.disabled = true;
        fetch(form.action, { method: 'POST', body: new FormData(form), headers: { Accept: 'application/json' } })
          .then(function (r) { if (!r.ok) throw new Error(r.status); form.hidden = true; sucesso.hidden = false; })
          .catch(function () { form.submit(); });   // sem resposta legível: envia do jeito normal (o Kit redireciona)
      });
    });
  }

  /* ---------- Folha "Sua cidade": lista dos municípios do PR, GPS opcional e sugestão pelo IP ---------- */

  function iniciarCidade() {
    var dialogo = document.getElementById('cidade');
    if (!dialogo) return;
    var form = $('[data-form-cidade]', dialogo);
    var campo = $('input[name="cidade"]', dialogo);
    var erro = $('#cidade-erro', dialogo);
    var aviso = $('[data-aviso-gps]', dialogo);
    var esquecer = $('[data-esquecer]', dialogo);
    var lista = null;
    esquecer.hidden = !CIDADE;

    function preparar() {
      if (lista) return Promise.resolve(lista);
      return municipios().then(function (l) {
        lista = l.filter(function (m) { return !m.ficticio; });
        $('#lista-municipios', dialogo).innerHTML = lista.map(function (m) { return '<option value="' + esc(m.nome) + '"></option>'; }).join('');
        return lista;
      });
    }
    function mostrarErro(texto) {
      erro.textContent = texto;
      erro.hidden = !texto;
      campo.setAttribute('aria-invalid', String(!!texto));
    }
    function escolher(m) {
      var valor = m ? { ibge: m.ibge, nome: m.nome, lat: m.lat, lon: m.lon, slug: m.slug } : null;
      if (!guardar(CHAVE_CIDADE, valor)) { mostrarErro('Este navegador não deixou guardar a cidade. Confira se o site pode salvar dados.'); return; }
      location.reload();
    }
    dialogo.addEventListener('focusin', preparar, { once: true });
    $$('[data-abrir-cidade]').forEach(function (b) { b.addEventListener('click', function () { campo.value = CIDADE && CIDADE.nome ? CIDADE.nome : ''; mostrarErro(''); preparar(); }); });
    campo.addEventListener('input', function () { mostrarErro(''); });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      preparar().then(function (l) {
        var alvo = normalizar(campo.value).trim();
        var m = l.filter(function (x) { return normalizar(x.nome) === alvo; })[0];
        if (!m) { mostrarErro('Escolha um município do Paraná da lista.'); campo.focus(); return; }
        escolher(m);
      }).catch(function () { mostrarErro('Não deu para carregar a lista de municípios. Tente de novo.'); });
    });
    esquecer.addEventListener('click', function () { escolher(null); });

    $('[data-gps]', dialogo).addEventListener('click', function () {
      if (!navigator.geolocation) { aviso.textContent = 'Seu navegador não permite usar a localização. Escolha a cidade na lista.'; return; }
      aviso.textContent = 'Procurando…';
      navigator.geolocation.getCurrentPosition(function (pos) {
        preparar().then(function (l) {
          var r = maisProximo(l, { lat: pos.coords.latitude, lon: pos.coords.longitude });
          campo.value = r.municipio.nome;
          mostrarErro('');
          aviso.textContent = r.km > 50
            ? 'Você parece estar fora do Paraná. O município do PR mais perto é ' + r.municipio.nome + ', a ' + Math.round(r.km) + ' km. Confira e toque em "Usar esta cidade".'
            : 'Mais perto de você: ' + r.municipio.nome + '. Confira e toque em "Usar esta cidade".';
        });
      }, function () { aviso.textContent = 'Sem permissão de localização. Escolha a cidade na lista.'; },
      { timeout: 10000, maximumAge: 600000 });
    });

    // Cidade guardada pelo protótipo (só o código): completa com nome e coordenadas.
    if (CIDADE && CIDADE.antiga) {
      preparar().then(function (l) {
        var m = l.filter(function (x) { return x.ibge === CIDADE.ibge; })[0];
        guardar(CHAVE_CIDADE, m ? { ibge: m.ibge, nome: m.nome, lat: m.lat, lon: m.lon, slug: m.slug } : null);
        location.reload();
      });
      return;
    }
    if (!CIDADE && CONFIG.localIP) sugerirPeloIP(preparar, escolher);
  }

  // Só no Cloudflare: a Pages Function /api/local devolve a região estimada pelo IP. Nada é guardado.
  function sugerirPeloIP(preparar, escolher) {
    fetch(caminho('/api/local'), { headers: { Accept: 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (local) {
        if (!local || local.regiao !== 'PR' || typeof local.lat !== 'number') return null;
        return preparar().then(function (l) { return maisProximo(l, local); });
      })
      .then(function (r) {
        if (!r || !r.municipio || r.km > 40) return;
        var m = r.municipio;
        $$('[data-perto], [data-sugestao-ip]').forEach(function (caixa) {
          caixa.innerHTML = '';
          caixa.appendChild(document.createTextNode('Você está perto de ' + m.nome + '? '));
          var b = document.createElement('button');
          b.type = 'button';
          b.className = 'pt-link-btn';
          b.textContent = 'Usar esta cidade';
          b.addEventListener('click', function () { escolher(m); });
          caixa.appendChild(b);
          caixa.hidden = false;
        });
      })
      .catch(function () { /* fora do Cloudflare ou sem rede: só não sugere */ });
  }

  /* ---------- Folha "Seu perfil" ---------- */

  function iniciarPerfil() {
    var dialogo = document.getElementById('perfil');
    if (!dialogo) return;
    var form = $('[data-form-perfil]', dialogo);
    var erro = $('#perfil-erro', dialogo);
    var apagar = $('[data-apagar-perfil]', dialogo);
    apagar.hidden = !PERFIL;
    function salvar(p) {
      if (!guardar(CHAVE_PERFIL, p)) { erro.textContent = 'Este navegador não deixou guardar o perfil. Confira se o site pode salvar dados.'; erro.hidden = false; return; }
      location.reload();
    }
    $$('[data-abrir-perfil]').forEach(function (b) {
      b.addEventListener('click', function () {
        form.elements.escolaridade.value = PERFIL ? PERFIL.escolaridade : '';
        form.elements.tecnico.checked = !!(PERFIL && PERFIL.tecnico);
        form.elements.formacao.value = PERFIL ? PERFIL.formacao || '' : '';
        erro.hidden = true;
      });
    });
    form.addEventListener('change', function () { erro.hidden = true; });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var nivel = form.elements.escolaridade.value;
      if (!nivel) { erro.textContent = 'Escolha até onde você estudou.'; erro.hidden = false; return; }
      salvar({ escolaridade: nivel, tecnico: form.elements.tecnico.checked, formacao: form.elements.formacao.value.trim() });
    });
    apagar.addEventListener('click', function () { salvar(null); });
    $$('[data-perfil-texto]').forEach(function (el) { el.textContent = PERFIL ? resumoPerfil() : 'Para ver o salário do seu cargo,'; });
    $$('[data-rotulo-perfil]').forEach(function (el) { el.textContent = PERFIL ? 'Alterar' : 'diga sua escolaridade'; });
    $$('[data-rotulo-perfil-ficha]').forEach(function (el) { el.textContent = PERFIL ? 'Alterar meu perfil' : 'Dizer minha escolaridade'; });
  }

  /* ---------- Cards: situação do dia, distância e salário do perfil ---------- */

  function selo(el, sit, fim) {
    if (!el) return;
    var texto = { aberto: 'Aberto', previsto: 'Previsto', encerrado: 'Encerrado' }[sit];
    if (sit === 'breve') {
      var d = diasAte(fim);
      texto = d <= 0 ? 'Encerra hoje' : d === 1 ? 'Encerra amanhã' : 'Encerra em ' + d + ' dias';
    }
    el.className = 'cc-status cc-status-' + sit;
    el.lastChild.textContent = texto;
  }
  function situacaoHoje(sit, fim) {
    if (sit === 'previsto' || !fim) return sit;
    if (fim < HOJE) return 'encerrado';
    return diasAte(fim) <= 7 ? 'breve' : 'aberto';
  }
  function atualizarSituacao() {
    $$('[data-card]').forEach(function (card) {
      var sit = situacaoHoje(card.getAttribute('data-sit'), card.getAttribute('data-fim'));
      if (sit !== card.getAttribute('data-sit') || sit === 'breve') {
        card.setAttribute('data-sit', sit);
        selo($('[data-selo]', card), sit, card.getAttribute('data-fim'));
        card.classList.toggle('cc-card-encerrado', sit === 'encerrado');
      }
    });
    var ficha = $('[data-ficha]');
    if (ficha && ficha.getAttribute('data-fim')) {
      var s = $('[data-selo]', ficha);
      var atual = s.className.replace(/.*cc-status-/, '');
      var nova = situacaoHoje(atual, ficha.getAttribute('data-fim'));
      if (nova !== atual || nova === 'breve') selo(s, nova, ficha.getAttribute('data-fim'));
    }
  }

  function kmDoCard(card, origem) {
    if (!origem || !card.hasAttribute('data-lat')) return null;
    return distancia(origem, { lat: +card.getAttribute('data-lat'), lon: +card.getAttribute('data-lon') });
  }
  function mostrarDistancias(origem) {
    $$('[data-card]').forEach(function (card) {
      var km = kmDoCard(card, origem);
      card._km = km;
      var local = $('[data-local]', card);
      if (!local.hasAttribute('data-original')) local.setAttribute('data-original', local.textContent);
      local.textContent = local.getAttribute('data-original') + (km !== null && km >= 1 ? ' · a ' + Math.round(km) + ' km' : '');
    });
  }

  // Com perfil, o card fala do cargo da pessoa: nome, salário e "nenhum cargo para o seu perfil".
  function aplicarPerfilNosCards() {
    if (!PERFIL || !$('[data-card]')) return Promise.resolve();
    return buscar('cargos').then(function (todos) {
      var niveis = niveisDoPerfil();
      $$('[data-card]').forEach(function (card) {
        var cargos = todos[card.getAttribute('data-id')];
        if (!cargos || !cargos.length) return;
        var meus = cargos.filter(function (k) { return niveis.indexOf(k[2]) >= 0 && serveFormacao(k[0], k[2], k[3]); });
        var sal = $('[data-salario]', card);
        // Cargo sem escolaridade na ficha: não dá para dizer que não serve. O card fica como está.
        if (!meus.length && cargos.some(function (k) { return !k[2]; })) return;
        if (!meus.length) {
          card.setAttribute('data-sal', '0');
          var grifo = $('.cc-grifo', sal);
          if (grifo) grifo.className = '';
          var aviso = $('small', sal) || sal.appendChild(document.createElement('small'));
          aviso.textContent = 'nenhum cargo para o seu perfil';
          return;
        }
        var valores = meus.map(function (k) { return k[1]; }).filter(function (v) { return v != null; });
        var max = valores.length ? Math.max.apply(null, valores) : null;
        card.setAttribute('data-sal', String(max || 0));
        $('[data-rotulo-salario]', card).textContent = 'Salário para você';
        $('[data-cargo]', card).textContent = meus[0][0] + (meus.length > 1 ? ' e mais ' + contar(meus.length - 1, 'cargo', 'cargos') + ' para você' : '');
        if (max !== null) {
          var alvo = $('.cc-grifo', sal) || $('span', sal);
          if (alvo) alvo.textContent = (valores.some(function (v) { return v !== max; }) ? 'até ' : '') + dinheiro(max);
        }
      });
    }).catch(function () { /* sem os cargos, o card fica com o salário do edital */ });
  }

  /* ---------- Início ---------- */

  function paginaInicio() {
    $$('[data-local-texto]').forEach(function (el) { el.textContent = CIDADE ? CIDADE.nome + ' (PR) · escolhida por você' : 'Nenhuma cidade escolhida'; });
    $$('[data-rotulo-cidade]').forEach(function (el) { el.textContent = CIDADE ? 'Alterar' : 'Escolher cidade'; });
    var caixa = $('[data-perto]');
    if (caixa && CIDADE && CIDADE.nome) {
      var a = document.createElement('a');
      a.className = 'pt-link';
      a.href = CIDADE.slug ? caminho('/cidade/' + CIDADE.slug + '/') : caminho('/concursos/?perto=' + CIDADE.ibge);
      a.textContent = 'Ver os concursos perto de ' + CIDADE.nome;
      caixa.appendChild(a);
      caixa.hidden = false;
    }
  }

  /* ---------- Listagem: busca, filtros e ordem, com o estado na URL ---------- */

  var RAIOS = [['10', '10 km'], ['25', '25 km'], ['50', '50 km'], ['100', '100 km'], ['estado', 'Sem limite']];
  var NOMES_ORDEM = { prazo: 'com salário e prazo mais curto primeiro', salario: 'maior salário primeiro', perto: 'mais perto primeiro' };

  function paginaConcursos() {
    var rotulos = lerJSON('rotulos') || { areas: {}, bancas: {}, niveis: NIVEIS };
    var params = new URLSearchParams(location.search);
    var pertoParam = params.get('perto');
    var origem = CIDADE;
    var grades = $$('[data-lista]');
    var cards = $$('[data-card]');
    cards.forEach(function (c, i) { c._ordem = i; c._texto = normalizar(c.textContent); c._grade = c.parentNode; });

    function padrao() {
      return { q: '', raio: pertoParam ? '50' : 'estado', federais: true, areas: [], niveis: [], bancas: [], sal: 0, previstos: true,
        ordem: origem ? 'perto' : 'prazo' };
    }
    function slugArea(v) { return normalizar(v).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''); }
    function lista(nome) { return params.get(nome) ? params.get(nome).split(',').filter(Boolean) : []; }
    var estado;

    function iniciarEstado() {
      estado = padrao();
      estado.q = params.get('q') || '';
      if (params.get('raio') && (origem || params.get('raio') === 'estado')) estado.raio = params.get('raio');
      if (params.get('federais') === '0' || params.get('nacionais') === '0') estado.federais = false;
      estado.areas = lista('area').map(slugArea);
      estado.niveis = lista('nivel');
      estado.bancas = lista('banca');
      estado.sal = Number(params.get('sal')) || 0;
      if (params.get('situacao') === 'aberto') estado.previstos = false;
      if (NOMES_ORDEM[params.get('ordem')]) estado.ordem = params.get('ordem');
    }

    function passa(card, e) {
      var q = normalizar(e.q).trim();
      if (q && card._texto.indexOf(q) < 0) return false;
      var foraPR = !card.hasAttribute('data-pr');
      if (foraPR) { if (!e.federais) return false; }
      else if (!q && e.raio !== 'estado' && !(card._km !== null && card._km !== undefined && card._km <= Number(e.raio))) return false;
      if (card.getAttribute('data-sit') === 'encerrado') return false;
      if (card.getAttribute('data-sit') === 'previsto' && !e.previstos) return false;
      if (e.areas.length && e.areas.indexOf(card.getAttribute('data-area')) < 0) return false;
      if (e.niveis.length && !card.getAttribute('data-niveis').split(' ').some(function (n) { return e.niveis.indexOf(n) >= 0; })) return false;
      if (e.bancas.length && e.bancas.indexOf(card.getAttribute('data-banca')) < 0) return false;
      if (e.sal > 0 && Number(card.getAttribute('data-sal')) < e.sal) return false;
      return true;
    }
    function comparar(a, b) {
      if (estado.ordem === 'salario') return Number(b.getAttribute('data-sal')) - Number(a.getAttribute('data-sal')) || a._ordem - b._ordem;
      if (estado.ordem === 'perto') {
        var ka = a._km == null ? 1e9 : a._km, kb = b._km == null ? 1e9 : b._km;
        return ka - kb || a._ordem - b._ordem;
      }
      return a._ordem - b._ordem;
    }
    function filtrar(e) { return cards.filter(function (c) { return passa(c, e); }); }
    function ativos(e) {
      var p = padrao(), n = 0;
      if (e.raio !== p.raio) n++;
      if (!e.federais) n++;
      if (e.areas.length) n++;
      if (e.niveis.length) n++;
      if (e.bancas.length) n++;
      if (e.sal > 0) n++;
      if (!e.previstos) n++;
      return n;
    }
    function salvarURL() {
      var p = new URLSearchParams(), d = padrao();
      if (pertoParam) p.set('perto', pertoParam);
      if (estado.q) p.set('q', estado.q);
      if (estado.raio !== d.raio) p.set('raio', estado.raio);
      if (!estado.federais) p.set('federais', '0');
      if (estado.areas.length) p.set('area', estado.areas.join(','));
      if (estado.niveis.length) p.set('nivel', estado.niveis.join(','));
      if (estado.bancas.length) p.set('banca', estado.bancas.join(','));
      if (estado.sal > 0) p.set('sal', String(estado.sal));
      if (!estado.previstos) p.set('situacao', 'aberto');
      if (estado.ordem !== d.ordem) p.set('ordem', estado.ordem);
      var qs = p.toString();
      try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '')); } catch (err) { /* file:// */ }
    }

    function render() {
      var visiveis = filtrar(estado);
      cards.forEach(function (c) { c.hidden = visiveis.indexOf(c) < 0; });
      grades.forEach(function (g) {
        $$('[data-card]', g).sort(comparar).forEach(function (c) { g.appendChild(c); });
      });
      var abertos = visiveis.filter(function (c) { return c.getAttribute('data-sit') !== 'previsto'; }).length;
      var previstos = visiveis.length - abertos;
      var titulo = estado.q ? 'Resultados para “' + estado.q + '”' : (origem && estado.raio !== 'estado' ? 'Concursos perto de ' + origem.nome : 'Concursos com inscrição aberta');
      $('[data-titulo]').textContent = titulo;
      $('[data-contagem]').textContent = contar(abertos, 'concurso aberto', 'concursos abertos') +
        (previstos ? ' e ' + contar(previstos, 'previsto', 'previstos') : '') + ' · ' + NOMES_ORDEM[estado.ordem];
      $$('[data-resumo-local]').forEach(function (el) {
        el.textContent = estado.q ? 'Em todos os concursos' : (!origem || estado.raio === 'estado' ? (origem ? 'A partir de ' + origem.nome + ' (PR), sem limite de distância' : 'Federais e todo o Paraná')
          : origem.nome + ' (PR) · a até ' + estado.raio + ' km') + (estado.federais ? '' : ' · sem federais de fora do PR');
      });
      $$('[data-area]').forEach(function (a) {
        if (estado.areas.length === 1 && estado.areas[0] === a.getAttribute('data-area')) a.setAttribute('aria-current', 'true');
        else a.removeAttribute('aria-current');
      });
      $$('[data-ordem]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-ordem') === estado.ordem)); });
      var n = ativos(estado), selo = $('[data-n-filtros]');
      selo.hidden = n === 0;
      selo.textContent = String(n);
      var secao = $('[data-secao-previstos]');
      if (secao) secao.hidden = previstos === 0;
      $('[data-vazio]').hidden = abertos !== 0;
      salvarURL();
    }

    function iniciarFiltros() {
      var dialogo = document.getElementById('filtros');
      var rascunho = null;
      var faixa = $('#faixa-salario', dialogo);
      $('[data-onde]', dialogo).textContent = origem ? origem.nome + ' (PR)' : 'Nenhuma cidade escolhida';
      function chips(itens, selecionados, grupo, unico) {
        return itens.map(function (it) {
          var ativo = unico ? selecionados === it[0] : selecionados.indexOf(it[0]) >= 0;
          return '<button class="pt-chip" type="button" data-grupo="' + grupo + '" data-valor="' + esc(it[0]) + '" aria-pressed="' + ativo + '">' + esc(it[1]) + '</button>';
        }).join('');
      }
      function pares(obj) { return Object.keys(obj).map(function (k) { return [k, obj[k]]; }); }
      function desenhar() {
        $('[data-grupo-raio]', dialogo).innerHTML = chips(origem ? RAIOS : RAIOS.slice(-1), rascunho.raio, 'raio', true);
        $('[data-grupo-areas]', dialogo).innerHTML = chips(pares(rotulos.areas), rascunho.areas, 'areas');
        $('[data-grupo-niveis]', dialogo).innerHTML = chips(rotulos.niveis.map(function (n) { return [n, n]; }), rascunho.niveis, 'niveis');
        $('[data-grupo-bancas]', dialogo).innerHTML = chips(pares(rotulos.bancas), rascunho.bancas, 'bancas');
        $('[name="federais"]', dialogo).checked = rascunho.federais;
        $('[name="previstos"]', dialogo).checked = rascunho.previstos;
        faixa.value = String(rascunho.sal);
        $('[data-valor-salario]', dialogo).textContent = rascunho.sal > 0 ? 'R$ ' + rascunho.sal.toLocaleString('pt-BR') : 'Qualquer salário';
        var abertos = filtrar(rascunho).filter(function (c) { return c.getAttribute('data-sit') !== 'previsto'; }).length;
        $('[data-ver-resultado]', dialogo).textContent = abertos === 0 ? 'Nenhum concurso aberto com esses filtros' : 'Ver ' + contar(abertos, 'concurso', 'concursos');
      }
      $('[data-filtros-corpo]', dialogo).addEventListener('click', function (ev) {
        var b = ev.target.closest('[data-grupo]');
        if (!b) return;
        var grupo = b.getAttribute('data-grupo'), valor = b.getAttribute('data-valor');
        if (grupo === 'raio') rascunho.raio = valor;
        else {
          var l = rascunho[grupo], i = l.indexOf(valor);
          if (i >= 0) l.splice(i, 1); else l.push(valor);
        }
        desenhar();
      });
      ['federais', 'previstos'].forEach(function (nome) {
        $('[name="' + nome + '"]', dialogo).addEventListener('change', function (ev) { rascunho[nome] = ev.target.checked; desenhar(); });
      });
      faixa.addEventListener('input', function () { rascunho.sal = Number(faixa.value); desenhar(); });
      $('[data-limpar]', dialogo).addEventListener('click', function () {
        var q = rascunho.q, ordem = rascunho.ordem;
        rascunho = padrao();
        rascunho.q = q;
        rascunho.ordem = ordem;
        desenhar();
      });
      $('[data-form-filtros]', dialogo).addEventListener('submit', function (ev) {
        ev.preventDefault();
        estado = JSON.parse(JSON.stringify(rascunho));
        dialogo.close();
        render();
      });
      $$('[data-abrir-filtros]').forEach(function (b) {
        b.addEventListener('click', function () { rascunho = JSON.parse(JSON.stringify(estado)); desenhar(); });
      });
    }

    // Origem da distância: ?perto=<IBGE> (link "perto de X") ou a cidade guardada.
    var pronto = Promise.resolve();
    if (pertoParam && (!CIDADE || CIDADE.ibge !== pertoParam)) {
      pronto = municipios().then(function (l) { origem = l.filter(function (m) { return m.ibge === pertoParam; })[0] || CIDADE; }).catch(function () {});
    }
    pronto.then(function () {
      mostrarDistancias(origem);
      $$('[data-rotulo-cidade]').forEach(function (el) { el.textContent = CIDADE ? 'Trocar minha cidade' : 'Escolher minha cidade'; });
      iniciarEstado();
      var campo = $('#busca-lista');
      campo.value = estado.q;
      $('[data-form-busca]').addEventListener('submit', function (ev) { ev.preventDefault(); estado.q = campo.value.trim(); render(); });
      $$('[data-area]').forEach(function (a) {
        a.addEventListener('click', function (ev) {
          ev.preventDefault();
          var s = a.getAttribute('data-area');
          estado.areas = estado.areas.length === 1 && estado.areas[0] === s ? [] : [s];
          render();
        });
      });
      $$('[data-ordem]').forEach(function (b) { b.addEventListener('click', function () { estado.ordem = b.getAttribute('data-ordem'); render(); }); });
      iniciarFiltros();
      return aplicarPerfilNosCards();
    }).then(render);
  }

  /* ---------- Ficha: "Este concurso é pra você?" e contagem até a prova ---------- */

  function paginaFicha() {
    var dados = lerJSON('ficha-dados');
    if (!dados) return;
    var prova = dados.prova;
    var contagem = $('[data-contagem]');
    if (prova && prova >= HOJE && contagem) {
      var d = diasAte(prova);
      contagem.textContent = (d === 0 ? 'A prova é hoje' : d === 1 ? 'Falta 1 dia para a prova' : 'Faltam ' + d + ' dias para a prova') +
        (d >= 14 ? ' · dá umas ' + Math.floor(d / 7) + ' semanas de estudo' : '');
      contagem.hidden = false;
    }

    var secao = $('[data-pra-voce]');
    if (!secao) return;
    var lista = $('[data-requisitos]', secao);
    var escolha = $('[data-requisitos-cargo]', secao);
    var resultado = $('[data-veredito]', secao);
    if (PERFIL) $('[data-pra-voce-perfil]', secao).textContent = 'Seu perfil: ' + resumoPerfil() + '. Marque o que você já tem. Nada disso sai do seu aparelho.';
    if (PERFIL && escolha) {   // começa pelo primeiro cargo que o perfil pode fazer
      var niveis = niveisDoPerfil();
      for (var i = 0; i < dados.cargos.length; i++) {
        var k = dados.cargos[i];
        if (niveis.indexOf(k[1]) >= 0 && serveFormacao(k[0], k[1], k[2])) { escolha.value = String(i); break; }
      }
    }
    var CAIXA = '<li><label class="cc-check pt-check44"><input type="checkbox"><span></span></label></li>';
    function itens(k) {
      var nivel = NOME_NIVEL[k[1]], partes = [];
      if (nivel && PERFIL) {
        var ok = niveisDoPerfil().indexOf(k[1]) >= 0;
        partes.push({ auto: true, ok: ok, texto: nivel + (ok ? '' : ' · seu perfil diz ' + minuscula(NOME_NIVEL[PERFIL.escolaridade])) });
      } else if (nivel) partes.push({ texto: nivel });
      (k[2] || '').split(';').map(function (r) { return r.trim(); })
        .filter(function (r) { return r && normalizar(r) !== normalizar(nivel); })
        .forEach(function (r) { partes.push({ texto: maiuscula(r) }); });
      return partes;
    }
    function montar() {
      var k = dados.cargos[escolha ? Number(escolha.value) : 0];
      lista.innerHTML = '';
      itens(k).forEach(function (it) {
        var li;
        if (it.auto) {
          li = document.createElement('li');
          li.className = 'pt-req-auto';
          li.setAttribute('data-ok', String(it.ok));
          li.innerHTML = it.ok ? '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/></svg>'
            : '<svg class="pt-i2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/></svg>';
          li.appendChild(document.createElement('span')).textContent = it.texto;
        } else {
          var tmp = document.createElement('ul');
          tmp.innerHTML = CAIXA;
          li = tmp.firstChild;
          $('span', li).textContent = it.texto;
        }
        lista.appendChild(li);
      });
      if (!k[2]) {
        var nota = document.createElement('li');
        nota.className = 'pt-apoio';
        nota.textContent = 'Outros requisitos: não informados nesta ficha. Confira no edital oficial.';
        lista.appendChild(nota);
      }
      resultado.textContent = veredito();
    }
    function veredito() {
      if ($('[data-ok="false"]', lista)) return 'Pelo seu perfil, falta a escolaridade que este cargo pede.';
      var caixas = $$('input', lista);
      if (!caixas.length && !$('[data-ok]', lista)) return 'Esta ficha não traz os requisitos do cargo. Confira no edital oficial.';
      var faltam = caixas.filter(function (x) { return !x.checked; }).length;
      if (faltam === caixas.length && caixas.length) return 'Marque o que você já tem.';
      if (faltam) return plural(faltam, 'Falta 1 item', 'Faltam ' + faltam + ' itens') + ' para você cumprir o que esta ficha lista.';
      return 'Você tem o que esta ficha lista para o cargo. Leia o edital completo antes de se inscrever no site da banca.';
    }
    if (escolha) escolha.addEventListener('change', montar);
    lista.addEventListener('change', function () { resultado.textContent = veredito(); });
    montar();
    if (PERFIL) {
      var niveisP = niveisDoPerfil();
      var algum = dados.cargos.some(function (k) { return !k[1] || (niveisP.indexOf(k[1]) >= 0 && serveFormacao(k[0], k[1], k[2])); });
      var detalhe = $('[data-detalhe]');
      if (!algum && detalhe) detalhe.textContent = 'Nenhum cargo deste concurso bate com o seu perfil';
    }
  }

  /* ---------- Botão flutuante: vira só o ícone ao rolar ---------- */

  function iniciarBotaoFlutuante() {
    var fab = $('.pt-fab');
    if (!fab) return;
    function ajustar() { fab.classList.toggle('pt-fab-icone', window.scrollY > 80); }
    window.addEventListener('scroll', ajustar, { passive: true });
    ajustar();
  }

  /* ---------- Anúncios (só com adsense no site.toml): escolha da pessoa antes de carregar ---------- */

  function iniciarAnuncios() {
    if (!CONFIG.adsense) return;
    var aviso = $('[data-cookies]');
    function carregar(personalizado) {
      window.adsbygoogle = window.adsbygoogle || [];
      if (!personalizado) window.adsbygoogle.requestNonPersonalizedAds = 1;
      var s = document.createElement('script');
      s.async = true;
      s.crossOrigin = 'anonymous';
      s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + encodeURIComponent(CONFIG.adsense);
      document.head.appendChild(s);
      $$('ins.adsbygoogle').forEach(function () { window.adsbygoogle.push({}); });
    }
    function decidir(sim) { guardar(CHAVE_ANUNCIOS, { personalizado: sim }); aviso.hidden = true; location.reload(); }
    var escolha = ler(CHAVE_ANUNCIOS);
    if (escolha) carregar(!!escolha.personalizado);
    else if (aviso) aviso.hidden = false;
    if (aviso) {
      $('[data-cookies-aceitar]', aviso).addEventListener('click', function () { decidir(true); });
      $('[data-cookies-recusar]', aviso).addEventListener('click', function () { decidir(false); });
    }
    $$('[data-cookies-abrir]').forEach(function (b) { b.addEventListener('click', function () { if (aviso) aviso.hidden = false; }); });
  }

  /* ---------- Início ---------- */

  document.addEventListener('DOMContentLoaded', function () {
    var pagina = document.body.getAttribute('data-pagina');
    iniciarFolhas();
    iniciarKit();
    iniciarCidade();
    iniciarPerfil();
    iniciarBotaoFlutuante();
    iniciarAnuncios();
    atualizarSituacao();
    if (pagina === 'concursos') { paginaConcursos(); return; }
    mostrarDistancias(CIDADE);
    aplicarPerfilNosCards();
    if (pagina === 'inicio') paginaInicio();
    if (pagina === 'concurso') paginaFicha();
  });
})();
