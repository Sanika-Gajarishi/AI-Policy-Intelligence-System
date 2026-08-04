// generate_pptx.js
// Usage: node generate_pptx.js <input_json_path> <output_pptx_path>
//
// Renders the DYNAMIC deck JSON: { title, narrative_label, theme, slides[] }
// where "theme" (fonts/colors) and "slides" (which layouts, how many, in
// what order, and all text/data) are chosen per-document by Claude.
// This file only knows how to DRAW a fixed set of layout primitives — it no
// longer hardcodes any document-type -> template mapping.

"use strict";
const pptxgen = require("pptxgenjs");
const fs = require("fs");

// ── THEME ────────────────────────────────────────────────────────────────
const DEFAULT_THEME = {
  style_name: "Modern Energy",
  title_font: "Cambria",
  body_font: "Calibri",
  primary_color: "0891B2",
  secondary_color: "0F172A",
  accent_color: "F59E0B",
  text_color: "E2E8F0",
  muted_color: "94A3B8",
};

function resolveTheme(themeInput) {
  const t = { ...DEFAULT_THEME, ...(themeInput || {}) };
  // normalize any leading '#'
  for (const k of ["primary_color", "secondary_color", "accent_color", "text_color", "muted_color"]) {
    t[k] = String(t[k] || DEFAULT_THEME[k]).replace(/^#/, "");
  }
  return t;
}

function hex(c) { return String(c).replace(/^#/, ""); }
function shadow() { return { type: "outer", color: "000000", blur: 8, offset: 3, angle: 45, opacity: 0.18 }; }

function truncate(text, max) {
  if (!text) return "";
  const s = String(text);
  return s.length <= max ? s : s.slice(0, max - 3).trimEnd() + "...";
}

// A slightly lighter/darker variant of the secondary color, used for card
// backgrounds so cards read as distinct from the slide background.
function cardBgFor(theme) {
  return theme.secondary_color; // pptxgenjs doesn't do color math easily;
  // rely on transparency instead, see addShape calls below.
}

// ── LAYOUT BUILDERS ─────────────────────────────────────────────────────────

function addCover(prs, s, theme) {
  const slide = prs.addSlide();
  slide.background = { color: hex(theme.secondary_color) };

  slide.addShape(prs.shapes.OVAL, {
    x: 7.5, y: -1.2, w: 4, h: 4,
    fill: { color: hex(theme.primary_color), transparency: 80 },
    line: { type: "none" },
  });
  slide.addShape(prs.shapes.OVAL, {
    x: -1, y: 3.5, w: 3, h: 3,
    fill: { color: hex(theme.accent_color), transparency: 85 },
    line: { type: "none" },
  });

  if (s.eyebrow) {
    slide.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x: 0.5, y: 0.4, w: 3.2, h: 0.38,
      fill: { color: hex(theme.accent_color) },
      rectRadius: 0.08, line: { type: "none" },
    });
    slide.addText(String(s.eyebrow).toUpperCase(), {
      x: 0.5, y: 0.4, w: 3.2, h: 0.38, fontSize: 8, bold: true, color: "1A1A1A",
      align: "center", valign: "middle", fontFace: theme.body_font, margin: 0,
    });
  }

  slide.addText(truncate(s.title || "", 70), {
    x: 0.5, y: 1.0, w: 8.7, h: 1.8, fontSize: 34, bold: true, color: "FFFFFF",
    fontFace: theme.title_font, align: "left", valign: "top",
  });

  if (s.subtitle) {
    slide.addText(truncate(s.subtitle, 130), {
      x: 0.5, y: 2.85, w: 8, h: 0.6, fontSize: 14, color: hex(theme.muted_color),
      fontFace: theme.body_font,
    });
  }

  slide.addShape(prs.shapes.RECTANGLE, {
    x: 0.5, y: 3.5, w: 3, h: 0.04,
    fill: { color: hex(theme.accent_color) }, line: { type: "none" },
  });

  const stats = (s.stats || []).slice(0, 4);
  if (stats.length) {
    const w = 9 / stats.length;
    stats.forEach((stat, i) => {
      const x = 0.5 + i * w;
      slide.addShape(prs.shapes.ROUNDED_RECTANGLE, {
        x, y: 3.8, w: w - 0.15, h: 1.4,
        fill: { color: "FFFFFF", transparency: 90 }, line: { color: "FFFFFF", transparency: 85, width: 1 },
        rectRadius: 0.1, shadow: shadow(),
      });
      slide.addText(truncate(String(stat.value || ""), 14), {
        x: x + 0.1, y: 3.85, w: w - 0.35, h: 0.7, fontSize: 20, bold: true,
        color: hex(theme.accent_color), fontFace: theme.title_font, align: "center", valign: "middle", margin: 0,
      });
      slide.addText(truncate(String(stat.label || ""), 34), {
        x: x + 0.1, y: 4.55, w: w - 0.35, h: 0.5, fontSize: 9,
        color: hex(theme.muted_color), fontFace: theme.body_font, align: "center", margin: 0,
      });
    });
  }
}

function addHeader(slide, s, theme) {
  if (s.eyebrow) {
    slide.addText(String(s.eyebrow).toUpperCase(), {
      x: 0.5, y: 0.2, w: 9, h: 0.28, fontSize: 9, color: hex(theme.accent_color),
      bold: true, charSpacing: 3, fontFace: theme.body_font, margin: 0,
    });
  }
  slide.addText(truncate(s.title || "", 65), {
    x: 0.5, y: s.eyebrow ? 0.48 : 0.3, w: 9, h: 0.65, fontSize: 25, bold: true,
    color: "FFFFFF", fontFace: theme.title_font,
  });
  if (s.subtitle) {
    slide.addText(truncate(s.subtitle, 160), {
      x: 0.5, y: s.eyebrow ? 1.12 : 0.95, w: 9, h: 0.5, fontSize: 11.5,
      color: hex(theme.muted_color), fontFace: theme.body_font, italic: true,
    });
  }
}

function addStatGrid(prs, s, theme) {
  const slide = prs.addSlide();
  slide.background = { color: hex(theme.secondary_color) };
  addHeader(slide, s, theme);

  const stats = (s.stats || []).slice(0, 6);
  const cols = stats.length > 4 ? 3 : 2;
  const rows = Math.ceil(stats.length / cols);
  const cardW = 9 / cols;
  const startY = 1.5;
  const cardH = Math.min((5.2 - startY) / rows, 1.5);

  stats.forEach((stat, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x = 0.5 + col * cardW, y = startY + row * cardH;
    slide.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x, y, w: cardW - 0.15, h: cardH - 0.15,
      fill: { color: hex(theme.primary_color), transparency: 82 },
      line: { color: hex(theme.primary_color), transparency: 50, width: 1 },
      rectRadius: 0.12, shadow: shadow(),
    });
    slide.addText(truncate(String(stat.value || ""), 14), {
      x: x + 0.1, y: y + 0.1, w: cardW - 0.35, h: 0.65, fontSize: 20, bold: true,
      color: hex(theme.accent_color), fontFace: theme.title_font, align: "center", valign: "middle", margin: 0,
    });
    slide.addText(truncate(String(stat.label || ""), 40), {
      x: x + 0.1, y: y + cardH - 0.6, w: cardW - 0.35, h: 0.5, fontSize: 9.5,
      color: hex(theme.text_color), fontFace: theme.body_font, align: "center", margin: 0,
    });
  });
}

