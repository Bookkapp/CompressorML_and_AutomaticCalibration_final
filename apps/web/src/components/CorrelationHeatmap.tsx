import React, { useState } from "react";

interface CorrelationHeatmapProps {
  correlations?: Record<string, Record<string, number>>;
  title?: string;
  subtitle?: string;
}

const FEATURE_META: Record<string, { label: string; short: string; desc: string }> = {
  hp1: { label: "CP1 High (Hp1)", short: "Hp1", desc: "High pressure CP1" },
  lp1: { label: "CP1 Low (Lp1)", short: "Lp1", desc: "Low pressure CP1" },
  hp2: { label: "CP2 High (Hp2)", short: "Hp2", desc: "High pressure CP2; qualified field reference 180–230 psi" },
  lp2: { label: "CP2 Low (Lp2)", short: "Lp2", desc: "Low pressure CP2" },
  dp1: { label: "CP1 ΔP (Dp1)", short: "ΔP1", desc: "Pressure difference Hp1 - Lp1 (not ratio)" },
  dp2: { label: "CP2 ΔP (Dp2)", short: "ΔP2", desc: "Pressure difference Hp2 - Lp2 (not ratio)" },
  valve: { label: "EEV Valve", short: "Valve", desc: "Expansion valve command (count)" },
  temphi: { label: "Temp High", short: "T_hi", desc: "Compressor temperature; source units" },
  templo: { label: "Temp Low", short: "T_lo", desc: "Discharge pipe temperature; source units" }
};

const ORDERED_KEYS = ["hp1", "lp1", "hp2", "lp2", "dp1", "dp2", "valve", "temphi", "templo"];

function getCellColor(value: number): { bg: string; text: string } {
  if (isNaN(value)) return { bg: "#f1f5f9", text: "#94a3b8" };
  if (value >= 0.99) return { bg: "#0284c7", text: "#ffffff" }; // Diagonal self

  if (value > 0) {
    const intensity = Math.min(1, value);
    if (intensity > 0.7) return { bg: `rgba(225, 112, 85, ${0.35 + intensity * 0.55})`, text: "#ffffff" };
    if (intensity > 0.35) return { bg: `rgba(230, 126, 34, ${0.2 + intensity * 0.45})`, text: "#1a202c" };
    return { bg: `rgba(243, 156, 18, ${0.1 + intensity * 0.25})`, text: "#4a5568" };
  } else {
    const intensity = Math.min(1, Math.abs(value));
    if (intensity > 0.7) return { bg: `rgba(41, 128, 185, ${0.4 + intensity * 0.5})`, text: "#ffffff" };
    if (intensity > 0.35) return { bg: `rgba(52, 152, 219, ${0.2 + intensity * 0.4})`, text: "#0f172a" };
    return { bg: `rgba(129, 178, 222, ${0.12 + intensity * 0.25})`, text: "#4a5568" };
  }
}

export const CorrelationHeatmap: React.FC<CorrelationHeatmapProps> = ({
  correlations,
  title = "Inter-Feature Correlation Matrix",
  subtitle = "Pearson correlation coefficients during qualified operating state"
}) => {
  const [hoveredCell, setHoveredCell] = useState<{ row: string; col: string; val: number } | null>(null);

  if (!correlations || Object.keys(correlations).length === 0) {
    return (
      <div className="heatmap-empty">
        <p>ไม่มีข้อมูล Correlation matrix สำหรับ Profile หรือ Module นี้</p>
      </div>
    );
  }

  const availableFeatures = ORDERED_KEYS.filter(k => correlations[k] !== undefined);

  return (
    <div className="correlation-heatmap-container">
      <div className="heatmap-header">
        <div>
          <h4>{title}</h4>
          <p>{subtitle}</p>
        </div>
        <div className="heatmap-scale-legend">
          <span className="legend-label">-1.0 (Inverse)</span>
          <div className="gradient-bar" />
          <span className="legend-label">+1.0 (Coupled)</span>
        </div>
      </div>

      <div className="heatmap-scroll-wrapper">
        <table className="heatmap-table">
          <thead>
            <tr>
              <th className="corner-cell">Feature</th>
              {availableFeatures.map(colKey => (
                <th key={colKey} title={FEATURE_META[colKey]?.desc ?? colKey}>
                  {FEATURE_META[colKey]?.short ?? colKey}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {availableFeatures.map(rowKey => (
              <tr key={rowKey}>
                <td className="row-header" title={FEATURE_META[rowKey]?.desc ?? rowKey}>
                  <strong>{FEATURE_META[rowKey]?.short ?? rowKey}</strong>
                  <small>{FEATURE_META[rowKey]?.label ?? rowKey}</small>
                </td>
                {availableFeatures.map(colKey => {
                  const rawValue = correlations[rowKey]?.[colKey];
                  const val = typeof rawValue === "number" ? rawValue : NaN;
                  const { bg, text } = getCellColor(val);
                  const isHovered = hoveredCell?.row === rowKey && hoveredCell?.col === colKey;

                  return (
                    <td
                      key={colKey}
                      className={`heatmap-cell ${isHovered ? "hovered" : ""}`}
                      style={{ backgroundColor: bg, color: text }}
                      onMouseEnter={() => setHoveredCell({ row: rowKey, col: colKey, val })}
                      onMouseLeave={() => setHoveredCell(null)}
                      title={`${FEATURE_META[rowKey]?.label} ↔ ${FEATURE_META[colKey]?.label}: r = ${Number.isFinite(val) ? val.toFixed(2) : "not available"}`}
                    >
                      {Number.isFinite(val) ? val.toFixed(2) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hoveredCell && (
        <div className="heatmap-tooltip-banner">
          <div className="tooltip-content">
            <span className="features">
              <strong>{FEATURE_META[hoveredCell.row]?.label ?? hoveredCell.row}</strong>
              {" ↔ "}
              <strong>{FEATURE_META[hoveredCell.col]?.label ?? hoveredCell.col}</strong>
            </span>
            <span className="value-tag">
              r = <strong>{Number.isFinite(hoveredCell.val) ? hoveredCell.val.toFixed(3) : "—"}</strong>
            </span>
            <span className="desc">
              {!Number.isFinite(hoveredCell.val)
                ? "ไม่มี correlation ที่คำนวณได้ ไม่ใช่ r = 0"
                : hoveredCell.row === hoveredCell.col
                ? "Self correlation (1.00)"
                : hoveredCell.val > 0.7
                ? "ค่าขยับในทิศทางเดียวกันใน Reference ที่เลือก ไม่ใช่หลักฐานของสาเหตุ"
                : hoveredCell.val < -0.4
                ? "ค่าขยับสวนทางกันใน Reference ที่เลือก ไม่ใช่หลักฐานของสาเหตุ"
                : "Moderate / weak baseline interaction"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
