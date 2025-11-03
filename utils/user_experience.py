# utils/user_experience.py
"""
用户体验增强模块 - 提升交互体验和界面友好性

本模块专注于改善用户交互体验：

主要功能：
- 智能消息格式化：美化消息显示效果
- 进度指示器：显示操作进度和状态
- 快捷操作菜单：提供便捷的操作选项
- 个性化设置：用户偏好和设置管理
- 操作反馈：及时的操作结果反馈
- 上下文感知：智能识别用户意图

用户体验原则：
1. 简洁明了：界面简洁，操作直观
2. 及时反馈：操作有即时响应
3. 容错设计：错误处理人性化
4. 个性化：支持用户个性化设置

作者: AI Assistant
版本: 2.0
最后更新: 2025-09-05
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext

from config import ADMIN_IDS
from utils.cache import cache_manager
from utils.logging_utils import log_user_activity
# 时间工具函数
from utils.time_utils import get_beijing_now

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """消息类型枚举"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PROGRESS = "progress"

@dataclass
class UserPreferences:
    """用户偏好设置"""
    language: str = "zh"
    notifications: bool = True
    compact_mode: bool = False
    show_tips: bool = True
    theme: str = "default"
    auto_preview: bool = True

class MessageFormatter:
    """消息格式化器"""
    
    # 图标映射
    ICONS = {
        MessageType.SUCCESS: "✅",
        MessageType.ERROR: "❌", 
        MessageType.WARNING: "⚠️",
        MessageType.INFO: "ℹ️",
        MessageType.PROGRESS: "⏳"
    }
    
    # 状态图标
    STATUS_ICONS = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌',
        'processing': '🔄',
        'completed': '✅',
        'failed': '❌',
        'cancelled': '🚫'
    }
    
    @classmethod
    def format_message(cls, msg_type: MessageType, title: str, content: str = "", 
                      show_timestamp: bool = False) -> str:
        """格式化消息"""
        icon = cls.ICONS.get(msg_type, "")
        
        formatted = f"{icon} **{title}**"
        
        if content:
            formatted += f"\n\n{content}"
        
        if show_timestamp:
            timestamp = get_beijing_now().strftime("%H:%M:%S")
            formatted += f"\n\n🕐 {timestamp}"
            
        return formatted
    
    @classmethod
    def format_submission_info(cls, submission_data: Dict) -> str:
        """格式化投稿信息显示"""
        user_info = f"👤 **用户信息**"
        user_info += f"\n• ID: `{submission_data.get('user_id', 'N/A')}`"
        user_info += f"\n• 用户名: @{submission_data.get('username', '无')}"
        
        if submission_data.get('anonymous', False):
            user_info += f"\n• 🎭 匿名投稿"
        
        submission_info = f"\n\n📝 **投稿信息**"
        submission_info += f"\n• 类型: {cls._get_type_display(submission_data.get('type', ''))}"
        submission_info += f"\n• 状态: {cls._get_status_display(submission_data.get('status', ''))}"
        
        if submission_data.get('category'):
            submission_info += f"\n• 分类: {submission_data.get('category')}"
        
        # 时间信息
        time_info = f"\n\n🕐 **时间信息**"
        if submission_data.get('timestamp'):
            time_info += f"\n• 提交时间: {cls._format_datetime(submission_data['timestamp'])}"
        
        if submission_data.get('handled_at'):
            time_info += f"\n• 处理时间: {cls._format_datetime(submission_data['handled_at'])}"
        
        return user_info + submission_info + time_info
    
    @classmethod
    def format_stats_display(cls, stats: Dict) -> str:
        """格式化统计信息显示"""
        text = "📊 **系统统计**\n\n"
        
        # 投稿统计
        if 'total_submissions' in stats:
            text += "📝 **投稿统计**\n"
            text += f"• 总投稿数: {stats.get('total_submissions', 0):,}\n"
            text += f"• 待审核: {stats.get('pending_submissions', 0):,}\n"
            text += f"• 已通过: {stats.get('approved_submissions', 0):,}\n"
            text += f"• 已拒绝: {stats.get('rejected_submissions', 0):,}\n"
            
            # 通过率
            if stats.get('total_submissions', 0) > 0:
                approval_rate = stats.get('approved_submissions', 0) / stats['total_submissions'] * 100
                text += f"• 通过率: {approval_rate:.1f}%\n"
        
        # 用户统计
        if 'total_users' in stats:
            text += f"\n👥 **用户统计**\n"
            text += f"• 总用户数: {stats.get('total_users', 0):,}\n"
        
        return text
    
    @classmethod
    def format_progress_bar(cls, current: int, total: int, width: int = 10) -> str:
        """生成进度条"""
        if total == 0:
            return "⬜" * width
        
        filled = int((current / total) * width)
        bar = "🟩" * filled + "⬜" * (width - filled)
        percentage = (current / total) * 100
        
        return f"{bar} {percentage:.1f}% ({current}/{total})"
    
    @classmethod
    def _get_type_display(cls, submission_type: str) -> str:
        """获取投稿类型显示名称"""
        type_map = {
            'text': '📝 文字',
            'photo': '🖼 图片',
            'video': '🎬 视频',
            'media': '🎭 媒体',
            'business': '🤝 商务'
        }
        return type_map.get(submission_type, submission_type)
    
    @classmethod
    def _get_status_display(cls, status: str) -> str:
        """获取状态显示"""
        icon = cls.STATUS_ICONS.get(status, "")
        status_map = {
            'pending': '待审核',
            'approved': '已通过',
            'rejected': '已拒绝',
            'processing': '处理中'
        }
        name = status_map.get(status, status)
        return f"{icon} {name}"
    
    @classmethod
    def _format_datetime(cls, dt) -> str:
        """格式化日期时间"""
        if isinstance(dt, str):
            return dt
        try:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(dt)

