import { useState } from "react";
import { Catalogue } from "../features/catalogue/Catalogue";
import { Checks } from "../features/checks/Checks";
import { Forecasts } from "../features/forecasts/Forecasts";
import { Gates } from "../features/gates/Gates";
import { Headcount } from "../features/headcount/Headcount";
import { Pilots } from "../features/pilots/Pilots";
import { Privacy } from "../features/privacy/Privacy";
import { useReport, type DesignRow, type Report, type WorldReport } from "../shared/data/report";
import { pct } from "../shared/format";
import { Empty, ErrorState, Loading } from "../shared/ui/states";
import styles from "./App.module.css";

type WorldKey = "dev" | "heldout";

function Figures({ world }: { world: WorldReport }) {
  const p = world.designs.platform as DesignRow;
  const s = world.designs.status_quo as DesignRow;
  const items = [
    { value: pct(p.kpi_correct), was: pct(s.kpi_correct), label: "of published KPI cells match the truth" },
    { value: String(p.disclosures), was: String(s.disclosures), label: "cells revealing groups of fewer than 5" },
    { value: `${p.analyst_hours_month.toFixed(0)} h`, was: `${s.analyst_hours_month.toFixed(0)} h`, label: "analyst time a month" },
  ];
  return (
    <dl className={styles.figures}>
      {items.map((i) => (
        <div key={i.label}>
          <dd className={styles.big}>{i.value}</dd>
          <dt>{i.label}</dt>
          <dd className={styles.was}>spreadsheets: {i.was}</dd>
        </div>
      ))}
    </dl>
  );
}

function WorldView({ world, report }: { world: WorldReport; report: Report }) {
  const p = world.designs.platform as DesignRow;
  const s = world.designs.status_quo as DesignRow;
  return (
    <>
      <section className={styles.hero} aria-labelledby="one">
        <div className={styles.heroText}>
          <h2 id="one">One headcount across the HRIS change</h2>
          <p>
            Three years of a growing defence-tech company, {world.seeds.length} simulated runs. The old HRIS hands over to
            the new one in month 24 and the migration brings its mistakes along.
          </p>
          <Figures world={world} />
        </div>
        <Headcount world={world} />
      </section>

      <section className={styles.section} aria-labelledby="checks">
        <h2 id="checks">What the checks found in the HR data</h2>
        <p className={styles.lede}>
          Payroll is the reference for who is employed. Code settles what the systems can settle; the rest goes to the
          People team as a question, never a guess. Totals over all runs.
        </p>
        <Checks platform={p} issues={world.issues_sample} />
      </section>

      <section className={styles.section} aria-labelledby="privacy">
        <h2 id="privacy">Small groups stay out of every published cell</h2>
        <Privacy world={world} />
      </section>

      <section className={styles.section} aria-labelledby="forecasts">
        <h2 id="forecasts">Retention and hiring forecasts, checked against trailing averages</h2>
        <Forecasts world={world} />
      </section>

      <section className={styles.section} aria-labelledby="pilots">
        <h2 id="pilots">AI pilots for the People team, read out against a control group</h2>
        <Pilots world={world} />
      </section>

      <section className={styles.section} aria-labelledby="catalogue">
        <h2 id="catalogue">One definition for each number</h2>
        <p className={styles.lede}>
          Defined once in the catalogue, computed once in SQL, summed up the org tree. Power BI shows these cells and
          never recomputes them.
        </p>
        <Catalogue kpis={report.catalogue} platform={p} spreadsheet={s} />
      </section>

      <section className={styles.section} aria-labelledby="gates">
        <h2 id="gates">Gates, fixed before the held-out run</h2>
        <Gates gates={world.gates} />
      </section>
    </>
  );
}

function Loaded({ report }: { report: Report }) {
  const [key, setKey] = useState<WorldKey>(report.dev ? "dev" : "heldout");
  const world = report[key];
  return (
    <>
      <div role="radiogroup" aria-label="Which seeds" className={styles.switch}>
        <button role="radio" aria-checked={key === "dev"} onClick={() => setKey("dev")}>
          Development seeds
        </button>
        <button role="radio" aria-checked={key === "heldout"} onClick={() => setKey("heldout")}>
          Held-out seeds, run once
        </button>
      </div>
      {world ? (
        <WorldView world={world} report={report} />
      ) : (
        <Empty title="The held-out seeds have not run yet">
          They run once, behind <code>reports/heldout.lock</code>, after the gates are fixed on the development seeds:{" "}
          <code>python -m paf.cli run heldout</code>.
        </Empty>
      )}
    </>
  );
}

export function App() {
  const { load, retry } = useReport();
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1>People analytics, built from the ground up</h1>
        <p>
          One governed HR data model across the old and new HRIS, KPIs defined once, small-group privacy, forecasts
          checked against trailing averages, and AI pilots for the People team measured against a control group. Every
          number is graded against a simulated company that knows the truth.
        </p>
      </header>
      <main>
        {load.state === "loading" && <Loading label="Loading the report" />}
        {load.state === "error" && <ErrorState message={load.message} onRetry={retry} />}
        {load.state === "ready" && <Loaded report={load.report} />}
      </main>
    </div>
  );
}
