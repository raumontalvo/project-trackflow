export interface RfpTicketCreatedNotification {
  ticket_id: string;
  rfp_id: string;
  client_name: string | null;
  client_country: string | null;
  services_requested: string[];
  status: "analyzing";
  created_at: string;
}

export interface NotificationHandlers {
  onRfpTicketCreated: (
    notification: RfpTicketCreatedNotification
  ) => void;
  onConnectionChange?: (
    state: "connected" | "reconnecting" | "disconnected"
  ) => void;
}

const STREAM_URL = "/api/notifications/stream";
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;

function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem("access_token");
}

function parseEventBlock(
  block: string
): {
  id: string | null;
  event: string | null;
  data: string | null;
} {
  let id: string | null = null;
  let event: string | null = null;
  const dataLines: string[] = [];

  for (const line of block.split("\n")) {
    if (line.startsWith(":")) {
      continue;
    }

    if (line.startsWith("id:")) {
      id = line.slice(3).trim();
    } else if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  return {
    id,
    event,
    data: dataLines.length ? dataLines.join("\n") : null,
  };
}

export function connectNotificationStream(
  handlers: NotificationHandlers
): () => void {
  let stopped = false;
  let controller: AbortController | null = null;
  let reconnectDelay = INITIAL_RECONNECT_DELAY_MS;
  let lastEventId: string | null = null;

  const seenTicketIds = new Set<string>();

  async function connect(): Promise<void> {
    if (stopped) {
      return;
    }

    controller = new AbortController();

    const headers = new Headers({
      Accept: "text/event-stream",
    });

    const token = getAccessToken();

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    if (lastEventId) {
      headers.set("Last-Event-ID", lastEventId);
    }

    try {
      const response = await fetch(STREAM_URL, {
        method: "GET",
        headers,
        cache: "no-store",
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(
          `Notification stream returned ${response.status}.`
        );
      }

      if (!response.body) {
        throw new Error(
          "Notification stream did not provide a response body."
        );
      }

      handlers.onConnectionChange?.("connected");
      reconnectDelay = INITIAL_RECONNECT_DELAY_MS;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let buffer = "";

      while (!stopped) {
        const { value, done } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, {
          stream: true,
        });

        buffer = buffer.replaceAll("\r\n", "\n");

        let boundary = buffer.indexOf("\n\n");

        while (boundary !== -1) {
          const block = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);

          const parsed = parseEventBlock(block);

          if (parsed.id) {
            lastEventId = parsed.id;
          }

          if (
            parsed.event === "rfp_ticket_created" &&
            parsed.data
          ) {
            const notification =
              JSON.parse(
                parsed.data
              ) as RfpTicketCreatedNotification;

            if (!seenTicketIds.has(notification.ticket_id)) {
              seenTicketIds.add(notification.ticket_id);

              handlers.onRfpTicketCreated(notification);
            }
          }

          boundary = buffer.indexOf("\n\n");
        }
      }

      if (!stopped) {
        throw new Error("Notification stream disconnected.");
      }
    } catch (error) {
      if (stopped) {
        return;
      }

      if (
        error instanceof DOMException &&
        error.name === "AbortError"
      ) {
        return;
      }

      handlers.onConnectionChange?.("reconnecting");

      await new Promise((resolve) =>
        window.setTimeout(resolve, reconnectDelay)
      );

      reconnectDelay = Math.min(
        reconnectDelay * 2,
        MAX_RECONNECT_DELAY_MS
      );

      await connect();
    }
  }

  void connect();

  return () => {
    stopped = true;
    controller?.abort();
    handlers.onConnectionChange?.("disconnected");
  };
}
