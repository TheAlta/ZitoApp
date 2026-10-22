// Learner dashboard: continue card, stats, my courses, activity, quick actions and today's goal.
import {
  ArrowLeft,
  Award,
  BookOpen,
  ChevronLeft,
  CircleCheck,
  CirclePlay,
  Compass,
  Ellipsis,
  Layers,
  MessageCircle,
  Sparkles,
  Target,
  Trophy,
} from "lucide-react";
import { ago, fa, hueOf, pct } from "../lib/format.js";
import { STAGE_TITLES, pathInfo, selectCourse, useCurrentPath, useOverview } from "../lib/learner.js";
import { useStore } from "../lib/store.jsx";
import { Drop, HeroArt, HeroScene, Landscape } from "../ui/art.jsx";
import { Empty, Panel, Ring, Skel, Stat, statusBadge } from "../ui/kit.jsx";

const ACTIVITY_ICONS = {
  stage: ["lav", <CircleCheck key="s" />],
  quiz: ["peach", <Target key="q" />],
  coach: ["rose", <MessageCircle key="c" />],
  exam: ["mint", <Trophy key="e" />],
  cert: ["mint", <Award key="a" />],
  start: ["lav", <CirclePlay key="p" />],
};

const destination = (status) => (status === "completed" ? "certs" : status === "awaiting_final" ? "final" : "lesson");

