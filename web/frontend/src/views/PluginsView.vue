<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NButton, NTag, NPopconfirm, useMessage } from 'naive-ui'
import { get, post } from '../api'

const message = useMessage()
const plugins = ref<any[]>([])
const discovering = ref(false)

const stateTagType = (state: string): 'default' | 'info' | 'success' | 'warning' | 'error' => {
  const map: Record<string, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
    found: 'default', loaded: 'info', enabled: 'success',
    disabled: 'warning', unloaded: 'default', error: 'error',
  }
  return map[state] || 'default'
}

async function load() {
  try {
    plugins.value = await get<any[]>('/plugins')
  } catch (e: any) {
    message.error('获取插件列表失败: ' + e.message)
  }
}

async function discoverPlugins() {
  discovering.value = true
  try {
    const res = await post<any>('/plugins/discover', {})
    message.success(`发现 ${res.discovered?.length || 0} 个新插件`)
    await load()
  } catch (e: any) {
    message.error('扫描失败: ' + e.message)
  } finally {
    discovering.value = false
  }
}

async function doAction(pluginId: string, action: string) {
  try {
    const res = await post<any>(`/plugins/${pluginId}/${action}`, {})
    if (res.status === 'ok') {
      message.success(`${action} 成功`)
    } else {
      message.error(`${action} 失败`)
    }
    await load()
  } catch (e: any) {
    message.error(`${action} 失败: ` + e.message)
  }
}

onMounted(load)
</script>

<template>
  <div class="plugins-view">
    <div class="view-header">
      <h2>🧩 插件管理</h2>
      <n-button type="primary" :loading="discovering" @click="discoverPlugins">🔍 扫描插件</n-button>
    </div>

    <p class="plugins-hint">
      扫描插件目录发现新插件 → 加载 → 启用后自动注册工具与能力 → 在 Agent 权限矩阵中可见。
    </p>

    <div class="plugin-grid">
      <div v-for="p in plugins" :key="p.id" class="plugin-card glass-panel glass-panel-hover">
        <div class="plugin-head">
          <span class="plugin-name">{{ p.name }}</span>
          <n-tag size="small" :type="stateTagType(p.state)" :bordered="false">{{ p.state }}</n-tag>
          <span class="plugin-ver">v{{ p.version }}</span>
        </div>
        <div class="plugin-desc">{{ p.description }}</div>
        <div v-if="p.error_message" class="plugin-error">{{ p.error_message }}</div>
        <div class="plugin-ops">
          <n-button v-if="p.state === 'found'" size="tiny" type="primary" secondary
                    @click="doAction(p.id, 'load')">加载</n-button>
          <n-button v-if="p.state === 'loaded' || p.state === 'disabled'" size="tiny" type="primary"
                    @click="doAction(p.id, 'enable')">启用</n-button>
          <n-button v-if="p.state === 'enabled'" size="tiny" type="warning"
                    @click="doAction(p.id, 'disable')">禁用</n-button>
          <n-button v-if="p.state === 'enabled'" size="tiny"
                    @click="doAction(p.id, 'reload')">重载</n-button>
          <n-popconfirm v-if="['loaded','disabled','error'].includes(p.state)"
                        @positive-click="doAction(p.id, 'unload')">
            <template #trigger>
              <n-button size="tiny" type="error" quaternary>卸载</n-button>
            </template>
            确认卸载插件「{{ p.name }}」？
          </n-popconfirm>
        </div>
      </div>

      <div v-if="!plugins.length" class="empty-state glass-panel">
        <p>暂无插件，点击右上角「扫描插件」发现可用插件</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.view-header h2 { font-family: 'Noto Serif SC', serif; }
.plugins-hint { font-size: 12.5px; color: var(--moon-dim); margin-bottom: 14px; }

.plugin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.plugin-card { padding: 14px 16px; }
.plugin-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.plugin-name { font-weight: 600; font-size: 15px; }
.plugin-ver { font-size: 12px; color: var(--moon-dim); }

.plugin-desc {
  font-size: 13px; color: var(--moon-dim);
  margin-bottom: 8px;
}

.plugin-error {
  font-size: 12px; color: var(--alert);
  background: rgba(217, 106, 95, 0.08);
  border-radius: 6px; padding: 4px 8px; margin-bottom: 8px;
}

.plugin-ops { display: flex; gap: 6px; flex-wrap: wrap; }

.empty-state { padding: 40px; text-align: center; color: var(--moon-dim); grid-column: 1 / -1; }
</style>
