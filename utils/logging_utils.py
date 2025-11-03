# utils/logging_utils.py
"""
日志工具模块 - 统一的日志记录系统

本模块提供统一的日志记录功能，解决循环导入问题。

主要功能：
1. 用户活动日志 - 记录用户在系统中的所有操作
2. 管理员操作日志 - 记录管理员的管理行为
3. 系统事件日志 - 记录系统级别的重要事件
4. 投稿事件日志 - 记录投稿相关的所有操作

设计目的：
- 避免模块间的循环导入问题
- 提供统一的日志格式和结构
- 分类记录不同类型的系统事件
- 支持灵活的日志级别设置

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

# =====================================================
# 日志配置 Logging Configuration
# =====================================================

# Python 标准库
import logging

# 初始化日志器 - 使用模块名作为日志器名称
logger = logging.getLogger(__name__)

def log_user_activity(user_id, username, activity, details=""):
    """
    记录用户活动日志
    
    Args:
        user_id: 用户ID
        username: 用户名
        activity: 活动类型
        details: 详细信息
    """
    logger.info(f"USER_ACTIVITY - ID:{user_id} @{username or 'None'} - {activity} - {details}")

def log_admin_operation(admin_id, admin_username, operation, target=None, details=""):
    """
    记录管理员操作日志
    
    Args:
        admin_id: 管理员ID
        admin_username: 管理员用户名
        operation: 操作类型
        target: 操作目标
        details: 详细信息
    """
    target_info = f" Target:{target}" if target else ""
    logger.info(f"ADMIN_OPERATION - ID:{admin_id} @{admin_username or 'None'} - {operation}{target_info} - {details}")

def log_system_event(event_type, details="", level="INFO"):
    """
    记录系统事件日志
    
    Args:
        event_type: 事件类型
        details: 详细信息
        level: 日志级别
    """
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(f"SYSTEM_EVENT - {event_type} - {details}")

def log_submission_event(user_id, username, submission_id, event_type, details=""):
    """
    记录投稿事件日志
    
    Args:
        user_id: 用户ID
        username: 用户名
        submission_id: 投稿ID
        event_type: 事件类型
        details: 详细信息
    """
    logger.info(f"SUBMISSION_EVENT - ID:{user_id} @{username or 'None'} - Submission:{submission_id} - {event_type} - {details}")