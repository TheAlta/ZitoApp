// Signed-in frame: glass sidebar, top bar (search, activity, account) and the phone bottom nav.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  BookOpen,
  ChevronDown,
  CirclePlay,
  Compass,
  Eye,
  Heart,
  Image,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Search as SearchIcon,
  Settings2,
  Users,
} from "lucide-react";
import { ago, fa } from "../lib/format.js";
import { useAdminCourses, useAdminLog, useAdminUsers } from "../lib/admin.js";
import { selectCourse, useCourses, useCurrentPath, useOverview } from "../lib/learner.js";
import { useStore } from "../lib/store.jsx";
import { Landscape, Logo, Sprig } from "../ui/art.jsx";

export function useNavItems() {
  const { session } = useStore();
  return session.role === "admin"
    ? [
        { label: "داشبورد", icon: <LayoutDashboard />, route: { name: "admin" }, match: ["admin"] },
        { label: "استودیوی دوره", icon: <CirclePlay />, route: { name: "admin-studio" }, match: ["admin-studio", "admin-new"] },
        { label: "عکس و ویدیو", icon: <Image />, route: { name: "admin-images" }, match: ["admin-images"] },
        { label: "کاربران", icon: <Users />, route: { name: "admin-users" }, match: ["admin-users"] },
        { label: "پیش‌نمایش لندینگ", icon: <Eye />, route: { name: "landing" }, match: [] },
      ]
    : [
        { label: "داشبورد", icon: <LayoutDashboard />, route: { name: "home" }, match: ["home"] },
        { label: "کوچ زیتو", icon: <MessageCircle />, route: { name: "coach" }, match: ["coach"] },
        { label: "مسیر یادگیری", icon: <CirclePlay />, route: { name: "lesson" }, match: ["lesson", "final"] },
        { label: "دوره‌ها", icon: <Compass />, route: { name: "courses" }, match: ["courses", "course"] },
        { label: "گواهی‌ها", icon: <BookOpen />, route: { name: "certs" }, match: ["certs"] },
        { label: "پروفایل", icon: <Settings2 />, route: { name: "profile" }, match: ["profile"] },
      ];
}

