#!/usr/bin/env node
/* Verify the landing mascot through a local Chrome DevTools session. */

import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

const [devtoolsUrl = "http://127.0.0.1:9226/json", captureDirectory] = process.argv.slice(2);
const targets = await (await fetch(devtoolsUrl)).json();
const target = targets.find((item) => item.type === "page");

if (!target?.webSocketDebuggerUrl) {
  throw new Error("No Chrome page target is available for Lottie verification.");
}

const expression = `(() => {
  const host = document.querySelector("zito-lottie-mascot");
  return {
    host: Boolean(host),
    ready: host?.getAttribute("data-ready") || null,
    fallback: host?.getAttribute("data-lottie-fallback") || null,
    canvasCount: host?.shadowRoot?.querySelectorAll("canvas").length || 0,
    lottieLoaded: Boolean(window.lottie),
    segments: window.ZitoMascot?.segments || null
  };
})()`;

const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let nextId = 1;

function call(method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

await new Promise((resolve, reject) => {
  const timeout = setTimeout(() => reject(new Error("Chrome DevTools connection timed out.")), 8000);
  socket.addEventListener("open", () => {
    clearTimeout(timeout);
    resolve();
  });
  socket.addEventListener("message", (event) => {
    const response = JSON.parse(event.data);
    if (!response.id || !pending.has(response.id)) return;
    const request = pending.get(response.id);
    pending.delete(response.id);
    if (response.error || response.result?.exceptionDetails) {
      request.reject(new Error(JSON.stringify(response.error || response.result.exceptionDetails)));
    } else {
      request.resolve(response.result);
    }
  });
  socket.addEventListener("error", () => reject(new Error("Chrome DevTools socket failed.")));
});

const evaluation = await call("Runtime.evaluate", { expression, returnByValue: true });
const result = evaluation.result?.value;

if (captureDirectory) {
  const event = (type) => `document.querySelector("zito-lottie-mascot")?.dispatchEvent(new Event("${type}", { bubbles: true }));`;
  const capture = async (name) => {
    const screenshot = await call("Page.captureScreenshot", { format: "png" });
    await writeFile(join(captureDirectory, name), Buffer.from(screenshot.data, "base64"));
  };

  await mkdir(captureDirectory, { recursive: true });
  await call("Runtime.evaluate", { expression: event("pointerenter") });
  await new Promise((resolve) => setTimeout(resolve, 650));
  await capture("zito-wave.png");
  await new Promise((resolve) => setTimeout(resolve, 1200));
  await call("Runtime.evaluate", { expression: event("click") });
  await new Promise((resolve) => setTimeout(resolve, 300));
  await capture("zito-smile.png");
}

socket.close();
console.log(JSON.stringify(result));
