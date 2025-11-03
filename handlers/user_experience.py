# handlers/user_experience.py
"""
用户体验处理器 - 用户界面和交互体验管理

本模块处理用户体验相关的回调和功能：

主要功能：
- 用户偏好设置管理
- 快捷操作菜单
- 智能帮助系统
- 个性化界面设置
- 交互体验优化

作者: AI Assistant
版本: 2.0
最后更新: 2025-09-05
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from config import ADMIN_IDS
from utils.user_experience import (
    MessageFormatter, MessageType, QuickActions, 
    UserPreferencesManager, UserPreferences,
    ContextAwareHelper, InteractionEnhancer,
    format_success_message, format_error_message,
    send_notification
)
from utils.logging_utils import log_user_activity

logger = logging.getLogger(__name__)

def is_admin(user_id):
    """检查用户是否为管理员"""
    return user_id in ADMIN_IDS

async def user_experience_menu_callback(update: Update, context: CallbackContext):
    """用户体验设置主菜单"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    # 获取用户偏好
    prefs = UserPreferencesManager.get_user_preferences(user.id)
    
    text = "🎨 **个性化设置**\n\n"
    text += "✨ 让机器人更符合你的使用习惯\n\n"
    
    text += f"📋 **当前设置**:\n"
    text += f"• 🔔 通知: {'开启' if prefs.notifications else '关闭'}\n"
    text += f"• 📱 紧凑模式: {'开启' if prefs.compact_mode else '关闭'}\n"
    text += f"• 💡 显示提示: {'开启' if prefs.show_tips else '关闭'}\n"
    text += f"• 👁 自动预览: {'开启' if prefs.auto_preview else '关闭'}\n"
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"🔔 通知 {'✅' if prefs.notifications else '❌'}", 
                callback_data="toggle_notifications"
            ),
            InlineKeyboardButton(
                f"📱 紧凑模式 {'✅' if prefs.compact_mode else '❌'}", 
                callback_data="toggle_compact_mode"
            )
        ],
        [
            InlineKeyboardButton(
                f"💡 提示 {'✅' if prefs.show_tips else '❌'}", 
                callback_data="toggle_tips"
            ),
            InlineKeyboardButton(
                f"👁 预览 {'✅' if prefs.auto_preview else '❌'}", 
                callback_data="toggle_preview"
            )
        ],
        [InlineKeyboardButton("🎨 主题设置", callback_data="theme_settings")],
        [InlineKeyboardButton("🌐 语言设置", callback_data="language_settings")],
        [
            InlineKeyboardButton("📊 使用统计", callback_data="usage_stats"),
            InlineKeyboardButton("🔄 重置设置", callback_data="reset_preferences")
        ],
        [InlineKeyboardButton("🔙 返回个人中心", callback_data="user_profile")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, "访问个性化设置")

async def toggle_notifications_callback(update: Update, context: CallbackContext):
    """切换通知设置"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    # 获取并更新偏好
    prefs = UserPreferencesManager.get_user_preferences(user.id)
    prefs.notifications = not prefs.notifications
    UserPreferencesManager.save_user_preferences(user.id, prefs)
    
    # 发送反馈
    status = "开启" if prefs.notifications else "关闭"
    await query.answer(f"📱 通知已{status}", show_alert=True)
    
    # 刷新菜单
    await user_experience_menu_callback(update, context)
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, f"切换通知设置: {status}")

async def toggle_compact_mode_callback(update: Update, context: CallbackContext):
    """切换紧凑模式"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    # 获取并更新偏好
    prefs = UserPreferencesManager.get_user_preferences(user.id)
    prefs.compact_mode = not prefs.compact_mode
    UserPreferencesManager.save_user_preferences(user.id, prefs)
    
    # 发送反馈
    status = "开启" if prefs.compact_mode else "关闭"
    await query.answer(f"📱 紧凑模式已{status}", show_alert=True)
    
    # 刷新菜单
    await user_experience_menu_callback(update, context)
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, f"切换紧凑模式: {status}")

