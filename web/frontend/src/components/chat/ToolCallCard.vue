<script setup lang="ts">
import { ref } from 'vue'
import type { ToolCall } from '../../stores/chat'

defineProps<{ call: ToolCall }>()
const expanded = ref(false)
</script>

<template>
  <div class="tool-card" :class="{ failed: call.ok === false }" @click="expanded = !expanded">
    <div class="tool-head">
      <span class="tool-icon">🛠</span>
      <span class="tool-name">{{ call.tool }}</span>
      <span v-if="call.running" class="tool-spin">⏳</span>
      <template v-else>
        <span class="tool-time" v-if="call.elapsedMs != null">{{ (call.elapsedMs / 1000).toFixed(1) }}s</span>
        <span class="tool-result">{{ call.ok ? '✓' : '✗' }}</span>
      </template>
    </div>
    <div v-if="expanded && call.argsPreview" class="tool-args">{{ call.argsPreview }}</div>
  </div>
</template>

<style scoped>
.tool-card {
  background: rgba(15, 31, 23, 0.6);
  border: 1px solid rgba(127, 214, 80, 0.15);
  border-radius: 8px;
  padding: 5px 10px;
  margin: 4px 0;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.tool-card:hover { border-color: rgba(127, 214, 80, 0.35); }
.tool-card.failed { border-color: rgba(217, 106, 95, 0.35); }

.tool-head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tool-name {
  font-family: 'JetBrains Mono', monospace;
  color: var(--wisdom);
}

.tool-time { color: var(--moon-dim); margin-left: auto; }
.tool-result { color: var(--dendro); }
.failed .tool-result { color: var(--alert); }
.tool-spin { margin-left: auto; animation: spin 1.5s linear infinite; display: inline-block; }

.tool-args {
  margin-top: 5px;
  padding-top: 5px;
  border-top: 1px dashed rgba(127, 214, 80, 0.15);
  font-family: 'JetBrains Mono', monospace;
  color: var(--moon-dim);
  word-break: break-all;
  white-space: pre-wrap;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
