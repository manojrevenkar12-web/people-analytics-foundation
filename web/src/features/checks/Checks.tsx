import { motion, useReducedMotion } from "framer-motion";
import type { DesignRow, Issue } from "../../shared/data/report";
import { settle, STAGGER } from "../../shared/theme/motion";
import styles from "./checks.module.css";

const NAMES: Record<string, [string, string]> = {
  tenure_reset_at_migration: ["Hire date reset by the migration", "Restored from the old HRIS through identity linking."],
  contractor_recorded_as_employee: ["Contractor recorded as an employee", "External cost centre; no payroll."],
  paid_after_exit: ["Notice date typed as the last day", "Payroll kept paying; the People team gave the real date."],
  exit_never_recorded: ["Left, but never given an exit date", "Unpaid for two months with no leave on record."],
  leave_not_recorded: ["Parental leave nobody recorded", "Unpaid, but still employed: not counted as a leaver."],
  zombie_requisition_closed: ["Cancelled requisition still open", "No activity for 90 days in the ATS."],
};

export function Checks({ platform, issues }: { platform: DesignRow; issues: Issue[] }) {
  const reduce = useReducedMotion();
  const rows = Object.entries(platform.corrections).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...rows.map((r) => r[1]), 1);
  return (
    <div className={styles.grid}>
      <ul className={styles.list}>
        {rows.map(([k, v], i) => (
          <li key={k}>
            <span className={styles.count}>{v}</span>
            <motion.span
              className={styles.bar}
              initial={reduce ? false : { width: 0 }}
              whileInView={{ width: `${(v / max) * 100}%` }}
              viewport={{ once: true }}
              transition={{ ...settle, delay: i * STAGGER }}
              style={reduce ? { width: `${(v / max) * 100}%` } : undefined}
              aria-hidden
            />
            <span className={styles.what}>
              <strong>{NAMES[k]?.[0] ?? k}</strong>
              <span>{NAMES[k]?.[1] ?? ""}</span>
            </span>
          </li>
        ))}
      </ul>
      <aside className={styles.queue} aria-label="Questions the platform asked the People team">
        <h3>Asked the People team</h3>
        <p className={styles.note}>
          {Math.round(platform.review_hours * 10) / 10} hours of review per run. A few of the questions, with the
          answers they got:
        </p>
        {issues.length === 0 ? (
          <p className={styles.note}>No questions were needed.</p>
        ) : (
          <ol>
            {issues.slice(0, 6).map((i, n) => (
              <li key={n}>
                <span className={styles.rule}>{i.rule.replace(/_/g, " ")}</span> {i.detail} → <em>{i.resolved}</em>
              </li>
            ))}
          </ol>
        )}
      </aside>
    </div>
  );
}
