import type { DesignRow, ForecastPoint, WorldReport } from "../../shared/data/report";
import { monthLabel } from "../../shared/data/report";
import styles from "./forecasts.module.css";

function Mini({ title, unit, model, naive }: { title: string; unit: string; model: ForecastPoint[]; naive: ForecastPoint[] }) {
  const W = 340;
  const H = 170;
  const P = { l: 34, r: 12, t: 12, b: 28 };
  const vals = [...model.flatMap((p) => [p.predicted, p.actual]), ...naive.map((p) => p.predicted)];
  const hi = Math.max(...vals, 1) * 1.1;
  const n = model.length;
  const x = (i: number) => P.l + (i / Math.max(1, n - 1)) * (W - P.l - P.r);
  const y = (v: number) => P.t + (1 - v / hi) * (H - P.t - P.b);
  const line = (pts: ForecastPoint[], key: "predicted" | "actual") =>
    pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
  return (
    <figure className={styles.mini}>
      <figcaption>
        <strong>{title}</strong> <span>{unit}, by forecast origin</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: forecast against what happened`}>
        <line x1={P.l} x2={W - P.r} y1={y(0)} y2={y(0)} className={styles.axis} />
        <path d={line(model, "actual")} className={styles.actual} />
        <path d={line(naive, "predicted")} className={styles.naive} />
        <path d={line(model, "predicted")} className={styles.model} />
        {model.map((p, i) => (
          <circle key={i} cx={x(i)} cy={y(p.actual)} r={3} className={styles.dot} />
        ))}
        {[0, n - 1].map((i) => (
          <text key={i} x={x(i)} y={H - 8} textAnchor="middle" className={styles.tick}>
            {monthLabel(model[i]?.origin ?? 0)}
          </text>
        ))}
        <text x={P.l - 6} y={y(hi / 1.1) + 4} textAnchor="end" className={styles.tick}>
          {Math.round(hi / 1.1)}
        </text>
      </svg>
    </figure>
  );
}

export function Forecasts({ world }: { world: WorldReport }) {
  const p = world.designs.platform as DesignRow;
  return (
    <div className={styles.wrap}>
      <div className={styles.row}>
        <Mini title="Voluntary leavers, next 6 months" unit="company" model={world.series.retention.platform} naive={world.series.retention.naive} />
        <Mini title="Hires from open requisitions, next 90 days" unit="company" model={world.series.hiring.platform} naive={world.series.hiring.naive} />
      </div>
      <ul className={styles.legend}>
        <li>
          <span className={styles.kModel} /> forecast
        </li>
        <li>
          <span className={styles.kNaive} /> trailing average
        </li>
        <li>
          <span className={styles.kActual} /> what happened
        </li>
      </ul>
      <p className={styles.note}>
        Mean absolute error by department and origin: retention {p.retention_mae.toFixed(2)} against{" "}
        {p.retention_naive_mae.toFixed(2)} for the trailing average ({(p.retention_mae / p.retention_naive_mae).toFixed(2)}x); hiring by
        job family {p.hiring_mae.toFixed(2)} against {p.hiring_naive_mae.toFixed(2)} ({(p.hiring_mae / p.hiring_naive_mae).toFixed(2)}x).
        The strongest reason people leave here, a weak manager, is in no HR system.
      </p>
    </div>
  );
}
