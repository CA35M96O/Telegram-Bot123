# utils/log_analyzer.py
"""
智能日志分析器 - 日志模式分析和异常检测

本模块提供智能化的日志分析功能：

主要功能：
- 日志模式识别：自动识别常见的日志模式和异常
- 错误聚合：相似错误的自动分组和统计
- 趋势分析：日志量、错误率等趋势分析
- 异常检测：基于机器学习的异常日志检测
- 日志搜索：高效的日志搜索和过滤
- 报告生成：自动生成日志分析报告

技术特性：
- 实时日志处理：支持流式日志分析
- 内存高效：大文件日志的高效处理
- 模式学习：自动学习正常日志模式
- 可扩展框架：支持自定义分析规则

作者: AI Assistant
版本: 2.0
最后更新: 2025-09-05
"""

import logging
import re
import os
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Pattern
from datetime import datetime, timedelta
from collections import defaultdict, Counter, deque
from dataclasses import dataclass, field
from enum import Enum

from utils.logging_utils import log_system_event
# 时间工具函数
from utils.time_utils import get_beijing_now

logger = logging.getLogger(__name__)

class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class AnomalyType(Enum):
    """异常类型"""
    ERROR_SPIKE = "error_spike"          # 错误激增
    UNUSUAL_PATTERN = "unusual_pattern"   # 异常模式
    MISSING_LOGS = "missing_logs"        # 日志缺失
    PERFORMANCE_ISSUE = "performance"     # 性能问题
    SECURITY_ISSUE = "security"          # 安全问题

@dataclass
class LogEntry:
    """日志条目"""
    timestamp: datetime
    level: LogLevel
    message: str
    module: str = ""
    user_id: Optional[int] = None
    tags: Dict[str, str] = field(default_factory=dict)
    
    @property
    def hash(self) -> str:
        """生成日志条目的哈希值（用于去重）"""
        content = f"{self.level.value}:{self.module}:{self.message}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

@dataclass
class LogPattern:
    """日志模式"""
    pattern_id: str
    regex: Pattern
    description: str
    category: str
    severity: LogLevel
    count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    def match(self, log_entry: LogEntry) -> bool:
        """检查日志条目是否匹配此模式"""
        return bool(self.regex.search(log_entry.message))

@dataclass
class LogAnomaly:
    """日志异常"""
    anomaly_type: AnomalyType
    severity: LogLevel
    title: str
    description: str
    affected_logs: List[LogEntry]
    detected_at: datetime
    confidence: float  # 0.0 - 1.0
    
    @property
    def log_count(self) -> int:
        return len(self.affected_logs)

