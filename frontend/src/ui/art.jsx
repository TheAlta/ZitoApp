// Hand-drawn SVG art of the Zito look: sky, glass drop mascot, sprig, landscapes.
import { useId } from "react";

export function Sky({ dim: e = false }) {
  return (
    <div className="sky" aria-hidden="true" data-dim={e || undefined}>
      <svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="sky-base" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#efe4f5" />
            <stop offset="0.45" stopColor="#f8efee" />
            <stop offset="1" stopColor="#f3e5ee" />
          </linearGradient>
          <radialGradient id="sky-sun" cx="0.22" cy="0.18" r="0.55">
            <stop offset="0" stopColor="#fff3e6" stopOpacity="0.95" />
            <stop offset="0.45" stopColor="#fde5d6" stopOpacity="0.55" />
            <stop offset="1" stopColor="#fde5d6" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="sky-lav" cx="0.92" cy="0.95" r="0.6">
            <stop offset="0" stopColor="#d9c8f1" stopOpacity="0.85" />
            <stop offset="1" stopColor="#d9c8f1" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="sky-lav2" cx="0.02" cy="0.92" r="0.45">
            <stop offset="0" stopColor="#e6d4f2" stopOpacity="0.9" />
            <stop offset="1" stopColor="#e6d4f2" stopOpacity="0" />
          </radialGradient>
          <filter id="sky-blur" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="26" />
          </filter>
          <linearGradient id="sky-mtn" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#dccdee" />
            <stop offset="1" stopColor="#efe3f0" />
          </linearGradient>
        </defs>
        <rect width="1600" height="1000" fill="url(#sky-base)" />
        <rect width="1600" height="1000" fill="url(#sky-sun)" />
        <rect width="1600" height="1000" fill="url(#sky-lav)" />
        <rect width="1600" height="1000" fill="url(#sky-lav2)" />
        <g filter="url(#sky-blur)" opacity="0.8">
          <ellipse cx="420" cy="230" rx="260" ry="60" fill="#fff8f3" />
          <ellipse cx="1180" cy="160" rx="300" ry="54" fill="#fbf2f8" />
          <ellipse cx="900" cy="420" rx="380" ry="70" fill="#fdf5f1" />
          <ellipse cx="200" cy="640" rx="260" ry="70" fill="#f6ecf6" />
        </g>
        <path
          d="M0 860 L140 760 L260 800 L420 700 L560 790 L700 740 L860 820 L1000 760 L1160 830 L1320 740 L1460 800 L1600 760 L1600 1000 L0 1000 Z"
          fill="url(#sky-mtn)"
          opacity="0.55"
        />
        <path
          d="M0 930 C240 880 420 920 640 890 C880 860 1080 920 1300 880 C1440 860 1540 880 1600 870 L1600 1000 L0 1000 Z"
          fill="#f4e9f2"
          opacity="0.8"
        />
      </svg>
    </div>
  );
}

export function Sprig({ className: e, flowers: t = 9, tone: n = `lav` }) {
  let r = useId().replace(/:/g, ``),
    i = n === `lav` ? `#b9a0e8` : `#eab1c3`,
    a = n === `lav` ? `#8f72d0` : `#d0819c`;
  return (
    <svg className={e} viewBox="0 0 80 220" aria-hidden="true">
      <defs>
        <linearGradient id={`f${r}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={i} />
          <stop offset="1" stopColor={a} />
        </linearGradient>
      </defs>
      <path d="M40 220 C42 160 36 110 44 30" stroke="#9fb39a" strokeWidth="2.2" fill="none" strokeLinecap="round" />
      <path
        d="M41 170 C28 150 18 150 10 140 M42 150 C56 136 64 134 72 126"
        stroke="#a9bba2"
        strokeWidth="1.8"
        fill="none"
        strokeLinecap="round"
      />
      {Array.from(
        {
          length: t,
        },
        (e, t) => {
          let n = 30 + t * 11,
            a = 1 - t * 0.04,
            o = 44 - t * 0.6;
          return (
            <g key={t} transform={`translate(${o} ${n}) scale(${a})`}>
              <ellipse cx="-5" cy="0" rx="5" ry="3.6" fill={`url(#f${r})`} transform="rotate(-25)" opacity="0.92" />
              <ellipse cx="5" cy="1" rx="5" ry="3.6" fill={`url(#f${r})`} transform="rotate(25)" opacity="0.88" />
              <ellipse cx="0" cy="-3" rx="3.4" ry="4" fill={i} opacity="0.9" />
            </g>
          );
        },
      )}
    </svg>
  );
}

