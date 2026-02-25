import { defineStore } from 'pinia'
import api from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    username: '',
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
  },
  actions: {
    async login(username: string, password: string): Promise<{ code: number; msg?: string }> {
      const { data } = await api.post('/v1/admin/auth/login', { username, password })
      if (data.code === 1) {
        this.token = data.token
        this.username = username
        localStorage.setItem('token', data.token)
      }
      return data
    },
    logout() {
      this.token = ''
      this.username = ''
      localStorage.removeItem('token')
    },
  },
})