class ProgressIndicator:
    """进度指示器"""
    
    def __init__(self, context: CallbackContext, chat_id: int):
        self.context = context
        self.chat_id = chat_id
        self.message = None
        self.start_time = time.time()
    
    def start(self, initial_text: str):
        """开始显示进度"""
        try:
            self.message = self.context.bot.send_message(
                chat_id=self.chat_id,
                text=f"⏳ {initial_text}..."
            )
        except Exception as e:
            logger.error(f"发送进度消息失败: {e}")
    
    def update(self, text: str, current: int = 0, total: int = 0):
        """更新进度"""
        if not self.message:
            return
        
        try:
            formatted_text = f"🔄 {text}"
            
            if total > 0:
                progress_bar = MessageFormatter.format_progress_bar(current, total)
                formatted_text += f"\n\n{progress_bar}"
            
            elapsed = time.time() - self.start_time
            formatted_text += f"\n\n⏱️ 已用时: {elapsed:.1f}秒"
            
            self.context.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message.message_id,
                text=formatted_text
            )
        except Exception as e:
            logger.error(f"更新进度消息失败: {e}")
    
    def complete(self, final_text: str, success: bool = True):
        """完成进度指示"""
        if not self.message:
            return
        
        try:
            icon = "✅" if success else "❌"
            elapsed = time.time() - self.start_time
            
            final_message = f"{icon} {final_text}\n\n⏱️ 耗时: {elapsed:.1f}秒"
            
            self.context.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message.message_id,
                text=final_message
            )
        except Exception as e:
            logger.error(f"完成进度消息失败: {e}")