export function Drop({ size: e = 120, face: t = false, className: n, glow: r = true }) {
  let i = useId().replace(/:/g, ``),
    a = `M60 6 C70 26 98 52 98 82 A38 38 0 0 1 22 82 C22 52 50 26 60 6 Z`;
  return (
    <svg
      className={n}
      width={e}
      height={e}
      viewBox="0 0 120 132"
      aria-hidden="true"
      style={{
        overflow: `visible`,
      }}
    >
      <defs>
        <radialGradient id={`body${i}`} cx="0.42" cy="0.58" r="0.62">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.08" />
          <stop offset="0.55" stopColor="#d9ccff" stopOpacity="0.22" />
          <stop offset="0.82" stopColor="#9b84e6" stopOpacity="0.55" />
          <stop offset="1" stopColor="#6c55c4" stopOpacity="0.85" />
        </radialGradient>
        <linearGradient id={`rim${i}`} x1="0.8" y1="0" x2="0.2" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="1" />
          <stop offset="0.45" stopColor="#ffffff" stopOpacity="0.15" />
          <stop offset="1" stopColor="#c7b8ff" stopOpacity="0.9" />
        </linearGradient>
        <radialGradient id={`caustic${i}`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#ffd9c3" stopOpacity="0.95" />
          <stop offset="1" stopColor="#ffd9c3" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`blue${i}`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#9fc4ff" stopOpacity="0.8" />
          <stop offset="1" stopColor="#9fc4ff" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`shadow${i}`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#8a6dd1" stopOpacity="0.38" />
          <stop offset="1" stopColor="#8a6dd1" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`aura${i}`} cx="0.5" cy="0.55" r="0.5">
          <stop offset="0" stopColor="#fff4ec" stopOpacity="0.9" />
          <stop offset="0.6" stopColor="#ead9ff" stopOpacity="0.35" />
          <stop offset="1" stopColor="#ead9ff" stopOpacity="0" />
        </radialGradient>
        <clipPath id={`clip${i}`}>
          <path d={a} />
        </clipPath>
      </defs>
      {r && <ellipse cx="60" cy="74" rx="62" ry="62" fill={`url(#aura${i})`} />}
      <ellipse cx="60" cy="126" rx="30" ry="5" fill={`url(#shadow${i})`} />
      <path d={a} fill={`url(#body${i})`} />
      <g clipPath={`url(#clip${i})`}>
        <ellipse cx="68" cy="104" rx="26" ry="12" fill={`url(#caustic${i})`} />
        <ellipse cx="30" cy="80" rx="12" ry="26" fill={`url(#blue${i})`} />
        <path d="M24 90 C40 104 82 106 96 88" stroke="#ffffff" strokeOpacity="0.5" strokeWidth="1.4" fill="none" />
      </g>
      <path d={a} fill="none" stroke={`url(#rim${i})`} strokeWidth="2" />
      <path
        d="M72 36 C82 50 90 62 90 76"
        stroke="#ffffff"
        strokeWidth="4.5"
        strokeLinecap="round"
        fill="none"
        opacity="0.92"
      />
      <circle cx="86" cy="90" r="2.4" fill="#fff" opacity="0.85" />
      <path
        d="M44 46 C40 54 36 60 34 68"
        stroke="#ffffff"
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
        opacity="0.45"
      />
      {t && (
        <g>
          <ellipse cx="60" cy="84" rx="22" ry="17" fill="#fffdfd" opacity="0.94" />
          <ellipse cx="51.5" cy="82" rx="2.6" ry="3.4" fill="#2c2549" />
          <ellipse cx="68.5" cy="82" rx="2.6" ry="3.4" fill="#2c2549" />
          <circle cx="52.4" cy="80.8" r="0.9" fill="#fff" />
          <circle cx="69.4" cy="80.8" r="0.9" fill="#fff" />
          <path d="M54 90 Q60 95 66 90" stroke="#2c2549" strokeWidth="1.8" strokeLinecap="round" fill="none" />
          <ellipse cx="46" cy="89" rx="3" ry="1.7" fill="#f6b6c6" opacity="0.7" />
          <ellipse cx="74" cy="89" rx="3" ry="1.7" fill="#f6b6c6" opacity="0.7" />
        </g>
      )}
    </svg>
  );
}

