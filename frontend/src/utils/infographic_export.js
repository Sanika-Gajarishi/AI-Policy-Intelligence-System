// infographic_export.js
// Converts the DYNAMIC infographic JSON { title, narrative_label, theme, sections[] }
// into a self-contained downloadable HTML file. Mirrors the section types and
// chart rendering in PolicyInfographic.jsx exactly, just as HTML strings
// instead of React — so the downloaded file looks the same as what's shown
// in chat. Old fixed-shape data (data.header / data.color_scheme) still
// renders via the Legacy path below so nothing breaks mid-migration.

const DEFAULT_THEME = {
  style_name: "Modern Energy",
  title_font: "Merriweather, Georgia, serif",
  body_font: "Inter, sans-serif",
  primary_color: "2E7D32",
  secondary_color: "0F1F0F",
  accent_color: "F9A825",
  text_color: "E8F5E9",
  muted_color: "81C784",
};

function withHash(c) {
  if (!c) return "#000000";
  return String(c).startsWith("#") ? c : `#${c}`;
}

function resolveTheme(themeInput) {
  const t = { ...DEFAULT_THEME, ...(themeInput || {}) };
  return {
    titleFont: t.title_font,
    bodyFont: t.body_font,
    primary: withHash(t.primary_color),
    secondary: withHash(t.secondary_color),
    accent: withHash(t.accent_color),
    text: withHash(t.text_color),
    muted: withHash(t.muted_color),
  };
}

function esc(v) {
  if (v === null || v === undefined) return "";
  return String(v);
}

function truncate(text, max) {
  if (!text) return "";
  const s = String(text);
  return s.length <= max ? s : s.slice(0, max - 1).trimEnd() + "…";
}

// ── SVG CHART BUILDERS (same math as PolicyInfographic.jsx) ─────────────────

function svgBarChart(categories, values, theme, width = 760, height = 220) {
  const max = Math.max(...values, 1);
  const padL = 40, padB = 30, padT = 10;
  const chartW = width - padL - 20;
  const chartH = height - padB - padT;
  const barGap = 14;
  const barW = Math.max((chartW - barGap * (values.length - 1)) / values.length, 10);

  const bars = values.map((v, i) => {
    const h = (v / max) * chartH;
    const x = padL + i * (barW + barGap);
    const y = padT + chartH - h;
    const opacity = (0.55 + (i / values.length) * 0.4).toFixed(2);
    return `
      <rect x="${x}" y="${y}" width="${barW}" height="${h}" rx="4" fill="${theme.primary}" opacity="${opacity}" />
      <text x="${x + barW / 2}" y="${y - 6}" text-anchor="middle" font-size="12" font-weight="700" fill="${theme.accent}" font-family="${theme.bodyFont}">${esc(v)}</text>
      <text x="${x + barW / 2}" y="${padT + chartH + 18}" text-anchor="middle" font-size="10" fill="${theme.text}" font-family="${theme.bodyFont}">${esc(truncate(categories[i], 12))}</text>
    `;
  }).join("");

  return `<svg viewBox="0 0 ${width} ${height}" style="width:100%;height:auto">
    <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + chartH}" stroke="${theme.muted}" stroke-opacity="0.4" />
    <line x1="${padL}" y1="${padT + chartH}" x2="${width - 10}" y2="${padT + chartH}" stroke="${theme.muted}" stroke-opacity="0.4" />
    ${bars}
  </svg>`;
}

