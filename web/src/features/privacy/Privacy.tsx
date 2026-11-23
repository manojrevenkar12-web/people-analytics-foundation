import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { settle } from "../../shared/theme/motion";
import type { PrivacyCell, WorldReport } from "../../shared/data/report";
import { pct } from "../../shared/format";
import styles from "./privacy.module.css";

type View = "platform" | "status_quo";

export function Privacy({ world }: { world: WorldReport }) {
  const [view, setView] = useState<View>("platform");
  const cells = world.privacy_view[view].filter((c) => c.population > 0); // a cell about nobody shows nothing
  const depts = cells.filter((c) => c.level === "dept").sort((a, b) => b.population - a.population);
  const teamsOf = (d: string) => cells.filter((c) => c.level === "team" && c.parent === d).sort((a, b) => b.population - a.population);
  const hidden = cells.filter((c) => !c.published).length;
  const small = cells.filter((c) => c.published && c.population < 5).length;
  return (
    <div className={styles.wrap}>
      <div className={styles.controls}>
        <div role="radiogroup" aria-label="Whose table" className={styles.seg}>
          <button role="radio" aria-checked={view === "platform"} onClick={() => setView("platform")}>
            Platform
          </button>
          <button role="radio" aria-checked={view === "status_quo"} onClick={() => setView("status_quo")}>
            Spreadsheets
          </button>
        </div>
        <p className={styles.summary}>
          {view === "platform"
            ? `${hidden} cells hidden; none about fewer than 5 people is shown or can be worked out.`
            : `${small} cells about fewer than 5 people are shown to every leader.`}
        </p>
      </div>
      <div className={styles.tree}>
        {depts.map((d) => (
          <section key={d.node} className={styles.dept} aria-label={d.node}>
            <Cell c={d} strong />
            <div className={styles.teams}>
              {teamsOf(d.node).map((t) => (
                <Cell key={t.node} c={t} />
              ))}
            </div>
          </section>
        ))}
      </div>
      <p className={styles.caption}>
        Voluntary turnover over the last 12 months, last month of seed {world.sample_seed}. Hatched cells are hidden; the
        number under each name is how many people the cell is about.
      </p>
    </div>
  );
}

function Cell({ c, strong = false }: { c: PrivacyCell; strong?: boolean }) {
  const exposed = c.published && c.population < 5;
  return (
    <div className={[styles.cell, c.published ? "" : styles.hidden, exposed ? styles.exposed : "", strong ? styles.strong : ""].join(" ")}>
      <span className={styles.name}>{c.node}</span>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={c.published ? `v${c.value}` : "hidden"}
          className={styles.value}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={settle}
        >
          {c.published ? pct(c.value, 0) : "hidden"}
        </motion.span>
      </AnimatePresence>
      <span className={styles.pop}>
        {c.population} people{c.published ? (exposed ? ", fewer than 5" : "") : `, ${c.why}`}
      </span>
    </div>
  );
}
