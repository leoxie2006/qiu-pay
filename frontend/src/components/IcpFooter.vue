<template>
  <div v-if="icpRecord" class="icp-footer" :class="customClass">
    <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">{{ icpRecord }}</a>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

defineProps<{
  customClass?: string
}>()

const icpRecord = ref('')

onMounted(async () => {
  try {
    const res = await api.get('/v1/system/info')
    if (res.data && res.data.code === 1) {
      icpRecord.value = res.data.icp_record
    }
  } catch (e) {
    // 忽略错误
  }
})
</script>

<style scoped>
.icp-footer {
  text-align: center;
  font-size: 14px;
  font-weight: 900;
  letter-spacing: 1px;
}

.icp-footer a {
  color: #000;
  text-decoration: none;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.icp-footer a:hover {
  background-color: #000;
  color: #fff;
  border-bottom: 2px solid #000;
}
</style>