async def toggle_tips_callback(update: Update, context: CallbackContext):
    """切换提示显示"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    # 获取并更新偏好
    prefs = UserPreferencesManager.get_user_preferences(user.id)
    prefs.show_tips = not prefs.show_tips
    UserPreferencesManager.save_user_preferences(user.id, prefs)
    
    # 发送反馈
    status = "开启" if prefs.show_tips else "关闭"
    await query.answer(f"💡 操作提示已{status}", show_alert=True)
    
    # 刷新菜单
    await user_experience_menu_callback(update, context)
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, f"切换提示显示: {status}")

async def toggle_preview_callback(update: Update, context: CallbackContext):
    """切换自动预览"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    # 获取并更新偏好
    prefs = UserPreferencesManager.get_user_preferences(user.id)
    prefs.auto_preview = not prefs.auto_preview
    UserPreferencesManager.save_user_preferences(user.id, prefs)
    
    # 发送反馈
    status = "开启" if prefs.auto_preview else "关闭"
    await query.answer(f"👁 自动预览已{status}", show_alert=True)
    
    # 刷新菜单
    await user_experience_menu_callback(update, context)
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, f"切换自动预览: {status}")

async def usage_stats_callback(update: Update, context: CallbackContext):
    """显示用户使用统计"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    try:
        # 从数据库获取用户统计
        from database import db
        
        user_data = db.get_user_by_id(user.id)
        submission_count = db.get_database_stats().get('total_submissions', 0) if hasattr(db, 'get_database_stats') else 0
        
        text = "📊 **使用统计**\n\n"
        
        if user_data:
            text += f"👤 **基本信息**:\n"
            text += f"• 用户ID: `{user.id}`\n"
            text += f"• 用户名: @{user.username or '未设置'}\n"
            text += f"• 姓名: {user.first_name} {user.last_name or ''}\n"
            
            if hasattr(user_data, 'first_interaction'):
                text += f"• 加入时间: {user_data.first_interaction}\n"
        
        text += f"\n📝 **投稿统计**:\n"
        text += f"• 总投稿数: {submission_count}\n"
        
        # 获取更详细的统计
        if hasattr(db, 'get_user_submission_stats'):
            stats = db.get_user_submission_stats(user.id)
            text += f"• 通过数量: {stats.get('approved', 0)}\n"
            text += f"• 拒绝数量: {stats.get('rejected', 0)}\n"
            text += f"• 待审数量: {stats.get('pending', 0)}\n"
            
            if submission_count > 0:
                approval_rate = stats.get('approved', 0) / submission_count * 100
                text += f"• 通过率: {approval_rate:.1f}%\n"
        
        # 活跃度统计
        text += f"\n📈 **活跃度**:\n"
        text += f"• 本周投稿: {_get_weekly_submissions(user.id)}\n"
        text += f"• 本月投稿: {_get_monthly_submissions(user.id)}\n"
        
        # 偏好统计
        prefs = UserPreferencesManager.get_user_preferences(user.id)
        text += f"\n⚙️ **个性化设置**:\n"
        text += f"• 通知: {'开启' if prefs.notifications else '关闭'}\n"
        text += f"• 紧凑模式: {'开启' if prefs.compact_mode else '关闭'}\n"
        text += f"• 显示提示: {'开启' if prefs.show_tips else '关闭'}\n"
        
    except Exception as e:
        logger.error(f"获取用户统计失败: {e}")
        text = format_error_message("获取统计失败", "无法获取用户统计信息，请稍后重试")
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 刷新统计", callback_data="usage_stats"),
            InlineKeyboardButton("📊 投稿历史", callback_data="my_submission_stats")
        ],
        [InlineKeyboardButton("🔙 返回设置", callback_data="user_experience_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, "查看使用统计")

async def smart_help_callback(update: Update, context: CallbackContext):
    """智能帮助系统"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    # 确定用户角色
    user_role = "admin" if is_admin(user.id) else "user"
    
    # 从callback_data获取上下文
    help_context = "general"
    if query.data and query.data.startswith("help_"):
        help_context = query.data.replace("help_", "")
    
    # 获取上下文相关的帮助
    help_content = ContextAwareHelper.get_contextual_help(help_context, user_role)
    
    # 创建帮助类别菜单
    keyboard = [
        [
            InlineKeyboardButton("📝 投稿帮助", callback_data="help_submission"),
            InlineKeyboardButton("👤 个人中心", callback_data="help_profile")
        ]
    ]
    
    if user_role == "admin":
        keyboard.extend([
            [
                InlineKeyboardButton("👑 审核帮助", callback_data="help_review"),
                InlineKeyboardButton("⚙️ 管理帮助", callback_data="help_admin")
            ]
        ])
    
    keyboard.extend([
        [
            InlineKeyboardButton("❓ 常见问题", callback_data="help_faq"),
            InlineKeyboardButton("📞 联系客服", callback_data="copy_support_link")
        ],
        [InlineKeyboardButton("🔙 返回", callback_data="main_menu")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(help_content, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "Message is not modified" in str(e):
            pass  # 忽略消息未修改的错误
        else:
            raise  # 重新抛出其他异常
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, f"查看帮助: {help_context}")

async def reset_preferences_callback(update: Update, context: CallbackContext):
    """重置用户偏好设置"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    # 显示确认对话框
    text = "🔄 **重置个性化设置**\n\n"
    text += "⚠️ 此操作将恢复所有设置到默认值：\n\n"
    text += "• 🔔 通知：开启\n"
    text += "• 📱 紧凑模式：关闭\n"
    text += "• 💡 显示提示：开启\n"
    text += "• 👁 自动预览：开启\n"
    text += "• 🎨 主题：默认\n"
    text += "• 🌐 语言：中文\n\n"
    text += "确定要继续吗？"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ 确认重置", callback_data="confirm_reset_preferences"),
            InlineKeyboardButton("❌ 取消", callback_data="user_experience_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def confirm_reset_preferences_callback(update: Update, context: CallbackContext):
    """确认重置偏好设置"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    try:
        # 创建默认偏好并保存
        default_prefs = UserPreferences()
        UserPreferencesManager.save_user_preferences(user.id, default_prefs)
        
        # 发送成功消息
        success_msg = format_success_message(
            "设置重置成功",
            "所有个性化设置已恢复到默认值"
        )
        
        keyboard = [
            [InlineKeyboardButton("📊 查看设置", callback_data="user_experience_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(success_msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        if user.id is not None and user.username is not None:
            log_user_activity(user.id, user.username, "重置个性化设置")
        
    except Exception as e:
        logger.error(f"重置用户偏好失败: {e}")
        error_msg = format_error_message("重置失败", "无法重置设置，请稍后重试")
        await query.edit_message_text(error_msg, parse_mode='Markdown')

async def quick_action_callback(update: Update, context: CallbackContext):
    """处理快捷操作回调"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
        
    action = query.data
    
    await query.answer()
    
    # 根据快捷操作类型执行相应功能
    if action == "quick_submit":
        # 快捷投稿
        from handlers.submission import start_text_submission
        # 创建一个新的Update对象，只包含必要的信息
        new_update = Update(
            update_id=update.update_id,
            message=update.message
        )
        await start_text_submission(new_update, context)
        
    elif action == "quick_profile":
        # 快捷个人中心
        from handlers.user_profile import user_profile_callback
        await user_profile_callback(update, context)
        
    elif action == "quick_help":
        # 快捷帮助
        await smart_help_callback(update, context)
        
    elif action == "quick_admin" and is_admin(user.id):
        # 快捷管理面板
        from handlers.admin import admin_panel_callback
        await admin_panel_callback(update, context)
    
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, f"使用快捷操作: {action}")

async def theme_settings_callback(update: Update, context: CallbackContext):
    """主题设置菜单"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    text = "🎨 **主题设置**\n\n"
    text += "📝 当前仅支持默认主题\n\n"
    text += "🔎 **可用主题**:\n"
    text += "• 🌆 默认主题 - 简洁明亮\n"
    text += "• 🌃 深色主题 - 即将推出\n"
    text += "• 🌈 彩色主题 - 即将推出\n\n"
    text += "💫 更多主题正在开发中..."
    
    keyboard = [
        [InlineKeyboardButton("🌆 默认主题 ✅", callback_data="theme_default")],
        [InlineKeyboardButton("🔙 返回设置", callback_data="user_experience_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, "查看主题设置")

async def language_settings_callback(update: Update, context: CallbackContext):
    """语言设置菜单"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    prefs = UserPreferencesManager.get_user_preferences(user.id)
    
    text = "🌐 **语言设置**\n\n"
    text += f"📝 当前语言: {'简体中文' if prefs.language == 'zh' else prefs.language}\n\n"
    text += "🔎 **可用语言**:\n"
    text += "• 🇨🇳 简体中文 (当前)\n"
    text += "• 🇺🇸 English - 即将支持\n"
    text += "• 🇯🇵 日本語 - 即将支持\n"
    text += "• 🇰🇷 한국어 - 即将支持\n\n"
    text += "💫 多语言支持正在开发中..."
    
    keyboard = [
        [InlineKeyboardButton("🇨🇳 简体中文 ✅", callback_data="lang_zh")],
        [InlineKeyboardButton("🔙 返回设置", callback_data="user_experience_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    if user.id is not None and user.username is not None:
        log_user_activity(user.id, user.username, "查看语言设置")

# 辅助函数
def _get_weekly_submissions(user_id: int) -> int:
    """获取本周投稿数量"""
    try:
        from database import db
        
        week_ago = get_beijing_now() - timedelta(days=7)
        
        # 使用数据库管理器的现有方法
        return 0
    except Exception as e:
        logger.error(f"获取本周投稿数量失败: {e}")
        return 0

def _get_monthly_submissions(user_id: int) -> int:
    """获取本月投稿数量"""
    try:
        from database import db
        
        month_ago = get_beijing_now() - timedelta(days=30)
        
        # 使用数据库管理器的现有方法
        return 0
    except Exception as e:
        logger.error(f"获取本月投稿数量失败: {e}")
        return 0

from datetime import timedelta
# 导入时间工具
from utils.time_utils import get_beijing_now

async def generate_user_weekly_stats(user_id: int) -> dict:
    """生成用户周统计数据"""
    try:
        from database import db
        
        # 计算一周前的时间
        week_ago = get_beijing_now() - timedelta(days=7)
        
        stats = {
            'period': 'weekly',
            'start_date': week_ago,
            'end_date': get_beijing_now()
        }
        
        # 获取用户一周内的投稿统计
        with db.session_scope() as session:
            from database import Submission
            
            # 获取总投稿数
            total_submissions = session.query(Submission).filter(
                Submission.user_id == user_id,
                Submission.timestamp >= week_ago
            ).count()
            
            # 获取通过的投稿数
            approved_submissions = session.query(Submission).filter(
                Submission.user_id == user_id,
                Submission.status == 'approved',
                Submission.timestamp >= week_ago
            ).count()
            
            # 获取拒绝的投稿数
            rejected_submissions = session.query(Submission).filter(
                Submission.user_id == user_id,
                Submission.status == 'rejected',
                Submission.timestamp >= week_ago
            ).count()
            
            stats.update({
                'total_submissions': total_submissions,
                'approved_submissions': approved_submissions,
                'rejected_submissions': rejected_submissions
            })
        
        return stats
    except Exception as e:
        logger.error(f"生成用户周统计数据失败: {e}")
        return {}

async def generate_user_monthly_stats(user_id: int) -> dict:
    """生成用户月统计数据"""
    try:
        from database import db
        
        # 计算一个月前的时间
        month_ago = get_beijing_now() - timedelta(days=30)
        
        stats = {
            'period': 'monthly',
            'start_date': month_ago,
            'end_date': get_beijing_now()
        }
        
        # 获取用户一个月内的投稿统计
        with db.session_scope() as session:
            from database import Submission
            
            # 获取总投稿数
            total_submissions = session.query(Submission).filter(
                Submission.user_id == user_id,
                Submission.timestamp >= month_ago
            ).count()
            
            # 获取通过的投稿数
            approved_submissions = session.query(Submission).filter(
                Submission.user_id == user_id,
                Submission.status == 'approved',
                Submission.timestamp >= month_ago
            ).count()
            
            # 获取拒绝的投稿数
            rejected_submissions = session.query(Submission).filter(
                Submission.user_id == user_id,
                Submission.status == 'rejected',
                Submission.timestamp >= month_ago
            ).count()
            
            stats.update({
                'total_submissions': total_submissions,
                'approved_submissions': approved_submissions,
                'rejected_submissions': rejected_submissions
            })
        
        return stats
    except Exception as e:
        logger.error(f"生成用户月统计数据失败: {e}")
        return {}
