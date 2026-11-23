/* global pdfjsLib */
import {
  drawStamp,
  buildValidStream,
  DS_UNKNOWN,
  FORM_W,
} from "./stamp-render.js";

pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.min.js";

/** Locked stamp layout from stamp lab (version 4). */
const STAMP_CONFIG = {
  globalScale: 1.23,
  stampOffsetX: -3.3,
  stampOffsetY: -0.7,
  n4: {
    x: 6,
    y: 23.2,
    fontSize: 5.15,
    fontWeight: 360,
    textValid: "Signature valid",
    textInvalid: "Signature Not Verified",
  },
  n2: {
    x: 7.1,
    fontSize: 2.4,
    fontWeight: 400,
    lineHeight: 2.1,
    yOffset: 0,
    ys: [17.9, 15.8, 13.7, 11.6, 9.5],
    lines: [
      "Digitally signed by DS Unique",
      "Identification Authority of India",
      "06",
      "Date: 2026.08.28 10:57:17",
      "IST",
    ],
  },
  n1: { tx: 5.4, ty: 2.8, scale: 0.27, flipY: true },
  tick: {
    points100: [
      [24.68, 47.88],
      [16.26, 58.5],
      [44.2, 84.3],
      [42.8, 67.2],
      [90.6, 21.5],
      [77.1, 12.9],
      [40.1, 81.1],
    ],
    mapScale: 7,
    mapOx: 200,
    mapOy: 100,
    shadowDx: 16,
    shadowDy: 21,
    shadowColor: "#000000",
    fillColor: "#00a651",
    borderWidth: 8.5,
    borderColor: "#000000",
  },
};

const DISPLAY_SCALE = 2;
const RENDER_SCALE = () =>
  Math.min(6, Math.max(4, Math.round(window.devicePixelRatio * 2)));
const PRINT_RENDER_SCALE = 600 / 72;

let printBuildToken = 0;
/** True once the 600 DPI print copy holds every page (see printSourceCanvases). */
let printStoreComplete = false;
/** True from a Print click until print() returns or fails; blocks re-entry. */
let printing = false;
/** Bumped by each print and by resetApp, so a stale print never opens. */
let printToken = 0;
/** The real title; a print whose afterprint never fires must not leave " ". */
const PAGE_TITLE = document.title;
/** A print stylesheet that neither loads nor errors (hung server) gives up after this. */
const PRINT_STYLES_TIMEOUT_MS = 10000;
/** Same cap as the server's MAX_UPLOAD_BYTES; checked before uploading. */
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
const printStoreEl = () => document.getElementById("print-store");

const form = document.getElementById("form");
const errorEl = document.getElementById("error");
const upload = document.getElementById("upload");
const workspace = document.getElementById("workspace");
const pagesEl = document.getElementById("pages");
const docbar = document.getElementById("docbar");
const docbarTitle = document.getElementById("docbar-title");
const docbarSub = document.getElementById("docbar-sub");
const docbarAlert = document.getElementById("docbar-alert");
const printBtn = document.getElementById("print");
const pdfInput = document.getElementById("pdf");
const filePick = document.getElementById("filePick");
const fileLabel = document.getElementById("fileLabel");
const fileChosen = document.getElementById("fileChosen");
const passwordField = document.getElementById("passwordField");
const passwordHint = document.getElementById("passwordHint");
const passwordInput = document.getElementById("password");
const previewBtn = document.getElementById("previewBtn");
const validationModal = document.getElementById("validationModal");
const validationModalHeader = document.getElementById("validationModalHeader");
const validationModalTitle = document.getElementById("validationModalTitle");
const validationModalLead = document.getElementById("validationModalLead");
const validationModalBody = document.getElementById("validationModalBody");
const validationModalAction = document.getElementById("validationModalAction");

/** @type {{ sessionId: string|null, widgets: object[], validated: boolean, valid: boolean|null, validating: boolean, pdfDoc: object|null, sheets: object[], pendingValidation: object|null }} */
const app = {
  sessionId: null,
  widgets: [],
  validated: false,
  valid: null,
  validating: false,
  pdfDoc: null,
  sheets: [],
  pendingValidation: null,
};

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/** The file field never moves: only its text and colour change. */
function updateFileChosen() {
  const file = pdfInput.files[0];
  filePick.classList.toggle("has-file", Boolean(file));
  fileLabel.textContent = file ? "Change" : "Choose PDF";
  fileChosen.textContent = file ? `${file.name} (${formatBytes(file.size)})` : "No file chosen";
  fileChosen.title = file ? file.name : "";
}

