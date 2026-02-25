<template>
  <div v-loading="loading" class="orders">
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input v-model="filters.pid" placeholder="商户ID" clearable style="width: 120px" />
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 120px">
        <el-option label="待支付" value="0" />
        <el-option label="已支付" value="1" />
        <el-option label="已超时" value="2" />
      </el-select>
      <el-input v-model="filters.trade_no" placeholder="订单号" clearable style="width: 200px" />
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        @change="onDateChange"
      />
      <el-button type="primary" @click="handleSearch">搜索</el-button>
      <el-button @click="exportCSV">导出 CSV</el-button>
    </div>

    <!-- 订单表格 -->
    <el-table :data="orders" stripe style="width: 100%" @row-click="(row: OrderBrief) => viewDetail(row.trade_no)">
      <el-table-column prop="trade_no" label="订单号" min-width="180" />
      <el-table-column prop="out_trade_no" label="外部订单号" min-width="180" />
      <el-table-column prop="merchant_id" label="商户ID" width="80" />
      <el-table-column prop="type" label="类型" width="80" />
      <el-table-column prop="name" label="商品名" min-width="120" />
      <el-table-column prop="money" label="金额" width="100">
        <template #default="{ row }">¥{{ row.money }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ STATUS_MAP[row.status] || '未知' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="160" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 0"
            type="warning"
            size="small"
            link
            @click.stop="renotifyOrder(row.trade_no)"
          >回调</el-button>
          <el-button
            v-if="row.status === 0"
            type="danger"
            size="small"
            link
            @click.stop="cancelOrder(row.trade_no)"
          >取消</el-button>
          <el-button
            v-if="row.status === 1"
            type="primary"
            size="small"
            link
            @click.stop="renotifyOrder(row.trade_no)"
          >回调</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="20"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import type { OrderBrief } from '@/types'

const router = useRouter()
const orders = ref<OrderBrief[]>([])
const total = ref(0)
const currentPage = ref(1)
const loading = ref(true)
const dateRange = ref<[string, string] | null>(null)

const filters = reactive({
  pid: '',
  status: '',
  trade_no: '',
  start_date: '',
  end_date: '',
})

const STATUS_MAP: Record<number, string> = { 0: '待支付', 1: '已支付', 2: '已超时' }

function statusTagType(status: number) {
  if (status === 1) return 'success'
  if (status === 2) return 'info'
  return 'warning'
}

function onDateChange(val: [string, string] | null) {
  if (val) {
    filters.start_date = val[0]
    filters.end_date = val[1]
  } else {
    filters.start_date = ''
    filters.end_date = ''
  }
}

async function loadOrders(page = 1) {
  loading.value = true
  try {
    const params = { ...filters, page, per_page: 20 }
    const res = await api.get('/v1/admin/orders', { params })
    if (res.data.code === 1) {
      orders.value = res.data.orders
      total.value = res.data.total
      currentPage.value = res.data.page
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  loadOrders(1)
}

function onPageChange(page: number) {
  loadOrders(page)
}

function viewDetail(tradeNo: string) {
  router.push(`/admin/orders/${tradeNo}`)
}

async function cancelOrder(tradeNo: string) {
  try {
    await ElMessageBox.confirm('确定要取消该订单吗？', '取消订单', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const res = await api.post(`/v1/admin/orders/${tradeNo}/cancel`)
    if (res.data.code === 1) {
      ElMessage.success(res.data.msg)
      loadOrders(currentPage.value)
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

async function renotifyOrder(tradeNo: string) {
  try {
    await ElMessageBox.confirm('确定要重新发送回调通知吗？', '重新回调', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info',
    })
    const res = await api.post(`/v1/admin/orders/${tradeNo}/renotify`)
    if (res.data.code === 1) {
      ElMessage.success(res.data.msg)
      loadOrders(currentPage.value)
    } else {
      ElMessage.error(res.data.msg || '操作失败')
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

async function exportCSV() {
  try {
    const res = await api.get('/v1/admin/orders/export', {
      params: filters,
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = 'orders.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('网络请求失败，请检查网络连接')
  }
}

onMounted(() => loadOrders())
</script>

<style scoped>
.orders {
  min-height: 200px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
