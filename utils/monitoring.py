# utils/monitoring.py
"""
高级监控系统 - 实时性能监控和指标收集

本模块提供全面的系统监控功能：

主要功能：
- 实时指标收集：CPU、内存、磁盘、网络等系统指标
- 应用监控：机器人响应时间、处理量、错误率等
- 自定义指标：业务相关的监控指标
- 历史数据存储：监控数据的持久化存储
- 报警规则引擎：基于阈值的智能报警
- 监控数据聚合：多维度数据统计和分析

技术特性：
- 多线程数据收集，不影响主程序性能
- 内存高效的时序数据存储
- 可配置的监控频率和保留策略
- 支持多种报警通道和策略

作者: AI Assistant
版本: 2.0
最后更新: 2025-09-05
"""

import logging
import time
import threading
import psutil
import sqlite3
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum

from config import ADMIN_IDS
from utils.logging_utils import log_system_event
from utils.cache import cache_manager

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """监控指标类型"""
    COUNTER = "counter"        # 计数器（只增不减）
    GAUGE = "gauge"           # 仪表（可增可减）
    HISTOGRAM = "histogram"   # 直方图
    TIMER = "timer"          # 时间测量

class AlertLevel(Enum):
    """报警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class MetricValue:
    """监控指标值"""
    timestamp: float
    value: float
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class AlertRule:
    """报警规则"""
    metric_name: str
    condition: str           # >, <, >=, <=, ==, !=
    threshold: float
    level: AlertLevel
    cooldown: int = 300     # 冷却时间（秒）
    message: str = ""
    enabled: bool = True

@dataclass
class AlertEvent:
    """报警事件"""
    rule: AlertRule
    metric_value: MetricValue
    triggered_at: float
    resolved_at: Optional[float] = None
    
    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None
    
    @property
    def duration(self) -> float:
        end_time = self.resolved_at or time.time()
        return end_time - self.triggered_at

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, max_points: int = 1000):
        self.max_points = max_points
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points))
        self.counters: Dict[str, float] = defaultdict(float)
        self.lock = threading.RLock()
    
    def record_counter(self, name: str, value: float = 1, tags: Optional[Dict[str, str]] = None):
        """记录计数器指标"""
        with self.lock:
            self.counters[name] += value
            self._store_metric(name, self.counters[name], tags or {})

    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录仪表指标"""
        with self.lock:
            self._store_metric(name, value, tags or {})

    def record_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """记录时间指标"""
        with self.lock:
            self._store_metric(f"{name}_duration", duration, tags or {})
    
    def _store_metric(self, name: str, value: float, tags: Dict[str, str]):
        """存储指标数据"""
        metric_value = MetricValue(
            timestamp=time.time(),
            value=value,
            tags=tags
        )
        self.metrics[name].append(metric_value)
    
    def get_metric_values(self, name: str, since: Optional[float] = None) -> List[MetricValue]:
        """获取指标值"""
        with self.lock:
            values = list(self.metrics.get(name, []))
            if since:
                values = [v for v in values if v.timestamp >= since]
            return values
    
    def get_latest_value(self, name: str) -> Optional[MetricValue]:
        """获取最新指标值"""
        with self.lock:
            values = self.metrics.get(name)
            return values[-1] if values else None
    
    def get_metric_stats(self, name: str, since: Optional[float] = None) -> Dict[str, float]:
        """获取指标统计"""
        values = self.get_metric_values(name, since)
        if not values:
            return {}
        
        numeric_values = [v.value for v in values]
        return {
            'count': len(numeric_values),
            'sum': sum(numeric_values),
            'avg': sum(numeric_values) / len(numeric_values),
            'min': min(numeric_values),
            'max': max(numeric_values),
            'latest': numeric_values[-1]
        }

