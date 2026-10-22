// Image studio: generate a draft image for a stage, review/regenerate, publish into the stage.
import { useMemo, useState } from "react";
import { Check, ImagePlus, LoaderCircle, RefreshCw, Rocket, Trash, Undo2 } from "lucide-react";
import { del, post } from "../../lib/api.js";
import { invalidate, useCached } from "../../lib/cache.js";
import { AK, useAdminCourses } from "../../lib/admin.js";
import { fa, secs } from "../../lib/format.js";
import { useStore } from "../../lib/store.jsx";
import { Dialog, Empty, Field, Form, Panel, Skel } from "../../ui/kit.jsx";

const IMAGE_SIZES = [
  ["square", "مربعی"],
  ["landscape", "افقی ۳:۲"],
  ["portrait", "عمودی ۲:۳"],
];

function ImgPic({ im }) {
  return im.status === "generating" ? (
    <div className="pic">
      <div className="skel" style={{ width: "100%", height: "100%", borderRadius: 0 }} />
    </div>
  ) : (
    <div className="pic">
      <img alt={im.prompt} src={`${im.src}?v=${encodeURIComponent(im.revision || "")}`} loading="lazy" />
    </div>
  );
}

const where = (im) => `${im.course_title} | ن${fa(im.version_number)} | ${im.module_title} | مرحله‌ی ${fa(im.stage_number)}`;

