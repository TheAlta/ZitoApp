// Course catalog with module preview on hover/long-press; shared enroll helpers.
import { useRef, useState } from "react";
import { Award, BookOpen, Clock, Layers } from "lucide-react";
import { useCached } from "../lib/cache.js";
import { fa, hueOf, pct } from "../lib/format.js";
import { K, refreshLearning, selectCourse, useCourses, useOverview } from "../lib/learner.js";
import { profileComplete, useStore } from "../lib/store.jsx";
import { Landscape } from "../ui/art.jsx";
import { Empty, Panel, Skel } from "../ui/kit.jsx";
import { MascotStill } from "../ui/mascot.jsx";

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
        <MascotStill pose="phone" height="4.6rem" />
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
