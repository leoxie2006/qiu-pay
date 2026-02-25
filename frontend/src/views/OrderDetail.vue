<template>
  <div v-loading="loading" class="order-detail">
    <div v-if="error" class="error-container">
      <el-result icon="error" :title="error">
        <template #extra>
          <el-button type="primary" @click="goBack">返回订单列表</el-button>
        </template>
      </el-result>
    </div>

    <template v-if="order">
      <div class="header">
        <el-button @click="goBack" :icon="ArrowLeft">返回订单列表</el-button>
      </div>

      <!-- 订单信息 -->
      <el-card shadow="never" class="info-card">
        <template #header>
          <span>订单信息</span>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="订单号">{{ order.trade_no }}</el-descriptions-item>
          <el-descriptions-item label="外部订单号">{{ order.out_trade_no }}</el-descriptions-item>
          <el-descriptions-item label="商户ID">{{ order.merchant_id }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ order.type }}</el-descriptions-item>
          <el-descriptions-item label="商品名称">{{ order.name }}</el-descriptions-item>
          <el-descriptions-item label="原始金额">¥{{ order.original_money }}</el-descriptions-item>
          <el-descriptions-item label="实际金额">¥{{ order.money }}</el-descriptions-item>
          <el-descriptions-item label="订单状态">
            <el-tag :type="statusTagType(order.status)" size="small">
              {{ order.status_text }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="回调状态">
            <el-tag :type="callbackTagType(order.callback_status)" size="small">
              {{ order.callback_status_text }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="通知地址">{{ order.notify_url || '-' }}</el-descriptions-item>
          <el-descriptions-item label="返回地址">{{ order.return_url || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ order.created_at }}</el-descriptions-item>
          <el-descriptions-item label="支付时间">{{ order.paid_at || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 回调日志 -->
      <el-card shadow="never" class="info-card">
        <template #header>
          <span>回调日志</span>
        </template>
        <el-table :data="callbackLogs" stripe style="width: 100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="status_code" label="状态码" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status_code === 200 ? 'success' : 'danger'" size="small">
                {{ row.status_code }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="response_body" label="响应内容" min-width="300" show-overflow-tooltip />
          <el-table-column prop="created_at" label="时间" min-width="160" />
        </el-table>
        <el-empty v-if="callbackLogs.length === 0" description="暂无回调日志" />
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import api from '@/api'
import type { OrderDetail, CallbackLog } from '@/types'

const route = useRoute()
const router = useRouter()
const tradeNo = route.params.tradeNo as string

const order = ref<OrderDetail | null>(null)
const callbackLogs = ref<CallbackLog[]>([])
const loading = ref(true)
const error = ref('')

function statusTagType(status: number) {
  if (status === 1) return 'success'
  if (status === 2) return 'info'
  return 'warning'
}

function callbackTagType(status: number) {
  if (status === 1) return 'success'
  if (status === 2) return 'danger'
  if (status === 3) return 'warning'
  return 'info'
}

function goBack() {
  router.push('/admin/orders')
}

onMounted(async () => {
  try {
    const res = await api.get(`/v1/admin/orders/${tradeNo}`)
    if (res.data.code === 1) {
      order.value = res.data.order
      callbackLogs.value = res.data.callback_logs || []
    } else {
      error.value = res.data.msg || '加载失败'
    }
  } catch (err: any) {
    if (err.response?.status === 404) {
      error.value = '订单不存在'
    } else {
      error.value = '网络请求失败，请检查网络连接'
      ElMessage.error('网络请求失败，请检查网络连接')
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.order-detail {
  min-height: 200px;
}

.header {
  margin-bottom: 16px;
}

.info-card {
  margin-bottom: 16px;
}

.error-container {
  padding: 40px 0;
}
</style>
