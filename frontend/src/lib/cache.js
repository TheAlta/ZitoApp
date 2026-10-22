// Shared request cache: pages and the shell read the same data without refetching.
import { useCallback, useEffect, useState } from "react";
import { get } from "./api.js";

const entries = new Map(); // key -> { data, error, promise, listeners:Set }

function entry(key) {
  if (!entries.has(key)) entries.set(key, { data: undefined, error: null, promise: null, listeners: new Set() });
  return entries.get(key);
}

function notify(item) {
  item.listeners.forEach((listener) => listener());
}

export function load(key, loader = () => get(key), { force = false } = {}) {
  const item = entry(key);
  if (item.promise && !force) return item.promise;
  if (item.data !== undefined && !force) return Promise.resolve(item.data);
  item.promise = loader()
    .then((data) => {
      item.data = data;
      item.error = null;
      return data;
    })
    .catch((error) => {
      item.error = error;
      throw error;
    })
    .finally(() => {
      item.promise = null;
      notify(item);
    });
  notify(item);
  return item.promise;
}

export function setCached(key, data) {
  const item = entry(key);
  item.data = data;
  item.error = null;
  notify(item);
}

export function invalidate(...keys) {
  for (const key of keys) {
    const item = entries.get(key);
    if (!item) continue;
    item.data = undefined;
    if (item.listeners.size) load(key).catch(() => {});
  }
}

export function clearCache() {
  entries.clear();
}

// useCached("/api/courses") -> { data, error, loading, reload }
export function useCached(key, loader, { enabled = true } = {}) {
  const [, force] = useState(0);
  useEffect(() => {
    if (!key || !enabled) return;
    const item = entry(key);
    const listener = () => force((n) => n + 1);
    item.listeners.add(listener);
    if (item.data === undefined && !item.promise) load(key, loader).catch(() => {});
    return () => item.listeners.delete(listener);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);
  const reload = useCallback(() => (key ? load(key, loader, { force: true }) : Promise.resolve()), [key, loader]);
  const item = key ? entry(key) : { data: undefined, error: null, promise: null };
  return { data: item.data, error: item.error, loading: !!item.promise || (item.data === undefined && !item.error), reload };
}
