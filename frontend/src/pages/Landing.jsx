// Public landing page and the phone sign-in / sign-up dialog.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  BadgeCheck,
  BookOpenCheck,
  Check,
  Footprints,
  Info,
  MessageCircleHeart,
  Pencil,
  RefreshCw,
  Route,
  Search,
  Send,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Volume2,
  VolumeX,
} from "lucide-react";
import { fa, normDigits } from "../lib/format.js";
import { toggleAmbient, useAmbient } from "../lib/ambient.js";
import { clearIntent, readIntent, rememberIntent } from "../lib/intent.js";
import { STAGE_TITLES, useCourses } from "../lib/learner.js";
import { profileComplete, useStore } from "../lib/store.jsx";
import { CoachAvatar, Logo, Sprig } from "../ui/art.jsx";
import { AIBar, Callout, Dialog, Field, Form, Skel, Sources } from "../ui/kit.jsx";
import { Mascot, MascotStill } from "../ui/mascot.jsx";
import { CourseCard } from "./Courses.jsx";
import { SectionHead } from "./CourseOverview.jsx";

const INTRO = "سلام، من زیتو هستم. هر روز یک قدم کوچک با هم برمی‌داریم تا مهارت تازه‌ات را در کار واقعی به کار ببری. آماده‌ای شروع کنیم؟";

const NAV = [
  ["land-samples", "نمونه‌ی گفت‌وگو"],
  ["land-about", "زیتو چیه؟"],
  ["land-courses", "دوره‌ها"],
];

