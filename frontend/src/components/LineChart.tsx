import { useRef, useState } from "react";

export interface LineSeries {
  name: string;
  color: string;
  values: number[];
}

const W = 640;
const PAD = { top: 16, right: 92, bottom: 28, left: 64 };

function niceStep(range: number, target: number) {
  const raw = range / target;
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  const norm = raw / mag;
  return (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
}

/**
 * Small dependency-free line chart: one shared y-axis, a zero baseline when the
 * data crosses zero, direct end labels, and a crosshair tooltip that lists every
 * series at the hovered month (keyboard: arrow keys when focused).
 */
export default function LineChart({
  series,
  format,
  height = 240,
  label,
}: {
  series: LineSeries[];
  format: (n: number) => string;
  height?: number;
  label: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const n = series[0]?.values.length ?? 0;
  if (n === 0) return null;

  const all = series.flatMap((s) => s.values);
  let lo = Math.min(0, ...all);
  let hi = Math.max(0, ...all);
  if (lo === hi) hi = lo + 1;
  const step = niceStep(hi - lo, 4);
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(v);

  const plotW = W - PAD.left - PAD.right;
  const plotH = height - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const y = (v: number) => PAD.top + (1 - (v - lo) / (hi - lo)) * plotH;

  const xTicks = Array.from({ length: n }, (_, i) => i).filter(
    (i) => (i + 1) % (n > 36 ? 12 : 6) === 0 || i === 0,
  );

  function onMove(e: React.PointerEvent) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - PAD.left) / plotW) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowRight") setHover((h) => Math.min(n - 1, (h ?? -1) + 1));
    else if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? n) - 1));
    else return;
    e.preventDefault();
  }

  // Keep end labels from colliding: nudge apart vertically when too close.
  const ends = series
    .map((s) => ({ s, yy: y(s.values[n - 1]) }))
    .sort((a, b) => a.yy - b.yy);
  for (let i = 1; i < ends.length; i++) {
    if (ends[i].yy - ends[i - 1].yy < 14) ends[i].yy = ends[i - 1].yy + 14;
  }

  const tipLeftPct = hover != null ? (x(hover) / W) * 100 : 0;

  return (
    <div className="chart-wrap">
      {series.length > 1 && (
        <div className="chart-legend">
          {series.map((s) => (
            <span key={s.name}>
              <i style={{ background: s.color }} />
              {s.name}
            </span>
          ))}
        </div>
      )}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${height}`}
        className="chart-svg"
        role="img"
        aria-label={label}
        tabIndex={0}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
        onFocus={() => setHover((h) => h ?? n - 1)}
        onBlur={() => setHover(null)}
        onKeyDown={onKey}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(t)}
              y2={y(t)}
              className={t === 0 ? "chart-zero" : "chart-grid"}
            />
            <text x={PAD.left - 8} y={y(t) + 4} textAnchor="end" className="chart-tick">
              {format(t)}
            </text>
          </g>
        ))}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={height - 8} textAnchor="middle" className="chart-tick">
            {i === 0 ? "Mo 1" : i + 1}
          </text>
        ))}
        {series.map((s) => (
          <polyline
            key={s.name}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
          />
        ))}
        {ends.map(({ s, yy }) => (
          <text key={s.name} x={W - PAD.right + 8} y={yy + 4} className="chart-end-label">
            {format(s.values[n - 1])}
          </text>
        ))}
        {hover != null && (
          <g pointerEvents="none">
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={PAD.top}
              y2={PAD.top + plotH}
              className="chart-crosshair"
            />
            {series.map((s) => (
              <circle
                key={s.name}
                cx={x(hover)}
                cy={y(s.values[hover])}
                r={4.5}
                fill={s.color}
                stroke="var(--panel)"
                strokeWidth={2}
              />
            ))}
          </g>
        )}
      </svg>
      {hover != null && (
        <div
          className="chart-tooltip"
          style={{
            left: `${tipLeftPct}%`,
            transform: tipLeftPct > 60 ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
          }}
        >
          <div className="chart-tooltip-title">Month {hover + 1}</div>
          {series.map((s) => (
            <div key={s.name} className="chart-tooltip-row">
              <i style={{ background: s.color }} />
              <strong>{format(s.values[hover])}</strong>
              <span>{s.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
