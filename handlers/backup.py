# handlers/backup.py
"""
备份功能模块

本模块处理系统数据的备份功能，包括：
- 数据库备份
- 配置文件备份
- 完整系统备份

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

import logging
import json
import re

from telegram import Update
from telegram.ext import CallbackContext

from config import ADMIN_IDS
from database import db

from keyboards import (
    back_button,                   # 返回按钮
    database_backup_menu,          # 数据备份菜单
    backup_confirmation_menu,      # 备份确认菜单
)

from utils.backup import (
    create_full_backup,            # 创建完整备份
    create_database_backup,        # 创建数据库备份
    create_config_backup,          # 创建配置备份
    get_backup_status              # 获取备份状态
)
from utils.logging_utils import log_user_activity, log_admin_operation, log_system_event

# 初始化日志器
logger = logging.getLogger(__name__)

# 权限检查函数
def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===================================================
# 备份功能处理器 Backup Function Handlers
# ===================================================

async def database_backup_callback(update: Update, context: CallbackContext):
    """数据备份菜单回调
    
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
    
    if not is_admin(user.id):
        await query.answer("⚠️ 您不是管理员", show_alert=True)
        return
    
    await query.answer()
    await query.edit_message_text(
        "💾 数据备份管理\n\n请选择备份类型：",
        reply_markup=database_backup_menu()
    )

async def backup_full_callback(update: Update, context: CallbackContext):
    """完整备份回调
    
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
    
    if not is_admin(user.id):
        await query.answer("⚠️ 您不是管理员", show_alert=True)
        return
    
    await query.answer()
    await query.edit_message_text(
        "📦 完整系统备份\n\n将备份以下内容：\n"
        "- 数据库文件\n"
        "- 配置文件\n"
        "- 系统日志\n\n"
        "⚠️ 此操作可能需要较长时间。",
        reply_markup=backup_confirmation_menu("full")
    )

async def backup_database_only_callback(update: Update, context: CallbackContext):
    """仅数据库备份回调
    
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
    
    if not is_admin(user.id):
        await query.answer("⚠️ 您不是管理员", show_alert=True)
        return
    
    await query.answer()
    await query.edit_message_text(
        "🗄️ 数据库备份\n\n将备份数据库文件。\n"
        "包含所有投稿、用户和配置数据。\n\n"
        "💾 备份文件可用于数据恢复。",
        reply_markup=backup_confirmation_menu("database")
    )

async def backup_config_callback(update: Update, context: CallbackContext):
    """配置文件备份回调
    
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
    
    if not is_admin(user.id):
        await query.answer("⚠️ 您不是管理员", show_alert=True)
        return
    
    await query.answer()
    await query.edit_message_text(
        "⚙️ 配置文件备份\n\n将备份系统配置文件。\n"
        "包含环境变量和配置设置。\n\n"
        "🔧 备份可用于系统迁移或恢复。",
        reply_markup=backup_confirmation_menu("config")
    )

async def confirm_backup_callback(update: Update, context: CallbackContext):
    """确认备份回调
    
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
        
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    if not is_admin(user.id):
        await query.answer("⚠️ 您不是管理员", show_alert=True)
        return
    
    # 解析备份类型
    backup_type = data.replace("confirm_backup_", "")
    
    await query.answer()
    
    # 记录管理员操作
    log_admin_operation(
        user.id,
        user.username,
        "SYSTEM_BACKUP",
        None,
        f"Performing {backup_type} backup"
    )
    
    await query.edit_message_text(
        f"🔄 正在执行{backup_type}备份...\n\n请稍候，此过程可能需要几分钟。"
    )
    
    try:
        # 根据备份类型执行相应的备份操作
        if backup_type == "full":
            result = create_full_backup()
        elif backup_type == "database":
            result = create_database_backup()
        elif backup_type == "config":
            result = create_config_backup()
        else:
            await query.edit_message_text(
                "❌ 无效的备份类型",
                reply_markup=database_backup_menu()
            )
            return
        
        # 处理备份结果
        if result['status'] == 'success':
            text = f"✅ {backup_type}备份完成\n\n"
            
            # 添加具体的备份结果
            text += f"📁 备份文件: {result.get('name', 'N/A')}\n"
            text += f"📊 文件大小: {result.get('size', 0) / (1024*1024):.2f} MB\n"
            text += f"⏱️ 执行时间: {result.get('execution_time', 0):.2f}秒\n\n"
            
            text += "📋 备份详情:\n"
            for file in result.get('files', []):
                text += f"- {file}\n"
            
            # 发送成功通知给所有管理员
            for admin_id in ADMIN_IDS:
                try:
                    context.bot.send_message(
                        chat_id=admin_id,
                        text=f"💾 备份完成通知\n\n{text}\n👤 操作者: @{user.username}"
                    )
                except Exception as e:
                    logger.error(f"发送备份通知给 {admin_id} 失败: {e}")
        else:
            # 备份失败
            error_msg = "\n".join(result.get('errors', ['未知错误']))
            text = (
                f"❌ {backup_type}备份失败\n\n"
                f"错误信息: {error_msg}"
            )
        
        await query.edit_message_text(
            text,
            reply_markup=database_backup_menu()
        )
        
    except Exception as e:
        logger.error(f"备份操作失败: {e}")
        await query.edit_message_text(
            f"❌ 备份操作失败\n\n错误信息: {str(e)}",
            reply_markup=database_backup_menu()
        )