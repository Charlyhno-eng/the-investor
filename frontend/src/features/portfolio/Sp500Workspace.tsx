import { useState } from "react";
import { Icon } from "../../components/Icon";
import type { Asset } from "../../lib/types";
import { Sp500Simulation } from "./Sp500Simulation";
import { ValidationPanel } from "./ValidationPanel";

export function Sp500Workspace({
  assets,
  downside = false,
}: {
  assets: Asset[];
  downside?: boolean;
}) {
  const [tab, setTab] = useState("history");
  const sp500 = assets.filter((a) => a.id === "yf-psp5.pa");
  const revision = JSON.stringify(
    sp500.map((a) => [
      a.id,
      a.data_revision,
      a.last_date,
      a.last_value,
      a.points,
    ]),
  );
  return (
    <section className="portfolio-panel strategy-built-in-workspace">
      <div
        className="detail-tabs"
        role="tablist"
        aria-label="Vues de la stratégie S&P 500"
      >
        {[
          {
            key: "history",
            label: "Validation historique",
            icon: "regression",
          },
          { key: "random", label: "Simulation aléatoire", icon: "prediction" },
        ].map(({ key, label, icon }) => (
          <button
            key={key}
            id={`sp500-tab-${key}`}
            role="tab"
            aria-selected={tab === key}
            aria-controls={`sp500-panel-${key}`}
            onClick={() => setTab(key)}
          >
            <Icon name={icon} size={16} />
            {label}
          </button>
        ))}
      </div>
      <div
        id="sp500-panel-history"
        role="tabpanel"
        aria-labelledby="sp500-tab-history"
        hidden={tab !== "history"}
      >
        <ValidationPanel
          prominentHeading
          mode={downside ? "psp5_downside" : "etf_switch"}
          holdings={JSON.stringify(
            sp500.map((a) => ({ asset_id: a.id, quantity: 1 })),
          )}
          dataRevision={revision}
        />
      </div>
      <div
        id="sp500-panel-random"
        role="tabpanel"
        aria-labelledby="sp500-tab-random"
        hidden={tab !== "random"}
      >
        <Sp500Simulation downside={downside} />
      </div>
    </section>
  );
}