// Sample conversations, written from the courses' own text. A tab shows only while its course is published.
const SAMPLES = [
  {
    key: "life",
    tab: "هوش مصنوعی در زندگی",
    match: /ai.?life|کار و زندگی/i,
    title: "از اولین درخواست تا یک دستیار روزمره",
    text: "بدون هیچ پیش‌زمینه‌ی فنی یاد می‌گیری از هوش مصنوعی درست بخواهی، جوابش را بسنجی و در کارهای واقعی خودت از آن کمک بگیری.",
    points: ["نوشتن درخواست دقیق", "برنامه‌ریزی و یادگیری سریع‌تر", "بررسی درستی جواب‌ها"],
    question: "چرا جواب هوش مصنوعی به کارم نمی‌آید و خیلی کلی است؟",
    answer:
      "چون احتمالاً فقط گفته‌ای چه می‌خواهی. درخواست دقیق می‌تواند پنج بخش داشته باشد: نقش، هدف، زمینه، قالب خروجی و محدودیت‌ها؛ البته همیشه هر پنج تا لازم نیست. به‌جای «یک برنامه بده» بنویس: «تو مربی برنامه‌ریزی هستی. برای هفته‌ی شلوغم با روزی ۳۰ دقیقه وقت آزاد، یک جدول با زمان استراحت بده.»",
    source: { n: 1, title: "جادوی پرامپت‌نویسی", scope: "سرفصل ۲" },
  },
  {
    key: "growth",
    tab: "توسعه‌ی فردی",
    match: /personal-development|فردی/,
    title: "از یک خواسته‌ی کلی تا یک برنامه‌ی قابل اجرا",
    text: "هدفت را به رفتاری روشن تبدیل می‌کنی، عادت می‌سازی و یاد می‌گیری بعد از هر وقفه به مسیر برگردی.",
    points: ["هدف‌گذاری از مسئله‌ی واقعی", "ساختن عادت و بازگشت بعد از وقفه", "تصمیم‌گیری با کمک هوش مصنوعی"],
    question: "هر بار برنامه می‌چینم ولی بعد از چند روز رهایش می‌کنم. چه کار کنم؟",
    answer:
      "«بیشتر تمرین می‌کنم» نشانه‌ی شروع ندارد. برنامه را اگر-آنگاه بنویس: «پس از جمع‌کردن میز صبحانه، پنج دقیقه تمرین می‌کنم.» محیط را از قبل آماده کن و یک مانع را کم کن. برای روز سخت هم یک نسخه‌ی حداقلی نگه دار تا بعد از وقفه راحت‌تر برگردی؛ فقط جای تمرین اصلی را برای همیشه نگیرد.",
    source: { n: 1, title: "سیستم عادت، محیط و بازگشت بعد از وقفه", scope: "سرفصل ۲" },
  },
  {
    key: "marketing",
    tab: "بازاریابی",
    match: /marketing|بازاریابی/,
    title: "از شناخت مشتری تا پیامی که فهمیده می‌شود",
    text: "مسئله‌ی واقعی مشتری را پیدا می‌کنی، پیشنهاد ارزش می‌سازی و جذب را با آزمایش‌های کوچک و قابل اندازه‌گیری جلو می‌بری.",
    points: ["شناخت مسئله و مشتری ایده‌آل", "پیشنهاد ارزش و پیام", "آزمایش کانال و اندازه‌گیری نتیجه"],
    question: "متن تبلیغم فقط ویژگی‌های محصول را می‌گوید. چطور بهترش کنم؟",
    answer:
      "ویژگی می‌گوید محصول چه دارد؛ منفعت می‌گوید چه تغییری برای مشتری ایجاد می‌کند. پیام را با چهار چیز بازنویسی کن: مخاطب، موقعیت، نتیجه‌ی مطلوب و یک دلیل باورپذیر. ادعای «بهترین» بدون معیار کمکی نمی‌کند. بعد متن را به یک نفر نشان بده و بخواه برداشتش را بازگو کند، نه فقط بگوید دوستش دارد یا نه.",
    source: { n: 1, title: "پیشنهاد ارزش، جایگاه‌سازی و پیام", scope: "سرفصل ۳" },
  },
  {
    key: "sales",
    tab: "فروش",
    match: /sales|فروش/,
    title: "از اولین تماس تا پاسخ درست به اعتراض مشتری",
    text: "تماس فروش را حرفه‌ای شروع می‌کنی، با پرسش درست نیاز مشتری را کشف می‌کنی و اعتراض را با آرامش جواب می‌دهی.",
    points: ["شروع قدرتمند تماس", "کشف نیاز با مدل SPIN", "مدیریت اعتراض مشتری"],
    question: "مشتری می‌گوید قیمت‌تان خیلی بالاست. چطور جواب بدهم که بحث نشود؟",
    answer:
      "اعتراض نشانه‌ی دغدغه‌ی مشتری است، نه بی‌علاقگی. اول کامل گوش بده و نگرانی‌اش را تأیید کن. قیمت اعتراض منطقی است، پس ارزش محصول را به نیاز خودش وصل کن؛ مثلاً: «درک می‌کنم قیمت برایتان مهم است. اجازه بدهید بگویم خدمات پس از فروش این محصول چه چیزی به شما می‌دهد. این خدمات برایتان مهم است؟» وارد بحث یا دفاع شدید نشو و جوابت را کوتاه و هدفمند نگه دار.",
    source: { n: 1, title: "مدیریت اعتراضات", scope: "سرفصل ۹" },
  },
];

const EXAMPLES = [
  ["کارشناس فروش", "اگر آخرین تماس صبح تمام شد، پنج دقیقه نتیجه‌ی تماس‌ها را یادداشت می‌کنم تا پیگیری بعدی از یادم نرود."],
  ["حسابداری", "اگر ثبت اسناد روز تمام شد، پنج دقیقه مغایرت‌ها را مرور می‌کنم تا آخر ماه غافلگیر نشوم."],
  ["دانشجو", "اگر کلاس صبح تمام شد، پنج دقیقه بدون نگاه به جزوه نکته‌های مهم را می‌نویسم."],
];

// The three intro sections in page order; the sticky tabs follow them as the page scrolls.
const INTRO_TABS = [
  ["land-coach", "کوچ با منبع"],
  ["land-example", "مثال در شغل تو"],
  ["land-path", "مسیر تا گواهی"],
];

