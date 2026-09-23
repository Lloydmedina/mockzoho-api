import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(sessionStorage.getItem('zoho_token') || '')
  const apiDomain = ref('')
  const creds = ref<{ client_id: string; client_secret: string; refresh_token: string } | null>(
    JSON.parse(sessionStorage.getItem('zoho_creds') || 'null')
  )

  const isLoggedIn = computed(() => !!token.value)

  function setToken(t: string, domain = '') {
    token.value = t
    apiDomain.value = domain
    sessionStorage.setItem('zoho_token', t)
  }

  function setCreds(c: { client_id: string; client_secret: string; refresh_token: string }) {
    creds.value = c
    sessionStorage.setItem('zoho_creds', JSON.stringify(c))
  }

  function logout() {
    token.value = ''
    apiDomain.value = ''
    creds.value = null
    sessionStorage.removeItem('zoho_token')
    sessionStorage.removeItem('zoho_creds')
  }

  return { token, apiDomain, creds, isLoggedIn, setToken, setCreds, logout }
})