class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.running = False
        self.monitor_thread = None
        self.interval = 30  # 监控间隔（秒）
    
    def start(self):
        """开始监控"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("系统监控已启动")
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("系统监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                self._collect_system_metrics()
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"系统监控出错: {e}")
                time.sleep(10)  # 出错时等待10秒再重试
    
    def _collect_system_metrics(self):
        """收集系统指标"""
        # CPU 指标
        cpu_percent = psutil.cpu_percent(interval=1)
        self.collector.record_gauge("system.cpu.usage_percent", cpu_percent)
        
        # 内存指标
        memory = psutil.virtual_memory()
        self.collector.record_gauge("system.memory.usage_percent", memory.percent)
        self.collector.record_gauge("system.memory.used_gb", memory.used / (1024**3))
        self.collector.record_gauge("system.memory.available_gb", memory.available / (1024**3))
        
        # 磁盘指标
        disk = psutil.disk_usage('/')
        self.collector.record_gauge("system.disk.usage_percent", (disk.used / disk.total) * 100)
        self.collector.record_gauge("system.disk.free_gb", disk.free / (1024**3))
        
        # 网络指标
        network = psutil.net_io_counters()
        self.collector.record_counter("system.network.bytes_sent", network.bytes_sent)
        self.collector.record_counter("system.network.bytes_recv", network.bytes_recv)
        
        # 进程指标
        try:
            process = psutil.Process()
            self.collector.record_gauge("bot.memory.usage_mb", process.memory_info().rss / (1024**2))
            self.collector.record_gauge("bot.cpu.usage_percent", process.cpu_percent())
            self.collector.record_gauge("bot.threads.count", process.num_threads())
            self.collector.record_gauge("bot.files.open_count", len(process.open_files()))
        except Exception as e:
            logger.warning(f"收集进程指标失败: {e}")

class AlertManager:
    """报警管理器"""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.rules: List[AlertRule] = []
        self.active_alerts: Dict[str, AlertEvent] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.lock = threading.RLock()
        self.last_check_time = {}
        self._setup_default_rules()
    
    def add_rule(self, rule: AlertRule):
        """添加报警规则"""
        with self.lock:
            self.rules.append(rule)
            logger.info(f"添加报警规则: {rule.metric_name} {rule.condition} {rule.threshold}")
    
    def remove_rule(self, metric_name: str):
        """移除报警规则"""
        with self.lock:
            self.rules = [r for r in self.rules if r.metric_name != metric_name]
            logger.info(f"移除报警规则: {metric_name}")
    
    def check_alerts(self) -> List[AlertEvent]:
        """检查报警"""
        triggered_alerts = []
        
        with self.lock:
            for rule in self.rules:
                if not rule.enabled:
                    continue
                
                # 检查冷却时间
                last_check = self.last_check_time.get(rule.metric_name, 0)
                if time.time() - last_check < rule.cooldown:
                    continue
                
                latest_value = self.collector.get_latest_value(rule.metric_name)
                if not latest_value:
                    continue
                
                if self._evaluate_condition(latest_value.value, rule.condition, rule.threshold):
                    alert_key = f"{rule.metric_name}_{rule.threshold}"
                    
                    if alert_key not in self.active_alerts:
                        # 新报警
                        alert_event = AlertEvent(
                            rule=rule,
                            metric_value=latest_value,
                            triggered_at=time.time()
                        )
                        self.active_alerts[alert_key] = alert_event
                        self.alert_history.append(alert_event)
                        triggered_alerts.append(alert_event)
                        
                        self.last_check_time[rule.metric_name] = time.time()
                        logger.warning(f"触发报警: {rule.metric_name} = {latest_value.value} {rule.condition} {rule.threshold}")
                else:
                    # 检查是否需要解除报警
                    alert_key = f"{rule.metric_name}_{rule.threshold}"
                    if alert_key in self.active_alerts:
                        self.active_alerts[alert_key].resolved_at = time.time()
                        del self.active_alerts[alert_key]
                        logger.info(f"解除报警: {rule.metric_name}")
        
        return triggered_alerts
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """评估报警条件"""
        if condition == ">":
            return value > threshold
        elif condition == "<":
            return value < threshold
        elif condition == ">=":
            return value >= threshold
        elif condition == "<=":
            return value <= threshold
        elif condition == "==":
            return abs(value - threshold) < 0.001
        elif condition == "!=":
            return abs(value - threshold) >= 0.001
        return False
    
    def _setup_default_rules(self):
        """设置默认报警规则"""
        default_rules = [
            AlertRule(
                metric_name="system.cpu.usage_percent",
                condition=">",
                threshold=80,
                level=AlertLevel.WARNING,
                message="CPU使用率过高"
            ),
            AlertRule(
                metric_name="system.memory.usage_percent",
                condition=">",
                threshold=85,
                level=AlertLevel.WARNING,
                message="内存使用率过高"
            ),
            AlertRule(
                metric_name="system.disk.usage_percent",
                condition=">",
                threshold=90,
                level=AlertLevel.ERROR,
                message="磁盘空间不足"
            ),
            AlertRule(
                metric_name="bot.memory.usage_mb",
                condition=">",
                threshold=500,
                level=AlertLevel.WARNING,
                message="机器人内存使用过高"
            )
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    def get_active_alerts(self) -> List[AlertEvent]:
        """获取活跃报警"""
        with self.lock:
            return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 50) -> List[AlertEvent]:
        """获取报警历史"""
        with self.lock:
            return list(self.alert_history)[-limit:]

class MonitoringManager:
    """监控管理器 - 统一监控系统管理"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self.collector = MetricsCollector(max_points=2000)
        self.system_monitor = SystemMonitor(self.collector)
        self.alert_manager = AlertManager(self.collector)
        self.notification_callbacks: List[Callable] = []
        self._initialized = True
        
        logger.info("监控管理器初始化完成")
    
    def start_monitoring(self):
        """启动监控"""
        self.system_monitor.start()
        log_system_event("MONITORING_STARTED", "系统监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.system_monitor.stop()
        log_system_event("MONITORING_STOPPED", "系统监控已停止")
    
    def add_notification_callback(self, callback: Callable):
        """添加通知回调"""
        self.notification_callbacks.append(callback)
    
    def check_and_notify_alerts(self):
        """检查并通知报警"""
        triggered_alerts = self.alert_manager.check_alerts()
        
        for alert in triggered_alerts:
            self._send_alert_notification(alert)
    
    def _send_alert_notification(self, alert: AlertEvent):
        """发送报警通知"""
        for callback in self.notification_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"发送报警通知失败: {e}")
    
    def get_monitoring_dashboard_data(self) -> Dict[str, Any]:
        """获取监控仪表板数据"""
        now = time.time()
        last_hour = now - 3600
        
        # 系统指标统计
        system_metrics = {
            'cpu': self.collector.get_metric_stats("system.cpu.usage_percent", last_hour),
            'memory': self.collector.get_metric_stats("system.memory.usage_percent", last_hour),
            'disk': self.collector.get_metric_stats("system.disk.usage_percent", last_hour)
        }
        
        # 机器人指标统计
        bot_metrics = {
            'memory': self.collector.get_metric_stats("bot.memory.usage_mb", last_hour),
            'cpu': self.collector.get_metric_stats("bot.cpu.usage_percent", last_hour),
            'threads': self.collector.get_metric_stats("bot.threads.count", last_hour)
        }
        
        # 活跃报警
        active_alerts = self.alert_manager.get_active_alerts()
        
        # 最近报警历史
        recent_alerts = self.alert_manager.get_alert_history(20)
        
        return {
            'timestamp': now,
            'system_metrics': system_metrics,
            'bot_metrics': bot_metrics,
            'active_alerts': len(active_alerts),
            'recent_alerts': len(recent_alerts),
            'alerts_detail': [
                {
                    'metric': alert.rule.metric_name,
                    'level': alert.rule.level.value,
                    'message': alert.rule.message,
                    'value': alert.metric_value.value,
                    'threshold': alert.rule.threshold,
                    'duration': alert.duration
                }
                for alert in active_alerts
            ]
        }