function svgLineAreaChart(categories, values, theme, filled, width = 760, height = 220) {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const padL = 40, padB = 30, padT = 20;
  const chartW = width - padL - 20;
  const chartH = height - padB - padT;
  const step = values.length > 1 ? chartW / (values.length - 1) : 0;

  const points = values.map((v, i) => {
    const x = padL + i * step;
    const y = padT + chartH - ((v - min) / (max - min || 1)) * chartH;
    return [x, y];
  });
  const linePath = points.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1][0]},${padT + chartH} L${points[0][0]},${padT + chartH} Z`;

  const dots = points.map(([x, y], i) => `
    <circle cx="${x}" cy="${y}" r="4" fill="${theme.accent}" />
    <text x="${x}" y="${y - 10}" text-anchor="middle" font-size="11" font-weight="700" fill="${theme.accent}" font-family="${theme.bodyFont}">${esc(values[i])}</text>
    <text x="${x}" y="${padT + chartH + 18}" text-anchor="middle" font-size="10" fill="${theme.text}" font-family="${theme.bodyFont}">${esc(truncate(categories[i], 12))}</text>
  `).join("");

  return `<svg viewBox="0 0 ${width} ${height}" style="width:100%;height:auto">
    <line x1="${padL}" y1="${padT + chartH}" x2="${width - 10}" y2="${padT + chartH}" stroke="${theme.muted}" stroke-opacity="0.4" />
    ${filled ? `<path d="${areaPath}" fill="${theme.primary}" opacity="0.25" />` : ""}
    <path d="${linePath}" fill="none" stroke="${theme.accent}" stroke-width="2.5" />
    ${dots}
  </svg>`;
}

function pieColors(theme) {
  return [theme.primary, theme.accent, "#60A5FA", "#A78BFA", "#34D399", "#F472B6", "#FBBF24"];
}

function svgPieChart(categories, values, theme, donut, size = 220) {
  const total = values.reduce((a, b) => a + b, 0) || 1;
  const r = size / 2 - 10;
  const cx = size / 2, cy = size / 2;
  const palette = pieColors(theme);

  let angle = -90;
  const slices = values.map((v, i) => {
    const frac = v / total;
    const startAngle = angle;
    const endAngle = angle + frac * 360;
    angle = endAngle;
    const toRad = (a) => (a * Math.PI) / 180;
    const x1 = cx + r * Math.cos(toRad(startAngle));
    const y1 = cy + r * Math.sin(toRad(startAngle));
    const x2 = cx + r * Math.cos(toRad(endAngle));
    const y2 = cy + r * Math.sin(toRad(endAngle));
    const largeArc = frac > 0.5 ? 1 : 0;
    const path = `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${largeArc} 1 ${x2},${y2} Z`;
    return `<path d="${path}" fill="${palette[i % palette.length]}" stroke="${theme.secondary}" stroke-width="1.5" />`;
  }).join("");

  const legend = categories.map((c, i) => `
    <div style="display:flex;align-items:center;gap:8px;font-size:11px;color:${theme.text};font-family:${theme.bodyFont}">
      <span style="width:10px;height:10px;border-radius:3px;background:${palette[i % palette.length]};flex-shrink:0"></span>
      <span>${esc(c)}: <strong style="color:${theme.accent}">${esc(values[i])}</strong></span>
    </div>`).join("");

  return `<div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">
    <svg viewBox="0 0 ${size} ${size}" style="width:${size}px;height:${size}px;flex-shrink:0">
      ${slices}
      ${donut ? `<circle cx="${cx}" cy="${cy}" r="${r * 0.55}" fill="${theme.secondary}" />` : ""}
    </svg>
    <div style="display:flex;flex-direction:column;gap:6px">${legend}</div>
  </div>`;
}

function renderChart(chartType, categories, values, theme) {
  const vals = (values || []).map((v) => Number(v) || 0);
  const cats = categories && categories.length ? categories : vals.map((_, i) => `#${i + 1}`);
  if (!vals.length) return "";
  switch ((chartType || "bar").toLowerCase()) {
    case "pie": return svgPieChart(cats, vals, theme, false);
    case "doughnut": return svgPieChart(cats, vals, theme, true);
    case "line": return svgLineAreaChart(cats, vals, theme, false);
    case "area": return svgLineAreaChart(cats, vals, theme, true);
    case "bar":
    default: return svgBarChart(cats, vals, theme);
  }
}

// ── SECTION RENDERERS (dynamic schema) ───────────────────────────────────────

function sectionHeading(eyebrow, title, theme) {
  return `
    ${eyebrow ? `<div style="font-size:9px;letter-spacing:2.5px;text-transform:uppercase;color:${theme.muted};font-weight:600;margin-bottom:5px;font-family:${theme.bodyFont}">${esc(eyebrow)}</div>` : ""}
    ${title ? `<h2 style="font-family:${theme.titleFont};font-size:20px;font-weight:700;color:#fff;margin-bottom:18px">${esc(title)}</h2>` : ""}
  `;
}

