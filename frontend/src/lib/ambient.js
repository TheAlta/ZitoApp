// Landing ambient music: fades in on the first visit, remembers mute for the tab session.
import { useEffect, useState } from "react";

const STORAGE_KEY = "zito:landing-sound-muted";
const TRACK_URL = "/landing-static/zito-ambient.mp3?v=20260928-euphoria-1";
const TARGET_VOLUME = 0.18;
const listeners = new Set();
let track = null;
let active = false;
let muted = (() => {
  try {
    return sessionStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
})();
let fadeFrame = null;
let starting = null;

function ensureTrack() {
  if (track) return track;
  track = new Audio(TRACK_URL);
  track.preload = "auto";
  track.loop = true;
  track.volume = 0;
  track.addEventListener("error", () => {
    active = false;
    publish();
  });
  return track;
}

function publish() {
  listeners.forEach((listener) => listener({ muted, active }));
}

function fadeTo(volume, duration, done) {
  const audio = ensureTrack();
  if (fadeFrame) cancelAnimationFrame(fadeFrame);
  const from = audio.volume;
  const startedAt = performance.now();
  const tick = (now) => {
    const progress = Math.min(Math.max((now - startedAt) / duration, 0), 1);
    audio.volume = Math.min(Math.max(from + (volume - from) * progress, 0), 1);
    if (progress < 1) fadeFrame = requestAnimationFrame(tick);
    else {
      fadeFrame = null;
      done?.();
    }
  };
  fadeFrame = requestAnimationFrame(tick);
}

export function startAmbient() {
  if (muted) return Promise.resolve(false);
  const audio = ensureTrack();
  if (active && !audio.paused) return Promise.resolve(true);
  if (starting) return starting;
  starting = audio
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
      starting = null;
    });
  return starting;
}

export function stopAmbient() {
  if (!track) return;
  active = false;
  fadeTo(0, 280, () => track.pause());
  publish();
}

export function toggleAmbient() {
  muted = !muted;
  try {
    if (muted) sessionStorage.setItem(STORAGE_KEY, "true");
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage is optional */
  }
  if (muted) stopAmbient();
  else startAmbient();
  publish();
}

// Plays while the calling page is mounted; browsers that block autoplay retry on the first tap.
export function useAmbient() {
  const [state, setState] = useState({ muted, active });
  useEffect(() => {
    listeners.add(setState);
    startAmbient();
    const retry = () => !muted && !active && startAmbient();
    document.addEventListener("pointerdown", retry, { once: true, passive: true });
    return () => {
      listeners.delete(setState);
      document.removeEventListener("pointerdown", retry);
      stopAmbient();
    };
  }, []);
  return state;
}
