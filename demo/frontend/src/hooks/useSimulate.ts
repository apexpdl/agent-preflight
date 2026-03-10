import { useState, useEffect, useCallback } from "react";
import api from "../utils/api";
import type { SimulateRequest, SimulateResponse, HistoryEntry } from "../types";

export function useSimulate() {
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await api.get<HistoryEntry[]>("/history");
      setHistory(res.data);
    } catch {
      // History endpoint may not be available yet
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const simulate = useCallback(
    async (request: SimulateRequest) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.post<SimulateResponse>("/simulate", request);
        setResult(res.data);
        await fetchHistory();
        return res.data;
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Simulation failed";
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [fetchHistory]
  );

  return { simulate, result, loading, error, history };
}
