import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { GlobalThemeOverrides } from 'naive-ui'

export type ThemeMode = 'light' | 'dark' | 'anchor' | 'auto' | 'ink' | 'cinnabar'

const STORAGE_KEY = 'aitext-theme-mode'

/** 
 * 主题配置映射表 (Technical Sovereignty)
 * 用于解决 Naive UI color calculations 无法处理 CSS 变量的问题
 */
const THEME_CONFIG = {
  anchor: {
    primary: '#c9a227',
    primaryHover: '#ddb930',
    primaryPressed: '#a88a1f',
    primarySuppl: '#e8c84a',
    text: '#f0ead6',
    surface: '#111620',
    bg: '#0a0c10'
  },
  ink: {
    primary: '#DC2626',
    primaryHover: '#ef4444',
    primaryPressed: '#b91c1c',
    primarySuppl: '#fca5a5',
    text: '#ffffff',
    surface: '#171717',
    bg: '#0F0F0F'
  },
  cinnabar: {
    primary: '#DC2626',
    primaryHover: '#ef4444',
    primaryPressed: '#b91c1c',
    primarySuppl: '#fca5a5',
    text: '#1a1a1a',
    surface: '#ffffff',
    bg: '#f4f1ea'
  },
  dark: {
    primary: '#818cf8',
    primaryHover: '#a5b4fc',
    primaryPressed: '#6366f1',
    primarySuppl: '#c7d2fe',
    text: '#e2e8f0',
    surface: '#131c31',
    bg: '#0b1121'
  },
  light: {
    primary: '#4f46e5',
    primaryHover: '#6366f1',
    primaryPressed: '#4338ca',
    primarySuppl: '#818cf8',
    text: '#0f172a',
    surface: '#ffffff',
    bg: '#eef1f6'
  }
}

function getStoredTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (['light', 'dark', 'anchor', 'auto', 'ink', 'cinnabar'].includes(stored as string)) return stored as ThemeMode
  } catch { /* ignore */ }
  return 'anchor'
}

function getSystemDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(getStoredTheme())

  const isDark = computed(() => {
    if (mode.value === 'auto') return getSystemDark()
    // 只有 dark, anchor, ink 是暗色；cinnabar (朱砂/宣纸) 是浅色
    return ['dark', 'anchor', 'ink'].includes(mode.value)
  })

  /** 是否为黑金（主播限定色）模式 */
  const isAnchor = computed(() => mode.value === 'anchor')

  /** 实际生效的主题名，供 naive-ui / CSS 使用 */
  const effectiveTheme = computed<'light' | 'dark'>(() =>
    isDark.value ? 'dark' : 'light'
  )

  function setTheme(newMode: ThemeMode) {
    mode.value = newMode
    try {
      localStorage.setItem(STORAGE_KEY, newMode)
    } catch { /* ignore */ }
  }

  // 监听系统主题变化（仅 auto 模式下需要响应）
  if (typeof window !== 'undefined' && window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      // 触发 computed 重新计算即可，无需额外操作
    })
  }

  // 同步 <html> 以支持全局 CSS 变量切换
  watch(mode, () => {
    const root = document.documentElement
    
    // 同步 data-theme 属性（墨枢、朱砂、锚点等）
    root.setAttribute('data-theme', mode.value)
    
    // 处理暗色基调类名（Naive UI 联动）
    if (isDark.value) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, { immediate: true })

  // 暴露当前模式下的 Hex 色值配置 (供 Naive UI 消费)
  const themeConfig = computed(() => {
    const activeMode = (mode.value === 'auto' ? (getSystemDark() ? 'dark' : 'light') : mode.value) as keyof typeof THEME_CONFIG
    return THEME_CONFIG[activeMode] || THEME_CONFIG.light
  })

  /** 统一的主题覆盖配置 (Technical Sovereignty Engine) */
  const themeOverrides = computed<GlobalThemeOverrides>(() => {
    return {
      common: {
        primaryColor: themeConfig.value.primary,
        primaryColorHover: themeConfig.value.primaryHover,
        primaryColorPressed: themeConfig.value.primaryPressed,
        primaryColorSuppl: themeConfig.value.primarySuppl,
        borderRadius: '10px',
        borderRadiusSmall: '8px',
        fontSize: '14px',
        fontSizeMedium: '15px',
        lineHeight: '1.55',
        heightMedium: '38px',
        bodyColor: themeConfig.value.bg,
        textColor1: themeConfig.value.text,
        textColor2: 'var(--app-text-secondary)',
        textColor3: 'var(--app-text-muted)',
        borderColor: 'var(--app-border)',
        dividerColor: 'var(--app-divider)',
        cardColor: themeConfig.value.surface,
        modalColor: themeConfig.value.surface,
        popoverColor: themeConfig.value.surface,
        tableColor: themeConfig.value.surface,
        tableColorStriped: 'var(--app-surface-subtle)',
        tableColorHover: 'var(--app-surface-raised)',
        tableHeaderColor: themeConfig.value.surface,
      },
      Card: {
        borderRadius: '14px',
        paddingMedium: '20px',
      },
      Button: {
        borderRadiusMedium: '10px',
      },
      Input: {
        borderRadius: '10px',
        color: themeConfig.value.surface,
      },
      Select: {
        peers: {
          InternalSelection: {
            color: themeConfig.value.surface,
            borderActive: themeConfig.value.primary,
            borderFocus: themeConfig.value.primary,
          },
        },
      },
      Drawer: {
        color: themeConfig.value.bg,
        bodyPadding: '0',
      },
      Tabs: {
        tabTextColorActiveLine: themeConfig.value.primary,
        tabTextColorHoverLine: 'var(--app-text-secondary)',
        barColor: themeConfig.value.primary,
      },
      Switch: {
        railColorActive: themeConfig.value.primary,
      },
      Alert: {
        color: themeConfig.value.surface,
        border: 'none',
      },
      Form: {
        labelTextColorTop: 'var(--app-text-secondary)',
      },
      Scrollbar: {
        width: '8px',
        height: '8px',
        borderRadius: '4px',
      },
    }
  })

  return { mode, isDark, isAnchor, effectiveTheme, themeConfig, themeOverrides, setTheme }
})
