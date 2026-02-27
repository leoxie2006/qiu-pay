<template>
  <div v-loading="loading" class="dashboard">
    <template v-if="data">
      <!-- 今日统计 -->
      <h3 class="section-title acc-bg-teal" style="padding: 4px 12px; border: 2px solid #000;">今日统计</h3>
      <el-row :gutter="24" class="stat-row">
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-sky clickable-card" @click="showDetail('今日总订单数', data.today_stats.total, '今日创建的所有订单总数（含待支付、已支付、已超时）')">
            <div class="stat-label">总订单数</div>
            <div class="stat-value">{{ data.today_stats.total }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-slate clickable-card" @click="showDetail('今日成功数', data.today_stats.success, '今日已成功支付的订单数量', `成功率: ${data.today_stats.total ? ((data.today_stats.success / data.today_stats.total) * 100).toFixed(1) : 0}%`)">
            <div class="stat-label">成功数</div>
            <div class="stat-value success">{{ data.today_stats.success }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-indigo clickable-card" @click="showDetail('今日金额', `¥${data.today_stats.amount}`, '今日成功支付的总金额', `平均单笔: ¥${data.today_stats.success ? (data.today_stats.amount / data.today_stats.success).toFixed(2) : '0.00'}`)">
            <div class="stat-label">金额</div>
            <div class="stat-value amount">¥{{ data.today_stats.amount }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 昨日统计 -->
      <h3 class="section-title acc-bg-sky" style="padding: 4px 12px; border: 2px solid #000;">昨日统计</h3>
      <el-row :gutter="24" class="stat-row">
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-white clickable-card" @click="showDetail('昨日总订单数', data.yesterday_stats.total, '昨日创建的所有订单总数')">
            <div class="stat-label">总订单数</div>
            <div class="stat-value">{{ data.yesterday_stats.total }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-white clickable-card" @click="showDetail('昨日成功数', data.yesterday_stats.success, '昨日已成功支付的订单数量', `成功率: ${data.yesterday_stats.total ? ((data.yesterday_stats.success / data.yesterday_stats.total) * 100).toFixed(1) : 0}%`)">
            <div class="stat-label">成功数</div>
            <div class="stat-value success">{{ data.yesterday_stats.success }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-white clickable-card" @click="showDetail('昨日金额', `¥${data.yesterday_stats.amount}`, '昨日成功支付的总金额', `平均单笔: ¥${data.yesterday_stats.success ? (data.yesterday_stats.amount / data.yesterday_stats.success).toFixed(2) : '0.00'}`)">
            <div class="stat-label">金额</div>
            <div class="stat-value amount">¥{{ data.yesterday_stats.amount }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 总体统计 -->
      <h3 class="section-title acc-bg-slate" style="padding: 4px 12px; border: 2px solid #000;">总体统计</h3>
      <el-row :gutter="24" class="stat-row">
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-gray clickable-card" @click="showDetail('总订单数', data.total_stats.total, '平台创建以来的所有订单总数')">
            <div class="stat-label">总订单数</div>
            <div class="stat-value">{{ data.total_stats.total }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-gray clickable-card" @click="showDetail('总成功数', data.total_stats.success, '平台累计成功支付的订单数量', `总成功率: ${data.total_stats.total ? ((data.total_stats.success / data.total_stats.total) * 100).toFixed(1) : 0}%`)">
            <div class="stat-label">成功数</div>
            <div class="stat-value success">{{ data.total_stats.success }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-gray clickable-card" @click="showDetail('总金额', `¥${data.total_stats.amount}`, '平台累计成功支付的总金额', `平均单笔: ¥${data.total_stats.success ? (data.total_stats.amount / data.total_stats.success).toFixed(2) : '0.00'}`)">
            <div class="stat-label">金额</div>
            <div class="stat-value amount">¥{{ data.total_stats.amount }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 趋势图 -->
      <!-- 趋势图 -->
      <h3 class="section-title acc-bg-indigo" style="padding: 4px 12px; border: 2px solid #000;">近 7 天趋势</h3>
      <el-card shadow="never" class="chart-card brutalist-card acc-bg-white">
        <div id="trend-chart" class="trend-chart"></div>
      </el-card>

      <!-- 最近订单 -->
      <h3 class="section-title acc-bg-violet" style="padding: 4px 12px; border: 2px solid #000; color: #000;">最近 10 条订单</h3>
      <el-card shadow="never" class="brutalist-card table-card acc-bg-white">
        <el-table :data="data.recent_orders" stripe style="width: 100%">
          <el-table-column prop="trade_no" label="订单号" min-width="180" />
          <el-table-column prop="merchant_id" label="商户ID" width="80" />
          <el-table-column prop="name" label="商品名称" min-width="120" />
          <el-table-column prop="money" label="金额" width="100">
            <template #default="{ row }">¥{{ row.money }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" min-width="160" />
        </el-table>
      </el-card>

      <!-- 平台信息 -->
      <h3 class="section-title acc-bg-white" style="padding: 4px 12px; border: 2px solid #000;">平台信息</h3>
      <el-row :gutter="24" class="stat-row">
        <el-col :span="8">
          <el-card shadow="never" class="brutalist-card acc-bg-teal clickable-card" @click="router.push({ name: 'Merchants' })">
            <div class="stat-label">商户数量 <span style="font-size:12px; opacity:0.6;">→ 点击管理</span></div>
            <div class="stat-value">{{ data.platform.merchant_count }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 详情弹窗 -->
      <el-dialog
        v-model="detailVisible"
        :title="detailTitle"
        width="420px"
        class="brutalist-dialog"
        :close-on-click-modal="true"
      >
        <div class="detail-content">
          <div class="detail-value">{{ detailValue }}</div>
          <div class="detail-desc">{{ detailDesc }}</div>
          <div v-if="detailExtra" class="detail-extra">{{ detailExtra }}</div>
        </div>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { DashboardData } from '@/types'
import * as echarts from 'echarts'

const router = useRouter()
const data = ref<DashboardData | null>(null)
const loading = ref(true)

const detailVisible = ref(false)
const detailTitle = ref('')
const detailValue = ref<string | number>('')
const detailDesc = ref('')
const detailExtra = ref('')

function showDetail(title: string, value: string | number, desc: string, extra = '') {
  detailTitle.value = title
  detailValue.value = value
  detailDesc.value = desc
  detailExtra.value = extra
  detailVisible.value = true
}

const STATUS_MAP: Record<number, string> = { 0: '待支付', 1: '已支付', 2: '已超时' }

function statusText(status: number): string {
  return STATUS_MAP[status] ?? '未知'
}

function statusTagType(status: number): '' | 'success' | 'info' | 'warning' | 'danger' {
  if (status === 1) return 'success'
  if (status === 2) return 'info'
  return 'warning'
}

onMounted(async () => {
  try {
    const res = await api.get('/v1/admin/dashboard')
    if (res.data.code === 1) {
      data.value = res.data
      await nextTick()
      initChart(res.data.chart)
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  } finally {
    loading.value = false
  }
})

function initChart(chart: DashboardData['chart']) {
  const el = document.getElementById('trend-chart')
  if (!el) return
  const instance = echarts.init(el)
  instance.setOption({
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#000', borderWidth: 2, textStyle: { color: '#000', fontWeight: 'bold' } },
    legend: { data: ['订单数', '金额'] },
    xAxis: { type: 'category', data: chart.labels, axisLine: { lineStyle: { color: '#000', width: 2 } } },
    yAxis: [
      { type: 'value', name: '订单数', axisLine: { lineStyle: { color: '#000', width: 2 } } },
      { type: 'value', name: '金额', axisLine: { lineStyle: { color: '#000', width: 2 } } },
    ],
    series: [
      { name: '订单数', type: 'bar', data: chart.order_counts, itemStyle: { color: '#334155', borderColor: '#000', borderWidth: 2 } },
      { name: '金额', type: 'line', yAxisIndex: 1, data: chart.amounts, symbolSize: 8, itemStyle: { color: '#64748b', borderWidth: 2, borderColor: '#000' }, lineStyle: { width: 4, color: '#64748b' } },
    ],
  })
}
</script>

<style scoped>
.dashboard {
  min-height: 200px;
}

.section-title {
  margin: 30px 0 16px;
  font-size: 20px;
  font-weight: 900;
  color: #000;
  border-bottom: 4px solid #000;
  box-shadow: 4px 4px 0 0 #cbd5e1;
  display: inline-block;
}

.section-title:first-child {
  margin-top: 0;
}

.stat-row {
  margin-bottom: 30px;
}

.brutalist-card {
  box-shadow: 8px 8px 0 0 #cbd5e1 !important;
  transition: transform 0.2s, box-shadow 0.2s;
}

.brutalist-card:hover {
  transform: translate(-2px, -2px);
  box-shadow: 12px 12px 0 0 #cbd5e1 !important;
}

.clickable-card {
  cursor: pointer;
}

.clickable-card:active {
  transform: translate(4px, 4px) !important;
  box-shadow: 0 0 0 0 #cbd5e1 !important;
}

.stat-label {
  font-size: 14px;
  font-weight: 900;
  color: #000;
  margin-bottom: 12px;
  text-transform: uppercase;
}

.stat-value {
  font-size: 36px;
  font-weight: 900;
  color: #000;
  letter-spacing: -1px;
}

.table-card {
  padding: 0 !important;
}

.chart-card {
  margin-bottom: 30px;
}

.trend-chart {
  width: 100%;
  height: 350px;
}

.detail-content {
  text-align: center;
  padding: 16px 0;
}

.detail-value {
  font-size: 48px;
  font-weight: 900;
  color: #000;
  letter-spacing: -1px;
  margin-bottom: 12px;
}

.detail-desc {
  font-size: 15px;
  color: #333;
  font-weight: 600;
  margin-bottom: 8px;
}

.detail-extra {
  font-size: 18px;
  font-weight: 900;
  color: #000;
  margin-top: 12px;
  padding: 8px 16px;
  border: 2px solid #000;
  display: inline-block;
  background: #e0f2fe;
}
</style>
