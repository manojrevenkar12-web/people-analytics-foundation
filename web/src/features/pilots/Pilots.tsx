import type { DesignRow, PilotMetric, WorldReport } from "../../shared/data/report";
import { pct } from "../../shared/format";
import styles from "./pilots.module.css";

const THEMES: Record<string, string> = {
  pay: "Pay",
  manager: "Manager",
  career_growth: "Career growth",
  workload: "Workload",
  role_fit: "Role fit",
  relocation: "Relocation",
  culture: "Culture",
};

function Interval({ label, metric, lo, hi }: { label: string; metric: PilotMetric; lo: number; hi: number }) {
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div className={styles.readout}>
      <span className={styles.readLabel}>{label}</span>
      <div className={styles.rows}>
        {metric.per_seed.map((s, i) => {
          const covered = s.ci[0] <= s.true_effect && s.true_effect <= s.ci[1];
          return (
            <div key={i} className={styles.track} aria-label={`seed ${i + 1}: ${s.estimate.toFixed(1)} minutes, interval ${s.ci[0].toFixed(1)} to ${s.ci[1].toFixed(1)}, truth ${s.true_effect.toFixed(1)}`}>
              <span className={covered ? styles.ci : styles.ciMiss} style={{ left: x(s.ci[0]), width: `calc(${x(s.ci[1])} - ${x(s.ci[0])})` }} />
              <span className={styles.est} style={{ left: x(s.estimate) }} />
              <span className={styles.truth} style={{ left: x(s.true_effect) }} title="true effect" />
            </div>
          );
        })}
      </div>
      <span className={styles.verdict}>
        {metric.covered_seeds} of {metric.seeds} intervals cover the truth
      </span>
    </div>
  );
}

export function Pilots({ world }: { world: WorldReport }) {
  const d = world.designs;
  const p = d.platform as DesignRow;
  const ba = d.before_after;
  const pm = p.pilot_minutes;
  const bam = ba?.pilot_minutes;
  if (!pm) return null;
  const all = [...pm.per_seed, ...(bam?.per_seed ?? [])].flatMap((s) => [s.ci[0], s.ci[1], s.true_effect]);
  const lo = Math.floor(Math.min(...all)) - 1;
  const hi = Math.ceil(Math.max(...all)) + 1;
  const shares = world.exit_shares;
  const maxShare = Math.max(...Object.values(shares.truth), ...Object.values(shares.platform), ...Object.values(shares.model_alone));
  const sens = [
    { name: "Platform", n: p.sensitive_read_by_model },
    { name: "Without the sensitive-topic rule", n: d.no_sensitive_rule?.sensitive_read_by_model ?? 0 },
    { name: "Model alone", n: d.model_alone?.sensitive_read_by_model ?? 0 },
  ];
  return (
    <div className={styles.wrap}>
      <section className={styles.block} aria-labelledby="hd">
        <h3 id="hd">Helpdesk assistant: People-team minutes per question</h3>
        <p className={styles.lede}>
          Requesters split by a hash of their id for six months. Each line is one seed: the bar is the 95% interval, the
          dot the estimate, the tick the true effect the world knows.
        </p>
        <Interval label="Randomised" metric={pm} lo={lo} hi={hi} />
        {bam && <Interval label="Before/after" metric={bam} lo={lo} hi={hi} />}
        <div className={styles.scale} aria-hidden>
          <span>{lo} min</span>
          <span>{hi} min</span>
        </div>
        <dl className={styles.facts}>
          <div>
            <dt>Wrong answers</dt>
            <dd>
              {pct(p.assistant_wrong_rate)} assistant, {pct(p.manual_wrong_rate)} People team
            </dd>
          </div>
          <div>
            <dt>People-team minutes taken off</dt>
            <dd>{pct(p.people_minutes_saved_share, 0)} if rolled out to everyone</dd>
          </div>
          <div>
            <dt>Sensitive questions a model read</dt>
            <dd>
              {sens.map((s) => (
                <span key={s.name} className={s.n ? styles.bad : styles.good}>
                  {s.name}: {s.n}
                </span>
              ))}
            </dd>
          </div>
        </dl>
      </section>
      <section className={styles.block} aria-labelledby="ex">
        <h3 id="ex">Exit comments: why people really left, and what each coder said</h3>
        <div className={styles.themes}>
          {Object.keys(THEMES).map((t) => (
            <div key={t} className={styles.theme}>
              <span className={styles.tname}>{THEMES[t]}</span>
              {(["truth", "platform", "model_alone"] as const).map((k) => (
                <span key={k} className={styles.tbar}>
                  <span className={styles[`t_${k}`]} style={{ width: `${((shares[k][t] ?? 0) / maxShare) * 100}%` }} />
                  <span className={styles.tval}>{pct(shares[k][t], 0)}</span>
                </span>
              ))}
            </div>
          ))}
        </div>
        <ul className={styles.legend}>
          <li>
            <span className={styles.t_truth} /> the real reason
          </li>
          <li>
            <span className={styles.t_platform} /> platform ({pct(p.exit_accuracy, 0)} right, {pct(p.exit_by_model, 0)} coded by the model)
          </li>
          <li>
            <span className={styles.t_model_alone} /> model alone ({pct(d.model_alone?.exit_accuracy, 0)} right)
          </li>
        </ul>
      </section>
    </div>
  );
}
