<template>
  <div class="pay-page">
    <!-- Loading -->
    <div v-if="loading" class="pay-card">
      <div class="spinner"></div>
      <p class="loading-text">加载中...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="pay-card error-card">
      <div class="error-icon">✕</div>
      <p class="error-text">{{ error }}</p>
    </div>

    <!-- Payment Content -->
    <div v-else-if="data" class="pay-card">
      <!-- 支付成功 -->
      <template v-if="status === 1">
        <div class="status-icon success-icon">✓</div>
        <p class="status-text success-text">支付成功</p>
        <p class="redirect-hint" v-if="data.return_url">3 秒后自动跳转...</p>
      </template>

      <!-- 订单已超时 -->
      <template v-else-if="status === 2">
        <div class="status-icon timeout-icon">!</div>
        <p class="status-text timeout-text">订单已超时</p>
      </template>

      <!-- 待支付 -->
      <template v-else>
        <h2 class="order-name">{{ data.order.name }}</h2>
        <p class="order-amount">¥ {{ data.order.money }}</p>
        <img
          v-if="data.qrcode_url"
          :src="data.qrcode_url"
          alt="收款码"
          class="qrcode-img"
        />
        <div class="waiting">
          <div class="spinner small"></div>
          <span>等待支付中...</span>
        </div>
        <p class="order-no">订单号: {{ data.order.trade_no }}</p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import type { PayPageData } from '@/types'

const route = useRoute()
const tradeNo = route.params.tradeNo as string
const data = ref<PayPageData | null>(null)
const status = ref(0)
const loading = ref(true)
const error = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

const publicApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 10000,
})

onMounted(async () => {
  try {
    const res = await publicApi.get(`/v1/pay/${tradeNo}`)
    if (res.data.code === 1) {
      data.value = res.data
      status.value = res.data.order.status
      if (status.value === 0) startPolling()
    } else {
      error.value = res.data.msg || '订单不存在'
    }
  } catch {
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
})

function startPolling() {
  pollTimer = setInterval(async () => {
    try {
      const res = await publicApi.get(`/v1/api/order/status/${tradeNo}`)
      if (res.data.code === 1) {
        status.value = res.data.status
        if (res.data.status !== 0) {
          stopPolling()
          if (res.data.status === 1 && data.value?.return_url) {
            setTimeout(() => {
              window.location.href = data.value!.return_url
            }, 3000)
          }
        }
      }
    } catch {
      /* 忽略轮询错误，继续下次 */
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onUnmounted(stopPolling)
</script>

<style scoped>
.pay-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  padding: 20px;
}

.pay-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  padding: 40px 32px;
  text-align: center;
  max-width: 400px;
  width: 100%;
}

.order-name {
  font-size: 18px;
  color: #333;
  margin: 0 0 12px;
  font-weight: 500;
}

.order-amount {
  font-size: 32px;
  color: #e6a23c;
  font-weight: 700;
  margin: 0 0 24px;
}

.qrcode-img {
  width: 220px;
  height: 220px;
  object-fit: contain;
  border: 1px solid #eee;
  border-radius: 8px;
  margin-bottom: 20px;
}

.waiting {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #909399;
  font-size: 14px;
  margin-bottom: 16px;
}

.order-no {
  font-size: 12px;
  color: #c0c4cc;
  margin: 0;
}

.status-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 700;
  margin: 0 auto 16px;
  color: #fff;
}

.success-icon {
  background: #67c23a;
}

.timeout-icon {
  background: #f56c6c;
}

.error-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #f56c6c;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 700;
  margin: 0 auto 16px;
  color: #fff;
}

.status-text {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 8px;
}

.success-text {
  color: #67c23a;
}

.timeout-text {
  color: #f56c6c;
}

.error-text {
  color: #f56c6c;
  font-size: 16px;
}

.redirect-hint {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.loading-text {
  color: #909399;
  font-size: 14px;
  margin: 12px 0 0;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e4e7ed;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}

.spinner.small {
  width: 16px;
  height: 16px;
  border-width: 2px;
  margin: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
