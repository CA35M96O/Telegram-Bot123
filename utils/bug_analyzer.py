# utils/bug_analyzer.py
"""
Bug分析器模块 - 分析各类bug日志并提供统计和报告功能

本模块提供智能化的bug分析功能：

主要功能：
- Bug统计：按类型统计bug数量和频率
- Bug趋势分析：分析bug随时间的变化趋势
- Bug严重性评估：评估bug的影响程度
- Bug模式识别：识别常见的bug模式
- Bug报告生成：生成详细的bug分析报告
- Bug预警：当bug数量超过阈值时发出预警

技术特性：
- 多文件分析：同时分析多个bug日志文件
- 实时监控：支持实时bug监控
- 智能分类：自动分类和标记bug
- 可视化支持：支持生成图表和可视化报告

作者: AI Assistant
版本: 2.1
最后更新: 2025-09-15
"""

import os
import re
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from enum import Enum
import logging

from utils.logging_utils import log_system_event
from utils.time_utils import get_beijing_now

class BugSeverity(Enum):
    """Bug严重性级别"""
    LOW = "low"          # 低级bug，不影响主要功能
    MEDIUM = "medium"    # 中级bug，影响部分功能
    HIGH = "high"        # 高级bug，影响核心功能
    CRITICAL = "critical"  # 严重bug，导致系统崩溃

class BugCategory(Enum):
    """Bug分类"""
    DATABASE = "database"      # 数据库相关bug
    NETWORK = "network"        # 网络相关bug
    MEDIA = "media"           # 媒体处理bug
    PERMISSION = "permission"  # 权限相关bug
    RESOURCE = "resource"     # 系统资源bug
    EXTERNAL = "external"     # 第三方服务bug
    INPUT = "input"          # 用户输入bug
    SCHEDULER = "scheduler"   # 定时任务bug
    UNKNOWN = "unknown"       # 未知类型bug

@dataclass
class BugEntry:
    """Bug条目"""
    timestamp: datetime
    category: BugCategory
    severity: BugSeverity
    error_type: str
    error_message: str
    context: Dict[str, Any] = field(default_factory=dict)
    traceback: str = ""
    
    @property
    def time_key(self) -> str:
        """获取时间键，用于按时间分组"""
        return self.timestamp.strftime("%Y-%m-%d %H:00")
    
    @property
    def day_key(self) -> str:
        """获取日期键，用于按日期分组"""
        return self.timestamp.strftime("%Y-%m-%d")

@dataclass
class BugPattern:
    """Bug模式"""
    pattern_id: str
    regex: str
    description: str
    category: BugCategory
    severity: BugSeverity
    count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

@dataclass
class BugStats:
    """Bug统计信息"""
    category: BugCategory
    total_count: int = 0
    daily_count: Dict[str, int] = field(default_factory=dict)
    hourly_count: Dict[str, int] = field(default_factory=dict)
    severity_distribution: Dict[BugSeverity, int] = field(default_factory=dict)
    top_errors: List[Tuple[str, int]] = field(default_factory=list)
    
    def add_bug(self, bug: BugEntry):
        """添加一个bug到统计中"""
        self.total_count += 1
        
        # 按日期统计
        day_key = bug.day_key
        self.daily_count[day_key] = self.daily_count.get(day_key, 0) + 1
        
        # 按小时统计
        hour_key = bug.time_key
        self.hourly_count[hour_key] = self.hourly_count.get(hour_key, 0) + 1
        
        # 按严重性统计
        self.severity_distribution[bug.severity] = self.severity_distribution.get(bug.severity, 0) + 1
        
        # 统计错误类型
        error_found = False
        for i, (error_type, count) in enumerate(self.top_errors):
            if error_type == bug.error_type:
                self.top_errors[i] = (error_type, count + 1)
                error_found = True
                break
        
        if not error_found:
            self.top_errors.append((bug.error_type, 1))
        
        # 按错误数量排序
        self.top_errors.sort(key=lambda x: x[1], reverse=True)
        # 只保留前10个
        self.top_errors = self.top_errors[:10]