// Native pptxgenjs charts — this is the actual bar/pie/donut/line support.
function addChartSlide(prs, s, theme) {
  const slide = prs.addSlide();
  slide.background = { color: hex(theme.secondary_color) };
  addHeader(slide, s, theme);

  const categories = s.categories || [];
  const values = (s.values || []).map(v => Number(v) || 0);
  const seriesName = s.series_name || s.title || "Value";
  const hasCallouts = (s.callouts || []).length > 0;
  const chartW = hasCallouts ? 5.6 : 8.6;

  const typeMap = {
    bar: prs.charts.BAR,
    pie: prs.charts.PIE,
    doughnut: prs.charts.DOUGHNUT,
    line: prs.charts.LINE,
    area: prs.charts.AREA,
  };
  const chartType = typeMap[(s.chart_type || "bar").toLowerCase()] || prs.charts.BAR;

  const chartData = [{ name: seriesName, labels: categories, values }];

  const colorList = [theme.primary_color, theme.accent_color, "60A5FA", "A78BFA", "34D399", "F472B6", "FBBF24"];

  const chartOpts = {
    x: 0.5, y: 1.4, w: chartW, h: 3.6,
    chartColors: colorList.map(hex),
    showLegend: chartType === prs.charts.PIE || chartType === prs.charts.DOUGHNUT,
    legendPos: "r",
    showValue: true,
    dataLabelColor: chartType === prs.charts.PIE || chartType === prs.charts.DOUGHNUT ? "FFFFFF" : hex(theme.text_color),
    dataLabelFontSize: 10,
    catAxisLabelColor: hex(theme.muted_color),
    valAxisLabelColor: hex(theme.muted_color),
    catAxisLineColor: hex(theme.muted_color),
    valAxisLineColor: hex(theme.muted_color),
    titleColor: hex(theme.text_color),
    barFillColor: hex(theme.primary_color),
    lineDataSymbol: "circle",
    chartArea: { fill: { type: "none" } },
    plotArea: { fill: { type: "none" } },
  };

  slide.addChart(chartType, chartData, chartOpts);

  if (hasCallouts) {
    const callouts = s.callouts.slice(0, 3);
    const ch = 3.6 / callouts.length;
    callouts.forEach((c, i) => {
      const y = 1.4 + i * ch;
      slide.addShape(prs.shapes.ROUNDED_RECTANGLE, {
        x: 6.3, y: y + 0.05, w: 3.2, h: ch - 0.15,
        fill: { color: hex(theme.primary_color), transparency: 85 },
        line: { color: hex(theme.primary_color), transparency: 55, width: 1 },
        rectRadius: 0.08,
      });
      slide.addText(truncate(String(c.title || ""), 32), {
        x: 6.45, y: y + 0.12, w: 2.9, h: 0.35, fontSize: 10.5, bold: true,
        color: hex(theme.accent_color), fontFace: theme.title_font, margin: 0,
      });
      slide.addText(truncate(String(c.detail || ""), 130), {
        x: 6.45, y: y + 0.45, w: 2.9, h: ch - 0.55, fontSize: 9,
        color: hex(theme.text_color), fontFace: theme.body_font,
      });
    });
  }
}

