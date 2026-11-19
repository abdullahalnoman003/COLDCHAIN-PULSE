const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const TOKEN_KEY = 'coldchain_access_token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const saveToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);
export const parseApiDate = (value) => {
  if (!value) return null;
  const text = String(value);
  return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(text) ? text : `${text}Z`);
};

export async function api(path, options = {}) {
  const token = getToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401) clearToken();
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

export const login = (email, password) => api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
export const me = () => api('/auth/me');
export const getSummary = () => api('/dashboard/summary');
export const getShipments = (params) => api(`/shipments?${new URLSearchParams(params)}`);
export const getAlerts = () => api('/alerts?unacknowledged=true&limit=8');
export const getTelemetry = (id) => api(`/shipments/${id}/telemetry?limit=24`);
export const acknowledgeAlert = (id) => api(`/alerts/${id}/acknowledge`, { method: 'POST' });
export async function getDelayedCount() {
  const now = Date.now();
  const first = await getShipments({ status: 'in_transit', page: 1, page_size: 200 });
  let delayed = (first.items || []).filter((shipment) => shipment.eta && parseApiDate(shipment.eta).getTime() < now).length;
  const pages = Math.ceil((first.total || 0) / 200);
  for (let page = 2; page <= pages; page += 1) {
    const result = await getShipments({ status: 'in_transit', page, page_size: 200 });
    delayed += (result.items || []).filter((shipment) => shipment.eta && parseApiDate(shipment.eta).getTime() < now).length;
  }
  return delayed;
}
