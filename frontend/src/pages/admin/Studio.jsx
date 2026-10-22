// Course studio: course list, new-course brief, version editor, module/stage dialogs, generation log, RAG.
import { useEffect, useMemo, useState } from "react";
import {
  ArchiveRestore,
  ArrowLeft,
  Check,
  CircleDot,
  Copy,
  Database,
  EllipsisVertical,
  ExternalLink,
  FileBraces,
  ImagePlus,
  Layers,
  LoaderCircle,
  Pencil,
  Plus,
  Power,
  RefreshCw,
  Rocket,
  Save,
  Sparkles,
  Trash,
  Video,
  X,
} from "lucide-react";
import { patch, post } from "../../lib/api.js";
import { invalidate, setCached, useCached } from "../../lib/cache.js";
import { AK, useAdminCourses } from "../../lib/admin.js";
import { ago, fa, hueOf, jalali } from "../../lib/format.js";
import { useStore } from "../../lib/store.jsx";
import { Landscape, Sprig } from "../../ui/art.jsx";
import { AIBar, Bar, Callout, Dialog, Empty, Field, Form, Panel, Skel } from "../../ui/kit.jsx";

export const LEVELS = ["مقدماتی", "متوسط", "پیشرفته"];
const STAGE_LABELS = {
  learning_path: "مسیر یادگیری",
  lesson_summary: "خلاصه درس",
  flashcards: "فلش‌کارت‌ها",
  golden_tips: "نکات طلایی",
  common_mistakes: "اشتباهات رایج",
  personalized_work_example: "مثال در شغل",
  module_assessment: "آزمونک",
  module_completion: "پایان سرفصل",
};

export function versionState(v) {
  if (v.status === "published") return ["منتشرشده", "badge-ok"];
  if (v.generation_status === "generating") return ["در حال تولید", "badge-info"];
  if (v.generation_status === "needs_regeneration") return ["نیازمند تولید دوباره", "badge-warn"];
  if (v.generation_status === "failed") return ["تولید ناموفق", "badge-err"];
  if (v.generation_status === "not_requested") return ["آماده‌ی تولید", "badge-quiet"];
  return ["پیش‌نویس", "badge-err"];
}
export const versionBadge = (v) => {
  const [label, tone] = versionState(v);
  return <span className={`badge ${tone}`}>{label}</span>;
};

// ---- brief <-> form -----------------------------------------------------------------------------

const emptyBrief = () => ({
  title: "",
  topic: "",
  goal: "",
  duration: "",
  audience: "",
  targetGroup: "",
  level: "مقدماتی",
  sections: 5,
  hours: 4,
  finalExam: true,
  instruction: "",
  domain: "",
  slug: "",
});

const fromBrief = (v) => {
  const b = v.authoring_brief || {};
  return {
    title: b.title || v.course_title || "",
    topic: b.topic || "",
    goal: b.goal || "",
    duration: b.duration || "",
    audience: b.audience || "",
    targetGroup: b.target_group || "",
    level: b.level || "مقدماتی",
    sections: Number(b.module_count) || v.modules.length || 5,
    hours: Number(b.estimated_learning_hours) || 4,
    finalExam: b.requires_final_exam ?? v.requires_final_exam,
    instruction: b.generation_instructions || "",
  };
};

const toPayload = (f) => ({
  title: f.title.trim(),
  topic: f.topic.trim(),
  goal: f.goal.trim(),
  duration: f.duration.trim(),
  audience: f.audience.trim(),
  target_group: f.targetGroup.trim() || f.audience.trim(),
  level: f.level,
  module_count: Number(f.sections),
  estimated_learning_hours: Number(f.hours),
  requires_final_exam: !!f.finalExam,
  generation_instructions: f.instruction.trim() || null,
});

function validateBrief(f) {
  const e = {};
  if (f.title.trim().length < 3) e.title = "عنوان دوره حداقل ۳ حرف باشد؛ مثل «فروش تلفنی حرفه‌ای».";
  if (!f.topic.trim()) e.topic = "موضوع را بنویس تا هوش مصنوعی بداند درباره‌ی چه بنویسد.";
  if (!f.goal.trim()) e.goal = "هدف دوره را در یک یا دو جمله بنویس.";
  if (!f.duration.trim()) e.duration = "مدت دوره را بنویس؛ مثلاً «۲ هفته».";
  if (!f.audience.trim()) e.audience = "مخاطب را مشخص کن؛ مثلاً «کارشناسان فروش».";
  if (!(f.sections >= 1 && f.sections <= 20)) e.sections = "تعداد سرفصل باید بین ۱ تا ۲۰ باشد.";
  if (!(f.hours >= 1 && f.hours <= 1000)) e.hours = "ساعت یادگیری عددی بین ۱ تا ۱۰۰۰ است.";
  if (f.instruction.length > 6000) e.instruction = "دستور تولید حداکثر ۶۰۰۰ نویسه است؛ متن را کوتاه کن.";
  if (f.slug && !/^[a-z0-9][a-z0-9-]*$/.test(f.slug.trim())) e.slug = "آدرس فقط حروف کوچک انگلیسی، عدد و خط تیره.";
  return e;
}

