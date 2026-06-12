<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  NButton, NModal, NForm, NFormItem, NInput, NTag, NPopconfirm,
  NDynamicInput, useMessage,
} from 'naive-ui'
import { get, post, put, del } from '../api'

const message = useMessage()
const servers = ref<any[]>([])
const showForm = ref(false)
const isCreate = ref(true)
const form = ref<any>({})
const busy = ref('')
const showImport = ref(false)
const importJson = ref('')
const importing = ref(false)

const IMPORT_PLACEHOLDER = `支持标准 mcpServers 格式，直接从文档复制粘贴：
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
      "env": { "KEY": "value" }
    }
  }
}`

async function runImport() {
  let parsed: any
  try {
    parsed = JSON.parse(importJson.value)
  } catch {
    message.error('JSON 解析失败，请检查格式')
    return
  }
  // 兼容 {mcpServers: {...}} / 裸 {name: {command...}} / 单个 {name, command}
  let entries: Array<[string, any]>
  if (parsed.mcpServers && typeof parsed.mcpServers === 'object') {
    entries = Object.entries(parsed.mcpServers)
  } else if (parsed.command && parsed.name) {
    entries = [[parsed.name, parsed]]
  } else if (typeof parsed === 'object' && !Array.isArray(parsed)) {
    entries = Object.entries(parsed)
  } else {
    message.error('未识别的结构：需要 mcpServers 对象或 {name: {command, ...}}')
    return
  }
  const bad = entries.find(([, v]) => !v || typeof v.command !== 'string')
  if (bad) {
    message.error(`"${bad[0]}" 缺少 command 字段`)
    return
  }
  importing.value = true
  let ok = 0
  const errors: string[] = []
  for (const [name, v] of entries) {
    try {
      await post('/mcp/servers', {
        name,
        command: v.command,
        args: (v.args || []).map(String),
        env: v.env || {},
      })
      ok++
    } catch (e: any) {
      errors.push(`${name}: ${e.message}`)
    }
  }
  importing.value = false
  if (ok) message.success(`成功导入 ${ok} 个 MCP server ✓`)
  for (const err of errors) message.error(err)
  if (ok && !errors.length) {
    showImport.value = false
    importJson.value = ''
  }
  await load()
}

onMounted(load)

async function load() {
  try {
    servers.value = await get<any[]>('/mcp/servers')
  } catch (e: any) {
    message.error(e.message)
  }
}

function openForm(server: any | null) {
  isCreate.value = !server
  form.value = server
    ? {
        name: server.name,
        command: server.command,
        args: [...(server.args || [])],
        env: Object.entries(server.env_keys || []).map(() => ({ key: '', value: '' })),
      }
    : { name: '', command: '', args: [], env: [] }
  showForm.value = true
}

async function save() {
  const body = {
    name: form.value.name,
    command: form.value.command,
    args: (form.value.args || []).filter((a: string) => a),
    env: Object.fromEntries(
      (form.value.env || []).filter((e: any) => e?.key).map((e: any) => [e.key, e.value])),
  }
  try {
    if (isCreate.value) {
      const data = await post('/mcp/servers', body)
      message.success(data.status === 'running'
        ? `已启动，发现 ${data.tool_names.length} 个工具 ✓`
        : `已保存但启动失败：${data.last_error}`)
    } else {
      await put(`/mcp/servers/${form.value.name}`, body)
      message.success('已更新并重启 ✓')
    }
    showForm.value = false
    await load()
  } catch (e: any) {
    message.error(e.message)
  }
}

async function lifecycle(name: string, action: 'start' | 'stop' | 'restart') {
  busy.value = `${name}:${action}`
  try {
    await post(`/mcp/servers/${name}/${action}`)
    message.success(`${name} ${action} 完成 ✓`)
    await load()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    busy.value = ''
  }
}

async function remove(name: string) {
  try {
    await del(`/mcp/servers/${name}`, true)
    message.success('已删除')
    await load()
  } catch (e: any) {
    message.error(e.message)
  }
}

const statusType: Record<string, any> = { running: 'success', stopped: 'default', error: 'error' }
</script>

