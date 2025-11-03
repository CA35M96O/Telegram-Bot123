# handlers/cleanup.py
"""
清理功能模块

本模块处理系统数据的清理功能，包括：
- 旧数据清理
- 用户状态清理
- 日志清理
- 数据库优化
- 内存垃圾收集

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
    database_cleanup_menu,         # 数据清理菜单
    cleanup_confirmation_menu      # 清理确认菜单
)

from utils.cleanup import (
    cleanup_old_data,              # 清理旧数据
    cleanup_user_states,           # 清理用户状态
    cleanup_logs,                  # 清理日志文件
    optimize_database,             # 优化数据库
    garbage_collection,            # 垃圾收集
    get_cleanup_status             # 获取清理状态
)
from utils.logging_utils import log_user_activity, log_admin_operation, log_system_event

# 初始化日志器
logger = logging.getLogger(__name__)

# 权限检查函数
def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===================================================
# 清理功能处理器 Cleanup Function Handlers
# ===================================================

async def database_cleanup_callback(update: Update, context: CallbackContext):
    """数据清理菜单回调
    
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
        "🧹 数据清理管理\n\n请选择清理类型：",
        reply_markup=database_cleanup_menu()
    )

async def cleanup_old_data_callback(update: Update, context: CallbackContext):
    """旧数据清理回调
    
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
        "🧹 旧数据清理\n\n将清理超过30天的旧数据：\n"
        "- 被拒绝的投稿\n"
        "- 过期的用户状态\n"
        "- 老旧的审核员申请\n\n"
        "⚠️ 此操作不可撤销！",
        reply_markup=cleanup_confirmation_menu("old_data")
    )

async def cleanup_user_states_callback(update: Update, context: CallbackContext):
    """用户状态清理回调
    
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
        "🗑️ 用户状态清理\n\n将清理所有用户的交互状态数据。\n"
        "这将重置所有用户的当前操作状态。\n\n",
        reply_markup=cleanup_confirmation_menu("user_states")
    )

async def cleanup_logs_callback(update: Update, context: CallbackContext):
    """日志清理回调
    
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
        "📅 日志清理\n\n将清理超过30天的旧日志文件。\n"
        "保留最近30天的日志以供问题排查。\n\n"
        "📀 可以释放磁盘空间。",
        reply_markup=cleanup_confirmation_menu("logs")
    )

async def optimize_database_callback(update: Update, context: CallbackContext):
    """数据库优化回调
    
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
        "📊 数据库优化\n\n将执行以下优化操作：\n"
        "- 重建数据库索引\n"
        "- 更新统计信息\n"
        "- 数据库空间清理\n"
        "- 优化数据库设置\n\n"
        "⚙️ 可以提高查询性能。",
        reply_markup=cleanup_confirmation_menu("optimize_database")
    )

async def garbage_collection_callback(update: Update, context: CallbackContext):
    """垃圾收集回调
    
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
        "🧽 垃圾收集\n\n将执行 Python 内存垃圾收集。\n"
        "清理无用的内存对象和缓存数据。\n\n"
        "💾 可以释放内存空间。",
        reply_markup=cleanup_confirmation_menu("garbage_collection")
    )

async def cleanup_status_callback(update: Update, context: CallbackContext):
    """清理状态回调
    
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
    
    try:
        # 获取清理状态
        status_info = get_cleanup_status()
        
        if status_info['status'] == 'error':
            text = (
                "📈 清理状态\n\n"
                f"❌ 错误: {status_info['message']}"
            )
        else:
            # 构建状态信息
            db_stats = status_info.get('database', {})
            log_stats = status_info.get('logs', {})
            system_stats = status_info.get('system', {})
            recommendations = status_info.get('recommendations', [])
            
            text = "📈 清理状态\n\n"
            
            # 数据库统计
            if db_stats and 'error' not in db_stats:
                text += "📄 数据库情况:\n"
                text += f"- 总投稿数: {db_stats.get('total_submissions', 0)}\n"
                text += f"- 待审投稿: {db_stats.get('pending_submissions', 0)}\n"
                text += f"- 被拒投稿: {db_stats.get('rejected_submissions', 0)}\n"
                text += f"- 用户状态: {db_stats.get('user_states', 0)}\n"
                
                if 'database_size_mb' in db_stats:
                    text += f"- 数据库大小: {db_stats['database_size_mb']:.2f} MB\n"
                text += "\n"
            
            # 日志统计
            if log_stats and 'error' not in log_stats:
                text += "📅 日志情况:\n"
                text += f"- 日志文件数: {log_stats.get('log_files_count', 0)}\n"
                text += f"- 日志大小: {log_stats.get('total_size_mb', 0):.2f} MB\n\n"
            
            # 系统资源
            if system_stats and 'error' not in system_stats:
                text += "🖥 系统资源:\n"
                text += f"- 内存使用: {system_stats.get('memory_usage_mb', 0):.2f} MB\n"
                text += f"- CPU 使用率: {system_stats.get('cpu_percent', 0):.1f}%\n"
                text += f"- 线程数: {system_stats.get('threads_count', 0)}\n\n"
            
            # 清理建议
            if recommendations:
                text += "💡 清理建议:\n"
                for i, rec in enumerate(recommendations[:3], 1):  # 只显示前3个建议
                    text += f"{i}. {rec}\n"
        
        await query.edit_message_text(
            text,
            reply_markup=database_cleanup_menu()
        )
        
    except Exception as e:
        logger.error(f"获取清理状态失败: {e}")
        await query.edit_message_text(
            "❌ 获取清理状态失败，请稍后再试。",
            reply_markup=database_cleanup_menu()
        )

