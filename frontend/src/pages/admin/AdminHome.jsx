// Admin dashboard: create-course hero, CMS stats, recent content and activity.
import { ArrowLeft, BookOpen, ChevronLeft, Ellipsis, Eye, FilePen, Image, Layers, Rocket, ShieldCheck, Sparkles, SquarePen, SquarePlus, UserPlus, Users } from "lucide-react";
import { useCached } from "../../lib/cache.js";
import { ago, fa, hueOf, pct } from "../../lib/format.js";
import { useAdminCourses, useAdminLog, useAdminUsers } from "../../lib/admin.js";
import { useStore } from "../../lib/store.jsx";
import { HeroArt, HeroScene, Landscape } from "../../ui/art.jsx";
import { Callout, Panel, Ring, Skel, Stat } from "../../ui/kit.jsx";
import { versionBadge } from "./Studio.jsx";
import { MascotStill } from "../../ui/mascot.jsx";

const LOG_ICONS = {
  publish: ["mint", <Rocket key="p" />],
  generate: ["lav", <Sparkles key="g" />],
  user: ["rose", <UserPlus key="u" />],
  image: ["peach", <Image key="i" />],
  version: ["lav", <FilePen key="v" />],
};

export function AdminHome() {
  const { go } = useStore();
  const courses = useAdminCourses();
  const users = useAdminUsers();
  const stats = useCached("/api/admin/stats");
  const log = useAdminLog();
  if (courses.loading && !courses.data) return <Skel lines={8} />;

  const versions = courses.data || [];
  const live = versions.filter((v) => v.course_status !== "deleted");
  const courseIds = [...new Set(live.map((v) => v.course_id))];
  const activeCourses = new Set(live.filter((v) => v.course_status !== "inactive").map((v) => v.course_id));
  const learners = (users.data || []).filter((u) => !u.deleted_at);
  const monthAgo = Date.now() - 30 * 24 * 3600 * 1000;
  const newLearners = learners.filter((u) => new Date(u.created_at) > monthAgo).length;
  const drafts = live.filter((v) => v.status !== "published");
  const published = live.filter((v) => v.status === "published");
  const readyDrafts = drafts.filter((v) => ["generated", "edited"].includes(v.generation_status));
  const recent = [...live].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)).slice(0, 3);
  const open = (v) => go({ name: "admin-studio", courseId: v.course_id, version: v.version_number });

  return (
    <div className="dash">
      <div className="dash-main">
        <section className="hero">
          <HeroScene />
          <HeroArt />
          <h1>
            ایده‌هایت را به <em>دوره‌ی آموزشی</em> تبدیل کن
          </h1>
          <p>مشخصات دوره را بنویس؛ هوش مصنوعی سرفصل‌ها، مراحل و آزمونک‌ها را می‌سازد و تو بازبینی و منتشر می‌کنی.</p>
          <button className="btn btn-primary btn-lg" onClick={() => go({ name: "admin-new" })}>
            <Sparkles /> ساخت دوره‌ی جدید
          </button>
        </section>
        <div className="stats">
          <Stat tone="lav" icon={<BookOpen />} label="کل دوره‌ها" value={fa(courseIds.length)} sub={`${fa(activeCourses.size)} فعال`} />
          <Stat tone="rose" icon={<Users />} label="یادگیرنده‌ها" value={fa(learners.length)} delta={newLearners ? `${fa(newLearners)} نفر` : undefined} sub="در ۳۰ روز گذشته" />
          <Stat tone="peach" icon={<Layers />} label="نسخه‌های ساخته‌شده" value={fa(live.length)} sub={`${fa(published.length)} منتشر، ${fa(drafts.length)} پیش‌نویس`} />
          <Stat
            tone="mint"
            icon={<SquarePen />}
            label="میانگین پیشرفت"
            value={stats.data ? pct(stats.data.average_progress) : "—"}
            sub={stats.data ? `${fa(stats.data.enrollment_count)} ثبت‌نام` : ""}
          />
        </div>
        <div className="dash-row">
          <Panel
            title="محتوای اخیر"
            action={
              <button className="link-btn" onClick={() => go({ name: "admin-studio" })}>
                همه <ArrowLeft />
              </button>
            }
          >
            <div className="list">
              {recent.map((v) => (
                <button key={v.id} className="list-row" onClick={() => open(v)}>
                  <span className="thumb">
                    <Landscape hue={hueOf(v.course_id)} seed={hueOf(v.course_id)} />
                  </span>
                  <span className="list-main">
                    <b>{v.course_title}</b>
                    <small>
                      نسخه‌ی {fa(v.version_number)} | {fa(v.modules.length)} سرفصل
                    </small>
                  </span>
                  {versionBadge(v)}
                  <Ellipsis size={16} className="muted" aria-hidden />
                </button>
              ))}
            </div>
          </Panel>
          <Panel title="فعالیت اخیر">
            <div className="list">
              {log.slice(0, 4).map((item, i) => (
                <div key={i} className="act-row">
                  <span className={`tile tile-${(LOG_ICONS[item.kind] || LOG_ICONS.version)[0]}`}>{(LOG_ICONS[item.kind] || LOG_ICONS.version)[1]}</span>
                  <div>
                    <p>{item.text}</p>
                    <small>{ago(item.at)}</small>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
      <aside className="dash-side">
        <Panel title="کارهای سریع">
          <div className="quick">
            {[
              [<SquarePlus key="1" />, "ساخت دوره‌ی جدید", () => go({ name: "admin-new" })],
              [<Sparkles key="2" />, "تولید عکس با هوش مصنوعی", () => go({ name: "admin-images" })],
              [<ShieldCheck key="3" />, "مدیریت کاربران", () => go({ name: "admin-users" })],
              [<Eye key="4" />, "پیش‌نمایش لندینگ", () => go({ name: "landing" })],
            ].map(([icon, label, run], i) => (
              <button key={i} className="quick-btn mat mat-raised" onClick={run}>
                <span className="tile tile-quiet tile-sq">{icon}</span>
                <span>{label}</span>
                <ChevronLeft />
              </button>
            ))}
          </div>
        </Panel>
        <Panel>
          <div className="assistant">
            <span className="assistant-hero">
              <MascotStill pose="laptop" height="5.4rem" float={false} />
            </span>
            <div>
              <h3>دستیار تولید</h3>
              <p>از مشخصات دوره تا همه‌ی سرفصل‌ها، مراحل و آزمونک‌ها را در پس‌زمینه می‌سازم.</p>
              <button className="btn btn-primary btn-sm" onClick={() => go({ name: "admin-new" })}>
                شروع تولید <ArrowLeft />
              </button>
            </div>
          </div>
        </Panel>
        <Panel title="آماده‌ی انتشار">
          <div className="goal">
            <Ring value={published.length} max={published.length + drafts.length} />
            <p>{readyDrafts.length ? `${fa(readyDrafts.length)} پیش‌نویس تولیدشده منتظر بازبینی و انتشار است.` : "پیش‌نویس آماده‌ای منتظر انتشار نیست."}</p>
            <button
              className="icon-btn"
              aria-label="رفتن به پیش‌نویس"
              onClick={() => (readyDrafts[0] ? open(readyDrafts[0]) : go({ name: "admin-studio" }))}
            >
              <ArrowLeft />
            </button>
          </div>
        </Panel>
        {live.some((v) => v.generation_status === "failed") && <Callout tone="err">تولید یکی از پیش‌نویس‌ها ناموفق بوده است؛ در استودیو دوباره تولیدش کن.</Callout>}
      </aside>
    </div>
  );
}
