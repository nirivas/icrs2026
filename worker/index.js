/* Tiny sync API for ICRS planner — one JSON blob per sync code (Cloudflare KV). */
var CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, PUT, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type'
};
var ROOM_RE = /^[a-z][a-z0-9-]{2,31}$/i;
var MAX_BYTES = 512000;

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS });
    }
    var url = new URL(request.url);
    var room = decodeURIComponent(url.pathname.replace(/^\/+/, '')).toLowerCase().trim();
    if (!ROOM_RE.test(room)) {
      return json({ error: 'bad code' }, 400);
    }
    if (request.method === 'GET') {
      var raw = await env.SYNC.get(room);
      if (!raw) return json({ error: 'not found' }, 404);
      return new Response(raw, { headers: { ...CORS, 'Content-Type': 'application/json' } });
    }
    if (request.method === 'PUT') {
      var body = await request.text();
      if (!body || body.length > MAX_BYTES) return json({ error: 'too large' }, 413);
      try { JSON.parse(body); } catch (e) { return json({ error: 'bad json' }, 400); }
      await env.SYNC.put(room, body);
      return json({ ok: true });
    }
    return json({ error: 'method' }, 405);
  }
};

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { ...CORS, 'Content-Type': 'application/json' }
  });
}
