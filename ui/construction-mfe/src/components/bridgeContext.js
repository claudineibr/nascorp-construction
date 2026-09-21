import { createContext, useContext } from "react"

// O bridge (token, empresa, tema, URLs) vive no topo do MFE e era passado de mao
// em mao ate quem precisasse. Os campos de pessoa mudaram isso: eles aparecem em
// seis modais diferentes e passaram a falar com o servidor por conta propria --
// arrastar a prop por seis assinaturas so para chegar la seria ruido em cada
// uma delas.
//
// Continua valendo passar `bridge` por prop onde ele ja e passado: o contexto e
// o padrao, nao a obrigacao.
const BridgeContext = createContext(null)

export const BridgeProvider = BridgeContext.Provider

export function useBridge(bridgeFromProps = null) {
  const fromContext = useContext(BridgeContext)
  return bridgeFromProps ?? fromContext
}
