<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import VChart from 'vue-echarts';
import axios from 'axios';
import { use } from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

use([TitleComponent, TooltipComponent, GridComponent, LegendComponent, LineChart, CanvasRenderer]);

const props = defineProps<{
  selectedGpuId: string
}>();

const emit = defineEmits(['select']);

const timeRangeOptions = [
  { label: '1 分钟', value: 1 },
  { label: '5 分钟', value: 5 },
  { label: '15 分钟', value: 15 },
  { label: '1 小时', value: 60 }
];
const selectedRange = ref(5);
const allData = ref<any[]>([]);
const allReservations = ref<any[]>([]);
let timer: number | undefined;

// 分组计算 GPU 数据
const gpuList = computed(() => {
  const cutoffTime = (Date.now() / 1000) - (selectedRange.value * 60);
  const filtered = allData.value.filter(item => item.timestamp >= cutoffTime);
  
  const map = new Map<string, any>();
  filtered.forEach(item => {
    if (!map.has(item.gpu_id)) {
      map.set(item.gpu_id, {
        gpu_id: item.gpu_id,
        gpu_name: item.gpu_name,
        history: []
      });
    }
    map.get(item.gpu_id).history.push(item);
  });
  
  return Array.from(map.values()).sort((a, b) => {
    if (a.gpu_id === 'SYS') return -1;
    if (b.gpu_id === 'SYS') return 1;
    return parseInt(a.gpu_id) - parseInt(b.gpu_id);
  });
});

// 智能诊断：判断当前有没有预约，以及当前有没有人在跑
const getDiagnosis = (gpuId: string, currentUtil: number) => {
  const now = new Date();
  const currentRes = allReservations.value.find(r => {
    if (r.gpu_id !== gpuId) return false;
    const start = new Date(r.start_time);
    const end = new Date(r.end_time);
    return now >= start && now <= end;
  });
  
  const isRunning = currentUtil >= 5.0; // 利用率 >= 5% 判定为在运行任务
  
  if (currentRes) {
    if (isRunning) return { label: `✅ 合规运行中`, user: currentRes.user_id, class: 'bg-green-50 text-green-700 border-green-200' };
    return { label: `💤 预约但闲置`, user: currentRes.user_id, class: 'bg-yellow-50 text-yellow-700 border-yellow-200' };
  } else {
    if (isRunning) return { label: '⚠️ 违规占用 (未预约)', user: '未知', class: 'bg-red-50 text-red-700 border-red-200 animate-pulse' };
    return { label: '🟢 空闲中', user: '无', class: 'bg-slate-50 text-slate-500 border-slate-200' };
  }
};

const fetchMetrics = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8000/api/metrics');
    if (res.data) allData.value = res.data;
    
    // 顺便拉取日历排期，用于智能诊断分析
    const res2 = await axios.get('http://127.0.0.1:8000/api/reservations');
    allReservations.value = res2.data;
  } catch (error) {
    console.error("抓取数据失败:", error);
  }
};

// 抽取基础图表配置以复用
const getBaseChartOption = (times: string[], title: string, seriesName: string, data: string[], colorStr: string, rgbaFill: string) => {
  return {
    title: {
      text: title,
      left: 'center',
      top: 5,
      textStyle: { fontSize: 13, color: '#475569', fontWeight: 'bold' }
    },
    tooltip: { 
      trigger: 'axis', 
      textStyle: { fontSize: 12, color: '#334155' }, 
      padding: [6, 10], 
      backgroundColor: 'rgba(255, 255, 255, 0.95)', 
      borderColor: '#e2e8f0',
      formatter: `{b}<br/><span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:${colorStr};"></span>{a}: {c}%`
    },
    grid: { left: '8%', right: '5%', top: '25%', bottom: '15%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: times, 
      boundaryGap: false, 
      axisLabel: { color: '#94a3b8', fontSize: 10, margin: 10 },
      axisLine: { lineStyle: { color: '#e2e8f0' } }
    },
    yAxis: { 
      type: 'value', 
      max: 100, 
      min: 0, 
      splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
      axisLabel: { color: '#94a3b8', fontSize: 10, formatter: '{value}%' }
    },
    series: [
      { 
        name: seriesName, 
        type: 'line', 
        data: data, 
        smooth: true, 
        showSymbol: false, 
        itemStyle: { color: colorStr }, 
        lineStyle: { width: 2 }, 
        areaStyle: { 
          color: { 
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1, 
            colorStops: [
              { offset: 0, color: rgbaFill }, 
              { offset: 1, color: 'rgba(255,255,255,0)' }
            ] 
          } 
        } 
      }
    ]
  };
};

// 核心利用率图表
const getCoreChartOption = (gpu: any) => {
  const times = gpu.history.map((h: any) => {
    const d = new Date(h.timestamp * 1000);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  });
  const utils = gpu.history.map((h: any) => parseFloat(h.utilization).toFixed(1));
  if (times.length === 0) return {};
  return getBaseChartOption(times, '🔥 核心利用率 (GPU Core)', '核心占用率', utils, '#ef4444', 'rgba(239, 68, 68, 0.3)');
};

// 显存利用率图表
const getMemChartOption = (gpu: any) => {
  const times = gpu.history.map((h: any) => {
    const d = new Date(h.timestamp * 1000);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  });
  const mems = gpu.history.map((h: any) => {
    if (!h.memory_total || h.memory_total === 0) return "0.0";
    return ((h.memory_used / h.memory_total) * 100).toFixed(1);
  });
  if (times.length === 0) return {};
  return getBaseChartOption(times, '💾 显存占用率 (VRAM)', '显存占用率', mems, '#3b82f6', 'rgba(59, 130, 246, 0.3)');
};