export function Images() {
  const { toast } = useStore();
  const courses = useAdminCourses();
  const images = useCached(AK.images);
  const versions = useMemo(() => (courses.data || []).filter((v) => v.modules.length && v.course_status !== "deleted"), [courses.data]);
  const [versionId, setVersionId] = useState("");
  const [moduleId, setModuleId] = useState("");
  const [stageId, setStageId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState("landscape");
  const [error, setError] = useState("");
  const [pending, setPending] = useState([]);
  const [approveOpen, setApproveOpen] = useState(false);

  const version = versions.find((v) => String(v.id) === String(versionId)) || versions[0];
  const module = version?.modules.find((m) => String(m.id) === String(moduleId)) || version?.modules[0];
  const stage = module?.stages.find((s) => String(s.id) === String(stageId)) || module?.stages[1] || module?.stages[0];
  const all = images.data || [];
  const drafts = [...pending, ...all.filter((im) => im.status !== "published")];
  const published = all.filter((im) => im.status === "published");

  const generate = async () => {
    if (!version || !module || !stage) return;
    if (prompt.trim().length < 8) return setError("پرامپت را کمی کامل‌تر بنویس (حداقل ۸ نویسه)؛ مثلاً چه کسی، کجا، چه کاری.");
    setError("");
    const temp = {
      id: `p${Date.now()}`,
      status: "generating",
      prompt: prompt.trim(),
      course_title: version.course_title,
      version_number: version.version_number,
      module_title: module.title,
      stage_number: stage.stage_number,
    };
    setPending((list) => [temp, ...list]);
    toast("تولید عکس شروع شد؛ معمولاً ۴۵ تا ۱۵۵ ثانیه طول می‌کشد.", "info");
    const started = Date.now();
    try {
      await post(`/api/admin/courses/${version.course_id}/versions/${version.version_number}/images`, { module_id: module.id, stage_id: stage.id, prompt: prompt.trim(), size });
      setPrompt("");
      toast(`عکس آماده شد (${secs(Date.now() - started)}) و منتظر تأیید است.`);
    } catch (err) {
      toast(err.message, "err");
    } finally {
      setPending((list) => list.filter((x) => x.id !== temp.id));
      invalidate(AK.images);
    }
  };

  const unpublish = async (im) => {
    try {
      await del(`/api/admin/courses/${im.course_id}/versions/${im.version_number}/stages/${im.stage_id}/images/${im.id}`);
      invalidate(AK.images, AK.courses, AK.version(im.course_id, im.version_number));
      toast("عکس از مرحله برداشته شد و دوباره پیش‌نویس است.", "info");
    } catch (err) {
      toast(err.message, "err");
    }
  };

  return (
    <div className="stack">
      <div className="studio-head">
        <h1>تولید عکس و ویدیو</h1>
        <button className="btn btn-soft" onClick={() => setApproveOpen(true)}>
          <Check /> تأیید ({fa(drafts.filter((d) => d.status !== "generating").length)})
        </button>
      </div>
      <div className="seg" role="tablist" style={{ justifySelf: "start" }}>
        <button role="tab" aria-selected>
          عکس
        </button>
        <button role="tab" disabled title="درگاه فعلی مدل تولید ویدیو ندارد">
          ویدیو
        </button>
      </div>
      <div className="studio">
        <Panel title="عکس تازه">
          {courses.loading && !courses.data ? (
            <Skel lines={6} />
          ) : versions.length ? (
            <Form onSubmit={generate}>
              <Field label="دوره و نسخه">
                <select className="select" value={version?.id ?? ""} onChange={(e) => (setVersionId(e.target.value), setModuleId(""), setStageId(""))}>
                  {versions.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.course_title} | نسخه‌ی {fa(v.version_number)} ({v.status === "published" ? "منتشرشده" : "پیش‌نویس"})
                    </option>
                  ))}
                </select>
              </Field>
              <div className="form-row">
                <Field label="سرفصل">
                  <select className="select" value={module?.id ?? ""} onChange={(e) => (setModuleId(e.target.value), setStageId(""))}>
                    {version?.modules.map((m) => (
                      <option key={m.id} value={m.id}>
                        {fa(m.module_number)}. {m.title}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="مرحله">
                  <select className="select" value={stage?.id ?? ""} onChange={(e) => setStageId(e.target.value)}>
                    {module?.stages.map((s) => (
                      <option key={s.id} value={s.id}>
                        {fa(s.stage_number)}. {s.title}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field
                label="پرامپت"
                req
                error={error || undefined}
                hint={`با نام دوره، سرفصل، مرحله، متن درس (${version?.status === "published" ? "از پایگاه دانش" : "از متن مرحله"}) و سبک ثابت زیتو ترکیب می‌شود.`}
              >
                <textarea className="textarea" rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="مثلاً: کارشناس فروش پشت میز، در حال آماده کردن برگه‌ی تماس" />
              </Field>
              <Field label="اندازه">
                <div className="seg" role="radiogroup">
                  {IMAGE_SIZES.map(([key, label]) => (
                    <button key={key} type="button" role="radio" aria-checked={size === key} onClick={() => setSize(key)}>
                      {label}
                    </button>
                  ))}
                </div>
              </Field>
              <button className="btn btn-primary" type="submit">
                <ImagePlus /> تولید عکس
              </button>
              <p className="muted" style={{ fontSize: "var(--t-micro)" }}>
                مدل <span className="ltr">Gemini-3.1-Flash-Image</span> | عکس اول پیش‌نویس است و تا انتشار به یادگیرنده نشان داده نمی‌شود.
              </p>
            </Form>
          ) : (
            <Empty icon={<ImagePlus />} title="دوره‌ای برای عکس نیست" text="اول یک دوره بساز و تولید کن." />
          )}
        </Panel>
        <div className="stack">
          <Panel
            title="پیش‌نویس‌ها"
            action={
              <span className="muted" style={{ fontSize: "var(--t-micro)" }}>
                {fa(drafts.length)} عکس
              </span>
            }
          >
            {images.loading && !images.data ? (
              <Skel lines={4} />
            ) : drafts.length ? (
              <div className="img-grid">
                {drafts.map((im) => (
                  <div key={im.id} className="img-card mat mat-raised">
                    <ImgPic im={im} />
                    <small>{where(im)}</small>
                    <span className="row" style={{ justifyContent: "space-between" }}>
                      {im.status === "generating" ? (
                        <span className="badge badge-info">
                          <LoaderCircle className="spin" /> در حال تولید
                        </span>
                      ) : (
                        <span className="badge badge-warn">پیش‌نویس</span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <Empty icon={<ImagePlus />} title="پیش‌نویسی نیست" text="پرامپت بنویس و «تولید عکس» را بزن. عکس‌ها اینجا منتظر تأیید می‌مانند." />
            )}
          </Panel>
          <Panel title="منتشرشده‌ها">
            {published.length ? (
              <div className="img-grid">
                {published.map((im) => (
                  <div key={im.id} className="img-card mat mat-raised">
                    <ImgPic im={im} />
                    <small>{where(im)}</small>
                    <button className="btn btn-ghost btn-sm" onClick={() => unpublish(im)}>
                      <Undo2 /> برداشتن از مرحله
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ fontSize: "var(--t-small)" }}>
                هنوز عکسی منتشر نشده. عکس منتشرشده به ابتدای محتوای مرحله اضافه می‌شود؛ حتی روی دوره‌ی منتشرشده، بدون نسخه‌ی جدید.
              </p>
            )}
          </Panel>
        </div>
      </div>
      {approveOpen && <ApproveDialog drafts={all.filter((im) => im.status === "draft")} onClose={() => setApproveOpen(false)} />}
    </div>
  );
}

function ApproveDialog({ drafts, onClose }) {
  const { toast } = useStore();
  const [selected, setSelected] = useState(() => Object.fromEntries(drafts.map((d) => [d.id, true])));
  const [prompts, setPrompts] = useState({});
  const [busy, setBusy] = useState({});
  const chosen = drafts.filter((d) => selected[d.id]).map((d) => d.id);
  const mark = (id, value) => setBusy((b) => ({ ...b, [id]: value }));
  const regenerate = async (im) => {
    mark(im.id, "regen");
    try {
      await post(`/api/admin/course-images/${im.id}/regenerate`, { prompt: prompts[im.id] ?? im.prompt, size: im.size });
      invalidate(AK.images);
      toast("عکس تازه ساخته شد.");
    } catch (err) {
      toast(err.message, "err");
    } finally {
      mark(im.id, null);
    }
  };
  const remove = async (im) => {
    mark(im.id, "del");
    try {
      await del(`/api/admin/course-images/${im.id}`);
      invalidate(AK.images);
    } catch (err) {
      toast(err.message, "err");
    } finally {
      mark(im.id, null);
    }
  };
  const publish = async () => {
    try {
      await post("/api/admin/course-images/publish", { asset_ids: chosen });
      invalidate(AK.images, AK.courses);
      toast(`${fa(chosen.length)} عکس منتشر شد.`);
      onClose();
    } catch (err) {
      toast(err.message, "err");
    }
  };
  return (
    <Dialog
      wide
      title="تأیید و انتشار عکس‌ها"
      onClose={onClose}
      icon={
        <span className="tile tile-mint">
          <Check />
        </span>
      }
    >
      {drafts.length ? (
        <div className="stack">
          {drafts.map((im) => (
            <div key={im.id} className="mat mat-raised row" style={{ padding: ".6rem", alignItems: "flex-start", flexWrap: "nowrap" }}>
              <button role="checkbox" aria-checked={!!selected[im.id]} className="check-row" style={{ width: "auto" }} onClick={() => setSelected({ ...selected, [im.id]: !selected[im.id] })} aria-label="انتخاب برای انتشار">
                <span className="check-box">{selected[im.id] && <Check />}</span>
              </button>
              <div style={{ width: "6rem", flex: "none" }}>
                <ImgPic im={busy[im.id] === "regen" ? { ...im, status: "generating" } : im} />
              </div>
              <div className="stack" style={{ gap: ".4rem", flex: 1 }}>
                <small className="muted">{where(im)}</small>
                <input className="input" value={prompts[im.id] ?? im.prompt} onChange={(e) => setPrompts({ ...prompts, [im.id]: e.target.value })} aria-label="پرامپت" />
                <div className="row">
                  <button className="btn btn-soft btn-sm" disabled={!!busy[im.id]} onClick={() => regenerate(im)}>
                    <RefreshCw /> {busy[im.id] === "regen" ? "در حال ساخت…" : "تولید دوباره"}
                  </button>
                  <button className="btn btn-ghost btn-sm" disabled={!!busy[im.id]} onClick={() => remove(im)}>
                    <Trash /> حذف
                  </button>
                </div>
              </div>
            </div>
          ))}
          <button className="btn btn-primary" disabled={!chosen.length} onClick={publish}>
            <Rocket /> انتشار {fa(chosen.length)} عکس انتخابی
          </button>
        </div>
      ) : (
        <Empty icon={<ImagePlus />} title="عکس آماده‌ای برای تأیید نیست" text="عکس‌های در حال تولید بعد از آماده شدن اینجا می‌آیند." />
      )}
    </Dialog>
  );
}
