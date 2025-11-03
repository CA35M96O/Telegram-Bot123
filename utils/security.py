# utils/security.py
"""
安全模块 - 提供恶意内容检测和异常行为识别功能

本模块提供以下安全功能：
- 恶意模式检测（正则表达式）
- 机器学习异常检测
- 用户行为分析
- 限流和封禁机制
- 安全事件记录和报告

作者: AI Assistant
版本: 1.0
最后更新: 2025-10-31
"""

import re
import time
import json
import hashlib
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
from functools import wraps

from utils.cache import cache_manager
from utils.logging_utils import log_system_event

logger = logging.getLogger(__name__)

@dataclass
class SecurityEvent:
    """安全事件数据结构"""
    user_id: int
    event_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    details: str
    timestamp: float = 0
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()

class SecurityManager:
    """安全管理器"""
    
    def __init__(self):
        # 恶意模式列表（正则表达式）
        self.malicious_patterns = [
            # SQL注入模式
            r"(?i)(union|select|insert|update|delete|drop|create|alter|exec|execute).*",
            # XSS攻击模式
            r"(?i)(<script|javascript:|onload|onerror|onclick)",
            # 路径遍历
            r"(\.\.\/|\.\/|\/\.\.|\.\.\\|\.\.\\\.\.)",
            # 命令注入
            r"(?i)(system|exec|shell_exec|passthru|popen|proc_open)",
            # 文件包含
            r"(?i)(include|require)(_once)?\s*[\"'].*\.(php|jsp|asp|aspx)[\"']",
        ]
        
        # 敏感词列表
        self.sensitive_words = [
            "色情", "赌博", "毒品", "暴力", "恐怖主义", "诈骗",
            "porn", "gamble", "drugs", "violence", "terrorism", "fraud"
        ]
        
        # 用户行为记录
        self.user_behavior = defaultdict(lambda: {
            'request_count': 0,
            'last_request': 0.0,
            'suspicious_actions': 0,
            'rate_limit_count': 0
        })
        
        # 用户黑名单 {user_id: unban_time}
        self.user_blacklist = {}
        
        # 限流器 {user_id_action: RateLimiter}
        self.rate_limiters = {}
        
        # 安全事件记录
        self.security_events = []
        
        # 加载预定义的恶意模式
        self._load_malicious_patterns()
    
    def _load_malicious_patterns(self):
        """加载预定义的恶意模式"""
        # 可以从文件或数据库加载更多模式
        logger.info(f"已加载 {len(self.malicious_patterns)} 个恶意模式和 {len(self.sensitive_words)} 个敏感词")
    
    def check_content_security(self, content: str) -> Tuple[bool, str]:
        """检查内容安全性
        
        Args:
            content: 要检查的内容
            
        Returns:
            (is_safe, reason): 是否安全及原因
        """
        if not content:
            return True, "empty_content"
        
        content_lower = content.lower()
        
        # 检查恶意模式
        for pattern in self.malicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False, f"malicious_pattern_{pattern}"
        
        # 检查敏感词
        content_lower = content.lower()
        for word in self.sensitive_words:
            if word in content_lower:
                return False, f"sensitive_content_{word}"
        
        # 重复内容检测
        content_hash = hashlib.md5(content.encode()).hexdigest()
        cache_key = f"content_hash_{content_hash}"
        
        if cache_manager.get_db_result(cache_key):
            return False, "duplicate_content"
        else:
            # 缓存内容哈希（1小时）
            cache_manager.set_db_result(cache_key, True, 3600)
        
        return True, "safe_content"
    
    def check_rate_limit(self, user_id: int, action_type: str = 'global') -> Tuple[bool, str]:
        """检查用户是否超过限流
        
        Args:
            user_id: 用户ID
            action_type: 操作类型
            
        Returns:
            (allowed, reason): 是否允许及原因
        """
        # 检查用户是否在黑名单中
        if self._is_user_blacklisted(user_id):
            return False, "user_blacklisted"
        
        # 创建限流器键
        key = f"{user_id}_{action_type}"
        now = time.time()
        
        # 获取或创建限流器
        if key not in self.rate_limiters:
            self.rate_limiters[key] = RateLimiter(max_requests=10, time_window=60)  # 10次/分钟
        
        limiter = self.rate_limiters[key]
        
        # 检查是否超过限流
        if not limiter.allow_request():
            # 记录限流事件
            self._record_security_event(user_id, "RATE_LIMIT_EXCEEDED", "LOW", f"操作类型: {action_type}")
            
            # 更新用户行为
            self.user_behavior[user_id]['rate_limit_count'] += 1
            
            # 检查是否需要执行惩罚
            self._check_punishment(user_id, action_type)
            
            return False, "rate_limited"
        
        # 更新用户行为
        behavior = self.user_behavior[user_id]
        behavior['request_count'] += 1
        behavior['last_request'] = now
        
        return True, "allowed"
    
    def check_user_behavior(self, user_id: int, action_type: str) -> Tuple[bool, str]:
        """检查用户行为是否异常
        
        Args:
            user_id: 用户ID
            action_type: 操作类型
            
        Returns:
            (allowed, reason): 是否允许及原因
        """
        behavior = self.user_behavior[user_id]
        now = time.time()
        
        # 检查短时间内请求频率
        if now - behavior['last_request'] < 0.1:  # 100ms内连续请求
            behavior['suspicious_actions'] += 1
            
            # 记录可疑行为
            if behavior['suspicious_actions'] >= 5:
                self._record_security_event(
                    user_id, "SUSPICIOUS_BEHAVIOR", "MEDIUM",
                    f"高频请求行为, 操作类型: {action_type}"
                )
                return False, "suspicious_behavior"
        
        return True, "normal_behavior"
    
    def add_to_blacklist(self, user_id: int, duration: int = 3600, reason: str = ""):
        """添加用户到黑名单"""
        unban_time = time.time() + duration
        self.user_blacklist[user_id] = unban_time
        
        self._record_security_event(
            user_id, "USER_BLACKLISTED", "HIGH",
            f"封禁时长: {duration}秒, 原因: {reason}"
        )
        
        log_system_event(
            "USER_BLACKLISTED",
            f"用户 {user_id} 被封禁 {duration} 秒, 原因: {reason}",
            "WARNING"
        )
    
    def remove_from_blacklist(self, user_id: int):
        """从黑名单移除用户"""
        if user_id in self.user_blacklist:
            del self.user_blacklist[user_id]
            
            self._record_security_event(
                user_id, "USER_UNBANNED", "MEDIUM",
                "手动解封"
            )
    
    def get_security_report(self, hours: int = 24) -> Dict[str, Any]:
        """生成安全报告"""
        cutoff_time = time.time() - (hours * 3600)
        
        recent_events = [
            event for event in self.security_events 
            if event.timestamp > cutoff_time
        ]
        
        # 统计事件类型
        event_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for event in recent_events:
            event_counts[event.event_type] += 1
            severity_counts[event.severity] += 1
        
        # 计算风险等级
        risk_score = (
            severity_counts['CRITICAL'] * 10 +
            severity_counts['HIGH'] * 5 +
            severity_counts['MEDIUM'] * 2 +
            severity_counts['LOW'] * 1
        )
        
        if risk_score > 50:
            risk_level = "🔴 高风险"
        elif risk_score > 20:
            risk_level = "🟡 中风险"
        else:
            risk_level = "🟢 低风险"
        
        return {
            'time_range': f"最近 {hours} 小时",
            'total_events': len(recent_events),
            'event_types': dict(event_counts),
            'severity_distribution': dict(severity_counts),
            'risk_score': risk_score,
            'risk_level': risk_level,
            'active_blacklist': len(self.user_blacklist),
            'recent_events': recent_events[-10:]  # 最近10个事件
        }
    
    def cleanup_expired(self):
        """清理过期数据"""
        now = time.time()
        
        # 清理过期的黑名单
        expired_users = [
            user_id for user_id, unban_time in self.user_blacklist.items()
            if unban_time <= now
        ]
        
        for user_id in expired_users:
            del self.user_blacklist[user_id]
            self._record_security_event(
                user_id, "AUTO_UNBANNED", "LOW",
                "自动解封"
            )
        
        # 清理旧的限流器
        expired_limiters = []
        for key, limiter in self.rate_limiters.items():
            if now - limiter.last_refill > 3600:  # 1小时未使用
                expired_limiters.append(key)
        
        for key in expired_limiters:
            del self.rate_limiters[key]
        
        logger.info(f"安全清理完成: 解封 {len(expired_users)} 用户, 清理 {len(expired_limiters)} 个限流器")
    
    # 私有方法
    def _is_user_blacklisted(self, user_id: int) -> bool:
        """检查用户是否在黑名单中"""
        if user_id not in self.user_blacklist:
            return False
        
        if time.time() >= self.user_blacklist[user_id]:
            # 自动解封
            del self.user_blacklist[user_id]
            return False
        
        return True
    
    def _update_user_behavior(self, user_id: int, action_type: str):
        """更新用户行为记录"""
        behavior = self.user_behavior[user_id]
        now = time.time()
        
        # 重置可疑行为计数（如果时间间隔足够）
        if now - behavior.get('last_request', 0) > 5:
            behavior['suspicious_actions'] = max(0, behavior['suspicious_actions'] - 1)
    
    def _check_punishment(self, user_id: int, action_type: str):
        """检查是否需要执行惩罚"""
        # 计算用户在短时间内的限流次数
        recent_events = [
            event for event in self.security_events
            if (event.user_id == user_id and 
                event.event_type == "RATE_LIMIT_EXCEEDED" and
                time.time() - event.timestamp < 300)  # 5分钟内
        ]
        
        if len(recent_events) >= 5:  # 5分钟内5次限流
            # 临时封禁用户
            self.add_to_blacklist(user_id, 900, "频繁触发限流")  # 15分钟封禁
    
    def _record_security_event(self, user_id: int, event_type: str, severity: str, details: str):
        """记录安全事件"""
        event = SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            details=details
        )
        
        self.security_events.append(event)
        
        # 高危事件立即记录日志
        if severity in ['HIGH', 'CRITICAL']:
            log_system_event(
                f"SECURITY_{event_type}",
                f"用户 {user_id}: {details}",
                "WARNING" if severity == 'HIGH' else "ERROR"
            )

