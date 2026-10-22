// Shared building blocks of the Zito interface (ported from the design demo).
import { cloneElement, isValidElement, useEffect, useId, useRef } from "react";
import { CircleAlert, CircleCheck, CircleX, Info, LoaderCircle, TriangleAlert, ArrowUp, X } from "lucide-react";
import { clock, fa, secs } from "../lib/format.js";
import { useStore } from "../lib/store.jsx";
import { Drop } from "./art.jsx";

export function Panel({ title: e, action: t, children: n, className: r = ``, as: Tag = `section`, id: a }) {
  let o = useId();
  return (
    <Tag className={`mat mat-panel panel ${r}`} aria-labelledby={e ? o : undefined} id={a}>
      {(e || t) && (
        <header className="panel-head">
          {e && <h2 id={o}>{e}</h2>}
          {t}
        </header>
      )}
      {n}
    </Tag>
  );
}

export function Field({ label: e, error: t, hint: n, children: r, req: i, count: a }) {
  let o = useId(),
    s = `${o}-msg`,
    c = isValidElement(r) && typeof r.type == `string` && [`input`, `textarea`, `select`].includes(r.type),
    u = c
      ? cloneElement(r, {
          id: o,
          "aria-invalid": t ? true : undefined,
          "aria-describedby": t || n ? s : undefined,
          "aria-required": i || undefined,
        })
      : r;
  return (
    <div
      className="field"
      data-error={t ? true : undefined}
      role={c ? undefined : `group`}
      aria-labelledby={c ? undefined : `${o}-l`}
    >
      {c ? (
        <label className="field-label" htmlFor={o}>
          {e} {i && <span className="req">*</span>}
        </label>
      ) : (
        <span className="field-label" id={`${o}-l`}>
          {e} {i && <span className="req">*</span>}
        </span>
      )}
      {u}
      {t ? (
        <span className="field-error" role="alert" id={s}>
          <CircleAlert />
          {t}
        </span>
      ) : n ? (
        <span className="field-hint" id={s}>
          {n}
        </span>
      ) : null}
      {a && (
        <span className="counter" data-over={a[0] > a[1] || undefined}>
          {fa(a[0])} / {fa(a[1])}
        </span>
      )}
    </div>
  );
}

export function Dialog({ title: e, onClose: t, children: n, wide: r, icon: i, labelledBy: a }) {
  let o = useRef(null),
    s = useId();
  return (
    useEffect(() => {
      let e = document.activeElement,
        n = o.current;
      n?.querySelector(`input, textarea, select, button:not([data-close])`)?.focus();
      let r = (e) => {
        if ((e.key === `Escape` && t(), e.key === `Tab` && n)) {
          let t = [...n.querySelectorAll(`button:not(:disabled), input, textarea, select, a[href], [tabindex="0"]`)];
          if (!t.length) return;
          let [r, i] = [t[0], t[t.length - 1]];
          e.shiftKey && document.activeElement === r
            ? (e.preventDefault(), i.focus())
            : !e.shiftKey && document.activeElement === i && (e.preventDefault(), r.focus());
        }
      };
      return (
        document.addEventListener(`keydown`, r),
        () => {
          document.removeEventListener(`keydown`, r), e?.focus?.();
        }
      );
    }, [t]),
    (
      <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && t()}>
        <div
          ref={o}
          className={`dialog ${r ? `dialog-wide` : ``}`}
          role="dialog"
          aria-modal="true"
          aria-labelledby={a ?? s}
        >
          <div className="dialog-head">
            {i}
            <h2 id={s}>{e}</h2>
            <button className="icon-btn" onClick={t} aria-label="بستن" data-close>
              <X />
            </button>
          </div>
          {n}
        </div>
      </div>
    )
  );
}

export function Toasts() {
  let { toasts: e } = useStore();
  return (
    <div className="toasts" role="status" aria-live="polite">
      {e.map((e) => (
        <div key={e.id} className="toast" data-tone={e.tone}>
          {e.tone === `ok` ? (
            <CircleCheck />
          ) : e.tone === `err` ? (
            <CircleX />
          ) : e.tone === `warn` ? (
            <TriangleAlert />
          ) : (
            <Info />
          )}
          {e.text}
        </div>
      ))}
    </div>
  );
}

export function Empty({ icon: e, title: t, text: n, action: r }) {
  return (
    <div className="empty">
      <span className="tile tile-lg tile-lav">{e}</span>
      <h3>{t}</h3>
      <p>{n}</p>
      {r}
    </div>
  );
}

export function Callout({ tone: e, children: t, title: n }) {
  let Icon = e === `warn` ? TriangleAlert : e === `err` ? CircleX : e === `ok` ? CircleCheck : Info;
  return (
    <div className={`callout callout-${e}`} role={e === `err` ? `alert` : undefined}>
      <Icon />
      <div>
        {n && (
          <b
            style={{
              display: `block`,
            }}
          >
            {n}
          </b>
        )}
        {t}
      </div>
    </div>
  );
}

