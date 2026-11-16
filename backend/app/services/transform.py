"""转换编排 DAG 图服务：生成节点、边示例结构与流转规则。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "transform"
REQUIRED_FIELDS = ["节点编号", "输入数据集", "输出数据集"]
STATUS_ORDER = ["草稿", "待校验", "已启用", "已停用"]
ACTION_RULES = {"提交校验": "待校验", "启用配置": "已启用", "停用配置": "已停用"}
NEGATIVE_ACTIONS = ["停用配置"]


def csv_cell(value: Any) -> str:
    text = str(value) if value is not None else ""
    if text and text[0] in "=+-@":
        text = "'" + text
    return '"' + text.replace('"', '""') + '"'


class TransformService:
    def get_graph(self) -> dict[str, Any]:
        rows = store.rows(MODULE)
        nodes: list[dict] = []
        edges: list[dict] = []
        for i, row in enumerate(rows):
            nodes.append({"id": int(row.get("id", i+1)), "name": str(row.get(list(row.keys())[1] if len(row)>1 else "name", "")), "status": str(row.get("status", STATUS_ORDER[0])),
                          **{k: row[k] for k in row if k not in ("id","status","pending","abnormal")}})
        for i in range(len(nodes)-1):
            edges.append({"from": nodes[i]["id"], "to": nodes[i+1]["id"], "label": "依赖"})
        return {"nodes": nodes, "edges": edges}

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [f for f in REQUIRED_FIELDS if not str(values.get(f) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(r.get("id",0)) for r in rows), default=0) + 1}
        entry.update({f: values.get(f) for f in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"转换节点 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于转换编排可执行范围"
        target = ACTION_RULES[action]
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"转换节点已{action}"

    def raw_data(self) -> tuple[list[dict], list[dict]]:
        g = self.get_graph()
        return g["nodes"], g["edges"]

    def get_failure_runs(self) -> dict[str, Any]:
        """同步获取自动化采集的失败运行记录：与运行页面读取同一运行批次。"""
        flows = {str(row.get("流程编号", "")): row for row in store.rows("robotflow")}
        runs = {str(run.get("运行批次", "")): run for run in store.aux_rows("robotflow_runs")}
        items: list[dict[str, Any]] = []
        for record in store.aux_rows("robotflow_failures"):
            flow = flows.get(str(record.get("流程编号", "")), {})
            run = runs.get(str(record.get("运行批次", "")), {})
            items.append({
                **record,
                "批次状态": str(run.get("状态", "")),
                "最新批次": str(flow.get("运行批次", "") or record.get("运行批次", "")),
            })
        return {"items": items, "total": len(items)}