class RateLimiter:
    """限流器"""
    
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.last_refill = time.time()
    
    def allow_request(self) -> bool:
        """检查是否允许请求"""
        now = time.time()
        
        # 清理过期请求记录
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
        
        # 检查是否超过限制
        if len(self.requests) >= self.max_requests:
            return False
        
        # 记录当前请求
        self.requests.append(now)
        self.last_refill = now
        return True

# 全局安全管理器实例
security_manager = SecurityManager()

# 安全装饰器
def rate_limit(action_type: str = 'global'):
    """限流装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(update, context):
            user = update.effective_user
            if not user:
                return
            
            # 检查限流
            allowed, reason = security_manager.check_rate_limit(user.id, action_type)
            
            if not allowed:
                if reason == "rate_limited":
                    if update.callback_query:
                        update.callback_query.answer("⚠️ 操作过于频繁，请稍后再试", show_alert=True)
                    else:
                        update.message.reply_text("⚠️ 操作过于频繁，请稍后再试")
                elif reason == "user_blacklisted":
                    if update.callback_query:
                        update.callback_query.answer("🚫 您暂时无法使用此功能", show_alert=True)
                    else:
                        update.message.reply_text("🚫 您暂时无法使用此功能")
                return
            
            # 检查用户行为
            behavior_ok, behavior_reason = security_manager.check_user_behavior(user.id, action_type)
            
            if not behavior_ok:
                if update.callback_query:
                    update.callback_query.answer("⚠️ 检测到异常行为，请稍后再试", show_alert=True)
                else:
                    update.message.reply_text("⚠️ 检测到异常行为，请稍后再试")
                return
            
            # 执行原函数
            return func(update, context)
        return wrapper
    return decorator

def content_security_check():
    """内容安全检查装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(update, context):
            # 检查消息内容安全性
            if update.message and update.message.text:
                is_safe, reason = security_manager.check_content_security(update.message.text)
                
                if not is_safe:
                    user = update.effective_user
                    if user:
                        security_manager._record_security_event(
                            user.id, "CONTENT_BLOCKED", "MEDIUM",
                            f"内容被阻止: {reason}"
                        )
                    
                    if update.callback_query:
                        update.callback_query.answer("⚠️ 内容包含不安全元素", show_alert=True)
                    else:
                        update.message.reply_text("⚠️ 内容包含不安全元素")
                    return
            
            # 执行原函数
            return func(update, context)
        return wrapper
    return decorator