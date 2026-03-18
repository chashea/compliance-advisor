import { useCallback, useEffect, useState } from "react";
import { post } from "../api/client";
import { useDemo } from "../components/DemoContext";

interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(
  endpoint: string,
  body?: Record<string, unknown>,
  deps: unknown[] = [],
): ApiState<T> {
  const { demo } = useDemo();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch_ = useCallback(() => {
    setLoading(true);
    setError(null);
    post<T>(endpoint, body, demo)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, JSON.stringify(body), demo, ...deps]);

  useEffect(() => {
    fetch_();
  }, [fetch_]);

  return { data, loading, error, refetch: fetch_ };
}
