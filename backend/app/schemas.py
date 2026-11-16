"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ActionPayload(BaseModel):
    """状态动作使用独立契约，避免与登记的 values 载荷混用。"""

    action: str
    remark: str | None = None


class RunPayload(BaseModel):
    """自动化采集运行请求：同一运行批次只采纳首个采集请求。

    超时步骤用于模拟某一步动作的等待条件超时；等待条件可在重跑时携带修复后的版本。
    """

    运行批次: str = ""
    超时步骤: int | None = None
    等待条件: str | None = None
    remark: str | None = None



class DatasourceEntry(BaseModel):
    """数据源明细结构。"""

    field_0: str | None = None  # 源端编号
    field_1: str | None = None  # 连接类型
    field_2: str | None = None  # 接入地址
    field_3: str | None = None  # 采样周期
    field_4: str | None = None  # 字符编码
    field_5: str | None = None  # 连接超时
    field_6: str | None = None  # 重试上限
    field_7: str | None = None  # 负责人

class ExtractorEntry(BaseModel):
    """采集游标明细结构。"""

    field_0: str | None = None  # 采集编号
    field_1: str | None = None  # 来源标识
    field_2: str | None = None  # 增量字段
    field_3: str | None = None  # 游标位置
    field_4: str | None = None  # 批次大小
    field_5: str | None = None  # 采集间隔
    field_6: str | None = None  # 起始水位
    field_7: str | None = None  # 截止水位

class CrawlruleEntry(BaseModel):
    """抽取规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 入口地址
    field_2: str | None = None  # 页面选择器
    field_3: str | None = None  # 正文选择器
    field_4: str | None = None  # 分页参数
    field_5: str | None = None  # 字符编码
    field_6: str | None = None  # 抓取间隔
    field_7: str | None = None  # 重试次数

class RobotflowEntry(BaseModel):
    """自动化流程明细结构。"""

    field_0: str | None = None  # 流程编号
    field_1: str | None = None  # 输入来源
    field_2: str | None = None  # 页面定位器
    field_3: str | None = None  # 等待条件
    field_4: str | None = None  # 动作顺序
    field_5: str | None = None  # 结果字段
    field_6: str | None = None  # 超时秒数
    field_7: str | None = None  # 运行批次

class LandingEntry(BaseModel):
    """落地区段明细结构。"""

    field_0: str | None = None  # 区段编号
    field_1: str | None = None  # 来源名称
    field_2: str | None = None  # 落地路径
    field_3: str | None = None  # 文件格式
    field_4: str | None = None  # 批次标识
    field_5: str | None = None  # 接收时间
    field_6: str | None = None  # 原始行数
    field_7: str | None = None  # 校验摘要

class SchemaEntry(BaseModel):
    """字段契约明细结构。"""

    field_0: str | None = None  # 契约编号
    field_1: str | None = None  # 数据集名称
    field_2: str | None = None  # 字段名称
    field_3: str | None = None  # 字段类型
    field_4: str | None = None  # 可空标识
    field_5: str | None = None  # 默认取值
    field_6: str | None = None  # 契约版本
    field_7: str | None = None  # 生效批次

class CleaningEntry(BaseModel):
    """清洗规则明细结构。"""

    field_0: str | None = None  # 清洗编号
    field_1: str | None = None  # 输入数据集
    field_2: str | None = None  # 空值策略
    field_3: str | None = None  # 格式表达式
    field_4: str | None = None  # 异常阈值
    field_5: str | None = None  # 输出字段
    field_6: str | None = None  # 规则版本
    field_7: str | None = None  # 生效日期

class DedupEntry(BaseModel):
    """去重策略明细结构。"""

    field_0: str | None = None  # 策略编号
    field_1: str | None = None  # 输入数据集
    field_2: str | None = None  # 业务键列
    field_3: str | None = None  # 排序字段
    field_4: str | None = None  # 保留顺序
    field_5: str | None = None  # 时间窗口
    field_6: str | None = None  # 重复阈值
    field_7: str | None = None  # 输出数据集

class PartitionEntry(BaseModel):
    """分区方案明细结构。"""

    field_0: str | None = None  # 方案编号
    field_1: str | None = None  # 数据表名
    field_2: str | None = None  # 分区字段
    field_3: str | None = None  # 分区粒度
    field_4: str | None = None  # 保留天数
    field_5: str | None = None  # 冷热阈值
    field_6: str | None = None  # 预建天数
    field_7: str | None = None  # 目录规则

class TransformEntry(BaseModel):
    """转换节点明细结构。"""

    field_0: str | None = None  # 节点编号
    field_1: str | None = None  # 输入数据集
    field_2: str | None = None  # 输出数据集
    field_3: str | None = None  # 转换表达式
    field_4: str | None = None  # 执行顺序
    field_5: str | None = None  # 依赖节点
    field_6: str | None = None  # 失败策略
    field_7: str | None = None  # 调度周期

class DimensionEntry(BaseModel):
    """维度实体明细结构。"""

    field_0: str | None = None  # 维度编号
    field_1: str | None = None  # 维度名称
    field_2: str | None = None  # 自然键列
    field_3: str | None = None  # 代理键列
    field_4: str | None = None  # 历史策略
    field_5: str | None = None  # 生效字段
    field_6: str | None = None  # 失效字段
    field_7: str | None = None  # 刷新周期

class FactsetEntry(BaseModel):
    """事实数据集明细结构。"""

    field_0: str | None = None  # 事实编号
    field_1: str | None = None  # 事实名称
    field_2: str | None = None  # 粒度说明
    field_3: str | None = None  # 关联维度
    field_4: str | None = None  # 度量字段
    field_5: str | None = None  # 时间字段
    field_6: str | None = None  # 主键组合
    field_7: str | None = None  # 刷新水位

class QualityEntry(BaseModel):
    """质量规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 校验数据集
    field_2: str | None = None  # 目标字段
    field_3: str | None = None  # 校验表达式
    field_4: str | None = None  # 阈值下界
    field_5: str | None = None  # 阈值上界
    field_6: str | None = None  # 采样比例
    field_7: str | None = None  # 阻断级别

