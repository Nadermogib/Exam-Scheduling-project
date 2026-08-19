/**
 * Centralised Axios API client (P0-T4).
 *
 * The base URL is read from the VITE_API_BASE_URL environment variable so
 * that switching from localhost to a hosted server requires only a .env
 * change — no code edits (AQ-4 / P7-T8 server-ready requirement).
 *
 * Default: http://localhost:8000
 */
import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000, // 60 s — allows for longer solve calls
  headers: {
    Accept: 'application/json',
  },
});

// ── Response interceptor: normalise error shape ──────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Attach a human-readable message from the backend if available.
    const detail =
      error.response?.data?.detail ??
      error.response?.data?.message ??
      error.message ??
      'خطأ في الاتصال بالخادم';
    error.userMessage = detail;
    return Promise.reject(error);
  }
);

export default api;

// ── Convenience helpers ──────────────────────────────────────────────────────

/** Verify the backend is reachable. Returns { status: "ok" } on success. */
export const checkHealth = () => api.get('/health').then((r) => r.data);

/** Verify the SQLite database is initialised. Returns { ok, row_count }. */
export const checkDbStatus = () => api.get('/api/db/status').then((r) => r.data);

/** Upload an .xlsx file. Returns { session_id, is_valid, errors, warnings, rows, row_count }. */
export const uploadFile = (file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/api/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data);
};

/** Patch a single cell in the session and re-run validation. */
export const patchCell = (sessionId, row, field, value) =>
  api.patch(`/api/session/${sessionId}/row/${row}/field/${field}`, { value })
    .then((r) => r.data);

/** Download the official .xlsx template. Returns a Blob. */
export const downloadTemplate = () =>
  api.get('/api/template', { responseType: 'blob' }).then((r) => r.data);

/** Run the CP-SAT scheduler. Returns success or infeasibility response. */
export const runSchedule = (payload) =>
  api.post('/api/schedule', payload).then((r) => r.data);

