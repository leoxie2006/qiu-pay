<template>
  <div v-loading="loading" class="merchants">
    <div class="toolbar">
      <el-button type="primary" @click="showCreateDialog = true">创建商户</el-button>
    </div>

    <el-table :data="merchants" stripe style="width: 100%">
      <el-table-column prop="pid" label="PID" width="70" />
      <el-table-column prop="username" label="用户名" min-width="100" />
      <el-table-column prop="email" label="邮箱" min-width="160" />
      <el-table-column label="密钥" min-width="160">
        <template #default="{ row }">
          <span style="margin-right: 6px;">{{ row.key.substring(0, 8) }}...</span>
          <el-button size="small" link @click.stop="copyKey(row.key)">复制</el-button>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.active ? 'success' : 'danger'" size="small">
            {{ row.active ? '正常' : '封禁' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="money" label="余额" width="100">
        <template #default="{ row }">¥{{ row.money }}</template>
      </el-table-column>
      <el-table-column prop="orders" label="总订单" width="80" />
      <el-table-column prop="order_today" label="今日订单" width="90" />
      <el-table-column prop="created_at" label="创建时间" min-width="160" />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button
            :type="row.active ? 'danger' : 'success'"
            size="small"
            @click="toggleMerchant(row.pid, row.active ? 0 : 1)"
          >
            {{ row.active ? '封禁' : '解封' }}
          </el-button>
          <el-button size="small" @click="resetKey(row.pid)">重置密钥</el-button>
          <el-button type="primary" size="small" @click="openCredentials(row.pid)">凭证配置</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建商户对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建商户" width="420px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createMerchant">确定</el-button>
      </template>
    </el-dialog>

    <!-- 凭证配置对话框 -->
    <el-dialog v-model="showCredDialog" title="凭证配置（收款码+支付宝凭证）" width="700px">
      <div style="margin-bottom: 16px;">
        <span>商户 PID: {{ credPid }}</span>
      </div>

      <!-- 已有凭证列表 -->
      <el-table :data="credList" stripe style="width: 100%; margin-bottom: 16px;" v-if="credList.length">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="app_id" label="App ID" min-width="140" show-overflow-tooltip />
        <el-table-column label="收款码" width="100">
          <template #default="{ row }">
            <el-image
              v-if="row.qrcode_image"
              :src="row.qrcode_image"
              :preview-src-list="[row.qrcode_image]"
              fit="cover"
              style="width: 40px; height: 40px; cursor: pointer;"
              preview-teleported
            />
            <el-tag v-else type="info" size="small">无</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="验证状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.credential_status === 'verified' ? 'success' : 'danger'" size="small">
              {{ row.credential_status === 'verified' ? '已验证' : '验证失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="70">
          <template #default="{ row }">
            <el-tag :type="row.active ? 'success' : 'info'" size="small">
              {{ row.active ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" link @click="toggleCred(row.id)">
              {{ row.active ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" link type="danger" @click="deleteCred(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无凭证配置" />

      <!-- 新增凭证表单 -->
      <el-divider>新增凭证</el-divider>
      <el-form :model="credForm" label-width="100px">
        <el-form-item label="收款码">
          <el-upload
            :auto-upload="false"
            :show-file-list="true"
            :limit="1"
            accept=".png,.jpg,.jpeg"
            :on-change="onCredFileChange"
            :on-remove="onCredFileRemove"
          >
            <el-button size="small">选择图片</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="App ID">
          <el-input v-model="credForm.app_id" placeholder="支付宝应用ID" />
        </el-form-item>
        <el-form-item label="公钥">
          <el-input v-model="credForm.public_key" type="textarea" :rows="3" placeholder="支付宝公钥" />
        </el-form-item>
        <el-form-item label="私钥">
          <el-input v-model="credForm.private_key" type="textarea" :rows="3" placeholder="应用私钥" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="credSaving" @click="saveCredential">保存</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import type { Merchant } from '@/types'

const merchants = ref<Merchant[]>([])
const loading = ref(true)
const showCreateDialog = ref(false)
const form = ref({ username: '', email: '' })

// 凭证管理
const showCredDialog = ref(false)
const credPid = ref(0)
const credList = ref<any[]>([])
const credForm = ref({ app_id: '', public_key: '', private_key: '' })
const credFile = ref<File | null>(null)
const credSaving = ref(false)

async function loadMerchants() {
  try {
    const res = await api.get('/v1/admin/merchants')
    if (res.data.code === 1) {
      merchants.value = res.data.merchants
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}

async function createMerchant() {
  try {
    const res = await api.post('/v1/admin/merchants', form.value)
    if (res.data.code === 1) {
      ElMessage.success('商户创建成功')
      showCreateDialog.value = false
      form.value = { username: '', email: '' }
      await loadMerchants()
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  }
}

async function toggleMerchant(pid: number, active: number) {
  const action = active ? '解封' : '封禁'
  await ElMessageBox.confirm(`确定${action}该商户?`)
  try {
    const res = await api.put(`/v1/admin/merchants/${pid}`, { action: 'toggle', active })
    if (res.data.code === 1) {
      ElMessage.success(res.data.msg)
      await loadMerchants()
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  }
}

async function resetKey(pid: number) {
  await ElMessageBox.confirm('重置密钥后旧密钥立即失效，确定继续?')
  try {
    const res = await api.put(`/v1/admin/merchants/${pid}`, { action: 'reset_key' })
    if (res.data.code === 1) {
      await ElMessageBox.alert(`新密钥: ${res.data.key}`, '密钥已重置')
      await loadMerchants()
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  }
}

function copyKey(key: string) {
  navigator.clipboard.writeText(key).then(() => {
    ElMessage.success('密钥已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

// 凭证管理
async function openCredentials(pid: number) {
  credPid.value = pid
  showCredDialog.value = true
  await loadCredentials()
}

async function loadCredentials() {
  try {
    const res = await api.get(`/v1/admin/merchants/${credPid.value}/credentials`)
    if (res.data.code === 1) {
      credList.value = res.data.credentials
    }
  } catch {
    ElMessage.error('加载凭证列表失败')
  }
}

function onCredFileChange(uploadFile: any) {
  credFile.value = uploadFile.raw
}

function onCredFileRemove() {
  credFile.value = null
}

async function saveCredential() {
  if (!credForm.value.app_id || !credForm.value.public_key || !credForm.value.private_key) {
    ElMessage.error('App ID、公钥和私钥不能为空')
    return
  }
  if (!credFile.value && credList.value.length === 0) {
    ElMessage.error('首次配置必须上传收款码')
    return
  }
  credSaving.value = true
  try {
    const fd = new FormData()
    fd.append('app_id', credForm.value.app_id)
    fd.append('public_key', credForm.value.public_key)
    fd.append('private_key', credForm.value.private_key)
    if (credFile.value) {
      fd.append('file', credFile.value)
    }
    const res = await api.post(`/v1/admin/merchants/${credPid.value}/credentials`, fd)
    if (res.data.code === 1) {
      ElMessage.success(res.data.msg || '保存成功')
      credForm.value = { app_id: '', public_key: '', private_key: '' }
      credFile.value = null
      await loadCredentials()
    } else {
      ElMessage.error(res.data.msg || '保存失败')
    }
  } catch {
    ElMessage.error('网络请求失败')
  } finally {
    credSaving.value = false
  }
}

async function toggleCred(credId: number) {
  try {
    const res = await api.post(`/v1/admin/merchants/${credPid.value}/credentials/${credId}/toggle`)
    if (res.data.code === 1) {
      ElMessage.success(res.data.msg)
      await loadCredentials()
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch {
    ElMessage.error('操作失败')
  }
}

async function deleteCred(credId: number) {
  await ElMessageBox.confirm('确定删除该凭证配置？')
  try {
    const res = await api.delete(`/v1/admin/merchants/${credPid.value}/credentials/${credId}`)
    if (res.data.code === 1) {
      ElMessage.success(res.data.msg)
      await loadCredentials()
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch {
    ElMessage.error('操作失败')
  }
}

onMounted(loadMerchants)
</script>

<style scoped>
.merchants {
  min-height: 200px;
}

.toolbar {
  margin-bottom: 16px;
}
</style>
