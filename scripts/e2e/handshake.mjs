// One turn through the real display, in headless Chromium.
//
// What it proves, in order: the client loads, a typed utterance reaches
// the host, the host routes it to a tool on the example MCP server, the
// tool's own words come back as the spoken answer, the card named by that
// tool is fetched and mounted, and the card's handshake completes far
// enough that it is handed its facts and draws them.
import puppeteer from "puppeteer-core";
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";

const TARGET = process.env.DISPLAY_URL ?? "http://127.0.0.1:8090/";
const SHOTS = process.env.SHOT_DIR ?? new URL("../../docs/", import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

function chromePath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const candidates = [
    "ls -d $HOME/.cache/puppeteer/chrome/*/chrome-linux64/chrome 2>/dev/null | head -1",
    "which chromium 2>/dev/null",
    "which google-chrome 2>/dev/null",
  ];
  for (const probe of candidates) {
    const found = execSync(probe, { shell: "/bin/bash" }).toString().trim();
    if (found) return found;
  }
  throw new Error("no Chromium found; set CHROME_PATH");
}

let failures = 0;
const check = (ok, line) => {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${line}`);
  if (!ok) failures += 1;
};

const browser = await puppeteer.launch({
  executablePath: chromePath(),
  headless: "new",
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--window-size=1600,900"],
  defaultViewport: { width: 1600, height: 900, deviceScaleFactor: 2 },
});
const page = await browser.newPage();
page.on("pageerror", (e) => console.log("  [pageerror]", String(e).slice(0, 200)));
page.on("response", (r) => {
  if (r.url().includes("/turn") && r.status() !== 200) {
    void r.text().then((body) => console.log(`  [http ${r.status()}] ${body.slice(0, 200)}`));
  }
});

await page.goto(TARGET, { waitUntil: "networkidle2", timeout: 60000 });
check(true, `loaded ${TARGET}`);

// The display disables its input while a turn is in flight, and the input
// is controlled by React — so a script types into a disabled field, or
// clicks before the value has reached state and submits an empty string.
// Wait for the field, then for the button to arm.
await page.waitForFunction(() => {
  const input = document.querySelector('[data-testid="typed-input"]');
  return Boolean(input) && !input.disabled;
}, { timeout: 30000 });
await page.type('[data-testid="typed-input"]', "What's on today?");
await page.waitForFunction(() => {
  const send = document.querySelector('[data-testid="typed-send"]');
  return Boolean(send) && !send.disabled;
}, { timeout: 30000 });
await page.click('[data-testid="typed-send"]');

await page.waitForFunction(
  () => (document.querySelector('[data-testid="spoken"]')?.textContent ?? "").length > 10,
  { timeout: 60000 },
);
const spoken = await page.$eval('[data-testid="spoken"]', (n) => n.textContent ?? "");
const tools = await page.$eval('[data-testid="spoken"]', (n) => n.dataset.tools ?? "");
const card = await page.$eval('[data-testid="spoken"]', (n) => n.dataset.card ?? "");

console.log(`\n  spoken: ${spoken}\n`);
check(/day \d+ of \d+/i.test(spoken), "the tool's own words came through");
check(!spoken.trimStart().startsWith("{"), "the answer is a sentence, not a payload");
check(tools === "get_today", `a fast lane routed it (${tools})`);
check(card === "ui://example/today", `the tool named its card (${card})`);

// The card is mounted and handed its facts. Waiting on the render counter
// rather than the app name: the name is set when the card's script runs,
// which is before any data has reached it.
let drawn = { name: null, count: 0 };
for (let i = 0; i < 60; i += 1) {
  const frame = page.frames().find((f) => f.parentFrame() === page.mainFrame());
  if (frame) {
    try {
      drawn = await frame.evaluate(() => ({
        name: window.CARD_APP_NAME ?? null,
        count: window.CARD_RENDERED || 0,
        text: document.body.innerText,
      }));
      if (drawn.name === "example-today-card" && drawn.count > 0) break;
    } catch { /* the document is being replaced; look again */ }
  }
  await new Promise((r) => setTimeout(r, 250));
}
check(drawn.name === "example-today-card", `the card mounted (${drawn.name})`);
check(drawn.count > 0, `the handshake completed and the card drew (${drawn.count})`);
check(/\d{1,3}%/.test(drawn.text ?? ""), "the card shows a figure from the tool's structure");

await page.screenshot({ path: `${SHOTS}/example.png` });
console.log(`  wrote ${SHOTS}/example.png`);

console.log(`\nfailures=${failures}`);
await browser.close();
process.exit(failures > 0 ? 1 : 0);