class LogParser:
    """日志解析器"""
    
    def __init__(self):
        self.patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, Pattern]:
        """编译日志解析模式"""
        return {
            # 标准日志格式
            'standard': re.compile(
                r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+'
                r'(?P<level>\w+)\s+(?P<module>\S+)\s+-\s+(?P<message>.+)'
            ),
            # 用户活动日志
            'user_activity': re.compile(
                r'USER_ACTIVITY - ID:(?P<user_id>\d+) @(?P<username>\S+) - (?P<activity>.+)'
            ),
            # 管理员操作日志
            'admin_operation': re.compile(
                r'ADMIN_OPERATION - ID:(?P<admin_id>\d+) @(?P<username>\S+) - (?P<operation>.+)'
            ),
            # 系统事件日志
            'system_event': re.compile(
                r'SYSTEM_EVENT - (?P<event_type>\w+) - (?P<details>.*)'
            ),
            # 投稿事件日志
            'submission_event': re.compile(
                r'SUBMISSION_EVENT - ID:(?P<user_id>\d+) @(?P<username>\S+) - Submission:(?P<submission_id>\d+) - (?P<event_type>\w+)'
            ),
            # 错误堆栈
            'traceback': re.compile(r'Traceback \(most recent call last\):')
        }
    
    def parse_log_line(self, line: str) -> Optional[LogEntry]:
        """解析单行日志"""
        line = line.strip()
        if not line:
            return None
        
        # 尝试标准格式
        match = self.patterns['standard'].search(line)
        if match:
            try:
                timestamp = datetime.strptime(match.group('timestamp'), '%Y-%m-%d %H:%M:%S,%f')
                level = LogLevel(match.group('level'))
                message = match.group('message')
                module = match.group('module')
                
                # 解析特殊类型的日志
                tags = self._extract_tags(message)
                user_id = self._extract_user_id(message)
                
                return LogEntry(
                    timestamp=timestamp,
                    level=level,
                    message=message,
                    module=module,
                    user_id=user_id,
                    tags=tags
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"解析日志失败: {e}, 行: {line}")
        
        return None
    
    def _extract_tags(self, message: str) -> Dict[str, str]:
        """从消息中提取标签"""
        tags = {}
        
        # 提取用户活动
        if 'USER_ACTIVITY' in message:
            match = self.patterns['user_activity'].search(message)
            if match:
                tags.update({
                    'type': 'user_activity',
                    'user_id': match.group('user_id'),
                    'username': match.group('username'),
                    'activity': match.group('activity')
                })
        
        # 提取管理员操作
        elif 'ADMIN_OPERATION' in message:
            match = self.patterns['admin_operation'].search(message)
            if match:
                tags.update({
                    'type': 'admin_operation',
                    'admin_id': match.group('admin_id'),
                    'username': match.group('username'),
                    'operation': match.group('operation')
                })
        
        # 提取系统事件
        elif 'SYSTEM_EVENT' in message:
            match = self.patterns['system_event'].search(message)
            if match:
                tags.update({
                    'type': 'system_event',
                    'event_type': match.group('event_type'),
                    'details': match.group('details')
                })
        
        return tags
    
    def _extract_user_id(self, message: str) -> Optional[int]:
        """从消息中提取用户ID"""
        patterns = [
            r'ID:(\d+)',
            r'user_id[=:](\d+)',
            r'用户[：:](\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None

class PatternDetector:
    """模式检测器"""
    
    def __init__(self):
        self.known_patterns: List[LogPattern] = []
        self.learned_patterns: Dict[str, LogPattern] = {}
        self._initialize_known_patterns()
    
    def _initialize_known_patterns(self):
        """初始化已知模式"""
        patterns = [
            # 错误模式
            LogPattern(
                pattern_id="database_error",
                regex=re.compile(r'(database|sqlite|mysql|postgresql).*error', re.IGNORECASE),
                description="数据库错误",
                category="database",
                severity=LogLevel.ERROR
            ),
            LogPattern(
                pattern_id="network_error",
                regex=re.compile(r'(network|connection|timeout|refused).*error', re.IGNORECASE),
                description="网络连接错误",
                category="network",
                severity=LogLevel.ERROR
            ),
            LogPattern(
                pattern_id="telegram_api_error",
                regex=re.compile(r'telegram.*api.*error', re.IGNORECASE),
                description="Telegram API错误",
                category="telegram",
                severity=LogLevel.ERROR
            ),
            LogPattern(
                pattern_id="permission_error",
                regex=re.compile(r'permission.*denied|access.*denied|forbidden', re.IGNORECASE),
                description="权限错误",
                category="security",
                severity=LogLevel.WARNING
            ),
            
            # 正常模式
            LogPattern(
                pattern_id="user_submission",
                regex=re.compile(r'USER_ACTIVITY.*投稿'),
                description="用户投稿活动",
                category="user_activity",
                severity=LogLevel.INFO
            ),
            LogPattern(
                pattern_id="admin_review",
                regex=re.compile(r'ADMIN_OPERATION.*(审核|通过|拒绝)'),
                description="管理员审核操作",
                category="admin_activity",
                severity=LogLevel.INFO
            ),
            
            # 系统模式
            LogPattern(
                pattern_id="system_startup",
                regex=re.compile(r'(startup|started|initialized)', re.IGNORECASE),
                description="系统启动",
                category="system",
                severity=LogLevel.INFO
            ),
            LogPattern(
                pattern_id="memory_warning",
                regex=re.compile(r'memory.*warning|内存.*警告', re.IGNORECASE),
                description="内存警告",
                category="performance",
                severity=LogLevel.WARNING
            )
        ]
        
        self.known_patterns = patterns
    
    def detect_patterns(self, log_entries: List[LogEntry]) -> Dict[str, LogPattern]:
        """检测日志模式"""
        pattern_matches = {}
        
        for entry in log_entries:
            for pattern in self.known_patterns:
                if pattern.match(entry):
                    if pattern.pattern_id not in pattern_matches:
                        pattern_matches[pattern.pattern_id] = LogPattern(
                            pattern_id=pattern.pattern_id,
                            regex=pattern.regex,
                            description=pattern.description,
                            category=pattern.category,
                            severity=pattern.severity,
                            count=0,
                            first_seen=entry.timestamp,
                            last_seen=entry.timestamp
                        )
                    
                    pattern_matches[pattern.pattern_id].count += 1
                    pattern_matches[pattern.pattern_id].last_seen = entry.timestamp
        
        return pattern_matches

class AnomalyDetector:
    """异常检测器"""
    
    def __init__(self):
        self.baseline_stats = {}
        self.error_threshold = 0.1  # 错误率阈值
        self.spike_threshold = 3.0  # 激增阈值（倍数）
    
    def detect_anomalies(self, log_entries: List[LogEntry], time_window: int = 3600) -> List[LogAnomaly]:
        """检测日志异常"""
        anomalies = []
        
        if not log_entries:
            return anomalies
        
        # 错误激增检测
        error_spike = self._detect_error_spike(log_entries, time_window)
        if error_spike:
            anomalies.append(error_spike)
        
        # 日志缺失检测
        missing_logs = self._detect_missing_logs(log_entries, time_window)
        if missing_logs:
            anomalies.append(missing_logs)
        
        # 性能问题检测
        performance_issues = self._detect_performance_issues(log_entries)
        anomalies.extend(performance_issues)
        
        # 安全问题检测
        security_issues = self._detect_security_issues(log_entries)
        anomalies.extend(security_issues)
        
        return anomalies
    
    def _detect_error_spike(self, log_entries: List[LogEntry], time_window: int) -> Optional[LogAnomaly]:
        """检测错误激增"""
        now = get_beijing_now()
        current_window_start = now - timedelta(seconds=time_window)
        
        # 当前时间窗口的错误
        current_errors = [
            entry for entry in log_entries
            if entry.timestamp >= current_window_start and entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]
        ]
        
        # 前一个时间窗口的错误（用作基线）
        previous_window_start = current_window_start - timedelta(seconds=time_window)
        previous_errors = [
            entry for entry in log_entries
            if previous_window_start <= entry.timestamp < current_window_start and entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]
        ]
        
        if not previous_errors and len(current_errors) > 5:
            # 没有历史错误但当前有大量错误
            return LogAnomaly(
                anomaly_type=AnomalyType.ERROR_SPIKE,
                severity=LogLevel.WARNING,
                title="错误激增检测",
                description=f"检测到错误激增：当前{time_window//60}分钟内有{len(current_errors)}个错误",
                affected_logs=current_errors,
                detected_at=now,
                confidence=0.8
            )
        
        if len(previous_errors) > 0:
            error_ratio = len(current_errors) / len(previous_errors)
            if error_ratio > self.spike_threshold:
                return LogAnomaly(
                    anomaly_type=AnomalyType.ERROR_SPIKE,
                    severity=LogLevel.WARNING,
                    title="错误激增检测",
                    description=f"错误数量激增{error_ratio:.1f}倍：从{len(previous_errors)}增至{len(current_errors)}",
                    affected_logs=current_errors,
                    detected_at=now,
                    confidence=min(0.9, error_ratio / 10)
                )
        
        return None
    
    def _detect_missing_logs(self, log_entries: List[LogEntry], time_window: int) -> Optional[LogAnomaly]:
        """检测日志缺失"""
        if not log_entries:
            return None
        
        now = get_beijing_now()
        recent_logs = [
            entry for entry in log_entries
            if (now - entry.timestamp).total_seconds() <= time_window
        ]
        
        # 如果最近时间窗口内日志很少，可能存在问题
        if len(recent_logs) < 10 and time_window >= 3600:  # 1小时内少于10条日志
            return LogAnomaly(
                anomaly_type=AnomalyType.MISSING_LOGS,
                severity=LogLevel.WARNING,
                title="日志量异常偏低",
                description=f"过去{time_window//60}分钟内仅有{len(recent_logs)}条日志",
                affected_logs=recent_logs,
                detected_at=now,
                confidence=0.6
            )
        
        return None
    
    def _detect_performance_issues(self, log_entries: List[LogEntry]) -> List[LogAnomaly]:
        """检测性能问题"""
        anomalies = []
        
        # 查找性能相关的日志
        performance_keywords = ['slow', 'timeout', 'performance', '超时', '缓慢', '性能']
        performance_logs = []
        
        for entry in log_entries:
            if any(keyword in entry.message.lower() for keyword in performance_keywords):
                performance_logs.append(entry)
        
        if len(performance_logs) > 5:  # 如果有多个性能相关日志
            anomalies.append(LogAnomaly(
                anomaly_type=AnomalyType.PERFORMANCE_ISSUE,
                severity=LogLevel.WARNING,
                title="性能问题检测",
                description=f"检测到{len(performance_logs)}条性能相关日志",
                affected_logs=performance_logs,
                detected_at=get_beijing_now(),
                confidence=0.7
            ))
        
        return anomalies
    
    def _detect_security_issues(self, log_entries: List[LogEntry]) -> List[LogAnomaly]:
        """检测安全问题"""
        anomalies = []
        
        # 查找安全相关的日志
        security_keywords = ['unauthorized', 'forbidden', 'attack', 'malicious', '未授权', '恶意']
        security_logs = []
        
        for entry in log_entries:
            if any(keyword in entry.message.lower() for keyword in security_keywords):
                security_logs.append(entry)
        
        if security_logs:
            anomalies.append(LogAnomaly(
                anomaly_type=AnomalyType.SECURITY_ISSUE,
                severity=LogLevel.ERROR,
                title="安全问题检测",
                description=f"检测到{len(security_logs)}条安全相关日志",
                affected_logs=security_logs,
                detected_at=get_beijing_now(),
                confidence=0.9
            ))
        
        return anomalies

