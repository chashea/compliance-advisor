import { useState } from "react";
import { useDepartment } from "../components/DepartmentContext";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { post } from "../api/client";
import type { BriefingResponse } from "../types";

export default function Advisor() {
  const { department } = useDepartment();

  const [briefing, setBriefing] = useState<string | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingError, setBriefingError] = useState<string | null>(null);

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

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold text-slate-800">Executive Briefing</h2>

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
    </div>
  );
}
