// CWNG feedback Worker — anonymous "Back to old theme" feedback collector.
// Design: notes/FEEDBACK-SERVER-DESIGN.md. Stores ONLY {type,reasons,comment,created_at}.
// Never stores IP/identity. IP is used solely as a salted, in-memory-only hash for a 60s
// rate-limit key (KV with TTL), then discarded. HTTPS/TLS is the "encrypted in transit" basis.

const TYPE_WHITELIST = new Set(["new_version_feedback"]);
const MAX_COMMENT = 2000;
const MAX_REASONS = 12;
const RL_WINDOW_SECONDS = 60; // 1 submission per type per minute per (hashed) IP

function cors(origin) {
  // Public feedback endpoint: allow browser cross-origin POSTs from anywhere (the CWNG app
  // is served from many per-user origins). Abuse is handled by rate-limit + type whitelist
  // (+ Turnstile when configured), not by CORS.
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

async function sha256hex(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function verifyTurnstile(token, ip, secret) {
  if (!secret) return true; // Turnstile optional until a widget/secret is configured
  if (!token) return false;
  const body = new URLSearchParams({ secret, response: token });
  if (ip) body.set("remoteip", ip);
  try {
    const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST", body,
    });
    const d = await r.json();
    return !!d.success;
  } catch (_) {
    return false;
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin");

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(origin) });
    }
    if (request.method === "GET" && url.pathname === "/") {
      return new Response(JSON.stringify({ ok: true, service: "cwng-feedback" }), {
        headers: { "Content-Type": "application/json", ...cors(origin) },
      });
    }
    if (request.method !== "POST" || url.pathname !== "/feedback") {
      return new Response(JSON.stringify({ error: "not_found" }), {
        status: 404, headers: { "Content-Type": "application/json", ...cors(origin) },
      });
    }

    let payload;
    try {
      payload = await request.json();
    } catch (_) {
      return json(400, { error: "bad_json" }, origin);
    }

    const type = String(payload.type || "");
    if (!TYPE_WHITELIST.has(type)) return json(400, { error: "bad_type" }, origin);

    // Turnstile (no-op until TURNSTILE_SECRET is set)
    const ip = request.headers.get("CF-Connecting-IP") || "";
    const okTs = await verifyTurnstile(payload.turnstileToken, ip, env.TURNSTILE_SECRET);
    if (!okTs) return json(403, { error: "turnstile_failed" }, origin);

    // Rate limit: 1 per type per minute per salted-hashed IP. Never store the raw IP.
    if (ip && env.RATELIMIT) {
      const salt = env.RL_SALT || "cwng-static-salt";
      const rlKey = "rl:" + type + ":" + (await sha256hex(salt + "|" + ip)).slice(0, 32);
      const seen = await env.RATELIMIT.get(rlKey);
      if (seen) return json(429, { error: "rate_limited" }, origin);
      await env.RATELIMIT.put(rlKey, "1", { expirationTtl: RL_WINDOW_SECONDS });
    }

    // Sanitize + cap the payload; store ONLY the anonymous content.
    let reasons = Array.isArray(payload.reasons) ? payload.reasons : [];
    reasons = reasons.slice(0, MAX_REASONS).map((r) => String(r).slice(0, 80));
    const comment = String(payload.comment || "").slice(0, MAX_COMMENT);
    const created_at = new Date().toISOString();

    const record = { type, reasons, comment, created_at };
    // Key sorts chronologically; random suffix avoids collisions. No IP/identity anywhere.
    const key = "fb:" + created_at + ":" + crypto.randomUUID().slice(0, 8);
    await env.FEEDBACK.put(key, JSON.stringify(record));

    return json(200, { ok: true }, origin); // never echo IP/identity
  },
};

function json(status, obj, origin) {
  return new Response(JSON.stringify(obj), {
    status, headers: { "Content-Type": "application/json", ...cors(origin) },
  });
}
