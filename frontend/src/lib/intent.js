// Where a visitor was heading when sign-in or the profile stopped them; kept for the tab so a refresh keeps it.
const STORAGE_KEY = "zito:intent";

export function readIntent() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

export function rememberIntent(route) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(route));
  } catch {
    /* storage is optional */
  }
}

export function clearIntent() {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage is optional */
  }
}