function BriefForm({ b, set, errors, readOnly, extra }) {
  const bind = (key) => ({ value: String(b[key] ?? ""), readOnly, onChange: (e) => set({ ...b, [key]: e.target.value }) });
  return (
    <div className="form">
      <Field label="عنوان دوره" req error={errors.title}>
        <input className="input" maxLength={255} {...bind("title")} placeholder="مثلاً فروش تلفنی حرفه‌ای" />
      </Field>
      <div className="form-row">
        <Field label="موضوع" req error={errors.topic}>
          <input className="input" {...bind("topic")} placeholder="فروش تلفنی" />
        </Field>
        <Field label="مدت" req error={errors.duration} hint="فقط برای نمایش">
          <input className="input" {...bind("duration")} placeholder="۲ هفته" />
        </Field>
      </div>
      <Field label="هدف دوره" req error={errors.goal}>
        <textarea className="textarea" rows={3} {...bind("goal")} placeholder="یادگیرنده در پایان دوره چه کاری را بهتر انجام می‌دهد؟" />
      </Field>
      <div className="form-row">
        <Field label="مخاطب" req error={errors.audience}>
          <input className="input" {...bind("audience")} placeholder="کارشناسان فروش" />
        </Field>
        <Field label="گروه هدف">
          <input className="input" {...bind("targetGroup")} placeholder="کارشناسان فروش و پشتیبانی" />
        </Field>
      </div>
      <Field label="سطح">
        <div className="seg" role="radiogroup" aria-label="سطح">
          {LEVELS.map((level) => (
            <button key={level} type="button" role="radio" aria-checked={b.level === level} disabled={readOnly} onClick={() => set({ ...b, level })}>
              {level}
            </button>
          ))}
        </div>
      </Field>
      <div className="form-row">
        <Field label="تعداد سرفصل" req error={errors.sections} hint="۱ تا ۲۰">
          <input className="input" type="number" min={1} max={20} readOnly={readOnly} value={b.sections} onChange={(e) => set({ ...b, sections: Number(e.target.value) })} />
        </Field>
        <Field label="ساعت یادگیری" error={errors.hours}>
          <input className="input" type="number" min={1} readOnly={readOnly} value={b.hours} onChange={(e) => set({ ...b, hours: Number(e.target.value) })} />
        </Field>
      </div>
      {extra}
      <button type="button" role="switch" aria-checked={!!b.finalExam} className="check-row mat mat-raised" disabled={readOnly} onClick={() => set({ ...b, finalExam: !b.finalExam })}>
        <span className="check-box">{b.finalExam && <Check />}</span>
        <span>آزمون نهایی و گواهی (حدنصاب ۷۰) فعال باشد</span>
      </button>
      <Field label="دستور تولید" error={errors.instruction} count={[b.instruction.length, 6000]} hint="لحن، نوع مثال‌ها و هر قاعده‌ی خاص این دوره. مستقیماً در تولید معرفی، سرفصل‌ها و آزمونک‌ها استفاده می‌شود.">
        <textarea className="textarea" rows={4} {...bind("instruction")} placeholder="مثلاً: مثال‌ها از محیط کار ایرانی باشد…" />
      </Field>
    </div>
  );
}

// ---- data helpers --------------------------------------------------------------------------------

function useVersion(courseId, version) {
  return useCached(courseId && version ? AK.version(courseId, version) : null);
}

function refreshAfter(version) {
  setCached(AK.version(version.course_id, version.version_number), version);
  invalidate(AK.courses);
}

const vbase = (v) => `/api/admin/courses/${v.course_id}/versions/${v.version_number}`;

// ---- new course ----------------------------------------------------------------------------------

