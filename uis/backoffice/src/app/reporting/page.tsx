"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./reporting.module.css";

type WeeklyPerformanceEntry = {
  warehouse: string;
  client_id: string;
  inbound_units_count: number;
  outbound_orders_count: number;
  stockout_events_count: number;
  discrepancy_events_count: number;
  discrepancy_rate: number;
};

type WeeklyPerformanceResponse = {
  week_start: string | null;
  entries: WeeklyPerformanceEntry[];
};

const reportingApiUrl =
  process.env.NEXT_PUBLIC_REPORTING_API_URL ??
  "http://localhost:8000";

function formatWarehouse(warehouse: string): string {
  return warehouse
    .split("_")
    .map(
      (word) =>
        word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

function formatClient(clientId: string): string {
  return clientId
    .split("-")
    .map(
      (word) =>
        word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

function formatWeekStart(value: string | null): string {
  if (!value) {
    return "No reporting period available";
  }

  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatPercentage(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export default function ReportingPage() {
  const [report, setReport] =
    useState<WeeklyPerformanceResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchInitialReport(): Promise<void> {
      try {
        const response = await fetch(
          `${reportingApiUrl}/reporting/weekly-warehouse-client-performance`,
          {
            cache: "no-store",
          },
        );

        if (!response.ok) {
          throw new Error(
            `Reporting service returned ${response.status}`,
          );
        }

        const data =
          (await response.json()) as WeeklyPerformanceResponse;

        if (!cancelled) {
          setReport(data);
        }
      } catch (requestError) {
        const message =
          requestError instanceof Error
            ? requestError.message
            : "Unable to load the weekly performance report.";

        if (!cancelled) {
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchInitialReport();

    return () => {
      cancelled = true;
    };
  }, []);

  async function refreshReport(): Promise<void> {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${reportingApiUrl}/reporting/weekly-warehouse-client-performance`,
        {
          cache: "no-store",
        },
      );

      if (!response.ok) {
        throw new Error(
          `Reporting service returned ${response.status}`,
        );
      }

      const data =
        (await response.json()) as WeeklyPerformanceResponse;

      setReport(data);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Unable to load the weekly performance report.";

      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  const totals = useMemo(() => {
    const entries = report?.entries ?? [];

    return entries.reduce(
      (summary, entry) => ({
        inboundVolume:
          summary.inboundVolume +
          entry.inbound_units_count,
        outboundThroughput:
          summary.outboundThroughput +
          entry.outbound_orders_count,
        stockoutFrequency:
          summary.stockoutFrequency +
          entry.stockout_events_count,
        discrepancyEvents:
          summary.discrepancyEvents +
          entry.discrepancy_events_count,
      }),
      {
        inboundVolume: 0,
        outboundThroughput: 0,
        stockoutFrequency: 0,
        discrepancyEvents: 0,
      },
    );
  }, [report]);

  const overallDiscrepancyRate =
    totals.outboundThroughput > 0
      ? totals.discrepancyEvents /
        totals.outboundThroughput
      : 0;

  return (
    <main className={styles.page}>
      <section className={styles.container}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              TrackFlow Executive Reporting
            </p>

            <h1>
              Weekly Warehouse &amp; Client Performance Report
            </h1>

            <p className={styles.subtitle}>
              Week beginning{" "}
              <strong>
                {formatWeekStart(report?.week_start ?? null)}
              </strong>
            </p>
          </div>

          <button
            className={styles.refreshButton}
            type="button"
            onClick={() => void refreshReport()}
            disabled={isLoading}
          >
            {isLoading ? "Refreshing..." : "Refresh report"}
          </button>
        </header>

        {error && (
          <section className={styles.errorCard}>
            <h2>Report unavailable</h2>
            <p>{error}</p>
          </section>
        )}

        {!error && isLoading && (
          <section className={styles.statusCard}>
            Loading the latest weekly performance data...
          </section>
        )}

        {!error && !isLoading && report && (
          <>
            <section className={styles.summaryGrid}>
              <article className={styles.summaryCard}>
                <span>Inbound Volume</span>
                <strong>
                  {totals.inboundVolume.toLocaleString(
                    "en-US",
                  )}
                </strong>
                <p>Units received during the week</p>
              </article>

              <article className={styles.summaryCard}>
                <span>Outbound Throughput</span>
                <strong>
                  {totals.outboundThroughput.toLocaleString(
                    "en-US",
                  )}
                </strong>
                <p>Orders picked and dispatched</p>
              </article>

              <article className={styles.summaryCard}>
                <span>Stockout Frequency</span>
                <strong>
                  {totals.stockoutFrequency.toLocaleString(
                    "en-US",
                  )}
                </strong>
                <p>Stock threshold events detected</p>
              </article>

              <article className={styles.summaryCard}>
                <span>Discrepancy Rate</span>
                <strong>
                  {formatPercentage(
                    overallDiscrepancyRate,
                  )}
                </strong>
                <p>
                  Inventory discrepancies per outbound order
                </p>
              </article>
            </section>

            <section className={styles.reportCard}>
              <div className={styles.reportHeading}>
                <div>
                  <h2>Warehouse and client breakdown</h2>
                  <p>
                    One row per warehouse and client for the
                    selected ISO week.
                  </p>
                </div>

                <span className={styles.entryCount}>
                  {report.entries.length}{" "}
                  {report.entries.length === 1
                    ? "entry"
                    : "entries"}
                </span>
              </div>

              {report.entries.length === 0 ? (
                <div className={styles.emptyState}>
                  No performance entries were produced for this
                  week.
                </div>
              ) : (
                <div className={styles.tableWrapper}>
                  <table>
                    <thead>
                      <tr>
                        <th>Warehouse</th>
                        <th>Client</th>
                        <th>Inbound Volume</th>
                        <th>Outbound Throughput</th>
                        <th>Stockout Frequency</th>
                        <th>Discrepancy Rate</th>
                      </tr>
                    </thead>

                    <tbody>
                      {report.entries.map((entry) => (
                        <tr
                          key={`${entry.warehouse}-${entry.client_id}`}
                        >
                          <td>
                            {formatWarehouse(
                              entry.warehouse,
                            )}
                          </td>

                          <td>
                            {formatClient(entry.client_id)}
                          </td>

                          <td>
                            {entry.inbound_units_count.toLocaleString(
                              "en-US",
                            )}
                          </td>

                          <td>
                            {entry.outbound_orders_count.toLocaleString(
                              "en-US",
                            )}
                          </td>

                          <td>
                            {entry.stockout_events_count.toLocaleString(
                              "en-US",
                            )}
                          </td>

                          <td>
                            {formatPercentage(
                              entry.discrepancy_rate,
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}