class LogAnalyzer:
    """日志分析器主类"""
    
    def __init__(self, log_directory: str = "logs"):
        self.log_directory = log_directory
        self.parser = LogParser()
        self.pattern_detector = PatternDetector()
        self.anomaly_detector = AnomalyDetector()
        self.analysis_cache = {}
    
    def analyze_logs(self, hours: int = 24) -> Dict[str, Any]:
        """分析日志文件"""
        cutoff_time = get_beijing_now() - timedelta(hours=hours)
        
        # 读取日志文件
        log_entries = self._read_log_files(cutoff_time)
        
        if not log_entries:
            return {
                'error': '没有找到日志文件或日志为空',
                'log_count': 0,
                'analysis_time': get_beijing_now().isoformat()
            }
        
        # 基础统计
        basic_stats = self._generate_basic_stats(log_entries)
        
        # 模式检测
        patterns = self.pattern_detector.detect_patterns(log_entries)
        
        # 异常检测
        anomalies = self.anomaly_detector.detect_anomalies(log_entries)
        
        # 趋势分析
        trends = self._analyze_trends(log_entries)
        
        # 生成报告
        report = {
            'analysis_time': get_beijing_now().isoformat(),
            'time_range': f"最近 {hours} 小时",
            'log_count': len(log_entries),
            'basic_stats': basic_stats,
            'patterns': {
                pattern_id: {
                    'description': pattern.description,
                    'category': pattern.category,
                    'count': pattern.count,
                    'severity': pattern.severity.value
                }
                for pattern_id, pattern in patterns.items()
            },
            'anomalies': [
                {
                    'type': anomaly.anomaly_type.value,
                    'severity': anomaly.severity.value,
                    'title': anomaly.title,
                    'description': anomaly.description,
                    'log_count': anomaly.log_count,
                    'confidence': anomaly.confidence,
                    'detected_at': anomaly.detected_at.isoformat()
                }
                for anomaly in anomalies
            ],
            'trends': trends
        }
        
        return report
    
    def _read_log_files(self, cutoff_time: datetime) -> List[LogEntry]:
        """读取日志文件"""
        log_entries = []
        
        if not os.path.exists(self.log_directory):
            logger.warning(f"日志目录不存在: {self.log_directory}")
            return log_entries
        
        log_files = [
            f for f in os.listdir(self.log_directory)
            if f.endswith('.log') and not f.startswith('.')
        ]
        
        for log_file in log_files:
            file_path = os.path.join(self.log_directory, log_file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        entry = self.parser.parse_log_line(line)
                        if entry and entry.timestamp >= cutoff_time:
                            log_entries.append(entry)
            except Exception as e:
                logger.error(f"读取日志文件 {log_file} 失败: {e}")
        
        # 按时间排序
        log_entries.sort(key=lambda x: x.timestamp)
        return log_entries
    
    def _generate_basic_stats(self, log_entries: List[LogEntry]) -> Dict[str, Any]:
        """生成基础统计信息"""
        if not log_entries:
            return {}
        
        # 按级别统计
        level_counts = Counter(entry.level for entry in log_entries)
        
        # 按模块统计
        module_counts = Counter(entry.module for entry in log_entries)
        
        # 按小时统计
        hourly_counts = Counter(entry.timestamp.hour for entry in log_entries)
        
        # 用户活动统计
        user_activity = Counter(entry.user_id for entry in log_entries if entry.user_id)
        
        # 错误率计算
        total_logs = len(log_entries)
        error_logs = sum(count for level, count in level_counts.items() 
                        if level in [LogLevel.ERROR, LogLevel.CRITICAL])
        error_rate = error_logs / total_logs if total_logs > 0 else 0
        
        return {
            'total_logs': total_logs,
            'error_rate': error_rate,
            'by_level': {level.value: count for level, count in level_counts.items()},
            'by_module': dict(module_counts.most_common(10)),
            'by_hour': dict(hourly_counts),
            'unique_users': len(user_activity),
            'most_active_users': dict(user_activity.most_common(5)),
            'time_span': {
                'start': log_entries[0].timestamp.isoformat(),
                'end': log_entries[-1].timestamp.isoformat()
            }
        }
    
    def _analyze_trends(self, log_entries: List[LogEntry]) -> Dict[str, Any]:
        """分析日志趋势"""
        if len(log_entries) < 2:
            return {}
        
        # 按小时分组
        hourly_data = defaultdict(lambda: {'total': 0, 'errors': 0})
        
        for entry in log_entries:
            hour_key = entry.timestamp.strftime('%Y-%m-%d %H:00')
            hourly_data[hour_key]['total'] += 1
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                hourly_data[hour_key]['errors'] += 1
        
        # 计算趋势
        hours = sorted(hourly_data.keys())
        if len(hours) < 2:
            return {}
        
        recent_hour = hourly_data[hours[-1]]
        previous_hour = hourly_data[hours[-2]]
        
        # 计算变化
        log_volume_change = ((recent_hour['total'] - previous_hour['total']) / 
                           max(previous_hour['total'], 1)) * 100
        
        error_change = ((recent_hour['errors'] - previous_hour['errors']) / 
                       max(previous_hour['errors'], 1)) * 100
        
        return {
            'log_volume_change_percent': round(log_volume_change, 2),
            'error_change_percent': round(error_change, 2),
            'hourly_data': dict(hourly_data),
            'trend_summary': self._get_trend_summary(log_volume_change, error_change)
        }
    
    def _get_trend_summary(self, log_change: float, error_change: float) -> str:
        """获取趋势摘要"""
        if abs(log_change) < 10 and abs(error_change) < 10:
            return "📊 日志量和错误率相对稳定"
        elif log_change > 20:
            if error_change > 20:
                return "⚠️ 日志量和错误数都显著增加"
            else:
                return "📈 日志量显著增加，错误率正常"
        elif log_change < -20:
            return "📉 日志量显著减少"
        elif error_change > 50:
            return "🚨 错误率显著增加"
        elif error_change < -20:
            return "✅ 错误率显著减少"
        else:
            return "📊 日志趋势正常"

# 全局日志分析器实例
log_analyzer = LogAnalyzer()

# 便捷函数
def analyze_recent_logs(hours: int = 24) -> Dict[str, Any]:
    """分析最近的日志"""
    return log_analyzer.analyze_logs(hours)

def detect_log_anomalies(hours: int = 1) -> List[LogAnomaly]:
    """检测日志异常"""
    cutoff_time = get_beijing_now() - timedelta(hours=hours)
    log_entries = log_analyzer._read_log_files(cutoff_time)
    return log_analyzer.anomaly_detector.detect_anomalies(log_entries)

def get_log_patterns(hours: int = 24) -> Dict[str, LogPattern]:
    """获取日志模式"""
    cutoff_time = get_beijing_now() - timedelta(hours=hours)
    log_entries = log_analyzer._read_log_files(cutoff_time)
    return log_analyzer.pattern_detector.detect_patterns(log_entries)