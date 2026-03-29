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
  outDir,
  durationSecondsArg = "343",
  maxAttemptsArg = "12",
  pollSecondsArg = "10",
] = process.argv;

const depsDir = process.env.VA_DEPS_DIR;
if (!depsDir) {
  throw new Error("Missing VA_DEPS_DIR env var");
}
if (!videoUrl || !outDir) {
  throw new Error(
    "Usage: yandex_fetch_transcription.mjs <video_url> <source_lang> <target_lang> <out_dir> [duration] [max_attempts] [poll_seconds]",
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

function msToSrtTime(ms) {
  const totalMs = Math.max(0, Number(ms) || 0);
  const h = Math.floor(totalMs / 3600000);
  const m = Math.floor((totalMs % 3600000) / 60000);
  const s = Math.floor((totalMs % 60000) / 1000);
  const milli = Math.floor(totalMs % 1000);
  const pad = (n, w = 2) => String(n).padStart(w, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)},${pad(milli, 3)}`;
}

const requestLang = normalizeLang(sourceLangRaw);
const targetLang = normalizeLang(targetLangRaw);
const videoId = extractYoutubeVideoId(videoUrl);
if (!videoId) {
  throw new Error("Could not extract YouTube video id for Yandex subtitles");
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
    responseLang: targetLang,
  }),
  new VOTClient({
    requestLang,
    responseLang: targetLang,
  }),
];

let subtitlesPayload = null;
let usedClient = "";

for (const client of clients) {
  for (let i = 0; i < maxAttempts; i += 1) {
    try {
      const res = await client.getSubtitles({
        videoData,
        requestLang,
        responseLang: targetLang,
      });
      if (!res?.waiting && Array.isArray(res.subtitles) && res.subtitles.length) {
        subtitlesPayload = res;
        usedClient = client.constructor.name;
        break;
      }
    } catch (_err) {
      // Try next iteration/client.
    }
    await sleep(Math.max(1, pollSeconds) * 1000);
  }
  if (subtitlesPayload) break;
}

if (!subtitlesPayload) {
  throw new Error("Failed to fetch subtitles list from Yandex API");
}

const subtitlesItems = subtitlesPayload.subtitles || [];
const selectedItem =
  subtitlesItems.find(
    (item) =>
      normalizeLang(item?.translatedLanguage) === targetLang &&
      item?.translatedUrl,
  ) ||
  subtitlesItems.find(
    (item) => normalizeLang(item?.language) === targetLang && item?.url,
  ) ||
  subtitlesItems.find((item) => item?.translatedUrl || item?.url);

const selectedUrl = selectedItem?.translatedUrl || selectedItem?.url;
if (!selectedUrl) {
  throw new Error("Subtitles list was returned, but no subtitle URL found");
}

const rawResponse = await fetch(selectedUrl, { redirect: "follow" });
if (!rawResponse.ok) {
  throw new Error(`Failed to download subtitle payload: HTTP ${rawResponse.status}`);
}
const payload = await rawResponse.json();
const lines = Array.isArray(payload?.subtitles) ? payload.subtitles : [];
if (!lines.length) {
  throw new Error("Subtitle payload is empty");
}

const withTimestampsPath = path.join(outDir, "transcript_with_timestamps.txt");
const plainTextPath = path.join(outDir, "transcript_plain.txt");

const withTimestamps = [];
const plain = [];
for (const line of lines) {
  const text = String(line?.text || "").trim();
  if (!text) continue;
  const startMs = Number(line?.startMs || 0);
  const durationMs = Number(line?.durationMs || 0);
  const endMs = Math.max(startMs, startMs + durationMs);
  withTimestamps.push(
    `[${msToSrtTime(startMs)} --> ${msToSrtTime(endMs)}] ${text}`,
  );
  plain.push(text);
}

await fs.mkdir(outDir, { recursive: true });
await fs.writeFile(withTimestampsPath, `${withTimestamps.join("\n")}\n`, "utf8");
await fs.writeFile(plainTextPath, `${plain.join("\n")}\n`, "utf8");

console.log(
  JSON.stringify({
    usedClient,
    selectedLanguage: selectedItem?.translatedLanguage || selectedItem?.language || "",
    selectedUrl,
    withTimestampsPath,
    plainTextPath,
    lines: plain.length,
  }),
);
