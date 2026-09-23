import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getModuleSchemas } from '../api/modules'

export interface FieldSpec {
  api_name: string
  type: string
  required: boolean
  picklist_values: string[]
  lookup_module: string | null
  read_only: boolean
}

export interface ModuleSpec {
  fields: FieldSpec[]
  required: string[]
  related_lists: string[]
}

export const useModulesStore = defineStore('modules', () => {
  const schemas = ref<Record<string, ModuleSpec>>({})
  const loaded = ref(false)
  const error = ref('')

  async function load(force = false) {
    if (loaded.value && !force) return
    error.value = ''
    try {
      schemas.value = await getModuleSchemas()
      loaded.value = true
    } catch (e: any) {
      error.value = e.message || 'Failed to load module schemas'
    }
  }

  function spec(module: string): ModuleSpec | null {
    return schemas.value[module] || null
  }

  return { schemas, loaded, error, load, spec }
})
