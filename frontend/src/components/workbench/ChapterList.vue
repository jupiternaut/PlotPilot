<template>
  <aside class="sidebar">
    <div class="sidebar-head">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <n-button quaternary size="small" class="back-btn" style="margin-bottom: 0;" @click="handleBack">
          <template #icon>
            <span class="ico-arrow">←</span>
          </template>
          书目列表
        </n-button>
        
        <n-dropdown :options="resetOptions" @select="handleResetSelect">
          <n-button quaternary circle size="small" type="warning" title="重置与清空选项">
            <template #icon>
              <span style="font-size: 14px; display: inline-flex; align-items: center; justify-content: center; height: 100%;">⚙️</span>
            </template>
          </n-button>
        </n-dropdown>
      </div>

      <!-- 视图模式切换 -->
      <div class="view-mode-row">
        <n-select
          v-model:value="viewMode"
          :options="viewModeOptions"
          size="small"
          style="flex: 1;"
        />
      </div>
    </div>

    <n-scrollbar class="sidebar-scroll">
      <!-- 平铺视图：分页显示章节列表，避免大量章节一次性渲染 -->
      <div v-if="viewMode === 'flat'">
        <div v-if="!chapters.length" class="sidebar-empty">
          <p>暂无章节</p>
          <p class="hint">请切换到「托管撰稿」模式，启动全托管自动生成大纲与正文</p>
        </div>
        <template v-else>
          <n-list hoverable clickable>
            <n-list-item
              v-for="ch in visibleChapters"
              :key="ch.id"
              :class="{ 'is-active': currentChapterId === ch.id }"
              @click="handleChapterClick(ch.id, ch.title)"
            >
              <n-thing :title="narrativeOrdinalLabel(ch.number, generationPrefs)">
                <template #description>
                  <div style="display: flex; flex-direction: column; gap: 4px;">
                    <n-text depth="3" style="font-size: 12px;">{{ ch.title }}</n-text>
                    <n-tag size="small" :type="ch.word_count > 0 ? 'success' : 'default'" round>
                      {{ ch.word_count > 0 ? '已收稿' : '未收稿' }}
                    </n-tag>
                  </div>
                </template>
              </n-thing>
            </n-list-item>
          </n-list>
          <div v-if="hasMoreChapters" class="load-more-bar">
            <n-button text size="small" @click="loadMoreChapters">
              查看更多（剩余 {{ chapters.length - visibleCount }} {{ narrativeUnitNoun(generationPrefs) }}）
            </n-button>
          </div>
        </template>
      </div>

      <!-- 树形视图：显示完整叙事结构（部-卷-幕-章） -->
      <div v-else-if="viewMode === 'tree'">
        <StoryStructureTree
          ref="storyTreeRef"
          :slug="slug"
          :current-chapter-id="currentChapterId"
          :generation-prefs="generationPrefs"
          @select-chapter="handleChapterClick"
          @plan-act="handlePlanAct"
          @open-plan-modal="showMacroPlan = true"
          @tree-loaded="handleTreeLoaded"
        />
      </div>
    </n-scrollbar>

    <!-- 引导用户使用全托管 -->
    <div v-if="!chapters.length && viewMode === 'flat'" class="sidebar-foot-hint">
      <n-alert type="info" :show-icon="false" style="font-size: 12px">
        <strong>提示</strong>：切换到「托管撰稿」模式，点击「启动全托管」即可自动生成大纲与正文
      </n-alert>
    </div>
  </aside>

  <MacroPlanModal
    v-model:show="showMacroPlan"
    :novel-id="slug"
    @confirmed="emit('refresh')"
  />
</template>

<script setup lang="ts">
import { ref, computed, type ComponentPublicInstance } from 'vue'
import { useRouter } from 'vue-router'
import { useDialog, useMessage, NDropdown } from 'naive-ui'
import StoryStructureTree from '@/components/StoryStructureTree.vue'
import MacroPlanModal from '@/components/workbench/MacroPlanModal.vue'
import type { GenerationPrefsDTO } from '@/api/novel'
import { novelApi } from '@/api/novel'
import { narrativeOrdinalLabel, narrativeUnitNoun } from '@/utils/narrativeUnitLabel'
import { clearWizardUiCache } from '@/utils/wizardStageCache'

const INITIAL_VISIBLE_COUNT = 50
const LOAD_MORE_STEP = 50

interface Chapter {
  id: number
  number: number
  title: string
  word_count: number
}

interface ChapterListProps {
  slug: string
  chapters: Chapter[]
  currentChapterId?: number | null
  generationPrefs?: GenerationPrefsDTO | null
}

const props = withDefaults(defineProps<ChapterListProps>(), {
  chapters: () => [],
  currentChapterId: null,
  generationPrefs: null,
})

const emit = defineEmits<{
  select: [id: number, title: string]
  back: []
  refresh: []
  planAct: [actId: string, actTitle: string]
}>()

const router = useRouter()
const viewMode = ref('tree')
const viewModeOptions = [
  { label: '树形视图', value: 'tree' },
  { label: '平铺视图', value: 'flat' }
]

const dialog = useDialog()
const message = useMessage()

