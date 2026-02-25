<template>
  <div class="docs-page">
    <el-row :gutter="20">
      <!-- 左侧文档列表 -->
      <el-col :span="6">
        <el-card shadow="never">
          <template #header>
            <span>文档列表</span>
          </template>
          <el-menu
            :default-active="activeKey"
            @select="handleSelect"
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
        <el-card shadow="never">
          <div v-if="loading" v-loading="true" style="min-height: 200px" />
          <div
            v-else-if="htmlContent"
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
import { ref, onMounted } from 'vue'
import { Document } from '@element-plus/icons-vue'
import { marked } from 'marked'
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

function docKey(doc: DocItem) {
  return `${doc.source}:${doc.filename}`
}

function parseKey(key: string): { source: string; filename: string } {
  const idx = key.indexOf(':')
  return { source: key.substring(0, idx), filename: key.substring(idx + 1) }
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

.markdown-body {
  line-height: 1.8;
  font-size: 18px;
  color: #303133;
}

.markdown-body :deep(h1) {
  font-size: 32px;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 10px;
  margin-bottom: 16px;
}

.markdown-body :deep(h2) {
  font-size: 26px;
  margin-top: 24px;
  margin-bottom: 12px;
}

.markdown-body :deep(h3) {
  font-size: 21px;
  margin-top: 20px;
  margin-bottom: 8px;
}

.markdown-body :deep(code) {
  background-color: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 16px;
}

.markdown-body :deep(pre) {
  background-color: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
  overflow-x: auto;
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 8px 12px;
  text-align: left;
}

.markdown-body :deep(th) {
  background-color: #f5f7fa;
  font-weight: 600;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid #409eff;
  padding: 8px 16px;
  margin: 12px 0;
  background-color: #f0f9ff;
  color: #606266;
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