const setRange = (mins: number) => selectedRange.value = mins;

onMounted(() => {
  fetchMetrics();
  timer = setInterval(fetchMetrics, 10000) as unknown as number;
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <div class="w-full h-full flex flex-col relative overflow-hidden">
    <!-- 顶部控制条 -->
    <div class="flex justify-between items-center mb-4 px-1 shrink-0">
      <div class="text-sm text-gray-500 font-medium flex items-center gap-2">
        <span class="flex h-2 w-2 relative">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
        </span>
        集群探测到 <span class="text-blue-600 font-bold px-1">{{ gpuList.length }}</span> 张物理节点
      </div>
      <div class="flex gap-1.5">
        <button 
          v-for="opt in timeRangeOptions" :key="opt.value" @click="setRange(opt.value)"
          class="px-2.5 py-1 text-xs font-medium rounded transition-all duration-200 border"
          :class="selectedRange === opt.value ? 'bg-blue-50 text-blue-600 border-blue-200 shadow-sm' : 'bg-white text-gray-500 border-gray-200 hover:bg-gray-50 hover:text-gray-700'"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>
    
    <!-- 大屏新排版：一卡一行，防溢出 -->
    <div class="flex-1 overflow-y-auto min-h-0 pr-2 pb-2 custom-scrollbar">
      <div class="grid grid-cols-1 gap-6">
        <div 
          v-for="gpu in gpuList" 
          :key="gpu.gpu_id" 
          @click="emit('select', gpu.gpu_id)"
          class="cursor-pointer border-2 rounded-xl flex flex-col transition-all duration-200 bg-white"
          :class="props.selectedGpuId === gpu.gpu_id ? 'border-blue-500 shadow-md ring-4 ring-blue-50/50' : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'"
          style="min-height: 280px;"
        >
          <!-- 详细的头部信息栏 -->
          <div class="px-5 py-3.5 border-b border-gray-100 flex flex-wrap lg:flex-nowrap justify-between items-center gap-4 shrink-0 rounded-t-xl"
               :class="props.selectedGpuId === gpu.gpu_id ? 'bg-blue-50/60' : 'bg-slate-50/40'">
            
            <!-- 左侧：基础显卡信息 -->
            <div class="flex items-center gap-3 min-w-[280px]">
              <span class="inline-flex items-center justify-center px-2 py-1 rounded bg-slate-800 text-white text-xs font-bold shadow-sm shrink-0">
                CUDA ID: {{ gpu.gpu_id }}
              </span>
              <span class="text-base font-bold text-slate-800 truncate max-w-[200px]" :title="gpu.gpu_name">{{ gpu.gpu_name }}</span>
            </div>

            <!-- 中间：动态详情 (工号, 容量) -->
            <div class="flex items-center flex-wrap gap-4 text-xs font-medium text-slate-600">
              <div class="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-md shadow-sm">
                <span class="text-gray-400">总容量:</span>
                <span class="font-bold text-slate-700">{{ gpu.history.length ? gpu.history[gpu.history.length - 1].memory_total : 0 }} MB</span>
              </div>
              <div class="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-md shadow-sm">
                <span class="text-gray-400">当前占用工号:</span>
                <span class="font-bold" :class="getDiagnosis(gpu.gpu_id, gpu.history[gpu.history.length - 1]?.utilization || 0).user === '未知' ? 'text-red-500' : 'text-slate-700'">
                  {{ getDiagnosis(gpu.gpu_id, gpu.history[gpu.history.length - 1]?.utilization || 0).user }}
                </span>
              </div>
            </div>
            
            <!-- 右侧：诊断状态和绝对值数据 -->
            <div class="flex items-center flex-wrap gap-3 shrink-0">
              <span v-if="gpu.history.length" 
                    class="px-3 py-1 text-xs font-bold rounded-full border shadow-sm"
                    :class="getDiagnosis(gpu.gpu_id, gpu.history[gpu.history.length - 1].utilization).class">
                {{ getDiagnosis(gpu.gpu_id, gpu.history[gpu.history.length - 1].utilization).label }}
              </span>
              
              <div class="flex gap-4 text-sm font-bold bg-white px-3 py-1.5 rounded-md shadow-sm border border-gray-200">
                <span class="text-red-500 flex items-center gap-1.5" title="核心占用率">
                  🔥 <span v-if="gpu.history.length">{{ parseFloat(gpu.history[gpu.history.length - 1].utilization).toFixed(1) }}%</span>
                </span>
                <span class="text-blue-600 flex items-center gap-1.5" title="已用显存">
                  💾 <span v-if="gpu.history.length">{{ gpu.history[gpu.history.length - 1].memory_used }} MB</span>
                </span>
              </div>
            </div>
          </div>
          
          <!-- ECharts 图表拆分：一行两列，左核心右显存 -->
          <div class="flex-1 w-full flex flex-col md:flex-row min-h-[220px] p-2 gap-3">
            <div class="flex-1 min-h-[200px] border border-gray-100 rounded-lg bg-gray-50/30">
              <v-chart class="w-full h-full" :option="getCoreChartOption(gpu)" autoresize />
            </div>
            <div class="flex-1 min-h-[200px] border border-gray-100 rounded-lg bg-gray-50/30">
              <v-chart class="w-full h-full" :option="getMemChartOption(gpu)" autoresize />
            </div>
          </div>
        </div>
      </div>
      
      <div v-if="gpuList.length === 0" class="h-full flex items-center justify-center text-gray-400 text-sm flex-col gap-3">
        <svg class="animate-spin h-6 w-6 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        <span>正在拉取多卡集群节点数据...</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 10px; }
</style>
