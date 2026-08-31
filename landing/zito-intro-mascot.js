/* Real Canvas Lottie controller used only by Zito's introduction landing. */
(() => {
  "use strict";

  const ROOT = "/landing-static/zito-intro-lottie";
  const RUNTIME_URL = "/landing-static/zito-lottie/lottie_canvas.min.js";
  const INTRO_SEGMENT = Object.freeze([0, 179]);

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

  class ZitoIntroMascot extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.animation = null;
      this.observer = null;
      this.active = false;
      this.visible = false;
      this.hasInitialized = false;
      this.mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      this.onVisibilityChange = this.onVisibilityChange.bind(this);
      this.onReducedMotionChange = this.onReducedMotionChange.bind(this);
    }

    connectedCallback() {
      this.setAttribute("role", "img");
      this.setAttribute("aria-label", this.getAttribute("aria-label") || "زیتو، همراه هوشمند یادگیری");
      this.renderFallback();
      this.mediaQuery.addEventListener("change", this.onReducedMotionChange);
      this.observer = new IntersectionObserver(this.onVisibilityChange, {
        rootMargin: "120px 0px",
        threshold: 0.01,
      });
      this.observer.observe(this);
    }

    disconnectedCallback() {
      this.mediaQuery.removeEventListener("change", this.onReducedMotionChange);
      this.observer?.disconnect();
      this.observer = null;
      this.animation?.destroy();
      this.animation = null;
    }

    renderFallback() {
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; width: 100%; height: 100%; }
          .stage { position: relative; width: 100%; height: 100%; overflow: visible; filter: drop-shadow(0 18px 22px rgba(92, 75, 148, .18)); }
          canvas, .fallback { position: absolute; inset: 0; display: block; width: 100%; height: 100%; object-fit: contain; }
          canvas { z-index: 2; }
          .fallback { z-index: 1; transition: opacity 160ms ease; }
          :host([data-ready="true"]) .fallback { opacity: 0; pointer-events: none; }
        </style>
        <div class="stage">
          <img class="fallback" src="${ROOT}/source/zito-intro.svg" alt="" decoding="async">
        </div>
      `;
    }

    activate() {
      this.active = true;
      if (!this.mediaQuery.matches && this.visible) {
        this.initialize();
        this.animation?.play();
      }
    }

    deactivate() {
      this.active = false;
      this.animation?.pause();
    }

    onVisibilityChange(entries) {
      this.visible = Boolean(entries[0]?.isIntersecting);
      if (!this.visible || !this.active) {
        this.animation?.pause();
        return;
      }
      if (this.mediaQuery.matches) {
        return;
      }
      this.initialize();
      this.animation?.play();
    }

    async initialize() {
      if (this.hasInitialized || this.mediaQuery.matches || !this.active) {
        return;
      }
      this.hasInitialized = true;

      try {
        const lottie = await loadLottieRuntime();
        if (!this.isConnected || this.mediaQuery.matches || !this.active) {
          return;
        }
        const stage = this.shadowRoot.querySelector(".stage");
        this.animation = lottie.loadAnimation({
          container: stage,
          renderer: "canvas",
          loop: true,
          autoplay: false,
          path: `${ROOT}/zito-intro-lottie.json`,
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
          this.animation.loop = true;
          this.animation.playSegments(INTRO_SEGMENT, true);
          if (!this.active || !this.visible) {
            this.animation.pause();
          }
        });
      } catch (error) {
        this.hasInitialized = false;
        this.setAttribute("data-lottie-fallback", "true");
        console.warn("Zito introduction Lottie fallback is active.", error);
      }
    }

    onReducedMotionChange(event) {
      if (event.matches) {
        this.animation?.destroy();
        this.animation = null;
        this.hasInitialized = false;
        this.removeAttribute("data-ready");
        return;
      }
      if (this.active && this.visible) {
        this.initialize();
      }
    }
  }

  if (!customElements.get("zito-intro-lottie-mascot")) {
    customElements.define("zito-intro-lottie-mascot", ZitoIntroMascot);
  }
})();