function addSplit(prs, s, theme) {
  const slide = prs.addSlide();
  slide.background = { color: hex(theme.secondary_color) };
  addHeader(slide, s, theme);

  const pairs = [
    [s.left_label, s.left_text, theme.primary_color],
    [s.right_label, s.right_text, theme.accent_color],
  ];
  pairs.forEach(([label, text, borderColor], i) => {
    const x = 0.5 + i * 4.6;
    slide.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x, y: 1.5, w: 4.4, h: 3.4,
      fill: { color: hex(theme.primary_color), transparency: 88 },
      line: { color: hex(borderColor), width: 1.5 },
      rectRadius: 0.1, shadow: shadow(),
    });
    slide.addText(String(label || "").toUpperCase(), {
      x: x + 0.2, y: 1.65, w: 4, h: 0.3, fontSize: 9, bold: true,
      color: hex(theme.accent_color), charSpacing: 2, fontFace: theme.body_font, margin: 0,
    });
    slide.addText(truncate(text || "", 420), {
      x: x + 0.2, y: 2.0, w: 4, h: 2.75, fontSize: 12,
      color: hex(theme.text_color), fontFace: theme.body_font,
    });
  });
}

function addCards(prs, s, theme) {
  const slide = prs.addSlide();
  slide.background = { color: hex(theme.secondary_color) };
  addHeader(slide, s, theme);

  const items = (s.items || []).slice(0, 9);
  const cols = items.length > 6 ? 3 : items.length > 2 ? 3 : 2;
  const rows = Math.ceil(items.length / cols);
  const cardW = 9 / cols;
  const startY = s.subtitle ? 1.7 : 1.4;
  const cardH = Math.min((5.3 - startY) / rows, 1.5);

  items.forEach((item, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x = 0.5 + col * cardW, y = startY + row * cardH;
    slide.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x, y, w: cardW - 0.14, h: cardH - 0.12,
      fill: { color: hex(theme.primary_color), transparency: 85 },
      line: { color: hex(theme.primary_color), transparency: 45, width: 1.2 },
      rectRadius: 0.1, shadow: shadow(),
    });
    const icon = item.icon || "\u25C6";
    slide.addText(icon, {
      x: x + 0.12, y: y + 0.08, w: 0.5, h: 0.35, fontSize: 16,
      color: hex(theme.accent_color), align: "center", margin: 0,
    });
    slide.addText(truncate(item.title || "", 32), {
      x: x + 0.6, y: y + 0.08, w: cardW - 0.85, h: 0.35, fontSize: 11, bold: true,
      color: "FFFFFF", fontFace: theme.title_font, margin: 0,
    });
    if (item.detail) {
      slide.addText(truncate(item.detail, 180), {
        x: x + 0.12, y: y + 0.42, w: cardW - 0.35, h: cardH - 0.5, fontSize: 9.5,
        color: hex(theme.text_color), fontFace: theme.body_font,
      });
    }
  });
}

