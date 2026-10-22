// Learner management: search/filter, profile detail, block/unblock, soft delete/restore, referral report.
import { useMemo, useState } from "react";
import { Ban, LockOpen, Trash, Undo2, UserRound, Users as UsersIcon, X } from "lucide-react";
import { del, post } from "../../lib/api.js";
import { invalidate, useCached } from "../../lib/cache.js";
import { AK } from "../../lib/admin.js";
import { ago, fa, jalali } from "../../lib/format.js";
import { PROFILE_KEYS, useStore } from "../../lib/store.jsx";
import { Callout, Empty, Panel, Skel } from "../../ui/kit.jsx";
import { PROFILE_QUESTIONS } from "../Onboarding.jsx";

const ALL_USERS = `${AK.users}?include_deleted=true`;
const filled = (u, key) => !!u[key] || (key === "daily_learning_time_text" && u.daily_learning_minutes != null);

export function Users({ userId }) {
  const { go, toast } = useStore();
  const list = useCached(ALL_USERS);
  const detail = useCached(userId ? `${AK.users}/${userId}` : null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const users = list.data || [];
  const shown = useMemo(
    () =>
      users
        .filter((u) => (filter === "deleted" ? !!u.deleted_at : !u.deleted_at))
        .filter((u) => (filter === "blocked" ? !!u.blocked_at : filter !== "incomplete" || !u.profile_completed))
        .filter((u) => !query || u.display_name.includes(query) || u.phone.includes(query))
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
    [users, query, filter],
  );
  const selected = detail.data || users.find((u) => String(u.id) === String(userId));
  const referrals = users
    .filter((u) => !u.deleted_at)
    .reduce((acc, u) => {
      if (u.referral_source) acc[u.referral_source] = (acc[u.referral_source] ?? 0) + 1;
      return acc;
    }, {});
  const totalLive = users.filter((u) => !u.deleted_at).length || 1;

  const act = async (path, method, message, tone) => {
    if (busy) return;
    setBusy(true);
    try {
      await (method === "DELETE" ? del(path) : post(path));
      invalidate(ALL_USERS, AK.users, `${AK.users}/${selected.id}`);
      toast(message, tone);
    } catch (error) {
      toast(error.message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <div className="studio-head">
        <h1>کاربران</h1>
        <label className="search-box mat mat-field" style={{ width: "min(18rem,100%)" }}>
          <UserRound size={16} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="اسم یا شماره" aria-label="جست‌وجوی کاربر" />
        </label>
      </div>
      <div className="seg" role="radiogroup" style={{ justifySelf: "start" }}>
        {[
          ["all", "همه"],
          ["blocked", "مسدود"],
          ["incomplete", "پروفایل ناقص"],
          ["deleted", "حذف‌شده"],
        ].map(([key, label]) => (
          <button key={key} role="radio" aria-checked={filter === key} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>
      <div className="studio">
        <Panel>
          {list.loading && !list.data ? (
            <Skel lines={8} />
          ) : shown.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>کاربر</th>
                    <th className="hide-sm">عضویت</th>
                    <th>پروفایل</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((u) => (
                    <tr key={u.id} onClick={() => go({ name: "admin-users", userId: u.id })} style={{ cursor: "pointer" }} aria-selected={String(u.id) === String(userId)}>
                      <td>
                        <button className="row" style={{ flexWrap: "nowrap" }} onClick={() => go({ name: "admin-users", userId: u.id })}>
                          <span className="avatar" style={{ width: "2rem", height: "2rem", fontSize: ".8rem" }}>
                            {u.display_name.trim()[0]}
                          </span>
                          <span style={{ display: "grid", textAlign: "start" }}>
                            <b style={{ fontWeight: 500 }}>{u.display_name}</b>
                            <small className="ltr muted">{u.phone}</small>
                          </span>
                        </button>
                      </td>
                      <td className="hide-sm">{ago(u.created_at)}</td>
                      <td>
                        {u.profile_completed ? (
                          <span className="badge badge-ok">کامل</span>
                        ) : (
                          <span className="badge badge-warn">{fa(PROFILE_KEYS.filter((k) => filled(u, k)).length)} از ۷</span>
                        )}
                      </td>
                      <td>
                        {u.deleted_at ? <span className="badge badge-quiet">حذف‌شده</span> : u.blocked_at ? <span className="badge badge-err">مسدود</span> : <span className="badge badge-ok">فعال</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty icon={<UsersIcon />} title="کاربری پیدا نشد" text="فیلتر یا جست‌وجو را تغییر بده." />
          )}
        </Panel>
        <div className="stack">
          {selected ? (
            <Panel
              title={selected.display_name}
              action={
                <button className="icon-btn" aria-label="بستن" onClick={() => go({ name: "admin-users" })}>
                  <X />
                </button>
              }
            >
              <dl className="kv">
                <dt>شماره</dt>
                <dd className="ltr">{selected.phone}</dd>
                <dt>عضویت</dt>
                <dd>{jalali(selected.created_at)}</dd>
                {PROFILE_KEYS.map((key) => (
                  <div key={key} style={{ display: "contents" }}>
                    <dt>{PROFILE_QUESTIONS[key].q.replace("؟", "")}</dt>
                    <dd>{selected[key] ?? (key === "daily_learning_time_text" && selected.daily_learning_minutes != null ? `${fa(selected.daily_learning_minutes)} دقیقه` : <span className="muted">—</span>)}</dd>
                  </div>
                ))}
                <dt>دوره‌ها</dt>
                <dd>{detail.data ? detail.data.course_titles?.join("، ") || "—" : "…"}</dd>
              </dl>
              <div className="row" style={{ marginTop: "1rem" }}>
                {!selected.deleted_at &&
                  (selected.blocked_at ? (
                    <button className="btn btn-soft btn-sm" disabled={busy} onClick={() => act(`${AK.users}/${selected.id}/unblock`, "POST", `${selected.display_name} رفع مسدودیت شد.`)}>
                      <LockOpen /> رفع مسدودیت
                    </button>
                  ) : (
                    <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => act(`${AK.users}/${selected.id}/block`, "POST", `${selected.display_name} مسدود شد؛ جلسه‌های بازش باطل شد.`, "warn")}>
                      <Ban /> مسدود کردن
                    </button>
                  ))}
                {selected.deleted_at ? (
                  <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act(`${AK.users}/${selected.id}/restore`, "POST", "کاربر بازیابی شد.", "info")}>
                    <Undo2 /> بازیابی
                  </button>
                ) : (
                  <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act(`${AK.users}/${selected.id}`, "DELETE", "کاربر حذف شد (نرم؛ داده‌ها می‌ماند).", "info")}>
                    <Trash /> حذف
                  </button>
                )}
              </div>
            </Panel>
          ) : (
            <Panel>
              <Empty icon={<UserRound />} title="یک کاربر را انتخاب کن" text="جزئیات پروفایل و کارهای مسدودسازی اینجا نمایش داده می‌شود." />
            </Panel>
          )}
          <Panel title="نحوه‌ی آشنایی (گزارش بازاریابی)">
            <div className="stack" style={{ gap: ".4rem" }}>
              {Object.entries(referrals).length ? (
                Object.entries(referrals)
                  .sort((a, b) => b[1] - a[1])
                  .map(([source, count]) => (
                    <div key={source} className="row" style={{ fontSize: "var(--t-small)" }}>
                      <span style={{ minWidth: "7rem" }}>{source}</span>
                      <div className="bar" style={{ flex: 1 }}>
                        <i style={{ width: `${(count / totalLive) * 100}%` }} />
                      </div>
                      <span className="muted">{fa(count)}</span>
                    </div>
                  ))
              ) : (
                <p className="muted">هنوز داده‌ای ثبت نشده.</p>
              )}
            </div>
          </Panel>
          <Callout tone="info">مسدود کردن جلسه‌های باز را باطل می‌کند؛ با درخواست کد تازه، کاربر پیام «این حساب توسط مدیریت مسدود شده است» می‌بیند.</Callout>
        </div>
      </div>
    </div>
  );
}
