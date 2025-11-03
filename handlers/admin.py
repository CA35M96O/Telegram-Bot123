# handlers/admin.py
"""
管理员面板处理模块 - 系统管理和审核功能

本模块处理所有管理员和审核员相关的功能，包括：
- 管理员面板导航和权限控制
- 投稿审核和状态管理
- 用户管理和封禁操作
- 系统统计和数据监控
- 服务器状态检查和维护
- 审核员权限管理和申请处理

设计原则：
- 严格的权限验证机制
- 操作日志记录和追踪
- 安全的回调查询处理
- 数据验证和错误恢复

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

# =====================================================
# 所需库导入 Required Library Imports
# =====================================================

# Python 标准库
import logging
import json
import time
import re
from datetime import datetime

# Telegram Bot API 组件
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

# 项目配置和数据库
from config import ADMIN_IDS, MANAGEMENT_GROUP_ID, CHANNEL_IDS, GROUP_IDS
from database import db

# 键盘布局组件
from keyboards import (
    admin_panel_menu,              # 管理员主面板菜单
    admin_panel_menu_for_reviewer,  # 审核员专用的管理员面板菜单
    reviewer_panel_menu,           # 审核员面板菜单
    reviewer_management_menu,      # 新增：审核员管理菜单
    review_panel_menu,             # 审核面板菜单
    history_review_panel_menu,     # 历史审核面板菜单
    back_button,                   # 返回按钮
    server_status_menu,            # 服务器状态菜单
    membership_check_menu,         # 成员资格检查菜单
    reviewer_applications_menu,    # 审核员申请菜单
    broadcast_confirmation_menu,   # 广播确认菜单
    restart_bot_confirmation_menu, # 重启机器人确认菜单
    database_backup_menu,          # 数据备份菜单
    database_cleanup_menu,         # 数据清理菜单
    backup_confirmation_menu,      # 备份确认菜单
    cleanup_confirmation_menu,     # 清理确认菜单
    user_list_menu                 # 用户列表菜单
)

# 工具函数
from utils.logging_utils import log_system_event
from utils.time_utils import get_beijing_now, format_beijing_time
from utils.helpers import show_submission

# 初始化日志器
logger = logging.getLogger(__name__)

# 权限检查函数
def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_reviewer(user_id):
    try:
        with db.session_scope() as session:
            from database import ReviewerApplication
            application = session.query(ReviewerApplication).filter_by(
                user_id=user_id, 
                status='approved'
            ).first()
            
            return application is not None
    except Exception as e:
        logger.error(f"检查审核员状态失败: {e}")
        return False

def is_reviewer_or_admin(user_id):
    return is_admin(user_id) or is_reviewer(user_id)

# =====================================================
# 管理员面板主功能 Admin Panel Main Functions
# =====================================================

async def admin_panel_callback(update: Update, context: CallbackContext):
    """管理员面板回调处理
    
    根据用户权限显示不同的管理员面板界面
    管理员可访问完整功能，审核员仅可访问部分功能
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    # 验证用户权限
    if not is_reviewer_or_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    # 记录管理员活动
    from utils.logging_utils import log_admin_operation
    log_admin_operation(
        user.id, 
        user.username, 
        "ADMIN_PANEL_ACCESS", 
        "Accessed admin panel"
    )
    
    # 根据用户权限显示不同的面板
    if is_admin(user.id):
        # 管理员 - 显示完整功能面板
        await query.edit_message_text(
            "🔧 管理员面板\n\n"
            "请选择要执行的操作：",
            reply_markup=admin_panel_menu()
        )
    else:
        # 审核员 - 显示受限功能面板
        await query.edit_message_text(
            "📋 审核员面板\n\n"
            "请选择要执行的操作：",
            reply_markup=admin_panel_menu_for_reviewer()
        )

async def reviewer_management_callback(update: Update, context: CallbackContext):
    """审核员管理回调处理
    
    处理审核员相关的管理操作，包括：
    - 审核员列表查看
    - 添加/删除审核员
    - 权限设置
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    # 只有管理员可以管理审核员
    if not is_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    await query.answer()
    
    # 记录管理员活动
    from utils.logging_utils import log_admin_operation
    log_admin_operation(
        user.id, 
        user.username, 
        "REVIEWER_MANAGEMENT", 
        "Accessed reviewer management"
    )
    
    # 显示审核员管理菜单
    await query.edit_message_text(
        "👥 审核员管理\n\n"
        "请选择要执行的操作：",
        reply_markup=reviewer_management_menu()
    )


async def debug_mode_settings_callback(update: Update, context: CallbackContext):
    """调试模式设置回调处理
    
    处理调试模式相关的设置操作
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    # 只有管理员可以管理系统设置
    if not is_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    await query.answer()
    
    # 显示调试模式设置菜单
    keyboard = [
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)  # type: ignore
    
    await query.edit_message_text(
        "🔧 调试模式设置\n\n"
        "调试模式相关设置功能正在开发中...",
        reply_markup=reply_markup  # type: ignore
    )

# =====================================================
# 投稿审核功能 Submission Review Functions
# =====================================================

