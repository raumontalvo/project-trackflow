"use client";

import { FormEvent, useState } from "react";
import styles from "./page.module.css";

type KnowledgeResponse = {
  answer: string;
};

const API_URL =
  process.env.NEXT_PUBLIC_TRACKFLOW_API_URL ?? "http://localhost:8000";

export default function KnowledgePage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const cleanedQuestion = question.trim();

    if (!cleanedQuestion) {
      setError("Enter a question before submitting.");
      return;
    }

    setIsLoading(true);
    setError("");
    setAnswer("");

    try {
      const response = await fetch(`${API_URL}/knowledge/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: cleanedQuestion,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}.`);
      }

      const data = (await response.json()) as KnowledgeResponse;
      setAnswer(data.answer);
    } catch (requestError) {
      console.error(requestError);
      setError(
        "The TrackFlow knowledge assistant is unavailable. Confirm that the API and Qdrant are running."
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.container}>
        <header className={styles.header}>
          <p className={styles.eyebrow}>TrackFlow Commercial Assistant</p>

          <h1 className={styles.title}>Ask the TrackFlow knowledge base</h1>

          <p className={styles.description}>
            Ask about delivery SLAs, returns, carrier coverage, or storage
            pricing. Answers are generated from approved TrackFlow source
            documents.
          </p>
        </header>

        <form className={styles.card} onSubmit={handleSubmit}>
          <label className={styles.label} htmlFor="question">
            Sales question
          </label>

          <textarea
            id="question"
            className={styles.textarea}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Example: Can we guarantee delivery times during Black Friday?"
            rows={5}
            maxLength={1000}
          />

          <div className={styles.actions}>
            <span className={styles.counter}>{question.length}/1000</span>

            <button
              className={styles.button}
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? "Generating answer..." : "Ask TrackFlow"}
            </button>
          </div>
        </form>

        {error && (
          <section className={styles.error} role="alert">
            {error}
          </section>
        )}

        {answer && (
          <section className={styles.answerCard}>
            <h2 className={styles.answerTitle}>Generated answer</h2>
            <p className={styles.answer}>{answer}</p>
          </section>
        )}
      </section>
    </main>
  );
}
