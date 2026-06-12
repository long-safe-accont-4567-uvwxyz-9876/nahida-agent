<script setup lang="ts">
// 草元素神之眼徽记（原神草元素符号的四叶印化简）
withDefaults(defineProps<{ size?: number; spin?: boolean; glow?: boolean }>(), {
  size: 36, spin: false, glow: true,
})
</script>

<template>
  <span class="dendro-emblem" :class="{ spin, glow }" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" viewBox="0 0 48 48" fill="none">
      <!-- 外环藤纹 -->
      <circle cx="24" cy="24" r="21" stroke="currentColor" stroke-width="1.2" opacity="0.35"
              stroke-dasharray="4 5" stroke-linecap="round" />
      <!-- 四片主叶 -->
      <g stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" fill="rgba(127,214,80,0.16)">
        <path d="M24 6c4 4.5 4 9.5 0 13-4-3.5-4-8.5 0-13Z" />
        <path d="M42 24c-4.5 4-9.5 4-13 0 3.5-4 8.5-4 13 0Z" />
        <path d="M24 42c-4-4.5-4-9.5 0-13 4 3.5 4 8.5 0 13Z" />
        <path d="M6 24c4.5-4 9.5-4 13 0-3.5 4-8.5 4-13 0Z" />
      </g>
      <!-- 核心智慧之种 -->
      <circle cx="24" cy="24" r="3.4" fill="currentColor" />
      <circle cx="24" cy="24" r="6.5" stroke="currentColor" stroke-width="1" opacity="0.5" />
    </svg>
  </span>
</template>

<style scoped>
.dendro-emblem {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--dendro);
}
.dendro-emblem.glow { filter: drop-shadow(0 0 6px rgba(127, 214, 80, 0.45)); }
.dendro-emblem.spin svg { animation: emblem-spin 9s linear infinite; }
@keyframes emblem-spin { to { transform: rotate(360deg); } }
</style>
