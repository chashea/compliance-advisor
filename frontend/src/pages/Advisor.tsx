import { useState } from "react";
import { useDepartment } from "../components/DepartmentContext";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { post } from "../api/client";
import type { BriefingResponse, AskResponse } from "../types";

interface QAPair {
  question: string;
  answer: string;
}

export default function Advisor() {
  const { department } = useDepartment();

  const [briefing, setBriefing] = useState<string | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingError, setBriefingError] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [history, setHistory] = useState<QAPair[]>([]);

  async function generateBriefing() {
    setBriefingLoading(true);
    setBriefingError(null);
    try {
      const res = await post<BriefingResponse>("briefing", department ? { department } : {});
      setBriefing(res.briefing);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to generate briefing";
      setBriefingError(msg.includes("429") ? "Rate limit reached. Please wait a moment and try again." : msg);
    } finally {
      setBriefingLoading(false);
    }
  }

  async function askQuestion(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setAskLoading(true);
    setAskError(null);
    try {
      const res = await post<AskResponse>("ask", { question: q, ...(department ? { department } : {}) });
      setHistory((prev) => [...prev, { question: q, answer: res.answer }]);
      setQuestion("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to get answer";
      setAskError(msg.includes("429") ? "Rate limit reached. Please wait a moment and try again." : msg);
    } finally {
      setAskLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold text-slate-800">AI Advisor</h2>

      {/* Executive Briefing */}
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-medium text-slate-700">Executive Briefing</h3>
          <button
            onClick={generateBriefing}
            disabled={briefingLoading}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {briefingLoading ? "Generating..." : "Generate Briefing"}
          </button>
        </div>
        {briefingLoading && <Loading />}
        {briefingError && <ErrorBanner message={briefingError} />}
        {briefing && !briefingLoading && (
          <div className="prose prose-slate max-w-none whitespace-pre-wrap text-sm">{briefing}</div>
        )}
      </section>

      {/* Ask AI */}
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="mb-4 text-lg font-medium text-slate-700">Ask AI</h3>
        <form onSubmit={askQuestion} className="flex gap-3">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your compliance data..."
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={askLoading}
          />
          <button
            type="submit"
            disabled={askLoading || !question.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {askLoading ? "Thinking..." : "Ask"}
          </button>
        </form>
        {askError && <div className="mt-3"><ErrorBanner message={askError} /></div>}
        {askLoading && <Loading />}
        {history.length > 0 && (
          <div className="mt-6 space-y-4">
            {history.map((qa, i) => (
              <div key={i} className="rounded-md border border-slate-100 bg-slate-50 p-4">
                <p className="mb-2 text-sm font-medium text-slate-700">Q: {qa.question}</p>
                <div className="whitespace-pre-wrap text-sm text-slate-600">{qa.answer}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