export function Home() {
  const { me, profile, go, toast } = useStore();
  const overview = useOverview();
  const path = useCurrentPath();
  if (!me || (overview.loading && !overview.data)) return <Skel lines={8} />;

  const enrollments = overview.data?.enrollments || [];
  const certificates = overview.data?.certificates || [];
  const activity = overview.data?.activity || [];
  const info = pathInfo(path.data);
  const completedStages = enrollments.reduce((sum, e) => sum + e.completed_stage_count, 0);
  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
  const recent = activity.filter((a) => new Date(a.at) > weekAgo && (a.kind === "stage" || (a.kind === "quiz" && a.text.includes("قبول")))).length;
  const goal = Math.max(2, Math.round((profile?.daily_learning_minutes ?? 30) / 15));
  const today = new Date().setHours(0, 0, 0, 0);
  const doneToday = Math.min(goal, activity.filter((a) => new Date(a.at) >= today && (a.kind === "stage" || a.kind === "quiz")).length);
  const firstName = me.display_name.split(" ")[0];
  const open = (enrollment) =>
    selectCourse(enrollment.course_id)
      .then(() => go({ name: destination(enrollment.status) }))
      .catch((error) => toast(error.message, "err"));

  return (
    <div className="dash">
      <div className="dash-main">
        <section className="hero" aria-label="ادامه‌ی مسیر">
          <HeroScene />
          <HeroArt />
          {info ? (
            <>
              <span className="hero-chip">
                <Drop size="1rem" glow={false} /> {path.data.course_title} | سرفصل {fa(info.moduleIndex + 1)} از {fa(info.moduleCount)}
              </span>
              {info.status === "learning" ? (
                <>
                  <h1>
                    {firstName} جان، <em>یک قدم</em> تا پایان امروز مانده
                  </h1>
                  <p>
                    مرحله‌ی بعدی تو «{info.current?.title}» در سرفصل «{info.module?.title}» است.
                  </p>
                </>
              ) : (
                <>
                  <h1>
                    {firstName} جان، <em>{info.status === "completed" ? "دوره را تمام کردی" : "یک قدم"}</em>
                    {info.status === "completed" ? "" : " تا گواهی مانده"}
                  </h1>
                  <p>
                    {info.status === "completed"
                      ? "گواهی‌ات صادر شده و قابل استعلام است. هر وقت خواستی دوره‌ی تازه‌ای شروع کن."
                      : "همه‌ی سرفصل‌ها تمام شد؛ حالا نوبت آزمون نهایی است."}
                  </p>
                </>
              )}
              <button className="btn btn-primary btn-lg" onClick={() => go({ name: destination(info.status) })}>
                <Sparkles /> {info.status === "awaiting_final" ? "شروع آزمون نهایی" : info.status === "completed" ? "مشاهده‌ی گواهی" : "ادامه‌ی مسیر"}
              </button>
            </>
          ) : (
            <>
              <h1>
                ایده‌هایت را به <em>مهارت</em> تبدیل کن
              </h1>
              <p>یک دوره انتخاب کن؛ زیتو هر درس را با شغل و هدف تو تطبیق می‌دهد.</p>
              <button className="btn btn-primary btn-lg" onClick={() => go({ name: "courses" })}>
                <Compass /> انتخاب دوره
              </button>
            </>
          )}
        </section>
        <div className="stats">
          <Stat
            tone="lav"
            icon={<Layers />}
            label="دوره‌های من"
            value={fa(enrollments.length)}
            sub={`${fa(enrollments.filter((e) => e.status !== "completed").length)} دوره‌ی فعال`}
          />
          <Stat tone="rose" icon={<CircleCheck />} label="مراحل تمام‌شده" value={fa(completedStages)} delta={recent ? `${fa(recent)} مرحله` : undefined} sub="در ۷ روز گذشته" />
          <Stat
            tone="peach"
            icon={<Target />}
            label="پیشرفت دوره‌ی جاری"
            value={info ? pct(info.percent) : "—"}
            sub={info ? `${fa(info.completed)} از ${fa(info.total)} مرحله` : "هنوز دوره‌ای نداری"}
          />
          <Stat tone="mint" icon={<Award />} label="گواهی‌ها" value={fa(certificates.length)} sub="قابل استعلام عمومی" />
        </div>
        <div className="dash-row">
          <Panel
            title="دوره‌های من"
            action={
              <button className="link-btn" onClick={() => go({ name: "courses" })}>
                همه‌ی دوره‌ها <ArrowLeft />
              </button>
            }
          >
            {enrollments.length ? (
              <div className="list">
                {enrollments.slice(0, 3).map((e) => (
                  <button key={e.id} className="list-row" onClick={() => open(e)}>
                    <span className="thumb">
                      <Landscape hue={hueOf(e.course_id)} seed={hueOf(e.course_id)} />
                    </span>
                    <span className="list-main">
                      <b>{e.course_title}</b>
                      <small>
                        {fa(e.module_count)} سرفصل | {pct(e.total_stage_count ? (e.completed_stage_count / e.total_stage_count) * 100 : 0)}
                      </small>
                    </span>
                    {statusBadge(e)}
                    <Ellipsis size={16} className="muted" aria-hidden />
                  </button>
                ))}
              </div>
            ) : (
              <Empty
                icon={<BookOpen />}
                title="هنوز دوره‌ای شروع نکرده‌ای"
                text="از فهرست دوره‌ها یکی را انتخاب کن."
                action={
                  <button className="btn btn-primary btn-sm" onClick={() => go({ name: "courses" })}>
                    دیدن دوره‌ها
                  </button>
                }
              />
            )}
          </Panel>
          <Panel title="فعالیت اخیر">
            {activity.length ? (
              <div className="list">
                {activity.slice(0, 4).map((a, i) => (
                  <div key={i} className="act-row">
                    <span className={`tile tile-${(ACTIVITY_ICONS[a.kind] || ACTIVITY_ICONS.stage)[0]}`}>{(ACTIVITY_ICONS[a.kind] || ACTIVITY_ICONS.stage)[1]}</span>
                    <div>
                      <p>{fa(a.text)}</p>
                      <small>{ago(a.at)}</small>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Empty icon={<Sparkles />} title="فعالیتی ثبت نشده" text="با تمام کردن اولین مرحله، اینجا پر می‌شود." />
            )}
          </Panel>
        </div>
      </div>
      <aside className="dash-side">
        <Panel title="کارهای سریع">
          <div className="quick">
            {[
              [<CirclePlay key="1" />, info?.current ? `ادامه‌ی «${info.current.title}»` : info ? "ادامه‌ی دوره" : "انتخاب اولین دوره", () => go({ name: info ? destination(info.status) : "courses" })],
              [<MessageCircle key="2" />, "پرسیدن از زیتو", () => go({ name: info ? "coach" : "courses" })],
              [<Compass key="3" />, "مرور دوره‌ها", () => go({ name: "courses" })],
              [<Award key="4" />, "گواهی‌های من", () => go({ name: "certs" })],
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
              <Drop size="3.4rem" face glow={false} />
            </span>
            <div>
              <h3>کوچ تو، زیتو</h3>
              <p>سؤالی از درس داری؟ از روی محتوای همین دوره و با توجه به کارت جواب می‌دهم.</p>
              <button className="btn btn-primary btn-sm" onClick={() => go({ name: info ? "coach" : "courses" })}>
                گفت‌وگو با زیتو <ArrowLeft />
              </button>
            </div>
          </div>
        </Panel>
        <Panel title="هدف امروز">
          <div className="goal">
            <Ring value={doneToday} max={goal} />
            <p>
              {fa(goal)} مرحله در روز، بر اساس «{profile?.daily_learning_time_text ?? "زمان روزانه"}» که در پروفایل گفتی.
              {doneToday >= goal && " امروز به هدفت رسیدی!"}
            </p>
            <button className="icon-btn" aria-label="ادامه‌ی مسیر" onClick={() => go({ name: info ? "lesson" : "courses" })}>
              <ArrowLeft />
            </button>
          </div>
        </Panel>
        {info && info.status === "learning" && (
          <Panel title="مراحل این سرفصل" className="hide-tab">
            <div className="stage-rail" aria-label={`قدم ${fa(info.stageIndex + 1)} از ${fa(info.moduleStages.length || 8)}`}>
              {(info.moduleStages.length ? info.moduleStages : Object.keys(STAGE_TITLES)).map((s, i) => (
                <i key={i} data-s={i < info.stageIndex ? "done" : i === info.stageIndex ? "now" : "lock"} title={s.title || STAGE_TITLES[s]} />
              ))}
            </div>
          </Panel>
        )}
      </aside>
    </div>
  );
}
