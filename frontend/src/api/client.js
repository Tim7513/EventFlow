/**
 * EventFlow API client.
 *
 * All functions throw on non-2xx responses with a descriptive Error so
 * callers can surface the message in the UI.
 */

const BASE_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

if (!BASE_URL) {
  console.warn(
    "[EventFlow] VITE_API_URL is not set. " +
      "Copy frontend/.env.example → frontend/.env.local and add your API Gateway URL."
  );
}

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  let body;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const message =
      body?.error || body?.message || `HTTP ${res.status} ${res.statusText}`;
    throw new Error(message);
  }

  return body;
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

/**
 * POST /event
 * @param {string} type
 * @param {number} value
 * @returns {Promise<{ event_id: string, message: string, created_at: string }>}
 */
export async function postEvent(type, value) {
  return request("/event", {
    method: "POST",
    body: JSON.stringify({ type, value }),
  });
}

/**
 * GET /stats
 * @returns {Promise<{
 *   total_events: number,
 *   total_value: number,
 *   average_value: number,
 *   by_type: Record<string, { count: number, total_value: number, average_value: number }>
 * }>}
 */
export async function getStats() {
  return request("/stats");
}

/**
 * GET /events/recent
 * @param {{ limit?: number, type?: string, since?: string }} params
 * @returns {Promise<{ count: number, events: object[] }>}
 */
export async function getRecentEvents({ limit = 20, type, since } = {}) {
  const qs = new URLSearchParams();
  qs.set("limit", String(limit));
  if (type) qs.set("type", type);
  if (since) qs.set("since", since);
  return request(`/events/recent?${qs.toString()}`);
}