<template>
  <div class="mcp-view">
    <div class="view-header">
      <h2>🔌 MCP 服务</h2>
      <div style="display:flex; gap:8px">
        <n-button type="primary" @click="showImport = true">📋 粘贴 JSON 导入</n-button>
        <n-button @click="openForm(null)">＋ 手动新增</n-button>
      </div>
    </div>

    <p class="mcp-hint">
      新增 server → 启动握手 → 工具自动注册（source=mcp:名称）→ 出现在工具页与各 Agent 权限矩阵中。
    </p>

    <div class="server-grid">
      <div v-for="s in servers" :key="s.name" class="server-card glass-panel glass-panel-hover">
        <div class="server-head">
          <span class="server-name">{{ s.name }}</span>
          <n-tag size="small" :type="statusType[s.status]" :bordered="false">{{ s.status }}</n-tag>
        </div>
        <div class="server-cmd mono">{{ s.command }} {{ (s.args || []).join(' ') }}</div>
        <div v-if="s.last_error" class="server-error">{{ s.last_error }}</div>
        <div class="server-tools">
          <n-tag v-for="t in (s.tool_names || []).slice(0, 8)" :key="t" size="tiny" :bordered="false">{{ t }}</n-tag>
          <span v-if="(s.tool_names || []).length > 8" class="more">
            +{{ s.tool_names.length - 8 }}
          </span>
          <span v-if="!s.tool_names?.length" class="more">（未发现工具）</span>
        </div>
        <div class="server-ops">
          <n-button v-if="s.status !== 'running'" size="tiny" type="primary" secondary
                    :loading="busy === `${s.name}:start`" @click="lifecycle(s.name, 'start')">启动</n-button>
          <n-button v-else size="tiny" :loading="busy === `${s.name}:stop`"
                    @click="lifecycle(s.name, 'stop')">停止</n-button>
          <n-button size="tiny" :loading="busy === `${s.name}:restart`"
                    @click="lifecycle(s.name, 'restart')">重启</n-button>
          <n-button v-if="s.managed_by_webui" size="tiny" @click="openForm(s)">编辑</n-button>
          <n-popconfirm v-if="s.managed_by_webui" @positive-click="remove(s.name)">
            <template #trigger><n-button size="tiny" type="error" quaternary>删</n-button></template>
            删除前会先停止该 server，确认？
          </n-popconfirm>
        </div>
      </div>
      <div v-if="!servers.length" class="empty-state glass-panel">
        <p>还没有接入 MCP 服务哦～点右上角「新增」试试（例如 filesystem server）</p>
      </div>
    </div>

    <n-modal v-model:show="showForm" preset="card"
             :title="isCreate ? '新增 MCP Server' : `编辑 · ${form.name}`"
             style="width: min(580px, 94vw)">
      <n-form label-placement="left" label-width="90">
        <n-form-item label="name" v-if="isCreate">
          <n-input v-model:value="form.name" placeholder="如 filesystem" />
        </n-form-item>
        <n-form-item label="command">
          <n-input v-model:value="form.command" placeholder="如 /usr/bin/npx 或 uvx" />
        </n-form-item>
        <n-form-item label="args">
          <n-dynamic-input v-model:value="form.args" placeholder="逐行一个参数" />
        </n-form-item>
        <n-form-item label="env">
          <n-dynamic-input v-model:value="form.env" preset="pair"
                           key-placeholder="变量名" value-placeholder="值（保密处理）" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display:flex; justify-content:flex-end; gap:10px">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" @click="save">保存并启动</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="showImport" preset="card" title="粘贴 JSON 导入 MCP Server"
             style="width: min(640px, 94vw)">
      <n-input v-model:value="importJson" type="textarea" :rows="14"
               class="mono" :placeholder="IMPORT_PLACEHOLDER" />
      <template #footer>
        <div style="display:flex; justify-content:flex-end; gap:10px">
          <n-button @click="showImport = false">取消</n-button>
          <n-button type="primary" :loading="importing" :disabled="!importJson.trim()"
                    @click="runImport">导入并启动</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.view-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.view-header h2 { font-family: 'Noto Serif SC', serif; }
.mcp-hint { font-size: 12.5px; color: var(--moon-dim); margin-bottom: 14px; }

.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.server-card { padding: 14px 16px; }
.server-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.server-name { font-weight: 600; font-size: 15px; }

.server-cmd {
  font-size: 12px; color: var(--moon-dim);
  word-break: break-all; margin-bottom: 8px;
}
.mono { font-family: 'JetBrains Mono', monospace; }

.server-error {
  font-size: 12px; color: var(--alert);
  background: rgba(217, 106, 95, 0.08);
  border-radius: 6px; padding: 4px 8px; margin-bottom: 8px;
}

.server-tools { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; min-height: 22px; }
.more { font-size: 11px; color: var(--moon-dim); }

.server-ops { display: flex; gap: 6px; flex-wrap: wrap; }

.empty-state { padding: 40px; text-align: center; color: var(--moon-dim); grid-column: 1 / -1; }
</style>
