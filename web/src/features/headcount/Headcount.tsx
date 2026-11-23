import { useState } from "react";
import { CUTOVER, monthLabel, type WorldReport } from "../../shared/data/report";
import styles from "./headcount.module.css";

const W = 720;
const H = 300;
const PAD = { l: 44, r: 120, t: 20, b: 34 };

export function Headcount({ world }: { world: WorldReport }) {
  const [hover, setHover] = useState<number | null>(null);
  const s = world.series;
  const n = s.truth_headcount.length;
  const all = [...s.truth_headcount, ...s.status_quo_headcount, ...s.platform_headcount];
  const lo = Math.floor((Math.min(...all) - 10) / 50) * 50;
  const hi = Math.ceil((Math.max(...all) + 10) / 50) * 50;
  const x = (m: number) => PAD.l + (m / (n - 1)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const path = (vs: number[]) => vs.map((v, m) => `${m ? "L" : "M"}${x(m).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const lines = [
    { key: "truth", vs: s.truth_headcount, cls: styles.truth, name: "Who really works here" },
    { key: "sq", vs: s.status_quo_headcount, cls: styles.sq, name: "Spreadsheets" },
    { key: "pf", vs: s.platform_headcount, cls: styles.pf, name: "Platform" },
  ];
  const ticks: number[] = [];
  for (let v = lo; v <= hi; v += 50) ticks.push(v);
  return (
    <figure className={styles.figure}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className={styles.svg}
        role="img"
        aria-label="Company headcount each month: the truth, what spreadsheets reported, and what the platform reported"
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          const m = Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (n - 1));
          setHover(m >= 0 && m < n ? m : null);
        }}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className={styles.grid} />
            <text x={PAD.l - 8} y={y(v) + 4} className={styles.tick} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {[0, 12, 24, n - 1].map((m) => (
          <text key={m} x={x(m)} y={H - 12} className={styles.tick} textAnchor="middle">
            {monthLabel(m)}
          </text>
        ))}
        <line x1={x(CUTOVER)} x2={x(CUTOVER)} y1={PAD.t} y2={H - PAD.b} className={styles.cutover} />
        <text x={x(CUTOVER) + 6} y={PAD.t + 10} className={styles.cutLabel}>
          New HRIS live
        </text>
        {lines.map((l, i) =>
          l.key === "truth" ? (
            <path key={l.key} d={path(l.vs)} className={l.cls} />
          ) : (
            // drawn in once on load; the global reduced-motion rule makes it instant
            <path key={l.key} d={path(l.vs)} className={`${l.cls} ${styles.draw}`} pathLength={1} style={{ animationDelay: `${0.2 * i}s` }} />
          ),
        )}
        {lines.map((l, i) => (
          <text key={l.key} x={x(n - 1) + 8} y={y(l.vs[n - 1] ?? 0) + [6, -8, 20][i]!} className={styles.label}>
            {l.name}
          </text>
        ))}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={H - PAD.b} className={styles.cross} />}
      </svg>
      {hover !== null && (
        <div className={styles.tip} role="status">
          <strong>{monthLabel(hover)}</strong>
          <span>Truth: {s.truth_headcount[hover]}</span>
          <span>Spreadsheets: {s.status_quo_headcount[hover]}</span>
          <span>Platform: {s.platform_headcount[hover]}</span>
        </div>
      )}
      <Gap world={world} />
      <figcaption className={styles.caption}>
        Company headcount, seed {world.sample_seed} (simulated). The platform&apos;s line sits on the truth; the
        spreadsheets count ghosts and contractors, then lose the migration.
      </figcaption>
    </figure>
  );
}

/** Reported minus true headcount, month by month: the error the main chart is too tall to show. */
function Gap({ world }: { world: WorldReport }) {
  const s = world.series;
  const n = s.truth_headcount.length;
  const gaps = [
    { name: "Spreadsheets", cls: styles.gapSq, vs: s.status_quo_headcount.map((v, i) => v - (s.truth_headcount[i] ?? 0)) },
    { name: "Platform", cls: styles.gapPf, vs: s.platform_headcount.map((v, i) => v - (s.truth_headcount[i] ?? 0)) },
  ];
  const max = Math.max(1, ...gaps.flatMap((g) => g.vs.map(Math.abs)));
  return (
    <div className={styles.gap} aria-label="Reported minus true headcount by month">
      {gaps.map((g) => (
        <div key={g.name} className={styles.gapRow}>
          <span className={styles.gapName}>{g.name}</span>
          <span className={styles.gapBars}>
            {g.vs.map((v, i) => (
              <span
                key={i}
                className={g.cls}
                style={{ height: `${(Math.abs(v) / max) * 100}%`, opacity: i === CUTOVER ? 1 : 0.8 }}
                title={`${monthLabel(i)}: ${v > 0 ? "+" : ""}${v}`}
              />
            ))}
          </span>
          <span className={styles.gapMax}>
            {Math.max(...g.vs.map(Math.abs)) === 0 ? "exact every month" : `off by up to ${Math.max(...g.vs.map(Math.abs))}`}
          </span>
        </div>
      ))}
      <span className={styles.gapNote}>
        Reported minus true headcount, {n} months
      </span>
    </div>
  );
}
