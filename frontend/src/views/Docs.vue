<template>
  <div class="docs-page">
    <el-row :gutter="20">
      <!-- 左侧文档列表 -->
      <el-col :span="6">
        <el-card shadow="never" class="brutalist-card acc-bg-slate">
          <template #header>
            <div class="card-header-title acc-bg-white" style="display:inline-block; padding: 4px 12px; border: 2px solid #000;">文档列表</div>
          </template>
          <el-menu
            :default-active="activeKey"
            @select="handleSelect"
            class="brutalist-menu"
          >
            <el-menu-item
              v-for="doc in docList"
              :key="docKey(doc)"
              :index="docKey(doc)"
            >
              <el-icon><Document /></el-icon>
              <span>{{ doc.title }}</span>
            </el-menu-item>
          </el-menu>
          <el-empty v-if="docList.length === 0" description="暂无文档" />
        </el-card>
      </el-col>

      <!-- 右侧文档内容 -->
      <el-col :span="18">
        <el-card shadow="never" class="brutalist-card acc-bg-white">
          <div v-if="loading" v-loading="true" style="min-height: 200px" />
          <div
            v-else-if="htmlContent"
            ref="contentRef"
            class="markdown-body"
            v-html="htmlContent"
          />
          <el-empty v-else description="请从左侧选择文档" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { Document } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'
import api from '@/api'

interface DocItem {
  filename: string
  title: string
  source: string
}

const docList = ref<DocItem[]>([])
const activeKey = ref('')
const htmlContent = ref('')
const loading = ref(false)
const contentRef = ref<HTMLElement | null>(null)

function docKey(doc: DocItem) {
  return `${doc.source}:${doc.filename}`
}

function parseKey(key: string): { source: string; filename: string } {
  const idx = key.indexOf(':')
  return { source: key.substring(0, idx), filename: key.substring(idx + 1) }
}

function addCopyButtons() {
  if (!contentRef.value) return
  const pres = contentRef.value.querySelectorAll('pre')
  pres.forEach((pre) => {
    if (pre.querySelector('.copy-btn')) return
    const wrapper = document.createElement('div')
    wrapper.className = 'code-block-wrapper'
    pre.parentNode?.insertBefore(wrapper, pre)
    wrapper.appendChild(pre)

    const btn = document.createElement('button')
    btn.className = 'copy-btn'
    btn.textContent = '复制'
    btn.addEventListener('click', () => {
      const code = pre.querySelector('code')?.textContent || pre.textContent || ''
      navigator.clipboard.writeText(code).then(() => {
        btn.textContent = '已复制'
        setTimeout(() => { btn.textContent = '复制' }, 1500)
      }).catch(() => {
        ElMessage.error('复制失败')
      })
    })
    wrapper.appendChild(btn)
  })
}

async function fetchDocList() {
  try {
    const { data } = await api.get('/api/admin/docs/list')
    if (data.code === 0) {
      docList.value = data.data
      if (docList.value.length > 0) {
        handleSelect(docKey(docList.value[0]))
      }
    }
  } catch (e) {
    console.error('获取文档列表失败', e)
  }
}

async function handleSelect(key: string) {
  activeKey.value = key
  const { source, filename } = parseKey(key)
  loading.value = true
  try {
    const { data } = await api.get('/api/admin/docs/content', {
      params: { filename, source },
    })
    if (data.code === 0) {
      htmlContent.value = marked(data.data.content) as string
      await nextTick()
      addCopyButtons()
    }
  } catch (e) {
    htmlContent.value = '<p style="color:red">加载文档失败</p>'
  } finally {
    loading.value = false
  }
}

onMounted(fetchDocList)
</script>

<style scoped>
.docs-page {
  padding: 0;
}

.brutalist-card {
  border: 4px solid #000 !important;
  box-shadow: 8px 8px 0 0 #cbd5e1 !important;
  border-radius: 0;
}

.card-header-title {
  font-weight: 900;
  font-size: 16px;
  text-transform: uppercase;
}

.brutalist-menu {
  border-right: none;
}

/* markdown reset for swiss brutalism */
.markdown-body {
  line-height: 1.6;
  font-size: 16px;
  color: #000;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: -0.5px;
  color: #000;
}

.markdown-body :deep(h1) {
  font-size: 42px;
  border-bottom: 4px solid #000;
  padding-bottom: 10px;
  margin-bottom: 24px;
}

.markdown-body :deep(h2) {
  font-size: 32px;
  margin-top: 32px;
  margin-bottom: 16px;
}

.markdown-body :deep(h3) {
  font-size: 24px;
  margin-top: 24px;
  margin-bottom: 12px;
}

.markdown-body :deep(code) {
  background-color: #fff;
  border: 2px solid #000;
  font-weight: bold;
  padding: 2px 6px;
  font-size: 14px;
}

.markdown-body :deep(pre) {
  background-color: #000;
  color: #fff;
  padding: 16px;
  border: 4px solid #000;
  box-shadow: 4px 4px 0 0 #cbd5e1;
  overflow-x: auto;
  border-radius: 0;
  margin: 0;
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  border: none;
}

.markdown-body :deep(.code-block-wrapper) {
  position: relative;
  margin: 16px 0;
}

.markdown-body :deep(.copy-btn) {
  position: absolute;
  top: 8px;
  right: 8px;
  background: #fff;
  color: #000;
  border: 2px solid #fff;
  padding: 4px 12px;
  font-weight: 900;
  font-size: 12px;
  text-transform: uppercase;
  cursor: pointer;
  font-family: var(--font-swiss);
  transition: transform 0.1s, box-shadow 0.1s;
  box-shadow: 2px 2px 0 0 rgba(255,255,255,0.3);
}

.markdown-body :deep(.copy-btn:hover) {
  background: #e0f2fe;
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 0 rgba(255,255,255,0.3);
}

.markdown-body :deep(.copy-btn:active) {
  transform: translate(2px, 2px);
  box-shadow: 0 0 0 0;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 20px 0;
  border: 4px solid #000;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 2px solid #000;
  padding: 12px 16px;
  text-align: left;
}

.markdown-body :deep(th) {
  background-color: #000;
  color: #fff;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.markdown-body :deep(blockquote) {
  border-left: 8px solid #000;
  padding: 16px;
  margin: 20px 0;
  background-color: #fff;
  color: #000;
  font-weight: bold;
  font-style: italic;
  box-shadow: 4px 4px 0 0 #cbd5e1;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

.markdown-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  margin: 8px 0;
}
</style>
