<script setup lang="ts">
import { ref } from 'vue'
import GPUChart from './components/GPUChart.vue'
import GPUCalendar from './components/GPUCalendar.vue'

const selectedGpuId = ref<string>('0') // 默认选中物理卡 0

const handleGpuSelect = (gpuId: string) => {
  selectedGpuId.value = gpuId
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 flex flex-col font-sans">
    <!-- 头部 NavBar -->
    <header class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
      <div class="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-xl">
            G
          </div>
          <h1 class="text-xl font-bold text-gray-800 tracking-tight">实验室 GPU 算力预约与监控看板</h1>
        </div>
        <div class="flex items-center gap-4 text-sm text-gray-600">
          <span class="px-3 py-1 bg-green-100 text-green-700 rounded-full font-medium">当前身份: 组内成员 (当前用户)</span>
        </div>
      </div>
    </header>

    <!-- 主体内网格布局 -->
    <main class="flex-1 max-w-[1600px] w-full mx-auto p-4 md:p-6 grid grid-cols-1 xl:grid-cols-12 gap-6 xl:h-[calc(100vh-64px)] overflow-y-auto xl:overflow-hidden">
      
      <!-- 左侧：日历排班表 (占 7 列) -->
      <section class="xl:col-span-7 flex flex-col xl:h-full min-h-[500px]">
        <div class="flex items-center justify-between mb-4 flex-shrink-0">
          <h2 class="text-lg font-semibold text-gray-800 flex items-center gap-2">
            <span class="text-blue-500">📅</span> [GPU {{ selectedGpuId }}] 专属预约排期表
          </h2>
          <span class="text-xs text-gray-400">点击右侧显卡卡片可切换排班表，拖拽日历可发起新预约</span>
        </div>
        
        <div class="flex-1 min-h-0 bg-white rounded-xl shadow-sm border border-gray-100 p-4">
          <GPUCalendar :gpu-id="selectedGpuId" />
        </div>
      </section>

      <!-- 右侧：实时监控图表 (占 5 列) -->
      <section class="xl:col-span-5 flex flex-col xl:h-full min-h-[500px]">
        <div class="flex items-center justify-between mb-4 flex-shrink-0">
          <h2 class="text-lg font-semibold text-gray-800 flex items-center gap-2">
            <span class="text-red-500">📈</span> 实时硬件状态墙 & 违规占用检测
          </h2>
          <span class="flex h-3 w-3">
            <span class="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
          </span>
        </div>
        
        <div class="flex-1 min-h-0 bg-transparent rounded-xl flex flex-col">
          <GPUChart :selected-gpu-id="selectedGpuId" @select="handleGpuSelect" />
        </div>
      </section>
      
    </main>
  </div>
</template>

<style>
/* 确保组件撑满容器高度 */
html, body, #app {
  height: 100%;
}
</style>