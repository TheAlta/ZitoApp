(function () {
  "use strict";

  const STORAGE_KEY = "zito:landing-sound-muted";
  const TRACK_URL = "/landing-static/zito-ambient.mp3";
  const TARGET_VOLUME = 0.18;
  const listeners = new Set();
  const track = new Audio(TRACK_URL);

  let active = false;
  let muted = sessionStorage.getItem(STORAGE_KEY) === "true";
  let fadeFrame = null;
  let startPromise = null;

  track.preload = "auto";
  track.loop = true;
  track.volume = 0;

  function publish() {
    const state = { muted, active };
    listeners.forEach((listener) => listener(state));
  }

  function fadeTo(volume, duration, onComplete) {
    if (fadeFrame) window.cancelAnimationFrame(fadeFrame);

    const initialVolume = track.volume;
    const startedAt = window.performance.now();
    const tick = (now) => {
      const progress = Math.min((now - startedAt) / duration, 1);
      track.volume = initialVolume + (volume - initialVolume) * progress;
      if (progress < 1) {
        fadeFrame = window.requestAnimationFrame(tick);
        return;
      }
      fadeFrame = null;
      onComplete?.();
    };

    fadeFrame = window.requestAnimationFrame(tick);
  }

  async function start() {
    if (muted) return false;
    if (active && !track.paused) return true;
    if (startPromise) return startPromise;

    startPromise = track
      .play()
      .then(() => {
        active = true;
        fadeTo(TARGET_VOLUME, 900);
        publish();
        return true;
      })
      .catch(() => {
        active = false;
        publish();
        return false;
      })
      .finally(() => {
        startPromise = null;
      });

    return startPromise;
  }

  function stop() {
    active = false;
    fadeTo(0, 280, () => track.pause());
    publish();
  }

  async function toggle() {
    if (muted) {
      muted = false;
      sessionStorage.removeItem(STORAGE_KEY);
      publish();
      return start();
    }

    muted = true;
    sessionStorage.setItem(STORAGE_KEY, "true");
    stop();
    return false;
  }

  function attemptAutoplay() {
    if (!muted) start();
  }

  track.addEventListener("error", () => {
    active = false;
    publish();
  });

  document.addEventListener(
    "pointerdown",
    () => {
      if (!muted && !active) start();
    },
    { once: true, passive: true }
  );

  window.ZitoAmbient = {
    attemptAutoplay,
    getState: () => ({ muted, active }),
    onStateChange: (listener) => {
      listeners.add(listener);
      listener({ muted, active });
      return () => listeners.delete(listener);
    },
    start,
    stop,
    toggle,
  };

  // Try immediately on the first landing. Browsers that require a gesture retry on the first tap.
  attemptAutoplay();
})();
