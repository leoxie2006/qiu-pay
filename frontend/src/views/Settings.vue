<template>
  <div v-loading="loading" class="settings">
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
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const loading = ref(false)

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
</script>

<style scoped>
.settings {
  min-height: 200px;
}

.section-card {
  margin-bottom: 20px;
}
</style>