async def confirm_cleanup_callback(update: Update, context: CallbackContext):
    """确认清理回调
    
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
    
    # 解析清理类型
    cleanup_type = data.replace("confirm_cleanup_", "")
    
    await query.answer()
    
    # 记录管理员操作
    log_admin_operation(
        user.id,
        user.username,
        "SYSTEM_CLEANUP",
        None,
        f"Performing {cleanup_type} cleanup"
    )
    
    await query.edit_message_text(
        f"🔄 正在执行{cleanup_type}清理...\n\n请稍候，此过程可能需要几分钟。"
    )
    
    try:
        # 根据清理类型执行相应的清理操作
        if cleanup_type == "old_data":
            result = cleanup_old_data()
        elif cleanup_type == "user_states":
            result = cleanup_user_states()
        elif cleanup_type == "logs":
            result = cleanup_logs(30)  # 清理30天前的日志
        elif cleanup_type == "optimize_database":
            result = optimize_database()
        elif cleanup_type == "garbage_collection":
            result = garbage_collection()
        else:
            await query.edit_message_text(
                "❌ 无效的清理类型",
                reply_markup=database_cleanup_menu()
            )
            return
        
        # 处理清理结果
        if result['status'] == 'success':
            text = f"✅ {cleanup_type}清理完成\n\n"
            
            # 添加具体的清理结果
            if cleanup_type == "old_data":
                total_cleaned = result.get('total_cleaned', 0)
                text += f"🗑️ 清理数量: {total_cleaned}条记录\n"
                
                cleaned_items = result.get('cleaned_items', {})
                if cleaned_items:
                    text += "清理详情:\n"
                    for item_type, count in cleaned_items.items():
                        if count > 0:
                            text += f"- {item_type}: {count}条\n"
            
            elif cleanup_type == "user_states":
                cleaned_count = result.get('cleaned_count', 0)
                text += f"🗑️ 清理数量: {cleaned_count}条状态\n"
            
            elif cleanup_type == "logs":
                files_count = result.get('files_count', 0)
                size_freed_mb = result.get('total_size_freed', 0) / (1024 * 1024)
                text += f"📅 清理文件: {files_count}个\n"
                text += f"📀 释放空间: {size_freed_mb:.2f} MB\n"
            
            elif cleanup_type == "optimize_database":
                operations = result.get('operations', [])
                if operations:
                    text += "操作列表:\n"
                    for op in operations[:5]:  # 只显示前5个操作
                        text += f"- {op}\n"
            
            elif cleanup_type == "garbage_collection":
                collected = result.get('total_collected', 0)
                memory_freed = result.get('memory_freed_mb', 0)
                text += f"🧽 收集对象: {collected}个\n"
                text += f"💾 释放内存: {memory_freed:.2f} MB\n"
            
            # 添加执行时间
            execution_time = result.get('execution_time', 0)
            text += f"\n⏱️ 执行时间: {execution_time:.2f}秒"
            
            # 发送成功通知给所有管理员
            for admin_id in ADMIN_IDS:
                try:
                    context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🧹 清理完成通知\n\n{text}\n👤 操作者: @{user.username}"
                    )
                except Exception as e:
                    logger.error(f"发送清理通知给 {admin_id} 失败: {e}")
        else:
            # 清理失败
            error_msg = "\n".join(result.get('errors', ['未知错误']))
            text = (
                f"❌ {cleanup_type}清理失败\n\n"
                f"错误信息: {error_msg}"
            )
        
        await query.edit_message_text(
            text,
            reply_markup=database_cleanup_menu()
        )
        
    except Exception as e:
        logger.error(f"清理操作失败: {e}")
        await query.edit_message_text(
            f"❌ 清理操作失败\n\n错误信息: {str(e)}",
            reply_markup=database_cleanup_menu()
        )