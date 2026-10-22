// Coaching station: course-grounded chat with sources, plus the context the coach uses.
import { useEffect, useRef, useState } from "react";
import { BookOpen, ChevronDown, Compass, Footprints, Info, Layers, ListChecks, Paperclip, History, Send } from "lucide-react";
import { post } from "../lib/api.js";
import { useCached } from "../lib/cache.js";
import { clock, fa } from "../lib/format.js";
import { K, pathInfo, useCurrentPath } from "../lib/learner.js";
import { useStore } from "../lib/store.jsx";
import { CoachAvatar } from "../ui/art.jsx";
import { AIBar, Callout, Empty, Form, Panel, Skel, Sources } from "../ui/kit.jsx";
import { citationsToSources } from "./Lesson.jsx";

const COACH_MODES = {
  grounded: ["جواب مستند", "badge-ok"],
  out_of_scope: ["بیرون از حوزه‌ی درس", "badge-warn"],
  stage_text: ["منبع: متن همین مرحله", "badge-info"],
  model_error: ["خطای مدل", "badge-err"],
  no_source: ["بدون منبع", "badge-quiet"],
};
const MODE_OF = { ok: "grounded", stage_fallback: "stage_text", out_of_scope: "out_of_scope", no_grounding: "no_source", fallback: "model_error" };

function fromServer(message) {
  return message.role === "user"
    ? { id: message.id, role: "user", text: message.content, at: message.created_at }
    : {
        id: message.id,
        role: "coach",
        text: message.content,
        at: message.created_at,
        mode: MODE_OF[message.answer_status] ?? (message.grounded === false ? "no_source" : "grounded"),
        sources: citationsToSources(message.citations),
        nextStep: message.suggested_action,
      };
}

