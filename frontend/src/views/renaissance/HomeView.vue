<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { 
  SendHorizontal, 
  Settings, 
  BookOpen, 
  Plus,
  MoveRight 
} from 'lucide-vue-next'
import { useThemeStore } from '../../stores/themeStore'
import { useNovelStore } from '../../stores/novelStore'

const themeStore = useThemeStore()
const novelStore = useNovelStore()
const router = useRouter()

const searchQuery = ref('')
const isFocused = ref(false)

const handleCreate = () => {
  if (searchQuery.value.trim()) {
    router.push('/renaissance/onboarding')
  }
}

const handleBookClick = (id: string) => {
  router.push(`/renaissance/workbench/${id}`)
}

onMounted(() => {
  novelStore.fetchBooks()
})
</script>

<template>
  <div class="renaissance-root" :class="{ 'is-dark': themeStore.isDark }">
    <!-- 1. 背景材质层 (Deep Sea Surge) -->
    <div class="bg-layer fixed inset-0">
      <div class="rice-paper"></div>
      
      <!-- 影子墨块：极致慢节奏 -->
      <div 
        class="ink-blob ink-blob-1" 
        :style="{ opacity: isFocused ? 0.12 : 0.04 }"
      ></div>
      <div 
        class="ink-blob ink-blob-2" 
        :style="{ opacity: isFocused ? 0.12 : 0.04 }"
      ></div>
    </div>

    <!-- 2. 顶层主权区 -->
    <header class="renaissance-header">
      <div class="header-right">
        <button class="icon-btn" @click="novelStore.fetchBooks" title="刷新作品库">
          <Settings :size="20" :stroke-width="1" />
        </button>
      </div>
    </header>

    <!-- 3. 核心交互区 (Hero Section) -->
    <main class="renaissance-main">
      <section class="hero-section" :class="{ 'is-searching': isFocused }">
        <div class="brand-identity">
          <div class="brand-glow"></div>
          <h1 class="main-title font-brush">墨枢</h1>
          <div class="brand-sub">
            <div class="accent-line"></div>
            <span class="sub-text font-display">Plot Pilot</span>
            <div class="accent-line"></div>
          </div>
        </div>

        <p class="slogan font-serif">
          —— 作者的领航员 ——
        </p>

        <!-- 输入终端 -->
        <div class="search-container">
          <div class="input-glow"></div>
          <div class="search-box">
            <input 
              v-model="searchQuery"
              type="text" 
              placeholder="在此处输入你的故事原点..." 
              class="neo-input"
              @focus="isFocused = true"
              @blur="isFocused = false"
              @keyup.enter="handleCreate"
            />
            <button class="send-btn" @click="handleCreate" :disabled="!searchQuery.trim()">
              <SendHorizontal :size="24" :stroke-width="1.5" />
            </button>
          </div>
          <div class="protocol-hints">
            <span>INITIATE PROTOCOL</span>
            <span>LOGIC READY</span>
          </div>
        </div>
      </section>

      <!-- 4. 作品库 (Bookshelf) -->
      <Transition name="shelf-slide">
        <section v-if="novelStore.books.length > 0 && !isFocused" class="library-shelf">
          <div class="shelf-inner">
            <div class="section-header">
              <div class="header-label">
                <BookOpen :size="18" class="text-cinnabar" :stroke-width="1.5" />
                <span class="font-display">我的作品库</span>
              </div>
              <span class="header-stats">{{ novelStore.books.length }} PROJECTS FOUND</span>
            </div>

            <div class="bookshelf-grid">
              <div 
                v-for="novel in novelStore.books" 
                :key="novel.slug"
                class="novel-card-glass"
                @click="handleBookClick(novel.slug)"
              >
                <div class="card-brush"></div>
                <div class="card-content">
                  <div class="card-top">
                    <span class="status-tag">{{ novel.stage_label }}</span>
                    <span class="date">UPDATED</span>
                  </div>
                  <h3 class="card-title font-brush">{{ novel.title }}</h3>
                  <div class="card-footer">
                    <div class="stats">
                      <span class="label">Words</span>
                      <span class="value">{{ novel.word_count || 0 }}</span>
                    </div>
                    <div class="action-btn">
                      <MoveRight :size="14" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </Transition>
    </main>

    <!-- 5. 极简页脚 -->
    <footer class="renaissance-footer">
      <div class="footer-left">
        <span>INK-TECH PROTOCOL V1.0</span>
        <span>STATUS: STABLE</span>
      </div>
      <div class="footer-right">
        <span>© 2026 PLOT PILOT | 墨枢</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* 🏹 原生 CSS 自治体系 (Vanilla Design System) */
