import styles from "./page.module.css";
import { runTrackFlowDashboard } from "../lib/trackflowDashboard";

export default function Home() {
  const dashboard = runTrackFlowDashboard();

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>TrackFlow Operations</p>
          <h1>Logistics Control Center</h1>
          <p className={styles.subtitle}>
            Live demonstration of the reusable Milestone 2 TypeScript
            business logic.
          </p>
        </div>

        <span className={styles.status}>System operational</span>
      </header>

      <section className={styles.metrics}>
        <article className={styles.card}>
          <span>Inventory value</span>
          <strong>
            ${dashboard.totalInventoryValue.toLocaleString("en-US")}
          </strong>
          <small>Across both warehouses</small>
        </article>

        <article className={styles.card}>
          <span>Low-stock products</span>
          <strong>{dashboard.lowStockProducts.length}</strong>
          <small>Requires operational review</small>
        </article>

        <article className={styles.card}>
          <span>Shipment distance</span>
          <strong>{dashboard.averageShipmentDistance} km</strong>
          <small>Zaragoza to Madrid</small>
        </article>

        <article className={styles.card}>
          <span>SEUR shipping cost</span>
          <strong>${dashboard.seurShippingCost.toFixed(2)}</strong>
          <small>Calculated by Milestone 2 logic</small>
        </article>
      </section>

      <section className={styles.grid}>
        <article className={styles.panel}>
          <div className={styles.panelHeading}>
            <div>
              <p className={styles.eyebrow}>Inventory</p>
              <h2>Low-stock alerts</h2>
            </div>
          </div>

          {dashboard.lowStockProducts.map((product) => (
            <div className={styles.alertRow} key={product.sku}>
              <div>
                <strong>{product.name}</strong>
                <p>{product.sku}</p>
              </div>

              <span>
                {product.stockQuantity} / {product.minStockThreshold}
              </span>
            </div>
          ))}
        </article>

        <article className={styles.panel}>
          <div className={styles.panelHeading}>
            <div>
              <p className={styles.eyebrow}>Carrier engine</p>
              <h2>Recommended carrier</h2>
            </div>
          </div>

          {dashboard.recommendedCarrier ? (
            <div className={styles.recommendation}>
              <strong>
                {dashboard.recommendedCarrier.carrier.name}
              </strong>

              <p>
                Selected for shipment {dashboard.shipment.id} to{" "}
                {dashboard.shipment.destination.city}.
              </p>

              <dl>
                <div>
                  <dt>Score</dt>
                  <dd>{dashboard.recommendedCarrier.score}</dd>
                </div>

                <div>
                  <dt>Estimated cost</dt>
                  <dd>
                    ${dashboard.recommendedCarrier.cost.toFixed(2)}
                  </dd>
                </div>

                <div>
                  <dt>Priority</dt>
                  <dd>{dashboard.shipment.priority}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <p>No suitable carrier was found.</p>
          )}
        </article>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeading}>
          <div>
            <p className={styles.eyebrow}>Carrier performance</p>
            <h2>Reliability ranking</h2>
          </div>
        </div>

        <div className={styles.tableWrapper}>
          <table>
            <thead>
              <tr>
                <th>Carrier</th>
                <th>Markets</th>
                <th>On-time rate</th>
                <th>Average delivery</th>
              </tr>
            </thead>

            <tbody>
              {dashboard.carriersByReliability.map((carrier) => (
                <tr key={carrier.id}>
                  <td>{carrier.name}</td>
                  <td>{carrier.operatesIn.join(", ")}</td>
                  <td>{carrier.onTimeRate}%</td>
                  <td>{carrier.avgDeliveryDays} day(s)</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <footer className={styles.proof}>
        Business logic imported from{" "}
        <code>src/utils/collections.ts</code> and{" "}
        <code>src/utils/transformations.ts</code>.
      </footer>
    </main>
  );
}
