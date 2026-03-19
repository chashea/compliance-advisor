import { useState } from "react";
import { useDepartment } from "./DepartmentContext";
import { useDemo } from "./DemoContext";
import ErrorBanner from "./ErrorBanner";
import Loading from "./Loading";
import { post } from "../api/client";
import type { AskResponse, BriefingResponse } from "../types";

function stripMarkdown(text: string): string {
  return text
    .replace(/^#{1,6}\s+/gm, "")        // headings
    .replace(/\*\*(.+?)\*\*/g, "$1")     // bold
    .replace(/\*(.+?)\*/g, "$1")         // italic
    .replace(/__(.+?)__/g, "$1")         // bold alt
    .replace(/_(.+?)_/g, "$1")           // italic alt
    .replace(/`(.+?)`/g, "$1")           // inline code
    .replace(/^\s*[-*]\s+/gm, "- ")      // normalize list markers
    .replace(/^\s*\d+\.\s+/gm, (m) => m.trimStart()); // normalize numbered lists
}

function handleError(err: unknown): string {
  const msg = err instanceof Error ? err.message : "Request failed";
  return msg.includes("429") ? "Rate limit reached. Please wait a moment and try again." : msg;
}

export function BriefingDrawer({ onClose }: { onClose: () => void }) {
  const { department } = useDepartment();
  const { demo } = useDemo();
  const [briefing, setBriefing] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const res = await post<BriefingResponse>("briefing", department ? { department } : {}, demo);
      setBriefing(res.briefing);
    } catch (e) {
      setError(handleError(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <DrawerShell title="Executive Briefing" onClose={onClose}>
      <button
        onClick={generate}
        disabled={loading}
        className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? "Generating..." : briefing ? "Regenerate Briefing" : "Generate Briefing"}
      </button>
      {loading && <Loading />}
      {error && <ErrorBanner message={error} />}
      {briefing && !loading && (
        <div className="whitespace-pre-wrap text-sm text-slate-700">{stripMarkdown(briefing)}</div>
      )}
    </DrawerShell>
  );
}

const SUGGESTED_PROMPTS = [
  "What are our top compliance risks right now?",
  "Summarize our DLP alert trends",
  "Which sensitivity labels have the lowest adoption?",
  "Are there any open eDiscovery cases that need attention?",
  "How is our Secure Score trending over time?",
  "What improvement actions should we prioritize?",
];

export function AskDrawer({ onClose }: { onClose: () => void }) {
  const { department } = useDepartment();
  const { demo } = useDemo();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(q?: string) {
    const text = q ?? question;
    if (!text.trim()) return;
    if (q) setQuestion(q);
    setLoading(true);
    setError(null);
    try {
      const res = await post<AskResponse>("ask", { question: text, ...(department ? { department } : {}) }, demo);
      setAnswer(res.answer);
    } catch (e) {
      setError(handleError(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <DrawerShell title="Ask AI" onClose={onClose}>
      <div className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && ask()}
          placeholder="Ask about your compliance posture..."
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <button
          onClick={() => ask()}
          disabled={loading || !question.trim()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "..." : "Ask"}
        </button>
      </div>
      {!answer && !loading && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-slate-500">Suggested questions</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                onClick={() => ask(prompt)}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}
      {loading && <Loading />}
      {error && <ErrorBanner message={error} />}
      {answer && !loading && (
        <div className="whitespace-pre-wrap text-sm text-slate-700">{stripMarkdown(answer)}</div>
      )}
    </DrawerShell>
  );
}

function DrawerShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {children}
        </div>
      </div>
    </>
  );
}
