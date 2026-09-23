import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(sessionStorage.getItem('zoho_token') || '')
  const apiDomain = ref('')

  const isLoggedIn = computed(() => !!token.value)

  function setToken(t: string, domain = '') {
    token.value = t
    apiDomain.value = domain
    sessionStorage.setItem('zoho_token', t)
  }

  function logout() {
    token.value = ''
    apiDomain.value = ''
    sessionStorage.removeItem('zoho_token')
  }

  return { token, apiDomain, isLoggedIn, setToken, logout }
})
