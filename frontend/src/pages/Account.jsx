// Learner certificates list and profile editor.
import { useState } from "react";
import { Award, Save } from "lucide-react";
import { patch } from "../lib/api.js";
import { fa, jalali } from "../lib/format.js";
import { useOverview } from "../lib/learner.js";
import { PROFILE_KEYS, useStore } from "../lib/store.jsx";
import { Empty, Field, Form, Panel, Skel } from "../ui/kit.jsx";
import { PROFILE_QUESTIONS } from "./Onboarding.jsx";

export function Certs() {
  const { go } = useStore();
  const overview = useOverview();
  if (overview.loading && !overview.data) return <Skel lines={6} />;
  const certificates = overview.data?.certificates || [];
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>گواهی‌های من</h1>
          <p>هر گواهی یک لینک عمومی دارد که بدون ورود قابل استعلام است.</p>
        </div>
      </div>
      {certificates.length ? (
        <div className="course-grid">
          {certificates.map((c) => (
            <button key={c.certificate_number} className="course-card mat mat-panel" onClick={() => go({ name: "certificate", id: c.certificate_number })}>
              <span className="course-body">
                <span className="tile tile-lg tile-mint">
                  <Award />
                </span>
                <h3>{c.course_title}</h3>
                <span className="meta-row">
                  <span>نمره {fa(c.score)}</span>
                  <span>{jalali(c.issued_at)}</span>
                </span>
                <small className="ltr muted">{c.certificate_number}</small>
              </span>
            </button>
          ))}
        </div>
      ) : (
        <Panel>
          <Empty
            icon={<Award />}
            title="هنوز گواهی‌ای نگرفته‌ای"
            text="با تمام کردن یک دوره و قبولی در آزمون نهایی، گواهی‌ات اینجا می‌آید."
            action={
              <button className="btn btn-primary" onClick={() => go({ name: "lesson" })}>
                ادامه‌ی مسیر
              </button>
            }
          />
        </Panel>
      )}
    </div>
  );
}

export function Profile() {
  const { me, profile, setProfile, toast } = useStore();
  const [form, setForm] = useState(() => ({ ...profile }));
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  if (!me) return null;

  const save = async () => {
    const found = {};
    PROFILE_KEYS.forEach((key) => {
      const empty = !String(form[key] ?? "").trim() && !(key === "daily_learning_time_text" && form.daily_learning_minutes != null);
      if (empty) found[key] = "این فیلد خالی است؛ کوچ و مثال شخصی از آن استفاده می‌کنند.";
    });
    setErrors(found);
    if (Object.keys(found).length || busy) return;
    const body = {};
    PROFILE_KEYS.forEach((key) => {
      if (form[key] != null) body[key] = String(form[key]).trim();
    });
    if (form.daily_learning_minutes != null) body.daily_learning_minutes = form.daily_learning_minutes;
    setBusy(true);
    try {
      const saved = await patch("/api/me/profile", body);
      setProfile(saved);
      setForm({ ...saved });
      toast("پروفایل ذخیره شد؛ کوچ و مثال‌های بعدی از همین اطلاعات استفاده می‌کنند.");
    } catch (error) {
      toast(error.message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack" style={{ maxWidth: "44rem" }}>
      <div className="page-head">
        <div>
          <h1>پروفایل من</h1>
          <p>
            {me.display_name} | <span className="ltr">{me.phone}</span>
            {me.created_at && ` | عضو از ${jalali(me.created_at)}`}
          </p>
        </div>
      </div>
      <Panel>
        <Form onSubmit={save}>
          {PROFILE_KEYS.map((key) => {
            const q = PROFILE_QUESTIONS[key];
            return (
              <Field key={key} label={q.q} error={errors[key]}>
                {q.choices ? (
                  <div className="seg" role="radiogroup">
                    {q.choices.map(([label, minutes]) => (
                      <button
                        key={label}
                        type="button"
                        role="radio"
                        aria-checked={form[key] === label || (!form[key] && form.daily_learning_minutes === minutes)}
                        onClick={() => setForm({ ...form, [key]: label, daily_learning_minutes: minutes })}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                ) : (
                  <input className="input" maxLength={500} value={String(form[key] ?? "")} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
                )}
              </Field>
            );
          })}
          <button className="btn btn-primary" type="submit" style={{ justifySelf: "start" }} disabled={busy}>
            <Save /> {busy ? "در حال ذخیره…" : "ذخیره‌ی پروفایل"}
          </button>
        </Form>
      </Panel>
    </div>
  );
}
