<script setup lang="ts">
/**
 * 🎨文艺复兴特区：朱砂印章按钮
 * 严禁引入 Naive UI，全原生 CSS 变量驱动。
 */
defineProps<{
  label: string
  active?: boolean
}>()

defineEmits(['click'])
</script>

<template>
  <button 
    class="cinnabar-seal-btn"
    :class="{ 'is-active': active }"
    @click="$emit('click')"
  >
    <span class="btn-texture"></span>
    <span class="btn-label">{{ label }}</span>
    <span class="seal-glow"></span>
  </button>
</template>

<style scoped>
.cinnabar-seal-btn {
  position: relative;
  padding: 10px 24px;
  background: var(--color-brand);
  color: #ffffff;
  border: none;
  border-radius: 4px; /* 模拟印模的微圆角 */
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 18px;
  letter-spacing: 0.1em;
  cursor: pointer;
  outline: none;
  overflow: hidden;
  transition: all 0.2s cubic-bezier(0.23, 1, 0.32, 1);
  box-shadow: 
    0 4px 0 #b91c1c,
    0 8px 15px rgba(220, 38, 38, 0.2);
  user-select: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* 宣纸感纹理覆盖 */
.btn-texture {
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3Q%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
  opacity: 0.08;
  mix-blend-mode: soft-light;
  pointer-events: none;
}

/* 印章下压动效 (救命核心：摆脱框架后的物理感) */
.cinnabar-seal-btn:active {
  transform: translateY(3px);
  box-shadow: 
    0 1px 0 #b91c1c,
    0 2px 4px rgba(220, 38, 38, 0.4);
}

.cinnabar-seal-btn:hover {
  filter: brightness(1.1);
  box-shadow: 
    0 4px 0 #b91c1c,
    0 10px 20px rgba(220, 38, 38, 0.3);
}

.btn-label {
  position: relative;
  z-index: 1;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

/* 朱砂光晕呼吸 */
.seal-glow {
  position: absolute;
  inset: -10px;
  background: radial-gradient(circle, rgba(220, 38, 38, 0.4) 0%, transparent 70%);
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

.cinnabar-seal-btn:hover .seal-glow {
  opacity: 1;
  animation: pulse-glow 2s infinite ease-in-out;
}

@keyframes pulse-glow {
  0%, 100% { transform: scale(0.8); opacity: 0.3; }
  50% { transform: scale(1.1); opacity: 0.6; }
}

/* 激活态（已选中）*/
.cinnabar-seal-btn.is-active {
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 
    0 0 15px rgba(220, 38, 38, 0.5),
    inset 0 0 10px rgba(0, 0, 0, 0.1);
}
</style>
