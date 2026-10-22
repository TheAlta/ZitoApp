// Router: picks the page for the current URL, guards roles, wraps signed-in pages in the shell.
import { useEffect } from "react";
import { profileComplete, useStore } from "./lib/store.jsx";
import { Sky } from "./ui/art.jsx";
import { Skel, Toasts } from "./ui/kit.jsx";
import { PAGES } from "./pages/index.jsx";

const PUBLIC_ROUTES = ["landing", "certificate", "admin-login"];
const TITLES = {
  landing: "زیتو",
  home: "داشبورد",
  onboarding: "پروفایل",
  lesson: "مسیر یادگیری",
  coach: "کوچ زیتو",
  courses: "دوره‌ها",
  course: "معرفی دوره",
  final: "آزمون نهایی",
  certs: "گواهی‌ها",
  profile: "پروفایل من",
  admin: "پنل مدیر",
  "admin-login": "ورود مدیر",
  "admin-studio": "استودیوی دوره",
  "admin-new": "دوره‌ی جدید",
  "admin-images": "عکس و ویدیو",
  "admin-users": "کاربران",
  certificate: "گواهی",
};

function guard(route, role, complete) {
  if (PUBLIC_ROUTES.includes(route.name)) return null;
  const adminRoute = route.name.startsWith("admin");
  if (adminRoute && role !== "admin") return { name: "admin-login" };
  if (!adminRoute && role !== "learner") return role === "admin" ? { name: "admin" } : { name: "landing" };
  if (role === "learner" && !complete && route.name !== "onboarding" && route.name !== "profile") return { name: "onboarding" };
  return null;
}

export function App() {
  const { route, session, profile, go } = useStore();
  const loading = session.role === "loading";
  const redirect = loading ? null : guard(route, session.role, profileComplete(profile));

  useEffect(() => {
    if (redirect) go(redirect, { replace: true });
  }, [redirect?.name]);
  useEffect(() => {
    document.title = `${TITLES[route.name] ?? "زیتو"} | زیتو`;
  }, [route.name]);

  const page = PAGES[route.name];
  const isPublic = PUBLIC_ROUTES.includes(route.name);
  let content = null;
  if (!redirect && page && (isPublic || !loading)) content = page.render(route);
  const Shell = PAGES.shell;
  const inShell = !isPublic && !!Shell;

  return (
    <>
      <Sky dim={inShell} />
      <a href="#main" className="sr-only">
        رفتن به محتوای اصلی
      </a>
      {inShell ? <Shell wide={!!page?.wide}>{content ?? <Skel lines={6} />}</Shell> : content}
      <Toasts />
    </>
  );
}
