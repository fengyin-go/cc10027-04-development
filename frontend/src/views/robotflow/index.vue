<template>
  <section class="page" data-module="robotflow">
    <header class="page-head">
      <div><h2>自动化采集</h2><p class="page-desc">维护自动化流程的输入、执行约束与结果记录，为自动化采集提供可验证的数据工程流程。</p></div>
      <div class="page-actions">
        <button class="btn primary" type="button" data-testid="open-create" @click="openCreate">登记自动化流程</button>
        <button class="btn" type="button" data-testid="export" @click="exportRows">导出作业清单</button>
      </div>
    </header>
    <div class="filter-bar">
      <label><span>开始日期</span><input type="date" v-model="dateFrom" /></label>
      <label><span>结束日期</span><input type="date" v-model="dateTo" /></label>
      <button class="btn" type="button" @click="reload">查询</button>
    </div>
    <div class="timeline-wrap">
      <div v-for="item in timelineItems" :key="item.id" class="timeline-row">
        <span class="timeline-label">{{ item.name || item.label }}</span>
        <div class="timeline-track">
          <div class="timeline-bar" :class="`status-${item.status}`" :style="{ left: barLeft(item) + '%', width: barWidth(item) + '%' }" :data-testid="`bar-${item.id}`" :title="`${item.start} ~ ${item.end}`" @click="selectItem(item)">&nbsp;</div>
        </div>
        <span style="font-size:12px;color:var(--muted);margin-left:8px;">{{ item.start }} ~ {{ item.end }}</span>
        <span style="font-size:12px;color:var(--muted);margin-left:8px;">{{ item.运行批次 || '未运行' }}</span>
      </div>
      <p v-if="!timelineItems.length" style="text-align:center;color:var(--muted)">暂无作业记录</p>
    </div>
    <div v-if="selectedItem" class="timeline-log" data-testid="timeline-log">
      <strong>{{ selectedItem.name || selectedItem.label }}</strong> — 状态：{{ selectedItem.status }} — 当前批次：{{ selectedItem.运行批次 || '未运行' }}（{{ selectedItem.批次状态 }}）
      <div style="margin-top:4px;white-space:pre-wrap;">{{ selectedItem.logs || '暂无日志' }}</div>
    </div>
    <div v-if="selectedItem" class="run-panel">
      <div class="run-actions">
        <input v-model="timeoutStep" type="number" min="1" placeholder="模拟超时步骤（可选）" />
        <button class="btn primary" type="button" data-testid="run-collect" @click="runCollect">执行采集</button>
        <span class="run-hint">相同运行批次只采纳首个采集请求；中断后从失败步骤续做，成功动作自动复用。</span>
      </div>
      <div v-for="batch in runBatches" :key="batch.运行批次" class="batch-block" :data-testid="`batch-${batch.运行批次}`">
        <div class="batch-head">
          批次 {{ batch.运行批次 }}（{{ batch.状态 }}） {{ batch.开始时间 }} ~ {{ batch.结束时间 }} — {{ batch.结果摘要 }}
          <span v-if="batch.续跑来源">｜续跑来源：{{ batch.续跑来源 }}</span>
        </div>
        <table class="data-table">
          <thead><tr><th>动作序号</th><th>动作</th><th>状态</th><th>开始时间</th><th>结束时间</th><th>超时原因</th></tr></thead>
          <tbody>
            <tr v-for="s in batch.steps" :key="`${batch.运行批次}-${s.序号}`">
              <td>{{ s.序号 }}</td>
              <td>{{ s.动作 }}</td>
              <td>{{ s.状态 }}<template v-if="s.来源批次">（{{ s.来源批次 }}）</template></td>
              <td>{{ s.开始时间 || '—' }}</td>
              <td>{{ s.结束时间 || '—' }}</td>
              <td>{{ s.超时原因 || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <table v-if="failures.length" class="data-table" data-testid="failure-table">
        <thead><tr><th>记录编号</th><th>运行批次</th><th>失败步骤</th><th>失败动作</th><th>超时位置</th><th>未执行动作</th></tr></thead>
        <tbody>
          <tr v-for="f in failures" :key="f.记录编号">
            <td>{{ f.记录编号 }}</td>
            <td>{{ f.运行批次 }}</td>
            <td>第{{ f.失败步骤 }}步</td>
            <td>{{ f.失败动作 }}</td>
            <td>{{ f.超时位置 }}</td>
            <td>{{ (f.未执行动作 || []).join('、') || '无' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="showCreate" class="modal-backdrop" data-testid="create-modal">
      <form class="modal" @submit.prevent="submitCreate"><h3>登记自动化流程</h3>
        <label v-for="(field, i) in columns" :key="field" class="create-field"><span>{{ field }}<template v-if="i >= 3">（选填）</template></span><input v-model="createValues[field]" :placeholder="`请输入${field}`" :required="i < 3" /></label>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
          <button class="btn" type="button" @click="showCreate=false">取消</button>
          <button class="btn primary" type="submit" data-testid="submit-create">提交</button>
        </div>
      </form>
    </div>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { request } from '@/api/client'
const ENDPOINT = '/api/robotflow'
const columns = ["流程编号", "输入来源", "页面定位器", "等待条件", "动作顺序", "结果字段", "超时秒数", "运行批次"]
const timelineItems = ref<any[]>([])
const selectedItem = ref<any>(null)
const dateFrom = ref(''); const dateTo = ref('')
const errorMessage = ref(''); const showCreate = ref(false)
const createValues = ref<Record<string,string>>({})
const allItems = ref<any[]>([])
const runBatches = ref<any[]>([])
const failures = ref<any[]>([])
const timeoutStep = ref('')
function barLeft(item: any) { const all = allItems.value.filter(i => i.start && i.end); if(!all.length) return 0; const min = Math.min(...all.map(i => new Date(i.start).getTime())); const max = Math.max(...all.map(i => new Date(i.end).getTime())); const range = max - min || 86400000; return ((new Date(item.start).getTime() - min) / range) * 100 }
function barWidth(item: any) { const all = allItems.value.filter(i => i.start && i.end); if(!all.length) return 20; const min = Math.min(...all.map(i => new Date(i.start).getTime())); const max = Math.max(...all.map(i => new Date(i.end).getTime())); const range = max - min || 86400000; return Math.max(5, ((new Date(item.end).getTime() - new Date(item.start).getTime()) / range) * 100) }
async function selectItem(item: any) {
  if (selectedItem.value?.id === item.id) { selectedItem.value = null; runBatches.value = []; failures.value = []; return }
  selectedItem.value = item
  await loadRuns()
}
async function loadRuns() {
  if (!selectedItem.value) return
  try {
    const res = await request(`${ENDPOINT}/${selectedItem.value.id}/runs`)
    const data = await res.json()
    runBatches.value = data.items || []
    failures.value = data.failures || []
  } catch(e) { errorMessage.value = '加载失败' }
}
async function runCollect() {
  const id = selectedItem.value?.id
  if (!id) return
  const flowNo = String(selectedItem.value.name || '')
  const day = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  const seq = String(runBatches.value.length + 1).padStart(2, '0')
  const payload: Record<string, any> = { 运行批次: `RUN-${day}-${flowNo.slice(-4)}-${seq}` }
  if (timeoutStep.value) payload.超时步骤 = Number(timeoutStep.value)
  try {
    await request(`${ENDPOINT}/${id}/runs`, { method: 'POST', body: JSON.stringify(payload) })
    timeoutStep.value = ''
    await reload()
    const again = allItems.value.find((i: any) => i.id === id)
    if (again) { selectedItem.value = again; await loadRuns() }
  } catch(e) { errorMessage.value = '执行失败' }
}
async function reload() {
  try { const res = await request(ENDPOINT); const data = await res.json(); allItems.value = data.items || []; applyFilter() } catch(e) { errorMessage.value = '加载失败' }
}
function applyFilter() {
  let items = allItems.value
  if(dateFrom.value) items = items.filter((i: any) => i.start >= dateFrom.value)
  if(dateTo.value) items = items.filter((i: any) => i.end <= dateTo.value)
  timelineItems.value = items; selectedItem.value = null
}
function openCreate() { createValues.value = {}; showCreate.value = true }
async function submitCreate() {
  try { const res = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values: createValues.value }) }); if(!res.ok) throw new Error('创建失败'); showCreate.value = false; await reload() } catch(e: any) { errorMessage.value = e.message }
}
function exportRows() { window.open(`${ENDPOINT}/export`, '_blank') }
onMounted(reload)
</script>
<style scoped>
.run-panel { margin-top: 8px; background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.run-actions { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
.run-actions input { width: 160px; padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; }
.run-hint { font-size: 12px; color: var(--muted); }
.batch-block { margin-bottom: 12px; }
.batch-head { font-size: 13px; margin-bottom: 4px; }
</style>
