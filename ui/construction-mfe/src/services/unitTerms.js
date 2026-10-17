import { requestJson } from "./constructionApi.js";

export function unitTermRequest(bridge, unitId, kind, path, body) {
  return requestJson({ bridge,
    baseUrl: bridge?.erpApiBaseUrl || import.meta.env.VITE_ERP_API_URL || "http://127.0.0.1:8000",
    path: `/v1/unit-terms/${unitId}/${kind}${path}`, method: body ? "POST" : "GET", body });
}
