// Public landing page and the phone sign-in / sign-up dialog.
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  BadgeCheck,
  BookOpenCheck,
  MessageCircleHeart,
  Pencil,
  RefreshCw,
  Route,
  ShieldCheck,
  Smartphone,
  Volume2,
  VolumeX,
} from "lucide-react";
import { fa, normDigits } from "../lib/format.js";
import { toggleAmbient, useAmbient } from "../lib/ambient.js";
import { useStore } from "../lib/store.jsx";
import { Logo, Sprig } from "../ui/art.jsx";
import { Callout, Dialog, Field, Form } from "../ui/kit.jsx";
import { Mascot, MascotAvatar } from "../ui/mascot.jsx";

const INTRO = "سلام، من زیتو هستم. هر روز یک قدم کوچک با هم برمی‌داریم تا مهارت تازه‌ات را در کار واقعی به کار ببری. آماده‌ای شروع کنیم؟";

export function Landing() {
  const { session, go } = useStore();
  const [typed, setTyped] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const sound = useAmbient();

  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return setTyped(INTRO);
    let count = 0;
    let next;
    const first = setTimeout(function tick() {
      count++;
      setTyped(INTRO.slice(0, count));
      if (count < INTRO.length) next = setTimeout(tick, 35);
    }, 800);
    return () => (clearTimeout(first), clearTimeout(next));
  }, []);

  const done = typed.length === INTRO.length;
  const learner = session.role === "learner";
  const start = () => (learner ? go({ name: "home" }) : setAuthOpen(true));

  return (
    <div className="landing">
      <header className="land-top">
        <Logo />
        <button
          className="icon-btn"
          onClick={toggleAmbient}
          aria-pressed={!sound.muted}
          aria-label={sound.muted ? "پخش موسیقی" : "قطع موسیقی"}
          title={sound.muted ? "پخش موسیقی" : "قطع موسیقی"}
          style={{ marginInlineStart: "auto" }}
        >
          {sound.muted ? <VolumeX /> : <Volume2 />}
        </button>
        <button className="btn btn-ghost" style={{ marginInlineStart: 0 }} onClick={() => go({ name: "certificate" })}>
          <BadgeCheck /> استعلام گواهی
        </button>
        <button className="btn btn-soft" onClick={start}>
          {learner ? "ادامه‌ی یادگیری" : "ورود / ثبت‌نام"}
        </button>
      </header>
      <section className="land-hero">
        <div>
          <span className="badge badge-accent" style={{ marginBottom: "1rem" }}>
            آموزش فارسی با کوچ هوشمند
          </span>
          <h1>
            مهارت کاری تازه،
            <br />
            <em>قدم‌به‌قدم</em> و مخصوص تو
          </h1>
          <p className="lead">
            زیتو هر درس را با شغل و هدف تو تطبیق می‌دهد، کنار هر مرحله به سؤال‌هایت از روی محتوای همان دوره جواب می‌دهد
            و در پایان گواهی قابل استعلام می‌گیری.
          </p>
          <div className="row">
            <button className="btn btn-primary btn-lg" onClick={start} disabled={!done && !learner} aria-disabled={!done}>
              شروع کنید <ArrowLeft />
            </button>
            <button className="btn btn-ghost btn-lg" onClick={() => setAboutOpen(true)}>
              زیتو چیه؟
            </button>
          </div>
        </div>
        <div className="land-stage">
          <div className="land-orb" />
          <div className="speech mat mat-panel" aria-live="polite">
            {typed}
            {!done && <span className="caret" />}
          </div>
          <Mascot motion="wave" height="17rem" className="land-mascot" />
        </div>
      </section>
      <section className="land-feats" aria-label="ویژگی‌ها">
        {[
          [<Route />, "lav", "مسیر ۸مرحله‌ای", "هر سرفصل از نقشه تا آزمونک؛ همیشه می‌دانی قدم بعدی چیست."],
          [<MessageCircleHeart />, "rose", "کوچ با منبع", "جواب‌ها فقط از محتوای تأییدشده‌ی همان دوره و با منبع."],
          [<BookOpenCheck />, "peach", "مثال در شغل تو", "هر درس یک مثال از دنیای کاری خودت دارد."],
          [<ShieldCheck />, "mint", "گواهی قابل استعلام", "شماره‌دار و قابل بررسی برای هر کارفرما."],
        ].map(([icon, tone, title, text]) => (
          <div key={title} className="feat mat mat-panel">
            <span className={`tile tile-${tone}`}>{icon}</span>
            <b>{title}</b>
            <p>{text}</p>
          </div>
        ))}
      </section>
      <Sprig className="land-sprig" flowers={12} />
      {aboutOpen && (
        <Dialog title="زیتو چیه؟" onClose={() => setAboutOpen(false)} icon={<MascotAvatar size="2.4rem" />}>
          <div className="about-mascot">
            <Mascot motion="intro" height="13rem" />
          </div>
          <p className="soft" style={{ lineHeight: 2.1 }}>
            زیتو یک همراه یادگیری است. دوره‌ها را تیم محتوا با کمک هوش مصنوعی می‌سازد و بازبینی می‌کند. تو
            سرفصل‌به‌سرفصل جلو می‌روی؛ هر سرفصل هشت مرحله دارد: نقشه، خلاصه‌ی درس، فلش‌کارت، نکات طلایی، اشتباهات رایج،
            مثال در شغل تو، آزمونک و جمع‌بندی. هر جا گیر کردی، از زیتو بپرس.
          </p>
          <button
            className="btn btn-primary btn-block"
            style={{ marginTop: "1.2rem" }}
            onClick={() => (setAboutOpen(false), start())}
          >
            آماده‌ام، شروع کنیم
          </button>
        </Dialog>
      )}
      {authOpen && <AuthDialog onClose={() => setAuthOpen(false)} />}
    </div>
  );
}

