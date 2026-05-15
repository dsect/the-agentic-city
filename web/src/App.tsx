import { FormEvent, useState } from "react";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type ChatResponse = {
  answer: string;
  model: string;
};

export function App() {
  const [message, setMessage] = useState("What makes a city agentic?");
  const [answer, setAnswer] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage || isLoading) {
      return;
    }

    setIsLoading(true);
    setAnswer(null);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmedMessage }),
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Request failed with ${response.status}`);
      }

      const data = (await response.json()) as ChatResponse;
      setAnswer(data);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unknown API error");
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
          Ask a question and the FastAPI service will route it to a local Ollama model running
          inside Docker Compose.
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
            {isLoading ? "Asking qwen3:8b..." : "Ask local LLM"}
          </button>
        </form>

        {answer ? (
          <article className="answer">
            <h2>Answer from {answer.model}</h2>
            <p>{answer.answer}</p>
          </article>
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
