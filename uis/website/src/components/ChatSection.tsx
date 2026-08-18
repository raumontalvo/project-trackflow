"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import styles from "./ChatSection.module.css";

type ConnectionStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

type MessageStatus =
  | "streaming"
  | "completed"
  | "interrupted"
  | "error";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: MessageStatus;
};

type HistoryMessage = {
  message_id: string;
  role: "assistant";
  content: string;
  status: MessageStatus;
};

type ServerEvent = {
  event: string;
  data: {
    session_id?: string;
    agent_id?: string;
    user_id?: string;
    client_id?: string;
    token?: string;
    sequence?: number;
    message_id?: string;
    status?: string;
    error?: string;
    messages?: HistoryMessage[];
  };
};

const RECONNECT_DELAYS = [
  1000,
  2000,
  4000,
  8000,
  10000,
];

function createId(prefix: string): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return `${prefix}_${crypto.randomUUID()}`;
  }

  return `${prefix}_${Date.now()}_${Math.random()
    .toString(36)
    .slice(2)}`;
}

function getStoredIdentity() {
  let sessionId = localStorage.getItem(
    "trackflow_chat_session_id",
  );

  let userId = localStorage.getItem(
    "trackflow_chat_user_id",
  );

  let clientId = localStorage.getItem(
    "trackflow_chat_client_id",
  );

  if (!sessionId) {
    sessionId = createId("chat");
    localStorage.setItem(
      "trackflow_chat_session_id",
      sessionId,
    );
  }

  if (!userId) {
    userId = createId("user");
    localStorage.setItem(
      "trackflow_chat_user_id",
      userId,
    );
  }

  if (!clientId) {
    clientId = createId("client");
    localStorage.setItem(
      "trackflow_chat_client_id",
      clientId,
    );
  }

  return {
    sessionId,
    userId,
    clientId,
  };
}

function getWebSocketBaseUrl(): string {
  const configuredUrl =
    process.env.NEXT_PUBLIC_API_URL?.trim();

  if (configuredUrl) {
    return configuredUrl
      .replace(/^https:/, "wss:")
      .replace(/^http:/, "ws:")
      .replace(/\/$/, "");
  }

  return "ws://127.0.0.1:8000";
}

