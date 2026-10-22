// Public pages: certificate verification and the admin sign-in.
import { useState } from "react";
import { BadgeCheck, Lock, Printer, Search, Share2 } from "lucide-react";
import { useCached } from "../lib/cache.js";
import { fa, jalali } from "../lib/format.js";
import { useStore } from "../lib/store.jsx";
import { Drop, Logo, Sprig } from "../ui/art.jsx";
import { Empty, Field, Form, Skel } from "../ui/kit.jsx";

export function Certificate({ id }) {
  const { session, go, toast } = useStore();
  const [query, setQuery] = useState(id ?? "");
  const number = (id || "").trim().toUpperCase();
  const lookup = useCached(number ? `/api/certificates/${encodeURIComponent(number)}` : null);
  const cert = lookup.data;
  const back = () => go(session.role === "learner" ? { name: "certs" } : session.role === "admin" ? { name: "admin" } : { name: "landing" });
  const link = cert ? `${location.origin}/certificate/${cert.certificate_number}` : "";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      toast("لینک عمومی گواهی کپی شد.");
    } catch {
      toast(link, "info");
    }
  };

  return (
    <div className="public">
      <div className="public-top no-print">
        <button onClick={back} aria-label="بازگشت">
          <Logo />
        </button>
        <Form className="search-box mat mat-field" style={{ width: "min(22rem,60%)" }} onSubmit={() => query.trim() && go({ name: "certificate", id: query.trim().toUpperCase() })}>
          <Search />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="شماره‌ی گواهی، مثل ZITO-2026-…" aria-label="شماره‌ی گواهی" dir="ltr" style={{ textAlign: "left" }} />
        </Form>
      </div>
      {!number ? (
        <div className="cert">
          <Empty icon={<BadgeCheck />} title="استعلام گواهی زیتو" text="شماره‌ی گواهی را وارد کن تا اصالتش بررسی شود. نمونه: ZITO-2026-39BC6E0453BF" />
        </div>
      ) : lookup.loading && !cert ? (
        <div className="cert">
          <Skel lines={6} />
        </div>
      ) : cert ? (
        <>
          <article className="cert" aria-label="گواهی پایان دوره">
            <Sprig className="cert-sprig" flowers={12} />
            <span className="seal">
              <Drop size="3.4rem" glow={false} />
            </span>
            <span className="muted" style={{ fontSize: "var(--t-small)" }}>
              گواهی پایان دوره زیتو
            </span>
            <p className="soft">این گواهی تأیید می‌کند که</p>
            <h1>{cert.recipient_name}</h1>
            <p className="soft">
              دوره‌ی <b style={{ color: "var(--ink)" }}>«{cert.course_title}»</b> را با موفقیت به پایان رسانده است.
            </p>
            <div className="cert-grid">
              <div>
                <small>نمره</small>
                <b>{fa(cert.score)} از ۱۰۰</b>
              </div>
              <div>
                <small>حدنصاب</small>
                <b>{fa(cert.passing_score)}</b>
              </div>
              <div>
                <small>نسخه‌ی دوره</small>
                <b>{fa(cert.course_version_number)}</b>
              </div>
              <div>
                <small>تاریخ صدور</small>
                <b>{jalali(cert.issued_at)}</b>
              </div>
            </div>
            <small className="ltr muted" style={{ justifySelf: "center", marginTop: ".4rem" }}>
              {cert.certificate_number}
            </small>
          </article>
          <div className="row no-print" style={{ justifyContent: "center" }}>
            <button className="btn btn-primary" onClick={() => window.print()}>
              <Printer /> چاپ یا ذخیره PDF
            </button>
            <button className="btn btn-soft" onClick={copy}>
              <Share2 /> کپی لینک استعلام
            </button>
          </div>
        </>
      ) : (
        <div className="cert">
          <Empty icon={<BadgeCheck />} title="گواهی قابل نمایش نیست" text="شماره‌ای که وارد کردی در زیتو ثبت نشده. شماره را دوباره و با دقت بررسی کن." />
        </div>
      )}
    </div>
  );
}

export function AdminLogin() {
  const { adminLogin, go } = useStore();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (busy) return;
    setBusy(true);
    const message = await adminLogin(username, password);
    setBusy(false);
    setError(message || "");
  };
  return (
    <div className="public" style={{ placeItems: "center", alignContent: "center" }}>
      <Form className="mat mat-panel form" style={{ width: "min(24rem,100%)", padding: "1.8rem" }} onSubmit={submit}>
        <Logo />
        <h1 style={{ fontSize: "var(--t-h1)" }}>ورود مدیر زیتو</h1>
        <Field label="نام کاربری">
          <input className="input ltr" dir="ltr" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus />
        </Field>
        <Field label="رمز" error={error || undefined}>
          <input className="input ltr" dir="ltr" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </Field>
        <button className="btn btn-primary btn-block btn-lg" type="submit" disabled={busy || !username.trim() || !password}>
          <Lock /> {busy ? "در حال ورود…" : "ورود به پنل"}
        </button>
        <button type="button" className="link-btn" style={{ justifySelf: "center" }} onClick={() => go({ name: "landing" })}>
          بازگشت به لندینگ
        </button>
      </Form>
    </div>
  );
}