// AI request status strip. meta: {status, ms?, expect?, model?, attempt?, at?}
export function AIBar({ meta: e, sources: t, extra: n }) {
  let r = e.status === `processing` ? `در حال پردازش` : e.status === `ready` ? `آماده` : `نیاز به بررسی`;
  return (
    <div className="aibar" data-status={e.status}>
      <span className="aibar-state">
        {e.status === `processing` ? <LoaderCircle className="spin" size={13} /> : <Drop size={14} glow={false} />}
        <b>{r}</b>
      </span>
      {e.model && (
        <>
          <span className="sep" />
          <span>
            مدل <span className="ltr">{e.model}</span>
          </span>
        </>
      )}
      {(e.status === `processing` ? e.expect : e.ms) ? (
        <>
          <span className="sep" />
          <span>{e.status === `processing` ? `معمولاً ${e.expect}` : `ساخته‌شده در ${secs(e.ms)}`}</span>
        </>
      ) : null}
      {e.attempt ? (
        <>
          <span className="sep" />
          <span>تلاش {fa(e.attempt)}</span>
        </>
      ) : null}
      {t !== undefined && (
        <>
          <span className="sep" />
          <span>{t ? `${fa(t)} منبع خوانده شد` : `بدون منبع`}</span>
        </>
      )}
      {e.status !== `processing` && e.at && (
        <>
          <span className="sep" />
          <span className="muted">{clock(e.at)}</span>
        </>
      )}
      {n}
    </div>
  );
}
// Verified sources under a coach answer. Items: {n, title, scope?, excerpt?, score?}
export function Sources({ sources: e }) {
  return e.length ? (
    <details className="sources">
      <summary>
        <CircleCheck size={13} /> منابع تأییدشده ({fa(e.length)})
      </summary>
      <ol>
        {e.map((e) => (
          <li key={e.n}>
            <b>
              [{fa(e.n)}] {e.title}
            </b>
            {e.score != null && <span className="muted"> | شباهت {fa(e.score)}</span>}
            {e.scope && <span className="muted"> | {e.scope}</span>}
            {e.excerpt && <p>{e.excerpt}</p>}
          </li>
        ))}
      </ol>
    </details>
  ) : null;
}

export function Ring({ value: e, max: t, size: n = `4.4rem`, label: r }) {
  let i = Math.min(1, t ? e / t : 0),
    a = 2 * Math.PI * 42,
    o = useId().replace(/:/g, ``);
  return (
    <span
      className="ring"
      style={{
        width: n,
        height: n,
      }}
      role="img"
      aria-label={`${fa(e)} از ${fa(t)}`}
    >
      <svg viewBox="0 0 100 100">
        <defs>
          <linearGradient id={`rg${o}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#c3b0f2" />
            <stop offset="1" stopColor="#8a6dd1" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(214,200,240,.55)" strokeWidth="7" />
        <circle
          cx="50"
          cy="50"
          r="42"
          fill="none"
          stroke={`url(#rg${o})`}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${a * i} ${a}`}
          transform="rotate(-90 50 50) scale(1 -1) translate(0 -100)"
          style={{
            transition: `stroke-dasharray .6s`,
          }}
        />
      </svg>
      <span className="ring-label">{r ?? `${fa(e)}/${fa(t)}`}</span>
    </span>
  );
}

export function Bar({ value: e, label: t }) {
  return (
    <div
      className="bar"
      role="progressbar"
      aria-valuenow={Math.round(e)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={t}
    >
      <i
        style={{
          width: `${Math.max(2, Math.min(100, e))}%`,
        }}
      />
    </div>
  );
}

export function Skel({ lines: e = 3 }) {
  return (
    <div className="skel-wrap" aria-busy="true" aria-label="در حال بارگذاری">
      {Array.from(
        {
          length: e,
        },
        (e, t) => (
          <div
            key={t}
            className="skel"
            style={{
              width: `${92 - t * 14}%`,
            }}
          />
        ),
      )}
    </div>
  );
}

export function Form({ onSubmit: e, children: t, className: n = `form`, style: r }) {
  return (
    <form
      className={n}
      style={r}
      noValidate
      onSubmit={(t) => {
        t.preventDefault(), e();
      }}
      onClickCapture={(t) => {
        let n = t.target.closest(`button`);
        n && (n.getAttribute(`type`) ?? `submit`) === `submit` && !n.disabled && (t.preventDefault(), e());
      }}
      onKeyDown={(t) => {
        let n = t.target;
        t.key === `Enter` && n.tagName === `INPUT` && n.type !== `checkbox` && (t.preventDefault(), e());
      }}
    >
      {t}
    </form>
  );
}

export function Stat({ tone: e, icon: t, label: n, value: r, delta: i, sub: a }) {
  return (
    <div className="stat mat mat-panel">
      <span className={`tile tile-lg tile-${e}`}>{t}</span>
      <div className="stat-body">
        <span className="stat-label">{n}</span>
        <span className="stat-value num">{r}</span>
        {i && (
          <span className="stat-delta">
            <ArrowUp /> {i}
          </span>
        )}
        {a && <span className="stat-sub">{a}</span>}
      </div>
    </div>
  );
}

export function statusBadge(e) {
  return e.status === `completed` ? (
    <span className="badge badge-ok">تکمیل‌شده</span>
  ) : e.status === `awaiting_final` ? (
    <span className="badge badge-warn">منتظر آزمون نهایی</span>
  ) : (
    <span className="badge badge-accent">در حال یادگیری</span>
  );
}
