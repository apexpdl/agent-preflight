import ActionForm from "./components/ActionForm";
import { useSimulate } from "./hooks/useSimulate";
import type { SimulateResponse } from "./types";

function decisionColor(decision: string): string {
  switch (decision.toUpperCase()) {
    case "ALLOW":
      return "text-allow";
    case "WARN":
      return "text-warn";
    case "BLOCK":
      return "text-block";
    default:
      return "text-secondary";
  }
}

function decisionBg(decision: string): string {
  switch (decision.toUpperCase()) {
    case "ALLOW":
      return "bg-allow";
    case "WARN":
      return "bg-warn";
    case "BLOCK":
      return "bg-block";
    default:
      return "bg-card";
  }
}

function RiskBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.7 ? "var(--block)" : score >= 0.4 ? "var(--warn)" : "var(--allow)";
  return (
    <div className="w-full bg-primary rounded-full h-2.5 mt-1">
      <div
        className="h-2.5 rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

function ResultPanel({ result }: { result: SimulateResponse }) {
  return (
    <div className="bg-card rounded-xl border border-theme p-6 fade-in">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-primary">Result</h2>
        <span
          className={`${decisionBg(result.decision)} text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider`}
        >
          {result.decision}
        </span>
      </div>

      <p className="text-secondary text-sm mb-4">{result.human_summary}</p>

      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-secondary uppercase tracking-wider font-medium">
              Risk Score
            </span>
            <span className={decisionColor(result.decision)}>
              {(result.risk_score * 100).toFixed(0)}%
            </span>
          </div>
          <RiskBar score={result.risk_score} />
        </div>

        {result.risk_factors.length > 0 && (
          <div>
            <p className="text-secondary text-xs mb-2 uppercase tracking-wider font-medium">
              Risk Factors
            </p>
            <div className="flex flex-wrap gap-1.5">
              {result.risk_factors.map((f, i) => (
                <span
                  key={i}
                  className="bg-primary text-secondary text-xs px-2 py-0.5 rounded border border-theme"
                >
                  {f}
                </span>
              ))}
            </div>
          </div>
        )}

        {result.passport && (
          <div>
            <p className="text-secondary text-xs mb-2 uppercase tracking-wider font-medium">
              Passport
            </p>
            <div className="bg-primary rounded-lg border border-theme p-3 font-mono text-xs text-secondary overflow-x-auto">
              <pre className="whitespace-pre-wrap">
                {JSON.stringify(result.passport, null, 2)}
              </pre>
            </div>
          </div>
        )}

        <div className="text-xs text-secondary">
          Pipeline: {result.pipeline_ms?.toFixed(1) ?? "—"}ms
        </div>
      </div>
    </div>
  );
}

function HistoryPanel({
  history,
}: {
  history: Array<{ action_id?: string; actor: string; action_type?: string; action?: string; resource: string; decision: string; risk_score: number; timestamp?: number }>;
}) {
  if (history.length === 0) return null;
  return (
    <div className="bg-card rounded-xl border border-theme p-6">
      <h2 className="text-lg font-semibold text-primary mb-4">
        Recent Activity
      </h2>
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {[...history].reverse().map((entry, i) => (
          <div
            key={entry.action_id ?? i}
            className="flex items-center justify-between bg-primary rounded-lg px-3 py-2 border border-theme text-sm"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span
                className={`${decisionBg(entry.decision)} w-2 h-2 rounded-full shrink-0`}
              />
              <span className="text-primary truncate">
                {entry.actor}
              </span>
              <span className="text-secondary text-xs">
                {entry.action_type ?? entry.action}
              </span>
            </div>
            <span className={`${decisionColor(entry.decision)} text-xs font-medium shrink-0 ml-2`}>
              {entry.decision.toUpperCase()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const { simulate, result, loading, error, history } = useSimulate();

  return (
    <div className="gradient-bg min-h-screen">
      <header className="border-b border-theme px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-card border border-theme flex items-center justify-center text-sm font-bold text-primary">
              P
            </div>
            <div>
              <h1 className="text-base font-semibold text-primary leading-tight">
                Preflight
              </h1>
              <p className="text-xs text-secondary">
                Agent Action Governance
              </p>
            </div>
          </div>
          <span className="text-xs text-secondary font-mono">demo</span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-6">
            <ActionForm onSubmit={simulate} loading={loading} />
            {error && (
              <div className="bg-card border border-theme rounded-xl p-4 text-block text-sm fade-in">
                {error}
              </div>
            )}
          </div>
          <div className="space-y-6">
            {result && <ResultPanel result={result} />}
            <HistoryPanel history={history as any} />
          </div>
        </div>
      </main>
    </div>
  );
}
