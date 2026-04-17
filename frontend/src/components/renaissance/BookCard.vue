<script setup lang="ts">
/**
 * 🎨文艺复兴特区：原生书架卡片
 * 严禁引入 Naive UI，全原生 CSS 驱动。
 * 复刻 Mock 中的 HUD 扫描感与朱砂呼吸动效。
 */
import { computed } from 'vue'

const props = defineProps<{
  book: {
    slug: string
    title: string
    stage: string
    stage_label: string
    genre?: string
    chapter_count?: number
    word_count?: number
  }
}>()

defineEmits(['click', 'delete', 'select'])

const formatWordCount = (count: number): string => {
  if (count >= 10000) {
    return (count / 10000).toFixed(1) + '万字'
  }
  return count + '字'
}

const statusColor = computed(() => {
  const map: Record<string, string> = {
    planning: '#8b5cf6',
    writing: '#10b981',
    reviewing: '#f59e0b',
    completed: '#3b82f6'
  }
  return map[props.book.stage] || '#DC2626'
})
</script>

<template>
  <div class="renaissance-card group" @click="$emit('click')">
    <!-- 1. 背景光晕 (Mock 基因: 朱砂红模糊背景) -->
    <div class="card-glow"></div>
    
    <!-- 2. 边框与内容容器 -->
    <div class="card-inner">
      <div class="card-header">
        <div class="status-badge" :style="{ borderColor: `${statusColor}40`, color: statusColor }">
          {{ book.stage_label }}
        </div>
        <div class="timestamp">
          <slot name="header-right"></slot>
        </div>
      </div>

      <h3 class="book-title">{{ book.title }}</h3>
      
      <div class="card-footer">
        <div class="stats">
          <span class="stat-item">
            <span class="stat-label">章节</span>
            <span class="stat-value">{{ book.chapter_count || 0 }}</span>
          </span>
          <span class="stat-item">
            <span class="stat-label">字数</span>
            <span class="stat-value">{{ formatWordCount(book.word_count || 0) }}</span>
          </span>
        </div>
        
        <div class="action-zone" @click.stop>
          <slot name="actions"></slot>
        </div>
      </div>
    </div>
    
    <!-- HUD 扫描线装饰 -->
    <div class="scan-line"></div>
  </div>
</template>

<style scoped>
.renaissance-card {
  position: relative;
  background: rgba(23, 23, 23, 0.4);
  border: 1px solid rgba(212, 168, 67, 0.1);
  border-radius: 12px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.5s cubic-bezier(0.23, 1, 0.32, 1);
  overflow: hidden;
  backdrop-filter: blur(8px);
}

.renaissance-card:hover {
  border-color: rgba(220, 38, 38, 0.4);
  background: rgba(30, 30, 30, 0.6);
  transform: translateY(-2px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3), 0 0 20px rgba(220, 38, 38, 0.05);
}

/* 核心背景光晕 (Mock Style) */
.card-glow {
  position: absolute;
  top: -20%;
  right: -20%;
  width: 120px;
  height: 120px;
  background: radial-gradient(circle, rgba(220, 38, 38, 0.08) 0%, transparent 70%);
  filter: blur(30px);
  border-radius: 50%;
  transition: all 0.5s ease;
  pointer-events: none;
}

.renaissance-card:hover .card-glow {
  background: radial-gradient(circle, rgba(220, 38, 38, 0.15) 0%, transparent 70%);
  width: 180px;
  height: 180px;
}

.card-inner {
  position: relative;
  z-index: 2;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.status-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  padding: 2px 8px;
  border: 1px solid;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.timestamp {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #525252;
}

.book-title {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 24px;
  color: #ffffff;
  margin-bottom: 24px;
  letter-spacing: 0.05em;
  transition: color 0.3s ease;
}

[data-theme='cinnabar'] .book-title {
  color: #1a1a1a;
}

.renaissance-card:hover .book-title {
  color: #DC2626;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  padding-top: 16px;
}

.stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  color: #525252;
  text-transform: uppercase;
}

.stat-value {
  font-size: 13px;
  font-weight: 500;
  color: #a3a3a3;
}

[data-theme='cinnabar'] .stat-value {
  color: #444433;
}

/* HUD 扫描线效果 */
.scan-line {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(220, 38, 38, 0.2), transparent);
  opacity: 0;
  pointer-events: none;
}

.renaissance-card:hover .scan-line {
  animation: scan 3s infinite linear;
  opacity: 1;
}

@keyframes scan {
  0% { transform: translateY(-10px); }
  100% { transform: translateY(200px); }
}

.action-zone {
  display: flex;
  gap: 8px;
}
</style>
