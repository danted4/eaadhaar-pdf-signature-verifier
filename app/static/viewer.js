/* global pdfjsLib from CDN */
import {
  drawStamp,
  buildValidStream,
  DS_UNKNOWN,
  FORM_W,
} from "./stamp-render.js";

pdfjsLib.GlobalWorkerOptions.workerSrc =
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

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
const printStoreEl = () => document.getElementById("print-store");

const form = document.getElementById("form");
const errorEl = document.getElementById("error");
const upload = document.getElementById("upload");
const workspace = document.getElementById("workspace");
const pagesEl = document.getElementById("pages");
const docbar = document.getElementById("docbar");
const docbarTitle = document.getElementById("docbar-title");
const docbarSub = document.getElementById("docbar-sub");
const printBtn = document.getElementById("print");
const pdfInput = document.getElementById("pdf");
const filePick = document.getElementById("filePick");
const fileLabel = document.getElementById("fileLabel");
const fileChosen = document.getElementById("fileChosen");
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

function updateFileChosen() {
  const file = pdfInput.files[0];
  if (file) {
    fileLabel.textContent = "Change PDF";
    filePick.classList.add("has-file");
    fileChosen.hidden = false;
    fileChosen.textContent = `${file.name} (${formatBytes(file.size)})`;
  } else {
    fileLabel.textContent = "Choose PDF";
    filePick.classList.remove("has-file");
    fileChosen.hidden = true;
    fileChosen.textContent = "";
  }
}

pdfInput.addEventListener("change", updateFileChosen);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorEl.hidden = true;
  const file = pdfInput.files[0];
  const password = document.getElementById("password").value;
  if (!file) return;

  const data = new FormData();
  data.append("pdf", file);
  data.append("password", password);

  try {
    const res = await fetch("/api/preview", { method: "POST", body: data });
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.error || "Could not open PDF");
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
  updateFileChosen();
  resetApp();
});

printBtn.addEventListener("click", () => {
  if (app.validated) window.print();
});

function showError(err) {
  const msg =
    err instanceof TypeError && /fetch/i.test(String(err.message))
      ? "Cannot reach the server. Run ./everify-app in the project folder, then refresh this page."
      : err.message;
  errorEl.textContent = msg;
  errorEl.hidden = false;
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
  clearPrintStore();
  hideValidationModal();
}

function clearPrintStore() {
  printBuildToken += 1;
  printStoreEl()?.replaceChildren();
}

