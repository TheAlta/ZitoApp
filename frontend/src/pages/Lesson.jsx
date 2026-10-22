// Learning path: the current stage of the current course, its content blocks, quiz and personal example.
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Award, Check, ChevronDown, Compass, Lightbulb, Lock, MessageCircle, Play, RefreshCw, RotateCw, Sparkles, Trophy } from "lucide-react";
import { post } from "../lib/api.js";
import { setCached, useCached } from "../lib/cache.js";
import { fa, pct, shuffle } from "../lib/format.js";
import { K, pathInfo, refreshLearning, useCurrentPath } from "../lib/learner.js";
import { useStore } from "../lib/store.jsx";
import { CoachAvatar, Drop, Landscape, Logo } from "../ui/art.jsx";
import { AIBar, Bar, Callout, Empty, Panel, Skel, Sources } from "../ui/kit.jsx";

// ---- block normalisation: the CMS writes {body, items}, older content may use other keys ----

const textOf = (value) => (value == null ? "" : typeof value === "string" ? value : String(value.body ?? value.text ?? value.title ?? ""));

// "عنوان: توضیح" -> {title, text}; objects keep their own fields.
function split(item) {
  if (item && typeof item === "object") return { title: textOf(item.title ?? item.name ?? ""), text: textOf(item.body ?? item.text ?? item.description ?? "") };
  const s = String(item ?? "");
  const m = s.match(/^([^:：\n]{2,70})[:：]\s+([\s\S]+)$/);
  return m ? { title: m[1].trim(), text: m[2].trim() } : { title: "", text: s };
}

const list = (value) => (Array.isArray(value) ? value.filter((x) => x !== null && x !== undefined && x !== "") : []);

export const SCOPE_LABELS = { module: "همین سرفصل", course: "معرفی دوره", stage: "متن همین مرحله", general: "بخش عمومی دوره" };
export const citationsToSources = (citations) =>
  list(citations).map((c, i) => ({ n: c.source_number ?? i + 1, title: c.title, scope: SCOPE_LABELS[c.scope] ?? c.scope }));

function Title({ b }) {
  return b.title ? <h3>{b.title}</h3> : null;
}

