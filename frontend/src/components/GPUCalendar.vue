<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import FullCalendar from '@fullcalendar/vue3';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import axios from 'axios';

const props = defineProps<{
  gpuId: string
}>()

const isSubmitting = ref(false);
const toastMsg = ref('');

const showToast = (msg: string) => {
  toastMsg.value = msg;
  setTimeout(() => {
    toastMsg.value = '';
  }, 3000);
};

const calendarOptions = ref<any>({
  plugins: [timeGridPlugin, interactionPlugin],
  initialView: 'timeGridWeek',
  locale: 'zh-cn', // 中文支持
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'timeGridWeek,timeGridDay'
  },
  events: [],
  slotMinTime: '00:00:00',
  slotMaxTime: '24:00:00',
  allDaySlot: false,
  selectable: true,
  selectOverlap: false, // 禁止重叠选择
  eventOverlap: false,  // 禁止重叠拖拽
  select: handleDateSelect,
  eventClick: handleEventClick,
  height: '100%',
});

const fetchReservations = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8000/api/reservations');
    const data = res.data;
    
    // 只过滤出当前选中的那张显卡的数据！
    const filteredData = data.filter((r: any) => r.gpu_id === props.gpuId);

    calendarOptions.value.events = filteredData.map((r: any) => ({
      id: String(r.id),
      title: `[${r.user_id}] ${r.purpose}`,
      start: r.start_time,
      end: r.end_time,
      backgroundColor: r.user_id === '当前用户' ? '#10b981' : '#9ca3af',
      borderColor: r.user_id === '当前用户' ? '#059669' : '#6b7280',
      extendedProps: {
        userId: r.user_id
      }
    }));
  } catch (error) {
    console.error('获取预约数据失败:', error);
  }
};

// 监听选中的显卡变化，一旦右侧图表切卡，左边日历就重载数据
watch(() => props.gpuId, () => {
  fetchReservations();
});

// 拖拽发起真实后端预约请求
async function handleDateSelect(selectInfo: any) {
  const calendarApi = selectInfo.view.calendar;
  calendarApi.unselect(); 
  
  const purpose = prompt(`正在为 GPU ${props.gpuId} 预约时间段\n请输入您的预约用途:`);
  
  if (purpose) {
    try {
      // 真实 POST 请求
      isSubmitting.value = true;
      const res = await axios.post('http://127.0.0.1:8000/api/reservations', {
        user_id: '当前用户',
        gpu_id: props.gpuId,
        start_time: selectInfo.startStr.split('+')[0], // strip timezone for simple sqlite comparison
        end_time: selectInfo.endStr.split('+')[0],
        purpose: purpose
      });
      
      // 添加到日历
      calendarApi.addEvent({
        id: String(res.data.id),
        title: `[当前用户] ${purpose}`,
        start: selectInfo.startStr,
        end: selectInfo.endStr,
        backgroundColor: '#10b981',
        borderColor: '#059669',
        extendedProps: { userId: '当前用户' }
      });
      showToast('预约成功！');
    } catch (err: any) {
      if (err.response && err.response.status === 409) {
        showToast(err.response.data.detail); // 弹出防冲突拦截报错
      } else if (err.response && err.response.status === 400) {
        showToast(err.response.data.detail);
      } else {
        showToast('预约失败：' + err.message);
      }
    } finally {
      isSubmitting.value = false;
    }
  }
}

// 点击删除真实预约
async function handleEventClick(clickInfo: any) {
  const isCurrentUser = clickInfo.event.extendedProps.userId === '当前用户';
  if (isCurrentUser) {
    if (confirm(`您确定要取消该预约吗?\n'${clickInfo.event.title}'`)) {
      isSubmitting.value = true;
      try {
        await axios.delete(`http://127.0.0.1:8000/api/reservations/${clickInfo.event.id}`);
        clickInfo.event.remove();
        showToast('取消成功');
      } catch(e) {
        showToast('取消失败');
      } finally {
        isSubmitting.value = false;
      }
    }
  } else {
    showToast(`这是他人的占用时间块，不可取消。\n预约信息: ${clickInfo.event.title}`);
  }
}

onMounted(() => {
  fetchReservations();
});
</script>

<template>
  <div class="h-full w-full relative">
    <FullCalendar :options="calendarOptions" class="h-full" />
    
    <!-- Loading Overlay -->
    <div v-if="isSubmitting" class="absolute inset-0 bg-white/60 backdrop-blur-[1px] flex items-center justify-center z-50">
      <div class="flex flex-col items-center gap-3">
        <svg class="animate-spin h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        <span class="text-sm font-medium text-gray-600">处理中...</span>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toastMsg" class="absolute top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 bg-slate-800 text-white text-sm font-medium rounded-lg shadow-lg transition-opacity duration-300">
      {{ toastMsg }}
    </div>
  </div>
</template>

<style scoped>
:deep(.fc-theme-standard td), :deep(.fc-theme-standard th) {
  border-color: #e5e7eb;
}
:deep(.fc-col-header-cell) {
  background-color: #f9fafb;
  padding: 8px 0;
}
:deep(.fc-event) {
  cursor: pointer;
  border-radius: 4px;
  padding: 2px 4px;
  font-size: 0.85rem;
}
</style>