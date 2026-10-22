// Course overview ("course landing"): the old page's journey — hero, destination, route map, impact,
// certificate, start — rebuilt with the new UI's materials and Zito's original mascot.
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { ArrowLeft, Award, BookOpen, Briefcase, Check, Clock, Flag, Heart, Layers, Lightbulb, MapPin, ShieldCheck, Signal, Sparkles } from "lucide-react";
import { useCached } from "../lib/cache.js";
import { fa } from "../lib/format.js";
import { K, useOverview } from "../lib/learner.js";
import { useStore } from "../lib/store.jsx";
import { HeroScene, Logo, Sprig } from "../ui/art.jsx";
import { Callout, Empty, Panel, Skel } from "../ui/kit.jsx";
import { Mascot, MascotStill } from "../ui/mascot.jsx";
import { hoursOf, useEnroll } from "./Courses.jsx";

const BEFORE = [
  "نمی‌دانی از کجا و با چه ترتیبی شروع کنی.",
  "آموخته‌ها به تمرین‌های کوچک و قابل انجام تبدیل نمی‌شوند.",
  "بعد از یک وقفه، برگشتن به مسیر سخت و مبهم است.",
];
const AFTER_FALLBACK = [
  "قدم بعدی‌ات را با یک نقشه‌ی روشن انتخاب می‌کنی.",
  "برای یادگیری و تمرین، ریتمی پایدار می‌سازی.",
  "آموخته‌ها را به موقعیت‌های واقعی خودت وصل می‌کنی.",
];
const IMPACT = [
  ["تمرین‌های کوتاه و هدفمند", "هر ایستگاه یک کار کوچک دارد تا یادگیری از صفحه بیرون بیاید و قابل انجام بماند."],
  ["مسیر قابل پیگیری", "همیشه می‌دانی در کجای مسیر هستی، چه چیزی تمام شده و قدم بعدی چیست."],
  ["همراهی زیتو در راه", "هرجا گیر کردی، زیتو کنار همان سرفصل برای فکر کردن و جلو رفتن همراهت است."],
];

function SectionHead({ kicker, title, intro, id }) {
  return (
    <div className="ov-head">
      <div>
        <span className="ov-kicker">{kicker}</span>
        <h2 id={id}>{title}</h2>
      </div>
      {intro && <p>{intro}</p>}
    </div>
  );
}

// Smooth road through the centres of the station nodes, measured from the layout.
function roadPath(points, width) {
  if (points.length < 2) return "";
  return points.slice(1).reduce((path, point, index) => {
    const prev = points[index];
    const dy = point.y - prev.y;
    const dx = point.x - prev.x;
    const vertical = Math.abs(dy) > Math.abs(dx);
    const sway = vertical ? Math.min(13, width * 0.035) : Math.min(34, width * 0.06);
    const dir = index % 2 === 0 ? 1 : -1;
    const c1x = vertical ? prev.x + sway * dir : prev.x + dx * 0.38;
    const c2x = vertical ? point.x - sway * dir : point.x - dx * 0.38;
    const c1y = vertical ? prev.y + dy * 0.36 : prev.y + dy * 0.75;
    const c2y = vertical ? point.y - dy * 0.36 : point.y - dy * 0.75;
    return `${path} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${point.x} ${point.y}`;
  }, `M ${points[0].x} ${points[0].y}`);
}

