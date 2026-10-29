
const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request(endpoint, options = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`Erreur HTTP ${response.status}`);
  }

  if (response.status === 204) return null;

  return response.json();
}

export const api = {
  getDashboard: () => request("/dashboard"),
  getIncidents: () => request("/incidents"),
  getAlerts: () => request("/alerts"),
};