class BugAnalyzer:
    """Bug分析器"""
    
    def __init__(self, logs_dir: str = "logs"):
        """
        初始化Bug分析器
        
        Args:
            logs_dir: 日志目录路径
        """
        self.logs_dir = logs_dir
        self.bug_patterns = self._init_bug_patterns()
        self.bug_stats = {category: BugStats(category=category) for category in BugCategory}
        self.all_bugs: List[BugEntry] = []
        self.log_files = {
            BugCategory.DATABASE: "bugs_database.log",
            BugCategory.NETWORK: "bugs_network.log",
            BugCategory.MEDIA: "bugs_media.log",
            BugCategory.PERMISSION: "bugs_permission.log",
            BugCategory.RESOURCE: "bugs_resource.log",
            BugCategory.EXTERNAL: "bugs_external.log",
            BugCategory.INPUT: "bugs_input.log",
            BugCategory.SCHEDULER: "bugs_scheduler.log",
            BugCategory.UNKNOWN: "bugs_unknown.log"
        }
        self.logger = logging.getLogger(__name__)
    
    def _init_bug_patterns(self) -> List[BugPattern]:
        """初始化bug模式"""
        return [
            # 数据库相关模式
            BugPattern(
                pattern_id="db_connection_timeout",
                regex=r"connection timeout|connection timed out",
                description="数据库连接超时",
                category=BugCategory.DATABASE,
                severity=BugSeverity.HIGH
            ),
            BugPattern(
                pattern_id="db_operational_error",
                regex=r"OperationalError|operational error",
                description="数据库操作错误",
                category=BugCategory.DATABASE,
                severity=BugSeverity.HIGH
            ),
            BugPattern(
                pattern_id="db_integrity_error",
                regex=r"IntegrityError|integrity error",
                description="数据库完整性错误",
                category=BugCategory.DATABASE,
                severity=BugSeverity.MEDIUM
            ),
            
            # 网络相关模式
            BugPattern(
                pattern_id="network_timeout",
                regex=r"timeout|timed out",
                description="网络超时",
                category=BugCategory.NETWORK,
                severity=BugSeverity.MEDIUM
            ),
            BugPattern(
                pattern_id="network_connection_error",
                regex=r"connection error|connection failed",
                description="网络连接错误",
                category=BugCategory.NETWORK,
                severity=BugSeverity.HIGH
            ),
            
            # 媒体处理相关模式
            BugPattern(
                pattern_id="media_upload_failed",
                regex=r"upload failed|upload error",
                description="媒体上传失败",
                category=BugCategory.MEDIA,
                severity=BugSeverity.MEDIUM
            ),
            BugPattern(
                pattern_id="media_processing_error",
                regex=r"processing error|processing failed",
                description="媒体处理错误",
                category=BugCategory.MEDIA,
                severity=BugSeverity.MEDIUM
            ),
            
            # 权限相关模式
            BugPattern(
                pattern_id="permission_denied",
                regex=r"permission denied|access denied",
                description="权限拒绝",
                category=BugCategory.PERMISSION,
                severity=BugSeverity.MEDIUM
            ),
            BugPattern(
                pattern_id="unauthorized_access",
                regex=r"unauthorized|forbidden",
                description="未授权访问",
                category=BugCategory.PERMISSION,
                severity=BugSeverity.HIGH
            ),
            
            # 系统资源相关模式
            BugPattern(
                pattern_id="memory_error",
                regex=r"memory error|out of memory",
                description="内存错误",
                category=BugCategory.RESOURCE,
                severity=BugSeverity.CRITICAL
            ),
            BugPattern(
                pattern_id="cpu_error",
                regex=r"cpu error|cpu overload",
                description="CPU错误",
                category=BugCategory.RESOURCE,
                severity=BugSeverity.HIGH
            ),
            
            # 第三方服务相关模式
            BugPattern(
                pattern_id="external_service_error",
                regex=r"external service|service error",
                description="第三方服务错误",
                category=BugCategory.EXTERNAL,
                severity=BugSeverity.MEDIUM
            ),
            
            # 用户输入相关模式
            BugPattern(
                pattern_id="input_validation_error",
                regex=r"validation error|invalid input",
                description="输入验证错误",
                category=BugCategory.INPUT,
                severity=BugSeverity.LOW
            ),
            
            # 定时任务相关模式
            BugPattern(
                pattern_id="scheduler_error",
                regex=r"scheduler error|job error",
                description="定时任务错误",
                category=BugCategory.SCHEDULER,
                severity=BugSeverity.HIGH
            )
        ]
    
    def analyze_recent_bugs(self, days=7):
        """分析最近的Bug"""
        try:
            # 计算截止时间
            cutoff_time = get_beijing_now() - timedelta(days=days)
            
            analysis = {
                'analysis_time': get_beijing_now().strftime("%Y-%m-%d %H:%M:%S"),
                'analysis_period_days': days,
                'cutoff_time': cutoff_time.strftime("%Y-%m-%d %H:%M:%S"),
                'total_bugs': 0,
                'bugs_by_category': {},
                'bugs_by_severity': {},
                'daily_trend': [],
                'category_details': {},
                'recommendations': []
            }
            
            # 分析各类日志文件
            for category, log_file in self.log_files.items():
                bugs = self._analyze_log_file(log_file, cutoff_time)
                count = len(bugs)
                
                if count > 0:
                    analysis['total_bugs'] += count
                    analysis['bugs_by_category'][category] = count
                    analysis['category_details'][category] = {
                        'bugs': bugs,
                        'top_errors': self._get_top_errors(bugs),
                        'frequency_analysis': self._analyze_frequency(bugs)
                    }
            
            # 分析严重性分布
            analysis['bugs_by_severity'] = self._analyze_severity_distribution(analysis)
            
            # 分析每日趋势
            analysis['daily_trend'] = self._analyze_daily_trend(analysis, days)
            
            # 生成建议
            analysis['recommendations'] = self._generate_recommendations(analysis)
            
            return analysis
        except Exception as e:
            self.logger.error(f"分析最近Bug失败: {e}")
            return {}
    
    def _analyze_log_file(self, log_file: str, cutoff_time: datetime) -> List[BugEntry]:
        """解析单个bug日志文件"""
        bugs = []
        log_path = os.path.join(self.logs_dir, log_file)
        if not os.path.exists(log_path):
            return bugs
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    bug_entry = self._parse_log_line(line)
                    if bug_entry and bug_entry.timestamp >= cutoff_time:
                        bugs.append(bug_entry)
        except Exception as e:
            self.logger.error(f"解析日志文件失败: {log_path}, 错误: {e}")
        
        return bugs
    
    def _parse_log_line(self, line: str) -> Optional[BugEntry]:
        """
        解析单行日志
        
        Args:
            line: 日志行
            
        Returns:
            BugEntry对象或None
        """
        line = line.strip()
        if not line:
            return None
        
        # 解析时间戳
        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if not timestamp_match:
            return None
        
        try:
            timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
        
        # 解析错误类型和消息
        error_type_match = re.search(r'([A-Z]+_ERROR): (.+)', line)
        if not error_type_match:
            return None
        
        error_type = error_type_match.group(1)
        error_message = error_type_match.group(2)
        
        # 确定严重性
        severity = self._determine_severity(error_type, error_message)
        
        # 解析上下文信息
        context = self._extract_context(line)
        
        # 解析堆栈信息
        traceback = ""
        if "Traceback" in line:
            # 这里简化处理，实际应用中可能需要更复杂的堆栈解析
            traceback = "Traceback available"
        
        return BugEntry(
            timestamp=timestamp,
            category=BugCategory.UNKNOWN,
            severity=severity,
            error_type=error_type,
            error_message=error_message,
            context=context,
            traceback=traceback
        )
    
    def _determine_severity(self, error_type: str, error_message: str) -> BugSeverity:
        """
        确定bug的严重性
        
        Args:
            error_type: 错误类型
            error_message: 错误消息
            
        Returns:
            BugSeverity枚举值
        """
        error_message_lower = error_message.lower()
        
        # 检查是否匹配已知的bug模式
        for pattern in self.bug_patterns:
            if re.search(pattern.regex, error_message_lower, re.IGNORECASE):
                return pattern.severity
        
        # 基于错误类型的默认严重性
        if "critical" in error_type.lower() or "fatal" in error_message_lower:
            return BugSeverity.CRITICAL
        elif "error" in error_type.lower():
            return BugSeverity.HIGH
        elif "warning" in error_type.lower() or "warn" in error_message_lower:
            return BugSeverity.MEDIUM
        else:
            return BugSeverity.LOW
    
    def _extract_context(self, line: str) -> Dict[str, Any]:
        """
        从日志行中提取上下文信息
        
        Args:
            line: 日志行
            
        Returns:
            上下文字典
        """
        context = {}
        
        # 提取用户ID
        user_id_match = re.search(r'user_id[\'"]?\s*[:=]\s*(\d+)', line, re.IGNORECASE)
        if user_id_match:
            context["user_id"] = int(user_id_match.group(1))
        
        # 提取URL
        url_match = re.search(r'url[\'"]?\s*[:=]\s*[\'"]([^\'"]+)[\'"]', line, re.IGNORECASE)
        if url_match:
            context["url"] = url_match.group(1)
        
        # 提取文件ID
        file_id_match = re.search(r'file_id[\'"]?\s*[:=]\s*[\'"]([^\'"]+)[\'"]', line, re.IGNORECASE)
        if file_id_match:
            context["file_id"] = file_id_match.group(1)
        
        return context
    
    def _get_top_errors(self, bugs: List[BugEntry]) -> List[Tuple[str, int]]:
        """获取最常见的错误类型"""
        error_counts = Counter(bug.error_type for bug in bugs)
        return error_counts.most_common(10)
    
    def _analyze_severity_distribution(self, analysis: Dict[str, Any]) -> Dict[str, int]:
        """分析严重性分布"""
        severity_distribution = defaultdict(int)
        for category, details in analysis['category_details'].items():
            for bug in details['bugs']:
                severity_distribution[bug.severity.value] += 1
        return dict(severity_distribution)
    
    def _analyze_frequency(self, bugs: List[BugEntry]) -> Dict[str, int]:
        """分析错误频率"""
        frequency = defaultdict(int)
        for bug in bugs:
            frequency[bug.day_key] += 1
        return dict(frequency)
    
    def _analyze_daily_trend(self, analysis: Dict[str, Any], days: int) -> List[Tuple[str, int]]:
        """分析每日趋势"""
        daily_trend = defaultdict(int)
        for category, details in analysis['category_details'].items():
            for day, count in details['frequency_analysis'].items():
                daily_trend[day] += count
        
        # 排序日期
        sorted_days = sorted(daily_trend.keys())
        return [(day, daily_trend[day]) for day in sorted_days]
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """
        生成改进建议
        
        Returns:
            建议列表
        """
        recommendations = []
        
        # 检查各类bug的数量
        for category, count in analysis['bugs_by_category'].items():
            if count == 0:
                continue
                
            # 根据bug数量和类别生成建议
            if category == BugCategory.DATABASE and count > 10:
                recommendations.append(f"数据库错误较多({count}个)，建议检查数据库连接配置和查询优化")
            
            elif category == BugCategory.NETWORK and count > 15:
                recommendations.append(f"网络错误较多({count}个)，建议检查网络连接和API调用稳定性")
            
            elif category == BugCategory.MEDIA and count > 20:
                recommendations.append(f"媒体处理错误较多({count}个)，建议优化媒体上传和处理逻辑")
            
            elif category == BugCategory.PERMISSION and count > 5:
                recommendations.append(f"权限错误较多({count}个)，建议检查权限验证逻辑")
            
            elif category == BugCategory.RESOURCE and count > 3:
                recommendations.append(f"系统资源错误较多({count}个)，建议增加系统资源或优化资源使用")
            
            elif category == BugCategory.EXTERNAL and count > 8:
                recommendations.append(f"第三方服务错误较多({count}个)，建议检查外部服务状态和调用逻辑")
            
            elif category == BugCategory.INPUT and count > 25:
                recommendations.append(f"用户输入错误较多({count}个)，建议增强输入验证和用户引导")
            
            elif category == BugCategory.SCHEDULER and count > 5:
                recommendations.append(f"定时任务错误较多({count}个)，建议检查定时任务配置和异常处理")
            
            elif category == BugCategory.UNKNOWN and count > 10:
                recommendations.append(f"未知类型错误较多({count}个)，建议增强错误分类和日志记录")
        
        # 如果没有特定建议，提供通用建议
        if not recommendations:
            recommendations.append("系统运行稳定，建议继续保持当前监控和维护策略")
        
        return recommendations
    
    def generate_bug_report_filename(self):
        """生成Bug报告文件名"""
        timestamp = get_beijing_now().strftime("%Y%m%d_%H%M%S")
        return f"bug_analysis_report_{timestamp}.json"
    
    def save_report(self, report: Dict[str, Any], filename: Optional[str] = None):
        """
        保存分析报告到文件
        
        Args:
            report: 分析报告
            filename: 文件名，如果为None则使用默认名称
        """
        if filename is None:
            filename = self.generate_bug_report_filename()
        
        report_path = os.path.join(self.logs_dir, filename)
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            log_system_event("BUG_REPORT_SAVED", f"Bug分析报告已保存: {report_path}")
            return report_path if report_path is not None else ""
        except Exception as e:
            log_system_event("BUG_REPORT_SAVE_ERROR", f"保存Bug分析报告失败: {e}")
            return None

# 创建全局Bug分析器实例
bug_analyzer = BugAnalyzer()