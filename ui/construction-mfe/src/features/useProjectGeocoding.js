import { useEffect, useRef } from "react"
import { fetchProjectCoordinates } from "../services/constructionApi.js"

const text = (value) => String(value ?? "").trim()

function geocodingAddress(form) {
  const number = text(form.addressNumber)
  const withoutNumber = !/[\p{L}\p{N}]/u.test(number) || /^(?:s\s*[./-]?\s*n\.?|sem n[úu]mero)$/i.test(number)
  const zipCode = text(form.addressZipCode).replace(/\D/g, "")
  const address = {
    street: text(form.addressStreet),
    number: withoutNumber ? null : number,
    district: text(form.addressDistrict) || null,
    city: text(form.addressCity),
    state: text(form.addressState).toUpperCase(),
    zip_code: /^\d{8}$/.test(zipCode) ? zipCode : null,
  }
  return address.street && address.city && /^[A-Z]{2}$/.test(address.state) ? address : null
}

export function useProjectGeocoding({ bridge, projectId }) {
  const request = useRef(null)
  useEffect(() => () => request.current?.abort(), [])

  return async (form) => {
    if (text(form.addressLatitude) || text(form.addressLongitude)) return null
    const address = geocodingAddress(form)
    if (!address) return null

    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    try {
      const coordinates = await fetchProjectCoordinates({ bridge, projectId, address, signal: controller.signal })
      controller.signal.throwIfAborted()
      if (!coordinates) return { notice: "Não foi possível localizar o endereço. Você pode preencher as coordenadas manualmente." }
      return {
        fields: { addressLatitude: String(coordinates.latitude), addressLongitude: String(coordinates.longitude) },
        notice: address.number ? "" : "As coordenadas foram estimadas pelo logradouro.",
      }
    } catch (error) {
      if (controller.signal.aborted) throw error
      return { notice: "A busca de coordenadas está indisponível. Você pode preencher os campos manualmente." }
    } finally {
      if (request.current === controller) request.current = null
    }
  }
}
