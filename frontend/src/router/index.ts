import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  { path: '/pay/:tradeNo', name: 'Pay', component: () => import('@/views/Pay.vue'), meta: { public: true } },
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue') },
      { path: 'merchants', name: 'Merchants', component: () => import('@/views/Merchants.vue') },
      { path: 'orders', name: 'Orders', component: () => import('@/views/Orders.vue') },
      { path: 'orders/:tradeNo', name: 'OrderDetail', component: () => import('@/views/OrderDetail.vue') },
      { path: 'settings', name: 'Settings', component: () => import('@/views/Settings.vue') },
      { path: 'docs', name: 'Docs', component: () => import('@/views/Docs.vue') },
    ],
  },
  { path: '/', redirect: '/admin/dashboard' },
]

const router = createRouter({ history: createWebHistory(), routes })

// 检查 demo 模式状态
let demoModeChecked = false
let isDemoMode = false

async function checkDemoMode() {
  if (demoModeChecked) return
  try {
    const response = await fetch('/v1/admin/auth/demo-status')
    const data = await response.json()
    isDemoMode = data.demo_mode
    demoModeChecked = true
  } catch {
    // 如果检查失败，假设不是 demo 模式
    demoModeChecked = true
  }
}

router.beforeEach(async (to, _from, next) => {
  // 先检查 demo 模式
  await checkDemoMode()

  // Demo 模式下：允许访问所有页面（无需登录）
  if (isDemoMode) {
    return next()
  }

  // 正常模式：检查登录状态
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
