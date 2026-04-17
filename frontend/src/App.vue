<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { NConfigProvider, NMessageProvider, NDialogProvider, NLayout, zhCN, dateZhCN, darkTheme } from 'naive-ui'
import { useThemeStore } from './stores/themeStore'

const themeStore = useThemeStore()
const route = useRoute()

const naiveTheme = computed(() =>
  themeStore.isDark ? darkTheme : undefined
)

const themeOverrides = computed(() => themeStore.themeOverrides)

// Determine if we are in the Renaissance isolation zone
const isRenaissance = computed(() => {
  return themeStore.mode === 'ink' || 
         themeStore.mode === 'cinnabar' ||
         route.path.startsWith('/renaissance/')
})
</script>

<template>
  <n-config-provider
    :locale="zhCN"
    :date-locale="dateZhCN"
    :theme="naiveTheme"
    :theme-overrides="themeOverrides"
  >
    <n-message-provider>
      <n-dialog-provider>
        <div class="app-container">
          <!-- 🏹 文艺复兴隔离区 (Renaissance District) -->
          <template v-if="isRenaissance">
            <router-view v-slot="{ Component }">
              <transition name="app-fade" mode="out-in">
                <component :is="Component" />
              </transition>
            </router-view>
          </template>

          <!-- 🛡️ 作者原始布局 (Original Baseline) -->
          <template v-else>
            <router-view v-slot="{ Component }">
              <transition name="app-fade" mode="out-in">
                <component :is="Component" />
              </transition>
            </router-view>
          </template>
        </div>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
.app-container {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.app-layout {
  height: 100%;
}

.app-fade-enter-active,
.app-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.app-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.app-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
