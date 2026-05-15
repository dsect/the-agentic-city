import { FormEvent, useState } from "react";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type ChatResponse = {
  answer: string;
  model: string;
  used_tools: boolean;
  tool_names: string[];
  status: string;
  trace: ToolTraceEvent[];
};

type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
  model?: string;
  usedTools?: boolean;
  toolNames?: string[];
  status?: string;
  trace?: ToolTraceEvent[];
};

type ToolTraceEvent = {
  type: string;
  name?: string | null;
  payload: Record<string, unknown>;
};

export function App() {
  const [message, setMessage] = useState(
    "What is the weather in Seattle, New York City, Los Angeles, and Chicago?",
  );
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage || isLoading) {
      return;
    }

    setIsLoading(true);
    setError(null);
    const history = conversation.map((turn) => ({ role: turn.role, content: turn.content }));
    const userTurn: ConversationMessage = { role: "user", content: trimmedMessage };
    setConversation((currentConversation) => [...currentConversation, userTurn]);
    setMessage("");

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmedMessage, history }),
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Request failed with ${response.status}`);
      }

      const data = (await response.json()) as ChatResponse;
      setConversation((currentConversation) => [
        ...currentConversation,
        {
          role: "assistant",
          content: data.answer,
          model: data.model,
          usedTools: data.used_tools,
          toolNames: data.tool_names,
          status: data.status,
          trace: data.trace,
        },
      ]);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unknown API error");
      setMessage(trimmedMessage);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="shell">
      <section className="panel">
        <p className="eyebrow">Local LLM Workbench</p>
        <h1>The Agentic City</h1>
        <p className="intro">
          Ask a question and the FastAPI service will route it to a local Ollama model with a
          fake weather tool available for model-selected tool calls.
        </p>

        <form className="chat-form" onSubmit={submitQuestion}>
          <label htmlFor="message">Question</label>
          <textarea
            id="message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask the local model something..."
          />
          <button type="submit" disabled={isLoading || !message.trim()}>
            {isLoading ? "Running..." : "Ask with tools"}
          </button>
        </form>

        {conversation.length > 0 || isLoading ? (
          <section className="results" aria-live="polite">
            <div className="status-row">
              <span className={isLoading ? "status-pill active" : "status-pill"}>Thinking</span>
              <span className="status-pill">
                {latestAssistantTurn(conversation)?.usedTools ? "Tool call observed" : "No tool call yet"}
              </span>
            </div>

            <ol className="transcript">
              {conversation.map((turn, index) => (
                <li className={turn.role === "assistant" ? "turn assistant-turn" : "turn user-turn"} key={index}>
                  <div className="turn-heading">
                    <span>{turn.role === "assistant" ? `Assistant${turn.model ? ` · ${turn.model}` : ""}` : "You"}</span>
                    {turn.status ? <code>{formatTraceType(turn.status)}</code> : null}
                    {turn.toolNames?.map((toolName) => (
                      <code key={toolName}>{toolName}</code>
                    ))}
                  </div>
                  <p>{turn.content}</p>

                  {turn.trace?.length ? (
                    <details className="trace">
                      <summary>Evidence trace</summary>
                      <ol>
                        {turn.trace.map((event, traceIndex) => (
                          <li key={`${event.type}-${traceIndex}`}>
                            <div className="trace-heading">
                              <span>{formatTraceType(event.type)}</span>
                              {event.name ? <code>{event.name}</code> : null}
                            </div>
                            <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                          </li>
                        ))}
                      </ol>
                    </details>
                  ) : null}
                </li>
              ))}
              {isLoading ? (
                <li className="turn assistant-turn pending-turn">
                  <div className="turn-heading">
                    <span>Assistant</span>
                    <code>Thinking</code>
                  </div>
                  <p>Waiting for the model response and any tool-call evidence.</p>
                </li>
              ) : null}
            </ol>
          </section>
        ) : null}

        {error ? (
          <article className="error">
            <h2>Request failed</h2>
            <p>{error}</p>
          </article>
        ) : null}
      </section>
    </main>
  );
}

function latestAssistantTurn(conversation: ConversationMessage[]) {
  for (let index = conversation.length - 1; index >= 0; index -= 1) {
    if (conversation[index].role === "assistant") {
      return conversation[index];
    }
  }
  return undefined;
}

function formatTraceType(type: string) {
  return type
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