function renderHeaderStats(section, theme) {
  const stats = (section.stats || []).slice(0, 4);
  return `
  <div style="background:linear-gradient(135deg,${theme.primary}dd 0%,${theme.primary}99 50%,${theme.primary}dd 100%);
              padding:40px 36px 32px;position:relative;overflow:hidden;border-bottom:4px solid ${theme.accent}">
    <div style="position:absolute;top:-60px;right:-60px;width:240px;height:240px;border-radius:50%;background:rgba(255,255,255,0.05)"></div>
    ${section.eyebrow ? `<div style="font-size:10px;letter-spacing:2.5px;color:${theme.muted};text-transform:uppercase;margin-bottom:10px;font-family:${theme.bodyFont}">${esc(section.eyebrow)}</div>` : ""}
    <h1 style="font-family:${theme.titleFont};font-size:32px;font-weight:900;color:#fff;line-height:1.2;margin-bottom:10px">
      ${esc(section.title || "").replace(/\n/g, "<br>")}
    </h1>
    ${(section.reference_number || section.notified_date || section.valid_until) ? `
      <div style="font-size:10px;color:${theme.muted};margin-bottom:22px;font-family:${theme.bodyFont}">
        ${[section.reference_number, section.notified_date && `Notified: ${section.notified_date}`, section.valid_until && `Valid Till: ${section.valid_until}`].filter(Boolean).join("  ·  ")}
      </div>` : ""}
    ${stats.length ? `
      <div style="display:grid;grid-template-columns:repeat(${stats.length},1fr);gap:10px">
        ${stats.map(s => `
          <div style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.15);border-radius:10px;padding:12px 8px;text-align:center">
            <span style="font-family:${theme.titleFont};font-size:20px;font-weight:700;color:${theme.accent};display:block">${esc(s.value)}</span>
            <div style="font-size:9px;color:${theme.text};margin-top:3px;line-height:1.3;font-family:${theme.bodyFont}">${esc(s.label)}</div>
          </div>`).join("")}
      </div>` : ""}
  </div>`;
}

function renderStatGrid(section, theme) {
  const stats = section.stats || [];
  const cols = Math.min(stats.length, 4) || 1;
  return `
  <div style="padding:32px 36px;border-bottom:1px solid ${theme.primary}33">
    ${sectionHeading(section.eyebrow, section.title, theme)}
    <div style="display:grid;grid-template-columns:repeat(${cols},1fr);gap:12px">
      ${stats.map(s => `
        <div style="background:${theme.primary}22;border:1px solid ${theme.primary}55;border-radius:10px;padding:14px 10px;text-align:center">
          <div style="font-family:${theme.titleFont};font-size:18px;font-weight:700;color:${theme.accent}">${esc(s.value)}</div>
          <div style="font-size:9.5px;color:${theme.text};margin-top:4px;font-family:${theme.bodyFont}">${esc(s.label)}</div>
        </div>`).join("")}
    </div>
  </div>`;
}

function renderChartSection(section, theme) {
  if (!section.values || !section.values.length) return "";
  return `
  <div style="padding:32px 36px;border-bottom:1px solid ${theme.primary}33">
    ${sectionHeading(section.eyebrow, section.title, theme)}
    ${renderChart(section.chart_type, section.categories, section.values, theme)}
  </div>`;
}

function renderCards(section, theme) {
  const items = section.items || [];
  if (!items.length) return "";
  const cols = items.length > 6 ? 3 : items.length > 2 ? 3 : 2;
  return `
  <div style="padding:32px 36px;border-bottom:1px solid ${theme.primary}33">
    ${sectionHeading(section.eyebrow, section.title, theme)}
    <div style="display:grid;grid-template-columns:repeat(${cols},1fr);gap:12px">
      ${items.map(item => `
        <div style="border-radius:12px;padding:16px 14px;background:${theme.primary}18;border:1px solid ${theme.primary}55">
          ${item.icon ? `<div style="font-size:22px;margin-bottom:6px">${esc(item.icon)}</div>` : ""}
          <div style="font-size:13px;font-weight:700;color:#fff;margin-bottom:6px;font-family:${theme.titleFont}">${esc(item.title)}</div>
          ${item.detail ? `<div style="font-size:10.5px;color:${theme.text};line-height:1.5;font-family:${theme.bodyFont}">${esc(item.detail)}</div>` : ""}
        </div>`).join("")}
    </div>
  </div>`;
}

