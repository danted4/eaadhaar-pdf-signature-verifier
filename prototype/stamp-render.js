/**
 * e-Aadhaar signature stamp — PDF-exact layout (50×30 pt form).
 * Valid: n1 icon (behind) → n2 body → n4 title (on top).
 */

export const FORM_W = 50;
export const FORM_H = 30;

export const DEFAULTS = {
  version: 4,
  globalScale: 1.23,
  stampOffsetX: -3.3,
  stampOffsetY: -0.7,
  form: { width: 50, height: 30 },
  previewScale: 16,
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

/** @deprecated use DEFAULTS */
export const STAMP = {
  n4: DEFAULTS.n4,
  n2: DEFAULTS.n2,
  n1: DEFAULTS.n1,
};

export const ACROBAT_GREEN = "#00a651";

/** @deprecated use DEFAULTS.tick.points100 */
export const TICK_RIBBON_100 = DEFAULTS.tick.points100;

export const DEFAULT_TICK_POINTS_100 = DEFAULTS.tick.points100;

/** Polygon walk: stem → inner bridge → V outer → tail → V inner → close. */
export const TICK_POLYGON_FROM_SEMANTIC = [0, 1, 6, 2, 4, 5, 3];

export const TICK_POINT_LABELS = [
  "Point 1 — stem outer",
  "Point 2 — stem inner",
  "Point 3 — V outer",
  "Point 4 — V inner",
  "Point 5 — tail outer",
  "Point 6 — tail inner",
  "Point 7 — inner bridge",
];

/** Legacy v3 polygon-order (7 verts) → semantic control points. */
export function polygonOrderToSemantic(poly) {
  if (!poly || poly.length < 7) return DEFAULT_TICK_POINTS_100.map((p) => [...p]);
  return [
    [...poly[0]],
    [...poly[1]],
    [...poly[3]],
    [...poly[6]],
    [...poly[4]],
    [...poly[5]],
    [...poly[2]],
  ];
}

export function semanticToPolygonOrder(semantic) {
  return TICK_POLYGON_FROM_SEMANTIC.map((i) => [...semantic[i]]);
}

export function normalizeTickPoints100(points, version = 4) {
  if (!points || points.length < 6) {
    return DEFAULT_TICK_POINTS_100.map((p) => [...p]);
  }
  let pts = points.map((p) => [...p]);
  if (version < 4) {
    pts = polygonOrderToSemantic(pts);
  }
  while (pts.length < 7) {
    pts.push([...DEFAULT_TICK_POINTS_100[pts.length]]);
  }
  return pts.slice(0, 7);
}

export function bodyYs(yOffset = 0, lineHeight = DEFAULTS.n2.lineHeight, lineCount = DEFAULTS.n2.lines.length) {
  const topY = DEFAULTS.n2.ys[0] + yOffset;
  return Array.from({ length: lineCount }, (_, i) => topY - i * lineHeight);
}

/** Ribbon polygon in 100×100 icon space (before inner map). */
export function getTickPoints100(tick = {}) {
  const t = { ...DEFAULTS.tick, ...tick };
  const semantic = normalizeTickPoints100(t.points100, t.pointsVersion ?? 4);
  return semanticToPolygonOrder(semantic);
}

/** @deprecated alias */
export function buildTickRibbon100(tick = {}) {
  return getTickPoints100(tick);
}

export function buildTickInnerPoints(tick = {}) {
  const t = { ...DEFAULTS.tick, ...tick };
  return getTickPoints100(t).map(([x, y]) => [
    x * t.mapScale + t.mapOx,
    y * t.mapScale + t.mapOy,
  ]);
}

/** Adobe DSUnknown — exact UIDAI n1 stream */
export const DS_UNKNOWN = `q
1 G
1 g
0.1 0 0 0.1 9 0 cm
0 J 0 j 4 M []0 d
1 i
0 g
313 292 m
313 404 325 453 432 529 c
478 561 504 597 504 645 c
504 736 440 760 391 760 c
286 760 271 681 265 626 c
265 625 l
100 625 l
100 828 253 898 381 898 c
451 898 679 878 679 650 c
679 555 628 499 538 435 c
488 399 467 376 467 292 c
313 292 l
h
308 214 170 -164 re
f
0.44 G
1.2 w
1 1 0.4 rg
287 318 m
287 430 299 479 406 555 c
451 587 478 623 478 671 c
478 762 414 786 365 786 c
260 786 245 707 239 652 c
239 651 l
74 651 l
74 854 227 924 355 924 c
425 924 653 904 653 676 c
653 581 602 525 512 461 c
462 425 441 402 441 318 c
287 318 l
h
282 240 170 -164 re
B
Q`;

function hexToRgb(hex) {
  return {
    r: parseInt(hex.slice(1, 3), 16) / 255,
    g: parseInt(hex.slice(3, 5), 16) / 255,
    b: parseInt(hex.slice(5, 7), 16) / 255,
  };
}

function polyPath(pts, dx = 0, dy = 0, close = true) {
  const [x0, y0] = pts[0];
  let s = `${x0 + dx} ${y0 + dy} m\n`;
  for (let i = 1; i < pts.length; i++) {
    s += `${pts[i][0] + dx} ${pts[i][1] + dy} l\n`;
  }
  return close ? `${s}h\n` : s;
}

/** DSValid — filled ribbon + hard shadow + optional perimeter stroke. */
export function buildValidStream(tick = {}) {
  const t = { ...DEFAULTS.tick, ...tick };
  const pts = buildTickInnerPoints(t);
  const fill = hexToRgb(t.fillColor || ACROBAT_GREEN);
  const shadow = hexToRgb(t.shadowColor || "#000000");
  const shadowPath = polyPath(pts, t.shadowDx ?? 0, t.shadowDy ?? 0);
  const mainPath = polyPath(pts);
  const borderW = t.borderWidth ?? 0;
  let borderBlock = "";
  if (borderW > 0) {
    const border = hexToRgb(t.borderColor || "#000000");
    borderBlock = `${border.r.toFixed(3)} ${border.g.toFixed(3)} ${border.b.toFixed(3)} RG
${borderW} w
${mainPath}S
`;
  }
  return `q
1 G
1 g
0.1 0 0 0.1 9 0 cm
${shadow.r.toFixed(3)} ${shadow.g.toFixed(3)} ${shadow.b.toFixed(3)} rg
${shadowPath}f
${fill.r.toFixed(3)} ${fill.g.toFixed(3)} ${fill.b.toFixed(3)} rg
${mainPath}f
${borderBlock}Q`;
}

export function pdfToCanvasY(y, scale) {
  return (FORM_H - y) * scale;
}

function tokenize(stream) {
  return stream
    .replace(/%[^\n]*/g, "")
    .replace(/\n/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

function isNumberToken(t) {
  return /^-?(\d+\.?\d*|\d*\.\d+)$/.test(t);
}

export function execPdfStream(ctx, stream) {
  const tokens = tokenize(stream);
  const stack = [];
  let path = [];
  let i = 0;

  const pop = (n = 1) => {
    const v = stack.splice(-n);
    return n === 1 ? v[0] : v;
  };
  const push = (...v) => stack.push(...v);

  const flush = (op) => {
    if (!path.length) return;
    ctx.beginPath();
    for (const seg of path) {
      if (seg.t === "m") ctx.moveTo(seg.x, seg.y);
      else if (seg.t === "l") ctx.lineTo(seg.x, seg.y);
      else if (seg.t === "c")
        ctx.bezierCurveTo(seg.x1, seg.y1, seg.x2, seg.y2, seg.x3, seg.y3);
      else if (seg.t === "re") ctx.rect(seg.x, seg.y + seg.h, seg.w, -seg.h);
    }
    if (op === "f" || op === "F" || op === "B") ctx.fill();
    if (op === "S" || op === "B") ctx.stroke();
    path = [];
  };

  while (i < tokens.length) {
    const t = tokens[i++];
    if (isNumberToken(t)) {
      push(parseFloat(t));
      continue;
    }
    if (t === "[]0") {
      push(0);
      continue;
    }

    if (t === "m") {
      const y = pop();
      const x = pop();
      path.push({ t: "m", x, y });
    } else if (t === "l") {
      const y = pop();
      const x = pop();
      path.push({ t: "l", x, y });
    } else if (t === "c") {
      const y3 = pop();
      const x3 = pop();
      const y2 = pop();
      const x2 = pop();
      const y1 = pop();
      const x1 = pop();
      path.push({ t: "c", x1, y1, x2, y2, x3, y3 });
    } else if (t === "re") {
      const h = pop();
      const w = pop();
      const y = pop();
      const x = pop();
      path.push({ t: "re", x, y, w, h });
    } else if (t === "h") {
      const m = path.find((p) => p.t === "m");
      if (m) path.push({ t: "l", x: m.x, y: m.y });
    } else if (t === "f" || t === "F" || t === "S" || t === "B") {
      flush(t);
    } else if (t === "rg") {
      const b = pop();
      const g = pop();
      const r = pop();
      ctx.fillStyle = `rgb(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)})`;
      ctx.strokeStyle = ctx.fillStyle;
    } else if (t === "g") {
      const v = pop();
      const c = Math.round(v * 255);
      ctx.fillStyle = `rgb(${c},${c},${c})`;
    } else if (t === "G") {
      const v = pop();
      const c = Math.round(v * 255);
      ctx.strokeStyle = `rgb(${c},${c},${c})`;
    } else if (t === "RG") {
      const b = pop();
      const g = pop();
      const r = pop();
      ctx.strokeStyle = `rgb(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)})`;
    } else if (t === "w") ctx.lineWidth = pop();
    else if (t === "cm") {
      const f = pop();
      const e = pop();
      const d = pop();
      const c = pop();
      const b = pop();
      const a = pop();
      ctx.transform(a, b, c, d, e, f);
    } else if (t === "q") ctx.save();
    else if (t === "Q") ctx.restore();
    else if (t === "J" || t === "j" || t === "M" || t === "i") pop();
    else if (t === "d") {
      pop();
      pop();
    }
  }
}

export function drawN1Icon(ctx, scale, stream, n1, flipIconY = false) {
  const { tx, ty, scale: s } = n1;
  ctx.save();
  ctx.translate(tx * scale, pdfToCanvasY(ty, scale));
  ctx.scale(s * scale, -s * scale);
  if (flipIconY) ctx.transform(1, 0, 0, -1, 0, 100);
  execPdfStream(ctx, stream);
  ctx.restore();
}

export function drawStamp(ctx, scale, valid = true, opts = {}) {
  const n4 = { ...DEFAULTS.n4, ...(opts.n4 || {}) };
  const n2 = { ...DEFAULTS.n2, ...(opts.n2 || {}) };
  const n1 = { ...DEFAULTS.n1, ...(opts.n1 || {}) };
  const tick = { ...DEFAULTS.tick, ...(opts.tick || {}) };

  ctx.save();
  if (opts.originX != null || opts.originY != null) {
    ctx.translate(opts.originX ?? 0, opts.originY ?? 0);
  }
  if (!opts.skipBackground) {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, FORM_W * scale, FORM_H * scale);
  }

  const iconStream = valid
    ? opts.dsValid || buildValidStream(tick)
    : opts.dsUnknown || DS_UNKNOWN;
  const flipY = valid ? n1.flipY !== false : false;
  drawN1Icon(ctx, scale, iconStream, n1, flipY);

  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = opts.textColor || "#000000";

  const title = valid ? n4.textValid : n4.textInvalid;
  const n4w = n4.fontWeight ?? 400;
  ctx.font = `${n4w} ${n4.fontSize * scale}px Helvetica, Arial, sans-serif`;
  ctx.fillText(title, n4.x * scale, pdfToCanvasY(n4.y, scale));

  const n2w = n2.fontWeight ?? 400;
  ctx.font = `${n2w} ${n2.fontSize * scale}px Helvetica, Arial, sans-serif`;
  const lines = n2.lines || DEFAULTS.n2.lines;
  const lineHeight = n2.lineHeight ?? DEFAULTS.n2.lineHeight;
  const ys = n2.ys || bodyYs(n2.yOffset ?? 0, lineHeight, lines.length);
  lines.forEach((line, idx) => {
    const y = ys[idx] != null ? ys[idx] : ys[ys.length - 1];
    ctx.fillText(line, n2.x * scale, pdfToCanvasY(y, scale));
  });
  ctx.restore();
}

/** Build exportable config object from lab values. */
export function packConfig(values) {
  const yOffset = values.n2yOffset ?? 0;
  const lineHeight = values.n2LineHeight ?? DEFAULTS.n2.lineHeight;
  const points100 = values.tickPoints
    ?? DEFAULT_TICK_POINTS_100.map((p, i) => [
      values[`tickP${i}x`],
      values[`tickP${i}y`],
    ]);
  return {
    version: 4,
    globalScale: values.globalScale ?? 1,
    stampOffsetX: values.stampOffsetX ?? 0,
    stampOffsetY: values.stampOffsetY ?? 0,
    form: { width: FORM_W, height: FORM_H },
    n4: {
      x: values.n4x,
      y: values.n4y,
      fontSize: values.n4Size,
      fontWeight: values.n4Weight,
      textValid: DEFAULTS.n4.textValid,
      textInvalid: DEFAULTS.n4.textInvalid,
    },
    n2: {
      x: values.n2x,
      fontSize: values.n2Size,
      fontWeight: values.n2Weight,
      lineHeight,
      yOffset,
      ys: bodyYs(yOffset, lineHeight),
      lines: DEFAULTS.n2.lines,
    },
    n1: {
      tx: values.n1tx,
      ty: values.n1ty,
      scale: values.n1scale,
      flipY: values.n1flipY,
    },
    tick: {
      points100,
      mapScale: values.tickMapScale,
      mapOx: values.tickMapOx,
      mapOy: values.tickMapOy,
      shadowDx: values.shadowDx,
      shadowDy: values.shadowDy,
      shadowColor: values.shadowColor,
      fillColor: values.tickColor,
      borderWidth: values.tickBorderWidth,
      borderColor: values.tickBorderColor,
    },
    previewScale: values.scale,
  };
}

export function unpackConfig(cfg) {
  const c = cfg || {};
  const n2 = { ...DEFAULTS.n2, ...c.n2 };
  const lineHeight = n2.lineHeight ?? DEFAULTS.n2.lineHeight;
  if (c.n2?.yOffset != null) {
    n2.yOffset = c.n2.yOffset;
  } else if (c.n2?.ys?.length) {
    n2.yOffset = c.n2.ys[0] - DEFAULTS.n2.ys[0];
  } else {
    n2.yOffset = 0;
  }
  n2.lineHeight = lineHeight;
  n2.ys = bodyYs(n2.yOffset, lineHeight);
  const tick = { ...DEFAULTS.tick, ...c.tick };
  tick.points100 = normalizeTickPoints100(c.tick?.points100, c.version ?? 4);
  return {
    n4: { ...DEFAULTS.n4, ...c.n4 },
    n2,
    n1: { ...DEFAULTS.n1, ...c.n1 },
    tick,
    globalScale: c.globalScale ?? 1,
    stampOffsetX: c.stampOffsetX ?? 0,
    stampOffsetY: c.stampOffsetY ?? 0,
    scale: c.previewScale ?? 16,
  };
}
