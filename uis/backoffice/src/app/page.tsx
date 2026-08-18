/* eslint-disable react-hooks/set-state-in-effect */

"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./page.module.css";

const API = "https://probable-doodle-wrwr7wwqq46pcrqp-8000.app.github.dev/api/incidents";

const categories = [
  "lost_parcel",
  "delivery_failure",
  "inventory_discrepancy",
  "carrier_issue",
  "returns_issue",
  "warehouse_incident",
  "system_failure",
  "client_complaint",
  "other",
];

const statuses = ["open", "in_progress", "resolved", "discarded"];
const origins = ["customer", "branch", "internal"];

const branches = [
  ["central", "Central"],
  ["la_warehouse", "Los Angeles — Warehouse"],
  ["la_office", "Los Angeles — Office"],
  ["zaragoza_warehouse", "Zaragoza — Warehouse"],
  ["zaragoza_office", "Zaragoza — Office"],
];

type Incident = {
  id: number;
  title: string;
  description: string;
  category: string;
  status: string;
  origin: string;
  branch: string;
  created_at: string;
  updated_at: string;
};

type Summary = {
  total: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  by_origin: Record<string, number>;
  by_branch: Record<string, number>;
};

export default function Home() {
  const [form, setForm] = useState({
    title: "",
    description: "",
    category: "lost_parcel",
    status: "open",
    origin: "branch",
    branch: "central",
  });

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [filters, setFilters] = useState({ status: "", origin: "", branch: "" });

  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState("");

  const loadIncidents = useCallback(async () => {
    setListLoading(true);
    setError("");

    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });

      const res = await fetch(`${API}?${params.toString()}`);
      if (!res.ok) throw new Error("Could not load incidents.");

      setIncidents(await res.json());
    } catch {
      setError("We could not load incidents. Please try again.");
    } finally {
      setListLoading(false);
    }
  }, [filters]);

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);

    try {
      const res = await fetch(`${API}/summary`);
      if (!res.ok) throw new Error("Could not load summary.");

      setSummary(await res.json());
    } catch {
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadIncidents();
    void loadSummary();
  }, [loadIncidents, loadSummary]);

  async function submitIncident(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setSuccess("");
    setFieldError({});

    if (!form.title.trim()) {
      setFieldError({ title: "Title is required." });
      setLoading(false);
      return;
    }

    if (!form.description.trim()) {
      setFieldError({ description: "Description is required." });
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const detail = data?.detail;

        if (detail?.field) {
          setFieldError({ [detail.field]: detail.message });
        }

        throw new Error("Please check the incident form and try again.");
      }

      setForm({
        title: "",
        description: "",
        category: "lost_parcel",
        status: "open",
        origin: "branch",
        branch: "central",
      });

      setSuccess("Incident registered successfully.");
      await loadIncidents();
      await loadSummary();
    } catch {
      setError("The incident could not be saved. Please check the fields and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function updateStatus(incident: Incident, nextStatus: string) {
    const previous = incidents;

    setIncidents((items) =>
      items.map((item) =>
        item.id === incident.id ? { ...item, status: nextStatus } : item
      )
    );

    try {
      const res = await fetch(`${API}/${incident.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });

      if (!res.ok) throw new Error("Invalid transition.");

      await loadIncidents();
      await loadSummary();
    } catch {
      setIncidents(previous);
      setError("Status could not be updated. The previous value was restored.");
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.container}>
        <h1>TrackFlow Centralized Incident Manager</h1>

        {error && <p className={styles.error}>{error}</p>}
        {success && <p className={styles.success}>{success}</p>}

        <section className={styles.card}>
          <h2>Register incident</h2>

          <form className={styles.form} onSubmit={submitIncident}>
            <label>
              Title
              <input
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
              />
              {fieldError.title && <span>{fieldError.title}</span>}
            </label>

            <label>
              Description
              <textarea
                value={form.description}
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value })
                }
              />
              {fieldError.description && <span>{fieldError.description}</span>}
            </label>

            <label>
              Category
              <select
                value={form.category}
                onChange={(event) =>
                  setForm({ ...form, category: event.target.value })
                }
              >
                {categories.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Origin
              <select
                value={form.origin}
                onChange={(event) => setForm({ ...form, origin: event.target.value })}
              >
                {origins.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <label className={form.origin === "branch" ? styles.highlight : ""}>
              Branch
              <select
                value={form.branch}
                onChange={(event) => setForm({ ...form, branch: event.target.value })}
              >
                {branches.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>

            <button disabled={loading}>
              {loading ? "Saving..." : "Submit incident"}
            </button>
          </form>
        </section>

        <section className={styles.card}>
          <h2>Incident list</h2>

          <div className={styles.filters}>
            <select
              value={filters.status}
              onChange={(event) =>
                setFilters({ ...filters, status: event.target.value })
              }
            >
              <option value="">All statuses</option>
              {statuses.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>

            <select
              value={filters.origin}
              onChange={(event) =>
                setFilters({ ...filters, origin: event.target.value })
              }
            >
              <option value="">All origins</option>
              {origins.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>

            <select
              value={filters.branch}
              onChange={(event) =>
                setFilters({ ...filters, branch: event.target.value })
              }
            >
              <option value="">All branches</option>
              {branches.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {listLoading ? (
            <p>Loading incidents...</p>
          ) : incidents.length === 0 ? (
            <p>No incidents found.</p>
          ) : (
            <div className={styles.list}>
              {incidents.map((incident) => (
                <article key={incident.id} className={styles.incident}>
                  <strong>{incident.title}</strong>
                  <p>{incident.description}</p>
                  <small>
                    {incident.category} · {incident.origin} · {incident.branch}
                  </small>

                  <select
                    value={incident.status}
                    onChange={(event) => void updateStatus(incident, event.target.value)}
                  >
                    {statuses.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className={styles.card}>
          <h2>Summary</h2>

          {summaryLoading ? (
            <p>Loading summary...</p>
          ) : summary ? (
            <pre>{JSON.stringify(summary, null, 2)}</pre>
          ) : (
            <p>Summary is temporarily unavailable.</p>
          )}
        </section>
      </section>
    </main>
  );
}
