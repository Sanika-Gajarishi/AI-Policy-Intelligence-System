// PolicyInfographic.jsx
// Renders the rich adaptive infographic JSON produced by the new infographic prompt.
// Supports: policy, regulatory_order, roadmap, incentive_scheme, generic document types.

import React from "react";

// ── SECTION RENDERERS ────────────────────────────────────────────────────────

function Header({ data, colors }) {
  const { gov_label, title, year_badge, reference_number, notified_date, valid_until, stats } = data.header || {};

  return (
    <div
      style={{
        background: `linear-gradient(135deg, ${colors.primary}dd 0%, ${colors.primary}99 50%, ${colors.primary}dd 100%)`,
        padding: "40px 36px 32px",
        position: "relative",
        overflow: "hidden",
        borderBottom: `4px solid ${colors.accent}`,
      }}
    >
      {/* Decorative circles */}
      <div style={{ position: "absolute", top: -60, right: -60, width: 240, height: 240, borderRadius: "50%", background: "rgba(255,255,255,0.05)" }} />
      <div style={{ position: "absolute", bottom: -30, left: -30, width: 160, height: 160, borderRadius: "50%", background: "rgba(255,255,255,0.03)" }} />

      {gov_label && (
        <div style={{ fontSize: 10, letterSpacing: 2.5, color: colors.muted, textTransform: "uppercase", marginBottom: 10, fontFamily: "Inter, sans-serif" }}>
          {gov_label}
        </div>
      )}

      <h1 style={{ fontFamily: "Merriweather, Georgia, serif", fontSize: 34, fontWeight: 900, color: "#fff", lineHeight: 1.2, marginBottom: 8 }}>
        {(title || "").split("\\n").map((line, i) => <span key={i}>{line}{i < title.split("\\n").length - 1 && <br />}</span>)}
      </h1>

      {year_badge && (
        <span style={{ display: "inline-block", background: colors.accent, color: "#1a1a1a", fontSize: 18, fontWeight: 700, padding: "3px 16px", borderRadius: 6, marginBottom: 10 }}>
          {year_badge}
        </span>
      )}

      {(reference_number || notified_date || valid_until) && (
        <div style={{ fontSize: 10, color: colors.muted, marginBottom: 24, fontFamily: "Inter, sans-serif" }}>
          {[reference_number, notified_date && `Notified: ${notified_date}`, valid_until && `Valid Till: ${valid_until}`].filter(Boolean).join("  ·  ")}
        </div>
      )}

      {stats && stats.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(stats.length, 4)}, 1fr)`, gap: 10 }}>
          {stats.slice(0, 4).map((s, i) => (
            <div key={i} style={{ background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 10, padding: "12px 8px", textAlign: "center", backdropFilter: "blur(4px)" }}>
              <span style={{ fontFamily: "Merriweather, serif", fontSize: 20, fontWeight: 700, color: colors.accent, display: "block" }}>{s.value}</span>
              <div style={{ fontSize: 9, color: "#c8e6c9", marginTop: 3, lineHeight: 1.3, fontFamily: "Inter, sans-serif" }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function VisionMissionSection({ section, colors }) {
  const { label, title, cards, grid_items } = section;
  return (
    <div style={{ padding: "32px 36px", borderBottom: `1px solid ${colors.primary}33` }}>
      {label && <div style={{ fontSize: 9, letterSpacing: 2.5, textTransform: "uppercase", color: colors.muted, fontWeight: 600, marginBottom: 5, fontFamily: "Inter, sans-serif" }}>{label}</div>}
      {title && <h2 style={{ fontFamily: "Merriweather, serif", fontSize: 20, fontWeight: 700, color: "#fff", marginBottom: 20 }}>{title}</h2>}

      {cards && cards.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 22 }}>
          {cards.map((card, i) => (
            <div key={i} style={{ borderRadius: 12, padding: 18, background: i === 0 ? `${colors.primary}22` : `${colors.accent}22`, border: `1px solid ${i === 0 ? colors.primary : colors.accent}55` }}>
              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 2, textTransform: "uppercase", color: i === 0 ? colors.muted : colors.accent, marginBottom: 8, fontFamily: "Inter, sans-serif" }}>{card.tag}</div>
              <p style={{ fontSize: 12, color: colors.text, lineHeight: 1.6, fontFamily: "Inter, sans-serif" }}>{card.text}</p>
            </div>
          ))}
        </div>
      )}

      {grid_items && grid_items.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
          {grid_items.map((g, i) => (
            <div key={i} style={{ background: `${colors.primary}18`, borderRadius: 8, padding: "11px 12px", display: "flex", alignItems: "flex-start", gap: 8, border: `1px solid ${colors.primary}33` }}>
              <span style={{ fontSize: 18, flexShrink: 0 }}>{g.icon}</span>
              <p style={{ fontSize: 11, color: colors.text, lineHeight: 1.4, fontFamily: "Inter, sans-serif" }}>{g.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TrajectorySection({ section, colors }) {
  const { label, title, bars } = section;
  if (!bars || bars.length === 0) return null;

  const maxVal = Math.max(...bars.map(b => parseFloat(b.value_num) || 1));
  const MAX_BAR_H = 100;

  return (
    <div style={{ padding: "32px 36px", borderBottom: `1px solid ${colors.primary}33` }}>
      {label && <div style={{ fontSize: 9, letterSpacing: 2.5, textTransform: "uppercase", color: colors.muted, fontWeight: 600, marginBottom: 5, fontFamily: "Inter, sans-serif" }}>{label}</div>}
      {title && <h2 style={{ fontFamily: "Merriweather, serif", fontSize: 20, fontWeight: 700, color: "#fff", marginBottom: 24 }}>{title}</h2>}

      <div style={{ display: "flex", alignItems: "flex-end", gap: 12, paddingBottom: 8, borderBottom: `1px solid ${colors.muted}33` }}>
        {bars.map((bar, i) => {
          const h = Math.max(((parseFloat(bar.value_num) || 1) / maxVal) * MAX_BAR_H, 8);
          const alpha = 55 + Math.floor((i / bars.length) * 45);
          return (
            <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: colors.accent, marginBottom: 4, fontFamily: "Merriweather, serif" }}>{bar.display}</div>
              <div style={{ width: "100%", height: h, background: colors.primary, opacity: alpha / 100, borderRadius: "4px 4px 0 0" }} />
              <div style={{ fontSize: 11, fontWeight: 700, color: "#fff", marginTop: 6, fontFamily: "Inter, sans-serif" }}>{bar.year}</div>
              {bar.note && <div style={{ fontSize: 9, color: colors.muted, textAlign: "center", lineHeight: 1.3, marginTop: 3, fontFamily: "Inter, sans-serif" }}>{bar.note}</div>}
            </div>
          );
        })}
      </div>

      {/* Milestone cards */}
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(bars.length, 4)}, 1fr)`, gap: 10, marginTop: 16 }}>
        {bars.map((bar, i) => (
          <div key={i} style={{ background: "#1a2a3a", border: `1px solid ${colors.primary}44`, borderRadius: 10, padding: 12, textAlign: "center" }}>
            <div style={{ fontSize: 11, color: colors.accent, fontWeight: 700, fontFamily: "Inter, sans-serif" }}>{bar.year}</div>
            <div style={{ fontSize: 17, fontWeight: 700, color: colors.muted, fontFamily: "Merriweather, serif", margin: "4px 0" }}>{bar.display}</div>
            {bar.note && <div style={{ fontSize: 9, color: "#78909c", lineHeight: 1.3, fontFamily: "Inter, sans-serif" }}>{bar.note}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

const TECH_COLORS = {
  solar: { bg: "#2a1a00", border: "#f9a825" },
  wind: { bg: "#001a2a", border: "#29b6f6" },
  bess: { bg: "#1a001a", border: "#ba68c8" },
  ocean: { bg: "#001a1a", border: "#26c6da" },
  hybrid: { bg: "#1a1a00", border: "#aed581" },
  emerging: { bg: "#0a1a0a", border: "#66bb6a" },
  default: { bg: "#1a1a2a", border: "#7986cb" },
};

function TechnologyGridSection({ section, colors }) {
  const { label, title, items } = section;
  if (!items || items.length === 0) return null;

  return (
    <div style={{ padding: "32px 36px", borderBottom: `1px solid ${colors.primary}33` }}>
      {label && <div style={{ fontSize: 9, letterSpacing: 2.5, textTransform: "uppercase", color: colors.muted, fontWeight: 600, marginBottom: 5, fontFamily: "Inter, sans-serif" }}>{label}</div>}
      {title && <h2 style={{ fontFamily: "Merriweather, serif", fontSize: 20, fontWeight: 700, color: "#fff", marginBottom: 20 }}>{title}</h2>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        {items.map((item, i) => {
          const tc = TECH_COLORS[item.color] || TECH_COLORS.default;
          return (
            <div key={i} style={{ borderRadius: 14, padding: "18px 14px", background: tc.bg, border: `1px solid ${tc.border}88`, color: "#fff" }}>
              <div style={{ fontSize: 26, marginBottom: 8 }}>{item.icon}</div>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 7, fontFamily: "Merriweather, serif" }}>{item.title}</div>
              <div style={{ fontSize: 10.5, opacity: 0.85, lineHeight: 1.5, fontFamily: "Inter, sans-serif" }}>{item.detail}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function IncentivesSection({ section, colors }) {
  const { label, title, items } = section;
  if (!items || items.length === 0) return null;

  return (
    <div style={{ padding: "32px 36px", borderBottom: `1px solid ${colors.primary}33` }}>
      {label && <div style={{ fontSize: 9, letterSpacing: 2.5, textTransform: "uppercase", color: colors.muted, fontWeight: 600, marginBottom: 5, fontFamily: "Inter, sans-serif" }}>{label}</div>}
      {title && <h2 style={{ fontFamily: "Merriweather, serif", fontSize: 20, fontWeight: 700, color: "#fff", marginBottom: 20 }}>{title}</h2>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 11 }}>
        {items.map((item, i) => (
          <div key={i} style={{ background: "#fff", borderRadius: 10, padding: "14px 16px 14px 18px", borderLeft: `4px solid ${colors.primary}`, position: "relative" }}>
            <h4 style={{ fontSize: 12, fontWeight: 700, color: colors.primary === "#2E7D32" ? "#1b5e20" : colors.primary, marginBottom: 5, fontFamily: "Merriweather, serif" }}>{item.title}</h4>
            <p style={{ fontSize: 10.5, color: "#546e7a", lineHeight: 1.5, fontFamily: "Inter, sans-serif" }}>{item.detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ImpactSection({ section, colors }) {
  const { label, title, big_number, columns } = section;

  return (
    <div style={{ padding: "32px 36px", borderBottom: `1px solid ${colors.primary}33` }}>
      {label && <div style={{ fontSize: 9, letterSpacing: 2.5, textTransform: "uppercase", color: colors.muted, fontWeight: 600, marginBottom: 5, fontFamily: "Inter, sans-serif" }}>{label}</div>}
      {title && <h2 style={{ fontFamily: "Merriweather, serif", fontSize: 20, fontWeight: 700, color: "#fff", marginBottom: 20 }}>{title}</h2>}

      <div style={{ display: "grid", gridTemplateColumns: big_number ? "180px 1fr 1fr" : "1fr 1fr", gap: 14 }}>
        {big_number && (
          <div style={{ background: "#fff9c4", border: `2px solid ${colors.accent}`, borderRadius: "50%", width: 165, height: 165, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: 10 }}>
            <div style={{ fontFamily: "Merriweather, serif", fontSize: 26, fontWeight: 900, color: "#e65100", lineHeight: 1 }}>{big_number.value}</div>
            <div style={{ fontSize: 11, color: "#5d4037", marginTop: 5, lineHeight: 1.3, fontFamily: "Inter, sans-serif" }}>{big_number.label}</div>
          </div>
        )}
        {(columns || []).map((col, i) => (
          <div key={i} style={{ borderRadius: 12, padding: 14, background: i === 0 ? "#e8f5e9" : "#e3f2fd", border: `1px solid ${i === 0 ? "#a5d6a7" : "#90caf9"}` }}>
            <h4 style={{ fontSize: 12, fontWeight: 700, marginBottom: 10, color: i === 0 ? "#1b5e20" : "#1565c0", fontFamily: "Merriweather, serif" }}>{col.title}</h4>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {(col.items || []).map((item, j) => (
                <li key={j} style={{ fontSize: 10.5, color: "#37474f", padding: "3px 0 3px 14px", position: "relative", lineHeight: 1.4, fontFamily: "Inter, sans-serif" }}>
                  <span style={{ position: "absolute", left: 0, color: i === 0 ? "#66bb6a" : "#42a5f5", fontSize: 10 }}>▸</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function AtAGlanceSection({ section, colors }) {
  const { label, title, stats, agencies, supersedes } = section;

  return (
    <div style={{ padding: "28px 36px", background: colors.bg === "#FFFFFF" ? "#f5f5f5" : "#0a150a" }}>
      {label && <div style={{ fontSize: 9, letterSpacing: 2.5, textTransform: "uppercase", color: colors.muted, fontWeight: 600, marginBottom: 5, fontFamily: "Inter, sans-serif" }}>{label}</div>}
      {title && <h2 style={{ fontFamily: "Merriweather, serif", fontSize: 18, fontWeight: 700, color: "#fff", marginBottom: 16 }}>{title}</h2>}

      {stats && stats.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 14 }}>
          {stats.map((s, i) => (
            <div key={i} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: colors.accent, fontFamily: "Merriweather, serif" }}>{s.value}</div>
              <div style={{ fontSize: 9, color: colors.muted, marginTop: 2, fontFamily: "Inter, sans-serif" }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {(agencies || supersedes) && (
        <div style={{ fontSize: 9, color: "#388e3c", lineHeight: 1.5, textAlign: "center", fontFamily: "Inter, sans-serif" }}>
          {agencies && <div>{agencies}</div>}
          {supersedes && <div style={{ marginTop: 3, opacity: 0.7 }}>{supersedes}</div>}
        </div>
      )}
    </div>
  );
}

// Generic fallback for unknown section types
function GenericSection({ section, colors }) {
  const { label, title, items, cards, grid_items, stats } = section;
  const allItems = items || cards || grid_items || stats || [];

  return (
    <div style={{ padding: "32px 36px", borderBottom: `1px solid ${colors.primary}33` }}>
      {label && <div style={{ fontSize: 9, letterSpacing: 2.5, textTransform: "uppercase", color: colors.muted, fontWeight: 600, marginBottom: 5, fontFamily: "Inter, sans-serif" }}>{label}</div>}
      {title && <h2 style={{ fontFamily: "Merriweather, serif", fontSize: 20, fontWeight: 700, color: "#fff", marginBottom: 18 }}>{title}</h2>}
      {allItems.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
          {allItems.map((item, i) => {
            const text = item.text || item.detail || item.value || JSON.stringify(item);
            const heading = item.title || item.tag || item.label || item.icon || "";
            return (
              <div key={i} style={{ background: `${colors.primary}18`, borderRadius: 8, padding: "11px 13px", border: `1px solid ${colors.primary}33` }}>
                {heading && <div style={{ fontSize: 11, fontWeight: 700, color: colors.accent, marginBottom: 4, fontFamily: "Merriweather, serif" }}>{heading}</div>}
                <p style={{ fontSize: 10.5, color: colors.text, lineHeight: 1.4, fontFamily: "Inter, sans-serif" }}>{text}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── SECTION DISPATCHER ────────────────────────────────────────────────────────
function Section({ section, colors }) {
  const type = (section.type || "").toLowerCase();
  switch (type) {
    case "vision_mission":
    case "vision":
      return <VisionMissionSection section={section} colors={colors} />;
    case "trajectory":
    case "capacity_trajectory":
      return <TrajectorySection section={section} colors={colors} />;
    case "technology_grid":
    case "technologies":
      return <TechnologyGridSection section={section} colors={colors} />;
    case "incentives":
    case "incentives_provisions":
      return <IncentivesSection section={section} colors={colors} />;
    case "impact":
    case "jobs_impact":
      return <ImpactSection section={section} colors={colors} />;
    case "at_a_glance":
    case "policy_glance":
    case "footer_glance":
      return <AtAGlanceSection section={section} colors={colors} />;
    default:
      return <GenericSection section={section} colors={colors} />;
  }
}

// ── DEFAULT COLOR SCHEME (fallback if missing) ────────────────────────────────
const DEFAULT_COLORS = {
  bg: "#0F1F0F",
  primary: "#2E7D32",
  accent: "#F9A825",
  text: "#E8F5E9",
  muted: "#81C784",
  card: "#1A3A1A",
};

// ── MAIN COMPONENT ────────────────────────────────────────────────────────────
export default function PolicyInfographic({ data }) {
  if (!data) {
    return (
      <div style={{ padding: 32, color: "#666", textAlign: "center", fontFamily: "Inter, sans-serif" }}>
        No infographic data available.
      </div>
    );
  }

  // Support both new rich format (data.header, data.sections) and old flat format
  const isNewFormat = !!(data.header || data.sections);

  if (!isNewFormat) {
    return <LegacyInfographic data={data} />;
  }

  const colors = data.color_scheme || DEFAULT_COLORS;
  const sections = data.sections || [];

  return (
    <div
      style={{
        fontFamily: "'Inter', sans-serif",
        background: colors.bg,
        color: colors.text,
        maxWidth: 900,
        margin: "0 auto",
        borderRadius: 8,
        overflow: "hidden",
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
      }}
    >
      {/* Google Fonts */}
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700;900&family=Inter:wght@400;500;600;700&display=swap');`}</style>

      {/* Header */}
      {data.header && <Header data={data} colors={colors} />}

      {/* Sections */}
      {sections.map((section, i) => (
        <Section key={i} section={section} colors={colors} />
      ))}
    </div>
  );
}

// ── LEGACY RENDERER (handles old flat infographic_data format) ───────────────
function LegacyInfographic({ data }) {
  const colors = DEFAULT_COLORS;

  return (
    <div
      style={{
        fontFamily: "'Inter', sans-serif",
        background: colors.bg,
        color: colors.text,
        maxWidth: 900,
        margin: "0 auto",
        borderRadius: 8,
        overflow: "hidden",
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        padding: 32,
      }}
    >
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700;900&family=Inter:wght@400;500;600;700&display=swap');`}</style>

      {/* Title */}
      <h1 style={{ fontFamily: "Merriweather, serif", fontSize: 30, color: colors.accent, marginBottom: 14, borderBottom: `3px solid ${colors.accent}`, paddingBottom: 8 }}>
        {data.title || "Policy Infographic"}
      </h1>
      {data.context && <p style={{ fontSize: 15, color: colors.text, marginBottom: 28, lineHeight: 1.6 }}>{data.context}</p>}

      {/* Two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, marginBottom: 28 }}>
        {/* Left: phases / timeline */}
        <div>
          {data.leftColTitle && <h2 style={{ fontSize: 20, color: colors.muted, marginBottom: 18, fontFamily: "Merriweather, serif" }}>{data.leftColTitle}</h2>}
          {data.phases && data.phases.length > 0 && (
            <div style={{ borderLeft: `3px solid ${colors.primary}`, paddingLeft: 14 }}>
              {data.phases.map((p, i) => (
                <div key={i} style={{ marginBottom: 20 }}>
                  <span style={{ fontSize: 22, marginRight: 8 }}>{p.icon || "📌"}</span>
                  <strong style={{ color: colors.accent }}>{p.year}</strong>
                  <span style={{ color: colors.text, marginLeft: 6 }}>{p.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: stats + cards */}
        <div>
          {data.rightColTitle && <h2 style={{ fontSize: 20, color: "#f9a825", marginBottom: 18, fontFamily: "Merriweather, serif" }}>{data.rightColTitle}</h2>}
          {data.stats && data.stats.length > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
              {data.stats.map((s, i) => (
                <div key={i} style={{ background: ["#2AADA8", "#E8A020", "#D85A30", "#8B5CF6"][i % 4], color: "white", padding: 14, borderRadius: 4, textAlign: "center" }}>
                  <p style={{ fontSize: 22, fontWeight: "bold", margin: 0 }}>{s.value}</p>
                  <p style={{ fontSize: 11, margin: "4px 0 0" }}>{s.label}</p>
                </div>
              ))}
            </div>
          )}
          {data.rightCards && data.rightCards.map((c, i) => (
            <div key={i} style={{ background: "white", padding: 11, borderRadius: 4, borderLeft: `4px solid ${["#2AADA8", "#E8A020", "#D85A30"][i % 3]}`, marginBottom: 10 }}>
              <h4 style={{ fontWeight: "bold", marginBottom: 3, color: "#1a1a1a", fontSize: 12 }}>{c.title}</h4>
              <p style={{ fontSize: 11, color: "#666", margin: 0 }}>{c.text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