export function AdminNew() {
  const { go, toast } = useStore();
  const [brief, setBrief] = useState(emptyBrief);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  const create = async () => {
    const found = validateBrief(brief);
    setErrors(found);
    if (Object.keys(found).length || busy) return;
    setBusy(true);
    try {
      const body = {
        ...toPayload(brief),
        domain: brief.domain.trim() || null,
        slug: brief.slug.trim() || null,
        client_request_id: globalThis.crypto?.randomUUID?.() || `cms-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      };
      const draft = await post("/api/admin/courses", body);
      const started = await post(`${vbase(draft)}/generate`);
      refreshAfter(started);
      toast("پیش‌نویس ساخته شد و تولید در پس‌زمینه شروع شد.");
      go({ name: "admin-studio", courseId: started.course_id, version: started.version_number });
    } catch (error) {
      toast(error.message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <div className="studio-head">
        <button className="icon-btn" onClick={() => go({ name: "admin-studio" })} aria-label="بازگشت">
          <ArrowLeft style={{ transform: "scaleX(-1)" }} />
        </button>
        <h1>دوره‌ی جدید</h1>
      </div>
      <div className="studio">
        <Panel title="مشخصات دوره (brief)">
          <BriefForm
            b={brief}
            set={setBrief}
            errors={errors}
            extra={
              <div className="form-row">
                <Field label="دامنه‌ی داخلی (اختیاری)">
                  <input className="input ltr" dir="ltr" value={brief.domain} onChange={(e) => setBrief({ ...brief, domain: e.target.value })} placeholder="product_management" />
                </Field>
                <Field label="آدرس انگلیسی (اختیاری)" error={errors.slug}>
                  <input className="input ltr" dir="ltr" value={brief.slug} onChange={(e) => setBrief({ ...brief, slug: e.target.value })} placeholder="product-management" />
                </Field>
              </div>
            }
          />
        </Panel>
        <div className="stack">
          <Panel title="چه اتفاقی می‌افتد؟">
            <ol style={{ display: "grid", gap: ".45rem", fontSize: "var(--t-small)", color: "var(--ink-2)" }}>
              <li>طرح کلی: معرفی دوره و دقیقاً {fa(brief.sections || 0)} سرفصل.</li>
              <li>هر سرفصل یکی‌یکی: هشت مرحله + متن پایگاه دانش ۸۰۰ تا ۱۳۰۰ واژه.</li>
              <li>کنترل کیفیت؛ سرفصل ردشده دوباره تولید می‌شود.</li>
              <li>بازنویسی گزینه‌هایی که گزینه‌ی درستشان لو می‌رود.</li>
            </ol>
            <p className="muted" style={{ fontSize: "var(--t-micro)", marginTop: ".6rem" }}>
              مدل <span className="ltr">GPT-4.1</span> | حدود ۸ تا ۱۰ دقیقه برای ۷ سرفصل؛ تولید در پس‌زمینه است.
            </p>
          </Panel>
          <button className="btn btn-primary btn-lg" onClick={create} disabled={busy}>
            <Sparkles /> {busy ? "در حال ساخت…" : "ساخت پیش‌نویس با هوش مصنوعی"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- list ----------------------------------------------------------------------------------------

export function Studio({ courseId, version, tab }) {
  return courseId && version ? <StudioEditor key={`${courseId}-${version}`} courseId={Number(courseId)} versionNumber={Number(version)} initialTab={tab} /> : <StudioList />;
}

function useCourseRows() {
  const courses = useAdminCourses();
  return useMemo(() => {
    const byCourse = new Map();
    for (const v of courses.data || []) {
      if (!byCourse.has(v.course_id)) byCourse.set(v.course_id, []);
      byCourse.get(v.course_id).push(v);
    }
    return [...byCourse.entries()].map(([id, versions]) => {
      versions.sort((a, b) => b.version_number - a.version_number);
      return {
        id,
        title: versions[0].course_title,
        status: versions[0].course_status,
        versions,
        published: versions.find((v) => v.status === "published"),
        draft: versions.find((v) => v.status !== "published"),
      };
    });
  }, [courses.data]);
}

async function setCourseState(v, action) {
  const updated = await post(`${vbase(v)}/${action}`);
  refreshAfter(updated);
  return updated;
}

function StudioList() {
  const { go, toast } = useStore();
  const courses = useAdminCourses();
  const rows = useCourseRows();
  const [showDeleted, setShowDeleted] = useState(false);
  const visible = rows.filter((r) => (r.status === "deleted") === showDeleted);
  const act = (row, action, message, tone) =>
    setCourseState(row.versions[0], action)
      .then(() => toast(message, tone))
      .catch((error) => toast(error.message, "err"));
  const revise = async (row) => {
    try {
      const v = await post(`/api/admin/courses/${row.id}/revisions`);
      refreshAfter(v);
      toast("کپی پیش‌نویس ساخته شد. یادگیرنده‌های فعلی روی نسخه‌ی خودشان می‌مانند.");
      go({ name: "admin-studio", courseId: v.course_id, version: v.version_number });
    } catch (error) {
      toast(error.message, "err");
    }
  };

  return (
    <div className="stack">
      <div className="studio-head">
        <h1>استودیوی دوره</h1>
        <button className="chip" aria-pressed={showDeleted} onClick={() => setShowDeleted(!showDeleted)}>
          {showDeleted ? "نمایش دوره‌های فعال" : "نمایش حذف‌شده‌ها"}
        </button>
        <button className="btn btn-primary" onClick={() => go({ name: "admin-new" })}>
          <Plus /> دوره‌ی جدید
        </button>
      </div>
      <Panel>
        {courses.loading && !courses.data ? (
          <Skel lines={6} />
        ) : visible.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>دوره</th>
                  <th>نسخه‌ها</th>
                  <th className="hide-sm">پایگاه دانش</th>
                  <th className="hide-sm">نمایش</th>
                  <th>کار</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <div className="row" style={{ flexWrap: "nowrap" }}>
                        <span className="thumb" style={{ width: "2.8rem", height: "2.2rem" }}>
                          <Landscape hue={hueOf(row.id)} seed={hueOf(row.id)} />
                        </span>
                        <b style={{ fontWeight: 500 }}>{row.title}</b>
                      </div>
                    </td>
                    <td>
                      <div className="row" style={{ gap: ".3rem" }}>
                        {row.versions.map((v) => {
                          const [label, tone] = versionState(v);
                          return (
                            <button key={v.id} className={`badge ${tone}`} onClick={() => go({ name: "admin-studio", courseId: v.course_id, version: v.version_number })}>
                              ن{fa(v.version_number)} | {label}
                            </button>
                          );
                        })}
                      </div>
                    </td>
                    <td className="hide-sm">{row.published ? <RagBadge v={row.published} /> : <span className="muted">—</span>}</td>
                    <td className="hide-sm">
                      {row.status === "inactive" ? <span className="badge badge-quiet">غیرفعال</span> : row.status === "deleted" ? <span className="badge badge-quiet">حذف‌شده</span> : <span className="badge badge-ok">فعال</span>}
                    </td>
                    <td>
                      <div className="row" style={{ gap: ".2rem", flexWrap: "nowrap" }}>
                        <button className="btn btn-soft btn-sm" onClick={() => go({ name: "admin-studio", courseId: row.id, version: (row.draft ?? row.versions[0]).version_number })}>
                          <Pencil /> باز کردن
                        </button>
                        {row.published && !row.draft && row.status !== "deleted" && (
                          <button className="icon-btn" title="ویرایش با نسخه جدید" aria-label="ویرایش با نسخه جدید" onClick={() => revise(row)}>
                            <Copy />
                          </button>
                        )}
                        {row.status !== "deleted" && row.published && (
                          <button
                            className="icon-btn"
                            title={row.status === "inactive" ? "فعال کردن" : "غیرفعال کردن"}
                            aria-label={row.status === "inactive" ? "فعال کردن" : "غیرفعال کردن"}
                            onClick={() =>
                              row.status === "inactive"
                                ? act(row, "reactivate", "دوره دوباره برای یادگیرنده‌ها نمایش داده می‌شود.")
                                : act(row, "deactivate", "دوره از فهرست یادگیرنده‌ها پنهان شد.", "info")
                            }
                          >
                            <Power />
                          </button>
                        )}
                        <button
                          className="icon-btn"
                          title={row.status === "deleted" ? "بازیابی" : "حذف (نرم)"}
                          aria-label={row.status === "deleted" ? "بازیابی" : "حذف"}
                          onClick={() =>
                            row.status === "deleted"
                              ? act(row, "restore", "دوره بازیابی شد.")
                              : act(row, "soft-delete", "دوره حذف شد (نرم)؛ از فهرست «حذف‌شده‌ها» بازیابی می‌شود.", "warn")
                          }
                        >
                          {row.status === "deleted" ? <ArchiveRestore /> : <Trash />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            icon={<Layers />}
            title={showDeleted ? "دوره‌ی حذف‌شده‌ای نیست" : "هنوز دوره‌ای نساخته‌ای"}
            text={showDeleted ? "حذف نرم است؛ دوره‌های حذف‌شده اینجا برای بازیابی می‌مانند." : "مشخصات اولین دوره را بنویس تا هوش مصنوعی آن را بسازد."}
            action={
              showDeleted ? undefined : (
                <button className="btn btn-primary" onClick={() => go({ name: "admin-new" })}>
                  دوره‌ی جدید
                </button>
              )
            }
          />
        )}
      </Panel>
    </div>
  );
}

function RagBadge({ v }) {
  const rag = useCached(v.status === "published" ? AK.rag(v.course_id, v.version_number) : null);
  const r = rag.data;
  if (!r) return <span className="badge badge-quiet">—</span>;
  const busy = r.queued_job_count + r.running_job_count + r.retry_job_count;
  if (r.failed_job_count) return <span className="badge badge-err">دارای خطا</span>;
  if (busy)
    return (
      <span className="badge badge-info">
        <LoaderCircle className="spin" /> در حال ایندکس {fa(r.succeeded_job_count)}/{fa(r.succeeded_job_count + busy)}
      </span>
    );
  if (r.document_count)
    return (
      <span className="badge badge-ok">
        <Database /> آماده
      </span>
    );
  return <span className="badge badge-quiet">ایندکس نشده</span>;
}

// ---- editor --------------------------------------------------------------------------------------

function StudioEditor({ courseId, versionNumber, initialTab }) {
  const { go, toast } = useStore();
  const loaded = useVersion(courseId, versionNumber);
  const allCourses = useAdminCourses();
  const v = loaded.data;
  const [form, setForm] = useState(null);
  const [errors, setErrors] = useState({});
  const [tab, setTab] = useState(initialTab === "overview" || initialTab === "versions" ? initialTab : "course");
  const [moduleDialog, setModuleDialog] = useState(null);
  const [stageDialog, setStageDialog] = useState(null);
  const [publishError, setPublishError] = useState(null);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    if (v) setForm(fromBrief(v));
  }, [v?.id, v?.authoring_brief]);

  // Generation runs in the background: poll the version until it finishes.
  useEffect(() => {
    if (v?.generation_status !== "generating") return;
    const timer = setInterval(() => loaded.reload().then((next) => next && next.generation_status !== "generating" && invalidate(AK.courses)).catch(() => {}), 3000);
    return () => clearInterval(timer);
  }, [v?.generation_status]);

  if (loaded.loading && !v) return <Skel lines={10} />;
  if (!v || !form)
    return (
      <Panel>
        <Empty
          icon={<Layers />}
          title="این نسخه پیدا نشد"
          text={loaded.error?.message || "ممکن است حذف شده باشد."}
          action={
            <button className="btn btn-soft" onClick={() => go({ name: "admin-studio" })}>
              برگشت به فهرست
            </button>
          }
        />
      </Panel>
    );

  const published = v.status === "published";
  const generating = v.generation_status === "generating";
  const dirty = JSON.stringify(toPayload(form)) !== JSON.stringify(toPayload(fromBrief(v)));
  const otherVersions = (allCourses.data || []).filter((x) => x.course_id === v.course_id).sort((a, b) => b.version_number - a.version_number);
  const hue = hueOf(v.course_id);
  const stageCount = v.modules.reduce((sum, m) => sum + m.stages.length, 0);
  const overview = v.overview || {};

  const run = async (key, fn) => {
    if (busy) return null;
    setBusy(key);
    try {
      return await fn();
    } catch (error) {
      toast(error.message, "err");
      return null;
    } finally {
      setBusy(null);
    }
  };
  const save = async () => {
    const found = validateBrief({ ...form, slug: "" });
    setErrors(found);
    if (Object.keys(found).length) return null;
    return run("save", async () => {
      const next = await patch(`${vbase(v)}/brief`, toPayload(form));
      refreshAfter(next);
      toast(next.generation_status === "needs_regeneration" ? "ذخیره شد؛ ساختار عوض شده و باید دوباره تولید شود." : "پیش‌نویس ذخیره شد.", next.generation_status === "needs_regeneration" ? "warn" : "ok");
      return next;
    });
  };
  const generate = () =>
    run("generate", async () => {
      if (dirty && !(await save())) return;
      const next = await post(`${vbase(v)}/generate`);
      refreshAfter(next);
      toast("تولید در پس‌زمینه شروع شد؛ می‌توانی صفحه را ترک کنی.", "info");
    });
  const publish = () =>
    run("publish", async () => {
      setPublishError(null);
      if (dirty && !(await save())) return;
      try {
        const result = await post(`${vbase(v)}/publish`);
        refreshAfter(result.course);
        invalidate(AK.rag(v.course_id, v.version_number));
        toast(`نسخه‌ی ${fa(v.version_number)} منتشر شد؛ ${fa(result.index_changes)} تغییر در صف پایگاه دانش رفت.`);
      } catch (error) {
        setPublishError(error.message);
      }
    });
  const revise = () =>
    run("revise", async () => {
      const next = await post(`/api/admin/courses/${v.course_id}/revisions`);
      refreshAfter(next);
      toast("کپی پیش‌نویس ساخته شد. یادگیرنده‌های فعلی روی نسخه‌ی خودشان می‌مانند.");
      go({ name: "admin-studio", courseId: next.course_id, version: next.version_number });
    });
  const courseAction = (action, message, tone) =>
    run(action, async () => {
      await setCourseState(v, action);
      toast(message, tone);
      return true;
    });
  const publishBlocked = generating || ["not_requested", "needs_regeneration", "failed"].includes(v.generation_status) || !v.modules.length;

  return (
    <div className="stack">
      <div className="studio-head">
        <button className="icon-btn" onClick={() => go({ name: "admin-studio" })} aria-label="بازگشت به فهرست">
          <ArrowLeft style={{ transform: "scaleX(-1)" }} />
        </button>
        <h1>
          {v.course_title}
          <span className={`badge ${published ? "badge-ok" : versionState(v)[1]}`}>
            نسخه‌ی {fa(v.version_number)} | {versionState(v)[0]}
          </span>
        </h1>
        {published ? (
          <button className="btn btn-primary" onClick={revise} disabled={!!busy}>
            <Copy /> ویرایش با نسخه جدید
          </button>
        ) : (
          <>
            <button className="btn btn-soft" onClick={save} disabled={!dirty || !!busy || generating}>
              <Save /> {busy === "save" ? "در حال ذخیره…" : "ذخیره‌ی پیش‌نویس"}
            </button>
            <button className="btn btn-primary" onClick={publish} disabled={publishBlocked || !!busy} title={publishBlocked ? "اول تولید را کامل کن" : undefined}>
              <Rocket /> {busy === "publish" ? "در حال انتشار…" : "انتشار"}
            </button>
          </>
        )}
      </div>
      <div className="seg" role="tablist" aria-label="بخش‌های استودیو" style={{ justifySelf: "start" }}>
        {[
          ["course", "دوره"],
          ["overview", "معرفی"],
          ["images", "عکس"],
          ["video", "ویدیو"],
          ["versions", "نسخه‌ها"],
        ].map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => (key === "images" ? go({ name: "admin-images" }) : setTab(key))}>
            {label}
          </button>
        ))}
      </div>
      {publishError && (
        <Callout tone="err" title="منتشر نشد">
          {publishError}
        </Callout>
      )}
      {published && (
        <Callout tone="info">
          نسخه‌ی منتشرشده تغییرناپذیر است. برای تغییر، «ویرایش با نسخه جدید» را بزن؛ یادگیرنده‌های فعلی روی نسخه‌ی خودشان می‌مانند.
        </Callout>
      )}
      {v.generation_status === "needs_regeneration" && (
        <Callout tone="warn" title="نیازمند تولید دوباره">
          فیلدهای ساختاری (موضوع، مخاطب، گروه هدف، سطح یا تعداد سرفصل) عوض شده‌اند. تا تولید دوباره، انتشار ممکن نیست.{" "}
          <button className="btn btn-sm btn-soft" onClick={generate} disabled={!!busy}>
            <RefreshCw /> تولید دوباره
          </button>
        </Callout>
      )}
      {v.generation_status === "failed" && (
        <Callout tone="err" title="تولید ناموفق">
          {v.generation_error || "تولید کامل نشد."}{" "}
          <button className="btn btn-sm btn-soft" onClick={generate} disabled={!!busy}>
            <RefreshCw /> تلاش دوباره
          </button>
        </Callout>
      )}
      {tab === "course" && (
        <div className="studio">
          <Panel title="جزئیات دوره">
            <div className="cover" style={{ marginBlockEnd: "1rem" }}>
              <Landscape hue={hue} seed={hue} />
              <span className="chip">
                <ImagePlus size={13} /> جلد رویه‌ای از رنگ دوره
              </span>
            </div>
            <BriefForm b={form} set={setForm} errors={errors} readOnly={published || generating} />
          </Panel>
          <div className="stack">
            {(generating || v.generation_progress) && <GenPanel v={v} />}
            <Panel
              title="ساختار دوره"
              action={
                <span className="muted" style={{ fontSize: "var(--t-micro)" }}>
                  {fa(v.modules.length)} سرفصل | {fa(stageCount)} مرحله
                </span>
              }
            >
              {v.modules.length ? (
                <div className="stack" style={{ gap: ".55rem" }}>
                  {v.modules.map((m, i) => (
                    <div key={m.id} className="mod-card mat mat-raised">
                      <span className="thumb">
                        <Landscape hue={hue + i * 14} seed={hue + i} />
                      </span>
                      <div className="list-main">
                        <small className="k">سرفصل {fa(m.module_number)}</small>
                        <b>{m.title}</b>
                        <small>
                          {fa(m.stages.length)} مرحله{m.tags?.[0] ? ` | ${m.tags[0]}` : ""} | {fa(m.learning_objectives.length)} هدف
                        </small>
                      </div>
                      <ModuleMenu module={m} onEdit={() => setModuleDialog(m)} onStage={(stage) => setStageDialog({ module: m, stage })} readOnly={published} />
                    </div>
                  ))}
                  {!published && !generating && (
                    <button
                      className="add-row mat mat-raised"
                      onClick={() => {
                        setForm({ ...form, sections: Math.min(20, Number(form.sections) + 1) });
                        toast("تعداد سرفصل یکی بیشتر شد؛ برای ساخت آن «ذخیره» و بعد «تولید دوباره» را بزن.", "info");
                      }}
                    >
                      <Plus size={16} /> افزودن سرفصل
                    </button>
                  )}
                </div>
              ) : (
                <Empty
                  icon={<Sparkles />}
                  title={generating ? "در حال تولید…" : "هنوز سرفصلی تولید نشده"}
                  text="هوش مصنوعی از روی مشخصات، سرفصل‌ها و مراحل را می‌سازد."
                  action={
                    generating ? undefined : (
                      <button className="btn btn-primary btn-sm" onClick={generate} disabled={!!busy}>
                        تولید
                      </button>
                    )
                  }
                />
              )}
              {!published && !generating && v.modules.length > 0 && v.generation_status !== "needs_regeneration" && (
                <button className="btn btn-ghost btn-sm" style={{ marginTop: ".7rem" }} onClick={() => confirmRegenerate() && generate()} disabled={!!busy}>
                  <RefreshCw /> تولید دوباره‌ی کل محتوا
                </button>
              )}
            </Panel>
            {published && <RagPanel v={v} />}
            <div className="motto">
              محتوای خوب زندگی‌ها را عوض می‌کند. ادامه بده ✨<Sprig flowers={8} />
            </div>
          </div>
        </div>
      )}
      {tab === "overview" && (
        <Panel title="صفحه‌ی معرفی (ساخته‌شده هنگام تولید)">
          <dl className="kv">
            <dt>خلاصه</dt>
            <dd>{overview.summary || "—"}</dd>
            <dt>توضیح</dt>
            <dd>{overview.description || "—"}</dd>
            <dt>نتایج یادگیری</dt>
            <dd>{(overview.learning_outcomes || []).join(" | ") || "—"}</dd>
            <dt>نتایج شغلی</dt>
            <dd>{(overview.career_outcomes || []).join(" | ") || "—"}</dd>
            <dt>زندگی روزمره</dt>
            <dd>{(overview.daily_life_outcomes || []).join(" | ") || "—"}</dd>
            <dt>آزمون نهایی</dt>
            <dd>{v.requires_final_exam ? overview.final_exam_label || "آزمون نهایی" : "ندارد؛ دوره بعد از آخرین مرحله مستقیم تکمیل می‌شود"}</dd>
          </dl>
          {published && (
            <a className="btn btn-soft btn-sm" style={{ marginTop: "1rem" }} href={`/app/courses/${encodeURIComponent(v.course_slug)}`} target="_blank" rel="noreferrer">
              <ExternalLink /> دیدن صفحه‌ی معرفی
            </a>
          )}
        </Panel>
      )}
      {tab === "video" && (
        <Panel>
          <Empty icon={<Video />} title="تولید ویدیو در دسترس نیست" text="درگاه هوش مصنوعی فعلی مدل ویدیو ندارد. ویدیوی آماده از راه گیت در landing/course-media/ قرار می‌گیرد و در محتوای مرحله با بلوک video اضافه می‌شود." />
        </Panel>
      )}
      {tab === "versions" && (
        <Panel title="نسخه‌ها و نمایش">
          <div className="list">
            {otherVersions.map((x) => (
              <button
                key={x.id}
                className="list-row"
                onClick={() => go({ name: "admin-studio", courseId: x.course_id, version: x.version_number })}
                aria-current={x.id === v.id ? "true" : undefined}
              >
                <CircleDot size={16} className={x.id === v.id ? "" : "muted"} />
                <span className="list-main">
                  <b>نسخه‌ی {fa(x.version_number)}</b>
                  <small>{x.status === "published" ? `منتشرشده ${x.published_at ? jalali(x.published_at) : ""}` : `پیش‌نویس | ساخته‌شده ${x.created_at ? ago(x.created_at) : ""}`}</small>
                </span>
                {versionBadge(x)}
              </button>
            ))}
          </div>
          <div className="row" style={{ marginTop: "1rem" }}>
            {v.course_status !== "deleted" && otherVersions.some((x) => x.status === "published") && (
              <button
                className="btn btn-soft btn-sm"
                disabled={!!busy}
                onClick={() =>
                  v.course_status === "inactive"
                    ? courseAction("reactivate", "دوره دوباره برای یادگیرنده‌ها نمایش داده می‌شود.")
                    : courseAction("deactivate", "دوره از فهرست یادگیرنده‌ها پنهان شد.", "info")
                }
              >
                <Power /> {v.course_status === "inactive" ? "فعال کردن دوره" : "غیرفعال کردن دوره"}
              </button>
            )}
            {v.course_status === "deleted" ? (
              <button className="btn btn-soft btn-sm" disabled={!!busy} onClick={() => courseAction("restore", "دوره بازیابی شد.")}>
                <ArchiveRestore /> بازیابی دوره
              </button>
            ) : (
              <button
                className="btn btn-danger btn-sm"
                disabled={!!busy}
                onClick={() =>
                  courseAction("soft-delete", "دوره حذف شد (نرم)؛ از فهرست «حذف‌شده‌ها» بازیابی می‌شود.", "warn").then((ok) => ok && go({ name: "admin-studio" }))
                }
              >
                <Trash /> حذف دوره
              </button>
            )}
          </div>
        </Panel>
      )}
      {moduleDialog && <ModuleDialog v={v} m={moduleDialog} readOnly={published} onClose={() => setModuleDialog(null)} />}
      {stageDialog && <StageDialog v={v} m={stageDialog.module} stage={stageDialog.stage} readOnly={published} onClose={() => setStageDialog(null)} />}
    </div>
  );
}

// A second generation replaces the current draft content; the old studio asked first too.
const confirmRegenerate = () => window.confirm("محتوای فعلی این پیش‌نویس با نسخه‌ی تازه‌ی هوش مصنوعی جایگزین می‌شود. ادامه می‌دهی؟");

function ModuleMenu({ module, onEdit, onStage, readOnly }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    const onClick = () => setOpen(false);
    document.addEventListener("keydown", onKey);
    const timer = setTimeout(() => document.addEventListener("click", onClick), 0);
    return () => (document.removeEventListener("keydown", onKey), document.removeEventListener("click", onClick), clearTimeout(timer));
  }, [open]);
  return (
    <div className="pop">
      <button className="icon-btn" aria-label="کارهای سرفصل" aria-expanded={open} onClick={() => setOpen(!open)}>
        <EllipsisVertical />
      </button>
      {open && (
        <div className="menu menu-end" role="menu" style={{ minWidth: "14rem" }}>
          <button role="menuitem" className="menu-item" onClick={onEdit}>
            <b>{readOnly ? "دیدن سرفصل" : "ویرایش سرفصل"}</b>
            <small>عنوان، توضیح، اهداف، برچسب</small>
          </button>
          <p className="menu-title">مراحل (JSON)</p>
          <div className="row" style={{ padding: "0 .6rem .5rem", gap: ".25rem" }}>
            {module.stages.map((stage) => (
              <button key={stage.id} className="chip" title={`${stage.title} | ${STAGE_LABELS[stage.template_code] || stage.template_code}`} onClick={() => onStage(stage)}>
                {fa(stage.stage_number)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ModuleDialog({ v, m, readOnly, onClose }) {
  const { toast } = useStore();
  const [form, setForm] = useState({
    title: m.title,
    description: m.description || "",
    objectives: (m.learning_objectives || []).join("\n"),
    tags: (m.tags || []).join("\n"),
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lines = (text) => text.split("\n").map((x) => x.trim()).filter(Boolean);
  const save = async () => {
    if (form.title.trim().length < 3) return setError("عنوان سرفصل حداقل ۳ حرف باشد.");
    setBusy(true);
    try {
      const next = await patch(`${vbase(v)}/modules/${m.id}`, {
        title: form.title.trim(),
        description: form.description.trim(),
        learning_objectives: lines(form.objectives),
        tags: lines(form.tags),
      });
      refreshAfter(next);
      toast("سرفصل ذخیره شد.");
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      title={readOnly ? "سرفصل (فقط خواندنی)" : "ویرایش سرفصل"}
      onClose={onClose}
      icon={
        <span className="tile tile-lav">
          <Pencil />
        </span>
      }
    >
      <Form onSubmit={save}>
        <Field label="عنوان" error={error || undefined}>
          <input className="input" readOnly={readOnly} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </Field>
        <Field label="توضیح">
          <textarea className="textarea" readOnly={readOnly} rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </Field>
        <Field label="اهداف" hint="هر خط یک هدف">
          <textarea className="textarea" readOnly={readOnly} rows={3} value={form.objectives} onChange={(e) => setForm({ ...form, objectives: e.target.value })} />
        </Field>
        <Field label="برچسب‌ها" hint="هر خط یک برچسب؛ اولی در نقشه‌ی دوره نمایش داده می‌شود">
          <textarea className="textarea" readOnly={readOnly} rows={2} value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
        </Field>
        {!readOnly && (
          <button className="btn btn-primary" type="submit" disabled={busy}>
            <Save /> {busy ? "در حال ذخیره…" : "ذخیره‌ی سرفصل"}
          </button>
        )}
      </Form>
    </Dialog>
  );
}

function StageDialog({ v, m, stage, readOnly, onClose }) {
  const { toast } = useStore();
  const original = JSON.stringify(stage.content, null, 2);
  const originalKey = stage.evaluation_config ? JSON.stringify(stage.evaluation_config, null, 2) : "";
  const [title, setTitle] = useState(stage.title);
  const [content, setContent] = useState(original);
  const [evaluation, setEvaluation] = useState(originalKey);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    let parsed, parsedKey;
    try {
      parsed = JSON.parse(content);
    } catch (err) {
      return setError(`JSON معتبر نیست: ${err.message}`);
    }
    if (typeof parsed.intro !== "string" || !Array.isArray(parsed.blocks)) return setError("ساختار باید «intro» (متن) و «blocks» (آرایه) داشته باشد.");
    if (evaluation.trim()) {
      try {
        parsedKey = JSON.parse(evaluation);
      } catch (err) {
        return setError(`JSON کلید آزمونک معتبر نیست: ${err.message}`);
      }
    }
    setBusy(true);
    try {
      const body = { title: title.trim() || stage.title, content: parsed };
      if (parsedKey !== undefined) body.evaluation_config = parsedKey;
      const next = await patch(`${vbase(v)}/stages/${stage.id}`, body);
      refreshAfter(next);
      toast("محتوای مرحله ذخیره شد.");
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      wide
      title={`سرفصل ${fa(m.module_number)} | مرحله‌ی ${fa(stage.stage_number)}: ${stage.title}`}
      onClose={onClose}
      icon={
        <span className="tile tile-peach">
          <FileBraces />
        </span>
      }
    >
      <div className="form">
        <Callout tone="info">محتوای مرحله با JSON ویرایش می‌شود. ساختار: intro (متن)، blocks (آرایه)، activity (اختیاری).</Callout>
        <Field label="عنوان مرحله">
          <input className="input" readOnly={readOnly} value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="محتوا (JSON)" error={error ?? undefined}>
          <textarea className="textarea code" readOnly={readOnly} value={content} onChange={(e) => setContent(e.target.value)} spellCheck={false} />
        </Field>
        {(stage.template_code === "module_assessment" || originalKey) && (
          <Field label="کلید آزمونک و تنظیم ارزیابی (فقط سرور؛ به مرورگر یادگیرنده فرستاده نمی‌شود)">
            <textarea className="textarea code" style={{ minHeight: "6rem" }} readOnly={readOnly} value={evaluation} onChange={(e) => setEvaluation(e.target.value)} spellCheck={false} />
          </Field>
        )}
        {!readOnly && (
          <div className="row">
            <button className="btn btn-primary" onClick={save} disabled={busy}>
              <Save /> {busy ? "در حال ذخیره…" : "ذخیره"}
            </button>
            <button className="btn btn-ghost" onClick={() => (setContent(original), setEvaluation(originalKey), setTitle(stage.title), setError(null))}>
              <X /> برگرداندن تغییرها
            </button>
          </div>
        )}
      </div>
    </Dialog>
  );
}

const timeFormat = new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

function GenPanel({ v }) {
  const generating = v.generation_status === "generating";
  const progress = v.generation_progress;
  const ratio = progress?.total ? progress.done / progress.total : 0;
  const started = progress?.started_at ? new Date(progress.started_at).getTime() : null;
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!generating) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [generating]);
  const meta = generating
    ? { status: "processing", model: v.generation_model || "GPT-4.1", expect: "۸ تا ۱۰ دقیقه برای ۷ سرفصل" }
    : { status: v.generation_status === "failed" ? "review" : "ready", model: v.generation_model, ms: started && v.generated_at ? new Date(v.generated_at).getTime() - started : undefined, at: v.generated_at };
  return (
    <Panel
      title="تولید با هوش مصنوعی"
      action={
        generating ? (
          <span className="badge badge-info">
            <LoaderCircle className="spin" /> {progress ? `${fa(Math.round(ratio * 100))}٪` : "در حال اجرا"}
          </span>
        ) : v.generation_status === "failed" ? (
          <span className="badge badge-err">ناموفق</span>
        ) : (
          <span className="badge badge-ok">
            <Check /> تمام شد
          </span>
        )
      }
    >
      <AIBar meta={meta} />
      <div style={{ margin: ".7rem 0" }}>
        <Bar value={generating ? Math.max(4, ratio * 100) : 100} label="پیشرفت تولید" />
      </div>
      {progress?.log?.length ? (
        <ul className="gen-log" style={{ listStyle: "none", padding: 0 }}>
          {progress.log.map((item, i) => (
            <li key={i}>
              <span className="muted ltr">{timeFormat.format(new Date(item.at))}</span>
              <span>{fa(item.text)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted" style={{ fontSize: "var(--t-small)" }}>
          {generating ? "در حال ساخت طرح کلی و سرفصل‌ها…" : "گزارش جزئیات تولید قبلی در دسترس نیست."}
        </p>
      )}
      <p className="muted" style={{ fontSize: "var(--t-micro)", marginTop: ".5rem" }}>
        {generating && started ? `زمان سپری‌شده: ${fa(Math.floor((now - started) / 60000))} دقیقه | ` : ""}تولید در پس‌زمینه است؛ می‌توانی صفحه را ترک کنی.
      </p>
    </Panel>
  );
}

function RagPanel({ v }) {
  const { toast } = useStore();
  const key = AK.rag(v.course_id, v.version_number);
  const rag = useCached(key);
  const r = rag.data;
  useEffect(() => {
    if (!r || !(r.queued_job_count + r.running_job_count + r.retry_job_count)) return;
    const timer = setInterval(() => rag.reload().catch(() => {}), 4000);
    return () => clearInterval(timer);
  }, [r?.queued_job_count, r?.running_job_count, r?.retry_job_count]);
  const retry = async () => {
    try {
      setCached(key, await post(`${key.replace("rag-status", "rag-retry-failed")}`));
      toast("کارهای ناموفق دوباره در صف ایندکس رفتند.", "info");
    } catch (error) {
      toast(error.message, "err");
    }
  };
  return (
    <Panel title="پایگاه دانش (RAG)" action={<RagBadge v={v} />}>
      {!r ? (
        <Skel lines={3} />
      ) : (
        <div className="stack" style={{ gap: ".35rem", fontSize: "var(--t-micro)" }}>
          {[
            ["سند", r.document_count],
            ["کار موفق", r.succeeded_job_count],
            ["در صف یا در حال اجرا", r.queued_job_count + r.running_job_count],
            ["در انتظار تلاش دوباره", r.retry_job_count],
            ["ناموفق", r.failed_job_count],
          ].map(([label, count]) => (
            <div key={label} className="row" style={{ justifyContent: "space-between" }}>
              <span>{label}</span>
              <span className="muted">{fa(count)}</span>
            </div>
          ))}
          {r.last_error && <Callout tone="err">{r.last_error}</Callout>}
          <p className="muted">تکه‌های ۹۰۰ نویسه‌ای با ۱۲۰ هم‌پوشانی | بردار ۳۰۷۲ بُعدی | عکس، ویدیو و کلید آزمونک وارد سند نمی‌شوند.</p>
          {r.failed_job_count > 0 && (
            <button className="btn btn-soft btn-sm" style={{ justifySelf: "start" }} onClick={retry}>
              <RefreshCw /> ایندکس دوباره
            </button>
          )}
        </div>
      )}
    </Panel>
  );
}
