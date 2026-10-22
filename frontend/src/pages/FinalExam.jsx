// Final exam: generate three open questions, answer them, AI grading, certificate on pass.
import { useEffect, useState } from "react";
import { ArrowLeft, Award, BadgeCheck, Compass, RefreshCw, Trophy } from "lucide-react";
import { post } from "../lib/api.js";
import { setCached, useCached } from "../lib/cache.js";
import { fa } from "../lib/format.js";
import { K, pathInfo, refreshLearning, useCurrentPath } from "../lib/learner.js";
import { useStore } from "../lib/store.jsx";
import { Drop } from "../ui/art.jsx";
import { AIBar, Callout, Empty, Field, Panel, Ring, Skel } from "../ui/kit.jsx";

const draftKey = (attemptId) => `zito:final-draft:${attemptId}`;
const readDraft = (attemptId) => {
  try {
    return JSON.parse(localStorage.getItem(draftKey(attemptId)) || "{}");
  } catch {
    return {};
  }
};
const writeDraft = (attemptId, answers) => {
  try {
    localStorage.setItem(draftKey(attemptId), JSON.stringify(answers));
  } catch {
    /* a draft is a convenience only */
  }
};

export function FinalExam() {
  const { go, toast } = useStore();
  const path = useCurrentPath();
  const info = pathInfo(path.data);
  const enrollmentId = path.data?.enrollment_id;
  const state = useCached(info && info.status !== "learning" ? K.final(enrollmentId) : null);
  const [attempt, setAttempt] = useState(null);
  const [answers, setAnswers] = useState({});
  const [phase, setPhase] = useState("idle"); // idle | generating | answering | grading | graded | grading_failed
  const [result, setResult] = useState(null);
  const [timing, setTiming] = useState(null);

  useEffect(() => {
    const live = state.data?.attempt;
    if (live && live.status === "in_progress" && !attempt) {
      setAttempt(live);
      setAnswers(readDraft(live.id));
      setPhase("answering");
    }
  }, [state.data]);

  if (path.loading && !path.data) return <Skel lines={8} />;
  if (!path.data)
    return (
      <Panel>
        <Empty icon={<Compass />} title="دوره‌ای انتخاب نشده" text="آزمون نهایی بعد از تمام کردن همه‌ی سرفصل‌های یک دوره باز می‌شود." />
      </Panel>
    );
  if (info.status === "learning")
    return (
      <Panel>
        <Empty
          icon={<Trophy />}
          title="آزمون نهایی هنوز قفل است"
          text="بعد از تمام کردن همه‌ی سرفصل‌ها باز می‌شود."
          action={
            <button className="btn btn-primary" onClick={() => go({ name: "lesson" })}>
              ادامه‌ی مسیر
            </button>
          }
        />
      </Panel>
    );
  if (state.loading && !state.data) return <Skel lines={8} />;

  const exam = state.data || {};
  const passing = attempt?.passing_score ?? exam.passing_score ?? 70;
  const examTitle = attempt?.title || exam.title || "آزمون نهایی";
  const certificate = result?.certificate || exam.certificate;
  const head = (
    <section className="stage-head mat mat-panel">
      <div className="crumb">
        {path.data.course_title} | نسخه‌ی {fa(path.data.course_version_number)}
      </div>
      <h1>{examTitle}</h1>
      <p className="soft" style={{ fontSize: "var(--t-small)" }}>
        سه پاسخ تشریحی (دو سؤال باز و یک سناریو). با نمره‌ی {fa(passing)} یا بیشتر گواهی صادر می‌شود. زمان محدود نیست و پیش‌نویس پاسخ‌ها در همین مرورگر نگه داشته می‌شود.
      </p>
    </section>
  );

  const start = async () => {
    setPhase("generating");
    setResult(null);
    const started = Date.now();
    try {
      const next = await post(`/api/learning/enrollments/${enrollmentId}/final-exam/start`);
      setTiming({ ms: Date.now() - started, at: Date.now() });
      setAttempt(next);
      setAnswers(readDraft(next.id));
      setPhase("answering");
    } catch (error) {
      setPhase("idle");
      toast(error.message, "err");
    }
  };

  const setAnswer = (id, value) => {
    const next = { ...answers, [id]: value.slice(0, 2500) };
    setAnswers(next);
    writeDraft(attempt.id, next);
  };

  const submit = async () => {
    setPhase("grading");
    const started = Date.now();
    try {
      const graded = await post(`/api/learning/enrollments/${enrollmentId}/final-exam/attempts/${attempt.id}/submit`, { answers });
      setResult({ ...graded, meta: { status: "ready", ms: Date.now() - started, at: Date.now() } });
      setPhase("graded");
      writeDraft(attempt.id, {});
      refreshLearning(enrollmentId);
      if (graded.passed) setCached(K.final(enrollmentId), { ...exam, status: "passed", certificate: graded.certificate });
    } catch (error) {
      setPhase("grading_failed");
      toast(error.message, "err");
    }
  };

  // Passed before (or just now with no attempt in memory): show the certificate card.
  if (exam.status === "passed" && !result)
    return (
      <div className="stack">
        {head}
        <Panel>
          <div className="empty">
            <Drop size="5.5rem" face />
            <h2>این آزمون را با موفقیت گذرانده‌ای</h2>
            <p>{certificate ? "گواهی‌ات صادر شده و هر کسی می‌تواند بدون ورود استعلامش کند." : "این دوره برای تو تکمیل شده است."}</p>
            {certificate && (
              <button className="btn btn-primary btn-lg" onClick={() => go({ name: "certificate", id: certificate.certificate_number })}>
                <Award /> مشاهده و چاپ مدرک
              </button>
            )}
          </div>
        </Panel>
      </div>
    );

  if (phase === "idle" || (!attempt && phase !== "generating"))
    return (
      <div className="stack">
        {head}
        <Panel>
          <div className="empty">
            <Drop size="5.5rem" face />
            <h2>آماده‌ای؟</h2>
            <p>زیتو از روی کل محتوای دوره سه سؤال تازه می‌سازد. ساخت سؤال‌ها معمولاً حدود ۴۵ ثانیه طول می‌کشد.</p>
            <div className="row" style={{ justifyContent: "center" }}>
              <button className="btn btn-primary btn-lg" onClick={start}>
                <Trophy /> شروع آزمون نهایی
              </button>
            </div>
          </div>
        </Panel>
      </div>
    );

  if (phase === "generating")
    return (
      <div className="stack">
        {head}
        <Panel>
          <AIBar meta={{ status: "processing", expect: "۴۵ ثانیه" }} sources={0} />
          <p className="soft" style={{ margin: ".8rem 0", fontSize: "var(--t-small)" }}>
            در حال خواندن بخش‌هایی از پایگاه دانش و فهرست سرفصل‌ها و ساختن سؤال‌ها…
          </p>
          <Skel lines={6} />
        </Panel>
      </div>
    );

  const graded = phase === "graded" && result;
  const passed = graded && result.passed;
  const questions = attempt.questions || [];
  const feedbackOf = (id) => result?.question_feedback?.find((q) => q.question_id === id);
  const written = questions.filter((q) => (answers[q.id] ?? "").trim().length > 20).length;

  return (
    <div className="stack">
      {head}
      {attempt.generation_method === "approved_fallback" && (
        <Callout tone="info">ساخت سؤال با هوش مصنوعی ممکن نشد؛ سؤال‌های پیش‌فرض تأییدشده‌ی دوره آمده است.</Callout>
      )}
      {graded && (
        <Panel>
          <div className="row" style={{ gap: "1.2rem", alignItems: "center" }}>
            <Ring value={result.score} max={100} size="6rem" label={<span style={{ fontSize: "1.4rem" }}>{fa(result.score)}</span>} />
            <div style={{ flex: 1, minWidth: "14rem" }}>
              <h2>{passed ? "قبول شدی! گواهی‌ات صادر شد." : `نمره ${fa(result.score)} از ۱۰۰؛ حدنصاب ${fa(passing)}`}</h2>
              <p className="soft" style={{ fontSize: "var(--t-small)" }}>
                {result.feedback}
              </p>
            </div>
            {passed ? (
              <button className="btn btn-primary btn-lg" onClick={() => go({ name: "certificate", id: result.certificate?.certificate_number })} disabled={!result.certificate}>
                <Award /> مشاهده و چاپ مدرک
              </button>
            ) : (
              <button className="btn btn-primary btn-lg" onClick={start}>
                <RefreshCw /> شروع تلاش تازه
              </button>
            )}
          </div>
          <div style={{ marginTop: ".8rem" }}>
            <AIBar meta={result.meta} />
          </div>
          <p className="formula" style={{ marginTop: ".6rem" }}>
            هر پاسخ با معیارهای داخلی همان سؤال تصحیح می‌شود؛ معیارها نشان داده نمی‌شوند. تعداد تلاش محدود نیست و هر تلاش سؤال‌های تازه دارد.
          </p>
        </Panel>
      )}
      {phase === "grading_failed" && (
        <Callout tone="err" title="تصحیح هوشمند در حال حاضر در دسترس نیست">
          پاسخ‌هایت ذخیره شده‌اند. چند لحظه بعد دوباره «ثبت و تصحیح آزمون» را بزن.
        </Callout>
      )}
      {questions.map((q, i) => {
        const fb = feedbackOf(q.id);
        const length = (answers[q.id] ?? "").length;
        return (
          <Panel key={q.id}>
            <div className="row" style={{ justifyContent: "space-between", marginBlockEnd: ".5rem" }}>
              <span className="badge badge-quiet">
                سؤال {fa(i + 1)} | {q.type === "scenario" ? "سناریو" : "تشریحی"}
              </span>
              <span className="badge badge-accent">{fb && fb.score != null ? `${fa(fb.score)} از ${fa(q.max_score)}` : `${fa(q.max_score)} امتیاز`}</span>
            </div>
            <Field label={q.question} count={[length, 2500]}>
              <textarea
                className="textarea"
                rows={5}
                value={answers[q.id] ?? ""}
                maxLength={2500}
                readOnly={!!graded || phase === "grading"}
                onChange={(e) => setAnswer(q.id, e.target.value)}
                placeholder="پاسخت را کامل و با یک مثال از کار خودت بنویس…"
              />
            </Field>
            {fb && (
              <div className="next-step" style={{ marginTop: ".6rem", background: "rgba(238,230,252,.8)", color: "var(--ink-2)" }}>
                <BadgeCheck />
                <span>{fb.feedback}</span>
              </div>
            )}
          </Panel>
        );
      })}
      {!graded && questions.length > 0 && (
        <div className="stage-foot mat mat-panel">
          <div className="grow">
            <span>
              {fa(written)} از {fa(questions.length)} پاسخ نوشته شده
            </span>
          </div>
          <button className="btn btn-primary btn-lg" disabled={phase === "grading" || questions.some((q) => !(answers[q.id] ?? "").trim())} onClick={submit}>
            {phase === "grading" ? "در حال تصحیح…" : "ثبت و تصحیح آزمون"} <ArrowLeft />
          </button>
        </div>
      )}
      {timing && phase === "answering" && <AIBar meta={{ status: "ready", ms: timing.ms, at: timing.at }} />}
    </div>
  );
}
