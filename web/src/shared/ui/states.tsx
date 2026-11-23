import type { ReactNode } from "react";
import styles from "./states.module.css";

export function Loading({ label }: { label: string }) {
  return (
    <div className={styles.loading} role="status" aria-live="polite">
      <span className={styles.bar} />
      <span className={styles.bar} />
      <span className={styles.bar} />
      <span className={styles.label}>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className={styles.error} role="alert">
      <p>{message}</p>
      <p className={styles.hint}>
        Run <code>python -m paf.cli report</code> to write <code>web/public/data/report.json</code>, then load it again.
      </p>
      <button type="button" className={styles.button} onClick={onRetry}>
        Load the report again
      </button>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.empty}>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
