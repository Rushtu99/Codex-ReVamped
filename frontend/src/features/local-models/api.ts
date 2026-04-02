import { get } from "@/lib/api-client";

import {
  LocalModelListSchema,
  LocalModelMetricsSchema,
  LocalModelStatusSchema,
} from "@/features/local-models/schemas";

const LOCAL_MODELS_PATH = "/api/local-models";

export function getLocalModelStatus() {
  return get(`${LOCAL_MODELS_PATH}/status`, LocalModelStatusSchema);
}

export function getLocalModels() {
  return get(`${LOCAL_MODELS_PATH}/models`, LocalModelListSchema);
}

export function getLocalModelMetrics() {
  return get(`${LOCAL_MODELS_PATH}/metrics`, LocalModelMetricsSchema);
}
