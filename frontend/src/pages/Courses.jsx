// Course catalog (with module preview on hover/long-press) and the course overview page.
import { useRef, useState } from "react";
import { ArrowLeft, Award, BookOpen, Briefcase, Clock, GraduationCap, Heart, Layers, Lightbulb, Signal, Sparkles } from "lucide-react";
import { useCached } from "../lib/cache.js";
import { fa, hueOf, pct } from "../lib/format.js";
import { K, refreshLearning, selectCourse, useCourses, useOverview } from "../lib/learner.js";
import { profileComplete, useStore } from "../lib/store.jsx";
import { Drop, HeroScene, Landscape } from "../ui/art.jsx";
import { Empty, Panel, Skel } from "../ui/kit.jsx";

export const hoursOf = (course) =>
  course?.estimated_learning_hours ?? (course?.estimated_learning_minutes ? Math.max(1, Math.round(course.estimated_learning_minutes / 60)) : null);

export function useEnroll() {
  const { go, toast, profile } = useStore();
  const overview = useOverview();
  return async (courseId) => {
    if (!profileComplete(profile)) return go({ name: "onboarding" });
    const existing = overview.data?.enrollments?.find((e) => e.course_id === courseId);
    try {
      const enrollment = await selectCourse(courseId);
      refreshLearning(enrollment.id);
      toast(existing ? "این دوره دوره‌ی جاری‌ات شد؛ پیشرفتت سر جایش است." : "ثبت‌نام انجام شد. اولین مرحله باز است.");
      go({ name: existing?.status === "completed" ? "certs" : existing?.status === "awaiting_final" ? "final" : "lesson" });
    } catch (error) {
      toast(error.message, "err");
    }
  };
}

function CourseCard({ course, enrollment, onPreview, onLeave }) {
  const { go } = useStore();
  const detail = useCached(K.course(course.slug));
  const info = detail.data;
  const hue = hueOf(course.id);
  const hours = hoursOf(info);
  const percent = enrollment?.total_stage_count ? (enrollment.completed_stage_count / enrollment.total_stage_count) * 100 : 0;
  return (
    <button
      className="course-card mat mat-panel"
      onClick={() => go({ name: "course", slug: course.slug })}
      onMouseEnter={(e) => info && onPreview(info, e.currentTarget, 340)}
      onMouseLeave={onLeave}
      onTouchStart={(e) => info && onPreview(info, e.currentTarget, 520)}
      onTouchEnd={onLeave}
      onFocus={(e) => info && onPreview(info, e.currentTarget, 600)}
      onBlur={onLeave}
    >
      <span className="course-cover">
        <Landscape hue={hue} seed={hue} />
        {enrollment ? (
          <span className={`badge ${enrollment.status === "completed" ? "badge-ok" : "badge-accent"}`}>
            {enrollment.status === "completed" ? "تکمیل‌شده" : `${pct(percent)} پیش رفته‌ای`}
          </span>
        ) : (
          info?.level && <span className="badge badge-quiet">{info.level}</span>
        )}
      </span>
      <span className="course-body">
        <h3>{course.title}</h3>
        <p>{info?.summary ?? "…"}</p>
        <span className="meta-row">
          <span>
            <Layers /> {fa(course.module_count)} سرفصل
          </span>
          {hours && (
            <span>
              <Clock /> {fa(hours)} ساعت
            </span>
          )}
          {course.requires_final_exam && (
            <span>
              <Award /> گواهی
            </span>
          )}
        </span>
      </span>
    </button>
  );
}

export function Courses() {
  const courses = useCourses();
  const overview = useOverview();
  const [preview, setPreview] = useState(null);
  const timer = useRef(0);
  const show = (info, el, delay) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const rect = el.getBoundingClientRect();
      const x = Math.min(innerWidth - 16 - 336, Math.max(16, rect.left + rect.width / 2 - 168));
      setPreview({ info, x, y: Math.min(innerHeight - 260, rect.bottom + 8) });
    }, delay);
  };
  const hide = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setPreview(null), 260);
  };
  const list = courses.data || [];
  const mine = overview.data?.enrollments || [];

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>چه دوره‌ای می‌خواهی انتخاب کنی؟</h1>
          <p>ماوس را روی هر دوره نگه دار (یا روی گوشی فشار طولانی بده) تا سرفصل‌هایش را ببینی.</p>
        </div>
        <Drop size="3.4rem" face />
      </div>
      {courses.loading && !courses.data ? (
        <Skel lines={6} />
      ) : list.length ? (
        <div className="course-grid">
          {list.map((course) => (
            <CourseCard key={course.id} course={course} enrollment={mine.find((e) => e.course_id === course.id)} onPreview={show} onLeave={hide} />
          ))}
        </div>
      ) : (
        <Panel>
          <Empty icon={<BookOpen />} title="فعلاً دوره‌ای منتشر نشده" text="تیم محتوا در حال آماده کردن دوره‌هاست. کمی بعد دوباره سر بزن." />
        </Panel>
      )}
      {preview && (
        <div className="preview-pop" style={{ insetInlineStart: "auto", left: preview.x, top: preview.y }} role="tooltip">
          <b>{preview.info.title}</b>
          <ol>
            {preview.info.modules.map((m) => (
              <li key={m.module_id}>{m.title}</li>
            ))}
          </ol>
          {preview.info.requires_final_exam && <small className="muted">{preview.info.final_exam_label || "آزمون نهایی"}</small>}
        </div>
      )}
    </div>
  );
}

