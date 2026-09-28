// Renders scene.html to docs/media/cloakroom-explainer.{mp4,webm}, a poster, and a README thumbnail.
// node render.mjs            full render
// node render.mjs still 12.5 out.png
import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MEDIA = path.resolve(HERE, "..");
const SCENE = `file://${path.join(HERE, "scene.html")}`;
const CHROME = process.env.CHROME || "/usr/local/bin/google-chrome";
const FPS = 30;
const WORKERS = 4;
const POSTER_T = 4.5;

async function openScene(browser, query = "") {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(SCENE + query);
  await page.evaluate(() => window.ready);
  return page;
}

async function still(browser, t, out, query = "") {
  const page = await openScene(browser, query);
  await page.evaluate((x) => window.render(x), t);
  await page.screenshot({ path: out });
}

async function frames(browser, dir) {
  const probe = await openScene(browser);
  const duration = await probe.evaluate(() => window.DURATION);
  await probe.close();
  const total = Math.round(duration * FPS);
  let next = 0;
  const worker = async () => {
    const page = await openScene(browser);
    while (next < total) {
      const i = next++;
      await page.evaluate((x) => window.render(x), i / FPS);
      await page.screenshot({ path: path.join(dir, `${String(i).padStart(5, "0")}.png`) });
      if (i % 150 === 0) console.log(`frame ${i}/${total}`);
    }
  };
  await Promise.all(Array.from({ length: WORKERS }, worker));
}

function encode(dir) {
  const input = ["-y", "-framerate", String(FPS), "-i", path.join(dir, "%05d.png")];
  execFileSync("ffmpeg", [
    ...input, "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-tune", "animation",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    path.join(MEDIA, "cloakroom-explainer.mp4"),
  ], { stdio: "inherit" });
  execFileSync("ffmpeg", [
    ...input, "-c:v", "libvpx-vp9", "-crf", "36", "-b:v", "0", "-row-mt", "1",
    "-deadline", "good", "-cpu-used", "2", "-pix_fmt", "yuv420p",
    path.join(MEDIA, "cloakroom-explainer.webm"),
  ], { stdio: "inherit" });
}

const browser = await chromium.launch({ executablePath: CHROME, args: ["--allow-file-access-from-files"] });
if (process.argv[2] === "still") {
  await still(browser, Number(process.argv[3]), process.argv[4]);
  await browser.close();
  process.exit(0);
}
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cloakroom-frames-"));
await frames(browser, dir);
await still(browser, POSTER_T, path.join(MEDIA, "cloakroom-explainer-poster.png"));
await still(browser, POSTER_T, path.join(MEDIA, "cloakroom-explainer-thumb.png"), "?play");
await browser.close();
encode(dir);
fs.rmSync(dir, { recursive: true });
