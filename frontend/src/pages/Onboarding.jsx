// Seven-question profile chat; every answer is saved immediately.
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Send } from "lucide-react";
import { patch } from "../lib/api.js";
import { fa } from "../lib/format.js";
import { useOverview } from "../lib/learner.js";
import { PROFILE_KEYS, answered, useStore } from "../lib/store.jsx";
import { CoachAvatar } from "../ui/art.jsx";
import { Bar, Form } from "../ui/kit.jsx";

export const PROFILE_QUESTIONS = {
  work_or_study_field: { q: "حوزه‌ی کاری یا رشته‌ی تحصیلی‌ات چیست؟", suggest: ["کارشناس فروش", "پشتیبانی مشتری", "حسابداری", "دانشجو"] },
  education_level: { q: "سطح تحصیلاتت؟", suggest: ["دیپلم", "کاردانی", "کارشناسی", "کارشناسی ارشد و بالاتر"] },
  learning_goal_interests: { q: "از یادگیری در زیتو چه هدفی داری؟ به چه چیزهایی علاقه داری؟" },
  ai_familiarity_level: { q: "چقدر با هوش مصنوعی آشنایی داری؟", suggest: ["آشنایی ندارم", "کمی کار کرده‌ام", "زیاد استفاده می‌کنم"] },
  daily_learning_time_text: {
    q: "روزی چقدر وقت برای یادگیری داری؟",
    choices: [
      ["کمتر از یک ساعت", 30],
      ["یک ساعت", 60],
      ["بیشتر", 90],
    ],
  },
  preferred_career_path: { q: "دوست داری در آینده در چه مسیر شغلی‌ای باشی؟", suggest: ["سرپرست تیم", "کارشناس ارشد", "کسب‌وکار شخصی"] },
  referral_source: { q: "از کجا با زیتو آشنا شدی؟", suggest: ["اینستاگرام", "معرفی دوستان", "جست‌وجو در اینترنت", "محل کار"] },
};

const shown = (profile, key) =>
  key === "daily_learning_time_text" && !profile[key] && profile.daily_learning_minutes != null
    ? `${fa(profile.daily_learning_minutes)} دقیقه`
    : String(profile[key]);

export function Onboarding() {
  const { me, profile: saved, setProfile, go, toast } = useStore();
  const overview = useOverview();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  const profile = saved ?? {};
  const index = PROFILE_KEYS.findIndex((key) => !answered(profile, key));
  const done = index === -1;
  const key = done ? null : PROFILE_KEYS[index];
  const question = key ? PROFILE_QUESTIONS[key] : null;
  const firstName = me?.display_name?.split(" ")[0] ?? "";

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [index]);

  const answer = async (value, minutes) => {
    const text = value.trim();
    if (!key || !text || busy) return;
    const body = { [key]: text };
    if (minutes) body.daily_learning_minutes = minutes;
    setBusy(true);
    setProfile({ ...profile, ...body });
    setDraft("");
    try {
      setProfile(await patch("/api/me/profile", body));
    } catch (error) {
      setProfile(profile);
      setDraft(text);
      toast(error.message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="onb">
      <div className="onb-head">
        <CoachAvatar size="3.4rem" />
        <div style={{ flex: 1 }}>
          <h1>سلام {firstName}، من زیتو هستم</h1>
          <p className="soft" style={{ fontSize: "var(--t-small)" }}>
            هفت سؤال کوتاه می‌پرسم تا مثال‌ها و جواب‌هایم مخصوص کار خودت باشد. هر جواب همان لحظه ذخیره می‌شود.
          </p>
        </div>
      </div>
      <div className="row" style={{ fontSize: "var(--t-micro)" }}>
        <span className="muted">{fa(done ? 7 : index)} از ۷ سؤال</span>
        <div style={{ flex: 1 }}>
          <Bar value={((done ? 7 : index) / 7) * 100} label="پیشرفت پروفایل" />
        </div>
      </div>
      <div className="mat mat-panel" style={{ padding: "1.1rem" }}>
        <div className="msgs" style={{ padding: 0 }} aria-live="polite">
          {PROFILE_KEYS.slice(0, done ? 7 : index + 1).map((k) => (
            <div key={k} style={{ display: "grid", gap: "0.7rem" }}>
              <div className="msg msg-coach">
                <CoachAvatar size="2.2rem" />
                <div className="bubble mat mat-raised">{PROFILE_QUESTIONS[k].q}</div>
              </div>
              {answered(profile, k) && (
                <div className="msg msg-user">
                  <div className="bubble">{shown(profile, k)}</div>
                </div>
              )}
            </div>
          ))}
          {done && (
            <div className="msg msg-coach">
              <CoachAvatar size="2.2rem" />
              <div className="bubble mat mat-raised">
                عالی شد {firstName}! پروفایلت کامل است. حالا یک دوره انتخاب کن تا اولین قدم را برداریم.
                <button
                  className="btn btn-primary"
                  style={{ justifySelf: "start" }}
                  onClick={() => go({ name: overview.data?.enrollments?.length ? "home" : "courses" })}
                >
                  انتخاب دوره <ArrowLeft />
                </button>
              </div>
            </div>
          )}
          <div ref={end} />
        </div>
      </div>
      {question && (
        <div className="stack">
          {question.choices ? (
            <div className="choice-row" role="radiogroup" aria-label={question.q}>
              {question.choices.map(([label, minutes]) => (
                <button key={label} className="btn btn-soft" role="radio" aria-checked={false} disabled={busy} onClick={() => answer(label, minutes)}>
                  {label}
                </button>
              ))}
            </div>
          ) : (
            <>
              {question.suggest && (
                <div className="choice-row">
                  {question.suggest.map((label) => (
                    <button key={label} className="chip" disabled={busy} onClick={() => answer(label)}>
                      {label}
                    </button>
                  ))}
                </div>
              )}
              <Form className="composer mat mat-panel" style={{ margin: 0 }} onSubmit={() => answer(draft)}>
                <textarea
                  rows={1}
                  value={draft}
                  maxLength={500}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="جوابت را بنویس…"
                  aria-label={question.q}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), answer(draft))}
                  autoFocus
                />
                <button className="send" type="submit" disabled={!draft.trim() || busy} aria-label="ثبت جواب">
                  <Send />
                </button>
              </Form>
            </>
          )}
        </div>
      )}
    </div>
  );
}
