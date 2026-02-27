<template>
  <el-container class="admin-layout">
    <el-aside width="240px" class="admin-aside">
      <div class="logo acc-bg-slate">QIU-PAY // 管理后台</div>
      <el-menu
        :default-active="activeMenu"
        router
        class="brutalist-menu"
        text-color="#000"
        active-text-color="#000"
      >
        <el-menu-item index="/admin/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/admin/merchants">
          <el-icon><User /></el-icon>
          <span>商户管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/orders">
          <el-icon><List /></el-icon>
          <span>订单管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
        <el-menu-item index="/admin/docs">
          <el-icon><Document /></el-icon>
          <span>使用文档</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container class="main-container">
      <el-header class="admin-header">
        <span class="admin-info">当前用户: {{ authStore.username || 'ADMIN' }}</span>
        <el-button class="logout-btn" size="small" @click="handleLogout">退出登录</el-button>
      </el-header>
      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Odometer, User, List, Setting, Document } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const activeMenu = computed(() => {
  // For order detail pages, highlight the orders menu item
  if (route.path.startsWith('/admin/orders')) {
    return '/admin/orders'
  }
  return route.path
})

async function handleLogout() {
  authStore.logout()
  await router.push('/login')
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
  background-color: #fff;
}

.admin-aside {
  border-right: 4px solid #000;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 64px;
  line-height: 64px;
  text-align: center;
  color: #000;
  font-size: 18px;
  font-weight: 900;
  letter-spacing: 1px;
  border-bottom: 4px solid #000;
}

.brutalist-menu {
  border-right: none;
  flex: 1;
}

:deep(.el-menu) {
  background-color: transparent;
}

:deep(.el-menu-item) {
  font-size: 15px;
  font-weight: 900;
  height: 60px;
  line-height: 60px;
  border-bottom: 2px solid #000;
  transition: all 0.2s;
}

:deep(.el-menu-item:hover) {
  background-color: #000 !important;
  color: #fff !important;
}

:deep(.el-menu-item.is-active) {
  background-color: #e0f2fe !important;
  color: #000 !important;
  border-right: 6px solid #000;
}

.main-container {
  background-image: radial-gradient(#000 1px, transparent 1px);
  background-size: 24px 24px;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 20px;
  height: 64px;
  border-bottom: 4px solid #000;
  padding: 0 30px;
}

.admin-info {
  font-size: 16px;
  font-weight: 900;
  color: #000;
  border: 2px solid #000;
  padding: 4px 12px;
  background-color: #fff;
  box-shadow: 2px 2px 0 0 #cbd5e1;
}

.logout-btn {
  background-color: #fff !important;
  color: #000 !important;
  border: 2px solid #000 !important;
  font-weight: 900 !important;
  box-shadow: 2px 2px 0 0 #cbd5e1 !important;
}

.logout-btn:hover {
  background-color: #f1f5f9 !important;
}

.admin-main {
  padding: 30px;
  height: calc(100vh - 64px);
  overflow-y: auto;
}
</style>
