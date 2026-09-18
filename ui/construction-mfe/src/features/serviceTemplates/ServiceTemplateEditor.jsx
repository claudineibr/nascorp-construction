import { useMemo, useState } from "react"
import { ChevronDown, ChevronUp, Plus, Trash2 } from "lucide-react"

import appStyles from "../../App.module.css"
import styles from "./ServiceTemplates.module.css"

const INFO_STEP = "info"

let sequenceCounter = 0

const nextKey = () => {
  sequenceCounter += 1
  return `k${sequenceCounter}`
}

const buildEmptyItem = () => ({
  key: nextKey(),
  description: "",
  verificationMethod: "",
  requiresComment: false,
  requiresPhoto: false,
})

const buildEmptySection = (name = "") => ({
  key: nextKey(),
  name,
  items: [buildEmptyItem()],
})

const buildInitialState = (template) => {
  if (!template) {
    return {
      name: "",
      productId: "",
      isActive: true,
      sections: [buildEmptySection()],
    }
  }

  const sections = (template.sections ?? []).map((section) => ({
    key: nextKey(),
    name: section.name ?? "",
    items: (section.items ?? []).map((item) => ({
      key: nextKey(),
      description: item.description ?? "",
      verificationMethod: item.verificationMethod ?? "",
      requiresComment: item.requiresComment ?? false,
      requiresPhoto: item.requiresPhoto ?? false,
    })),
  }))

  return {
    name: template.name ?? "",
    productId: template.productId ?? "",
    isActive: template.isActive ?? true,
    sections: sections.length > 0 ? sections : [buildEmptySection()],
  }
}

const moveInList = (list, index, offset) => {
  const target = index + offset
  if (target < 0 || target >= list.length) {
    return list
  }

  const reordered = [...list]
  const [moved] = reordered.splice(index, 1)
  reordered.splice(target, 0, moved)
  return reordered
}

