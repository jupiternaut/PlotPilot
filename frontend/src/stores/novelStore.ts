import { defineStore } from 'pinia'
import { ref } from 'vue'
import { novelApi, type NovelDTO } from '../api/novel'
import { useStatsStore } from './statsStore'
import { useMessage } from 'naive-ui'

export interface Book {
  slug: string
  title: string
  stage: string
  stage_label: string
  genre: string
  chapter_count: number
  word_count: number
}

export const useNovelStore = defineStore('novel', () => {
  const books = ref<Book[]>([])
  const loading = ref(false)
  const statsStore = useStatsStore()
  
  // Naive UI message and dialog provider can only be used inside setup of components
  // So we pass them as arguments or rely on the global provider if available.
  // For now, we handle basic error/success logging.

  const getStageLabel = (stage: string): string => {
    const labels: Record<string, string> = {
      planning: '规划中',
      writing: '写作中',
      reviewing: '审稿中',
      completed: '已完成',
    }
    return labels[stage] || stage
  }

  const formatWordCount = (count: number): string => {
    if (count >= 10000) {
      return (count / 10000).toFixed(1) + '万字'
    }
    return count + '字'
  }

  const fetchBooks = async () => {
    loading.value = true
    try {
      const novels = await novelApi.listNovels()
      books.value = novels.map((novel: NovelDTO) => ({
        slug: novel.id,
        title: novel.title,
        stage: novel.stage,
        stage_label: getStageLabel(novel.stage),
        genre: '',
        chapter_count: novel.chapters?.length || 0,
        word_count: novel.total_word_count,
      }))
    } catch (error) {
      console.error('Failed to fetch books:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  const deleteBook = async (slug: string) => {
    try {
      await novelApi.deleteNovel(slug)
      books.value = books.value.filter(b => b.slug !== slug)
      // 同步刷新全局统计
      await statsStore.loadGlobalStats(true)
    } catch (error) {
      console.error('Failed to delete book:', error)
      throw error
    }
  }

  const createBook = async (payload: any) => {
    try {
      const result = await novelApi.createNovel(payload)
      // 创建成功后重新获取列表或手动 push
      await fetchBooks()
      return result
    } catch (error) {
       console.error('Failed to create book:', error)
       throw error
    }
  }

  return { 
    books, 
    loading, 
    fetchBooks, 
    deleteBook, 
    createBook, 
    getStageLabel, 
    formatWordCount 
  }
})
