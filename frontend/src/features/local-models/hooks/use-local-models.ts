import { useQuery } from "@tanstack/react-query";

import {
  getLocalModelMetrics,
  getLocalModels,
  getLocalModelStatus,
} from "@/features/local-models/api";

export function useLocalModels() {
  const statusQuery = useQuery({
    queryKey: ["local-models", "status"],
    queryFn: () => getLocalModelStatus(),
    refetchInterval: 15_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });

  const modelsQuery = useQuery({
    queryKey: ["local-models", "models"],
    queryFn: () => getLocalModels(),
    refetchInterval: 20_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });

  const metricsQuery = useQuery({
    queryKey: ["local-models", "metrics"],
    queryFn: () => getLocalModelMetrics(),
    refetchInterval: 10_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });

  return {
    statusQuery,
    modelsQuery,
    metricsQuery,
  };
}