const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const jump = (id) => document.getElementById(id)?.scrollIntoView({ behavior: calm() ? "auto" : "smooth" });

// Scroll-driven depth is for wide screens; phones and reduced motion keep a plain page.
const deep = () => matchMedia("(min-width: 901px) and (prefers-reduced-motion: no-preference)").matches;

// Feeds the stylesheet the scroll position: how far the sheet has covered the hero, and how far each block has risen.
function useScrollDepth(hero, sheet) {
  useEffect(() => {
    let frame = 0;
    const paint = () => {
      frame = 0;
      const height = hero.current.offsetHeight;
      hero.current.style.setProperty("--land-hero-h", `${height}px`);
      if (!deep()) return;
      const covered = Math.min(1, window.scrollY / height);
      hero.current.style.setProperty("--covered", covered.toFixed(3));
      hero.current.classList.toggle("land-hero-gone", covered === 1);
      const top = sheet.current.getBoundingClientRect().top;
      for (const block of sheet.current.querySelectorAll("[data-depth]")) {
        // offsetTop ignores the transform this sets, so a block cannot chase its own position.
        const rise = (window.innerHeight - top - block.offsetTop) / (window.innerHeight * 0.45);
        block.style.setProperty("--rise", Math.min(1, Math.max(0, rise)).toFixed(3));
      }
    };
    const request = () => {
      frame ||= requestAnimationFrame(paint);
    };
    paint();
    window.addEventListener("scroll", request, { passive: true });
    window.addEventListener("resize", request);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", request);
      window.removeEventListener("resize", request);
    };
  }, [hero, sheet]);
}

// Types `text` out once `run` is true; with reduced motion it appears at once.
function useTyped(text, run, delay, speed) {
  const [typed, setTyped] = useState("");
  useEffect(() => {
    if (!run) return undefined;
    if (calm()) return setTyped(text);
    let count = 0;
    let next;
    const first = setTimeout(function tick() {
      count++;
      setTyped(text.slice(0, count));
      if (count < text.length) next = setTimeout(tick, speed);
    }, delay);
    return () => (clearTimeout(first), clearTimeout(next));
  }, [text, run, delay, speed]);
  return typed;
}

// Typing lives here so the page, and an open sign-in dialog, do not re-render with every letter.
function Speech() {
  const typed = useTyped(INTRO, true, 800, 35);
  return (
    <div className="speech mat mat-panel" aria-live="polite">
      {typed}
      {typed.length < INTRO.length && <span className="caret" />}
    </div>
  );
}

function SampleChat({ sample, run, onAsk }) {
  const typed = useTyped(sample.answer, run, 1100, 14);
  const done = typed.length === sample.answer.length;
  return (
    <div className="coach land-chat mat mat-panel">
      <header className="coach-head">
        <CoachAvatar size="2.4rem" />
        <div>
          <h3>کوچ زیتو</h3>
          <span className="online">آنلاین</span>
        </div>
      </header>
      <div className="msgs">
        <div className="msg msg-user">
          <div className="bubble">{sample.question}</div>
        </div>
        <div className="msg msg-coach">
          <CoachAvatar size="2.2rem" busy={!typed} />
          <div className="bubble mat mat-raised">
            <span className="sr-only">{sample.answer}</span>
            {typed ? (
              <>
                <span className="badge badge-ok" style={{ justifySelf: "start" }}>
                  جواب مستند
                </span>
                <span aria-hidden="true">
                  {typed}
                  {!done && <span className="caret" />}
                </span>
              </>
            ) : (
              <span className="soft" aria-hidden="true">
                در حال یافتن منابع تأییدشده…{" "}
                <span className="typing">
                  <i />
                  <i />
                  <i />
                </span>
              </span>
            )}
            {done && (
              <>
                <Sources sources={[sample.source]} />
                <AIBar meta={{ status: "ready" }} sources={1} />
              </>
            )}
          </div>
        </div>
      </div>
      <button className="composer mat mat-field land-ask" onClick={onAsk}>
        <span>سؤال خودت را از زیتو بپرس…</span>
        <span className="send" aria-hidden="true">
          <Send />
        </span>
      </button>
    </div>
  );
}

