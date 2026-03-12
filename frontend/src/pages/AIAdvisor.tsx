import { useState } from "react";
import { post } from "../api/client";
import { useDepartment } from "../components/DepartmentContext";
import ErrorBanner from "../components/ErrorBanner";
import type { AskResponse, BriefingResponse } from "../types";

export default function AIAdvisor() {
  const { department } = useDepartment();
  const [briefing, setBriefing] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchBriefing() {
    setLoading(true);
    setError(null);
    try {
      const res = await post<BriefingResponse>("briefing", department ? { department } : {});
      setBriefing(res.briefing);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate briefing");
    } finally {
      setLoading(false);
    }
  }

  async function askQuestion() {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await post<AskResponse>("ask", { question, ...(department ? { department } : {}) });
      setAnswer(res.answer);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to get answer");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-800">AI Advisor</h2>

      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-3 text-sm font-medium text-slate-600">Executive Briefing</h3>
        <button
          onClick={fetchBriefing}
          disabled={loading}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Generating..." : "Generate Briefing"}
        </button>
        {briefing && (
          <div className="mt-4 whitespace-pre-wrap rounded bg-slate-50 p-4 text-sm text-slate-700">
            {briefing}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-3 text-sm font-medium text-slate-600">Ask the Advisor</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && askQuestion()}
            placeholder="Ask a compliance question..."
            className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <button
            onClick={askQuestion}
            disabled={loading || !question.trim()}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Ask
          </button>
        </div>
        {answer && (
          <div className="mt-4 whitespace-pre-wrap rounded bg-slate-50 p-4 text-sm text-slate-700">
            {answer}
          </div>
        )}
      </div>

      {error && <ErrorBanner message={error} />}
    </div>
  );
}