export default function ChatSection() {
  const [messages, setMessages] = useState<ChatMessage[]>(
    [],
  );

  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState("");

  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");

  const [isGenerating, setIsGenerating] =
    useState(false);

  const socketRef = useRef<WebSocket | null>(null);

  const reconnectAttemptRef = useRef(0);

  const reconnectTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(null);

  const shouldReconnectRef = useRef(true);

  const currentAssistantIdRef =
    useRef<string | null>(null);

  const pendingRedirectRef = useRef(false);

  const updateAssistantMessage = useCallback(
    (
      messageId: string,
      updater: (message: ChatMessage) => ChatMessage,
    ) => {
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId
            ? updater(message)
            : message,
        ),
      );
    },
    [],
  );

  const createAssistantPlaceholder = useCallback(() => {
    const assistantId = createId("assistant");

    currentAssistantIdRef.current = assistantId;

    setMessages((current) => [
      ...current,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        status: "streaming",
      },
    ]);

    return assistantId;
  }, []);

  const handleServerEvent = useCallback(
    (payload: ServerEvent) => {
      switch (payload.event) {
        case "session_connected": {
          setConnectionStatus("connected");
          reconnectAttemptRef.current = 0;
          break;
        }

        case "session_history": {
          const history = payload.data.messages ?? [];

          const restoredMessages: ChatMessage[] =
            history.map((message) => ({
              id: message.message_id,
              role: message.role,
              content: message.content,
              status: message.status,
            }));

          /*
           * The backend is authoritative for persisted assistant
           * history. Preserve local user messages because the
           * current in-memory backend stores assistant messages.
           */
          setMessages((current) => {
            const localUserMessages = current.filter(
              (message) => message.role === "user",
            );

            return [
              ...localUserMessages,
              ...restoredMessages,
            ];
          });

          const activeMessage = [...history]
            .reverse()
            .find(
              (message) =>
                message.status === "streaming",
            );

          if (activeMessage) {
            currentAssistantIdRef.current =
              activeMessage.message_id;

            setIsGenerating(true);
          } else {
            currentAssistantIdRef.current = null;
            setIsGenerating(false);
          }

          break;
        }

        case "token_chunk": {
          let assistantId =
            currentAssistantIdRef.current;

          if (!assistantId) {
            assistantId =
              createAssistantPlaceholder();
          }

          const token = payload.data.token ?? "";

          updateAssistantMessage(
            assistantId,
            (message) => ({
              ...message,
              content: message.content + token,
              status: "streaming",
            }),
          );

          setIsGenerating(true);
          break;
        }

        case "generation_interrupted": {
          const assistantId =
            currentAssistantIdRef.current;

          if (assistantId) {
            updateAssistantMessage(
              assistantId,
              (message) => ({
                ...message,
                status: "interrupted",
              }),
            );
          }

          currentAssistantIdRef.current = null;

          if (pendingRedirectRef.current) {
            pendingRedirectRef.current = false;

            createAssistantPlaceholder();
            setIsGenerating(true);
          } else {
            setIsGenerating(false);
          }

          break;
        }

        case "generation_completed": {
          const assistantId =
            currentAssistantIdRef.current;

          if (assistantId) {
            updateAssistantMessage(
              assistantId,
              (message) => ({
                ...message,
                status: "completed",
              }),
            );
          }

          currentAssistantIdRef.current = null;
          pendingRedirectRef.current = false;
          setIsGenerating(false);
          break;
        }

        case "generation_error":
        case "chat_error": {
          const assistantId =
            currentAssistantIdRef.current;

          if (assistantId) {
            updateAssistantMessage(
              assistantId,
              (message) => ({
                ...message,
                content:
                  message.content ||
                  payload.data.error ||
                  "The support agent could not complete the response.",
                status: "error",
              }),
            );
          }

          currentAssistantIdRef.current = null;
          pendingRedirectRef.current = false;
          setIsGenerating(false);
          break;
        }

        default:
          break;
      }
    },
    [
      createAssistantPlaceholder,
      updateAssistantMessage,
    ],
  );

  useEffect(() => {
    const identity = getStoredIdentity();

    setSessionId(identity.sessionId);

    shouldReconnectRef.current = true;

    const connect = () => {
      if (!shouldReconnectRef.current) {
        return;
      }

      const attempt = reconnectAttemptRef.current;

      setConnectionStatus(
        attempt === 0
          ? "connecting"
          : "reconnecting",
      );

      const baseUrl = getWebSocketBaseUrl();

      const params = new URLSearchParams({
        user_id: identity.userId,
        client_id: identity.clientId,
      });

      const socket = new WebSocket(
        `${baseUrl}/ws/chat/${encodeURIComponent(
          identity.sessionId,
        )}?${params.toString()}`,
      );

      socketRef.current = socket;

      socket.onopen = () => {
        /*
         * session_connected is authoritative. We wait
         * for that event before enabling user input.
         */
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(
            event.data,
          ) as ServerEvent;

          handleServerEvent(payload);
        } catch {
          console.error(
            "TrackFlow received an invalid WebSocket event.",
          );
        }
      };

      socket.onerror = () => {
        socket.close();
      };

      socket.onclose = () => {
        if (socketRef.current === socket) {
          socketRef.current = null;
        }

        if (!shouldReconnectRef.current) {
          setConnectionStatus("disconnected");
          return;
        }

        setConnectionStatus("reconnecting");

        const reconnectIndex = Math.min(
          reconnectAttemptRef.current,
          RECONNECT_DELAYS.length - 1,
        );

        const delay =
          RECONNECT_DELAYS[reconnectIndex];

        reconnectAttemptRef.current += 1;

        reconnectTimerRef.current = setTimeout(
          connect,
          delay,
        );
      };
    };

    connect();

    return () => {
      shouldReconnectRef.current = false;

      if (reconnectTimerRef.current) {
        clearTimeout(
          reconnectTimerRef.current,
        );
      }

      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [handleServerEvent]);

  const sendEvent = (
    event: string,
    data: Record<string, string>,
  ): boolean => {
    const socket = socketRef.current;

    if (
      !socket ||
      socket.readyState !== WebSocket.OPEN
    ) {
      return false;
    }

    socket.send(
      JSON.stringify({
        event,
        data,
      }),
    );

    return true;
  };

  const handleSubmit = (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    const cleanedInput = input.trim();

    if (
      !cleanedInput ||
      !sessionId ||
      connectionStatus !== "connected"
    ) {
      return;
    }

    const userMessage: ChatMessage = {
      id: createId("user_message"),
      role: "user",
      content: cleanedInput,
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);

    if (isGenerating) {
      pendingRedirectRef.current = true;

      const sent = sendEvent(
        "interrupt_requested",
        {
          session_id: sessionId,
          new_input: cleanedInput,
        },
      );

      if (!sent) {
        pendingRedirectRef.current = false;
      }
    } else {
      createAssistantPlaceholder();
      setIsGenerating(true);

      const sent = sendEvent(
        "user_message",
        {
          session_id: sessionId,
          input: cleanedInput,
        },
      );

      if (!sent) {
        setIsGenerating(false);
      }
    }

    setInput("");
  };

  const statusText = {
    connecting: "Connecting…",
    connected: "Connected",
    reconnecting: "Reconnecting…",
    disconnected: "Disconnected",
  }[connectionStatus];

  return (
    <section className={styles.section}>
      <div className={styles.container}>
        <div className={styles.heading}>
          <p className={styles.eyebrow}>
            TrackFlow Support
          </p>

          <h2>
            Chat with our first-line CX agent
          </h2>

          <p>
            Ask about tracking, returns, or common
            delivery questions. Responses arrive as
            they are generated, and you can redirect
            the conversation at any time.
          </p>
        </div>

        <div className={styles.chat}>
          <div className={styles.chatHeader}>
            <div>
              <strong>TrackFlow Assistant</strong>

              <span>
                First-line customer experience
              </span>
            </div>

            <div
              className={`${styles.status} ${
                styles[connectionStatus]
              }`}
            >
              <span
                className={styles.statusDot}
              />

              {statusText}
            </div>
          </div>

          <div className={styles.messages}>
            {messages.length === 0 ? (
              <div className={styles.emptyState}>
                <strong>
                  How can we help?
                </strong>

                <p>
                  Try asking “What is the return
                  policy?” or “What is the status of
                  ticket 482?”
                </p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`${styles.messageRow} ${
                    message.role === "user"
                      ? styles.userRow
                      : styles.assistantRow
                  }`}
                >
                  <div
                    className={`${styles.message} ${
                      message.role === "user"
                        ? styles.userMessage
                        : styles.assistantMessage
                    }`}
                  >
                    {message.content ||
                      (message.status === "streaming"
                        ? "…"
                        : "")}

                    {message.status ===
                      "interrupted" && (
                      <span
                        className={
                          styles.interruptedLabel
                        }
                      >
                        Interrupted
                      </span>
                    )}

                    {message.status === "error" && (
                      <span
                        className={
                          styles.errorLabel
                        }
                      >
                        Error
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          <form
            className={styles.form}
            onSubmit={handleSubmit}
          >
            <textarea
              className={styles.input}
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              placeholder={
                isGenerating
                  ? "Type a new message to interrupt and redirect…"
                  : "Ask TrackFlow support…"
              }
              rows={3}
              disabled={
                connectionStatus !== "connected"
              }
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey
                ) {
                  event.preventDefault();

                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />

            <div className={styles.formFooter}>
              <span>
                {isGenerating
                  ? "Sending now will interrupt the current response."
                  : "Press Enter to send · Shift + Enter for a new line"}
              </span>

              <button
                type="submit"
                className={styles.sendButton}
                disabled={
                  !input.trim() ||
                  connectionStatus !== "connected"
                }
              >
                {isGenerating
                  ? "Interrupt & redirect"
                  : "Send"}
              </button>
            </div>
          </form>
        </div>

        {sessionId && (
          <p className={styles.session}>
            Session: {sessionId}
          </p>
        )}
      </div>
    </section>
  );
}