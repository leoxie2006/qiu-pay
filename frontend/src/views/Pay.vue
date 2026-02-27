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
    <div v-else-if="data" class="pay-card acc-bg-white">
      <div class="card-header acc-bg-slate">
        <h2 style="color: #000;">支付</h2>
      </div>
      
      <!-- 支付成功 -->
      <template v-if="status === 1">
        <div class="status-icon success-icon acc-bg-teal" style="color: #000; border-color: #000;">✓</div>
        <p class="status-text success-text">支付成功</p>
        <p class="redirect-hint" v-if="data.return_url">3 秒后自动跳转...</p>
      </template>

      <!-- 订单已超时 -->
      <template v-else-if="status === 2">
        <div class="status-icon timeout-icon acc-bg-white">!</div>
        <p class="status-text timeout-text">订单已超时</p>
      </template>

      <!-- 待支付 -->
      <template v-else>
        <div class="order-details-box">
          <p class="order-name">{{ data.order.name }}</p>
          <p class="order-amount">¥ {{ data.order.money }}</p>
        </div>
        <img
          v-if="data.qrcode_url"
          :src="data.qrcode_url"
          alt="收款码"
          class="qrcode-img"
        />
        <div class="waiting">
          <div class="spinner small" style="border-top-color: #64748b;"></div>
          <span>等待支付中...</span>
        </div>
        <div class="order-no-box acc-bg-sky">
          <p class="order-no" style="color: #000;">订单号: {{ data.order.trade_no }}</p>
        </div>
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
  background-color: #fff;
  background-image: radial-gradient(#000 1px, transparent 1px);
  background-size: 20px 20px;
  padding: 20px;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}

.pay-card {
  background: #fff;
  border: 4px solid #000;
  box-shadow: 16px 16px 0 0 #cbd5e1;
  padding: 0;
  text-align: center;
  max-width: 420px;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  background: #f1f5f9;
  color: #000;
  padding: 20px;
  border-bottom: 4px solid #000;
}

.card-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 900;
  letter-spacing: 2px;
}

.order-details-box {
  padding: 30px;
  border-bottom: 4px solid #000;
}

.order-name {
  font-size: 18px;
  color: #000;
  margin: 0 0 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.order-amount {
  font-size: 48px;
  color: #000;
  font-weight: 900;
  margin: 0;
  letter-spacing: -2px;
}

.qrcode-img {
  width: 240px;
  height: 240px;
  object-fit: contain;
  border: 4px solid #000;
  box-shadow: 6px 6px 0 0 #cbd5e1;
  margin: 30px auto 20px;
  display: block;
}

.waiting {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #000;
  font-size: 14px;
  font-weight: 900;
  margin-bottom: 30px;
}

.order-no-box {
  background: #000;
  padding: 12px;
  color: #fff;
}

.order-no {
  font-size: 14px;
  font-weight: bold;
  margin: 0;
  font-family: monospace;
}

.status-icon {
  width: 80px;
  height: 80px;
  border: 4px solid #000;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 900;
  margin: 40px auto 20px;
  color: #fff;
  box-shadow: 4px 4px 0 0 #cbd5e1;
}

.success-icon {
  background: #000;
  color: #fff;
}

.timeout-icon {
  background: #fff;
  color: #000;
}

.error-icon {
  width: 80px;
  height: 80px;
  border: 4px solid #000;
  background: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 900;
  margin: 40px auto 20px;
  color: #fff;
  box-shadow: 8px 8px 0 0 #cbd5e1;
}

.status-text {
  font-size: 24px;
  font-weight: 900;
  margin: 0 0 16px;
  color: #000;
}

.error-text {
  color: #000;
  font-size: 18px;
  font-weight: bold;
  padding: 0 20px 40px;
}

.redirect-hint {
  color: #000;
  font-size: 16px;
  font-weight: bold;
  margin: 0 0 40px;
}

.loading-text {
  color: #000;
  font-size: 16px;
  font-weight: 900;
  margin: 20px 0 40px;
  text-transform: uppercase;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #000;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 40px auto 0;
}

.spinner.small {
  width: 20px;
  height: 20px;
  border-width: 3px;
  margin: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
