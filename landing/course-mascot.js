/* Canvas Lottie controller used only by the course overview hero. */
(() => {
  "use strict";

  const ROOT = "/landing-static/course-mascot-lottie";
  const RUNTIME_URL = "/landing-static/zito-lottie/lottie_canvas.min.js";
  const ASSET_VERSION = "20260905-clean-face-1";

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

  class CourseMascot extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.animation = null;
      this.observer = null;
      this.isVisible = false;
      this.hasInitialized = false;
      this.mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      this.onVisibilityChange = this.onVisibilityChange.bind(this);
      this.onReducedMotionChange = this.onReducedMotionChange.bind(this);
    }

    connectedCallback() {
      this.setAttribute("role", "img");
      this.setAttribute("aria-label", this.getAttribute("aria-label") || "زیتو، همراه مسیر این دوره");
      this.renderFallback();
      this.mediaQuery.addEventListener("change", this.onReducedMotionChange);
      if (!this.mediaQuery.matches) {
        this.observeVisibility();
      }
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
          .stage { position: relative; width: 100%; height: 100%; overflow: visible; }
          canvas, .fallback { position: absolute; inset: 0; display: block; width: 100%; height: 100%; object-fit: contain; }
          canvas { z-index: 2; opacity: 0; transition: opacity 180ms ease; }
          .fallback { z-index: 1; }
          .fallback-b { opacity: 0; }
          :host([data-ready="true"]) canvas { opacity: 1; }
          :host([data-ready="true"]) .fallback { opacity: 0; }
          @media (prefers-reduced-motion: reduce) {
            .fallback-b { opacity: 0; }
          }
        </style>
        <div class="stage">
          <img class="fallback fallback-a" src="${ROOT}/assets/zito-state-a.png" alt="" decoding="async" fetchpriority="high">
          <img class="fallback fallback-b" src="${ROOT}/assets/zito-state-b.png" alt="" decoding="async" fetchpriority="high">
        </div>
      `;
    }

    observeVisibility() {
      this.observer?.disconnect();
      this.observer = new IntersectionObserver(this.onVisibilityChange, {
        rootMargin: "160px 0px",
        threshold: 0.01,
      });
      this.observer.observe(this);
    }

    onVisibilityChange(entries) {
      const entry = entries[0];
      this.isVisible = Boolean(entry?.isIntersecting);
      if (!this.isVisible) {
        this.animation?.pause();
        return;
      }
      if (!this.hasInitialized) {
        this.initialize();
      } else {
        this.animation?.play();
      }
    }

    async initialize() {
      if (this.hasInitialized || this.mediaQuery.matches) {
        return;
      }
      this.hasInitialized = true;
      try {
        const lottie = await loadLottieRuntime();
        if (!this.isConnected || this.mediaQuery.matches) {
          return;
        }
        this.animation = lottie.loadAnimation({
          container: this.shadowRoot.querySelector(".stage"),
          renderer: "canvas",
          loop: true,
          autoplay: false,
          path: `${ROOT}/zito-course-mascot.json?v=${ASSET_VERSION}`,
          rendererSettings: {
            preserveAspectRatio: "xMidYMid meet",
            clearCanvas: true,
            progressiveLoad: false,
            dpr: Math.min(window.devicePixelRatio || 1, 1.5),
          },
        });
        this.animation.addEventListener("DOMLoaded", () => {
          if (!this.isConnected || this.mediaQuery.matches) {
            return;
          }
          this.animation.goToAndStop(0, true);
          window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => this.revealLottieCanvas());
          });
        });
      } catch (error) {
        this.hasInitialized = false;
        this.setAttribute("data-lottie-fallback", "true");
        console.warn("Course mascot Lottie fallback is active.", error);
      }
    }

    revealLottieCanvas() {
      if (
        !this.animation
        || !this.isConnected
        || this.mediaQuery.matches
      ) {
        return;
      }
      if (!this.hasAttribute("data-ready")) {
        this.setAttribute("data-ready", "true");
      }
      if (this.isVisible) {
        this.animation.play();
      }
    }

    onReducedMotionChange(event) {
      if (event.matches) {
        this.animation?.destroy();
        this.animation = null;
        this.hasInitialized = false;
        this.removeAttribute("data-ready");
        this.observer?.disconnect();
        return;
      }
      this.observeVisibility();
    }
  }

  if (!customElements.get("zito-course-mascot")) {
    customElements.define("zito-course-mascot", CourseMascot);
  }
})();
