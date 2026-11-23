import type { CatalogueKpi, DesignRow } from "../../shared/data/report";
import { pct } from "../../shared/format";
import styles from "./catalogue.module.css";

export function Catalogue({ kpis, platform, spreadsheet }: { kpis: CatalogueKpi[]; platform: DesignRow; spreadsheet: DesignRow }) {
  return (
    <dl className={styles.list}>
      {kpis.map((k) => (
        <div key={k.id} className={styles.item}>
          <dt>
            {k.name}
            <span className={styles.owner}>{k.owner}</span>
          </dt>
          <dd>
            <p>{k.definition}</p>
            <p className={styles.acc}>
              Cells right: <strong>{pct(platform.kpi_by[k.id])}</strong> platform,{" "}
              <span className={styles.sq}>{pct(spreadsheet.kpi_by[k.id])}</span> spreadsheets
            </p>
          </dd>
        </div>
      ))}
    </dl>
  );
}
