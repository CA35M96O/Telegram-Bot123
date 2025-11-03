# handlers/statistics.py
"""
数据统计功能模块

本模块处理各种数据统计功能，包括：
- 投稿统计数据
- 用户和系统数据统计
- 服务器状态信息

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

import logging
import json
from datetime import datetime, timedelta
from sqlalchemy import func

from telegram import Update
from telegram.ext import CallbackContext

from config import ADMIN_IDS
from database import db

from keyboards import (
    back_button,                   # 返回按钮
    server_status_menu,            # 服务器状态菜单
)

from utils.server_status import get_server_status  # 服务器状态获取
from utils.logging_utils import log_user_activity, log_admin_operation, log_system_event
from utils.time_utils import get_beijing_now, format_beijing_time

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
# 数据统计功能处理器 Statistics Function Handlers
# =====================================================

async def submission_stats_callback(update: Update, context: CallbackContext):
    """投稿统计回调 - 重构优化版本
    
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
    
    if not is_reviewer_or_admin(user.id):
        await query.answer("⚠️ 您没有权限", show_alert=True)
        return
    
    await query.answer()
    
    try:
        # 获取统计数据
        stats_data = _get_submission_statistics()
        
        # 格式化显示
        stats_text = _format_submission_stats(stats_data)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=back_button("admin_panel")
        )
        
    except Exception as e:
        logger.error(f"获取投稿统计失败: {e}")
        await query.edit_message_text(
            "❌ 获取统计数据失败，请稍后再试",
            reply_markup=back_button("admin_panel")
        )

def _get_submission_statistics():
    """获取投稿统计数据
    
    Returns:
        dict: 统计数据
    """
    session = db.Session()
    try:
        from database import Submission
        
        # 基本统计
        total = session.query(Submission).count()
        pending = session.query(Submission).filter_by(status='pending').count()
        approved = session.query(Submission).filter_by(status='approved').count()
        rejected = session.query(Submission).filter_by(status='rejected').count()
        
        # 类型统计
        text_count = session.query(Submission).filter_by(type='text', category='submission').count()
        photo_count = session.query(Submission).filter_by(type='photo', category='submission').count()
        video_count = session.query(Submission).filter_by(type='video', category='submission').count()
        business_count = session.query(Submission).filter_by(category='business').count()
        
        return {
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'text_count': text_count,
            'photo_count': photo_count,
            'video_count': video_count,
            'business_count': business_count
        }
    finally:
        session.close()

def _format_submission_stats(stats):
    """格式化投稿统计文本
    
    Args:
        stats: 统计数据
        
    Returns:
        str: 格式化后的文本
    """
    return (
        "📊 投稿统计\n\n"
        f"📬 总投稿数: {stats['total']}\n"
        f"⏳ 待审中: {stats['pending']}\n"
        f"✅ 已通过: {stats['approved']}\n"
        f"❌ 已拒绝: {stats['rejected']}\n\n"
        f"📁 按类型统计:\n"
        f"📝 文本投稿: {stats['text_count']}\n"
        f"🖼 图片投稿: {stats['photo_count']}\n"
        f"🎬 视频投稿: {stats['video_count']}\n"
        f"🤝 商务合作: {stats['business_count']}"
    )

async def data_stats_callback(update: Update, context: CallbackContext):
    """数据统计回调 - 重构优化版本
    
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
    
    if not is_reviewer_or_admin(user.id):
        await query.answer("⚠️ 您没有权限", show_alert=True)
        return
    
    await query.answer()
    
    try:
        # 获取数据统计
        data_stats = _get_data_statistics()
        
        # 格式化显示
        stats_text = _format_data_stats(data_stats)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=back_button("admin_panel")
        )
        
    except Exception as e:
        logger.error(f"获取数据统计失败: {e}")
        await query.edit_message_text(
            "❌ 获取统计数据失败，请稍后再试",
            reply_markup=back_button("admin_panel")
        )

def _get_data_statistics():
    """获取数据统计信息
    
    Returns:
        dict: 数据统计信息
    """
    session = db.Session()
    try:
        from database import Submission, User
        
        # 最近7天投稿统计
        seven_days_ago = get_beijing_now() - timedelta(days=7)
        recent_count = session.query(Submission).filter(Submission.timestamp >= seven_days_ago).count()
        
        # 总投稿和日均统计
        total = session.query(Submission).count()
        oldest = session.query(func.min(Submission.timestamp)).scalar()
        
        if oldest:
            # 确保两个datetime对象具有相同的时区属性
            # 如果oldest是naive datetime，将其转换为aware datetime
            if oldest.tzinfo is None:
                from datetime import timezone
                oldest = oldest.replace(tzinfo=timezone.utc)
            
            # 确保get_beijing_now()也是aware datetime
            now = get_beijing_now()
            if now.tzinfo is None:
                from datetime import timezone
                now = now.replace(tzinfo=timezone.utc)
                
            days = (now - oldest).days or 1
            daily_avg = total / days
        else:
            daily_avg = 0
        
        # 用户统计
        user_count = db.get_user_count()
        blocked_user_count = db.get_blocked_user_count()
        active_users = session.query(User).filter(
            User.last_interaction >= get_beijing_now() - timedelta(days=30)
        ).count()
        
        return {
            'recent_count': recent_count,
            'daily_avg': daily_avg,
            'user_count': user_count,
            'blocked_user_count': blocked_user_count,
            'active_users': active_users,
            'admin_count': len(ADMIN_IDS)
        }
    finally:
        session.close()

def _format_data_stats(stats):
    """格式化数据统计文本
    
    Args:
        stats: 统计数据
        
    Returns:
        str: 格式化后的文本
    """
    return (
        "📈 数据统计\n\n"
        f"📅 最近7天投稿: {stats['recent_count']}\n"
        f"📊 每日平均投稿: {stats['daily_avg']:.1f}\n"
        f"👥 总用户数: {stats['user_count']} (被拉黑删除: {stats['blocked_user_count']})\n"
        f"👤 月活跃用户: {stats['active_users']}\n"
        f"👑 管理员数量: {stats['admin_count']}\n"
    )

async def server_status_callback(update: Update, context: CallbackContext):
    """服务器状态回调
    
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
        status_text = get_server_status()
        await query.edit_message_text(
            status_text,
            parse_mode='Markdown',
            reply_markup=server_status_menu()
        )
    except Exception as e:
        logger.error(f"获取服务器状态失败: {e}")
        await query.edit_message_text(
            "⚠️ 无法获取服务器状态信息",
            reply_markup=back_button("admin_panel")
        )