export function ServiceTemplateEditor({ template, submitting, onCancel, onSubmit }) {
  const [form, setForm] = useState(() => buildInitialState(template))
  const [activeStep, setActiveStep] = useState(INFO_STEP)
  const [errors, setErrors] = useState({})

  const isEditing = Boolean(template)
  const activeSectionIndex = useMemo(
    () => form.sections.findIndex((section) => section.key === activeStep),
    [form.sections, activeStep],
  )
  const activeSection = activeSectionIndex >= 0 ? form.sections[activeSectionIndex] : null

  const updateSection = (sectionIndex, changes) => {
    setForm((current) => ({
      ...current,
      sections: current.sections.map((section, index) =>
        index === sectionIndex ? { ...section, ...changes } : section,
      ),
    }))
  }

  const updateItem = (sectionIndex, itemIndex, changes) => {
    setForm((current) => ({
      ...current,
      sections: current.sections.map((section, index) => {
        if (index !== sectionIndex) {
          return section
        }

        return {
          ...section,
          items: section.items.map((item, position) =>
            position === itemIndex ? { ...item, ...changes } : item,
          ),
        }
      }),
    }))
  }

  const addSection = () => {
    const section = buildEmptySection()
    setForm((current) => ({ ...current, sections: [...current.sections, section] }))
    setActiveStep(section.key)
  }

  const removeSection = (sectionIndex) => {
    setForm((current) => {
      const sections = current.sections.filter((_, index) => index !== sectionIndex)
      const remaining = sections.length > 0 ? sections : [buildEmptySection()]
      setActiveStep(remaining[Math.max(0, sectionIndex - 1)].key)
      return { ...current, sections: remaining }
    })
  }

  const addItem = (sectionIndex) => {
    setForm((current) => ({
      ...current,
      sections: current.sections.map((section, index) =>
        index === sectionIndex ? { ...section, items: [...section.items, buildEmptyItem()] } : section,
      ),
    }))
  }

  const removeItem = (sectionIndex, itemIndex) => {
    setForm((current) => ({
      ...current,
      sections: current.sections.map((section, index) =>
        index === sectionIndex
          ? { ...section, items: section.items.filter((_, position) => position !== itemIndex) }
          : section,
      ),
    }))
  }

  const moveItem = (sectionIndex, itemIndex, offset) => {
    setForm((current) => ({
      ...current,
      sections: current.sections.map((section, index) =>
        index === sectionIndex ? { ...section, items: moveInList(section.items, itemIndex, offset) } : section,
      ),
    }))
  }

  const validate = () => {
    const nextErrors = {}
    if (!form.name.trim()) {
      nextErrors.name = "Informe o nome do serviço."
    }

    const seenSections = new Set()
    form.sections.forEach((section) => {
      const sectionName = section.name.trim().toUpperCase()
      if (!sectionName) {
        nextErrors[section.key] = "Informe o nome da seção."
        return
      }

      if (seenSections.has(sectionName)) {
        nextErrors[section.key] = "Já existe uma seção com esse nome."
        return
      }

      seenSections.add(sectionName)

      const seenItems = new Set()
      const hasIncompleteItem = section.items.some(
        (item) => !item.description.trim() || !item.verificationMethod.trim(),
      )
      if (hasIncompleteItem) {
        nextErrors[section.key] = "Todo item precisa de descrição e método de verificação."
        return
      }

      const hasDuplicatedItem = section.items.some((item) => {
        const description = item.description.trim().toUpperCase()
        if (seenItems.has(description)) {
          return true
        }

        seenItems.add(description)
        return false
      })
      if (hasDuplicatedItem) {
        nextErrors[section.key] = "Há itens repetidos nesta seção."
      }
    })

    setErrors(nextErrors)
    return nextErrors
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    const nextErrors = validate()
    if (Object.keys(nextErrors).length > 0) {
      if (nextErrors.name) {
        setActiveStep(INFO_STEP)
        return
      }

      const failingSection = form.sections.find((section) => nextErrors[section.key])
      if (failingSection) {
        setActiveStep(failingSection.key)
      }
      return
    }

    onSubmit({
      name: form.name.trim(),
      productId: form.productId || null,
      isActive: form.isActive,
      sections: form.sections.map((section) => ({
        name: section.name.trim(),
        items: section.items.map((item) => ({
          description: item.description.trim(),
          verificationMethod: item.verificationMethod.trim(),
          requiresComment: item.requiresComment,
          requiresPhoto: item.requiresPhoto,
        })),
      })),
    })
  }

  return (
    <div className={styles.editorOverlay} role="dialog" aria-modal="true">
      <div className={styles.editorCard}>
        <header className={styles.editorHeader}>
          <h3>{isEditing ? "Editar serviço" : "Novo serviço"}</h3>
          <button type="button" className={appStyles.closeButton} onClick={onCancel}>
            Fechar
          </button>
        </header>

        <form className={styles.editorForm} onSubmit={handleSubmit}>
          <div className={styles.editorLayout}>
            <aside className={styles.stepColumn}>
              <p className={styles.stepGroupTitle}>Etapas de cadastro</p>
              <button
                type="button"
                className={`${styles.stepButton} ${activeStep === INFO_STEP ? styles.stepButtonActive : ""} ${
                  errors.name ? styles.stepButtonInvalid : ""
                }`}
                onClick={() => setActiveStep(INFO_STEP)}
              >
                Informações do serviço
              </button>

              <p className={styles.stepGroupTitle}>Seções</p>
              {form.sections.map((section, index) => (
                <button
                  key={section.key}
                  type="button"
                  className={`${styles.stepButton} ${activeStep === section.key ? styles.stepButtonActive : ""} ${
                    errors[section.key] ? styles.stepButtonInvalid : ""
                  }`}
                  onClick={() => setActiveStep(section.key)}
                >
                  {index + 1}. {section.name.trim() || "Sem nome"}
                </button>
              ))}
              <button type="button" className={styles.addStepButton} onClick={addSection}>
                <Plus size={14} />
                Nova seção
              </button>

              <div className={styles.stepFooter}>
                <button type="submit" className={appStyles.primaryButton} disabled={submitting}>
                  {submitting ? "Salvando..." : "Salvar serviço"}
                </button>
                <button
                  type="button"
                  className={appStyles.secondaryButton}
                  onClick={onCancel}
                  disabled={submitting}
                >
                  Cancelar
                </button>
              </div>
            </aside>

            <section className={styles.contentColumn}>
              {activeStep === INFO_STEP ? (
                <>
                  <header className={styles.contentHeader}>
                    <h4 className={styles.contentTitle}>Informações do serviço</h4>
                    <p className={styles.contentSubtitle}>
                      O nome identifica a ficha de verificação no catálogo da empresa.
                    </p>
                  </header>

                  <div className={styles.field}>
                    <label htmlFor="service-template-name">Nome do serviço</label>
                    <input
                      id="service-template-name"
                      className={styles.input}
                      value={form.name}
                      onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                      placeholder="Ex.: Aterro / Compactação de aterro"
                    />
                    {errors.name ? <span className={styles.fieldError}>{errors.name}</span> : null}
                  </div>

                  <label className={styles.checkbox}>
                    <input
                      type="checkbox"
                      checked={form.isActive}
                      onChange={(event) => setForm((current) => ({ ...current, isActive: event.target.checked }))}
                    />
                    Serviço ativo no catálogo
                  </label>
                </>
              ) : null}

              {activeSection ? (
                <>
                  <header className={styles.contentHeader}>
                    <h4 className={styles.contentTitle}>
                      {activeSectionIndex + 1}. {activeSection.name.trim() || "Nova seção"}
                    </h4>
                    <p className={styles.contentSubtitle}>
                      Itens a inspecionar e o método de verificação de cada um.
                    </p>
                  </header>

                  <div className={styles.field}>
                    <label htmlFor="section-name">Nome da seção</label>
                    <input
                      id="section-name"
                      className={styles.input}
                      value={activeSection.name}
                      onChange={(event) => updateSection(activeSectionIndex, { name: event.target.value })}
                      placeholder="Ex.: Materiais de acabamento"
                    />
                    {errors[activeSection.key] ? (
                      <span className={styles.fieldError}>{errors[activeSection.key]}</span>
                    ) : null}
                  </div>

                  <div className={styles.itemList}>
                    {activeSection.items.map((item, itemIndex) => (
                      <article key={item.key} className={styles.itemCard}>
                        <header className={styles.itemHeader}>
                          <span className={styles.itemNumber}>Item {itemIndex + 1}</span>
                          <div className={styles.rowActions}>
                            <button
                              type="button"
                              className={styles.iconButton}
                              onClick={() => moveItem(activeSectionIndex, itemIndex, -1)}
                              disabled={itemIndex === 0}
                              aria-label="Mover item para cima"
                              title="Mover item para cima"
                            >
                              <ChevronUp size={15} />
                            </button>
                            <button
                              type="button"
                              className={styles.iconButton}
                              onClick={() => moveItem(activeSectionIndex, itemIndex, 1)}
                              disabled={itemIndex === activeSection.items.length - 1}
                              aria-label="Mover item para baixo"
                              title="Mover item para baixo"
                            >
                              <ChevronDown size={15} />
                            </button>
                            <button
                              type="button"
                              className={`${styles.iconButton} ${styles.dangerIconButton}`}
                              onClick={() => removeItem(activeSectionIndex, itemIndex)}
                              aria-label="Remover item"
                              title="Remover item"
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </header>

                        <div className={styles.itemGrid}>
                          <div className={styles.field}>
                            <label>Item a ser inspecionado</label>
                            <textarea
                              className={styles.textarea}
                              rows={2}
                              value={item.description}
                              onChange={(event) =>
                                updateItem(activeSectionIndex, itemIndex, { description: event.target.value })
                              }
                              placeholder="Ex.: Terreno limpo, sem vegetação, entulho ou material orgânico"
                            />
                          </div>
                          <div className={`${styles.field} ${styles.itemMethod}`}>
                            <label>Método de verificação</label>
                            <input
                              className={styles.input}
                              value={item.verificationMethod}
                              onChange={(event) =>
                                updateItem(activeSectionIndex, itemIndex, {
                                  verificationMethod: event.target.value,
                                })
                              }
                              placeholder="Ex.: Visual / projeto"
                            />
                          </div>

                          <div className={styles.itemFlags}>
                            <label className={styles.checkbox}>
                              <input
                                type="checkbox"
                                checked={item.requiresComment}
                                onChange={(event) =>
                                  updateItem(activeSectionIndex, itemIndex, {
                                    requiresComment: event.target.checked,
                                  })
                                }
                              />
                              Exige comentário
                            </label>
                            <label className={styles.checkbox}>
                              <input
                                type="checkbox"
                                checked={item.requiresPhoto}
                                onChange={(event) =>
                                  updateItem(activeSectionIndex, itemIndex, {
                                    requiresPhoto: event.target.checked,
                                  })
                                }
                              />
                              Exige foto
                            </label>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>

                  <div className={appStyles.modalFooter}>
                    <button
                      type="button"
                      className={appStyles.secondaryButton}
                      onClick={() => removeSection(activeSectionIndex)}
                    >
                      <Trash2 size={15} />
                      Remover seção
                    </button>
                    <button
                      type="button"
                      className={appStyles.primaryButton}
                      onClick={() => addItem(activeSectionIndex)}
                    >
                      <Plus size={15} />
                      Adicionar item
                    </button>
                  </div>
                </>
              ) : null}
            </section>
          </div>

          <footer className={styles.editorFooter}>
            <button
              type="button"
              className={appStyles.secondaryButton}
              onClick={onCancel}
              disabled={submitting}
            >
              Cancelar
            </button>
            <button type="submit" className={appStyles.primaryButton} disabled={submitting}>
              {submitting ? "Salvando..." : "Salvar serviço"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  )
}