function addList(prs, s, theme) {
  const slide = prs.addSlide();
  slide.background = { color: hex(theme.secondary_color) };
  addHeader(slide, s, theme);

  const bullets = (s.bullets || []).slice(0, 8);
  if (bullets.length) {
    const items = bullets.map((b, i) => ({
      text: truncate(String(b), 220),
      options: { bullet: { code: "2022" }, breakLine: i < bullets.length - 1, paraSpaceAfter: 10, fontSize: 12, color: hex(theme.text_color) },
    }));
    slide.addText(items, { x: 0.5, y: s.subtitle ? 1.9 : 1.4, w: 9, h: 3.6, fontFace: theme.body_font });
  }
}

function addTimeline(prs, s, theme) {
  const slide = prs.addSlide();
  slide.background = { color: hex(theme.secondary_color) };
  addHeader(slide, s, theme);

  const events = (s.events || []).slice(0, 6);
  if (events.length) {
    const lineY = 2.55, x0 = 1.0, x1 = 9.0;
    slide.addShape(prs.shapes.RECTANGLE, {
      x: x0, y: lineY, w: x1 - x0, h: 0.035,
      fill: { color: hex(theme.primary_color), transparency: 30 }, line: { type: "none" },
    });
    const spacing = (x1 - x0) / (events.length - 1 || 1);
    const slotW = Math.min(spacing - 0.1, 1.7);

    events.forEach((ev, i) => {
      const ex = x0 + i * spacing;
      const above = i % 2 === 0;
      const labelX = Math.max(0.15, Math.min(ex - slotW / 2, 10 - slotW - 0.15));
      slide.addShape(prs.shapes.OVAL, {
        x: ex - 0.1, y: lineY - 0.085, w: 0.2, h: 0.2,
        fill: { color: hex(theme.accent_color) }, line: { type: "none" }, shadow: shadow(),
      });
      const dateBox = { x: labelX, y: above ? lineY - 0.6 : lineY + 0.26, w: slotW, h: 0.3 };
      const labelBox = { x: labelX, y: above ? lineY + 0.18 : lineY - 1.02, w: slotW, h: 0.85 };
      slide.addText(truncate(String(ev.date || ""), 12), {
        ...dateBox, fontSize: 12, bold: true, color: hex(theme.accent_color),
        fontFace: theme.title_font, align: "center", margin: 0,
      });
      slide.addText(truncate(String(ev.label || ""), 55), {
        ...labelBox, fontSize: 9, color: hex(theme.text_color), fontFace: theme.body_font, align: "center",
      });
    });
  }

  const highlights = (s.highlights || []).slice(0, 3);
  if (highlights.length) {
    const w = 9 / highlights.length;
    highlights.forEach((h, i) => {
      const x = 0.5 + i * w;
      slide.addShape(prs.shapes.ROUNDED_RECTANGLE, {
        x, y: 3.75, w: w - 0.15, h: 1.55,
        fill: { color: hex(theme.primary_color), transparency: 85 },
        line: { color: hex(theme.primary_color), transparency: 50, width: 1 },
        rectRadius: 0.1, shadow: shadow(),
      });
      slide.addText(truncate(String(h.title || ""), 30), {
        x: x + 0.15, y: 3.85, w: w - 0.4, h: 0.38, fontSize: 11, bold: true,
        color: hex(theme.accent_color), fontFace: theme.title_font, margin: 0,
      });
      slide.addText(truncate(String(h.detail || ""), 120), {
        x: x + 0.15, y: 4.25, w: w - 0.35, h: 0.95, fontSize: 9.5,
        color: hex(theme.text_color), fontFace: theme.body_font,
      });
    });
  }
}