// Topic tabs. Given `onNext` they play as the hero's slides: the open tab fills its bar, then hands over.
function TopicTabs({ tabs, sample, onPick, onNext, paused }) {
  if (tabs.length < 2) return null;
  return (
    <div className="seg land-tabs" role="tablist" aria-label="موضوع گفت‌وگو" data-paused={paused || undefined}>
      {tabs.map((tab) => (
        <button key={tab.key} role="tab" aria-selected={tab.key === sample.key} onClick={() => onPick(tab.key)}>
          {tab.tab}
          {onNext && tab.key === sample.key && <i className="land-tab-bar" onAnimationEnd={onNext} />}
        </button>
      ))}
    </div>
  );
}

// The hero's question box: types the open topic's question, and pressing it starts the way in.
function HeroAsk({ sample, onAsk }) {
  const typed = useTyped(sample?.question ?? "", Boolean(sample), 300, 28);
  return (
    <button className="composer mat mat-field land-ask" onClick={onAsk}>
      <span>{typed || "سؤال خودت را از زیتو بپرس…"}</span>
      <span className="send" aria-hidden="true">
        <Send />
      </span>
    </button>
  );
}

function Samples({ tabs, sample, onPick, onAsk, onView }) {
  const [seen, setSeen] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setSeen(true);
        onView(entry.isIntersecting);
      },
      { threshold: 0.3 },
    );
    observer.observe(box.current);
    return () => observer.disconnect();
  }, [onView]);

  return (
    <section id="land-samples" className="land-section land-samples" aria-labelledby="land-samples-title">
      <SectionHead
        id="land-samples-title"
        kicker="نمونه‌ی گفت‌وگو با زیتو"
        title="از کارهای روزمره تا مهارت‌های تخصصی، از زیتو بپرس"
        intro="یک موضوع انتخاب کن و ببین زیتو چطور از روی محتوای همان دوره جواب می‌دهد."
      />
      <TopicTabs tabs={tabs} sample={sample} onPick={onPick} />
      <div className="land-sample" ref={box} data-depth>
        <div className="ov-cert-copy">
          <h3>{sample.title}</h3>
          <p>{sample.text}</p>
          <ul className="ov-points">
            {sample.points.map((point) => (
              <li key={point}>
                <Check /> {point}
              </li>
            ))}
          </ul>
        </div>
        <SampleChat key={sample.key} sample={sample} run={seen} onAsk={onAsk} />
      </div>
    </section>
  );
}

function InfoRow({ id, kicker, title, text, points, children }) {
  return (
    <section id={id} className="land-info mat mat-panel" aria-labelledby={`${id}-title`} data-depth>
      <div className="ov-cert-copy">
        <span className="ov-kicker">{kicker}</span>
        <h2 id={`${id}-title`}>{title}</h2>
        <p>{text}</p>
        <ul className="ov-points">
          {points.map(([icon, point]) => (
            <li key={point}>
              {icon} {point}
            </li>
          ))}
        </ul>
      </div>
      <div className="land-info-art">{children}</div>
    </section>
  );
}

// Sticky tabs over the intro sections: the open one follows the section at the middle of the screen, a press jumps there.
function IntroTabs() {
  const [active, setActive] = useState(INTRO_TABS[0][0]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => entry.isIntersecting && setActive(entry.target.id)),
      { rootMargin: "-45% 0px -50% 0px" },
    );
    INTRO_TABS.forEach(([id]) => observer.observe(document.getElementById(id)));
    return () => observer.disconnect();
  }, []);

  return (
    <div className="seg land-spy" role="tablist" aria-label="بخش‌های معرفی">
      {INTRO_TABS.map(([id, label]) => (
        <button key={id} role="tab" aria-selected={id === active} onClick={() => jump(id)}>
          {label}
        </button>
      ))}
    </div>
  );
}

