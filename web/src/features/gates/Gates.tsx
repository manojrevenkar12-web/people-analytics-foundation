import type { Gate } from "../../shared/data/report";
import styles from "./gates.module.css";

const fmt = (v: number) => (Number.isInteger(v) ? String(v) : Math.abs(v) < 10 ? v.toFixed(3) : v.toFixed(1));

export function Gates({ gates }: { gates: Gate[] }) {
  const failed = gates.filter((g) => !g.pass).length;
  return (
    <div className={styles.wrap}>
      <p className={failed ? styles.fail : styles.pass}>
        {failed ? `${gates.length - failed} of ${gates.length} gates pass; ${failed} failed.` : `All ${gates.length} gates pass.`}
      </p>
      <ul className={styles.list}>
        {gates.map((g) => (
          <li key={g.gate} className={g.pass ? styles.ok : styles.no}>
            <span className={styles.mark} aria-hidden>
              {g.pass ? "✓" : "✕"}
            </span>
            <span className={styles.name}>{g.gate}</span>
            <span className={styles.val}>
              {fmt(g.value)} <span className={styles.lim}>{g.op === "<=" ? "≤" : "≥"} {fmt(g.limit)}</span>
            </span>
            <span className="sr-only">{g.pass ? "passed" : "failed"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
