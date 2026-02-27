<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header acc-bg-slate">
        <h2 class="login-title">QIU-PAY 管理后台</h2>
      </div>
      <div class="login-body" style="border-top: 4px solid #000;">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="0"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              prefix-icon="User"
              size="large"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              prefix-icon="Lock"
              show-password
              size="large"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-button
              class="login-btn"
              size="large"
              :loading="loading"
              style="width: 100%"
              @click="handleLogin"
            >
              登录 ➔
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const data = await authStore.login(form.username, form.password)
    if (data.code === 1) {
      await router.push('/admin/dashboard')
    } else {
      ElMessage.error(data.msg || '登录失败')
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background-color: #fff;
  background-image: radial-gradient(#000 1px, transparent 1px);
  background-size: 20px 20px;
}

.login-card {
  width: 400px;
  background-color: #fff;
  border: 4px solid #000;
  box-shadow: 12px 12px 0 0 #cbd5e1;
  display: flex;
  flex-direction: column;
}

.login-header {
  padding: 24px;
  color: #000;
}

.login-title {
  text-align: center;
  margin: 0;
  font-size: 26px;
  letter-spacing: 2px;
  font-weight: 900;
}

.login-body {
  padding: 30px;
}

.login-btn {
  background-color: #000 !important;
  color: #fff !important;
  font-size: 18px !important;
  font-weight: 900 !important;
  border: 4px solid #000 !important;
  box-shadow: 4px 4px 0 0 #cbd5e1 !important;
  transition: transform 0.1s, box-shadow 0.1s !important;
}

.login-btn:hover {
  background-color: #f1f5f9 !important;
  color: #000 !important;
  transform: translate(-2px, -2px) !important;
  box-shadow: 6px 6px 0 0 #cbd5e1 !important;
}

.login-btn:active {
  transform: translate(4px, 4px) !important;
  box-shadow: 0 0 0 0 #cbd5e1 !important;
}
</style>
