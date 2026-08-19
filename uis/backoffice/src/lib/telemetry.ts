"use client";

const TELEMETRY_ENDPOINT =
  process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT ||
  "http://localhost:8000/telemetry/events";

const SCHEMA_VERSION = "1.0.0";
const MAX_BATCH_SIZE = 20;
const FLUSH_INTERVAL_MS = 10_000;
const MAX_ATTEMPTS = 3;

export type TelemetryEventType =
  | "receiving_order_created"
  | "dispatch_order_created"
  | "dispatch_order_failed"
  | "stock_threshold_triggered"
  | "direct_stock_edit_rejected"
  | "user_login_failed"
  | "dispatch_form_abandoned";

export type TelemetryProperties = Record<string, unknown>;

export type TelemetryEvent = {
  eventId: string;
  timestamp: string;
  sessionId: string;
  userId: string;
  event_type: TelemetryEventType;
  schemaVersion: string;
  requestId: string;
  properties: TelemetryProperties;
};

type QueuedTelemetryEvent = Omit<TelemetryEvent, "requestId">;

let queue: QueuedTelemetryEvent[] = [];
let flushTimer: number | null = null;
let listenersRegistered = false;
let flushInProgress = false;

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function getUserId(): string | null {
  if (!isBrowser()) {
    return null;
  }

  return localStorage.getItem("user_uuid");
}

function getSessionId(): string {
  if (!isBrowser()) {
    return "server";
  }

  const storageKey = "telemetry_session_id";
  const existingSessionId = sessionStorage.getItem(storageKey);

  if (existingSessionId) {
    return existingSessionId;
  }

  const sessionId = crypto.randomUUID();
  sessionStorage.setItem(storageKey, sessionId);

  return sessionId;
}

function createEvent(
  eventType: TelemetryEventType,
  properties: TelemetryProperties
): QueuedTelemetryEvent | null {
  const sessionId = getSessionId();

  // Login failures occur before authentication succeeds, so there may be
  // no user_uuid yet. For that event only, use the anonymous session ID.
  const userId =
    getUserId() ?? (eventType === "user_login_failed" ? sessionId : null);

  if (!userId) {
    console.warn(
      "Telemetry event skipped because user_uuid is not available.",
      eventType
    );
    return null;
  }

  return {
    eventId: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    sessionId,
    userId,
    event_type: eventType,
    schemaVersion: SCHEMA_VERSION,
    properties,
  };
}

function attachRequestId(events: QueuedTelemetryEvent[]): TelemetryEvent[] {
  const requestId = crypto.randomUUID();

  return events.map((event) => ({
    ...event,
    requestId,
  }));
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

async function sendBatch(
  batch: TelemetryEvent[],
  attempt = 1
): Promise<void> {
  try {
    const response = await fetch(TELEMETRY_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ events: batch }),
      keepalive: true,
    });

    if (!response.ok) {
      throw new Error(
        `Telemetry endpoint returned status ${response.status}`
      );
    }
  } catch (error) {
    if (attempt >= MAX_ATTEMPTS) {
      console.warn(
        "Telemetry batch discarded after maximum retry attempts.",
        error
      );
      return;
    }

    const backoffMs = 1_000 * 2 ** (attempt - 1);

    await delay(backoffMs);
    await sendBatch(batch, attempt + 1);
  }
}

export async function flush(): Promise<void> {
  if (!isBrowser() || flushInProgress || queue.length === 0) {
    return;
  }

  flushInProgress = true;

  const pendingEvents = queue;
  queue = [];

  const batch = attachRequestId(pendingEvents);

  try {
    await sendBatch(batch);
  } finally {
    flushInProgress = false;

    if (queue.length >= MAX_BATCH_SIZE) {
      void flush();
    }
  }
}

function flushWithBeacon(): void {
  if (!isBrowser() || queue.length === 0) {
    return;
  }

  const pendingEvents = queue;
  queue = [];

  const batch = attachRequestId(pendingEvents);
  const payload = JSON.stringify({ events: batch });

  const blob = new Blob([payload], {
    type: "application/json",
  });

  const accepted = navigator.sendBeacon(TELEMETRY_ENDPOINT, blob);

  if (!accepted) {
    queue = pendingEvents.concat(queue);
  }
}

function registerLifecycleListeners(): void {
  if (!isBrowser() || listenersRegistered) {
    return;
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      flushWithBeacon();
    }
  });

  window.addEventListener("pagehide", () => {
    flushWithBeacon();
  });

  listenersRegistered = true;
}

export function startTelemetryService(): void {
  if (!isBrowser()) {
    return;
  }

  registerLifecycleListeners();

  if (flushTimer !== null) {
    return;
  }

  flushTimer = window.setInterval(() => {
    void flush();
  }, FLUSH_INTERVAL_MS);
}

export function stopTelemetryService(): void {
  if (!isBrowser() || flushTimer === null) {
    return;
  }

  window.clearInterval(flushTimer);
  flushTimer = null;
}

export function track(
  eventType: TelemetryEventType,
  properties: TelemetryProperties = {}
): void {
  if (!isBrowser()) {
    return;
  }

  startTelemetryService();

  const event = createEvent(eventType, properties);

  if (!event) {
    return;
  }

  queue.push(event);

  if (queue.length >= MAX_BATCH_SIZE) {
    void flush();
  }
}