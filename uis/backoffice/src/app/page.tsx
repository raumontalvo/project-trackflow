"use client";

import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useState,
} from "react";

import styles from "./page.module.css";

import {
  DepartmentSection,
  TicketResponse,
  getRfpTicket,
  uploadRfp,
} from "../lib/rfpIntakeServices";


const POLL_INTERVAL_MS = 3000;


const DEPARTMENT_NAMES: Record<string, string> = {
  warehouse: "Warehouse Operations",
  lastmile: "Last Mile and Carrier Management",
  reverse: "Reverse Logistics",
};


function formatMetric(
  value: number | null | undefined
): string {
  if (value === null || value === undefined) {
    return "Not available";
  }

  return value.toFixed(2);
}


function DepartmentCard({
  section,
}: {
  section: DepartmentSection;
}) {
  const aspects = section.key_aspects;

  return (
    <article className={styles.departmentCard}>
      <div className={styles.departmentHeader}>
        <div>
          <h3>
            {DEPARTMENT_NAMES[section.department_id] ??
              section.department_id}
          </h3>

          <p className={styles.owner}>
            Owner: {section.owner}
          </p>
        </div>

        <span className={styles.departmentBadge}>
          {section.department_id}
        </span>
      </div>

      {aspects.requested_scope?.length ? (
        <div className={styles.detailSection}>
          <h4>Requested scope</h4>

          <ul>
            {aspects.requested_scope.map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {aspects.known_requirements?.length ? (
        <div className={styles.detailSection}>
          <h4>Known requirements</h4>

          <ul>
            {aspects.known_requirements.map(
              (item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              )
            )}
          </ul>
        </div>
      ) : null}

      {aspects.quantitative_requirements &&
      Object.keys(aspects.quantitative_requirements).length ? (
        <div className={styles.detailSection}>
          <h4>Quantitative requirements</h4>

          <dl className={styles.metricsList}>
            {Object.entries(
              aspects.quantitative_requirements
            ).map(([key, value]) => (
              <div key={key}>
                <dt>{key.replaceAll("_", " ")}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}

      {aspects.open_questions?.length ? (
        <div className={styles.detailSection}>
          <h4>Open questions</h4>

          <ul>
            {aspects.open_questions.map(
              (question, index) => (
                <li key={`${question}-${index}`}>
                  {question}
                </li>
              )
            )}
          </ul>
        </div>
      ) : null}
    </article>
  );
}


export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [ticketId, setTicketId] = useState<string | null>(
    null
  );
  const [ticket, setTicket] =
    useState<TicketResponse | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);


  useEffect(() => {
    if (!ticketId) {
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null =
      null;

    async function pollTicket() {
      try {
        const currentTicket = await getRfpTicket(
          ticketId as string
        );

        if (cancelled) {
          return;
        }

        setTicket(currentTicket);

        if (
          currentTicket.status === "analyzing" &&
          !currentTicket.error_message
        ) {
          timeoutId = setTimeout(
            pollTicket,
            POLL_INTERVAL_MS
          );
        }
      } catch (pollError) {
        if (cancelled) {
          return;
        }

        setError(
          pollError instanceof Error
            ? pollError.message
            : "Unable to refresh ticket status."
        );
      }
    }

    pollTicket();

    return () => {
      cancelled = true;

      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [ticketId]);


  function handleFileChange(
    event: ChangeEvent<HTMLInputElement>
  ) {
    const selectedFile =
      event.target.files?.[0] ?? null;

    setFile(selectedFile);
    setError(null);
  }


  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (!file) {
      setError("Choose a PDF before uploading.");
      return;
    }

    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      setError("RFP intake accepts PDF files only.");
      return;
    }

    setUploading(true);
    setError(null);
    setTicket(null);
    setTicketId(null);

    try {
      const response = await uploadRfp(file);

      setTicketId(response.ticket_id);
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to upload RFP."
      );
    } finally {
      setUploading(false);
    }
  }


  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              TrackFlow Commercial Operations
            </p>

            <h1>RFP Intake</h1>

            <p className={styles.subtitle}>
              Upload a client RFP and TrackFlow will classify it,
              extract key metadata, and route the work to the
              departments Sales needs.
            </p>
          </div>

          <div className={styles.director}>
            <span>Commercial Director</span>
            <strong>Miguel Torres</strong>
          </div>
        </header>

        <section className={styles.uploadCard}>
          <div>
            <h2>New RFP ticket</h2>

            <p>
              PDF files are converted to Markdown before agent
              analysis. Processing continues in the background.
            </p>
          </div>

          <form
            className={styles.uploadForm}
            onSubmit={handleSubmit}
          >
            <label
              className={styles.filePicker}
              htmlFor="rfp-file"
            >
              <span>
                {file ? file.name : "Choose RFP PDF"}
              </span>

              <input
                id="rfp-file"
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleFileChange}
                disabled={uploading}
              />
            </label>

            <button
              className={styles.uploadButton}
              type="submit"
              disabled={!file || uploading}
            >
              {uploading
                ? "Creating ticket..."
                : "Upload & analyze"}
            </button>
          </form>

          {error ? (
            <p className={styles.errorMessage}>
              {error}
            </p>
          ) : null}
        </section>

        {ticketId && !ticket ? (
          <section className={styles.statusCard}>
            <div className={styles.statusRow}>
              <div>
                <p className={styles.statusLabel}>
                  Ticket
                </p>

                <code>{ticketId}</code>
              </div>

              <span
                className={`${styles.statusBadge} ${styles.analyzing}`}
              >
                analyzing
              </span>
            </div>

            <p className={styles.processingText}>
              TrackFlow is converting and analyzing the RFP.
            </p>
          </section>
        ) : null}

        {ticket ? (
          <section className={styles.results}>
            <div className={styles.statusCard}>
              <div className={styles.statusRow}>
                <div>
                  <p className={styles.statusLabel}>
                    Ticket
                  </p>

                  <code>{ticket.ticket_id}</code>
                </div>

                <span
                  className={`${styles.statusBadge} ${
                    styles[ticket.status] ?? ""
                  }`}
                >
                  {ticket.status.replaceAll("_", " ")}
                </span>
              </div>

              {ticket.status === "analyzing" ? (
                <p className={styles.processingText}>
                  Conversion and department analysis are
                  running. This page refreshes automatically.
                </p>
              ) : null}

              {ticket.error_message ? (
                <p className={styles.errorMessage}>
                  Processing error: {ticket.error_message}
                </p>
              ) : null}
            </div>

            {ticket.status === "discarded" ? (
              <section className={styles.discardedCard}>
                <h2>Document discarded</h2>

                <p>
                  This PDF was not classified as a legitimate
                  inbound TrackFlow RFP. No department work was
                  created.
                </p>
              </section>
            ) : null}

            {ticket.status === "intake_complete" &&
            ticket.rfp ? (
              <>
                <section className={styles.metadataCard}>
                  <div className={styles.sectionHeading}>
                    <div>
                      <p className={styles.eyebrow}>
                        Accepted RFP
                      </p>

                      <h2>
                        {ticket.rfp.client_name ??
                          "Unknown client"}
                      </h2>
                    </div>

                    <span className={styles.currencyBadge}>
                      {ticket.rfp.currency ??
                        "Currency unknown"}
                    </span>
                  </div>

                  <dl className={styles.metadataGrid}>
                    <div>
                      <dt>Country</dt>
                      <dd>
                        {ticket.rfp.client_country ??
                          "Not provided"}
                      </dd>
                    </div>

                    <div>
                      <dt>Monthly volume</dt>
                      <dd>
                        {ticket.rfp.monthly_volume !== null
                          ? ticket.rfp.monthly_volume.toLocaleString()
                          : "Not provided"}
                      </dd>
                    </div>

                    <div>
                      <dt>Proposal deadline</dt>
                      <dd>
                        {ticket.rfp.deadline ??
                          "Not provided"}
                      </dd>
                    </div>

                    <div>
                      <dt>Services requested</dt>
                      <dd>
                        {ticket.rfp.services_requested.join(
                          ", "
                        )}
                      </dd>
                    </div>
                  </dl>
                </section>

                <section className={styles.readabilityCard}>
                  <div className={styles.sectionHeading}>
                    <div>
                      <p className={styles.eyebrow}>
                        Processing metrics
                      </p>

                      <h2>Readability</h2>
                    </div>
                  </div>

                  <dl className={styles.readabilityGrid}>
                    <div>
                      <dt>Words</dt>
                      <dd>
                        {ticket.rfp.readability_metrics
                          .word_count ?? "—"}
                      </dd>
                    </div>

                    <div>
                      <dt>Flesch ease</dt>
                      <dd>
                        {formatMetric(
                          ticket.rfp
                            .readability_metrics
                            .flesch_reading_ease
                        )}
                      </dd>
                    </div>

                    <div>
                      <dt>Flesch-Kincaid</dt>
                      <dd>
                        {formatMetric(
                          ticket.rfp
                            .readability_metrics
                            .flesch_kincaid_grade
                        )}
                      </dd>
                    </div>

                    <div>
                      <dt>Gunning Fog</dt>
                      <dd>
                        {formatMetric(
                          ticket.rfp
                            .readability_metrics
                            .gunning_fog
                        )}
                      </dd>
                    </div>
                  </dl>
                </section>

                <section>
                  <div className={styles.sectionHeading}>
                    <div>
                      <p className={styles.eyebrow}>
                        Routed workstreams
                      </p>

                      <h2>Departments involved</h2>
                    </div>
                  </div>

                  <div className={styles.departmentGrid}>
                    {ticket.departments.map((section) => (
                      <DepartmentCard
                        key={section.id}
                        section={section}
                      />
                    ))}
                  </div>
                </section>

                {ticket.summary?.sales_questions?.length ? (
                  <section className={styles.questionsCard}>
                    <p className={styles.eyebrow}>
                      Sales follow-up
                    </p>

                    <h2>Open questions</h2>

                    <p>
                      Clarify these items before proposal
                      generation.
                    </p>

                    <ol>
                      {ticket.summary.sales_questions.map(
                        (question, index) => (
                          <li
                            key={`${question}-${index}`}
                          >
                            {question}
                          </li>
                        )
                      )}
                    </ol>
                  </section>
                ) : null}
              </>
            ) : null}
          </section>
        ) : null}
      </div>
    </main>
  );
}