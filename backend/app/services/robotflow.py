"""自动化采集 时间线服务：运行批次、失败运行记录与作业时间序列。

等待动作调用链：路由 POST /{id}/runs → run_batch → 逐步评估等待条件（_execute_steps）
→ 等待超时则中断并生成失败运行记录（_record_failure）。

约定：
- 同一运行批次只采纳首个自动化采集请求（幂等），重复提交直接返回首个批次；
- 执行中断后从失败步骤续做，已成功的动作复用旧批次结果、不重新写入成功记录；
- 旧批次日志只读，新的超时原因只追加到当前运行批次，不覆盖历史证据。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from app.store import store

MODULE = "robotflow"
AUX_RUNS = "robotflow_runs"
AUX_FAILURES = "robotflow_failures"
REQUIRED_FIELDS = ["流程编号", "输入来源", "页面定位器"]
ALL_FIELDS = ["流程编号", "输入来源", "页面定位器", "等待条件", "动作顺序", "结果字段", "超时秒数", "运行批次"]
STATUS_ORDER = ["草稿", "待校验", "已启用", "已停用"]
ACTION_RULES = {"提交校验": "待校验", "启用配置": "已启用", "停用配置": "已停用"}
NEGATIVE_ACTIONS = ["停用配置"]
DEFAULT_ACTIONS = ["登录", "切换到下一页", "下载"]
TIME_FMT = "%Y-%m-%d %H:%M:%S"
STEP_SECONDS = 5  # 演示环境中一步成功动作的执行耗时


def _fmt(moment: datetime) -> str:
    return moment.strftime(TIME_FMT)


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _split_actions(raw: Any) -> list[str]:
    parts = [p.strip() for p in re.split(r"[,，、;；/→>\n]+", str(raw or "")) if p.strip()]
    return parts or list(DEFAULT_ACTIONS)


def _split_fields(raw: Any) -> list[str]:
    return [p.strip() for p in re.split(r"[,，、;；/]+", str(raw or "")) if p.strip()]


class RobotflowService:
    # ---------- 运行批次与失败运行记录 ----------
    def _runs(self) -> list[dict[str, Any]]:
        return store.aux_rows(AUX_RUNS)

    def _failures(self) -> list[dict[str, Any]]:
        return store.aux_rows(AUX_FAILURES)

    def _flow_runs(self, flow_no: str) -> list[dict[str, Any]]:
        return [run for run in self._runs() if str(run.get("流程编号", "")) == flow_no]

    def get_runs(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        flow_no = str(entry.get("流程编号", ""))
        failures = [f for f in self._failures() if str(f.get("流程编号", "")) == flow_no]
        return {"items": self._flow_runs(flow_no), "failures": failures,
                "当前批次": str(entry.get("运行批次", ""))}

    def list_failures(self) -> list[dict[str, Any]]:
        return list(self._failures())

    def run_batch(self, entry_id: int, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str, bool]:
        """执行一次自动化采集，返回 (运行批次, 消息, 是否新批次)。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"自动化流程 {entry_id} 不存在或已归档", False
        batch_id = str(payload.get("运行批次") or "").strip()
        if not batch_id:
            return None, "缺少运行批次：每次采集必须携带唯一运行批次", False
        # 幂等：重复提交相同运行批次只认首个自动化采集请求
        for run in self._runs():
            if str(run.get("运行批次", "")) == batch_id:
                return run, f"运行批次 {batch_id} 已存在，仅采纳首个自动化采集请求", False

        flow_no = str(entry.get("流程编号", ""))
        actions = _split_actions(entry.get("动作顺序"))
        wait_cond = str(payload.get("等待条件") or entry.get("等待条件") or "").strip()
        timeout_secs = _parse_int(entry.get("超时秒数"), 30)

        # 续跑定位：最近一个批次失败时，从失败步骤续做；成功动作复用旧批次结果
        flow_runs = self._flow_runs(flow_no)
        last_run = flow_runs[-1] if flow_runs else None
        resume_from = 1
        reuse_source = ""
        if last_run and last_run.get("状态") == "失败" and _parse_int(last_run.get("失败步骤"), 0) > 0:
            resume_from = _parse_int(last_run["失败步骤"], 1)
            reuse_source = str(last_run.get("运行批次", ""))

        # 等待条件评估（等待动作调用链的修改点）：显式指定超时步骤优先，
        # 其次看本次携带的等待条件是否仍标记为超时/失效。
        timeout_step = payload.get("超时步骤")
        timeout_step = _parse_int(timeout_step, 0) if timeout_step is not None else 0
        if not timeout_step and wait_cond and ("超时" in wait_cond or "失效" in wait_cond):
            timeout_step = resume_from
        if timeout_step:
            if timeout_step < resume_from:
                return None, f"第{timeout_step}步已成功并可复用，不能作为本次超时步骤", False
            if timeout_step > len(actions):
                return None, f"超时步骤 {timeout_step} 超出动作顺序范围（共 {len(actions)} 步）", False

        started = datetime.now()
        steps: list[dict[str, Any]] = []
        # 复用前序成功动作：只引用旧批次结果，不重新写入一条成功动作
        if resume_from > 1 and last_run:
            for old in last_run.get("steps", []):
                if _parse_int(old.get("序号"), 0) < resume_from and old.get("状态") == "成功":
                    steps.append({
                        "序号": _parse_int(old.get("序号"), 0), "动作": old.get("动作", ""),
                        "状态": "复用", "开始时间": old.get("开始时间", ""), "结束时间": old.get("结束时间", ""),
                        "等待条件": old.get("等待条件", ""), "超时秒数": old.get("超时秒数", ""),
                        "超时原因": "", "来源批次": reuse_source,
                    })
        cursor = started
        failed_at = 0
        timeout_reason = ""
        for idx in range(resume_from, len(actions) + 1):
            name = actions[idx - 1]
            step = {"序号": idx, "动作": name, "状态": "未执行", "开始时间": _fmt(cursor),
                    "结束时间": "", "等待条件": wait_cond, "超时秒数": str(timeout_secs),
                    "超时原因": "", "来源批次": ""}
            if timeout_step == idx:
                # 等待条件在超时秒数内未满足：动作中断，后续动作不再执行
                cursor += timedelta(seconds=timeout_secs)
                step["状态"] = "失败"
                step["结束时间"] = _fmt(cursor)
                timeout_reason = f"等待条件「{wait_cond or '未配置'}」在 {timeout_secs} 秒内未满足：动作「{name}」执行中断"
                step["超时原因"] = timeout_reason
                failed_at = idx
                steps.append(step)
                break
            cursor += timedelta(seconds=STEP_SECONDS)
            step["状态"] = "成功"
            step["结束时间"] = _fmt(cursor)
            steps.append(step)
        # 未执行动作保留在当前批次里，供失败记录与导出清单引用
        for idx in range(len(steps) + 1, len(actions) + 1):
            steps.append({"序号": idx, "动作": actions[idx - 1], "状态": "未执行",
                          "开始时间": "", "结束时间": "", "等待条件": wait_cond,
                          "超时秒数": str(timeout_secs), "超时原因": "", "来源批次": ""})

        result_fields = _split_fields(entry.get("结果字段"))
        if failed_at:
            done = sum(1 for s in steps if s["状态"] in ("成功", "复用"))
            rows_collected = 0
            summary = f"采集中断：完成 {done}/{len(actions)} 步，第{failed_at}步「{actions[failed_at - 1]}」等待超时"
            status = "失败"
        else:
            rows_collected = len(result_fields) * 40
            summary = f"采集完成：{len(result_fields)} 个结果字段，共 {rows_collected} 行"
            status = "成功"
        run = {
            "id": max((int(r.get("id", 0)) for r in self._runs()), default=0) + 1,
            "流程编号": flow_no,
            "运行批次": batch_id,
            "状态": status,
            "开始时间": _fmt(started),
            "结束时间": _fmt(cursor),
            "输入来源": str(entry.get("输入来源", "")),
            "结果字段": str(entry.get("结果字段", "")),
            "采集行数": rows_collected,
            "结果摘要": summary,
            "失败步骤": failed_at,
            "续跑来源": reuse_source,
            "steps": steps,
        }
        self._runs().append(run)
        entry["运行批次"] = batch_id  # 当前批次指针：运行页面与转换入口共用同一批次
        if failed_at:
            record = self._record_failure(entry, run, timeout_reason)
            entry["pending"] = True
            entry["abnormal"] = True
            return run, f"批次 {batch_id} 第{failed_at}步等待超时，已生成失败运行记录 {record['记录编号']}", True
        entry["pending"] = False
        entry["abnormal"] = False
        return run, f"批次 {batch_id} 采集完成：{summary}", True

    def _record_failure(self, entry: dict[str, Any], run: dict[str, Any], timeout_reason: str) -> dict[str, Any]:
        """重算本次采集结果并生成失败运行记录：保留未执行动作与超时位置。"""
        failed_at = _parse_int(run.get("失败步骤"), 0)
        steps = run.get("steps", [])
        failed_step = steps[failed_at - 1] if 0 < failed_at <= len(steps) else {}
        done = [s["动作"] for s in steps if s.get("状态") in ("成功", "复用")]
        todo = [s["动作"] for s in steps if s.get("状态") == "未执行"]
        next_id = max((int(f.get("id", 0)) for f in self._failures()), default=0) + 1
        record = {
            "id": next_id,
            "记录编号": f"FR-{next_id:04d}",
            "流程编号": run["流程编号"],
            "输入来源": str(entry.get("输入来源", "")),
            "结果字段": str(entry.get("结果字段", "")),
            "运行批次": run["运行批次"],
            "失败步骤": failed_at,
            "失败动作": failed_step.get("动作", ""),
            "超时位置": f"第{failed_at}步「{failed_step.get('动作', '')}」等待条件「{failed_step.get('等待条件', '')}」",
            "超时原因": timeout_reason,
            "已完成动作": done,
            "未执行动作": todo,
            "发生时间": run["结束时间"],
        }
        self._failures().append(record)
        return record

    # ---------- 时间线与导出 ----------
    def get_timeline(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for i, row in enumerate(store.rows(MODULE)):
            flow_no = str(row.get("流程编号", ""))
            runs = self._flow_runs(flow_no)
            latest = runs[-1] if runs else None
            if latest:
                start = str(latest.get("开始时间", "")).split(" ")[0]
                end = str(latest.get("结束时间", "")).split(" ")[0]
                batch_no = str(latest.get("运行批次", ""))
                batch_status = str(latest.get("状态", ""))
            else:
                start = end = date.today().isoformat()
                batch_no = ""
                batch_status = "未运行"
            items.append({
                "id": int(row.get("id", i + 1)),
                "name": flow_no,
                "start": start,
                "end": end,
                "status": str(row.get("status", STATUS_ORDER[0])),
                "运行批次": batch_no,
                "批次状态": batch_status,
                "结果字段": str(row.get("结果字段", "")),
                "logs": self._trajectory(row, runs),
            })
        return items

    def _trajectory(self, row: dict[str, Any], runs: list[dict[str, Any]]) -> str:
        """把成功动作与失败运行记录合成一份可读运行轨迹；旧批次内容只读。"""
        if not runs:
            return "尚未产生运行批次"
        flow_no = str(row.get("流程编号", ""))
        failures = {f["运行批次"]: f for f in self._failures() if str(f.get("流程编号", "")) == flow_no}
        blocks: list[str] = []
        for run in runs:
            lines = [f"批次 {run['运行批次']}（{run['状态']}）{run['开始时间']} ~ {run['结束时间']}"]
            if run.get("续跑来源"):
                lines.append(f"  续跑来源：批次 {run['续跑来源']}，复用其成功动作")
            for s in run.get("steps", []):
                label = f"第{s['序号']}步「{s['动作']}」"
                if s["状态"] == "复用":
                    lines.append(f"  {label}复用批次 {s['来源批次']} 的成功结果（{s['开始时间']} ~ {s['结束时间']}）")
                elif s["状态"] == "未执行":
                    lines.append(f"  {label}未执行")
                elif s["状态"] == "失败":
                    lines.append(f"  {label}失败：{s['超时原因']}")
                else:
                    lines.append(f"  {label}成功 [{s['开始时间']} ~ {s['结束时间']}]")
            lines.append(f"  结果：{run['结果摘要']}（结果字段：{run['结果字段']}）")
            failure = failures.get(run["运行批次"])
            if failure:
                todo = "、".join(failure.get("未执行动作") or []) or "无"
                lines.append(f"  失败记录 {failure['记录编号']}：超时位置 {failure['超时位置']}；未执行动作 {todo}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def get_run_export_rows(self) -> list[dict[str, Any]]:
        """导出清单：每步状态与运行批次一行，与运行日志指向同一批次。"""
        failure_by_batch = {str(f.get("运行批次", "")): f for f in self._failures()}
        runs_by_flow: dict[str, list[dict[str, Any]]] = {}
        for run in self._runs():
            runs_by_flow.setdefault(str(run.get("流程编号", "")), []).append(run)
        rows: list[dict[str, Any]] = []
        for entry in store.rows(MODULE):
            flow_no = str(entry.get("流程编号", ""))
            runs = runs_by_flow.get(flow_no, [])
            if not runs:
                rows.append({"流程编号": flow_no, "运行批次": "（未运行）", "批次状态": "未运行",
                             "开始时间": "", "结束时间": "", "动作序号": "", "动作名称": "",
                             "动作状态": "未执行", "超时原因": "",
                             "结果字段": str(entry.get("结果字段", "")), "失败记录": ""})
                continue
            for run in runs:
                failure = failure_by_batch.get(str(run.get("运行批次", "")))
                for s in run.get("steps", []):
                    rows.append({
                        "流程编号": flow_no,
                        "运行批次": run["运行批次"],
                        "批次状态": run["状态"],
                        "开始时间": run["开始时间"],
                        "结束时间": run["结束时间"],
                        "动作序号": s.get("序号", ""),
                        "动作名称": s.get("动作", ""),
                        "动作状态": s.get("状态", ""),
                        "超时原因": s.get("超时原因", ""),
                        "结果字段": run.get("结果字段", ""),
                        "失败记录": failure["记录编号"] if failure and _parse_int(failure.get("失败步骤"), 0) == _parse_int(s.get("序号"), -1) else "",
                    })
        return rows

    # ---------- 登记与状态流转 ----------
    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [f for f in REQUIRED_FIELDS if not str(values.get(f) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(r.get("id", 0)) for r in rows), default=0) + 1}
        # 登记时保存全部配置字段（含结果字段与运行批次），不再只落三个必填项
        entry.update({f: str(values.get(f) or "").strip() for f in ALL_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"自动化流程 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于自动化采集可执行范围"
        target = ACTION_RULES[action]
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"自动化流程已{action}"
