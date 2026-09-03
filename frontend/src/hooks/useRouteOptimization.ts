import { useState, useCallback } from 'react';
import { routeApi } from '@/services/api';
import type { RouteRequest, RouteOptimizationResponse } from '@/types';

interface UseRouteOptimizationReturn {
  data: RouteOptimizationResponse | null;
  loading: boolean;
  error: string | null;
  optimize: (request: RouteRequest) => Promise<void>;
  reset: () => void;
}

export function useRouteOptimization(): UseRouteOptimizationReturn {
  const [data, setData] = useState<RouteOptimizationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const optimize = useCallback(async (request: RouteRequest) => {
    setLoading(true);
    setError(null);
    try {
      const response = await routeApi.optimizeRoutes(request);
      setData(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to optimize routes';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return { data, loading, error, optimize, reset };
}