export function Coach() {
  const { me, profile, go, toast } = useStore();
  const path = useCurrentPath();
  const info = pathInfo(path.data);
  const enrollmentId = path.data?.enrollment_id;
  const history = useCached(enrollmentId ? K.coach(enrollmentId) : null);
  const stage = useCached(info?.status === "learning" ? K.stage(enrollmentId) : null);
  const course = useCached(path.data ? K.course(path.data.course_slug) : null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(null);
  const [open, setOpen] = useState("stage");
  const [timings, setTimings] = useState({});
  const scroller = useRef(null);
  const messages = (history.data?.messages || []).map((m) => ({ ...fromServer(m), meta: timings[m.id] }));
  const shown = pending ? [...messages, ...pending] : messages;
  const visible = shown.slice(-12);

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [visible.length, pending]);

  if (path.loading && !path.data) return <Skel lines={8} />;
  if (!path.data || !me)
    return (
      <Panel>
        <Empty
          icon={<Compass />}
          title="کوچ داخل دوره کار می‌کند"
          text="زیتو فقط از روی محتوای دوره‌ای که می‌خوانی جواب می‌دهد. اول یک دوره شروع کن."
          action={
            <button className="btn btn-primary" onClick={() => go({ name: "courses" })}>
              دیدن دوره‌ها
            </button>
          }
        />
      </Panel>
    );

  const currentStage = stage.data;
  const stageTitle = currentStage?.title || info.current?.title;
  const module = course.data?.modules?.find((m) => m.module_id === info.module?.module_id);
  const objectives = module?.learning_objectives || [];
  const busy = !!pending;
  const firstName = me.display_name.split(" ")[0];

  const ask = async (text = draft) => {
    const question = text.trim();
    if (!question || busy) return;
    const started = Date.now();
    const userMsg = { id: `u${started}`, role: "user", text: question, at: new Date().toISOString() };
    setPending([userMsg, { id: `p${started}`, role: "coach", processing: true }]);
    setDraft("");
    try {
      const reply = await post(K.coach(enrollmentId), { message: question, stage_number: info.current?.stage_number ?? null });
      const coachMsg = {
        id: `c${started}`,
        role: "coach",
        text: reply.answer,
        at: reply.created_at || new Date().toISOString(),
        mode: MODE_OF[reply.answer_status] ?? (reply.grounded ? "grounded" : "no_source"),
        sources: citationsToSources(reply.citations),
        nextStep: reply.suggested_action,
        meta: { status: reply.grounded ? "ready" : "review", ms: Date.now() - started, at: Date.now() },
      };
      setPending([userMsg, coachMsg]);
      // Swap the optimistic pair for the saved history, keeping the fresh answer's timing strip.
      history
        .reload()
        .then((data) => {
          const last = data?.messages?.[data.messages.length - 1];
          if (last?.role === "assistant") setTimings((t) => ({ ...t, [last.id]: coachMsg.meta }));
          setPending(null);
        })
        .catch(() => {});
    } catch (error) {
      setPending(null);
      setDraft(question);
      toast(error.message, "err");
    }
  };

  const suggestions = [
    objectives[0] ? `«${objectives[0]}» را در کار من چطور انجام دهم؟` : `«${stageTitle}» را با یک مثال از کار من توضیح بده.`,
    `مهم‌ترین اشتباه در «${info.module?.title}» چیست؟`,
    "این مرحله را در سه جمله‌ی ساده خلاصه کن.",
  ];

  return (
    <div className="coach-page">
      <section className="coach mat mat-panel" aria-label="ایستگاه کوچینگ زیتو">
        <header className="coach-head">
          <CoachAvatar size="2.4rem" busy={busy && pending?.[1]?.processing} />
          <div>
            <h2>ایستگاه کوچینگ زیتو</h2>
            <span className="online">{busy && pending?.[1]?.processing ? "در حال یافتن منابع تأییدشده…" : "آنلاین"}</span>
          </div>
          <div className="ctx">
            {stageTitle && (
              <span className="badge badge-quiet hide-sm">
                <Layers /> سرفصل {fa(info.moduleIndex + 1)} | {stageTitle}
              </span>
            )}
            <button className="icon-btn" aria-label="تاریخچه" title={`${fa(messages.length)} پیام ذخیره‌شده؛ ۱۲ پیام آخر نمایش داده می‌شود`}>
              <History />
            </button>
          </div>
        </header>
        <div className="msgs" aria-live="polite" ref={scroller}>
          <div className="msg msg-coach">
            <CoachAvatar size="2.2rem" />
            <div className="bubble mat mat-raised">
              <span>سلام {firstName} 👋</span>
              <span>چطور کمکت کنم؟ از من می‌توانی بخواهی:</span>
              <ul>
                <li>یک مفهوم درس را ساده‌تر توضیح بدهم</li>
                <li>نکته‌ی درس را روی کار خودت پیاده کنم</li>
                <li>جوابت به یک موقعیت را بررسی کنم</li>
              </ul>
              <span className="muted" style={{ fontSize: "var(--t-micro)" }}>
                فقط از محتوای تأییدشده‌ی «{path.data.course_title}» جواب می‌دهم.
              </span>
            </div>
          </div>
          {history.loading && !history.data && <Skel lines={3} />}
          {visible.map((m) => (m.role === "user" ? <UserMsg key={m.id} m={m} name={me.display_name} /> : <CoachMsg key={m.id} m={m} />))}
          {!shown.length && !history.loading && (
            <div className="suggest">
              {suggestions.map((s) => (
                <button key={s} className="chip" onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
        <Form className="composer mat mat-field" onSubmit={() => ask()}>
          <Paperclip size={16} className="muted" aria-hidden />
          <textarea
            rows={1}
            value={draft}
            maxLength={1500}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), ask())}
            placeholder="سؤالت را بنویس… (اینتر = ارسال)"
            aria-label="سؤال از زیتو"
          />
          {draft.length > 1200 && <span className="counter">{fa(draft.length)}/۱۵۰۰</span>}
          <button className="send" type="submit" disabled={!draft.trim() || busy} aria-label="ارسال">
            <Send />
          </button>
        </Form>
      </section>
      <aside className="coach-ctx">
        <Panel title="زمینه‌ی این گفت‌وگو">
          <div className="accordion">
            {[
              [
                "stage",
                <BookOpen key="1" />,
                "مرحله‌ی جاری",
                <>
                  {stageTitle || "—"} | {info.module?.title}
                  {currentStage?.content?.intro && (
                    <>
                      <br />
                      {currentStage.content.intro}
                    </>
                  )}
                </>,
              ],
              [
                "goals",
                <ListChecks key="2" />,
                "اهداف سرفصل",
                objectives.length ? (
                  <ul>
                    {objectives.map((o) => (
                      <li key={o}>{o}</li>
                    ))}
                  </ul>
                ) : (
                  info.module?.description || "—"
                ),
              ],
              [
                "profile",
                <Footprints key="3" />,
                "پروفایل تو",
                <>
                  {profile?.work_or_study_field} | هدف: {profile?.preferred_career_path}
                </>,
              ],
            ].map(([key, icon, title, body]) => (
              <div key={key} className="acc">
                <button aria-expanded={open === key} onClick={() => setOpen(open === key ? null : key)}>
                  <span className="tile tile-quiet tile-sq" style={{ width: "1.6rem", height: "1.6rem" }}>
                    {icon}
                  </span>
                  <span>{title}</span>
                  <ChevronDown />
                </button>
                {open === key && <div className="acc-body">{body}</div>}
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="کوچ چطور جواب می‌دهد؟">
          <ol style={{ fontSize: "var(--t-micro)", color: "var(--ink-2)", display: "grid", gap: ".35rem" }}>
            <li>سه تکه‌ی مرتبط فقط از همین سرفصل و بخش‌های عمومی دوره بازیابی می‌شود (حداکثر ۴۲۰۰ نویسه).</li>
            <li>منبع‌ها، پروفایل، مرحله‌ی جاری و چهار پیام آخر به مدل داده می‌شود.</li>
            <li>جواب با شماره‌ی منبع می‌آید؛ سؤال نامرتبط جواب ساختگی نمی‌گیرد.</li>
          </ol>
        </Panel>
        <Callout tone="info">جواب‌ها معمولاً ۱۵ تا ۴۵ ثانیه طول می‌کشد و یکجا می‌آید.</Callout>
      </aside>
    </div>
  );
}


function UserMsg({ m, name }) {
  return (
    <div className="msg msg-user">
      <span className="avatar" style={{ width: "2.1rem", height: "2.1rem", fontSize: ".8rem" }}>
        {name.trim()[0]}
      </span>
      <div className="bubble">
        {m.text}
        <time>{clock(m.at)}</time>
      </div>
    </div>
  );
}

function CoachMsg({ m }) {
  const processing = !!m.processing;
  const mode = COACH_MODES[m.mode];
  return (
    <div className="msg msg-coach">
      <CoachAvatar size="2.2rem" busy={processing} />
      <div className="bubble mat mat-raised" style={{ maxWidth: "34rem" }}>
        {processing ? (
          <>
            <span className="soft">در حال یافتن منابع تأییدشده…</span>
            <span className="typing" aria-label="زیتو در حال نوشتن">
              <i />
              <i />
              <i />
            </span>
          </>
        ) : (
          <>
            {mode && (
              <span className={`badge ${mode[1]}`} style={{ justifySelf: "start" }}>
                {m.mode === "out_of_scope" && <Info />} {mode[0]}
              </span>
            )}
            <span style={{ whiteSpace: "pre-line" }}>{m.text}</span>
            {m.nextStep && (
              <div className="next-step">
                <Footprints />
                <span>
                  <b>قدم بعدی پیشنهادی: </b>
                  {m.nextStep}
                </span>
              </div>
            )}
            {m.sources?.length > 0 && <Sources sources={m.sources} />}
          </>
        )}
        {processing ? (
          <AIBar meta={{ status: "processing", expect: "۱۵ تا ۴۵ ثانیه" }} />
        ) : (
          <AIBar meta={m.meta || { status: m.mode === "grounded" || m.mode === "stage_text" ? "ready" : "review", at: m.at }} sources={m.sources?.length ?? 0} />
        )}
      </div>
    </div>
  );
}