function renderColumns(section, theme) {
  const columns = section.columns || [];
  if (!columns.length) return "";
  return `
  <div style="padding:32px 36px;border-bottom:1px solid ${theme.primary}33">
    ${sectionHeading(section.eyebrow, section.title, theme)}
    <div style="display:grid;grid-template-columns:repeat(${columns.length},1fr);gap:14px">
      ${columns.map(col => `
        <div style="border-radius:12px;padding:14px;background:${theme.primary}18;border:1px solid ${theme.primary}44">
          <h4 style="font-size:12px;font-weight:700;margin-bottom:10px;color:${theme.accent};font-family:${theme.titleFont}">${esc(col.title)}</h4>
          <ul style="list-style:none;padding:0;margin:0">
            ${(col.items || []).map(it => `
              <li style="font-size:10.5px;color:${theme.text};padding:3px 0 3px 14px;position:relative;line-height:1.4;font-family:${theme.bodyFont}">
                <span style="position:absolute;left:0;color:${theme.accent};font-size:10px">▸</span>${esc(it)}
              </li>`).join("")}
          </ul>
        </div>`).join("")}
    </div>
  </div>`;
}

function renderTimeline(section, theme) {
  const events = section.events || [];
  if (!events.length) return "";
  return `
  <div style="padding:32px 36px;border-bottom:1px solid ${theme.primary}33">
    ${sectionHeading(section.eyebrow, section.title, theme)}
    <div style="border-left:3px solid ${theme.primary};padding-left:16px">
      ${events.map(ev => `
        <div style="margin-bottom:14px">
          <span style="color:${theme.accent};font-weight:700;font-family:${theme.titleFont};font-size:12px">${esc(ev.date)}</span>
          <span style="color:${theme.text};margin-left:8px;font-size:11.5px;font-family:${theme.bodyFont}">${esc(ev.label)}</span>
        </div>`).join("")}
    </div>
  </div>`;
}

function renderGlance(section, theme) {
  const stats = section.stats || [];
  const cols = Math.min(stats.length, 3) || 1;
  return `
  <div style="padding:28px 36px;background:rgba(0,0,0,0.15)">
    ${section.title ? `<h2 style="font-family:${theme.titleFont};font-size:16px;font-weight:700;color:#fff;margin-bottom:14px">${esc(section.title)}</h2>` : ""}
    ${stats.length ? `
      <div style="display:grid;grid-template-columns:repeat(${cols},1fr);gap:14px;margin-bottom:12px">
        ${stats.map(s => `
          <div style="text-align:center">
            <div style="font-size:13px;font-weight:700;color:${theme.accent};font-family:${theme.titleFont}">${esc(s.value)}</div>
            <div style="font-size:9px;color:${theme.muted};margin-top:2px;font-family:${theme.bodyFont}">${esc(s.label)}</div>
          </div>`).join("")}
      </div>` : ""}
    ${section.footer ? `<div style="font-size:9px;color:${theme.muted};text-align:center;font-family:${theme.bodyFont}">${esc(section.footer)}</div>` : ""}
  </div>`;
}

function renderGenericSection(section, theme) {
  const items = section.items || [];
  const listHTML = items.length ? `
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px">
      ${items.map(item => {
        const text = item.text || item.detail || item.value || (typeof item === "string" ? item : JSON.stringify(item));
        const heading = item.title || item.label || item.icon || "";
        return `
        <div style="background:${theme.primary}18;border-radius:8px;padding:11px 13px;border:1px solid ${theme.primary}33">
          ${heading ? `<div style="font-size:11px;font-weight:700;color:${theme.accent};margin-bottom:4px;font-family:${theme.titleFont}">${esc(heading)}</div>` : ""}
          <p style="font-size:10.5px;color:${theme.text};line-height:1.4;font-family:${theme.bodyFont};margin:0">${esc(text)}</p>
        </div>`;
      }).join("")}
    </div>` : "";
  return `
  <div style="padding:32px 36px;border-bottom:1px solid ${theme.primary}33">
    ${section.title ? `<h2 style="font-family:${theme.titleFont};font-size:20px;font-weight:700;color:#fff;margin-bottom:18px">${esc(section.title)}</h2>` : ""}
    ${listHTML}
  </div>`;
}