async def admin_pending_callback(update: Update, context: CallbackContext):
    """待审稿件回调处理
    
    显示待审核的投稿列表，支持分页浏览
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    await query.answer()
    
    # 验证用户权限
    if not is_reviewer_or_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    # 记录管理员活动
    from utils.logging_utils import log_admin_operation
    log_admin_operation(
        user.id, 
        user.username, 
        "VIEW_PENDING", 
        "Viewed pending submissions"
    )
    
    # 尝试使用优化方法获取待审稿件
    try:
        await handle_admin_panel(update, context)
    except Exception as e:
        logger.error(f"处理管理员面板请求失败: {e}")
        # 回退到备用方法
        await _admin_pending_fallback(update, context)

async def handle_admin_panel(update: Update, context: CallbackContext):
    """处理管理员面板请求 - 优化版本
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    try:
        # 优化：使用数据库查询直接获取待审稿件，而不是加载所有数据
        pending_data = []
        with db.session_scope() as session:
            from database import Submission
            # 只查询待审稿件，限制数量以提高性能
            pending = session.query(Submission).filter_by(status='pending').order_by(Submission.timestamp.desc()).limit(50).all()
            
            for submission in pending:
                # 处理投稿数据
                try:
                    file_ids = json.loads(getattr(submission, 'file_ids', '[]')) if hasattr(submission, 'file_ids') and getattr(submission, 'file_ids') else []
                except:
                    file_ids = []
                    
                try:
                    tags = json.loads(getattr(submission, 'tags', '[]')) if hasattr(submission, 'tags') and getattr(submission, 'tags') else []
                except:
                    tags = []
                    
                try:
                    file_types = json.loads(getattr(submission, 'file_types', '[]')) if hasattr(submission, 'file_types') and getattr(submission, 'file_types') else []
                except:
                    file_types = []
                    
                submission_data = {
                    'id': getattr(submission, 'id'),
                    'user_id': getattr(submission, 'user_id'),
                    'username': getattr(submission, 'username'),
                    'type': getattr(submission, 'type'),
                    'content': getattr(submission, 'content'),
                    'file_id': getattr(submission, 'file_id'),
                    'file_ids': file_ids,
                    'file_types': file_types,
                    'tags': tags,
                    'status': getattr(submission, 'status'),
                    'category': getattr(submission, 'category'),
                    'anonymous': getattr(submission, 'anonymous'),
                    'cover_index': getattr(submission, 'cover_index') or 0,
                    'reject_reason': getattr(submission, 'reject_reason'),
                    'handled_by': getattr(submission, 'handled_by'),
                    'handled_at': getattr(submission, 'handled_at'),
                    'timestamp': getattr(submission, 'timestamp')
                }
                pending_data.append(submission_data)
        
        if not pending_data:
            await query.edit_message_text(
                "📬 待审稿件\n\n"
                "当前没有待审核的稿件。",
                reply_markup=InlineKeyboardMarkup([  # type: ignore
                    [InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_panel")]
                ])  # type: ignore
            )
            return
        
        # 缓存数据到用户上下文
        if context.user_data is not None:
            context.user_data['pending_submissions'] = pending_data
            context.user_data['current_index'] = 0
        
        # 显示第一个待审稿件
        await show_submission(context, pending_data[0], user.id, 0, len(pending_data))
        logger.info("成功处理管理员面板请求")
        
    except Exception as e:
        logger.error(f"处理管理员面板请求失败: {e}")
        # 回退到备用方法
        raise e

async def _admin_pending_fallback(update: Update, context: CallbackContext):
    """管理员面板备用方法 - 确保系统正常运行
    
    当优化方法失败时，回退到原始实现
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    try:
        pending_data = []
        with db.session_scope() as session:
            from database import Submission
            pending = session.query(Submission).filter_by(status='pending').limit(20).all()
            
            if not pending:
                if query is not None:
                    try:
                        await query.answer()
                    except:
                        pass
                    
                    await query.edit_message_text(
                        "📬 待审稿件\n\n"
                        "当前没有待审核的稿件。",
                        reply_markup=InlineKeyboardMarkup([  # type: ignore
                            [InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_panel")]
                        ])  # type: ignore
                    )
                return
            
            for submission in pending:
                # 处理投稿数据
                try:
                    file_ids = json.loads(getattr(submission, 'file_ids', '[]')) if hasattr(submission, 'file_ids') and getattr(submission, 'file_ids') else []
                except:
                    file_ids = []
                
                try:
                    tags = json.loads(getattr(submission, 'tags', '[]')) if hasattr(submission, 'tags') and getattr(submission, 'tags') else []
                except:
                    tags = []
                
                try:
                    file_types = json.loads(getattr(submission, 'file_types', '[]')) if hasattr(submission, 'file_types') and getattr(submission, 'file_types') else []
                except:
                    file_types = []
                
                processed_data = {
                    'id': getattr(submission, 'id'),
                    'user_id': getattr(submission, 'user_id'),
                    'username': getattr(submission, 'username'),
                    'type': getattr(submission, 'type'),
                    'content': getattr(submission, 'content'),
                    'file_id': getattr(submission, 'file_id'),
                    'file_ids': file_ids,
                    'file_types': file_types,
                    'tags': tags,
                    'status': getattr(submission, 'status'),
                    'category': getattr(submission, 'category'),
                    'anonymous': getattr(submission, 'anonymous'),
                    'cover_index': getattr(submission, 'cover_index') or 0,
                    'reject_reason': getattr(submission, 'reject_reason'),
                    'handled_by': getattr(submission, 'handled_by'),
                    'handled_at': getattr(submission, 'handled_at'),
                    'timestamp': getattr(submission, 'timestamp')
                }
                pending_data.append(processed_data)
        
        if context.user_data is not None:
            context.user_data['pending_submissions'] = pending_data
            context.user_data['current_index'] = 0
        
        await show_submission(context, pending_data[0], user.id, 0, len(pending_data))
        logger.info("使用备用方法成功处理管理员面板请求")
        
    except Exception as fallback_error:
        logger.error(f"备用方法也失败: {fallback_error}")
        await query.answer("系统错误，请稍后再试", show_alert=True)

# 导出所有回调函数
__all__ = [
    'admin_panel_callback',
    'reviewer_management_callback',
    'debug_mode_settings_callback',  # 系统管理功能已替换为调试模式设置
    'admin_pending_callback',
    'handle_admin_panel',
    '_admin_pending_fallback',
    'is_reviewer_or_admin',
    'is_admin',
    'is_reviewer',
    'add_reviewer_callback',
    'remove_reviewer_callback',
    'reviewer_permissions_callback',
    'broadcast_message_callback',
    'restart_bot_callback',
    'confirm_restart_bot_callback'  # 添加确认重启机器人回调函数
]

# 添加审核员相关处理器
async def add_reviewer_callback(update: Update, context: CallbackContext):
    """添加审核员回调处理
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    # 只有管理员可以添加审核员
    if not is_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    await query.answer()
    
    # 显示添加审核员界面
    await query.edit_message_text(
        "📥 添加审核员\n\n"
        "请发送要添加为审核员的用户ID：",
        reply_markup=back_button("reviewer_management")
    )
    
    # 设置用户状态等待输入
    from handlers.submission import STATE_ADD_REVIEWER
    db.set_user_state(user.id, STATE_ADD_REVIEWER)


async def remove_reviewer_callback(update: Update, context: CallbackContext):
    """删除审核员回调处理
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    # 只有管理员可以删除审核员
    if not is_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    await query.answer()
    
    # 显示删除审核员界面
    await query.edit_message_text(
        "📤 删除审核员\n\n"
        "请发送要删除的审核员用户ID：",
        reply_markup=back_button("reviewer_management")
    )
    
    # 设置用户状态等待输入
    from handlers.submission import STATE_REMOVE_REVIEWER
    db.set_user_state(user.id, STATE_REMOVE_REVIEWER)


async def reviewer_permissions_callback(update: Update, context: CallbackContext):
    """审核员权限设置回调处理
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    # 只有管理员可以设置审核员权限
    if not is_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    await query.answer()
    
    # 显示权限设置说明
    await query.edit_message_text(
        "⚙️ 审核员权限设置\n\n"
        "请先选择要设置权限的审核员，然后进行权限配置。",
        reply_markup=back_button("reviewer_management")
    )


async def broadcast_message_callback(update: Update, context: CallbackContext):
    """全员通知回调处理
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    # 只有管理员可以发送全员通知
    if not is_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    await query.answer()
    
    # 显示发送通知界面
    await query.edit_message_text(
        "📢 全员通知\n\n"
        "请发送要发送的全员通知内容：",
        reply_markup=back_button("admin_panel")
    )
    
    # 设置用户状态等待输入
    db.set_user_state(user.id, "broadcast_message")


async def restart_bot_callback(update: Update, context: CallbackContext):
    """重启机器人回调处理
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    # 只有管理员可以重启机器人
    if not is_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    await query.answer()
    
    # 显示重启确认界面
    await query.edit_message_text(
        "🔄 重启机器人\n\n"
        "您确定要重启机器人吗？这将中断所有正在进行的操作。",
        reply_markup=restart_bot_confirmation_menu()
    )


async def confirm_restart_bot_callback(update: Update, context: CallbackContext):
    """确认重启机器人回调处理
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    user = query.from_user
    if user is None:
        return
    
    # 只有管理员可以重启机器人
    if not is_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    await query.answer("✅ 正在重启机器人...", show_alert=True)
    
    # 记录重启事件
    log_system_event(
        "BOT_RESTART_INITIATED", 
        f"Bot restart initiated by admin {user.id} (@{user.username})"
    )
    
    # 发送重启通知给所有管理员
    restart_message = f"🔄 机器人正在重启...\n操作员: @{user.username} (ID: {user.id})"
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=restart_message)
        except Exception as e:
            logger.error(f"发送重启通知给管理员 {admin_id} 失败: {e}")
    
    # 延迟1秒后重启机器人
    import asyncio
    import sys
    await asyncio.sleep(1)
    
    # 退出程序，让外部进程管理器重启机器人
    logger.info("机器人重启已启动，正在关闭当前进程...")
    sys.exit(0)

