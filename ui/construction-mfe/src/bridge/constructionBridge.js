export function resolveConstructionBridge() {
  return window.__NASCORP_CONSTRUCTION_BRIDGE__ ?? createStandaloneBridge()
}

function createStandaloneBridge() {
  const constructionApiBaseUrl = import.meta.env.VITE_CONSTRUCTION_API_URL || "http://127.0.0.1:8010"
  const token = window.localStorage?.getItem("construction:token") ?? null
  const companyId = window.localStorage?.getItem("construction:companyId") ?? null
  const theme = document.documentElement.getAttribute("data-theme") || "light"

  return {
    version: "standalone",
    token,
    constructionApiBaseUrl,
    companyContext: {
      companyId,
      companyName: "",
      companyDocument: "",
    },
    user: {
      id: null,
      personId: null,
      name: "",
      email: "",
    },
    theme,
    getAuthHeaders: () => ({
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(companyId ? { "X-Company-ID": companyId } : {}),
    }),
    navigate: (path) => {
      window.location.assign(path)
    },
    feedback: {
      success: () => {},
      error: () => {},
      warning: () => {},
    },
  }
}