function addClosing(prs, s, theme) {
  const slide = prs.addSlide();
  slide.background = { color: hex(theme.secondary_color) };

  slide.addShape(prs.shapes.OVAL, {
    x: 7.5, y: -1, w: 4.5, h: 4.5,
    fill: { color: hex(theme.primary_color), transparency: 82 }, line: { type: "none" },
  });

  slide.addText(truncate(s.title || "Key Takeaways", 55), {
    x: 0.5, y: 0.5, w: 9, h: 0.75, fontSize: 28, bold: true, color: "FFFFFF", fontFace: theme.title_font,
  });
  slide.addShape(prs.shapes.RECTANGLE, {
    x: 0.5, y: 1.3, w: 2.5, h: 0.04, fill: { color: hex(theme.accent_color) }, line: { type: "none" },
  });

  const takeaways = (s.takeaways || []).slice(0, 7);
  if (takeaways.length) {
    const items = takeaways.map((t, i) => ({
      text: truncate(String(t), 180),
      options: { bullet: { code: "25B6" }, breakLine: i < takeaways.length - 1, paraSpaceAfter: 12, fontSize: 13, color: hex(theme.text_color) },
    }));
    slide.addText(items, { x: 0.5, y: 1.5, w: 9, h: 3.6, fontFace: theme.body_font });
  }

  if (s.footer) {
    slide.addText(truncate(s.footer, 90), {
      x: 0.5, y: 5.25, w: 9, h: 0.28, fontSize: 8.5, color: hex(theme.muted_color),
      fontFace: theme.body_font, align: "center", italic: true, margin: 0,
    });
  }
}

// ── DISPATCH ────────────────────────────────────────────────────────────────
function addSlide(prs, s, theme) {
  switch ((s.layout || "list").toLowerCase()) {
    case "cover": return addCover(prs, s, theme);
    case "stat_grid": return addStatGrid(prs, s, theme);
    case "chart": return addChartSlide(prs, s, theme);
    case "split": return addSplit(prs, s, theme);
    case "cards": return addCards(prs, s, theme);
    case "timeline": return addTimeline(prs, s, theme);
    case "closing": return addClosing(prs, s, theme);
    case "list":
    default: return addList(prs, s, theme);
  }
}

// ── MAIN ────────────────────────────────────────────────────────────────────
async function main() {
  const [, , inputPath, outputPath] = process.argv;
  if (!inputPath || !outputPath) {
    console.error("Usage: node generate_pptx.js <input.json> <output.pptx>");
    process.exit(1);
  }

  const data = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  const theme = resolveTheme(data.theme);

  const prs = new pptxgen();
  prs.layout = "LAYOUT_16x9";
  prs.title = data.title || "Policy Presentation";

  for (const s of data.slides || []) {
    addSlide(prs, s, theme);
  }

  await prs.writeFile({ fileName: outputPath });
  console.log("DONE:" + outputPath);
}

main().catch(err => {
  console.error("ERROR:", err.message);
  process.exit(1);
});