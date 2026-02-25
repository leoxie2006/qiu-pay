<template>
  <div v-loading="loading" class="settings">
    <!-- 收款码管理 -->
    <el-card class="section-card">
      <template #header>
        <span>收款码管理</span>
      </template>
      <div class="status-row">
        <span>状态：</span>
        <el-tag :type="qrcodeStatus.configured ? 'success' : 'info'" size="small">
          {{ qrcodeStatus.configured ? '已配置' : '未配置' }}
        </el-tag>
      </div>
      <div v-if="qrcodeStatus.configured" class="qrcode-preview">
        <img v-if="qrcodeStatus.qrcode_image" :src="qrcodeStatus.qrcode_image" alt="收款码" class="qrcode-img" />
        <div v-if="qrcodeStatus.qrcode_url" style="margin-top: 8px; font-size: 12px; color: #909399; word-break: break-all;">
          解析链接：{{ qrcodeStatus.qrcode_url }}
        </div>
      </div>
      <el-upload
        :action="uploadAction"
        :headers="uploadHeaders"
        name="file"
        :show-file-list="false"
        accept=".png,.jpg,.jpeg"
        :on-success="onUploadSuccess"
        :on-error="onUploadError"
      >
        <el-button type="primary">上传收款码</el-button>
      </el-upload>
    </el-card>

    <!-- 支付凭证配置 -->
    <el-card class="section-card">
      <template #header>
        <span>支付凭证配置</span>
      </template>
      <div class="status-row">
        <span>状态：</span>
        <el-tag :type="credentialTagType" size="small">
          {{ credentialStatusText }}
        </el-tag>
        <span v-if="credentialStatus.app_id" style="margin-left: 12px;">
          App ID: {{ credentialStatus.app_id }}
        </span>
      </div>
      <el-form :model="credentialForm" label-width="100px" style="margin-top: 16px;">
        <el-form-item label="App ID">
          <el-input v-model="credentialForm.app_id" placeholder="请输入支付宝应用ID" />
        </el-form-item>
        <el-form-item label="公钥">
          <el-input v-model="credentialForm.public_key" type="textarea" :rows="4" placeholder="请输入支付宝公钥" />
        </el-form-item>
        <el-form-item label="私钥">
          <el-input v-model="credentialForm.private_key" type="textarea" :rows="4" placeholder="请输入应用私钥" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="credentialSaving" @click="saveCredential">保存凭证</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 密码修改 -->
    <el-card class="section-card">
      <template #header>
        <span>密码修改</span>
      </template>
      <el-form :model="passwordForm" label-width="100px">
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
          <el-button type="primary" :loading="passwordSaving" @click="changePassword">修改密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const loading = ref(true)

// 收款码状态
const qrcodeStatus = ref<{ configured: boolean; qrcode_url: string | null; qrcode_image: string | null }>({
  configured: false,
  qrcode_url: null,
  qrcode_image: null,
})

// 凭证状态
const credentialStatus = ref<{ status: string; app_id?: string }>({
  status: 'unconfigured',
})

const credentialTagType = computed(() => {
  const map: Record<string, string> = {
    verified: 'success',
    configured: 'warning',
    failed: 'danger',
    unconfigured: 'info',
  }
  return map[credentialStatus.value.status] || 'info'
})

const credentialStatusText = computed(() => {
  const map: Record<string, string> = {
    verified: '已验证',
    configured: '已配置',
    failed: '验证失败',
    unconfigured: '未配置',
  }
  return map[credentialStatus.value.status] || '未配置'
})

// 上传相关
const uploadAction = '/v1/admin/settings/qrcode'
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
})

// 凭证表单
const credentialForm = ref({ app_id: '', public_key: '', private_key: '' })
const credentialSaving = ref(false)

// 密码表单
const passwordForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const passwordSaving = ref(false)

async function loadSettings() {
  try {
    const res = await api.get('/v1/admin/settings')
    if (res.data.code === 1) {
      qrcodeStatus.value = res.data.qrcode_status
      credentialStatus.value = res.data.credential_status
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}

function onUploadSuccess(response: any) {
  if (response.code === 1) {
    ElMessage.success(response.msg || '收款码上传成功')
    loadSettings()
  } else {
    ElMessage.error(response.msg || '上传失败')
  }
}

function onUploadError(error: any) {
  let msg = '上传失败'
  try {
    const data = JSON.parse(error.message)
    if (data.msg) msg = data.msg
  } catch {
    // ignore parse error
  }
  ElMessage.error(msg)
}

async function saveCredential() {
  credentialSaving.value = true
  try {
    const res = await api.post('/v1/admin/settings/alipay-credentials', credentialForm.value)
    if (res.data.code === 1) {
      ElMessage.success(res.data.message || '凭证保存成功')
      credentialForm.value = { app_id: '', public_key: '', private_key: '' }
      await loadSettings()
    } else {
      ElMessage.error(res.data.msg || '保存失败')
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  } finally {
    credentialSaving.value = false
  }
}

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

onMounted(loadSettings)
</script>

<style scoped>
.settings {
  min-height: 200px;
}

.section-card {
  margin-bottom: 20px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.qrcode-preview {
  margin-bottom: 12px;
}

.qrcode-img {
  max-width: 200px;
  max-height: 200px;
  border: 1px solid #eee;
  border-radius: 4px;
}
</style>