.renaissance-root {
  --ink-bg: #F4F1EA;
  --text-main: #1A1A1A;
  --text-muted: #737373;
  --cinnabar: #DC2626;
  --glass-border: rgba(0, 0, 0, 0.08);
  --panel-bg: rgba(255, 255, 255, 0.4);
  
  min-height: 100vh;
  background-color: var(--ink-bg);
  color: var(--text-main);
  font-family: 'Inter', system-ui, sans-serif;
  transition: all 0.8s cubic-bezier(0.23, 1, 0.32, 1);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow-x: hidden;
}

.renaissance-root.is-dark {
  --ink-bg: #0F0F0F;
  --text-main: #E5E5E5;
  --text-muted: #888888;
  --glass-border: rgba(255, 255, 255, 0.1);
  --panel-bg: rgba(23, 23, 23, 0.4);
}

.fixed { position: fixed; }
.inset-0 { top: 0; right: 0; bottom: 0; left: 0; }
.absolute { position: absolute; }
.relative { position: relative; }
.pointer-events-none { pointer-events: none; }

/* 1. Background Layers */
.rice-paper {
  position: absolute;
  inset: 0;
  opacity: 0.02;
  mix-blend-mode: overlay;
  background-image: url('https://www.transparenttextures.com/patterns/p6.png');
}

.ink-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(140px);
  transition: opacity 2s ease;
  animation: drift 40s infinite alternate ease-in-out;
}

.ink-blob-1 {
  width: 45vw; height: 45vw;
  top: 10%; left: 15%;
  background: var(--cinnabar);
}

.ink-blob-2 {
  width: 50vw; height: 50vw;
  bottom: 10%; right: 10%;
  background: var(--text-muted);
  animation-delay: -5s;
}

@keyframes drift {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(60px, -40px) scale(1.1); }
}

/* 2. Header */
.renaissance-header {
  padding: 2.5rem 3rem;
  display: flex;
  justify-content: flex-end;
  z-index: 50;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.3s;
  padding: 8px;
}
.icon-btn:hover { color: var(--cinnabar); }

/* 3. Hero Section */
.renaissance-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  items-center: center;
  justify-content: center;
  padding: 0 1.5rem;
  z-index: 10;
}

.hero-section {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  text-align: center;
  transition: transform 0.8s cubic-bezier(0.23, 1, 0.32, 1);
}

.hero-section.is-searching { transform: translateY(-30px); }

.brand-identity {
  margin-bottom: 3rem;
  position: relative;
}

.brand-glow {
  position: absolute;
  inset: 0;
  filter: blur(80px);
  background-color: var(--cinnabar);
  opacity: 0.05;
}

.main-title {
  font-size: 6rem;
  letter-spacing: 0.2em;
  margin-bottom: 1rem;
  position: relative;
}

.brand-sub {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  opacity: 0.6;
}

.accent-line {
  height: 1px;
  width: 48px;
  background: linear-gradient(to right, transparent, var(--text-muted));
}

.sub-text {
  font-size: 1.5rem;
  letter-spacing: 0.6em;
  text-transform: uppercase;
}

.slogan {
  color: var(--text-muted);
  font-size: 1.25rem;
  letter-spacing: 0.6em;
  margin-bottom: 5rem;
  opacity: 0.4;
}

/* 4. Terminal */
.search-container {
  width: 100%;
  max-width: 640px;
  margin: 0 auto;
  position: relative;
}

.input-glow {
  position: absolute;
  inset: -4px;
  background: radial-gradient(circle, var(--cinnabar), transparent 70%);
  border-radius: 12px;
  filter: blur(20px);
  opacity: 0.1;
  transition: opacity 1s;
}

.search-container:focus-within .input-glow { opacity: 0.4; }

