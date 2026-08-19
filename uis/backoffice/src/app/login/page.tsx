"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { track } from "@/lib/telemetry";

const API =
  process.env.NEXT_PUBLIC_INVENTORY_API_URL || "http://localhost:8000";

type LoginResponse = {
  access_token: string;
  token_type: string;
  user_uuid: string;
};

type ErrorResponse = {
  detail?: string;
};

type LoginFailureReason =
  | "wrong_credentials"
  | "expired_session"
  | "locked_account";

function getLoginFailureReason(error: unknown): LoginFailureReason {
  if (!(error instanceof Error)) {
    return "wrong_credentials";
  }

  const message = error.message.toLowerCase();

  if (message.includes("locked")) {
    return "locked_account";
  }

  if (
    message.includes("expired") ||
    message.includes("session")
  ) {
    return "expired_session";
  }

  return "wrong_credentials";
}

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [attemptCount, setAttemptCount] = useState(0);

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setLoading(true);
    setError("");

    try {
      const form = new URLSearchParams();
      form.append("username", email);
      form.append("password", password);

      const response = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: form.toString(),
      });

      const data = (await response.json()) as
        | LoginResponse
        | ErrorResponse;

      if (!response.ok) {
        const message =
          "detail" in data && typeof data.detail === "string"
            ? data.detail
            : "Login failed.";

        throw new Error(message);
      }

      if (
        !("access_token" in data) ||
        !("user_uuid" in data) ||
        typeof data.access_token !== "string" ||
        typeof data.user_uuid !== "string"
      ) {
        throw new Error(
          "The login response is missing required fields."
        );
      }

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("user_uuid", data.user_uuid);

      router.push("/backoffice/inventory/products");
    } catch (err) {
      const nextAttemptCount = attemptCount + 1;
      setAttemptCount(nextAttemptCount);

      track("user_login_failed", {
        failure_reason: getLoginFailureReason(err),
        warehouse: "unknown",
        user_role: "unknown",
        attempt_count: nextAttemptCount,
        ip_hash: "unavailable_client_side",
      });

      setError(
        err instanceof Error ? err.message : "Login failed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        maxWidth: 420,
        margin: "80px auto",
        padding: 32,
      }}
    >
      <h1 style={{ marginBottom: 24 }}>
        TrackFlow Login
      </h1>

      {error && (
        <div
          style={{
            background: "#fee2e2",
            color: "#991b1b",
            padding: 12,
            marginBottom: 16,
            borderRadius: 6,
          }}
        >
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        style={{
          display: "grid",
          gap: 16,
        }}
      >
        <input
          type="email"
          placeholder="Email"
          required
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          style={{
            padding: 12,
          }}
        />

        <input
          type="password"
          placeholder="Password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          style={{
            padding: 12,
          }}
        />

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: 12,
            fontWeight: 700,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Signing In..." : "Sign In"}
        </button>
      </form>
    </main>
  );
}