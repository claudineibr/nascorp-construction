import { requestJson } from "./constructionApi.js";

const baseUrl = (bridge) => bridge?.erpApiBaseUrl || import.meta.env.VITE_ERP_API_URL || "http://127.0.0.1:8000";

export function unitContractRequest(bridge, path, body) {
  return requestJson({ bridge, baseUrl: baseUrl(bridge), path: `/v1/unit-contracts${path}`,
    method: body ? "POST" : "GET", body });
}

export async function downloadUnitContract(bridge, unitId, versionId, kind) {
  const headers = bridge?.getAuthHeaders?.() ?? {};
  const url = `${baseUrl(bridge)}/v1/unit-contracts/${unitId}/versions/${versionId}/${kind}`;
  let response = await fetch(url, { headers });
  if (response.status === 401 && bridge?.refreshToken) {
    const renewed = await bridge.refreshToken();
    response = await fetch(url, { headers: { ...headers, Authorization: `Bearer ${renewed?.token}` } });
  }
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Não foi possível baixar esta versão.");
  }
  return response.blob();
}
