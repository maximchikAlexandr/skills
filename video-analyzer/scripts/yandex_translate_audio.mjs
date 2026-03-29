#!/usr/bin/env node
// Reference: https://github.com/ilyhalight/voice-over-translation
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [
  ,
  ,
  videoUrl,
  sourceLangRaw = "auto",
  targetLangRaw = "ru",
  outFile,
  durationSecondsArg = "343",
  maxAttemptsArg = "12",
  pollSecondsArg = "10",
] = process.argv;

const depsDir = process.env.VA_DEPS_DIR;
if (!depsDir) {
  throw new Error("Missing VA_DEPS_DIR env var");
}
if (!videoUrl || !outFile) {
  throw new Error(
    "Usage: yandex_translate_audio.mjs <video_url> <source_lang> <target_lang> <out_file> [duration] [max_attempts] [poll_seconds]",
  );
}

const extClientPath = pathToFileURL(
  path.join(depsDir, "node_modules", "@vot.js", "ext", "dist", "client.js"),
).href;
const extClientModule = await import(extClientPath);
const VOTClient = extClientModule.default;
const { VOTWorkerClient } = extClientModule;

const durationSecondsRaw = Number(durationSecondsArg);
const maxAttempts = Number(maxAttemptsArg);
const pollSeconds = Number(pollSecondsArg);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function normalizeLang(raw) {
  const value = String(raw || "").toLowerCase().split(/[-_]/)[0];
  if (!value || value === "na" || value === "none" || value === "unknown") {
    return "auto";
  }
  return value;
}

function extractYoutubeVideoId(url) {
  try {
    const u = new URL(url);
    if (u.hostname === "youtu.be") {
      return u.pathname.replace(/^\/+/, "") || "";
    }
    const qv = u.searchParams.get("v");
    if (qv) return qv;
    const m = u.pathname.match(/\/shorts\/([A-Za-z0-9_-]{6,})/);
    if (m) return m[1];
  } catch (_err) {
    // no-op
  }
  return "";
}

const requestLang = normalizeLang(sourceLangRaw);
const responseLang = normalizeLang(targetLangRaw);
const videoId = extractYoutubeVideoId(videoUrl);
if (!videoId) {
  throw new Error("Could not extract YouTube video id for Yandex translation");
}

const videoData = {
  url: videoUrl,
  videoId,
  host: "youtube",
  duration:
    Number.isFinite(durationSecondsRaw) && durationSecondsRaw > 0
      ? durationSecondsRaw
      : 343,
};

const clients = [
  new VOTWorkerClient({
    host: "vot-worker.kload.workers.dev",
    requestLang,
    responseLang,
  }),
  new VOTClient({
    requestLang,
    responseLang,
  }),
];

let translatedUrl = "";
let usedClient = "";

for (const client of clients) {
  for (let i = 0; i < maxAttempts; i += 1) {
    try {
      const res = await client.translateVideo({
        videoData,
        requestLang,
        responseLang,
      });
      if (res?.translated && res?.url) {
        translatedUrl = String(res.url);
        usedClient = client.constructor.name;
        break;
      }
    } catch (_err) {
      // Try next iteration/client.
    }
    await sleep(Math.max(1, pollSeconds) * 1000);
  }
  if (translatedUrl) break;
}

if (!translatedUrl) {
  throw new Error("Failed to get translated audio URL from Yandex API");
}

const response = await fetch(translatedUrl, { redirect: "follow" });
if (!response.ok) {
  throw new Error(
    `Failed to download translated audio: HTTP ${response.status}`,
  );
}
const audioBuffer = new Uint8Array(await response.arrayBuffer());
await fs.writeFile(outFile, audioBuffer);

console.log(
  JSON.stringify({
    translatedUrl,
    usedClient,
    outFile,
    size: audioBuffer.length,
  }),
);