pdfInput.addEventListener("change", onFileChosen);

/** Bumped per file pick, so a slow check for an earlier file can't win. */
let fileCheckToken = 0;

/**
 * Password field state. The field is always in the layout (so nothing jumps);
 * it is enabled only when pdf.js (in the browser, nothing uploaded) says the
 * picked PDF needs a password.
 *   idle: no file yet · checking · needed · not-needed · too-big
 */
let passwordState = "idle";

const PASSWORD_HINTS = {
  idle: "Choose a PDF first.",
  checking: "Checking PDF…",
  needed: "Usually the first 4 letters of the name in CAPITALS plus the birth year, e.g. NAME1990.",
  "not-needed": "No password needed: this PDF isn't protected.",
  "too-big": "This file is over the 20 MB limit.",
};

function setPasswordState(state) {
  passwordState = state;
  const needed = state === "needed";
  passwordField.dataset.state = state;
  passwordInput.disabled = !needed;
  passwordInput.required = needed;
  passwordInput.placeholder = state === "not-needed" ? "Not needed" : "PDF password";
  if (!needed) passwordInput.value = "";
  passwordHint.textContent = PASSWORD_HINTS[state];
  updatePreviewButton();
}

async function onFileChosen() {
  updateFileChosen();
  errorEl.hidden = true;
  passwordInput.value = "";
  const token = ++fileCheckToken;
  const file = pdfInput.files[0];
  if (!file) {
    setPasswordState("idle");
    return;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    setPasswordState("too-big");
    showError(new Error("File too large. The limit is 20 MB."));
    return;
  }
  setPasswordState("checking");
  let needs;
  try {
    needs = await pdfNeedsPassword(file);
  } catch {
    needs = true; // can't tell (damaged file?): ask for a password, the safe default
  }
  if (token !== fileCheckToken) return;
  setPasswordState(needs ? "needed" : "not-needed");
  (needs ? passwordInput : previewBtn).focus();
}

/** Preview is always shown; it is enabled only when there is something to open. */
function updatePreviewButton() {
  const ready =
    passwordState === "not-needed" ||
    (passwordState === "needed" && passwordInput.value.length > 0);
  previewBtn.disabled = !ready;
}

passwordInput.addEventListener("input", updatePreviewButton);

async function pdfNeedsPassword(file) {
  const data = new Uint8Array(await file.arrayBuffer());
  // Without an onPassword handler pdf.js rejects with PasswordException when
  // the PDF has an open password; owner-only (permissions) PDFs just open.
  const task = pdfjsLib.getDocument({ data, isEvalSupported: false });
  try {
    const doc = await task.promise;
    await doc.destroy();
    return false;
  } catch (err) {
    if (err?.name === "PasswordException") return true;
    throw err;
  } finally {
    task.destroy();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorEl.hidden = true;
  const file = pdfInput.files[0];
  const password = passwordState === "needed" ? passwordInput.value : "";
  if (!file) return;
  // The server rejects bigger uploads without reading them and closes the
  // connection, which fetch can report as "Cannot reach the server".
  if (file.size > MAX_UPLOAD_BYTES) {
    showError(new Error("File too large. The limit is 20 MB."));
    return;
  }

  const data = new FormData();
  data.append("pdf", file);
  data.append("password", password);

  try {
    const payload = await fetchJson("/api/preview", { method: "POST", body: data }, "Could not open PDF");
    await openPreview(payload);
  } catch (err) {
    showError(err);
  }
});

document.getElementById("again").addEventListener("click", () => {
  workspace.hidden = true;
  upload.hidden = false;
  pagesEl.innerHTML = "";
  pdfInput.value = "";
  onFileChosen();
  resetApp();
});

printBtn.addEventListener("click", () => {
  if (!app.validated || printing) return;
  clearAlert();
  printDocument();
});

/** Thrown when fetch itself fails (server stopped, port closed). */
class ServerUnreachableError extends Error {}

