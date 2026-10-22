// Route objects ({name, ...params}) <-> real URLs.
const table = [
  ["landing", "/"],
  ["certificate", "/certificate/:id?"],
  ["admin-login", "/admin/login"],
  ["onboarding", "/app/onboarding"],
  ["home", "/app"],
  ["courses", "/app/courses"],
  ["course", "/app/courses/:slug"],
  ["lesson", "/app/learn"],
  ["coach", "/app/coach"],
  ["final", "/app/final-exam"],
  ["certs", "/app/certificates"],
  ["profile", "/app/profile"],
  ["admin", "/admin"],
  ["admin-new", "/admin/new"],
  ["admin-studio", "/admin/studio/:courseId?/:version?"],
  ["admin-images", "/admin/images"],
  ["admin-users", "/admin/users/:userId?"],
];

const compiled = table.map(([name, pattern]) => {
  const keys = [];
  const source = pattern
    .replace(/\/$/, "")
    .replace(/\/:(\w+)(\?)?/g, (_, key, optional) => {
      keys.push(key);
      return optional ? "(?:/([^/]+))?" : "/([^/]+)";
    });
  return { name, pattern, keys, re: new RegExp(`^${source || ""}/?$`) };
});

export function fromPath(pathname) {
  const path = pathname.replace(/\/+$/, "") || "/";
  for (const route of compiled) {
    const match = path.match(route.re);
    if (!match) continue;
    const params = { name: route.name };
    route.keys.forEach((key, i) => {
      if (match[i + 1] !== undefined) params[key] = decodeURIComponent(match[i + 1]);
    });
    return params;
  }
  return pathname.startsWith("/admin") ? { name: "admin" } : pathname.startsWith("/app") ? { name: "home" } : { name: "landing" };
}

export function toPath(route) {
  const entry = compiled.find((r) => r.name === route.name) || compiled[0];
  let path = entry.pattern.replace(/\/:(\w+)\??/g, (_, key) => (route[key] !== undefined && route[key] !== null ? `/${encodeURIComponent(route[key])}` : ""));
  if (route.tab) path += `#${route.tab}`;
  return path || "/";
}