.search-box {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--panel-bg);
  backdrop-filter: blur(30px);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  padding: 8px;
  box-shadow: 0 30px 60px -15px rgba(0, 0, 0, 0.5);
  transition: border-color 0.4s;
}

.search-container:focus-within .search-box { border-color: rgba(220, 38, 38, 0.3); }

.neo-input {
  flex: 1;
  background: transparent;
  border: none;
  padding: 1.25rem 1.5rem;
  font-size: 1.25rem;
  color: var(--text-main);
  outline: none;
  font-family: inherit;
}
.neo-input::placeholder { color: var(--text-muted); opacity: 0.3; }

.send-btn {
  background: var(--cinnabar);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 10px 20px rgba(220, 38, 38, 0.2);
}
.send-btn:hover { background: #B91C1C; transform: scale(0.95); }
.send-btn:disabled { opacity: 0.2; transform: none; cursor: default; }

.protocol-hints {
  margin-top: 1.25rem;
  display: flex;
  justify-content: center;
  gap: 2.5rem;
  font-family: monospace;
  font-size: 10px;
  letter-spacing: 0.5em;
  opacity: 0.2;
}

/* 5. Library */
.library-shelf {
  width: 100%;
  max-width: 1200px;
  margin: 4rem auto 0;
  padding-top: 4rem;
  border-top: 1px solid var(--glass-border);
}

.shelf-inner { padding: 0 1rem; }

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2.5rem;
}

.header-label {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-label span {
  font-size: 12px;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  opacity: 0.6;
}

.text-cinnabar { color: var(--cinnabar); }

.header-stats {
  font-family: monospace;
  font-size: 10px;
  opacity: 0.3;
}

.bookshelf-grid {
  display: grid;
  grid-template-cols: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.5rem;
}

.novel-card-glass {
  position: relative;
  background: var(--panel-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  padding: 1.5rem;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.5s cubic-bezier(0.23, 1, 0.32, 1);
  display: flex;
  flex-direction: column;
}

.novel-card-glass:hover {
  border-color: rgba(220, 38, 38, 0.3);
  transform: translateY(-5px);
}

.card-brush {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at top right, rgba(220, 38, 38, 0.05), transparent 70%);
  opacity: 0;
  transition: opacity 0.5s;
}
.novel-card-glass:hover .card-brush { opacity: 1; }

.card-content { position: relative; z-index: 10; flex: 1; display: flex; flex-direction: column; }

.card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }

.status-tag {
  font-size: 9px;
  font-family: monospace;
  color: var(--cinnabar);
  border: 1px solid rgba(220, 38, 38, 0.2);
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(220, 38, 38, 0.05);
}

.date { font-family: monospace; font-size: 9px; opacity: 0.4; }

.card-title {
  font-size: 1.5rem;
  margin-bottom: 2rem;
  transition: color 0.3s;
}
.novel-card-glass:hover .card-title { color: var(--cinnabar); }

.card-footer {
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats .label { display: block; font-size: 8px; opacity: 0.4; text-transform: uppercase; margin-bottom: 4px; }
.stats .value { font-family: monospace; font-size: 14px; }

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  transition: all 0.3s;
}
.novel-card-glass:hover .action-btn { background: var(--cinnabar); color: white; }

/* Footer */
.renaissance-footer {
  padding: 2rem 3rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: monospace;
  font-size: 9px;
  letter-spacing: 0.1em;
  opacity: 0.3;
}

.footer-left { display: flex; gap: 2rem; }

/* Utilities */
.font-brush { font-family: 'Ma Shan Zheng', cursive; }
.font-display { font-family: 'Inter', sans-serif; font-weight: 300; }
.font-serif { font-family: 'Noto Serif SC', serif; }

/* Transitions */
.shelf-slide-enter-active, .shelf-slide-leave-active { transition: all 1s cubic-bezier(0.23, 1, 0.32, 1); }
.shelf-slide-enter-from { opacity: 0; transform: translateY(40px); }
.shelf-slide-leave-to { opacity: 0; transform: translateY(80px); }

@media (min-width: 768px) {
  .main-title { font-size: 8rem; }
  .sub-text { font-size: 2rem; }
}
</style>