export function Block({ b, uid }) {
  const kind = b.kind || "paragraph";
  const body = textOf(b.body ?? b.text);
  const items = list(b.items);
  switch (kind) {
    case "paragraph":
    case "explanation":
      return (
        <section className="blk">
          <Title b={b} />
          <p>{body}</p>
        </section>
      );
    case "highlight":
    case "worked_example":
      return (
        <section className="blk blk-hl">
          {b.title ? <h3>{b.title}</h3> : <h3>{kind === "worked_example" ? "مثال حل‌شده" : "نکته"}</h3>}
          <p>{body}</p>
        </section>
      );
    case "framework": {
      const lines = items.length ? items.map(split) : body.split("\n").filter(Boolean).map((line) => split(line.replace(/^\d+\.\s*/, "")));
      return (
        <section className="blk">
          <Title b={b} />
          <div className="grid2">
            {lines.map((line, i) => (
              <div key={i} className="mini mat mat-raised">
                <span className="n">{fa(String(i + 1).padStart(2, "0"))}</span>
                {line.title && <b>{line.title}</b>}
                <p>{line.text}</p>
              </div>
            ))}
          </div>
        </section>
      );
    }
    case "bullets":
    case "concepts":
      return (
        <section className="blk">
          <Title b={b} />
          {body && <p style={{ marginBlockEnd: ".6rem" }}>{body}</p>}
          <div className="grid2">
            {items.map((item, i) => {
              const it = split(item);
              return (
                <div key={i} className="mini mat mat-raised">
                  {it.title ? (
                    <>
                      <b>{it.title}</b>
                      <p>{it.text}</p>
                    </>
                  ) : (
                    it.text
                  )}
                </div>
              );
            })}
          </div>
        </section>
      );
    case "steps":
    case "cards":
      return (
        <section className="blk">
          <Title b={b} />
          {body && <p style={{ marginBlockEnd: ".6rem" }}>{body}</p>}
          <div className={items.length === 3 ? "grid3" : "grid2"}>
            {items.map((item, i) => {
              const it = split(item);
              return (
                <div key={i} className="mini mat mat-raised">
                  {kind === "steps" && <span className="n">قدم {fa(i + 1)}</span>}
                  {it.title && <b>{it.title}</b>}
                  <p>{it.text}</p>
                </div>
              );
            })}
          </div>
        </section>
      );
    case "timeline":
      return (
        <section className="blk">
          <Title b={b} />
          {body && <p style={{ marginBlockEnd: ".6rem" }}>{body}</p>}
          <div className="timeline">
            {items.map((item, i) => {
              const it = split(item);
              return (
                <div key={i} className="tl-item">
                  <span className="tl-dot">{fa(i + 1)}</span>
                  <b>{it.title || it.text}</b>
                  {it.title && <small>{it.text}</small>}
                </div>
              );
            })}
          </div>
        </section>
      );
    case "tips":
      return (
        <section className="blk stack" style={{ gap: ".6rem" }}>
          <Title b={b} />
          {items.map((item, i) => {
            const it = split(item);
            return (
              <div key={i} className="tip mat mat-raised" style={{ animationDelay: `${i * 180}ms` }}>
                <span className="tip-n">{fa(String(i + 1).padStart(2, "0"))}</span>
                <div>
                  {it.title && <b>{it.title}</b>}
                  <p>{it.text}</p>
                </div>
              </div>
            );
          })}
        </section>
      );
    case "mistakes":
      return (
        <section className="blk stack" style={{ gap: ".6rem" }}>
          <Title b={b} />
          {items.map((item, i) => (
            <div key={i} className="mistake mat mat-raised">
              <div>
                <small>اشتباه</small>
                {textOf(item.mistake ?? item.title ?? item)}
              </div>
              <div>
                <small>راه اصلاح</small>
                {textOf(item.correction ?? item.fix ?? item.body ?? "")}
              </div>
            </div>
          ))}
        </section>
      );
    case "flashcards":
      return <Flashcards title={b.title} items={items.filter((x) => x && typeof x === "object").map((x) => ({ front: textOf(x.front), back: textOf(x.back) }))} />;
    case "qa":
      return (
        <section className="blk accordion">
          <Title b={b} />
          {items.map((item, i) => (
            <Acc key={i} head={textOf(item.question ?? item.q)} open={i === 0}>
              {textOf(item.answer ?? item.a)}
            </Acc>
          ))}
        </section>
      );
    case "checklist":
      return <Checklist title={b.title} items={items.map(textOf)} />;
    case "scenario":
      return <Scenario title={b.title} text={body} options={list(b.options).map(textOf)} uid={uid} />;
    case "dialog": {
      const lines = list(b.lines).length ? b.lines : items;
      return (
        <section className="blk stack" style={{ gap: ".5rem" }}>
          <Title b={b} />
          {lines.map((line, i) => (
            <div key={i} className={`msg ${i % 2 ? "msg-user" : "msg-coach"}`}>
              <div className={`bubble ${i % 2 ? "" : "mat mat-raised"}`}>
                <b style={{ fontSize: "var(--t-micro)" }}>{textOf(line.speaker ?? line.who)}</b>
                {textOf(line.body ?? line.text)}
              </div>
            </div>
          ))}
        </section>
      );
    }
    case "mind_map":
      return (
        <section className="blk">
          <Title b={b} />
          <div className="mini mat mat-raised" style={{ textAlign: "center" }}>
            <b>{b.center || "موضوع مرکزی"}</b>
          </div>
          <ul style={{ marginTop: ".5rem" }}>
            {items.map((item, i) => (
              <li key={i}>{textOf(item)}</li>
            ))}
          </ul>
        </section>
      );
    case "image":
      return <LessonImage b={b} />;
    case "video":
      return <LessonVideo b={b} />;
    case "quiz":
    case "personalized_example":
      return null;
    default:
      return body ? (
        <section className="blk">
          <Title b={b} />
          <p>{body}</p>
        </section>
      ) : null;
  }
}