function Sidebar() {
  const { route, go, session, logout } = useStore();
  const items = useNavItems();
  const admin = session.role === "admin";
  const scenic = route.name === "coach" || route.name === "admin-studio";
  return (
    <aside className="side mat mat-side" aria-label="ناوبری اصلی">
      <button className="side-logo" onClick={() => go(items[0].route)} aria-label="زیتو، صفحه‌ی اصلی">
        <Logo />
      </button>
      <nav className="side-nav">
        {items.map((item) => (
          <button
            key={item.label}
            className="nav-item"
            aria-current={item.match.includes(route.name) ? "page" : undefined}
            onClick={() => go(item.route)}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="side-foot">
        {scenic ? (
          <div className="promo promo-land">
            <Landscape hue={route.name === "coach" ? 262 : 280} seed={route.name === "coach" ? 3 : 8} className="promo-art" />
            <p>{admin ? "محتوای خوب، زندگی‌ها را عوض می‌کند." : "سؤال خوب، یادگیری عمیق."}</p>
            <Heart className="promo-heart" />
          </div>
        ) : (
          <div className="promo">
            <Sprig className="promo-sprig" flowers={11} />
            <p>
              {admin ? "محتوای بهتر،" : "هر روز یک قدم،"}
              <br />
              {admin ? "ذهن‌های روشن‌تر." : "مسیرت روشن‌تر."}
            </p>
            <Heart className="promo-heart" />
          </div>
        )}
        <button className="nav-item nav-out" onClick={logout}>
          <LogOut />
          <span>خروج از حساب</span>
        </button>
      </div>
    </aside>
  );
}

export function useOutside(open, close) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => ref.current && !ref.current.contains(e.target) && close();
    const onKey = (e) => e.key === "Escape" && close();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);
  return ref;
}

function useSearchIndex(admin) {
  const { go, toast } = useStore();
  const courses = useCourses(!admin);
  const overview = useOverview(!admin);
  const path = useCurrentPath(!admin);
  const adminCourses = useAdminCourses(admin);
  const users = useAdminUsers(admin);
  return useMemo(() => {
    const index = [];
    if (admin) {
      const latest = new Map();
      for (const v of adminCourses.data || []) {
        if (v.course_status === "deleted") continue;
        const prev = latest.get(v.course_id);
        if (!prev || v.version_number > prev.version_number) latest.set(v.course_id, v);
      }
      for (const v of latest.values()) {
        const open = (tab) => go({ name: "admin-studio", courseId: v.course_id, version: v.version_number, tab });
        index.push({ text: v.course_title, label: v.course_title, sub: `دوره | نسخه‌ی ${fa(v.version_number)}`, run: () => open() });
        (v.modules || []).forEach((m, i) =>
          index.push({ text: m.title, label: m.title, sub: `سرفصل ${fa(i + 1)} | ${v.course_title}`, run: () => open("structure") }),
        );
      }
      for (const u of users.data || []) {
        if (u.deleted_at) continue;
        index.push({ text: `${u.display_name} ${u.phone}`, label: u.display_name, sub: `کاربر | ${u.phone}`, run: () => go({ name: "admin-users", userId: u.id }) });
      }
    } else {
      for (const c of courses.data || []) {
        index.push({ text: `${c.title} ${c.domain}`, label: c.title, sub: "دوره", run: () => go({ name: "course", slug: c.slug }) });
      }
      for (const m of path.data?.modules || []) {
        index.push({
          text: m.title,
          label: m.title,
          sub: `سرفصل ${fa(m.module_number)} | ${path.data.course_title}`,
          run: () => go({ name: "course", slug: path.data.course_slug }),
        });
      }
      for (const e of overview.data?.enrollments || []) {
        index.push({
          text: e.course_title,
          label: `ادامه‌ی ${e.course_title}`,
          sub: "دوره‌ی من",
          run: () =>
            selectCourse(e.course_id)
              .then(() => go({ name: "lesson" }))
              .catch((error) => toast(error.message, "err")),
        });
      }
    }
    return index;
  }, [admin, adminCourses.data, users.data, courses.data, path.data, overview.data, go, toast]);
}

function Search() {
  const { session } = useStore();
  const admin = session.role === "admin";
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  const input = useRef(null);
  const index = useSearchIndex(admin);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.current?.focus();
        setOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const q = query.trim();
  const results = q ? index.filter((item) => item.text.includes(q)).slice(0, 7) : [];

  return (
    <div className="search" ref={ref}>
      <label className="search-box mat mat-field">
        <SearchIcon />
        <input
          ref={input}
          value={query}
          onChange={(e) => (setQuery(e.target.value), setOpen(true))}
          onFocus={() => setOpen(true)}
          placeholder={admin ? "جست‌وجوی دوره، سرفصل یا کاربر…" : "جست‌وجوی دوره و سرفصل…"}
          aria-label="جست‌وجو"
          role="combobox"
          aria-expanded={open && !!q}
          aria-controls="search-results"
        />
        <kbd className="ltr">Ctrl K</kbd>
      </label>
      {open && q && (
        <div className="menu search-menu" id="search-results" role="listbox">
          {results.length ? (
            results.map((item, i) => (
              <button key={i} role="option" className="menu-item" onClick={() => (item.run(), setOpen(false), setQuery(""))}>
                <b>{item.label}</b>
                <small>{item.sub}</small>
              </button>
            ))
          ) : (
            <p className="menu-empty">برای «{q}» چیزی پیدا نشد. با نام دوره یا سرفصل امتحان کن.</p>
          )}
        </div>
      )}
    </div>
  );
}

function Notifications() {
  const { session } = useStore();
  const admin = session.role === "admin";
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  const overview = useOverview(!admin);
  const adminLog = useAdminLog(admin);
  const items = (admin ? adminLog : overview.data?.activity || []).slice(0, 6);
  return (
    <div className="pop" ref={ref}>
      <button className="icon-btn" aria-label="اعلان‌ها" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Bell />
        {items.length > 0 && <span className="dot-badge" />}
      </button>
      {open && (
        <div className="menu menu-end" role="menu">
          <p className="menu-title">فعالیت اخیر</p>
          {items.length ? (
            items.map((item, i) => (
              <div key={i} className="menu-row">
                <span>{fa(item.text)}</span>
                <small>{ago(item.at)}</small>
              </div>
            ))
          ) : (
            <p className="menu-empty">هنوز فعالیتی ثبت نشده.</p>
          )}
        </div>
      )}
    </div>
  );
}

function UserMenu() {
  const { session, me, go, logout } = useStore();
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  const admin = session.role === "admin";
  const name = admin ? "مدیر محتوا" : me?.display_name ?? "";
  return (
    <div className="pop" ref={ref}>
      <button className="user-btn" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen(!open)}>
        <span className="avatar" data-admin={admin || undefined}>
          {name.trim()[0]}
        </span>
        <span className="user-meta">
          <b>{name}</b>
          <small>{admin ? <span className="ltr">{session.admin?.username || "admin"}</span> : "یادگیرنده"}</small>
        </span>
        <ChevronDown size={16} className="muted" />
      </button>
      {open && (
        <div className="menu menu-end" role="menu">
          {!admin && (
            <>
              <button role="menuitem" className="menu-item" onClick={() => (go({ name: "profile" }), setOpen(false))}>
                <b>پروفایل من</b>
                <small className="ltr">{me?.phone}</small>
              </button>
              <button role="menuitem" className="menu-item" onClick={() => (go({ name: "certs" }), setOpen(false))}>
                <b>گواهی‌های من</b>
              </button>
            </>
          )}
          <button role="menuitem" className="menu-item" onClick={logout}>
            <b>خروج از حساب</b>
          </button>
        </div>
      )}
    </div>
  );
}

export function Shell({ children, wide = false }) {
  const items = useNavItems();
  const { route, go } = useStore();
  return (
    <div className="shell">
      <div className="frame mat mat-frame">
        <Sidebar />
        <div className="app-col">
          <header className="topbar">
            <Search />
            <div className="top-actions">
              <Notifications />
              <UserMenu />
            </div>
          </header>
          <main className={`app-main ${wide ? "is-wide" : ""}`} id="main">
            {children}
          </main>
        </div>
      </div>
      <nav className="bottom-nav mat mat-panel" aria-label="ناوبری موبایل">
        {items.slice(0, 5).map((item) => (
          <button key={item.label} aria-current={item.match.includes(route.name) ? "page" : undefined} onClick={() => go(item.route)}>
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
