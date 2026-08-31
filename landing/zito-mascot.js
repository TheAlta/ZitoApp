/* Real Lottie controller for the first landing-page Zito mascot. */
(() => {
  "use strict";

  const ROOT = "/landing-static/zito-lottie";
  const RUNTIME_URL = `${ROOT}/lottie_canvas.min.js`;
  const ZITO_SEGMENTS = Object.freeze({
    idle: [0, 59],
    wave: [60, 109],
    smile: [120, 150],
    welcome: [60, 150],
  });
  const WAVE_COOLDOWN_MS = 1800;

  function loadLottieRuntime() {
    if (window.lottie) {
      return Promise.resolve(window.lottie);
    }
    if (window.__zitoLottieRuntimePromise) {
      return window.__zitoLottieRuntimePromise;
    }

    window.__zitoLottieRuntimePromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = RUNTIME_URL;
      script.async = true;
      script.onload = () => window.lottie ? resolve(window.lottie) : reject(new Error("Lottie runtime did not initialize."));
      script.onerror = () => reject(new Error("Lottie runtime could not be loaded."));
      document.head.append(script);
    });
    return window.__zitoLottieRuntimePromise;
  }

  class ZitoMascot extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.animation = null;
      this.observer = null;
      this.mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      this.mode = "idle";
      this.pendingSmile = false;
      this.lastWaveAt = 0;
      this.hasInitialized = false;
      this.isVisible = false;
      this.isSuspended = false;
      this.onPointerEnter = this.onPointerEnter.bind(this);
      this.onClick = this.onClick.bind(this);
      this.onKeyDown = this.onKeyDown.bind(this);
      this.onReducedMotionChange = this.onReducedMotionChange.bind(this);
      this.onVisibilityChange = this.onVisibilityChange.bind(this);
    }

    connectedCallback() {
      this.setAttribute("role", "img");
      this.setAttribute("aria-label", this.getAttribute("aria-label") || "زیتو، همراه هوشمند یادگیری");
      this.setAttribute("tabindex", "0");
      this.renderFallback();
      this.addEventListener("pointerenter", this.onPointerEnter);
      this.addEventListener("click", this.onClick);
      this.addEventListener("keydown", this.onKeyDown);
      this.mediaQuery.addEventListener("change", this.onReducedMotionChange);

      if (!this.mediaQuery.matches) {
        this.observeVisibility();
      }
    }

    disconnectedCallback() {
      this.removeEventListener("pointerenter", this.onPointerEnter);
      this.removeEventListener("click", this.onClick);
      this.removeEventListener("keydown", this.onKeyDown);
      this.mediaQuery.removeEventListener("change", this.onReducedMotionChange);
      this.observer?.disconnect();
      this.observer = null;
      this.animation?.destroy();
      this.animation = null;
    }

    renderFallback() {
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; width: 110px; height: 132px; cursor: pointer; outline: none; }
          .stage { position: relative; width: 100%; height: 100%; overflow: visible; }
          canvas, .fallback { position: absolute; inset: 0; display: block; width: 100%; height: 100%; object-fit: contain; }
          canvas { z-index: 2; }
          .fallback { z-index: 1; transition: opacity 160ms ease; }
          :host([data-ready="true"]) .fallback { opacity: 0; pointer-events: none; }
          :host(:focus-visible) .stage { outline: 2px solid rgba(100, 84, 255, .72); outline-offset: 5px; border-radius: 20px; }
          @media (min-width: 1024px) { :host { width: 150px; height: 188px; } }
          @media (max-width: 640px) { :host { width: 140px; height: 168px; } }
        </style>
        <div class="stage">
          <img class="fallback" src="${ROOT}/assets/zito-fallback.svg" alt="" decoding="async">
        </div>
      `;
    }

    suspend() {
      this.isSuspended = true;
      this.animation?.pause();
    }

    resume() {
      this.isSuspended = false;
      if (!this.mediaQuery.matches && this.isVisible) {
        if (!this.hasInitialized) {
          this.initialize();
        } else {
          this.startIdle();
        }
      }
    }

    observeVisibility() {
      this.observer = new IntersectionObserver(this.onVisibilityChange, {
        rootMargin: "160px 0px",
        threshold: 0.01,
      });
      this.observer.observe(this);
    }

    onVisibilityChange(entries) {
      const entry = entries[0];
      this.isVisible = Boolean(entry?.isIntersecting);
      if (!this.isVisible || this.isSuspended) {
        this.animation?.pause();
        return;
      }
      if (!this.hasInitialized) {
        this.initialize();
      } else if (this.mode === "idle") {
        this.startIdle();
      } else {
        this.animation?.play();
      }
    }

    async initialize() {
      if (this.hasInitialized || this.mediaQuery.matches || this.isSuspended) {
        return;
      }
      this.hasInitialized = true;

      try {
        const lottie = await loadLottieRuntime();
        if (!this.isConnected || this.mediaQuery.matches) {
          return;
        }

        const stage = this.shadowRoot.querySelector(".stage");
        this.animation = lottie.loadAnimation({
          container: stage,
          renderer: "canvas",
          loop: false,
          autoplay: false,
          path: `${ROOT}/zito-lottie.json`,
          rendererSettings: {
            preserveAspectRatio: "xMidYMid meet",
            clearCanvas: true,
            progressiveLoad: true,
          },
        });
        this.animation.addEventListener("DOMLoaded", () => {
          if (!this.isConnected || this.mediaQuery.matches) {
            return;
          }
          this.setAttribute("data-ready", "true");
          if (this.isVisible && !this.isSuspended) {
            this.playSegment("welcome");
          }
        });
        this.animation.addEventListener("complete", () => this.handleSegmentComplete());
      } catch (error) {
        this.hasInitialized = false;
        this.setAttribute("data-lottie-fallback", "true");
        console.warn("Zito Lottie fallback is active.", error);
      }
    }

    playSegment(name) {
      if (!this.animation || this.mediaQuery.matches || !ZITO_SEGMENTS[name]) {
        return;
      }
      this.mode = name;
      this.animation.loop = false;
      this.animation.playSegments(ZITO_SEGMENTS[name], true);
    }

    startIdle() {
      if (!this.animation || this.mediaQuery.matches || !this.isVisible || this.isSuspended) {
        return;
      }
      this.mode = "idle";
      this.animation.loop = true;
      this.animation.playSegments(ZITO_SEGMENTS.idle, true);
    }

    handleSegmentComplete() {
      if (this.mode === "idle") {
        return;
      }
      if (this.mode === "wave" && this.pendingSmile) {
        this.pendingSmile = false;
        this.playSegment("smile");
        return;
      }
      this.startIdle();
    }

    onPointerEnter() {
      const now = Date.now();
      if (this.mediaQuery.matches || this.mode !== "idle" || now - this.lastWaveAt < WAVE_COOLDOWN_MS) {
        return;
      }
      this.lastWaveAt = now;
      this.playSegment("wave");
    }

    onClick() {
      if (this.mediaQuery.matches) {
        return;
      }
      if (this.mode === "wave" || this.mode === "welcome") {
        this.pendingSmile = true;
        return;
      }
      this.playSegment("smile");
    }

    onKeyDown(event) {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      this.onClick();
    }

    onReducedMotionChange(event) {
      if (event.matches) {
        this.animation?.destroy();
        this.animation = null;
        this.hasInitialized = false;
        this.removeAttribute("data-ready");
        return;
      }
      this.observeVisibility();
    }
  }

  if (!customElements.get("zito-lottie-mascot")) {
    customElements.define("zito-lottie-mascot", ZitoMascot);
  }

  window.ZitoMascot = Object.freeze({ segments: ZITO_SEGMENTS });
})();
