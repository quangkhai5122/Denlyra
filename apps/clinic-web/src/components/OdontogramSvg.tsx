"use client";

import { useState, type KeyboardEvent } from "react";

export const PERMANENT_UPPER_RIGHT = ["18", "17", "16", "15", "14", "13", "12", "11"] as const;
export const PERMANENT_UPPER_LEFT = ["21", "22", "23", "24", "25", "26", "27", "28"] as const;
export const PERMANENT_LOWER_RIGHT = ["48", "47", "46", "45", "44", "43", "42", "41"] as const;
export const PERMANENT_LOWER_LEFT = ["31", "32", "33", "34", "35", "36", "37", "38"] as const;

export const PRIMARY_UPPER_RIGHT = ["55", "54", "53", "52", "51"] as const;
export const PRIMARY_UPPER_LEFT = ["61", "62", "63", "64", "65"] as const;
export const PRIMARY_LOWER_RIGHT = ["85", "84", "83", "82", "81"] as const;
export const PRIMARY_LOWER_LEFT = ["71", "72", "73", "74", "75"] as const;

export const TOOTH_SURFACES = [
  { code: "O", label: "O — Mặt nhai / Rìa cắn" },
  { code: "M", label: "M — Mặt gần (Mesial)" },
  { code: "D", label: "D — Mặt xa (Distal)" },
  { code: "B", label: "B — Mặt ngoài / Má (Buccal)" },
  { code: "L", label: "L — Mặt trong / Lưỡi (Lingual)" },
] as const;

export type ToothSurfaceCode = (typeof TOOTH_SURFACES)[number]["code"];

export interface OdontogramFindingItem {
  id: string;
  tooth_code: string;
  surface: string;
  finding_text_demo: string;
  created_at: string;
}

interface OdontogramSvgProps {
  selectedTooth: string;
  selectedSurface: ToothSurfaceCode;
  findings: OdontogramFindingItem[];
  onSelectTooth: (toothCode: string) => void;
  onSelectSurface: (surface: ToothSurfaceCode) => void;
}

export function OdontogramSvg({
  selectedTooth,
  selectedSurface,
  findings,
  onSelectTooth,
  onSelectSurface,
}: OdontogramSvgProps) {
  const [dentition, setDentition] = useState<"permanent" | "primary">("permanent");

  const countByTooth = new Map<string, number>();
  for (const f of findings) {
    countByTooth.set(f.tooth_code, (countByTooth.get(f.tooth_code) ?? 0) + 1);
  }

  const handleToothKeyDown = (e: KeyboardEvent<SVGGElement>, code: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelectTooth(code);
    }
  };

  const upperRight = dentition === "permanent" ? PERMANENT_UPPER_RIGHT : PRIMARY_UPPER_RIGHT;
  const upperLeft = dentition === "permanent" ? PERMANENT_UPPER_LEFT : PRIMARY_UPPER_LEFT;
  const lowerRight = dentition === "permanent" ? PERMANENT_LOWER_RIGHT : PRIMARY_LOWER_RIGHT;
  const lowerLeft = dentition === "permanent" ? PERMANENT_LOWER_LEFT : PRIMARY_LOWER_LEFT;

  const renderRow = (
    rightQuad: readonly string[],
    leftQuad: readonly string[],
    yOffset: number,
    archLabel: string,
  ) => {
    const combined = [...rightQuad, ...leftQuad];
    const startX = dentition === "permanent" ? 18 : 144;
    const gapMid = 18;
    const halfIdx = rightQuad.length;

    return (
      <g aria-label={archLabel}>
        {combined.map((code, idx) => {
          const x = startX + idx * 42 + (idx >= halfIdx ? gapMid : 0);
          const isSelected = selectedTooth === code;
          const obsCount = countByTooth.get(code) ?? 0;
          const fill = isSelected ? "#0f766e" : obsCount > 0 ? "#ccfbf1" : "#ffffff";
          const stroke = isSelected ? "#103b4b" : obsCount > 0 ? "#0f766e" : "#94a3b8";
          const textFill = isSelected ? "#ffffff" : "#0f172a";

          return (
            <g
              key={code}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              aria-label={`Răng FDI ${code}${obsCount > 0 ? `, có ${obsCount} ghi nhận demo` : ""}`}
              onClick={() => onSelectTooth(code)}
              onKeyDown={(e) => handleToothKeyDown(e, code)}
              className="odontogram-tooth"
              transform={`translate(${x}, ${yOffset})`}
            >
              <rect
                x={0}
                y={0}
                width={36}
                height={48}
                rx={8}
                fill={fill}
                stroke={stroke}
                strokeWidth={isSelected ? 2.5 : 1.5}
              />
              <circle
                cx={18}
                cy={16}
                r={7}
                fill={isSelected ? "#14b8a6" : "#f1f5f9"}
                stroke={stroke}
                strokeWidth={1}
              />
              <text
                x={18}
                y={39}
                textAnchor="middle"
                fontSize={12}
                fontWeight={700}
                fill={textFill}
              >
                {code}
              </text>
              {obsCount > 0 && (
                <g transform="translate(28, 6)">
                  <circle cx={0} cy={0} r={7} fill="#b45309" />
                  <text x={0} y={3.5} textAnchor="middle" fontSize={9} fontWeight={700} fill="#fff">
                    {obsCount}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </g>
    );
  };

  return (
    <div className="odontogram-wrap">
      <div className="tab-strip" role="tablist" aria-label="Hệ răng FDI">
        <button
          type="button"
          role="tab"
          aria-selected={dentition === "permanent"}
          className={dentition === "permanent" ? "pill active" : "pill"}
          onClick={() => {
            setDentition("permanent");
            if (!selectedTooth.startsWith("1") && !selectedTooth.startsWith("2") && !selectedTooth.startsWith("3") && !selectedTooth.startsWith("4")) {
              onSelectTooth("16");
            }
          }}
        >
          Răng vĩnh viễn (11–48)
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={dentition === "primary"}
          className={dentition === "primary" ? "pill active" : "pill"}
          onClick={() => {
            setDentition("primary");
            onSelectTooth("55");
          }}
        >
          Răng sữa (51–85)
        </button>
      </div>

      <svg
        viewBox="0 0 726 146"
        className="odontogram-svg"
        role="group"
        aria-label="Sơ đồ răng FDI tương tác (giả lập nghiên cứu, hỗ trợ bàn phím Enter/Space)"
      >
        <line x1={363} y1={8} x2={363} y2={138} stroke="#cbd5e1" strokeDasharray="4 4" />
        <line x1={16} y1={73} x2={710} y2={73} stroke="#cbd5e1" strokeDasharray="4 4" />
        {renderRow(upperRight, upperLeft, 14, "Hàm trên FDI")}
        {renderRow(lowerRight, lowerLeft, 82, "Hàm dưới FDI")}
      </svg>

      <fieldset className="surface-fieldset">
        <legend>
          Bề mặt răng đang chọn cho <strong>Răng #{selectedTooth}</strong>
        </legend>
        <div className="surface-pills">
          {TOOTH_SURFACES.map((s) => (
            <button
              key={s.code}
              type="button"
              aria-pressed={selectedSurface === s.code}
              className={selectedSurface === s.code ? "pill active" : "pill"}
              onClick={() => onSelectSurface(s.code)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </fieldset>
    </div>
  );
}