function ExampleDemo() {
  const [picked, setPicked] = useState(0);
  return (
    <div className="land-example mat mat-raised">
      <span className="badge badge-accent" style={{ justifySelf: "start" }}>
        درس: برنامه‌ی اگر-آنگاه
      </span>
      <div className="choice-row" role="group" aria-label="یک شغل نمونه انتخاب کن">
        {EXAMPLES.map(([job], i) => (
          <button key={job} className="chip" aria-pressed={i === picked} onClick={() => setPicked(i)}>
            {job}
          </button>
        ))}
      </div>
      <h3>{STAGE_TITLES.personalized_work_example}</h3>
      <p aria-live="polite">«{EXAMPLES[picked][1]}»</p>
    </div>
  );
}

const REEL_PACE = 30; // pixels per second
const REEL_REST = 1500; // ms the row waits after a hand leaves it, so a swipe can finish

// The course row: a row wider than the screen slides by itself and loops on a hidden copy; one that fits stands still.
function CourseGallery({ courses, onOpen }) {
  const box = useRef(null);
  const set = useRef(null);
  const held = useRef(false);
  const wakeAt = useRef(0);
  const [loops, setLoops] = useState(false);

  useEffect(() => {
    const observer = new ResizeObserver(() => setLoops(!calm() && set.current.offsetWidth > box.current.clientWidth));
    observer.observe(box.current);
    return () => observer.disconnect();
  }, [courses.length]);

  useEffect(() => {
    if (!loops) return undefined;
    const el = box.current;
    let position = 0;
    let inView = false;
    let frame;
    let last = performance.now();
    const watcher = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
    });
    watcher.observe(el);
    const tick = (now) => {
      // The page is right-to-left, so the next card lies toward a negative scrollLeft.
      if (held.current || now < wakeAt.current) position = Math.abs(el.scrollLeft);
      else if (inView) {
        position = (position + (Math.min(now - last, 50) / 1000) * REEL_PACE) % set.current.offsetWidth;
        el.scrollLeft = -position;
      }
      last = now;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      watcher.disconnect();
    };
  }, [loops]);

  const hold = () => {
    held.current = true;
  };
  const release = () => {
    held.current = false;
    wakeAt.current = performance.now() + REEL_REST;
  };
  const cards = courses.map((course) => <CourseCard key={course.id} course={course} onOpen={onOpen} />);

  return (
    <div className="land-gallery" ref={box} onPointerEnter={hold} onPointerLeave={release} onFocus={hold} onBlur={release}>
      <div className="land-reel">
        <div className="land-reel-set" ref={set}>
          {cards}
        </div>
        {loops && (
          <div className="land-reel-set" aria-hidden="true" inert>
            {cards}
          </div>
        )}
      </div>
    </div>
  );
}

function CertLookup() {
  const { go } = useStore();
  const [query, setQuery] = useState("");
  const submit = () => query.trim() && go({ name: "certificate", id: query.trim().toUpperCase() });
  return (
    <div className="land-lookup">
      <span>گواهی زیتو داری؟ اینجا استعلام کن.</span>
      <Form className="search-box mat mat-field" onSubmit={submit}>
        <Search />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="شماره‌ی گواهی، مثل ZITO-2026-…" aria-label="شماره‌ی گواهی" dir="ltr" style={{ textAlign: "left" }} />
        <button type="submit" className="link-btn">
          استعلام
        </button>
      </Form>
    </div>
  );
}