class QuickActions:
    """快捷操作管理器"""
    
    @staticmethod
    def create_quick_menu(user_id: int, context: str = "general") -> InlineKeyboardMarkup:
        """创建快捷操作菜单"""
        is_admin = user_id in ADMIN_IDS
        
        if context == "submission":
            buttons = [
                [
                    InlineKeyboardButton("📝 文字投稿", callback_data="submit_text"),
                    InlineKeyboardButton("🎬 媒体投稿", callback_data="submit_media")
                ],
                [
                    InlineKeyboardButton("👤 个人中心", callback_data="user_profile"),
                    InlineKeyboardButton("📊 我的统计", callback_data="my_submission_stats")
                ]
            ]
        elif context == "admin" and is_admin:
            buttons = [
                [
                    InlineKeyboardButton("📬 待审稿件", callback_data="admin_pending"),
                    InlineKeyboardButton("📊 系统统计", callback_data="submission_stats")
                ],
                [
                    InlineKeyboardButton("🖥 服务器状态", callback_data="server_status")
                ]
            ]
        else:  # general
            buttons = [
                [
                    InlineKeyboardButton("📤 投稿", callback_data="submit_menu"),
                    InlineKeyboardButton("👤 个人", callback_data="user_profile")
                ],
                [
                    InlineKeyboardButton("❓ 帮助", callback_data="help_menu"),
                    InlineKeyboardButton("📞 客服", callback_data="copy_support_link")
                ]
            ]
            
            if is_admin:
                buttons.append([
                    InlineKeyboardButton("⚙️ 管理", callback_data="admin_panel")
                ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def create_action_confirmation(action: str, target: str = "") -> InlineKeyboardMarkup:
        """创建操作确认菜单"""
        buttons = [
            [
                InlineKeyboardButton("✅ 确认", callback_data=f"confirm_{action}_{target}"),
                InlineKeyboardButton("❌ 取消", callback_data=f"cancel_{action}")
            ]
        ]
        return InlineKeyboardMarkup(buttons)

class UserPreferencesManager:
    """用户偏好设置管理器"""
    
    @staticmethod
    def get_user_preferences(user_id: int) -> UserPreferences:
        """获取用户偏好设置"""
        cache_key = f"user_prefs_{user_id}"
        cached_prefs = cache_manager.get_config(cache_key)
        
        if cached_prefs:
            return UserPreferences(**cached_prefs)
        
        # 从数据库获取或创建默认设置
        try:
            from database import db
            user_data = db.get_user_data(user_id) if hasattr(db, 'get_user_data') else {}
            prefs_data = user_data.get('preferences', {})
            
            prefs = UserPreferences(**prefs_data)
            
            # 缓存设置
            cache_manager.set_config(cache_key, prefs.__dict__)
            
            return prefs
        except Exception as e:
            logger.error(f"获取用户偏好失败: {e}")
            return UserPreferences()
    
    @staticmethod
    def save_user_preferences(user_id: int, preferences: UserPreferences):
        """保存用户偏好设置"""
        try:
            # 更新缓存
            cache_key = f"user_prefs_{user_id}"
            cache_manager.set_config(cache_key, preferences.__dict__)
            
            # 保存到数据库（如果有相应方法）
            from database import db
            if hasattr(db, 'save_user_data'):
                db.save_user_data(user_id, {'preferences': preferences.__dict__})
            
            log_user_activity(user_id, None, "更新偏好设置")
            
        except Exception as e:
            logger.error(f"保存用户偏好失败: {e}")

class SmartNotification:
    """智能通知系统"""
    
    @staticmethod
    def send_smart_notification(context: CallbackContext, user_id: int, 
                              notification_type: str, content: str, 
                              priority: str = "normal"):
        """发送智能通知"""
        prefs = UserPreferencesManager.get_user_preferences(user_id)
        
        # 检查用户是否开启了通知
        if not prefs.notifications:
            return
        
        # 根据优先级决定通知方式
        if priority == "high":
            # 高优先级：立即发送
            icon = "🔔"
        elif priority == "low":
            # 低优先级：可能合并发送
            icon = "💡"
        else:
            # 普通优先级
            icon = "📢"
        
        try:
            message = f"{icon} **{notification_type}**\n\n{content}"
            
            context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            
            log_user_activity(user_id, None, f"接收通知: {notification_type}")
            
        except Exception as e:
            logger.error(f"发送智能通知失败: {e}")

class ContextAwareHelper:
    """上下文感知助手"""
    
    HELP_CONTEXTS = {
        'submission': {
            'title': '📝 投稿帮助',
            'content': '''
• **文字投稿**: 直接发送文字内容
• **图片投稿**: 发送图片并添加说明（最多20张）
• **视频投稿**: 发送视频并添加说明（最多20个）
• **混合媒体投稿**: 支持图片和视频混合上传
• **匿名投稿**: 可选择匿名发布
• **催审功能**: 投稿后可催促审核

💡 **小贴士**: 
• 内容要积极正面，符合社区规范
• 媒体文件会保留原始质量
• 混合媒体投稿会自动分组发布
            '''
        },
        'review': {
            'title': '👑 审核帮助',
            'content': '''
• **查看投稿**: 仔细阅读/观看内容
• **通过审核**: 内容符合要求
• **拒绝投稿**: 说明具体原因
• **联系用户**: 需要更多信息时
• **标签管理**: 为投稿添加标签

💡 **小贴士**: 公平公正，及时处理
            '''
        },
        'admin': {
            'title': '⚙️ 管理帮助',
            'content': '''
• **用户管理**: 查看用户信息和活动
• **数据统计**: 监控系统运行状况
• **系统设置**: 调整机器人配置
• **备份清理**: 维护系统性能
• **安全监控**: 查看安全事件

💡 **小贴士**: 定期备份，监控异常
            '''
        }
    }
    
    @staticmethod
    def get_contextual_help(context: str, user_role: str = "user") -> str:
        """获取上下文相关的帮助信息"""
        help_info = ContextAwareHelper.HELP_CONTEXTS.get(context)
        
        if not help_info:
            return ContextAwareHelper._get_general_help(user_role)
        
        return MessageFormatter.format_message(
            MessageType.INFO,
            help_info['title'],
            help_info['content']
        )
    
    @staticmethod
    def _get_general_help(user_role: str) -> str:
        """获取通用帮助信息"""
        if user_role == "admin":
            content = '''
🎛 **管理功能**
• 投稿审核和管理
• 用户数据统计
• 系统状态监控
• 备份和清理工具

📞 **需要帮助？**
• 查看各功能的帮助说明
• 联系技术支持
            '''
        else:
            content = '''
📝 **主要功能**
• 文字和媒体投稿
• 查看投稿状态
• 个人中心管理
• 申请成为审核员

❓ **常见问题**
• 如何投稿？发送内容即可
• 审核需要多久？通常24小时内
• 为什么被拒绝？查看拒绝原因

📞 **需要帮助？**
• 使用 /help 查看详细说明
• 联系客服获取支持
            '''
        
        return MessageFormatter.format_message(
            MessageType.INFO,
            "💡 使用帮助",
            content
        )

class InteractionEnhancer:
    """交互体验增强器"""
    
    @staticmethod
    def enhance_message_with_actions(text: str, context: str, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        """为消息增加快捷操作"""
        # 添加快捷操作菜单
        quick_menu = QuickActions.create_quick_menu(user_id, context)
        
        # 添加操作提示
        if context == "submission_complete":
            text += "\n\n💡 **接下来你可以**:"
            text += "\n• 查看投稿状态"
            text += "\n• 继续投稿"
            text += "\n• 查看个人统计"
        
        return text, quick_menu
    
    @staticmethod
    def add_smart_suggestions(text: str, user_activity: Dict) -> str:
        """添加智能建议"""
        suggestions = []
        
        # 基于用户活动的建议
        if user_activity.get('submission_count', 0) == 0:
            suggestions.append("💡 试试发送你的第一个投稿吧！")
        elif user_activity.get('recent_rejections', 0) > 2:
            suggestions.append("💡 查看投稿指南，提高通过率")
        
        if suggestions:
            text += "\n\n" + "\n".join(suggestions)
        
        return text

# 便捷函数
def format_success_message(title: str, content: str = "") -> str:
    """格式化成功消息"""
    return MessageFormatter.format_message(MessageType.SUCCESS, title, content)

def format_error_message(title: str, content: str = "") -> str:
    """格式化错误消息"""
    return MessageFormatter.format_message(MessageType.ERROR, title, content)

def format_warning_message(title: str, content: str = "") -> str:
    """格式化警告消息"""
    return MessageFormatter.format_message(MessageType.WARNING, title, content)

def create_progress_indicator(context: CallbackContext, chat_id: int) -> ProgressIndicator:
    """创建进度指示器"""
    return ProgressIndicator(context, chat_id)

def send_notification(context: CallbackContext, user_id: int, 
                     notification_type: str, content: str, priority: str = "normal"):
    """发送智能通知"""
    SmartNotification.send_smart_notification(
        context, user_id, notification_type, content, priority
    )