function Acc({ head, children, open: initial = false }) {
  const [open, setOpen] = useState(initial);
  return (
    <div className="acc">
      <button aria-expanded={open} onClick={() => setOpen(!open)}>
        <span>{head}</span>
        <ChevronDown />
      </button>
      {open && <div className="acc-body">{children}</div>}
    </div>
  );
}

function Flashcards({ title, items }) {
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  if (!items.length)
    return (
      <section className="blk">
        {title && <h3>{title}</h3>}
        <p className="muted">کارت‌های این بخش هنوز در دسترس نیستند.</p>
      </section>
    );
  const left = items.length - index;
  const next = () => {
    setFlipped(false);
    setTimeout(() => setIndex((i) => (i + 1) % items.length), flipped ? 210 : 0);
  };
  const card = items[index];
  return (
    <section className="blk">
      {title && <h3>{title}</h3>}
      <div className="deck">
        {Array.from({ length: Math.min(6, left - 1) }, (_, i) => (
          <div
            key={i}
            className="deck-layer"
            style={{ transform: `translate(${-(i + 1) * 6}px, ${(i + 1) * 7}px) rotate(${-(i + 1) * 1.6}deg)`, zIndex: -i - 1, opacity: 1 - i * 0.12 }}
          />
        ))}
        <div
          key={index}
          className="card3d deal"
          data-flip={flipped || undefined}
          onClick={() => setFlipped(!flipped)}
          role="button"
          tabIndex={0}
          aria-label={flipped ? "پشت کارت" : "روی کارت؛ برای دیدن جواب کلیک کن"}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setFlipped(!flipped))}
        >
          <div className="card-face">
            <span className="card-logo">
              <Logo compact />
            </span>
            <small>
              کارت {fa(index + 1)} از {fa(items.length)}
            </small>
            <b>{card.front}</b>
            <small>برای دیدن جواب، کارت را برگردان</small>
          </div>
          <div className="card-face back">
            <small>جواب</small>
            <b>{card.back}</b>
          </div>
        </div>
      </div>
      <div className="deck-ctrl">
        <button className="btn btn-soft btn-sm" onClick={() => setFlipped(!flipped)}>
          <RotateCw /> برگرداندن
        </button>
        <button className="btn btn-primary btn-sm" onClick={next}>
          {index === items.length - 1 ? "از اول" : "کارت بعدی"}
        </button>
      </div>
      <div style={{ maxWidth: "18rem", margin: ".8rem auto 0" }}>
        <Bar value={((index + 1) / items.length) * 100} label="کارت‌های مرورشده" />
      </div>
    </section>
  );
}

function Checklist({ title, items }) {
  const [checked, setChecked] = useState({});
  return (
    <section className="blk">
      {title && <h3>{title}</h3>}
      <div className="mat mat-raised" style={{ padding: ".3rem" }}>
        {items.map((item, i) => (
          <button key={i} role="checkbox" aria-checked={!!checked[i]} className="check-row" onClick={() => setChecked({ ...checked, [i]: !checked[i] })}>
            <span className="check-box">{checked[i] && <Check />}</span>
            <span>{item}</span>
          </button>
        ))}
      </div>
      <p className="muted" style={{ fontSize: "var(--t-micro)", marginTop: ".4rem" }}>
        تیک‌ها فقط برای همین صفحه است و ذخیره نمی‌شود.
      </p>
    </section>
  );
}

function Scenario({ title, text, options, uid }) {
  const [picked, setPicked] = useState(null);
  const shuffled = useMemo(() => shuffle(options, uid, text), [options, uid, text]);
  return (
    <section className="blk blk-hl">
      <h3>
        <Lightbulb size={16} /> {title || "موقعیت"}
      </h3>
      <p>{text}</p>
      <div className="opts" role="radiogroup" style={{ marginTop: ".6rem" }}>
        {shuffled.map((option) => (
          <button key={option} role="radio" aria-checked={picked === option} className="opt" onClick={() => setPicked(option)}>
            {option}
          </button>
        ))}
      </div>
    </section>
  );
}

