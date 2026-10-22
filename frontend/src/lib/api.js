// Thin JSON client for the Zito API. Errors carry the server's Persian message.
export class ApiError extends Error {
  constructor(status, message, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function messageOf(detail, status) {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail.message === "string") return detail.message;
  if (Array.isArray(detail) && detail[0]?.msg) return "ورودی معتبر نیست. دوباره بررسی کن.";
  if (status === 401) return "نشست تو تمام شده؛ دوباره وارد شو.";
  if (status >= 500) return "سرور در حال حاضر پاسخ نمی‌دهد. چند لحظه بعد دوباره امتحان کن.";
  return "درخواست انجام نشد.";
}

export async function api(path, { method = "GET", body, signal } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      signal,
      credentials: "same-origin",
      headers: body === undefined ? { Accept: "application/json" } : { "Content-Type": "application/json", Accept: "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(0, "اتصال به اینترنت برقرار نیست. اتصال را بررسی کن و دوباره امتحان کن.");
  }
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!response.ok) {
    const detail = data?.detail ?? data;
    throw new ApiError(response.status, messageOf(detail, response.status), detail);
  }
  return data;
}

export const get = (path, opts) => api(path, opts);
export const post = (path, body, opts) => api(path, { ...opts, method: "POST", body: body ?? {} });
export const patch = (path, body, opts) => api(path, { ...opts, method: "PATCH", body });
export const del = (path, opts) => api(path, { ...opts, method: "DELETE" });