/**
 * fetch + JSON with readable errors. Any TypeError from fetch is a network
 * failure (Chrome: "Failed to fetch", Safari: "Load failed", Firefox:
 * "NetworkError ..."), so don't match on the browser's wording.
 */
async function fetchJson(url, options, fallbackError) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (err) {
    if (err instanceof TypeError) throw new ServerUnreachableError(err.message);
    throw err;
  }
  let payload;
  try {
    payload = await res.json();
  } catch {
    throw new Error(`Unexpected response from the server (HTTP ${res.status})`);
  }
  if (!res.ok) throw new Error(payload?.error || fallbackError);
  return payload;
}

function printSourceCanvases() {
  const store = printStoreEl();
  // Use the 600 DPI copy only once it holds every page; while it is still
  // building (or if building failed) print the on-screen pages instead.
  if (printStoreComplete && store?.children.length) {
    return [...store.querySelectorAll("canvas")];
  }
  return [...pagesEl.querySelectorAll("canvas")];
}

/** Remove print frames left behind (e.g. afterprint never fired) and the blank title. */
function removePrintFrames() {
  document.querySelectorAll("iframe[data-print-frame]").forEach((frame) => frame.remove());
  document.title = PAGE_TITLE;
}

function printDocument() {
  const canvases = printSourceCanvases();
  if (!canvases.length) return;
  removePrintFrames();
  const token = ++printToken;
  printing = true;

  let iframe = null;
  let win = null;
  let cleanedUp = false;
  // Where afterprint never fires, restore the title and drop the frame on the
  // user's next click or key press instead of leaving " " in the tab.
  const onNextInteraction = () => cleanup();
  const cleanup = () => {
    cleanedUp = true;
    if (token === printToken) {
      printing = false;
      document.title = PAGE_TITLE;
    }
    iframe?.remove();
    win?.removeEventListener("afterprint", cleanup);
    document.removeEventListener("pointerdown", onNextInteraction, true);
    document.removeEventListener("keydown", onNextInteraction, true);
  };
  const fail = (err) => {
    cleanup();
    // A print superseded by "Open another" or a newer print fails quietly.
    if (token !== printToken) return;
    const msg = err?.message || String(err);
    showError(new Error(msg.startsWith("Could not") ? msg : `Could not print: ${msg}`));
  };

  // Any throw here (doc.write, a huge toDataURL, ...) must not leave Print
  // locked, the title blank, or a frame attached.
  try {
    // CSP has no 'unsafe-inline' for styles: use CSSOM for the iframe and a
    // same-origin stylesheet (not an inline <style>) inside it.
    iframe = document.createElement("iframe");
    iframe.dataset.printFrame = "";
    iframe.style.cssText =
      "position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0;pointer-events:none";
    document.body.appendChild(iframe);

    win = iframe.contentWindow;
    const doc = win.document;
    doc.open();
    doc.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title> </title>
<link rel="stylesheet" href="/static/print-frame.css"></head><body></body></html>`);
    doc.close();
    const sheet = doc.querySelector("link[rel=stylesheet]");
    if (!sheet) throw new Error("Could not prepare the print view.");
    // Without these rules the 600 DPI images print at natural size (a corner
    // per sheet), so refuse to print rather than waste paper.
    let armSheetTimeout = () => {};
    const sheetReady = sheet.sheet
      ? Promise.resolve()
      : new Promise((resolve, reject) => {
          let timer = null;
          const stylesFailed = () =>
            reject(new Error("Could not load print styles. Is the app still running?"));
          sheet.onload = () => {
            clearTimeout(timer);
            resolve();
          };
          sheet.onerror = () => {
            clearTimeout(timer);
            stylesFailed();
          };
          // A hung server never fires load or error; don't leave Print locked.
          // Armed only after the (synchronous, possibly slow) image encoding
          // below, so a long encode can't beat an already-queued load event.
          armSheetTimeout = () => {
            timer = setTimeout(
              () => (sheet.sheet ? resolve() : stylesFailed()),
              PRINT_STYLES_TIMEOUT_MS,
            );
          };
        });
    // Real handling is the Promise.all below; this only keeps a rejection from
    // being "unhandled" if the canvas loop throws before that is attached.
    sheetReady.catch(() => {});

    for (const canvas of canvases) {
      const img = doc.createElement("img");
      img.src = canvas.toDataURL("image/png");
      doc.body.appendChild(img);
    }
    armSheetTimeout();
    const imagesReady = Promise.all(
      [...doc.images].map((img) =>
        img.complete
          ? null
          : new Promise((resolve) => {
              img.onload = resolve;
              img.onerror = resolve;
            }),
      ),
    );

    document.title = " ";
    win.addEventListener("afterprint", cleanup);

    Promise.all([sheetReady, imagesReady])
      .then(() => {
        if (token !== printToken) {
          // "Open another" or a newer print happened while we waited.
          cleanup();
          return;
        }
        try {
          win.focus();
          win.print();
          printBtn.focus({ preventScroll: true });
          if (!cleanedUp) {
            document.addEventListener("pointerdown", onNextInteraction, { capture: true, once: true });
            document.addEventListener("keydown", onNextInteraction, { capture: true, once: true });
          }
        } finally {
          // print() returns once the dialog is up or closed; afterprint may
          // never fire in some browsers, so don't leave Print locked.
          if (token === printToken) printing = false;
        }
      })
      .catch(fail);
  } catch (err) {
    fail(err);
  }
}

/**
 * Show an app error where the user can see it: the red line on the upload
 * screen, or the amber alert inside the document bar once a PDF is open.
 * The alert never changes the bar's verdict colour or title.
 */
function showError(err) {
  const onDocument = !workspace.hidden;
  let msg = err?.message || String(err);
  if (err instanceof ServerUnreachableError) {
    msg = onDocument
      ? "Cannot reach the server. Start the app again, then open the PDF again."
      : "Cannot reach the server. Run ./everify-app in the project folder, then refresh this page.";
  }
  if (onDocument) {
    docbarAlert.textContent = msg;
    docbarAlert.hidden = false;
  } else {
    errorEl.textContent = msg;
    errorEl.hidden = false;
  }
}

function clearAlert() {
  docbarAlert.textContent = "";
  docbarAlert.hidden = true;
  errorEl.hidden = true;
}

function resetApp() {
  app.sessionId = null;
  app.widgets = [];
  app.validated = false;
  app.valid = null;
  app.validating = false;
  app.pdfDoc = null;
  app.sheets = [];
  app.pendingValidation = null;
  printing = false;
  printToken += 1;
  removePrintFrames();
  clearPrintStore();
  clearAlert();
  hideValidationModal();
}

function clearPrintStore() {
  printBuildToken += 1;
  printStoreComplete = false;
  printStoreEl()?.replaceChildren();
}

function schedulePrintStore() {
  printBuildToken += 1;
  const token = printBuildToken;
  const run = () => {
    // A failed build leaves printStoreComplete false, so Print falls back to
    // the on-screen pages: still complete, just at screen resolution.
    buildPrintStore(token).catch((err) => console.warn("Print copy not built:", err));
  };
  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(run, { timeout: 3000 });
  } else {
    setTimeout(run, 300);
  }
}

async function buildPrintStore(token) {
  const store = printStoreEl();
  if (!store || !app.pdfDoc || !app.validated || token !== printBuildToken) return;
  printStoreComplete = false;
  store.replaceChildren();

  for (const sheet of app.sheets) {
    if (token !== printBuildToken) return;
    const viewport = sheet.page.getViewport({ scale: PRINT_RENDER_SCALE });
    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext("2d");
    await sheet.page.render({ canvasContext: ctx, viewport }).promise;
    // "Open another" may have cleared the store while this page rendered.
    if (token !== printBuildToken) return;

    if (app.valid) {
      for (const widget of app.widgets) {
        if (widget.pageIndex !== sheet.pageIndex) continue;
        drawValidityMark(ctx, widget, viewport, true);
      }
    }

    const wrap = document.createElement("div");
    wrap.className = "sheet";
    wrap.appendChild(canvas);
    store.appendChild(wrap);
  }
  if (token === printBuildToken) printStoreComplete = true;
}

function updateDocbar() {
  docbar.classList.remove("valid", "invalid", "preview", "validating");
  printBtn.disabled = !app.validated;
  printBtn.title = app.validated ? "" : "Verify the signature first";

  if (app.validating) {
    docbar.classList.add("validating");
    docbarTitle.textContent = "Verifying signature…";
    docbarSub.textContent = "";
    return;
  }
  if (!app.validated) {
    docbar.classList.add("preview");
    const visible = app.widgets.some(hasVisibleBox);
    docbarTitle.textContent = visible
      ? "Preview: click the ? mark to verify"
      : "Preview: click the page to verify";
    docbarSub.textContent = visible
      ? "The stamp shown is from your PDF until you verify"
      : "This signature has no visible box, so the whole page is the target";
    return;
  }
  docbar.classList.toggle("valid", app.valid);
  docbar.classList.toggle("invalid", !app.valid);
  docbarTitle.textContent = app.valid
    ? "Signed and all signatures are valid."
    : "At least one signature has problems.";
  const reason = app.valid ? null : failureReasonOf(app.widgets);
  const first = app.widgets[0];
  docbarSub.textContent = reason
    ? `Reason: ${reason}.`
    : first
      ? first.signerCn || cnFromSigner(first.signer)
      : "";
}

/** First failing signature's short reason from the server, if any. */
function failureReasonOf(items) {
  const failed = (items || []).map((w) => w.report || w).find((r) => r && !r.valid);
  return failed?.failureReason || null;
}

async function openPreview(payload) {
  resetApp();
  app.sessionId = payload.sessionId;
  app.widgets = payload.widgets;

  upload.hidden = true;
  workspace.hidden = false;
  pagesEl.innerHTML = "";
  updateDocbar();

  try {
    await renderPreviewPages(payload.sessionId);
  } catch (err) {
    // "Open another" (or a newer PDF) while this one was loading: drop it.
    if (app.sessionId !== payload.sessionId) return;
    throw new Error(`Could not display this PDF: ${err?.message || err}`);
  }
}

async function renderPreviewPages(sessionId) {
  // isEvalSupported: false closes CVE-2024-4367 (font FontMatrix compiled via
  // new Function). The server's CSP also forbids eval; keep both layers.
  const pdfDoc = await pdfjsLib.getDocument({
    url: `/api/pdf/${sessionId}`,
    isEvalSupported: false,
  }).promise;
  // Every await below can outlive "Open another"; stop if this PDF is gone.
  const stale = () => app.sessionId !== sessionId;
  if (stale()) return;
  app.pdfDoc = pdfDoc;
  const renderScale = RENDER_SCALE();

  for (let i = 1; i <= pdfDoc.numPages; i++) {
    const page = await pdfDoc.getPage(i);
    if (stale()) return;
    const viewport = page.getViewport({ scale: renderScale });
    const displayVp = page.getViewport({ scale: DISPLAY_SCALE });
    const wrap = document.createElement("div");
    wrap.className = "sheet";
    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = `${displayVp.width}px`;
    canvas.style.height = `${displayVp.height}px`;
    canvas.classList.add("page-canvas");
    wrap.appendChild(canvas);
    pagesEl.appendChild(wrap);

    const ctx = canvas.getContext("2d");
    const sheet = { wrap, canvas, ctx, viewport, page, pageIndex: i - 1 };
    app.sheets.push(sheet);

    await renderSheet(sheet);
    if (stale()) return;
    bindSheetClicks(sheet);
  }
}

async function renderSheet(sheet) {
  const { ctx, viewport, page } = sheet;
  await page.render({ canvasContext: ctx, viewport }).promise;

  if (!app.validated) {
    return;
  }

  for (const widget of app.widgets) {
    if (widget.pageIndex !== sheet.pageIndex) continue;
    drawValidityMark(ctx, widget, viewport, app.valid);
  }
}

async function redrawAllSheets() {
  for (const sheet of app.sheets) {
    await renderSheet(sheet);
  }
}

function bindSheetClicks(sheet) {
  const { canvas, viewport, pageIndex } = sheet;
  canvas.addEventListener("click", async (e) => {
    if (app.validated || app.validating) return;
    if (!hitWidget(e, canvas, viewport, pageIndex)) return;
    await runValidation();
  });
  canvas.addEventListener("mousemove", (e) => {
    if (app.validated || app.validating) {
      canvas.classList.remove("sig-hit");
      return;
    }
    canvas.classList.toggle("sig-hit", hitWidget(e, canvas, viewport, pageIndex));
  });
}

function hitWidget(event, canvas, viewport, pageIndex) {
  const widgets = app.widgets.filter((w) => w.pageIndex === pageIndex);
  if (!widgets.length) return false;
  const rect = canvas.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * canvas.width;
  const y = ((event.clientY - rect.top) / rect.height) * canvas.height;
  for (const widget of widgets) {
    // No visible box (invisible signature): the whole page is the target.
    if (!hasVisibleBox(widget)) return true;
    const box = widgetCanvasRect(widget, viewport);
    if (x >= box.left && x <= box.right && y >= box.top && y <= box.bottom) {
      return true;
    }
  }
  return false;
}

function hasVisibleBox(widget) {
  const [x1, y1, x2, y2] = widget.rect || [0, 0, 0, 0];
  return Math.abs(x2 - x1) > 0 && Math.abs(y2 - y1) > 0;
}

/**
 * Widget rectangle in canvas pixels. pdf.js's viewport transform handles
 * CropBox offsets, a MediaBox that doesn't start at 0,0, and /Rotate. For an
 * e-Aadhaar page (MediaBox at 0,0, no CropBox, no rotation) it equals the
 * earlier x * scale, (pageH - y) * scale maths, so the tuned stamp stays put.
 */
function widgetCanvasRect(widget, viewport) {
  const [ax, ay, bx, by] = viewport.convertToViewportRectangle(widget.rect);
  return {
    left: Math.min(ax, bx),
    top: Math.min(ay, by),
    right: Math.max(ax, bx),
    bottom: Math.max(ay, by),
  };
}

async function runValidation() {
  if (app.validating || app.validated || !app.sessionId) return;
  app.validating = true;
  clearAlert();
  updateDocbar();
  const sid = app.sessionId;

  try {
    const payload = await fetchJson(
      "/api/validate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: sid }),
      },
      "Validation failed",
    );
    // The user may have opened another PDF meanwhile: never apply this
    // verdict (or its error) to a different document.
    if (app.sessionId !== sid) return;
    app.validating = false;
    app.pendingValidation = payload;
    updateDocbar();
    showValidationModal(payload);
  } catch (err) {
    if (app.sessionId !== sid) return;
    app.validating = false;
    updateDocbar();
    showError(err);
  }
}

function cnFromSigner(signer) {
  if (!signer) return "Unknown";
  const m = String(signer).match(/Common Name:\s*([^,]+)/i);
  return m ? m[1].trim() : String(signer).split(",")[0].trim();
}

function formatTrustAnchor(anchor) {
  if (!anchor) return "Not established";
  return cnFromSigner(anchor);
}

function formatDisplayTime(raw) {
  if (!raw || raw === "Unknown") return "Unknown";
  return String(raw).replace("T", " ").replace(/\+00:00$/, " UTC");
}

function yesNo(value) {
  return value ? "Yes" : "No";
}

function buildValidationModalBody(payload) {
  const reports = payload.reports?.length
    ? payload.reports
    : payload.widgets.map((w) => w.report || w).filter(Boolean);

  const sigBlocks = reports
    .map((r, i) => {
      const title = reports.length > 1 ? `Signature ${i + 1}` : "Digital signature";
      return `
        <section class="modal-section">
          <h3>${title}</h3>
          <dl class="modal-dl">
            <div><dt>Signer</dt><dd>${escapeHtml(r.signerCn || cnFromSigner(r.signer))}</dd></div>
            <div><dt>Signed at</dt><dd>${escapeHtml(formatDisplayTime(r.signingTime))}</dd></div>
            <div><dt>Trust anchor</dt><dd>${escapeHtml(formatTrustAnchor(r.trustAnchor))}</dd></div>
            <div><dt>Certificate trusted</dt><dd>${yesNo(r.certificateTrusted)}</dd></div>
            <div><dt>Integrity intact</dt><dd>${yesNo(r.integrityIntact)}</dd></div>
            <div><dt>Covers entire file</dt><dd>${yesNo(r.coversEntireFile)}</dd></div>
            <div><dt>Digest</dt><dd>${escapeHtml(r.digestAlgorithm || "Unknown")}</dd></div>
            <div><dt>Signature type</dt><dd>${escapeHtml(r.signatureMechanism || "Unknown")}</dd></div>
            <div><dt>SHA-256</dt><dd><code>${escapeHtml(r.sha256 || "Unknown")}</code></dd></div>
          </dl>
        </section>`;
    })
    .join("");

  return `
    ${sigBlocks}
    <section class="modal-section">
      <h3>How validation works</h3>
      <p class="modal-explainer">
        Validation runs locally on your machine using <strong>pyHanko</strong>, the same
        class of checks Adobe Acrobat performs, without sending your PDF to any server.
        <ol>
          <li>Read the embedded PKCS#7 signature from the original file bytes (decrypt in memory only).</li>
          <li>Verify the document digest (${escapeHtml(reports[0]?.digestAlgorithm || "SHA-256")}) and RSA signature.</li>
          <li>Build the signer certificate chain up to a trusted root.</li>
          <li>Trust roots are <strong>CCA India 2022</strong> certificates bundled with this app (India PKI).</li>
          <li>Confirm the signature covers the entire file and no disallowed changes were made.</li>
        </ol>
      </p>
    </section>
    <section class="modal-section">
      <h3>Checked at</h3>
      <dl class="modal-dl">
        <div><dt>Validation time</dt><dd>${escapeHtml(formatDisplayTime(reports[0]?.validatedAt))}</dd></div>
        <div><dt>Original PDF</dt><dd>Unchanged. Only the on-screen stamp is drawn for preview and print.</dd></div>
      </dl>
    </section>`;
}

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showValidationModal(payload) {
  const valid = Boolean(payload.valid);
  validationModalHeader.classList.toggle("valid", valid);
  validationModalHeader.classList.toggle("invalid", !valid);
  validationModalTitle.textContent = valid
    ? "Signature verified"
    : "Signature not verified";
  const reason = valid ? null : failureReasonOf(payload.reports?.length ? payload.reports : payload.widgets);
  validationModalLead.textContent = valid
    ? "This e-Aadhaar signature is cryptographically valid and chains to India's CCA root."
    : reason
      ? `Reason: ${reason}.`
      : "The signature could not be trusted or the document integrity check failed.";
  validationModalBody.innerHTML = buildValidationModalBody(payload);
  validationModalAction.textContent = valid ? "OK" : "Close";
  validationModal.hidden = false;
  validationModalAction.focus();
}

function hideValidationModal() {
  if (validationModal) validationModal.hidden = true;
}

async function completeValidation() {
  const payload = app.pendingValidation;
  if (!payload) {
    hideValidationModal();
    return;
  }
  app.validated = true;
  app.valid = payload.valid;
  app.widgets = payload.widgets;
  app.pendingValidation = null;
  hideValidationModal();
  clearAlert();
  updateDocbar();
  try {
    if (app.valid) {
      await redrawAllSheets();
      schedulePrintStore();
    }
  } catch (err) {
    showError(err);
  }
}

validationModalAction?.addEventListener("click", () => completeValidation());
validationModal?.querySelectorAll("[data-dismiss=validation]").forEach((el) => {
  el.addEventListener("click", () => completeValidation());
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && validationModal && !validationModal.hidden) {
    completeValidation();
  }
});

function formatSigningDate(raw) {
  if (!raw || raw === "Unknown") return null;
  const s = String(raw).replace("T", " ").trim();
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}:\d{2}:\d{2})/);
  if (m) return `Date: ${m[1]}.${m[2]}.${m[3]} ${m[4]}`;
  const bare = s.slice(0, 19);
  return bare ? `Date: ${bare}` : null;
}

/** Split text into at most `maxLines` lines of about `width` characters (last line may run long). */
function wrapLine(text, width, maxLines) {
  const words = String(text || "Unknown").split(/\s+/).filter(Boolean);
  const lines = [""];
  for (const word of words) {
    const last = lines.length - 1;
    if (lines[last] && (lines[last] + " " + word).length > width && lines.length < maxLines) {
      lines.push(word);
    } else {
      lines[last] = lines[last] ? `${lines[last]} ${word}` : word;
    }
  }
  return lines;
}

function bodyLines(widget) {
  const ap = widget.appearance || {};
  // e-Aadhaar always carries its own body lines (ap.n2Lines). Anything else
  // gets the actual signer's name: never claim UIDAI for a different signer.
  const fromPdf =
    ap.n2Lines && ap.n2Lines.length
      ? [...ap.n2Lines]
      : [
          "Digitally signed by",
          ...wrapLine(widget.signerCn || cnFromSigner(widget.signer), 34, 2),
          ...(formatSigningDate(widget.signingTime) ? ["Date:"] : []),
        ];
  const dateLine = formatSigningDate(widget.signingTime);
  if (dateLine) {
    const dateIdx = fromPdf.findIndex((l) => /^Date:/i.test(l));
    if (dateIdx >= 0) fromPdf[dateIdx] = dateLine;
    else if (fromPdf.length >= 4) fromPdf[3] = dateLine;
    else fromPdf.push(dateLine);
  }
  return fromPdf;
}

function stampOpts(widget) {
  const tick = { ...STAMP_CONFIG.tick };
  return {
    n4: { ...STAMP_CONFIG.n4 },
    n2: {
      ...STAMP_CONFIG.n2,
      lines: bodyLines(widget),
    },
    n1: { ...STAMP_CONFIG.n1 },
    tick,
    dsValid: buildValidStream(tick),
    dsUnknown: DS_UNKNOWN,
    textColor: "#000000",
  };
}

/**
 * Rotated pages: draw in the page's own (PDF) space through pdf.js's viewport
 * transform, so the stamp turns with the page like the PDF's native appearance.
 * Frame: origin at the widget's top-left, y down, 1 unit = 1 pt.
 */
function drawRotatedValidityMark(ctx, widget, viewport) {
  const [x1, y1, x2, y2] = widget.rect;
  const ap = widget.appearance || {};
  const formW = ap.formWidth || x2 - x1;
  const formH = ap.formHeight || y2 - y1;
  ctx.save();
  ctx.transform(...viewport.transform);
  ctx.translate(x1, y2);
  ctx.scale(1, -1);
  // Cover the whole widget: non-Acrobat appearances fall back to a 50x30
  // form size (see verify._appearance), smaller than the box.
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, Math.max(formW, x2 - x1), Math.max(formH, y2 - y1));
  drawStamp(ctx, (formW / FORM_W) * (STAMP_CONFIG.globalScale ?? 1), true, {
    ...stampOpts(widget),
    originX: STAMP_CONFIG.stampOffsetX ?? 0,
    originY: STAMP_CONFIG.stampOffsetY ?? 0,
    skipBackground: true,
  });
  ctx.restore();
}

function drawValidityMark(ctx, widget, viewport, valid) {
  if (!valid) return;

  const [x1, y1, x2, y2] = widget.rect;
  const scale = viewport.scale;
  const ap = widget.appearance || {};

  if (viewport.rotation % 360 !== 0) {
    drawRotatedValidityMark(ctx, widget, viewport);
    return;
  }

  // Unrotated pages (every e-Aadhaar): the tuned path, kept pixel-identical.
  const { left: boxL, top: boxT } = widgetCanvasRect(widget, viewport);
  const boxW = (ap.formWidth || x2 - x1) * scale;
  const boxH = (ap.formHeight || y2 - y1) * scale;
  const stampScale = (boxW / FORM_W) * (STAMP_CONFIG.globalScale ?? 1);
  const ox = (STAMP_CONFIG.stampOffsetX ?? 0) * scale;
  const oy = (STAMP_CONFIG.stampOffsetY ?? 0) * scale;

  ctx.fillStyle = "#ffffff";
  if (ap.n2Lines?.length) {
    // Acrobat-layered appearance (every e-Aadhaar): unchanged tuned cover.
    ctx.fillRect(boxL, boxT, boxW, boxH);
  } else {
    // Other appearances fall back to a 50x30 form size; cover the whole box.
    ctx.fillRect(boxL, boxT, Math.max(boxW, (x2 - x1) * scale), Math.max(boxH, (y2 - y1) * scale));
  }

  drawStamp(ctx, stampScale, true, {
    ...stampOpts(widget),
    originX: boxL + ox,
    originY: boxT + oy,
    skipBackground: true,
  });
}