export function CourseOverview({ slug }) {
  const { me, go } = useStore();
  const detail = useCached(K.course(slug));
  const overview = useOverview();
  const enroll = useEnroll();
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
            <button className="btn btn-soft" onClick={() => go({ name: "courses" })}>
              برگشت به دوره‌ها
            </button>
          }
        />
      </Panel>
    );

  const joined = overview.data?.enrollments?.find((e) => e.course_id === course.id);
  const hours = hoursOf(course);
  const stageCount = course.modules.reduce((sum, m) => sum + m.stage_count, 0) || course.module_count * 8;
  const examName = course.final_exam_label || "آزمون نهایی";
  const outcomes = [
    [<Briefcase key="1" />, "peach", "در کار", course.career_outcomes],
    [<Heart key="2" />, "rose", "در زندگی روزمره", course.daily_life_outcomes],
    [<Lightbulb key="3" />, "lav", "در یادگیری", course.learning_outcomes],
  ].filter(([, , , items]) => items?.length);

  return (
    <div className="stack">
      <button className="link-btn" onClick={() => go({ name: "courses" })} style={{ justifySelf: "start" }}>
        <ArrowLeft style={{ transform: "scaleX(-1)" }} /> همه‌ی دوره‌ها
      </button>
      <section className="ov-hero">
        <HeroScene />
        <span className="badge badge-accent" style={{ justifySelf: "start" }}>
          {course.level ? `${course.level} | ` : ""}نسخه‌ی {fa(course.version_number)}
        </span>
        <h1>{course.title}</h1>
        <p>{course.summary}</p>
        <div className="meta-row">
          <span>
            <Layers /> {fa(course.module_count)} سرفصل | {fa(stageCount)} مرحله
          </span>
          {(hours || course.estimated_duration_label) && (
            <span>
              <Clock /> {hours ? `حدود ${fa(hours)} ساعت` : course.estimated_duration_label}
            </span>
          )}
          {course.target_group && (
            <span>
              <Signal /> {course.target_group}
            </span>
          )}
        </div>
        <button className="btn btn-primary btn-lg" style={{ justifySelf: "start", marginTop: ".5rem" }} onClick={() => enroll(course.id)}>
          <Sparkles /> {joined ? "ادامه‌ی مسیر" : "شروع مسیر"}
        </button>
        <Drop size="8rem" face className="ov-hero-drop" />
      </section>
      <Panel title="مقصد این مسیر">
        <p className="soft" style={{ marginBlockEnd: ".8rem" }}>
          {course.description}
        </p>
        <div className="before-after">
          <div className="ba mat mat-raised">
            <small>قبل از دوره</small>
            <b>می‌دانی چه کاری باید بکنی، ولی هر بار از نو حدس می‌زنی.</b>
          </div>
          <ArrowLeft className="muted" />
          <div className="ba mat mat-raised" style={{ background: "linear-gradient(170deg,#efe6fc,#fbe9df)" }}>
            <small>بعد از دوره</small>
            <b>{course.learning_outcomes[0] ?? "یک روش روشن و قابل تکرار داری."}</b>
          </div>
        </div>
      </Panel>
      <Panel title="نقشه و مسیر دوره">
        <div className="road">
          {course.modules.map((m, i) => (
            <div key={m.module_id} className="road-item">
              <span className="road-dot" />
              <div className="mat mat-raised">
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h3>
                    سرفصل {fa(i + 1)}: {m.title}
                  </h3>
                  {m.tag && <span className="badge badge-quiet">{m.tag}</span>}
                </div>
                {m.description && <p>{m.description}</p>}
              </div>
            </div>
          ))}
          {course.requires_final_exam && (
            <div className="road-item">
              <span className="road-dot" style={{ background: "radial-gradient(circle at 35% 30%,#fff,#7fcfae)" }} />
              <div className="mat mat-raised">
                <h3>{examName}</h3>
                <p>سه سؤال تشریحی، تصحیح با هوش مصنوعی، حدنصاب ۷۰ برای گواهی.</p>
              </div>
            </div>
          )}
        </div>
      </Panel>
      {outcomes.length > 0 && (
        <Panel title="چیزی که همراهت می‌ماند">
          <div className="outcomes">
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
        </Panel>
      )}
      {course.requires_final_exam && (
        <Panel title="گواهی پایان دوره">
          <div className="row" style={{ gap: "1rem" }}>
            <span className="tile tile-lg tile-mint">
              <GraduationCap />
            </span>
            <p className="soft" style={{ flex: 1, fontSize: "var(--t-small)" }}>
              با نمره‌ی ۷۰ یا بیشتر در آزمون نهایی، گواهی شماره‌دار به اسم «{me?.display_name}» صادر می‌شود که هر کسی بدون ورود
              می‌تواند استعلامش کند.
            </p>
            <button className="btn btn-primary" onClick={() => enroll(course.id)}>
              {joined ? "ادامه‌ی مسیر" : "شروع مسیر"}
            </button>
          </div>
        </Panel>
      )}
    </div>
  );
}