function RouteMap({ modules, fallbackStages, finishLabel, durationLabel }) {
  const track = useRef(null);
  const [road, setRoad] = useState(null);
  const id = useId().replace(/:/g, "");

  const measure = useCallback(() => {
    const el = track.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    const points = [...el.querySelectorAll(".route-node")].map((node) => {
      const b = node.getBoundingClientRect();
      return { x: Math.round(b.left - box.left + b.width / 2), y: Math.round(b.top - box.top + b.height / 2) };
    });
    const width = Math.max(1, Math.round(box.width));
    setRoad({ width, height: Math.max(1, Math.round(box.height)), d: roadPath(points, width) });
  }, []);

  useLayoutEffect(measure, [measure, modules.length]);
  useEffect(() => {
    const observer = new ResizeObserver(() => requestAnimationFrame(measure));
    observer.observe(track.current);
    document.fonts?.ready.then(measure);
    return () => observer.disconnect();
  }, [measure]);

  return (
    <div className="route mat mat-panel">
      <div className="route-legend">
        <span>
          <MapPin /> شروع مسیر
        </span>
        {durationLabel && (
          <span>
            <Clock /> {durationLabel}
          </span>
        )}
      </div>
      <div className="route-track" ref={track}>
        {road?.d && (
          <svg className="route-road" viewBox={`0 0 ${road.width} ${road.height}`} preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient id={`orb${id}`} x1="0" x2="1" y1="0" y2="1">
                <stop offset="0" stopColor="#b6a0ee" />
                <stop offset="1" stopColor="#e59a86" />
              </linearGradient>
            </defs>
            <path className="route-road-shadow" d={road.d} />
            <path className="route-road-surface" d={road.d} />
            <path id={`lane${id}`} className="route-road-lane" d={road.d} />
            {[0, -3.8].map((begin) => (
              <circle key={begin} className="route-traveler" r={begin ? 5 : 7} fill={`url(#orb${id})`}>
                <animateMotion begin={`${begin}s`} dur="7.6s" repeatCount="indefinite" rotate="auto">
                  <mpath href={`#lane${id}`} />
                </animateMotion>
              </circle>
            ))}
          </svg>
        )}
        <ol className="route-stops">
          {modules.map((m, i) => {
            const stages = Math.max(1, m.stage_count || fallbackStages || 1);
            return (
              <li key={m.module_id ?? i} className="route-stop">
                <span className="route-node">{fa(m.module_number ?? i + 1)}</span>
                <article className="route-card mat mat-raised">
                  <small>سرفصل {fa(m.module_number ?? i + 1)}</small>
                  <h3>{m.title}</h3>
                  <p>{fa(stages)} ایستگاه یادگیری و تمرین</p>
                  {m.learning_objectives?.length > 0 && (
                    <div className="route-tags">
                      {m.learning_objectives.slice(0, 2).map((o) => (
                        <span key={o}>{o}</span>
                      ))}
                    </div>
                  )}
                  <div className="route-dots" aria-label={`${fa(stages)} مرحله`}>
                    {Array.from({ length: Math.min(12, stages) }, (_, k) => (
                      <i key={k} />
                    ))}
                  </div>
                </article>
              </li>
            );
          })}
        </ol>
      </div>
      <div className="route-finish">
        <Flag /> {finishLabel}
      </div>
    </div>
  );
}