export function Landing() {
  const { session, profile, go } = useStore();
  const courses = useCourses();
  const sound = useAmbient();
  const [authOpen, setAuthOpen] = useState(false);
  const [picked, setPicked] = useState(null);
  const [rolling, setRolling] = useState(() => !calm()); // the hero's slides turn until a person picks a topic
  const [chatInView, setChatInView] = useState(false);
  const held = useRef(null); // a click made before the session is known
  const hero = useRef(null);
  const sheet = useRef(null);
  const learner = session.role === "learner";
  useScrollDepth(hero, sheet);

  // Every way in: a guest signs in first, a learner with an unfinished profile finishes it, the rest arrive.
  const enter = (route) => {
    if (session.role === "loading") {
      held.current = route;
      return;
    }
    if (!learner) {
      rememberIntent(route);
      setAuthOpen(true);
      return;
    }
    if (!profileComplete(profile)) rememberIntent(route);
    go(route);
  };
  const closeAuth = useCallback(() => {
    clearIntent();
    setAuthOpen(false);
  }, []);

  useEffect(() => {
    if (session.role === "loading") return;
    if (held.current) {
      enter(held.current);
      held.current = null;
    } else if (session.role === "guest" && readIntent()) setAuthOpen(true); // a direct link, or a refresh mid sign-in
  }, [session.role]);

  const login = () => enter({ name: "home" });
  const start = () => enter({ name: "courses" });
  const startLabel = learner ? "دیدن دوره‌ها" : "شروع رایگان";
  const published = courses.data ?? [];
  const hasCourses = published.length > 0 || courses.loading;
  // A topic shows only while its course is published; the hero's slide and the sample chat follow the same pick.
  const tabs = SAMPLES.filter((s) => published.some((c) => s.match.test(`${c.slug} ${c.title}`)));
  const sample = tabs.find((s) => s.key === picked) ?? tabs[0];
  const pick = (key) => {
    setPicked(key);
    setRolling(false);
  };
  const nextTab = () => setPicked(tabs[(tabs.indexOf(sample) + 1) % tabs.length].key);
  const nav = NAV.filter(([id]) => (id !== "land-courses" || hasCourses) && (id !== "land-samples" || sample));

  return (
    <div className="landing">
      <header className="land-top mat mat-panel">
        <Logo />
        <nav className="land-nav" aria-label="بخش‌های صفحه">
          {nav.map(([id, label]) => (
            <button key={id} className="btn btn-ghost btn-sm" onClick={() => jump(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="land-actions">
          <button
            className="icon-btn land-wide"
            onClick={toggleAmbient}
            aria-pressed={!sound.muted}
            aria-label={sound.muted ? "پخش موسیقی" : "قطع موسیقی"}
            title={sound.muted ? "پخش موسیقی" : "قطع موسیقی"}
          >
            {sound.muted ? <VolumeX /> : <Volume2 />}
          </button>
          <button className="btn btn-ghost land-wide" onClick={() => go({ name: "certificate" })}>
            <BadgeCheck /> استعلام گواهی
          </button>
          <button className="btn btn-soft" onClick={login}>
            {learner ? "ادامه‌ی یادگیری" : "ورود / ثبت‌نام"}
          </button>
          <button className="btn btn-primary" onClick={start}>
            {startLabel}
          </button>
        </div>
      </header>
      <section className="land-hero" ref={hero}>
        <div className="land-hero-copy">
          <span className="badge badge-accent">آموزش فارسی با کوچ هوشمند</span>
          <h1>
            از روزمره‌ترین مهارت‌ها تا <em>تخصصی‌ترین آموزش‌ها</em>، با زیتو
          </h1>
          <p className="lead">
            زیتو هر درس را با شغل و هدف تو تطبیق می‌دهد، کنار هر مرحله به سؤال‌هایت از روی محتوای همان دوره جواب می‌دهد
            و در پایان گواهی قابل استعلام می‌گیری.
          </p>
        </div>
        <div className="land-hero-core">
          <HeroAsk key={sample?.key} sample={sample} onAsk={start} />
          <div className="land-stage">
            <div className="land-orb" aria-hidden="true" />
            <div className="land-stage-depth">
              <Speech />
              <Mascot motion="wave" height="15rem" className="land-mascot" />
            </div>
          </div>
        </div>
        <TopicTabs tabs={tabs} sample={sample} onPick={pick} onNext={rolling ? nextTab : undefined} paused={chatInView || authOpen} />
        <div className="row land-hero-cta">
          <button className="btn btn-primary btn-lg" onClick={start}>
            {startLabel} <ArrowLeft />
          </button>
          <button className="btn btn-ghost btn-lg" onClick={() => jump("land-about")}>
            زیتو چیه؟
          </button>
        </div>
        <Sprig className="land-sprig" flowers={12} />
      </section>
      <div className="land-sheet" ref={sheet}>
        {sample && <Samples tabs={tabs} sample={sample} onPick={pick} onAsk={start} onView={setChatInView} />}
        <div className="land-section land-infos">
          <IntroTabs />
          <InfoRow
            id="land-coach"
            kicker="کوچ با منبع"
            title="جواب‌ها از محتوای همان دوره می‌آید، نه از حدس"
            text="زیتو کنار هر مرحله به سؤال‌هایت جواب می‌دهد و نشان می‌دهد جواب از کدام بخش دوره آمده است."
            points={[
              [<MessageCircleHeart key="1" />, "جواب‌ها فقط از محتوای تأییدشده‌ی همان دوره و با منبع."],
              [<Footprints key="2" />, "بعد از هر جواب، یک قدم بعدی روشن پیشنهاد می‌شود."],
              [<ShieldCheck key="3" />, "سؤال نامرتبط جواب ساختگی نمی‌گیرد."],
            ]}
          >
            <div className="land-proof">
              <div className="msg msg-coach">
                <CoachAvatar size="2.2rem" />
                <div className="bubble mat mat-raised">
                  <span className="badge badge-ok" style={{ justifySelf: "start" }}>
                    جواب مستند
                  </span>
                  <span>«فعلاً وقت ندارم» اعتراض تاکتیکی است و معمولاً برای فرار از تصمیم‌گیری گفته می‌شود. جواب کوتاه و هدفمند بده و پیگیری در زمان مناسب را پیشنهاد کن.</span>
                  <div className="next-step">
                    <Footprints />
                    <span>
                      <b>قدم بعدی پیشنهادی: </b>اعتراض بعدی‌ای را که شنیدی، منطقی، احساسی یا تاکتیکی دسته‌بندی کن.
                    </span>
                  </div>
                  <Sources sources={[SAMPLES[3].source]} />
                  <AIBar meta={{ status: "ready" }} sources={1} />
                </div>
              </div>
              <div className="msg msg-coach">
                <CoachAvatar size="2.2rem" />
                <div className="bubble mat mat-raised">
                  <span className="badge badge-warn" style={{ justifySelf: "start" }}>
                    <Info /> بیرون از حوزه‌ی درس
                  </span>
                  <span>در منابع تأییدشده‌ی این سرفصل، پاسخ قابل اتکایی برای این سؤال پیدا نکردم.</span>
                  <AIBar meta={{ status: "review" }} sources={0} />
                </div>
              </div>
            </div>
          </InfoRow>
          <InfoRow
            id="land-example"
            kicker="مثال در شغل تو"
            title="هر درس یک مثال از دنیای کاری خودت دارد"
            text="زیتو از همان اول چند سؤال کوتاه درباره‌ی کار و هدفت می‌پرسد و مثال هر سرفصل را برای تو می‌سازد."
            points={[
              [<BookOpenCheck key="1" />, "مثال‌ها از روی محتوای درس و پروفایل خودت ساخته می‌شوند."],
              [<Sparkles key="2" />, "درس همان است؛ مثالش به زبان کار تو می‌آید."],
            ]}
          >
            <ExampleDemo />
          </InfoRow>
          <InfoRow
            id="land-path"
            kicker="از قدم اول تا گواهی"
            title="مسیر هشت‌مرحله‌ای، تا گواهی قابل استعلام"
            text="هر سرفصل از نقشه تا آزمونک هشت مرحله دارد؛ همیشه می‌دانی کجای مسیری و قدم بعدی چیست."
            points={[
              [<Route key="1" />, "پیشرفتت مرحله‌به‌مرحله ذخیره می‌شود."],
              [<ShieldCheck key="2" />, "گواهی شماره‌دار است و هر کارفرمایی بدون ورود می‌تواند بررسی‌اش کند."],
            ]}
          >
            <div className="land-path">
              <ol className="land-steps">
                {Object.values(STAGE_TITLES).map((title, i) => (
                  <li key={title} className="mat mat-raised">
                    <span className="ov-num">{fa(i + 1)}</span> {title}
                  </li>
                ))}
              </ol>
              <div className="ov-cert-card" aria-label="نمونه‌ی گواهی پایان دوره زیتو">
                <Logo compact />
                <span>گواهی پایان دوره زیتو</span>
                <strong>شماره‌دار و قابل استعلام</strong>
                <Sprig className="ov-cert-sprig" flowers={7} />
              </div>
            </div>
          </InfoRow>
        </div>
        <section id="land-about" className="land-about mat mat-panel" aria-labelledby="land-about-title" data-depth>
          <div className="land-about-art" aria-hidden="true">
            <Mascot motion="intro" height="13rem" />
          </div>
          <div className="ov-finish-copy">
            <span className="ov-kicker">زیتو چیه؟</span>
            <h2 id="land-about-title">یک همراه یادگیری که تا آخر مسیر کنارت می‌ماند</h2>
            <p>
              دوره‌ها را تیم محتوا با کمک هوش مصنوعی می‌سازد و بازبینی می‌کند. تو سرفصل‌به‌سرفصل جلو می‌روی و هر جا گیر کردی، از
              زیتو می‌پرسی؛ از مهارت‌های روزمره‌ای که هر روز به کارت می‌آید تا آموزش‌های تخصصی شغلت.
            </p>
          </div>
        </section>
        {hasCourses && (
          <section id="land-courses" className="land-courses" aria-labelledby="land-courses-title">
            <div className="land-section land-courses-head" data-depth>
              <SectionHead
                id="land-courses-title"
                kicker="دوره‌های زیتو"
                title="از همین دوره‌ها شروع کن"
                intro="روی هر دوره بزن تا مسیر و سرفصل‌هایش را ببینی."
              />
              <button className="btn btn-primary btn-lg" onClick={start}>
                {startLabel} <ArrowLeft />
              </button>
            </div>
            {published.length ? (
              <CourseGallery courses={published} onOpen={(course) => enter({ name: "course", slug: course.slug })} />
            ) : (
              <div className="land-section">
                <Skel lines={4} />
              </div>
            )}
          </section>
        )}
        <section className="land-section land-finish ov-finish mat mat-panel" aria-labelledby="land-finish" data-depth>
          <div className="ov-finish-art" aria-hidden="true">
            <span className="ov-portal" />
            <MascotStill pose="laptop" height="10.5rem" />
          </div>
          <div className="ov-finish-copy">
            <span className="ov-kicker">قدم اول همین‌جاست</span>
            <h2 id="land-finish">همین حالا شروع کنید</h2>
            <p>یک دوره انتخاب کن، چند سؤال کوتاه جواب بده و زیتو مسیر را با کار و هدف خودت همراه می‌کند.</p>
            <button className="btn btn-primary btn-lg" onClick={start}>
              {startLabel} <ArrowLeft />
            </button>
            <CertLookup />
          </div>
        </section>
      </div>
      {authOpen && <AuthDialog onClose={closeAuth} />}
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
    if (!result.ok) setError({ field: result.field, msg: result.msg }); // on success the store has moved on from this page
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
