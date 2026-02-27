<template>
  <div v-loading="loading" class="dashboard">
    <template v-if="data">
      <!-- 今日统计 -->
      <h3 class="section-title">今日统计</h3>
      <el-row :gutter="16" class="stat-row">
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">总订单数</div>
            <div class="stat-value">{{ data.today_stats.total }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">成功数</div>
            <div class="stat-value success">{{ data.today_stats.success }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">金额</div>
            <div class="stat-value amount">¥{{ data.today_stats.amount }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 昨日统计 -->
      <h3 class="section-title">昨日统计</h3>
      <el-row :gutter="16" class="stat-row">
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">总订单数</div>
            <div class="stat-value">{{ data.yesterday_stats.total }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">成功数</div>
            <div class="stat-value success">{{ data.yesterday_stats.success }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">金额</div>
            <div class="stat-value amount">¥{{ data.yesterday_stats.amount }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 总体统计 -->
      <h3 class="section-title">总体统计</h3>
      <el-row :gutter="16" class="stat-row">
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">总订单数</div>
            <div class="stat-value">{{ data.total_stats.total }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">成功数</div>
            <div class="stat-value success">{{ data.total_stats.success }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">金额</div>
            <div class="stat-value amount">¥{{ data.total_stats.amount }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 趋势图 -->
      <h3 class="section-title">近 7 天趋势</h3>
      <el-card class="chart-card">
        <div id="trend-chart" class="trend-chart"></div>
      </el-card>

      <!-- 最近订单 -->
      <h3 class="section-title">最近 10 条订单</h3>
      <el-card>
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
      <h3 class="section-title">平台信息</h3>
      <el-row :gutter="16" class="stat-row">
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">商户数量</div>
            <div class="stat-value">{{ data.platform.merchant_count }}</div>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { DashboardData } from '@/types'
import * as echarts from 'echarts'

const data = ref<DashboardData | null>(null)
const loading = ref(true)

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
    tooltip: { trigger: 'axis' },
    legend: { data: ['订单数', '金额'] },
    xAxis: { type: 'category', data: chart.labels },
    yAxis: [
      { type: 'value', name: '订单数' },
      { type: 'value', name: '金额' },
    ],
    series: [
      { name: '订单数', type: 'bar', data: chart.order_counts },
      { name: '金额', type: 'line', yAxisIndex: 1, data: chart.amounts },
    ],
  })
}
</script>

<style scoped>
.dashboard {
  min-height: 200px;
}

.section-title {
  margin: 20px 0 12px;
  font-size: 16px;
  color: #303133;
}

.section-title:first-child {
  margin-top: 0;
}

.stat-row {
  margin-bottom: 8px;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-value.success {
  color: #67c23a;
}

.stat-value.amount {
  color: #e6a23c;
}

.chart-card {
  margin-bottom: 8px;
}

.trend-chart {
  width: 100%;
  height: 350px;
}
</style>
