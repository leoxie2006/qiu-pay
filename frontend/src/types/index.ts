export interface ApiResponse {
  code: number
  msg?: string
  [key: string]: any
}

export interface DayStats {
  total: number
  success: number
  amount: number
}

export interface ChartData {
  labels: string[]
  order_counts: number[]
  amounts: number[]
}

export interface DashboardData {
  today_stats: DayStats
  yesterday_stats: DayStats
  total_stats: DayStats
  chart: ChartData
  recent_orders: OrderBrief[]
  platform: PlatformInfo
}

export interface PlatformInfo {
  merchant_count: number
}

export interface Merchant {
  pid: number
  username: string
  email: string
  key: string
  active: number
  money: string
  orders: number
  order_today: number
  created_at: string
}

export interface OrderBrief {
  trade_no: string
  out_trade_no: string
  merchant_id: number
  type: string
  name: string
  original_money: string
  money: string
  status: number
  callback_status: number
  created_at: string
  paid_at: string | null
}

export interface OrderDetail extends OrderBrief {
  status_text: string
  callback_status_text: string
  notify_url: string
  return_url: string
}

export interface CallbackLog {
  id: number
  status_code: number
  response_body: string
  created_at: string
}

export interface PaginatedOrders {
  orders: OrderBrief[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export interface PayPageData {
  order: {
    trade_no: string
    name: string
    money: string
    status: number
    created_at: string
  }
  qrcode_url: string
  return_url: string
}