export function CourseOverview({ slug, preview = false }) {
  const { me, go, toast } = useStore();
  const detail = useCached(K.course(slug));
  const overview = useOverview(!preview);
  const enroll = useEnroll();
  const [starting, setStarting] = useState(false);
  const course = detail.data;
  if (detail.loading && !course) return <Skel lines={8} />;
  if (!course)
    return (
      <Panel>
        <Empty
          icon={<BookOpen />}
          title="این دوره در دسترس نیست"
          text="ممکن است غیرفعال شده باشد یا هنوز منتشر نشده باشد."
          action={
            <button className="btn btn-soft" onClick={() => go({ name: preview ? "admin-studio" : "courses" })}>
              {preview ? "برگشت به استودیو" : "برگشت به دوره‌ها"}
            </button>
          }
        />
      </Panel>
    );

  const joined = overview.data?.enrollments?.find((e) => e.course_id === course.id);
  const modules = course.modules.length
    ? course.modules
    : [{ module_number: 1, title: "آماده‌سازی مسیر", stage_count: course.module_stage_count || 8, learning_objectives: [] }];
  const moduleCount = course.module_count || course.modules.length;
  const perModule = course.module_stage_count || modules[0]?.stage_count || 8;
  const hours = hoursOf(course);
  const duration = course.estimated_duration_label || (hours ? `حدود ${fa(hours)} ساعت` : "منعطف، مرحله‌به‌مرحله");
  const exam = !!course.requires_final_exam;
  const finishLabel = exam ? "آزمون نهایی و گواهی" : "پایان مسیر";
  const after = [...course.learning_outcomes, ...course.career_outcomes, ...course.daily_life_outcomes].filter(Boolean).slice(0, 4);
  const outcomes = [
    [<Briefcase key="1" />, "peach", "در کار", course.career_outcomes],
    [<Heart key="2" />, "rose", "در زندگی روزمره", course.daily_life_outcomes],
    [<Lightbulb key="3" />, "lav", "در یادگیری", course.learning_outcomes],
  ].filter(([, , , items]) => items?.length);
  const cta = joined ? "ادامه‌ی مسیر" : "شروع مسیر";
  const start = async () => {
    if (preview) return toast("این پیش‌نمایش ادمین است؛ شروع دوره فقط برای یادگیرنده فعال است.", "info");
    if (starting) return;
    setStarting(true);
    try {
      await enroll(course.id);
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="stack ov">
      <button className="link-btn" onClick={() => go({ name: preview ? "admin-studio" : "courses" })} style={{ justifySelf: "start" }}>
        <ArrowLeft style={{ transform: "scaleX(-1)" }} /> {preview ? "برگشت به استودیو" : "همه‌ی دوره‌ها"}
      </button>
      {preview && <Callout tone="info">پیش‌نمایش صفحه‌ی معرفی، همان‌طور که یادگیرنده می‌بیند. دکمه‌های شروع اینجا کاری انجام نمی‌دهند.</Callout>}

      <section className="ov-hero" aria-labelledby="ov-title">
        <HeroScene />
        <div className="ov-hero-copy">
          <span className="ov-kicker">معرفی مسیر یادگیری زیتو</span>
          <h1 id="ov-title">{course.title}</h1>
          <p>{course.summary}</p>
          <div className="ov-facts" aria-label="مشخصات دوره">
            <div className="mat mat-raised">
              <small>سرفصل‌های مسیر</small>
              <b>
                <Layers /> {fa(moduleCount)} سرفصل کاربردی
              </b>
            </div>
            <div className="mat mat-raised">
              <small>ریتم هر سرفصل</small>
              <b>
                <Sparkles /> {fa(perModule)} ایستگاه یادگیری
              </b>
            </div>
            <div className="mat mat-raised">
              <small>زمان پیشنهادی</small>
              <b>
                <Clock /> {duration}
              </b>
            </div>
          </div>
          <div className="row" style={{ gap: ".6rem", marginTop: ".4rem" }}>
            <button className="btn btn-primary btn-lg" disabled={starting} onClick={start}>
              <Sparkles /> {cta}
            </button>
            <span className="meta-row">
              {course.level && (
                <span>
                  <Signal /> {course.level}
                </span>
              )}
              {course.target_group && <span>{course.target_group}</span>}
            </span>
          </div>
        </div>
        <div className="ov-hero-art" aria-hidden="true">
          <span className="ov-orbit" />
          <i className="ov-dot ov-dot-1" />
          <i className="ov-dot ov-dot-2" />
          <i className="ov-dot ov-dot-3" />
          <Mascot motion="course" height="15rem" label="زیتو در حال آماده‌سازی مسیر دوره" />
        </div>
      </section>

      <section aria-labelledby="ov-dest">
        <SectionHead
          id="ov-dest"
          kicker="مقصد این مسیر"
          title="آخر این مسیر قرار است کجا برسی؟"
          intro={course.description || "در این دوره، هر قدم کوچک به یک نتیجه‌ی قابل استفاده در زندگی و کار تو وصل می‌شود."}
        />
        <div className="ov-dest mat mat-panel">
          <article className="ov-ba ov-ba-before mat mat-raised">
            <span className="ov-ba-kicker">قبل از این دوره</span>
            <h3>انرژی داری، اما مسیر هنوز روشن نیست.</h3>
            <ul>
              {BEFORE.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </article>
          <div className="ov-dest-mid" aria-hidden="true">
            <MascotStill pose="phone" height="9.5rem" />
            <span className="badge badge-accent">قدم‌به‌قدم، نه یک‌باره</span>
          </div>
          <article className="ov-ba ov-ba-after mat mat-raised">
            <span className="ov-ba-kicker">بعد از این دوره</span>
            <h3>می‌دانی قدم بعدی چیست و چرا انجامش می‌دهی.</h3>
            <ul>
              {(after.length ? after : AFTER_FALLBACK).map((t) => (
                <li key={t}>
                  <Check /> {t}
                </li>
              ))}
            </ul>
          </article>
        </div>
        {outcomes.length > 1 && (
          <div className="outcomes" style={{ marginTop: ".9rem" }}>
            {outcomes.map(([icon, tone, title, items]) => (
              <div key={title} className="mat mat-raised" style={{ padding: "1rem" }}>
                <span className={`tile tile-${tone}`}>{icon}</span>
                <h3 style={{ marginTop: ".6rem" }}>{title}</h3>
                <ul>
                  {items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="ov-route">
        <SectionHead
          id="ov-route"
          kicker="نقشه و مسیر دوره"
          title={`از اولین قدم تا ${finishLabel}`}
          intro="هر سرفصل یک ایستگاه واقعی در مسیر است؛ با تمرین‌های کوتاه جلو می‌روی و پیشرفتت در تمام راه ذخیره می‌شود."
        />
        <RouteMap modules={modules} fallbackStages={perModule} finishLabel={finishLabel} durationLabel={duration} />
      </section>

      <section aria-labelledby="ov-impact">
        <SectionHead
          id="ov-impact"
          kicker="چیزی که همراهت می‌ماند"
          title="این دوره چه چیزی را برایت متفاوت می‌کند؟"
          intro="هدف فقط گذراندن محتوا نیست؛ می‌خواهیم چیزی بسازی که در روزهای بعد هم به کارت بیاید."
        />
        <div className="ov-impact">
          {IMPACT.map(([title, text], i) => (
            <article key={title} className={`mat mat-panel${i === 2 ? " has-mascot" : ""}`}>
              <span className="ov-num">{fa(`0${i + 1}`)}</span>
              <h3>{title}</h3>
              <p>{text}</p>
              {i === 2 && <MascotStill pose="phone" height="7.4rem" className="ov-impact-mascot" float={false} />}
            </article>
          ))}
        </div>
      </section>

      <section className="ov-cert mat mat-panel" aria-labelledby="ov-cert">
        <div className="ov-cert-card" aria-label="پیش‌نمایش گواهی پایان دوره زیتو">
          <Logo compact />
          <span>گواهی پایان دوره زیتو</span>
          <strong>{course.title}</strong>
          <small>{me?.display_name ? `به نام ${me.display_name} | ` : ""}{exam ? "پس از تکمیل مسیر و ارزیابی نهایی" : "پس از تکمیل تمام ایستگاه‌های مسیر"}</small>
          <Sprig className="ov-cert-sprig" flowers={7} />
        </div>
        <div className="ov-cert-copy">
          <span className="ov-kicker">پایان مسیر، یک خروجی قابل اتکا</span>
          <h2 id="ov-cert">گواهی دوره فقط یک تصویر نیست؛ نشانه‌ی مسیری است که واقعاً طی کرده‌ای.</h2>
          <p>{course.final_exam_label || (exam ? "پس از تکمیل سرفصل‌ها، آزمون نهایی و مسیر دریافت گواهی برایت فعال می‌شود." : "پس از تکمیل همه‌ی ایستگاه‌ها، خروجی نهایی مسیر برایت فعال می‌شود.")}</p>
          <ul className="ov-points">
            <li>
              <Check /> مسیر و پیشرفتت مرحله‌به‌مرحله ثبت می‌شود.
            </li>
            <li>
              <Award /> {exam ? "آزمون نهایی سه سؤال تشریحی دارد و حدنصاب قبولی ۷۰ است." : "پس از تکمیل همه‌ی ایستگاه‌ها، خروجی نهایی مسیر برایت فعال می‌شود."}
            </li>
            <li>
              <ShieldCheck /> گواهی شماره‌دار است و هر کسی بدون ورود می‌تواند استعلامش کند.
            </li>
          </ul>
        </div>
      </section>

      <section className="ov-finish mat mat-panel" aria-labelledby="ov-finish">
        <div className="ov-finish-art" aria-hidden="true">
          <span className="ov-portal" />
          <MascotStill pose="laptop" height="10.5rem" />
        </div>
        <div className="ov-finish-copy">
          <span className="ov-kicker">مسیر آماده است</span>
          <h2 id="ov-finish">شروع از یک قدم کوچک، ادامه تا یک تغییر واقعی.</h2>
          <p>پیشرفتت ذخیره می‌شود، هر زمان خواستی برمی‌گردی و در هر ایستگاه زیتو را کنار خودت داری.</p>
          <div className="ov-next mat mat-raised">
            <small>{joined ? "دوره‌ی تو" : "اولین ایستگاه"}</small>
            <b>{joined ? `${fa(joined.completed_stage_count)} از ${fa(joined.total_stage_count)} مرحله تمام شده` : modules[0]?.title}</b>
          </div>
          <button className="btn btn-primary btn-lg" disabled={starting} onClick={start}>
            {cta} <ArrowLeft />
          </button>
        </div>
      </section>
    </div>
  );
}
