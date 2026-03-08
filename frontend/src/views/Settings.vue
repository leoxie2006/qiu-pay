<template>
  <div v-loading="loading" class="settings">
    <!-- 系统配置 -->
    <el-card shadow="never" class="section-card brutalist-card acc-bg-slate">
      <template #header>
        <div class="card-header-title acc-bg-white" style="display:inline-block; padding: 4px 12px; border: 2px solid #000;">系统配置</div>
      </template>
      <el-form :model="configForm" label-width="120px" class="brutalist-form acc-bg-white" style="padding: 20px; border: 2px solid #000; box-shadow: 4px 4px 0 0 #cbd5e1;">
        <el-form-item label="备案信息">
          <el-input v-model="configForm.icp_record" placeholder="请输入页面底部展示的备案信息" />
        </el-form-item>
        <el-form-item>
          <el-button class="action-btn" :loading="configSaving" @click="saveConfig">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 密码修改 -->
    <el-card shadow="never" class="section-card brutalist-card acc-bg-slate">
      <template #header>
        <div class="card-header-title acc-bg-white" style="display:inline-block; padding: 4px 12px; border: 2px solid #000;">密码修改</div>
      </template>
      <el-form :model="passwordForm" label-width="120px" class="brutalist-form acc-bg-white" style="padding: 20px; border: 2px solid #000; box-shadow: 4px 4px 0 0 #cbd5e1;">
        <el-form-item label="原密码">
          <el-input v-model="passwordForm.old_password" type="password" show-password placeholder="请输入原密码" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
        <el-form-item>
          <el-button class="action-btn" :loading="passwordSaving" @click="changePassword">修改密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const loading = ref(false)

// 系统配置表单
const configForm = ref({ icp_record: '' })
const configSaving = ref(false)

async function fetchConfig() {
  loading.value = true
  try {
    const res = await api.get('/v1/admin/settings/config')
    if (res.data.code === 1) {
      configForm.value.icp_record = res.data.config?.icp_record || ''
    }
  } catch {
    ElMessage.error('获取系统配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  configSaving.value = true
  try {
    const res = await api.post('/v1/admin/settings/config', {
      icp_record: configForm.value.icp_record
    })
    if (res.data.code === 1) {
      ElMessage.success('系统配置保存成功')
    } else {
      ElMessage.error(res.data.msg || '保存失败')
    }
  } catch {
    ElMessage.error('网络请求失败')
  } finally {
    configSaving.value = false
  }
}

// 密码表单
const passwordForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const passwordSaving = ref(false)

async function changePassword() {
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    ElMessage.error('两次输入的密码不一致')
    return
  }
  passwordSaving.value = true
  try {
    const res = await api.post('/v1/admin/settings/change-password', {
      old_password: passwordForm.value.old_password,
      new_password: passwordForm.value.new_password,
    })
    if (res.data.code === 1) {
      ElMessage.success(res.data.msg || '密码修改成功')
      passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
    } else {
      ElMessage.error(res.data.msg || '密码修改失败')
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  } finally {
    passwordSaving.value = false
  }
}

onMounted(() => {
  fetchConfig()
})
</script>

<style scoped>
.settings {
  min-height: 200px;
  max-width: 600px;
}

.section-card {
  margin-bottom: 24px;
}

.brutalist-card {
  border: 4px solid #000 !important;
  box-shadow: 8px 8px 0 0 #cbd5e1 !important;
}

.card-header-title {
  font-weight: 900;
  font-size: 18px;
  letter-spacing: 1px;
}

.brutalist-form {
  margin-top: 10px;
}

:deep(.el-form-item__label) {
  font-weight: 900;
  color: #000;
}

.action-btn {
  margin-top: 10px;
  font-size: 16px !important;
  padding: 12px 24px !important;
  height: auto !important;
}
</style>
