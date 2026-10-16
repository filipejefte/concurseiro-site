// Cloudflare Pages Function: GET /api/local devolve a região que a Cloudflare estima pelo IP de quem pede
// (request.cf), para o site sugerir a cidade. Não grava nada e não manda o IP de volta.
// Só existe no Cloudflare; no GitHub Pages o endereço dá 404 e o site segue sem sugestão.
export function onRequestGet({ request }) {
  const cf = request.cf || {};
  const numero = (v) => (v === undefined || v === null || v === '' ? null : Number(v));
  const corpo = {
    pais: cf.country || null,
    regiao: cf.country === 'BR' ? cf.regionCode || null : null,
    cidade: cf.city || null,
    lat: numero(cf.latitude),
    lon: numero(cf.longitude),
  };
  return new Response(JSON.stringify(corpo), {
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'private, no-store',
      'x-robots-tag': 'noindex',
    },
  });
}