function LessonImage({ b }) {
  const src = /^\/api\/course-images\/\d+$/.test(b.src || "") ? b.src : "";
  if (!src) return null;
  const caption = b.caption || b.title;
  return (
    <figure className="lesson-img" style={{ margin: 0 }}>
      <img src={src} alt={b.alt || caption || "عکس آموزشی درس"} loading="lazy" />
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  );
}

const MEDIA = /^\/landing-static\/course-media\/[a-z0-9][a-z0-9._-]*\.(mp4|jpg|png|webp)$/i;
const mmss = (s) => `${fa(String(Math.floor(s / 60)).padStart(2, "0"))}:${fa(String(Math.floor(s % 60)).padStart(2, "0"))}`;

// The demo's glass player frame around a real <video>: poster + play button, then native controls.
function LessonVideo({ b }) {
  const src = MEDIA.test(b.src || "") && /\.mp4$/i.test(b.src) ? b.src : "";
  const poster = MEDIA.test(b.poster || "") && !/\.mp4$/i.test(b.poster) ? b.poster : undefined;
  const [started, setStarted] = useState(false);
  const [time, setTime] = useState({ now: 0, total: 0 });
  const video = useRef(null);
  if (!src) return null;
  return (
    <section className="blk">
      {b.title && <h3>{b.title}</h3>}
      <div className="video mat mat-raised">
        {!started && (poster ? <img src={poster} alt="" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} /> : <Landscape hue={262} seed={5} />)}
        <video
          ref={video}
          src={src}
          poster={poster}
          controls={started}
          playsInline
          preload="metadata"
          controlsList="nodownload"
          aria-label={b.title || "ویدیوی آموزشی"}
          onLoadedMetadata={(e) => setTime((t) => ({ ...t, total: e.currentTarget.duration || 0 }))}
          onTimeUpdate={(e) => setTime({ now: e.currentTarget.currentTime, total: e.currentTarget.duration || 0 })}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain", background: started ? "#1d1830" : "transparent", opacity: started ? 1 : 0 }}
        />
        {!started && (
          <>
            <button
              className="video-play"
              onClick={() => {
                setStarted(true);
                video.current?.play().catch(() => {});
              }}
              aria-label="پخش ویدیو"
            >
              <span>
                <Play />
              </span>
              {b.caption && <small>{b.caption}</small>}
            </button>
            {time.total > 0 && (
              <div className="video-bar">
                <div className="row" style={{ fontSize: "var(--t-micro)", justifyContent: "space-between" }}>
                  <span className="ltr">{mmss(time.now)}</span>
                  <span className="ltr">{mmss(time.total)}</span>
                </div>
                <Bar value={(time.now / time.total) * 100} label="پیشرفت ویدیو" />
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

function StageGlyph({ kind }) {
  const shape = ["learning_path", "golden_tips", "module_assessment"].includes(kind)
    ? "tri"
    : ["lesson_summary", "common_mistakes", "module_completion"].includes(kind)
      ? "circle"
      : "square";
  return (
    <svg className="stage-glyph" viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <linearGradient id={`g-${kind}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.95" />
          <stop offset="0.5" stopColor="#d9cbf8" stopOpacity="0.6" />
          <stop offset="1" stopColor="#f6cdbd" stopOpacity="0.8" />
        </linearGradient>
      </defs>
      {shape === "tri" && <path d="M50 10 L90 82 L10 82Z" fill={`url(#g-${kind})`} stroke="#fff" strokeWidth="2" />}
      {shape === "circle" && <circle cx="50" cy="50" r="38" fill={`url(#g-${kind})`} stroke="#fff" strokeWidth="2" />}
      {shape === "square" && <rect x="16" y="16" width="68" height="68" rx="16" fill={`url(#g-${kind})`} stroke="#fff" strokeWidth="2" transform="rotate(12 50 50)" />}
      <circle cx="68" cy="30" r="5" fill="#fff" opacity="0.9" />
    </svg>
  );
}

// ---- stage completion -------------------------------------------------------------------------

function completionMessage(result) {
  const path = result.path;
  if (result.course_completed && !path?.final_exam_required) return "دوره تمام شد و گواهی صادر شد.";
  if (path?.final_exam_available || path?.status === "awaiting_final_exam") return "همه‌ی سرفصل‌ها تمام شد. آزمون نهایی باز است.";
  const next = path?.stages?.find((s) => s.stage_number === result.next_stage_number);
  const done = path?.stages?.find((s) => s.stage_number === result.completed_stage_number);
  if (next && done && next.module_id !== done.module_id) return `سرفصل ${fa(done.module_number)} تمام شد؛ سرفصل ${fa(next.module_number)} باز شد.`;
  if (next?.module_stage_number) return `مرحله ثبت شد؛ قدم ${fa(next.module_stage_number)} باز شد.`;
  return "مرحله ثبت شد.";
}

function useCompleteStage(path) {
  const { toast } = useStore();
  const [busy, setBusy] = useState(false);
  const complete = async (stageNumber, response) => {
    if (busy) return null;
    setBusy(true);
    try {
      const result = await post(`/api/learning/enrollments/${path.enrollment_id}/stages/${stageNumber}/complete`, { response: response ?? null });
      if (result.path) setCached(K.path, result.path);
      if (result.stage_completed !== false) {
        refreshLearning(path.enrollment_id);
        toast(completionMessage(result));
        try {
          document.querySelector(".app-main")?.scrollTo({ top: 0, behavior: "smooth" });
          window.scrollTo({ top: 0, behavior: "smooth" });
        } catch {
          /* cosmetic */
        }
      }
      return result;
    } catch (error) {
      toast(error.message, "err");
      return null;
    } finally {
      setBusy(false);
    }
  };
  return { complete, busy };
}

// ---- page ---------------------------------------------------------------------------------------

export function Lesson() {
  const { go, me } = useStore();
  const path = useCurrentPath();
  const info = pathInfo(path.data);
  const stageKey = info?.status === "learning" ? K.stage(path.data.enrollment_id) : null;
  const stage = useCached(stageKey);
  const { complete, busy } = useCompleteStage(path.data || {});

  if (path.loading && !path.data) return <Skel lines={8} />;
  if (!path.data)
    return (
      <Panel>
        <Empty
          icon={<Compass />}
          title="هنوز دوره‌ای انتخاب نکرده‌ای"
          text="یک دوره انتخاب کن تا مسیر یادگیری‌ات شروع شود."
          action={
            <button className="btn btn-primary" onClick={() => go({ name: "courses" })}>
              دیدن دوره‌ها
            </button>
          }
        />
      </Panel>
    );

  const p = path.data;
  const finished = info.status !== "learning";
  const s = stage.data;
  const current = s && s.stage_number === info.current?.stage_number ? s : null;
  const kind = current?.stage_type;
  const isQuiz = kind === "module_assessment";
  const content = current?.content || {};
  const blocks = list(content.blocks);
  const activity = typeof content.activity === "string" ? { prompt: content.activity } : content.activity;
  const coachHint = current?.coaching?.enabled && current.coaching.prompt;

  return (
    <div className="lesson">
      <div className="lesson-main">
        {finished ? (
          <CourseDone path={p} info={info} />
        ) : !current ? (
          stage.error ? (
            <Panel>
              <Callout tone="err" title="این مرحله باز نشد">
                {stage.error.message}{" "}
                <button className="btn btn-sm btn-soft" onClick={() => stage.reload()}>
                  <RefreshCw /> تلاش دوباره
                </button>
              </Callout>
            </Panel>
          ) : (
            <Skel lines={8} />
          )
        ) : (
          <>
            <section key={current.stage_number} className="stage-head mat mat-panel" style={{ animation: "rise .34s var(--ease)" }}>
              <div className="crumb">
                <span>
                  سرفصل {fa(info.moduleIndex + 1)} از {fa(info.moduleCount)} | قدم {fa(info.stageIndex + 1)} از {fa(info.moduleStages.length || current.module_stage_count || 8)}
                </span>
                <span className="badge badge-accent">{pct(info.percent)} از دوره</span>
              </div>
              <h1>{current.title}</h1>
              <span className="soft" style={{ fontSize: "var(--t-small)" }}>
                {current.module_title || info.module?.title}
              </span>
              <div className="stage-rail" aria-label="مراحل این سرفصل">
                {info.moduleStages.map((st, i) => (
                  <i key={st.stage_number} data-s={i < info.stageIndex ? "done" : i === info.stageIndex ? "now" : "lock"} title={st.title} />
                ))}
              </div>
              <StageGlyph kind={kind} />
            </section>
            {content.intro && (
              <Panel>
                <div className="focus">
                  <span className="tile tile-lav">
                    <Sparkles />
                  </span>
                  <div>
                    <div className="row" style={{ marginBlockEnd: ".2rem" }}>
                      <h3>تمرکز این مرحله</h3>
                      <span className="badge badge-quiet">در مسیر تو</span>
                    </div>
                    <p>{content.intro}</p>
                  </div>
                </div>
              </Panel>
            )}
            <Panel>
              <div className="blocks">
                {kind === "personalized_work_example" && <PersonalExample path={p} stage={current} />}
                {blocks.map((b, i) => (
                  <Block key={`${current.stage_number}-${i}`} b={b} uid={me?.id} />
                ))}
                {isQuiz && <Quiz path={p} stage={current} blocks={blocks} complete={complete} busy={busy} />}
              </div>
            </Panel>
            {activity?.prompt && (
              <Panel>
                <div className="focus">
                  <span className="tile tile-peach">
                    <Check />
                  </span>
                  <div>
                    <h3>{activity.title || "قدم عملی"}</h3>
                    <p>{activity.prompt}</p>
                  </div>
                </div>
              </Panel>
            )}
            {!isQuiz && (
              <div className="stage-foot mat mat-panel">
                <div className="grow">
                  <span>
                    پیشرفت کل مسیر | {fa(info.completed)} از {fa(info.total)} مرحله
                  </span>
                  <Bar value={info.percent} label="پیشرفت کل مسیر" />
                </div>
                <button className="btn btn-primary btn-lg" disabled={busy} onClick={() => complete(current.stage_number, null)}>
                  {busy ? "در حال ثبت…" : "تکمیل مرحله و ادامه"} <ArrowLeft />
                </button>
              </div>
            )}
          </>
        )}
      </div>
      <aside className="lesson-aside">
        <Panel title={p.course_title} className="mod-panel">
          <div className="row" style={{ fontSize: "var(--t-micro)", marginBlockEnd: ".4rem" }}>
            <span className="soft">
              {fa(info.completed)} از {fa(info.total)}
            </span>
          </div>
          <Bar value={info.percent} label="پیشرفت دوره" />
          <div className="mod-list" style={{ marginTop: ".8rem" }}>
            {(p.modules || []).map((m, i) => {
              const state = finished || m.status === "completed" ? "done" : m.is_current || i === info.moduleIndex ? "now" : "lock";
              return (
                <div key={m.module_id} className="mod" data-s={state}>
                  <span className="mod-ic">{state === "done" ? <Check /> : state === "lock" ? <Lock /> : fa(i + 1)}</span>
                  <span>{m.title}</span>
                </div>
              );
            })}
          </div>
          <button className="link-btn" style={{ marginTop: ".6rem" }} onClick={() => go({ name: "courses" })}>
            بازگشت به دوره‌ها
          </button>
        </Panel>
        <Panel>
          <div className="coach-card">
            <CoachAvatar size="3rem" />
            <p>{coachHint || "سؤالی داری؟ با زیتو بررسیش کن."}</p>
          </div>
          <button className="btn btn-soft btn-block" style={{ marginTop: ".7rem" }} onClick={() => go({ name: "coach" })}>
            <MessageCircle /> گفت‌وگو با زیتو
          </button>
        </Panel>
      </aside>
    </div>
  );
}

function CourseDone({ path, info }) {
  const { go } = useStore();
  const exam = useCached(info.status === "completed" ? K.final(path.enrollment_id) : null);
  const certificate = exam.data?.certificate;
  return (
    <Panel>
      <div className="empty">
        <Drop size="6rem" face />
        <h2>{info.status === "completed" ? "این دوره را تمام کرده‌ای" : "همه‌ی سرفصل‌ها تمام شد"}</h2>
        <p>
          {info.status === "completed"
            ? certificate
              ? `گواهی «${path.course_title}» صادر شده و قابل استعلام است.`
              : `دوره‌ی «${path.course_title}» را کامل کرده‌ای.`
            : "حالا نوبت آزمون نهایی است: سه سؤال تشریحی با حدنصاب ۷۰."}
        </p>
        {info.status === "completed" ? (
          certificate ? (
            <button className="btn btn-primary" onClick={() => go({ name: "certificate", id: certificate.certificate_number })}>
              <Award /> مشاهده مدرک
            </button>
          ) : (
            <button className="btn btn-primary" onClick={() => go({ name: "courses" })}>
              <Compass /> دوره‌ی بعدی
            </button>
          )
        ) : (
          <button className="btn btn-primary btn-lg" onClick={() => go({ name: "final" })}>
            <Trophy /> شروع آزمون نهایی
          </button>
        )}
      </div>
    </Panel>
  );
}

function Quiz({ stage, blocks, complete, busy }) {
  const quiz = blocks.find((b) => b.kind === "quiz");
  const questions = useMemo(
    () =>
      list(quiz?.items ?? quiz?.questions).map((q, i) => ({
        id: String(q.id ?? `q${i + 1}`),
        text: textOf(q.question ?? q.text),
        options: list(q.options).map(textOf),
      })),
    [quiz],
  );
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const previous = stage.assessment;
  const passScore = previous?.pass_score ?? 60;
  const answered = Object.keys(answers).length;

  useEffect(() => {
    setAnswers({});
    setResult(null);
  }, [stage.stage_number]);

  if (!questions.length) return <Callout tone="warn">سؤال‌های این آزمونک هنوز آماده نیست.</Callout>;

  const submit = async () => {
    const response = await complete(stage.stage_number, { answers, selected_items: Object.values(answers) });
    if (!response) return;
    if (response.stage_completed === false) {
      setResult(response.assessment);
      setAnswers({});
    }
  };

  return (
    <div className="stack">
      {result && !result.passed && (
        <Callout tone="warn" title={`نتیجه آزمونک: ${fa(result.score ?? 0)} از ۱۰۰ | حداقل نمره ${fa(result.pass_score ?? passScore)}`}>
          {result.feedback || "هنوز به حدنصاب نرسیدی. خلاصه‌ی درس و اشتباهات رایج را یک بار دیگر مرور کن و دوباره امتحان بده؛ محدودیتی در تعداد تلاش نیست."} (تلاش {fa(result.attempt_count)})
        </Callout>
      )}
      {!result && previous?.attempt_count > 0 && (
        <p className="muted" style={{ fontSize: "var(--t-micro)" }}>
          تلاش‌های قبلی: {fa(previous.attempt_count)}
          {previous.score != null && ` | آخرین نمره ${fa(previous.score)}`}
        </p>
      )}
      {questions.map((q, i) => (
        <div key={q.id} className="quiz-q mat mat-raised">
          <span className="muted" style={{ fontSize: "var(--t-micro)" }}>
            سؤال {fa(i + 1)}
          </span>
          <b>{q.text}</b>
          <div className="opts" role="radiogroup" aria-label={q.text}>
            {q.options.map((option) => (
              <button key={option} role="radio" aria-checked={answers[q.id] === option} className="opt" onClick={() => setAnswers({ ...answers, [q.id]: option })}>
                {option}
              </button>
            ))}
          </div>
        </div>
      ))}
      <div className="stage-foot mat mat-panel">
        <div className="grow">
          <span>
            {fa(answered)} از {fa(questions.length)} سؤال پاسخ داده شده
          </span>
          <Bar value={(answered / questions.length) * 100} label="پاسخ‌ها" />
        </div>
        <button className="btn btn-primary btn-lg" disabled={busy || answered < questions.length} onClick={submit}>
          {busy ? "در حال ثبت…" : "ثبت آزمونک و ادامه"} <ArrowLeft />
        </button>
      </div>
      <p className="formula">
        نمره = پاسخ‌های درست ÷ کل سؤال‌ها × ۱۰۰ | حدنصاب {fa(passScore)} | کلید پاسخ فقط روی سرور است و کدام سؤال غلط بوده نشان داده نمی‌شود.
      </p>
    </div>
  );
}

function PersonalExample({ path, stage }) {
  const [state, setState] = useState({ status: "processing" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    const started = Date.now();
    setState({ status: "processing" });
    post(`/api/learning/enrollments/${path.enrollment_id}/stages/${stage.stage_number}/personalized-example`)
      .then((result) => alive && setState({ status: "ready", result, ms: Date.now() - started, at: Date.now() }))
      .catch((error) => alive && setState({ status: "error", error, ms: Date.now() - started, at: Date.now() }));
    return () => {
      alive = false;
    };
  }, [path.enrollment_id, stage.stage_number, attempt]);

  if (state.status === "processing")
    return (
      <div className="stack">
        <AIBar meta={{ status: "processing", expect: "۳۰ تا ۴۵ ثانیه" }} />
        <div className="row">
          <CoachAvatar size="2.6rem" busy />
          <span className="soft" style={{ fontSize: "var(--t-small)" }}>
            زیتو بخش‌های مرتبط درس را با پروفایلت می‌خواند و مثال می‌سازد…
          </span>
        </div>
        <Skel lines={5} />
      </div>
    );

  if (state.status === "error")
    return (
      <div className="example">
        <AIBar meta={{ status: "review", ms: state.ms, at: state.at }} />
        <Callout tone="warn" title="مثال شخصی آماده نشد">
          مثال مخصوص تو فعلاً ساخته نشد؛ می‌توانی دوباره امتحان کنی یا از زیتو درباره‌ی همین مرحله سؤال بپرسی.{" "}
          <button className="btn btn-sm btn-soft" onClick={() => setAttempt((n) => n + 1)}>
            <RefreshCw /> تلاش دوباره
          </button>
        </Callout>
      </div>
    );

  const content = state.result.content || {};
  const steps = list(content.application_steps ?? content.steps).map(textOf);
  const sources = citationsToSources(state.result.citations);
  const fallback = !state.result.grounded;
  return (
    <div className="example">
      <AIBar meta={{ status: fallback ? "review" : "ready", ms: state.result.cached ? undefined : state.ms, at: state.at }} sources={sources.length} />
      {fallback && (
        <Callout tone="warn" title="نیاز به بررسی">
          این مثال بدون منبع تأییدشده ساخته شد؛ آن را یک نمونه‌ی عمومی در نظر بگیر.
        </Callout>
      )}
      <h3>{content.title || "مثال کاربردی"}</h3>
      <p style={{ lineHeight: 2.05 }}>{content.scenario || "مثال شخصی‌سازی‌شده فعلاً در دسترس نیست."}</p>
      {steps.length > 0 && (
        <ol>
          {steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      )}
      {(content.reflection_question || content.reflection) && (
        <div className="reflect">
          <b>پرسش تأملی: </b>
          {content.reflection_question || content.reflection}
        </div>
      )}
      <Sources sources={sources} />
    </div>
  );
}
