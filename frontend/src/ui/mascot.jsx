// Zito's original mascot and its Lottie motions, carried over from the previous UI.
// Assets live in landing/ (served at /landing-static/); the canvas runtime loads only when a motion plays.
import { useEffect, useRef, useState } from "react";

const STATIC = "/landing-static";
const RUNTIME = `${STATIC}/zito-lottie/lottie_canvas.min.js`;

export const MASCOT_ART = {
  base: `${STATIC}/zito-mascot.svg?v=20260831-static-2`,
  coach: `${STATIC}/coach-icons/zito-glasses.svg`,
  phone: `${STATIC}/course-mascot-lottie/assets/zito-state-a.png`,
  laptop: `${STATIC}/course-mascot-lottie/assets/zito-state-b.png`,
  wave: `${STATIC}/zito-lottie/assets/zito-fallback.svg`,
  intro: `${STATIC}/zito-intro-lottie/source/zito-intro.svg`,
};

// Each motion: the Lottie file, the still shown before it loads, and how it plays.
const MOTIONS = {
  // Landing: welcome once, idle loop, wave on hover, smile on click.
  wave: {
    path: `${STATIC}/zito-lottie/zito-lottie.json`,
    still: MASCOT_ART.wave,
    segments: { idle: [0, 59], wave: [60, 109], smile: [120, 150], welcome: [60, 150] },
    first: "welcome",
    interactive: true,
  },
  // "What is Zito?" introduction loop.
  intro: { path: `${STATIC}/zito-intro-lottie/zito-intro-lottie.json`, still: MASCOT_ART.intro, loop: [0, 179] },
  // Course overview: phone-in-hand to laptop and back.
  course: {
    path: `${STATIC}/course-mascot-lottie/zito-course-mascot.json?v=20260905-clean-face-1`,
    still: MASCOT_ART.phone,
    loop: true,
    dpr: true,
  },
};

let runtime;
function loadRuntime() {
  if (window.lottie) return Promise.resolve(window.lottie);
  runtime ||= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = RUNTIME;
    script.async = true;
    script.onload = () => (window.lottie ? resolve(window.lottie) : reject(new Error("lottie missing")));
    script.onerror = () => {
      runtime = undefined;
      reject(new Error("lottie failed"));
    };
    document.head.append(script);
  });
  return runtime;
}

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Animated mascot. `motion`: wave | intro | course. Width follows the art's ratio from `height`. */
export function Mascot({ motion = "wave", height = "12rem", className = "", label = "زیتو، همراه هوشمند یادگیری", float = false }) {
  const spec = MOTIONS[motion];
  const host = useRef(null);
  const stage = useRef(null);
  const [ready, setReady] = useState(false);
  const control = useRef({});

  useEffect(() => {
    if (reducedMotion()) return undefined;
    const state = { anim: null, mode: "idle", visible: false, pendingSmile: false, lastWave: 0, dead: false };
    control.current = state;
    const play = (name) => {
      if (!state.anim) return;
      state.mode = name;
      state.anim.loop = false;
      state.anim.playSegments(spec.segments[name], true);
    };
    const idle = () => {
      if (!state.anim || !state.visible) return;
      state.mode = "idle";
      state.anim.loop = true;
      state.anim.playSegments(spec.segments.idle, true);
    };
    state.play = play;
    const start = async () => {
      if (state.anim || state.loading) return;
      state.loading = true;
      try {
        const lottie = await loadRuntime();
        if (state.dead) return;
        state.anim = lottie.loadAnimation({
          container: stage.current,
          renderer: "canvas",
          loop: !!spec.loop,
          autoplay: false,
          path: spec.path,
          rendererSettings: {
            preserveAspectRatio: "xMidYMid meet",
            clearCanvas: true,
            progressiveLoad: !spec.dpr,
            ...(spec.dpr ? { dpr: Math.min(window.devicePixelRatio || 1, 1.5) } : {}),
          },
        });
        state.anim.addEventListener("DOMLoaded", () => {
          if (state.dead) return;
          setReady(true);
          if (spec.segments) play(spec.first);
          else if (Array.isArray(spec.loop)) state.anim.playSegments(spec.loop, true);
          else state.anim.play();
          if (!state.visible) state.anim.pause();
        });
        if (spec.segments)
          state.anim.addEventListener("complete", () => {
            if (state.mode === "idle") return;
            if (state.mode === "wave" && state.pendingSmile) {
              state.pendingSmile = false;
              play("smile");
            } else idle();
          });
      } catch {
        state.loading = false; // Runtime unavailable: the still image stays.
      }
    };
    const observer = new IntersectionObserver(
      ([entry]) => {
        state.visible = entry.isIntersecting;
        if (!state.visible) return state.anim?.pause();
        if (!state.anim) start();
        else if (spec.segments && state.mode === "idle") idle();
        else state.anim.play();
      },
      { rootMargin: "160px 0px", threshold: 0.01 },
    );
    observer.observe(host.current);
    return () => {
      state.dead = true;
      observer.disconnect();
      state.anim?.destroy();
    };
  }, [spec]);

  const wave = () => {
    const s = control.current;
    const now = Date.now();
    if (!spec.interactive || !s.anim || s.mode !== "idle" || now - s.lastWave < 1800) return;
    s.lastWave = now;
    s.play("wave");
  };
  const smile = () => {
    const s = control.current;
    if (!spec.interactive || !s.anim) return;
    if (s.mode === "wave" || s.mode === "welcome") s.pendingSmile = true;
    else s.play("smile");
  };

  return (
    <span
      ref={host}
      className={`mascot mascot-${motion}${float ? " mascot-float" : ""} ${className}`}
      style={{ height }}
      role="img"
      aria-label={label}
      data-ready={ready || undefined}
      tabIndex={spec.interactive ? 0 : undefined}
      onPointerEnter={wave}
      onClick={smile}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          smile();
        }
      }}
    >
      <img className="mascot-still" src={spec.still} alt="" decoding="async" />
      <span ref={stage} className="mascot-stage" />
    </span>
  );
}

/** Still mascot (no Lottie), e.g. side cards and empty states. `pose`: base | phone | laptop | wave | coach. */
export function MascotStill({ pose = "base", height = "6rem", className = "", float = true }) {
  return <img className={`mascot-img${float ? " mascot-float" : ""} ${className}`} src={MASCOT_ART[pose]} alt="" style={{ height }} decoding="async" />;
}

/** Round avatar showing the mascot's face; the coach wears glasses as in the original UI. */
export function MascotAvatar({ size = "2.6rem", busy = false, coach = false }) {
  return (
    <span className="coach-av mascot-av" style={{ width: size, height: size }} data-busy={busy || undefined}>
      <img src={coach ? MASCOT_ART.coach : MASCOT_ART.base} alt="" decoding="async" />
    </span>
  );
}