# 全局监控管理器实例
monitoring_manager = MonitoringManager()

# 便捷装饰器
def monitor_execution_time(metric_name: str, tags: Optional[Dict[str, str]] = None):
    """监控函数执行时间的装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                monitoring_manager.collector.record_timer(metric_name, execution_time, tags)
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                error_tags = (tags or {}).copy()
                error_tags['error'] = type(e).__name__
                monitoring_manager.collector.record_timer(f"{metric_name}_error", execution_time, error_tags)
                monitoring_manager.collector.record_counter(f"{metric_name}_error_count", 1, error_tags)
                raise
        return wrapper
    return decorator

def count_calls(metric_name: str, tags: Optional[Dict[str, str]] = None):
    """计数函数调用次数的装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitoring_manager.collector.record_counter(metric_name, 1, tags)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# 便捷函数
def record_metric(name: str, value: float, metric_type: MetricType = MetricType.GAUGE, tags: Optional[Dict[str, str]] = None):
    """记录指标的便捷函数"""
    if metric_type == MetricType.COUNTER:
        monitoring_manager.collector.record_counter(name, value, tags)
    else:
        monitoring_manager.collector.record_gauge(name, value, tags)

def get_current_metrics() -> Dict[str, Any]:
    """获取当前监控指标"""
    return monitoring_manager.get_monitoring_dashboard_data()

def start_monitoring():
    """启动系统监控"""
    monitoring_manager.start_monitoring()

def stop_monitoring():
    """停止系统监控"""
    monitoring_manager.stop_monitoring()

# 添加定期监控检查线程
class MonitoringThread(threading.Thread):
    """定期监控检查线程"""
    def __init__(self, interval=60):
        super().__init__(daemon=True)
        self.interval = interval
        self.running = False
    
    def run(self):
        self.running = True
        while self.running:
            try:
                time.sleep(self.interval)
                monitoring_manager.check_and_notify_alerts()
            except Exception as e:
                logger.error(f"监控线程出错: {e}")
    
    def stop(self):
        self.running = False

# 启动监控线程
monitoring_thread = MonitoringThread()
monitoring_thread.start()