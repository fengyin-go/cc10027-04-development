"""自动化采集 时间线接口：作业时间序列、运行批次与失败运行记录。"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.schemas import ActionPayload, ActionResult, EntryPayload, RunPayload
from app.services.robotflow import RobotflowService

router = APIRouter(prefix="/api/robotflow", tags=["自动化采集"])
service = RobotflowService()
LIST_FIELDS = ["流程编号", "输入来源", "页面定位器", "等待条件", "动作顺序", "结果字段", "超时秒数", "运行批次"]
EXPORT_FIELDS = ["流程编号", "运行批次", "批次状态", "开始时间", "结束时间", "动作序号", "动作名称", "动作状态", "超时原因", "结果字段", "失败记录"]
STATUSES = ["草稿", "待校验", "已启用", "已停用"]


def csv_cell(value: Any) -> str:
    text = str(value) if value is not None else ""
    if text and text[0] in "=+-@":
        text = "'" + text
    return '"' + text.replace('"', '""') + '"'


@router.get("")
def list_entries() -> dict[str, Any]:
    items = service.get_timeline()
    return {"items": items}


@router.get("/export")
def export_entries() -> StreamingResponse:
    rows = service.get_run_export_rows()
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(EXPORT_FIELDS)
    for row in rows:
        writer.writerow([csv_cell(row.get(k, "")) for k in EXPORT_FIELDS])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=robotflow.csv"})


@router.get("/failures")
def list_failures() -> dict[str, Any]:
    """失败运行记录清单：保留未执行动作与超时位置。"""
    return {"items": service.list_failures()}


@router.get("/{entry_id}")
def get_entry(entry_id: int) -> dict:
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"自动化流程 {entry_id} 不存在")
    return entry


@router.get("/{entry_id}/runs")
def get_runs(entry_id: int) -> dict[str, Any]:
    """该流程的运行批次与失败运行记录。"""
    data = service.get_runs(entry_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"自动化流程 {entry_id} 不存在")
    return data


@router.post("/{entry_id}/runs")
def run_batch(entry_id: int, payload: RunPayload) -> ActionResult:
    """执行一次自动化采集；相同运行批次只采纳首个请求，中断后从失败步骤续做。"""
    run, message, _created = service.run_batch(entry_id, payload.model_dump())
    if run is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=run)


@router.post("")
def create_entry(payload: EntryPayload) -> ActionResult:
    entry_or_none, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="自动化流程已登记", entry=entry_or_none)


@router.post("/{entry_id}/actions")
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    entry_or_none, message = service.run_action(entry_id, payload.action)
    if entry_or_none is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry_or_none)
