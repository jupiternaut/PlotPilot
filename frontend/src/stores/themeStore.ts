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
    textSecondary: '#c4b99a',
    textMuted: '#8a8070',
    surface: '#111620',
    surfaceSubtle: '#0d1018',
    surfaceRaised: '#181f2e',
    divider: 'rgba(201, 162, 39, 0.06)',
    border: 'rgba(201, 162, 39, 0.08)',
    bg: '#0a0c10'
  },
  ink: {
    primary: '#DC2626',
    primaryHover: '#ef4444',
    primaryPressed: '#b91c1c',
    primarySuppl: '#fca5a5',
    text: '#ffffff',
    textSecondary: '#a3a3a3',
    textMuted: '#737373',
    surface: '#171717',
    surfaceSubtle: '#121212',
    surfaceRaised: '#262626',
    divider: 'rgba(255, 255, 255, 0.05)',
    border: 'rgba(255, 255, 255, 0.08)',
    bg: '#0F0F0F'
  },
  cinnabar: {
    primary: '#DC2626',
    primaryHover: '#ef4444',
    primaryPressed: '#b91c1c',
    primarySuppl: '#fca5a5',
    text: '#1a1a1a',
    textSecondary: '#525252',
    textMuted: '#737373',
    surface: '#ffffff',
    surfaceSubtle: '#faf9f6',
    surfaceRaised: '#ffffff',
    divider: 'rgba(0, 0, 0, 0.05)',
    border: 'rgba(0, 0, 0, 0.08)',
    bg: '#F4F1EA'
  },
  dark: {
    primary: '#818cf8',
    primaryHover: '#a5b4fc',
    primaryPressed: '#6366f1',
    primarySuppl: '#c7d2fe',
    text: '#e2e8f0',
    textSecondary: '#d1d5db',
    textMuted: '#9ca3af',
    surface: '#131c31',
    surfaceSubtle: '#0f172a',
    surfaceRaised: '#1a2436',
    divider: 'rgba(51, 65, 85, 0.4)',
    border: 'rgba(148, 163, 184, 0.1)',
    bg: '#0b1121'
  },
  light: {
    primary: '#4f46e5',
    primaryHover: '#6366f1',
    primaryPressed: '#4338ca',
    primarySuppl: '#818cf8',
    text: '#0f172a',
    textSecondary: '#334155',
    textMuted: '#64748b',
    surface: '#ffffff',
    surfaceSubtle: '#f8fafc',
    surfaceRaised: '#ffffff',
    divider: 'rgba(15, 23, 42, 0.06)',
    border: 'rgba(15, 23, 42, 0.09)',
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
    const config = themeConfig.value
    return {
      common: {
        primaryColor: config.primary,
        primaryColorHover: config.primaryHover,
        primaryColorPressed: config.primaryPressed,
        primaryColorSuppl: config.primarySuppl,
        borderRadius: '10px',
        borderRadiusSmall: '8px',
        fontSize: '14px',
        fontSizeMedium: '15px',
        lineHeight: '1.55',
        heightMedium: '38px',
        bodyColor: config.bg,
        textColor1: config.text,
        textColor2: config.textSecondary,
        textColor3: config.textMuted,
        borderColor: config.border,
        dividerColor: config.divider,
        cardColor: config.surface,
        modalColor: config.surface,
        popoverColor: config.surface,
        tableColor: config.surface,
        tableColorStriped: config.surfaceSubtle,
        tableColorHover: config.surfaceRaised,
        tableHeaderColor: config.surface,
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
        color: config.surface,
      },
      Select: {
        peers: {
          InternalSelection: {
            color: config.surface,
            borderActive: config.primary,
            borderFocus: config.primary,
          },
        },
      },
      Drawer: {
        color: config.bg,
        bodyPadding: '0',
      },
      Tabs: {
        tabTextColorActiveLine: config.primary,
        tabTextColorHoverLine: config.textSecondary,
        barColor: config.primary,
      },
      Switch: {
        railColorActive: config.primary,
      },
      Alert: {
        color: config.surface,
        border: 'none',
      },
      Form: {
        labelTextColorTop: config.textSecondary,
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