class LineageEntry(BaseModel):
    """血缘关系明细结构。"""

    field_0: str | None = None  # 关系编号
    field_1: str | None = None  # 上游节点
    field_2: str | None = None  # 下游节点
    field_3: str | None = None  # 来源字段
    field_4: str | None = None  # 目标字段
    field_5: str | None = None  # 转换说明
    field_6: str | None = None  # 采集批次
    field_7: str | None = None  # 关系版本

class BackfillEntry(BaseModel):
    """补数批次明细结构。"""

    field_0: str | None = None  # 批次编号
    field_1: str | None = None  # 目标数据集
    field_2: str | None = None  # 开始日期
    field_3: str | None = None  # 结束日期
    field_4: str | None = None  # 并行数量
    field_5: str | None = None  # 覆盖策略
    field_6: str | None = None  # 完成水位
    field_7: str | None = None  # 失败区间

class MetricEntry(BaseModel):
    """指标定义明细结构。"""

    field_0: str | None = None  # 指标编号
    field_1: str | None = None  # 指标名称
    field_2: str | None = None  # 计算公式
    field_3: str | None = None  # 统计粒度
    field_4: str | None = None  # 时间范围
    field_5: str | None = None  # 筛选条件
    field_6: str | None = None  # 精度位数
    field_7: str | None = None  # 口径版本

class AnalysisEntry(BaseModel):
    """分析方案明细结构。"""

    field_0: str | None = None  # 方案编号
    field_1: str | None = None  # 分析数据集
    field_2: str | None = None  # 样本范围
    field_3: str | None = None  # 分组字段
    field_4: str | None = None  # 目标度量
    field_5: str | None = None  # 基准区间
    field_6: str | None = None  # 比较方法
    field_7: str | None = None  # 显著阈值

class DeliveryEntry(BaseModel):
    """服务版本明细结构。"""

    field_0: str | None = None  # 服务编号
    field_1: str | None = None  # 输出数据集
    field_2: str | None = None  # 查询参数
    field_3: str | None = None  # 响应字段
    field_4: str | None = None  # 缓存秒数
    field_5: str | None = None  # 分页上限
    field_6: str | None = None  # 发布版本
    field_7: str | None = None  # 消费应用
