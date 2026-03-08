import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 10000,
})

// 检查是否为 demo 模式
let demoMode = false
api.get('/v1/admin/auth/demo-status').then(res => {
  demoMode = res.data.demo_mode && res.data.ip_allowed
}).catch(() => {
  // 忽略错误
})

// 请求拦截：自动注入 JWT token（非 demo 模式）
api.interceptors.request.use((config) => {
  if (!demoMode) {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

// 响应拦截：401 自动跳转登录（非 demo 模式）
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !demoMode) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