const resetOptions = [
  {
    label: '🧹 仅清空已生成正文（保留大纲）',
    key: 'clear-drafts'
  },
  {
    label: '🔥 彻底重设（清空正文与大纲树）',
    key: 'clear-outline'
  }
]

const handleResetSelect = (key: string) => {
  if (key === 'clear-drafts') {
    dialog.warning({
      title: '清空已生成正文',
      content: '此操作将永久删除所有已生成的章节正文，并将章节状态重置为「草稿」！大纲骨架、角色卡和世界观设定将予以保留。确定要清空吗？',
      positiveText: '确定清空',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          const res = await novelApi.clearDrafts(props.slug)
          if (res.success) {
            message.success('已清空所有章节正文，大纲保留完整')
            // 清除当前活跃章节，避免编辑器展示旧内容
            emit('select', -1, '')
            emit('refresh')
            refreshStoryTree()
          } else {
            message.error(res.message || '清空失败')
          }
        } catch (err: any) {
          message.error(err.response?.data?.detail || err.message || '清空失败')
        }
      }
    })
  } else if (key === 'clear-outline') {
    dialog.warning({
      title: '彻底重设小说',
      content: '警告：此操作将永久删除所有已生成的章节正文、结构大纲树、故事线和剧情点，并将书目重置为初始「规划中」状态！角色卡和世界观设定将予以保留。此操作不可撤销，确定要重设吗？',
      positiveText: '确定重设',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          const res = await novelApi.clearOutline(props.slug)
          if (res.success) {
            message.success('已彻底重置小说，即将跳转到新书向导…')
            // 清除本地向导完成标记，让新书向导重新激活
            clearWizardUiCache(props.slug)
            // 延迟一拍让 message 先显示，再跳转
            setTimeout(() => {
              router.replace({ name: 'NovelSetup', params: { slug: props.slug } })
            }, 800)
          } else {
            message.error(res.message || '重置失败')
          }
        } catch (err: any) {
          message.error(err.response?.data?.detail || err.message || '重置失败')
        }
      }
    })
  }
}

const visibleCount = ref(INITIAL_VISIBLE_COUNT)
const visibleChapters = computed(() => props.chapters.slice(0, visibleCount.value))
const hasMoreChapters = computed(() => props.chapters.length > visibleCount.value)

function loadMoreChapters() {
  visibleCount.value += LOAD_MORE_STEP
}

const showMacroPlan = ref(false)
const hasStructure = ref(true)

const storyTreeRef = ref<ComponentPublicInstance<{ loadTree: () => Promise<void> }> | null>(null)

/** 合并短时间内的多次刷新（全托管 desk 更新等），减轻结构树请求叠压 */
let storyTreeRefreshTimer: ReturnType<typeof setTimeout> | null = null
const STORY_TREE_REFRESH_DEBOUNCE_MS = 200

/** 幕→章确认后由工作台调用，刷新左侧叙事结构树 */
function refreshStoryTree() {
  if (storyTreeRefreshTimer != null) {
    clearTimeout(storyTreeRefreshTimer)
  }
  storyTreeRefreshTimer = setTimeout(() => {
    storyTreeRefreshTimer = null
    void storyTreeRef.value?.loadTree?.()
  }, STORY_TREE_REFRESH_DEBOUNCE_MS)
}

defineExpose({ refreshStoryTree })

const handleChapterClick = (id: number, title = '') => {
  emit('select', id, title)
}

const handleBack = () => {
  emit('back')
}

const handlePlanAct = (id: string, title: string) => {
  emit('planAct', id, title)
}

const handleTreeLoaded = (hasData: boolean) => {
  hasStructure.value = hasData
}

</script>

<style scoped>
.sidebar {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: var(--plotpilot-sidebar-pad-y) var(--plotpilot-sidebar-pad-x);
  background: var(--app-surface);
  border-right: 1px solid var(--plotpilot-split-border);
}

.sidebar-head {
  margin-bottom: var(--plotpilot-sidebar-head-gap);
}

.back-btn {
  margin-bottom: 8px;
  font-weight: 500;
}

.ico-arrow {
  font-size: 14px;
  margin-right: 2px;
}

.view-mode-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.sidebar-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sidebar-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.sidebar-scroll {
  flex: 1;
  min-height: 0;
}

.sidebar-foot-hint {
  padding: 8px 4px;
  border-top: 1px solid var(--n-divider-color, rgba(0,0,0,.06));
}

.sidebar-empty {
  padding: 12px;
  font-size: 13px;
  color: var(--app-muted);
  line-height: 1.6;
}

.sidebar-empty .hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-brand, #18a058);
}

.sidebar :deep(.n-list-item) {
  border-radius: 10px;
  margin-bottom: 4px;
  transition: background var(--app-transition), transform 0.15s ease;
}

.sidebar :deep(.n-list-item:hover) {
  background: var(--color-brand-light);
}

.sidebar :deep(.n-list-item.is-active) {
  background: var(--color-brand-light);
  box-shadow: inset 0 0 0 1px var(--color-brand-border);
}

.load-more-bar {
  padding: 8px 12px;
  text-align: center;
  border-top: 1px solid var(--app-border);
}
</style>