function renderSection(section, theme) {
  switch ((section.type || "").toLowerCase()) {
    case "header_stats": return renderHeaderStats(section, theme);
    case "stat_grid": return renderStatGrid(section, theme);
    case "chart": return renderChartSection(section, theme);
    case "cards": return renderCards(section, theme);
    case "columns": return renderColumns(section, theme);
    case "timeline": return renderTimeline(section, theme);
    case "glance": return renderGlance(section, theme);
    default: return renderGenericSection(section, theme);
  }
}

// ── MAIN EXPORT ────────────────────────────────────────────────────────────

export function buildInfographicHTML(infData) {
  if (!infData) return null;

  const isLegacyFormat = !!(infData.header || infData.color_scheme);
  if (isLegacyFormat) {
    return buildLegacyInfographicHTML(infData);
  }

  const theme = resolveTheme(infData.theme);
  const sections = infData.sections || [];
  const headerSection = sections.find((s) => (s.type || "").toLowerCase() === "header_stats");

  const titleBlockHTML = !headerSection && infData.title
    ? `<div style="padding:28px 36px;background:${theme.primary}"><h1 style="font-family:${theme.titleFont};font-size:28px;color:#fff;margin:0">${esc(infData.title)}</h1></div>`
    : "";

  const sectionsHTML = sections.map((s) => renderSection(s, theme)).join("");

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${esc(infData.title) || "Policy Infographic"}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { background:${theme.secondary}; font-family:${theme.bodyFont}; }
    .infographic { max-width:900px; margin:0 auto; background:${theme.secondary};
                   border-radius:8px; overflow:hidden; box-shadow:0 8px 32px rgba(0,0,0,0.4); }
  </style>
</head>
<body>
  <div class="infographic">
    ${titleBlockHTML}
    ${sectionsHTML}
  </div>
</body>
</html>`;
}

// ── LEGACY EXPORT (old fixed data.header / data.sections[].type shape) ──────
function buildLegacyInfographicHTML(infData) {
  const colors = infData.color_scheme || {
    bg: "#0F1F0F", primary: "#2E7D32", accent: "#F9A825",
    text: "#E8F5E9", muted: "#81C784", card: "#1A3A1A",
  };
  const header = infData.header || {};
  const stats = (header.stats || []).slice(0, 4);

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${esc(header.title) || "Policy Infographic"}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { background:${colors.bg}; font-family:'Inter',sans-serif; }
    .infographic { max-width:900px; margin:0 auto; padding:32px; background:${colors.bg};
                   border-radius:8px; box-shadow:0 8px 32px rgba(0,0,0,0.4); }
  </style>
</head>
<body>
  <div class="infographic">
    <h1 style="font-family:Merriweather,serif;font-size:28px;color:${colors.accent};margin-bottom:14px;border-bottom:3px solid ${colors.accent};padding-bottom:8px">
      ${esc(header.title) || "Policy Infographic"}
    </h1>
    ${stats.length ? `
      <div style="display:grid;grid-template-columns:repeat(${stats.length},1fr);gap:10px;margin-top:16px">
        ${stats.map(s => `
          <div style="background:${colors.primary};color:#fff;padding:12px;border-radius:6px;text-align:center">
            <div style="font-size:18px;font-weight:700">${esc(s.value)}</div>
            <div style="font-size:10px;margin-top:4px">${esc(s.label)}</div>
          </div>`).join("")}
      </div>` : ""}
    <p style="margin-top:20px;font-size:12px;color:${colors.muted}">
      This infographic was generated with an older data format. Re-run "Export Infographic" for the latest dynamic layout with charts.
    </p>
  </div>
</body>
</html>`;
}