export function CoachAvatar({ size: e = `2.6rem`, busy: t = false }) {
  return (
    <span
      className="coach-av"
      style={{
        width: e,
        height: e,
      }}
      data-busy={t || undefined}
    >
      <Drop size="96%" face glow={false} />
    </span>
  );
}

export function Logo({ compact: e = false }) {
  return (
    <span className="logo">
      <span className="logo-mark">
        <Drop size="100%" glow={false} />
        <Sprig className="logo-sprig" flowers={6} />
      </span>
      {!e && (
        <span className="logo-text">
          <b>زیتو</b>
          <small>یاد بگیر | تمرین کن | رشد کن</small>
        </span>
      )}
    </span>
  );
}

export function Landscape({ hue: e = 270, seed: t = 1, className: n, sun: r = true }) {
  let i = useId().replace(/:/g, ``),
    a = (e) => {
      let n = Math.sin(t * 9301 + e * 49297) * 233280;
      return n - Math.floor(n);
    },
    o = (e, t, n) => {
      let r = `M0 200 L0 ${e}`;
      for (let i = 0; i <= 8; i++) r += ` L${i * 40} ${e - t * (0.3 + a(i + n) * 0.9) * (i % 2 ? 1 : 0.55)}`;
      return r + ` L320 200 Z`;
    };
  return (
    <svg className={n} viewBox="0 0 320 200" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id={`s${i}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={`hsl(${e} 55% 86%)`} />
          <stop offset="0.6" stopColor={`hsl(${e + 50} 70% 90%)`} />
          <stop offset="1" stopColor="hsl(22 85% 90%)" />
        </linearGradient>
        <filter id={`b${i}`}>
          <feGaussianBlur stdDeviation="8" />
        </filter>
      </defs>
      <rect width="320" height="200" fill={`url(#s${i})`} />
      {r && <circle cx={90 + a(1) * 160} cy={60 + a(2) * 20} r="38" fill="hsl(28 95% 93%)" filter={`url(#b${i})`} />}
      <g filter={`url(#b${i})`} opacity="0.75">
        <ellipse cx={80 + a(3) * 60} cy="70" rx="70" ry="10" fill="#fff" />
        <ellipse cx={200 + a(4) * 60} cy="56" rx="60" ry="8" fill="#fff" />
      </g>
      <path d={o(150, 80, 1)} fill={`hsl(${e} 32% 78%)`} />
      <path d={o(170, 45, 7)} fill={`hsl(${e - 10} 28% 70%)`} opacity="0.9" />
      <path d={o(186, 22, 13)} fill={`hsl(${e - 20} 24% 62%)`} opacity="0.8" />
    </svg>
  );
}

export function HeroScene() {
  return (
    <svg className="hero-scene" viewBox="0 0 760 240" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="hs-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#d9c4ef" />
          <stop offset="0.5" stopColor="#efd3e8" />
          <stop offset="0.85" stopColor="#fadccf" />
          <stop offset="1" stopColor="#fbe9df" />
        </linearGradient>
        <radialGradient id="hs-sun" cx="0.26" cy="0.7" r="0.42">
          <stop offset="0" stopColor="#fff6ea" />
          <stop offset="0.45" stopColor="#fde4d2" stopOpacity="0.8" />
          <stop offset="1" stopColor="#fde4d2" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="hs-veil" x1="1" y1="0" x2="0" y2="0">
          <stop offset="0" stopColor="#f6ecf5" stopOpacity="0.72" />
          <stop offset="0.42" stopColor="#f6ecf5" stopOpacity="0.4" />
          <stop offset="0.7" stopColor="#f7eef6" stopOpacity="0" />
        </linearGradient>
        <filter id="hs-blur" x="-20%" y="-60%" width="140%" height="220%">
          <feGaussianBlur stdDeviation="10" />
        </filter>
        <filter id="hs-blur2">
          <feGaussianBlur stdDeviation="2.5" />
        </filter>
      </defs>
      <rect width="760" height="240" fill="url(#hs-sky)" />
      <rect width="760" height="240" fill="url(#hs-sun)" />
      <g filter="url(#hs-blur)">
        <ellipse cx="150" cy="150" rx="170" ry="30" fill="#fff3ee" />
        <ellipse cx="330" cy="120" rx="140" ry="22" fill="#fbe8ee" />
        <ellipse cx="80" cy="96" rx="120" ry="20" fill="#fff" opacity="0.85" />
        <ellipse cx="260" cy="196" rx="200" ry="34" fill="#f8dfe6" />
        <ellipse cx="520" cy="70" rx="200" ry="26" fill="#f3e6f6" />
        <ellipse cx="640" cy="180" rx="160" ry="30" fill="#f6e4ee" />
      </g>
      <path
        d="M0 214 L70 176 L140 196 L210 160 L290 202 L360 184 L450 220 L450 240 L0 240Z"
        fill="#cdb9e6"
        opacity="0.5"
        filter="url(#hs-blur2)"
      />
      <path
        d="M0 232 C90 208 180 226 280 214 C360 204 430 224 760 220 L760 240 L0 240Z"
        fill="#ead5ea"
        opacity="0.85"
      />
      <rect width="760" height="240" fill="url(#hs-veil)" />
    </svg>
  );
}

export function HeroArt() {
  return (
    <svg
      className="hero-art"
      viewBox="0 0 400 240"
      preserveAspectRatio="xMaxYMid slice"
      aria-hidden="true"
      style={{
        transform: `scaleX(-1)`,
      }}
    >
      <defs>
        <linearGradient id="ha-wing" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="0.4" stopColor="#e2d1fb" stopOpacity="0.8" />
          <stop offset="1" stopColor="#ad8ee6" stopOpacity="0.8" />
        </linearGradient>
        <linearGradient id="ha-wing2" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.9" />
          <stop offset="1" stopColor="#f2c9dc" stopOpacity="0.7" />
        </linearGradient>
        {[
          [`#fff3f7`, `#f4bfd3`, `#d98fb2`],
          [`#fff6f2`, `#f6cfd6`, `#e5a2b6`],
          [`#f8f1ff`, `#ddc8f4`, `#b79ae2`],
        ].map((e, t) => (
          <radialGradient key={t} id={`ha-b${t}`} cx="0.5" cy="0.9" r="0.9">
            <stop offset="0" stopColor={e[0]} />
            <stop offset="0.55" stopColor={e[1]} />
            <stop offset="1" stopColor={e[2]} />
          </radialGradient>
        ))}
        <linearGradient id="ha-leaf" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#c9d8bf" />
          <stop offset="1" stopColor="#93ad8d" />
        </linearGradient>
        <radialGradient id="ha-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#fff7ef" stopOpacity="0.95" />
          <stop offset="1" stopColor="#fff7ef" stopOpacity="0" />
        </radialGradient>
        <filter id="ha-soft">
          <feGaussianBlur stdDeviation="0.5" />
        </filter>
        <filter id="ha-far">
          <feGaussianBlur stdDeviation="1.6" />
        </filter>
      </defs>
      <ellipse cx="290" cy="120" rx="150" ry="110" fill="url(#ha-glow)" opacity="0.7" />
      <g filter="url(#ha-far)" opacity="0.55">
        {[
          [250, 200, 0.5],
          [270, 172, 0.4],
          [232, 214, 0.45],
        ].map(([e, t, n], r) => (
          <g key={r} transform={`translate(${e} ${t}) scale(${n})`}>
            {[0, 72, 144, 216, 288].map((e) => (
              <ellipse key={e} cy="-10" rx="8" ry="11" fill="url(#ha-b0)" transform={`rotate(${e})`} />
            ))}
          </g>
        ))}
      </g>
      <g stroke="#9db497" strokeWidth="1.5" fill="none" strokeLinecap="round">
        <path d="M344 250 C338 190 352 120 356 58" />
        <path d="M372 250 C374 200 380 140 384 104" />
        <path d="M318 250 C320 200 322 150 326 120" />
        <path d="M384 250 C388 220 392 200 392 182" />
        <path d="M300 250 C300 210 298 190 300 168" />
        <path d="M352 160 C340 170 336 180 342 196" />
        <path d="M330 140 C320 110 318 96 318 82" />
      </g>
      {[
        [338, 170, -35],
        [380, 150, 30],
        [322, 200, -50],
        [358, 120, 40],
        [306, 210, -30],
        [392, 214, 35],
      ].map(([e, t, n], r) => (
        <path
          key={r}
          d="M0 0 C6 -10 20 -12 26 -4 C18 2 8 4 0 0Z"
          fill="url(#ha-leaf)"
          opacity="0.85"
          transform={`translate(${e} ${t}) rotate(${n})`}
        />
      ))}
      {[
        [354, 50, 1.35, 0],
        [388, 94, 1.1, 1],
        [320, 110, 1, 2],
        [366, 142, 0.9, 0],
        [394, 180, 1.05, 1],
        [292, 162, 0.8, 2],
        [338, 196, 0.78, 0],
        [308, 70, 0.7, 1],
        [266, 204, 0.62, 0],
        [376, 220, 0.78, 2],
      ].map(([e, t, n, r], i) => (
        <g key={i} transform={`translate(${e} ${t}) scale(${n})`} filter="url(#ha-soft)">
          {[0, 72, 144, 216, 288].map((e) => (
            <ellipse
              key={e}
              cx="0"
              cy="-9.5"
              rx="7.4"
              ry="10.5"
              fill={`url(#ha-b${r})`}
              transform={`rotate(${e + i * 11})`}
              stroke="#fff"
              strokeOpacity="0.55"
              strokeWidth="0.6"
            />
          ))}
          <circle r="3.6" fill="#f6d79a" />
          <circle r="1.6" cx="-0.8" cy="-0.8" fill="#fff6dc" />
        </g>
      ))}
      <g transform="translate(214 96) rotate(-14) scale(1.25)">
        <ellipse cx="0" cy="40" rx="36" ry="6" fill="#b79ae2" opacity="0.12" />
        <path
          d="M0 0 C-10 -44 -58 -58 -64 -24 C-68 0 -34 10 0 4Z"
          fill="url(#ha-wing)"
          stroke="#fff"
          strokeWidth="1.4"
        />
        <path d="M0 5 C-26 14 -46 38 -32 52 C-18 62 -4 34 0 9Z" fill="url(#ha-wing2)" stroke="#fff" strokeWidth="1.1" />
        <path
          d="M2 0 C14 -38 44 -46 48 -20 C50 -2 24 6 2 4Z"
          fill="url(#ha-wing)"
          stroke="#fff"
          strokeOpacity="0.85"
          strokeWidth="1"
          opacity="0.8"
        />
        <path
          d="M2 5 C20 12 32 30 22 40 C12 46 4 28 2 9Z"
          fill="url(#ha-wing2)"
          stroke="#fff"
          strokeWidth="0.9"
          opacity="0.75"
        />
        <g stroke="#fff" strokeOpacity="0.85" strokeWidth="0.7" fill="none">
          <path d="M-2 0 C-20 -16 -36 -30 -54 -34" />
          <path d="M-2 2 C-22 -6 -40 -10 -58 -12" />
          <path d="M-2 7 C-14 18 -24 30 -30 44" />
        </g>
        <path
          d="M-60 -26 C-62 -14 -54 -8 -44 -8"
          stroke="#fff"
          strokeWidth="2.4"
          strokeLinecap="round"
          fill="none"
          opacity="0.8"
        />
        <path d="M0 -6 L1 18" stroke="#8a77b8" strokeWidth="2.4" strokeLinecap="round" />
        <path
          d="M0 -6 C-4 -16 -8 -20 -12 -22 M0 -6 C2 -16 6 -20 10 -22"
          stroke="#8a77b8"
          strokeWidth="0.8"
          fill="none"
        />
      </g>
      {[
        [200, 60],
        [280, 40],
        [214, 150],
        [262, 196],
      ].map(([e, t], n) => (
        <circle key={n} cx={e} cy={t} r={1.2 + (n % 2)} fill="#fff" opacity="0.9" />
      ))}
    </svg>
  );
}