const EMPTY_CODE = ["", "", "", "", "", ""];

export function AuthDialog({ onClose }) {
  const { otp, requestOtp, verifyOtp, setOtp } = useStore();
  const [mode, setMode] = useState("login");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [digits, setDigits] = useState(EMPTY_CODE);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());
  const boxes = useRef([]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (otp) boxes.current[0]?.focus();
  }, [otp?.sentAt]);

  const send = async () => {
    if (busy) return;
    setError(null);
    setBusy(true);
    const result = await requestOtp(otp?.phone || phone, otp?.mode || mode, mode === "register" ? name : undefined);
    setBusy(false);
    if (result.ok) setDigits(EMPTY_CODE);
    else setError({ field: result.field, msg: result.msg });
  };
  const verify = async () => {
    if (busy) return;
    setError(null);
    setBusy(true);
    const result = await verifyOtp(digits.join(""), name);
    setBusy(false);
    if (result.ok) onClose();
    else setError({ field: result.field, msg: result.msg });
  };
  const typeDigit = (index, value) => {
    const clean = normDigits(value).replace(/\D/g, "");
    if (clean.length > 1) {
      const chars = clean.slice(0, 6).split("");
      setDigits(Array.from({ length: 6 }, (_, i) => chars[i] ?? ""));
      boxes.current[Math.min(chars.length, 5)]?.focus();
      return;
    }
    const next = digits.slice();
    next[index] = clean;
    setDigits(next);
    if (clean && index < 5) boxes.current[index + 1]?.focus();
  };
  const wait = otp ? Math.max(0, Math.ceil((otp.resendAt - now) / 1000)) : 0;
  const blocked = error?.msg?.includes("مسدود");

  return (
    <Dialog
      title={otp ? "کد تأیید را وارد کن" : mode === "login" ? "ورود به زیتو" : "ثبت‌نام در زیتو"}
      onClose={onClose}
      icon={
        <span className="tile tile-lav">
          <Smartphone />
        </span>
      }
    >
      {otp ? (
        <Form onSubmit={verify}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="soft" style={{ fontSize: "var(--t-small)" }}>
              کد به <span className="ltr">{otp.phone}</span> فرستاده شد.
            </span>
            <button type="button" className="link-btn" onClick={() => (setOtp(null), setError(null))}>
              <Pencil /> ویرایش شماره
            </button>
          </div>
          {otp.code && (
            <div className="callout callout-info test-code">
              <span>حالت تست (پیامک شبیه‌سازی‌شده). کد:</span>
              <b className="ltr">{otp.code}</b>
            </div>
          )}
          <Field
            label="کد ۶ رقمی"
            error={error?.field === "code" && !blocked ? error.msg : undefined}
            hint={`کد تا ${fa(Math.max(0, Math.ceil((otp.expiresAt - now) / 60000)))} دقیقه‌ی دیگر معتبر است. ارقام فارسی هم پذیرفته می‌شود.`}
          >
            <div className="otp-boxes" onPaste={(e) => (e.preventDefault(), typeDigit(0, e.clipboardData.getData("text")))}>
              {digits.map((digit, i) => (
                <input
                  key={i}
                  ref={(el) => (boxes.current[i] = el)}
                  className="input"
                  inputMode="numeric"
                  autoComplete={i === 0 ? "one-time-code" : "off"}
                  aria-label={`رقم ${fa(i + 1)}`}
                  value={digit}
                  maxLength={6}
                  onChange={(e) => typeDigit(i, e.target.value)}
                  onKeyDown={(e) => e.key === "Backspace" && !digit && i > 0 && boxes.current[i - 1]?.focus()}
                />
              ))}
            </div>
          </Field>
          {otp.requiresName && (
            <Field label="این شماره حساب ندارد. اسمت را بنویس" req error={error?.field === "name" ? error.msg : undefined} hint="همین اسم روی گواهی پایان دوره می‌آید.">
              <input
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                placeholder="اسم و فامیل"
              />
            </Field>
          )}
          {blocked && <Callout tone="err">این حساب توسط مدیریت مسدود شده است.</Callout>}
          <button className="btn btn-primary btn-block btn-lg" type="submit" disabled={busy || digits.join("").length !== 6}>
            {busy ? "در حال ورود…" : "ورود"}
          </button>
          <button type="button" className="btn btn-ghost" disabled={busy || wait > 0} onClick={send}>
            <RefreshCw /> {wait > 0 ? `ارسال دوباره‌ی کد تا ${fa(wait)} ثانیه‌ی دیگر` : "ارسال دوباره‌ی کد"}
          </button>
        </Form>
      ) : (
        <Form onSubmit={send}>
          <p className="soft" style={{ fontSize: "var(--t-small)" }}>
            رمز لازم نیست. شماره‌ی موبایلت را بنویس تا یک کد ۶ رقمی برایت پیامک شود.
          </p>
          {mode === "register" && (
            <Field label="اسم و فامیل" req error={error?.field === "name" ? error.msg : undefined} hint="همین اسم روی گواهی پایان دوره می‌آید.">
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" placeholder="مثلاً مریم احمدی" />
            </Field>
          )}
          <Field label="شماره‌ی موبایل" req error={["phone", "wait"].includes(error?.field) && !blocked ? error.msg : undefined}>
            <input
              className="input ltr"
              style={{ textAlign: "left" }}
              dir="ltr"
              inputMode="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="09121234567"
              autoComplete="tel"
            />
          </Field>
          {blocked && <Callout tone="err">این حساب توسط مدیریت مسدود شده است.</Callout>}
          <button className="btn btn-primary btn-block btn-lg" type="submit" disabled={busy}>
            {busy ? "در حال ارسال…" : "ارسال کد"}
          </button>
          <button
            type="button"
            className="link-btn"
            style={{ justifySelf: "center" }}
            onClick={() => (setMode(mode === "login" ? "register" : "login"), setError(null))}
          >
            {mode === "login" ? "حساب نداری؟ ثبت‌نام کن" : "حساب داری؟ وارد شو"}
          </button>
        </Form>
      )}
    </Dialog>
  );
}