function schedulePrintStore() {
  printBuildToken += 1;
  const token = printBuildToken;
  const run = () => {
    buildPrintStore(token).catch(() => {});
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
  store.replaceChildren();

  for (const sheet of app.sheets) {
    if (token !== printBuildToken) return;
    const viewport = sheet.page.getViewport({ scale: PRINT_RENDER_SCALE });
    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext("2d");
    await sheet.page.render({ canvasContext: ctx, viewport }).promise;

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
    docbarTitle.textContent = "Preview — click the ? mark to verify";
    docbarSub.textContent = "The stamp shown is from your PDF until you verify";
    return;
  }
  docbar.classList.toggle("valid", app.valid);
  docbar.classList.toggle("invalid", !app.valid);
  docbarTitle.textContent = app.valid
    ? "Signed and all signatures are valid."
    : "At least one signature has problems.";
  const first = app.widgets[0];
  docbarSub.textContent = first
    ? first.signer.split(",")[0].replace("Common Name: ", "")
    : "";
}

async function openPreview(payload) {
  resetApp();
  app.sessionId = payload.sessionId;
  app.widgets = payload.widgets;

  upload.hidden = true;
  workspace.hidden = false;
  pagesEl.innerHTML = "";
  updateDocbar();

  app.pdfDoc = await pdfjsLib.getDocument(`/api/pdf/${payload.sessionId}`).promise;
  const renderScale = RENDER_SCALE();

  for (let i = 1; i <= app.pdfDoc.numPages; i++) {
    const page = await app.pdfDoc.getPage(i);
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
    const box = widgetCanvasRect(widget, viewport);
    if (x >= box.left && x <= box.right && y >= box.top && y <= box.bottom) {
      return true;
    }
  }
  return false;
}

function widgetCanvasRect(widget, viewport) {
  const [x1, y1, x2, y2] = widget.rect;
  const [, , , pageH] = widget.mediaBox;
  const sx = viewport.width / viewport.viewBox[2];
  const sy = viewport.height / viewport.viewBox[3];
  const [left, top] = pdfToCanvas(x1, y2, pageH, sx, sy);
  const [right, bottom] = pdfToCanvas(x2, y1, pageH, sx, sy);
  return { left, top, right, bottom };
}

async function runValidation() {
  if (app.validating || app.validated || !app.sessionId) return;
  app.validating = true;
  updateDocbar();
  errorEl.hidden = true;

  try {
    const res = await fetch("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: app.sessionId }),
    });
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.error || "Validation failed");
    app.validating = false;
    app.pendingValidation = payload;
    updateDocbar();
    showValidationModal(payload);
  } catch (err) {
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
  if (!anchor) return "Unknown";
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
            <div><dt>Digest</dt><dd>${escapeHtml(r.digestAlgorithm || "—")}</dd></div>
            <div><dt>Signature type</dt><dd>${escapeHtml(r.signatureMechanism || "—")}</dd></div>
            <div><dt>SHA-256</dt><dd><code>${escapeHtml(r.sha256 || "—")}</code></dd></div>
          </dl>
        </section>`;
    })
    .join("");

  return `
    ${sigBlocks}
    <section class="modal-section">
      <h3>How validation works</h3>
      <p class="modal-explainer">
        Validation runs locally on your machine using <strong>pyHanko</strong> — the same
        class of checks Adobe Acrobat performs — without sending your PDF to any server.
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
        <div><dt>Original PDF</dt><dd>Unchanged — only the on-screen stamp is drawn for preview/print.</dd></div>
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
  validationModalLead.textContent = valid
    ? "This e-Aadhaar signature is cryptographically valid and chains to India's CCA root."
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

function pdfToCanvas(pageX, pageY, pageH, sx, sy) {
  return [pageX * sx, (pageH - pageY) * sy];
}

function formatSigningDate(raw) {
  if (!raw || raw === "Unknown") return null;
  const s = String(raw).replace("T", " ").trim();
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}:\d{2}:\d{2})/);
  if (m) return `Date: ${m[1]}.${m[2]}.${m[3]} ${m[4]}`;
  const bare = s.slice(0, 19);
  return bare ? `Date: ${bare}` : null;
}

function bodyLines(widget) {
  const ap = widget.appearance || {};
  const fromPdf =
    ap.n2Lines && ap.n2Lines.length
      ? [...ap.n2Lines]
      : [
          "Digitally signed by DS Unique",
          "Identification Authority of India",
          "06",
          "Date:",
          "IST",
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

function drawValidityMark(ctx, widget, viewport, valid) {
  if (!valid) return;

  const [x1, , x2] = widget.rect;
  const [, , , pageH] = widget.mediaBox;
  const sx = viewport.width / viewport.viewBox[2];
  const sy = viewport.height / viewport.viewBox[3];
  const ap = widget.appearance || {};
  const formW = ap.formWidth || x2 - x1;

  const [boxL, boxT] = pdfToCanvas(x1, widget.rect[3], pageH, sx, sy);
  const boxW = formW * sx;
  const boxH = (ap.formHeight || widget.rect[3] - widget.rect[1]) * sy;
  const stampScale = (boxW / FORM_W) * (STAMP_CONFIG.globalScale ?? 1);
  const ox = (STAMP_CONFIG.stampOffsetX ?? 0) * sx;
  const oy = (STAMP_CONFIG.stampOffsetY ?? 0) * sy;

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(boxL, boxT, boxW, boxH);

  drawStamp(ctx, stampScale, true, {
    ...stampOpts(widget),
    originX: boxL + ox,
    originY: boxT + oy,
    skipBackground: true,
  });
}
