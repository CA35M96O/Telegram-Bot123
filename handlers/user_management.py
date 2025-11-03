# handlers/user_management.py
"""
用户管理功能模块

本模块处理用户相关的管理功能，包括：
- 用户列表查看
- 用户封禁/解封
- 审核员列表查看

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

import logging
import json
import re
from datetime import datetime
import pytz

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

from config import ADMIN_IDS
from database import db

from keyboards import (
    back_button,                   # 返回按钮
    user_list_type_menu,           # 用户列表类型菜单
    user_list_menu,                # 用户列表菜单
    ban_user_menu,                 # 用户封禁菜单
)

from utils.helpers import (
    check_user_bot_blocked,        # 检查用户是否屏蔽机器人
)
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

# 导出所有回调函数
__all__ = [
    'user_list_callback',
    'all_user_list_callback',
    'normal_user_list_callback',
    'blocked_user_list_callback',
    'banned_user_list_callback',
    'handle_user_list_page',
    'view_user_callback',
    'ban_user_callback',
    'reviewer_list_callback',
    'user_list_type_callback',  # 添加新函数到导出列表
    'direct_ban_user_callback',  # 添加新函数到导出列表
    'handle_user_id_input',  # 添加新函数到导出列表
    'set_reviewer_permissions_callback',  # 添加新函数到导出列表
    'toggle_reviewer_permission_callback'  # 添加新函数到导出列表
]

# =====================================================
# 用户管理功能处理器 User Management Function Handlers
# =====================================================

async def user_list_callback(update: Update, context: CallbackContext):
    """用户列表类型选择回调
    
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
        await query.edit_message_text(
            "👥 请选择用户列表类型：",
            reply_markup=user_list_type_menu()
        )
    except Exception as e:
        logger.error(f"显示用户列表类型选择失败: {e}")
        await query.edit_message_text(
            "❌ 显示用户列表类型选择失败，请稍后再试。",
            reply_markup=back_button("admin_panel")
        )

async def all_user_list_callback(update: Update, context: CallbackContext):
    """全部用户列表回调
    
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
        # 获取所有用户，按最后交互时间排序
        with db.session_scope() as session:
            from database import User
            from sqlalchemy import desc
            
            # 获取所有用户，按最后交互时间排序
            users = session.query(User).order_by(desc(User.last_interaction)).all()
            
            if not users:
                await query.edit_message_text(
                    "👥 用户列表\n\n暂无用户数据",
                    reply_markup=back_button("user_list_type")
                )
                return
            
            # 将用户对象转换为字典形式，避免Session关闭后的访问问题
            users_data = []
            for user_obj in users:
                user_dict = {
                    'user_id': getattr(user_obj, 'user_id', 0),
                    'username': getattr(user_obj, 'username', None),
                    'first_name': getattr(user_obj, 'first_name', None),
                    'last_name': getattr(user_obj, 'last_name', None),
                    'is_bot': getattr(user_obj, 'is_bot', False),
                    'last_interaction': getattr(user_obj, 'last_interaction', None),
                    'first_interaction': getattr(user_obj, 'first_interaction', None),
                    'bot_blocked': getattr(user_obj, 'bot_blocked', False),
                    'is_banned': getattr(user_obj, 'is_banned', False)
                }
                users_data.append(user_dict)
            
            # 检测用户是否删除或屏蔽了机器人（只检测最近10个活跃用户，避免API限制）
            for i, user_dict in enumerate(users_data[:10]):
                if not user_dict['bot_blocked']:  # 只检测未标记为已屏蔽的用户
                    try:
                        from utils.helpers import check_user_bot_blocked
                        is_blocked = check_user_bot_blocked(context, user_dict['user_id'])
                        if is_blocked:
                            user_dict['bot_blocked'] = True
                            # 更新数据库中的状态
                            db.update_user_bot_blocked(user_dict['user_id'], True)
                    except Exception as e:
                        logger.error(f"检测用户 {user_dict['user_id']} 状态失败: {e}")
            
            # 计算分页信息（每页10个用户）
            total_users = len(users_data)
            users_per_page = 10
            total_pages = (total_users + users_per_page - 1) // users_per_page
            
            # 默认显示第一页
            current_page = 0
            start_idx = current_page * users_per_page
            end_idx = min(start_idx + users_per_page, total_users)
            page_users = users_data[start_idx:end_idx]
            
            # 保存分页信息到context
            if context.user_data is not None:
                context.user_data['user_list'] = users_data  # 存储字典数据而不是对象
                context.user_data['user_list_current_page'] = current_page
                context.user_data['user_list_total_pages'] = total_pages
                context.user_data['user_list_type'] = "all"
            
            # 格式化用户列表文本
            user_list_text = _format_user_list(page_users, current_page, total_pages, total_users, "用户")
            
            await query.edit_message_text(
                user_list_text,
                reply_markup=user_list_menu(users[start_idx:end_idx], current_page, total_pages, "all")
            )
            
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        await query.edit_message_text(
            "❌ 获取用户列表失败，请稍后再试。",
            reply_markup=back_button("user_list_type")
        )

async def normal_user_list_callback(update: Update, context: CallbackContext):
    """正常用户列表回调
    
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
        # 获取所有正常用户（未被屏蔽且未被封禁，按最后交互时间倒序排列）
        with db.session_scope() as session:
            from database import User
            from sqlalchemy import desc
            
            # 获取所有正常用户（bot_blocked=False 且 is_banned=False）
            users = session.query(User).filter_by(bot_blocked=False, is_banned=False).order_by(desc(User.last_interaction)).all()
            
            if not users:
                await query.edit_message_text(
                    "✅ 正常用户列表\n\n暂无正常用户数据",
                    reply_markup=back_button("user_list_type")
                )
                return
            
            # 将用户对象转换为字典形式，避免Session关闭后的访问问题
            users_data = []
            for user_obj in users:
                user_dict = {
                    'user_id': getattr(user_obj, 'user_id', 0),
                    'username': getattr(user_obj, 'username', None),
                    'first_name': getattr(user_obj, 'first_name', None),
                    'last_name': getattr(user_obj, 'last_name', None),
                    'is_bot': getattr(user_obj, 'is_bot', False),
                    'last_interaction': getattr(user_obj, 'last_interaction', None),
                    'first_interaction': getattr(user_obj, 'first_interaction', None),
                    'bot_blocked': getattr(user_obj, 'bot_blocked', False),
                    'is_banned': getattr(user_obj, 'is_banned', False)
                }
                users_data.append(user_dict)
            
            # 计算分页信息（每页10个用户）
            total_users = len(users_data)
            users_per_page = 10
            total_pages = (total_users + users_per_page - 1) // users_per_page
            
            # 默认显示第一页
            current_page = 0
            start_idx = current_page * users_per_page
            end_idx = min(start_idx + users_per_page, total_users)
            page_users = users_data[start_idx:end_idx]
            
            # 保存分页信息到context
            if context.user_data is not None:
                context.user_data['user_list'] = users_data  # 存储字典数据而不是对象
                context.user_data['user_list_current_page'] = current_page
                context.user_data['user_list_total_pages'] = total_pages
                context.user_data['user_list_type'] = "normal"
            
            # 格式化用户列表文本
            user_list_text = _format_user_list(page_users, current_page, total_pages, total_users, "正常用户")
            
            await query.edit_message_text(
                user_list_text,
                reply_markup=user_list_menu(users[start_idx:end_idx], current_page, total_pages, "normal")
            )
            
    except Exception as e:
        logger.error(f"获取正常用户列表失败: {e}")
        await query.edit_message_text(
            "❌ 获取正常用户列表失败，请稍后再试。",
            reply_markup=back_button("user_list_type")
        )

async def blocked_user_list_callback(update: Update, context: CallbackContext):
    """屏蔽用户列表回调
    
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
        # 获取所有屏蔽用户（bot_blocked=True，按最后交互时间倒序排列）
        with db.session_scope() as session:
            from database import User
            from sqlalchemy import desc
            
            # 获取所有屏蔽用户（bot_blocked=True）
            users = session.query(User).filter_by(bot_blocked=True).order_by(desc(User.last_interaction)).all()
            
            if not users:
                await query.edit_message_text(
                    "🚫 屏蔽用户列表\n\n暂无被屏蔽用户数据",
                    reply_markup=back_button("user_list_type")
                )
                return
            
            # 将用户对象转换为字典形式，避免Session关闭后的访问问题
            users_data = []
            for user_obj in users:
                user_dict = {
                    'user_id': getattr(user_obj, 'user_id', 0),
                    'username': getattr(user_obj, 'username', None),
                    'first_name': getattr(user_obj, 'first_name', None),
                    'last_name': getattr(user_obj, 'last_name', None),
                    'is_bot': getattr(user_obj, 'is_bot', False),
                    'last_interaction': getattr(user_obj, 'last_interaction', None),
                    'first_interaction': getattr(user_obj, 'first_interaction', None),
                    'bot_blocked': getattr(user_obj, 'bot_blocked', False),
                    'is_banned': getattr(user_obj, 'is_banned', False)
                }
                users_data.append(user_dict)
            
            # 计算分页信息（每页10个用户）
            total_users = len(users_data)
            users_per_page = 10
            total_pages = (total_users + users_per_page - 1) // users_per_page
            
            # 默认显示第一页
            current_page = 0
            start_idx = current_page * users_per_page
            end_idx = min(start_idx + users_per_page, total_users)
            page_users = users_data[start_idx:end_idx]
            
            # 保存分页信息到context
            if context.user_data is not None:
                context.user_data['user_list'] = users_data  # 存储字典数据而不是对象
                context.user_data['user_list_current_page'] = current_page
                context.user_data['user_list_total_pages'] = total_pages
                context.user_data['user_list_type'] = "blocked"
            
            # 格式化用户列表文本
            user_list_text = _format_user_list(page_users, current_page, total_pages, total_users, "屏蔽用户")
            
            await query.edit_message_text(
                user_list_text,
                reply_markup=user_list_menu(users[start_idx:end_idx], current_page, total_pages, "blocked")
            )
            
    except Exception as e:
        logger.error(f"获取屏蔽用户列表失败: {e}")
        await query.edit_message_text(
            "❌ 获取屏蔽用户列表失败，请稍后再试。",
            reply_markup=back_button("user_list_type")
        )

async def banned_user_list_callback(update: Update, context: CallbackContext):
    """封禁用户列表回调
    
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
        # 获取所有封禁用户（is_banned=True，按最后交互时间倒序排列）
        with db.session_scope() as session:
            from database import User
            from sqlalchemy import desc
            
            # 获取所有封禁用户（is_banned=True）
            users = session.query(User).filter_by(is_banned=True).order_by(desc(User.last_interaction)).all()
            
            if not users:
                await query.edit_message_text(
                    "🔒 封禁用户列表\n\n暂无被封禁用户数据",
                    reply_markup=back_button("user_list_type")
                )
                return
            
            # 将用户对象转换为字典形式，避免Session关闭后的访问问题
            users_data = []
            for user_obj in users:
                user_dict = {
                    'user_id': getattr(user_obj, 'user_id', 0),
                    'username': getattr(user_obj, 'username', None),
                    'first_name': getattr(user_obj, 'first_name', None),
                    'last_name': getattr(user_obj, 'last_name', None),
                    'is_bot': getattr(user_obj, 'is_bot', False),
                    'last_interaction': getattr(user_obj, 'last_interaction', None),
                    'first_interaction': getattr(user_obj, 'first_interaction', None),
                    'bot_blocked': getattr(user_obj, 'bot_blocked', False),
                    'is_banned': getattr(user_obj, 'is_banned', False)
                }
                users_data.append(user_dict)
            
            # 计算分页信息（每页10个用户）
            total_users = len(users_data)
            users_per_page = 10
            total_pages = (total_users + users_per_page - 1) // users_per_page
            
            # 默认显示第一页
            current_page = 0
            start_idx = current_page * users_per_page
            end_idx = min(start_idx + users_per_page, total_users)
            page_users = users_data[start_idx:end_idx]
            
            # 保存分页信息到context
            if context.user_data is not None:
                context.user_data['user_list'] = users_data  # 存储字典数据而不是对象
                context.user_data['user_list_current_page'] = current_page
                context.user_data['user_list_total_pages'] = total_pages
                context.user_data['user_list_type'] = "banned"
            
            # 格式化用户列表文本
            user_list_text = _format_user_list(page_users, current_page, total_pages, total_users, "封禁用户")
            
            await query.edit_message_text(
                user_list_text,
                reply_markup=user_list_menu(users[start_idx:end_idx], current_page, total_pages, "banned")
            )
            
    except Exception as e:
        logger.error(f"获取封禁用户列表失败: {e}")
        await query.edit_message_text(
            "❌ 获取封禁用户列表失败，请稍后再试。",
            reply_markup=back_button("user_list_type")
        )

async def handle_user_list_page(update: Update, context: CallbackContext):
    """处理用户列表分页回调
    
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
    
    if not is_reviewer_or_admin(user.id):
        await query.answer("⚠️ 您没有权限", show_alert=True)
        return
    
    # 解析页码和列表类型
    import re
    match = re.match(r'^user_list_page_(\d+)_(normal|blocked|banned|all)$', data)
    if not match:
        # 尝试匹配旧格式
        old_match = re.match(r'^user_list_page_(\d+)$', data)
        if old_match:
            target_page = int(old_match.group(1))
            list_type = "all"
        else:
            await query.answer("无效的操作")
            return
    else:
        target_page = int(match.group(1))
        list_type = match.group(2)
    
    # 获取用户列表数据
    users = []
    total_pages = 1
    if context.user_data is not None:
        users = context.user_data.get('user_list', [])
        total_pages = context.user_data.get('user_list_total_pages', 1)
    
    if not users:
        await query.answer("用户列表数据不存在")
        return
    
    # 检查页码有效性
    if target_page < 0 or target_page >= total_pages:
        await query.answer("页码超出范围")
        return
    
    # 更新当前页码
    if context.user_data is not None:
        context.user_data['user_list_current_page'] = target_page
    
    # 获取当前页的用户
    users_per_page = 10
    start_idx = target_page * users_per_page
    end_idx = min(start_idx + users_per_page, len(users))
    page_users = users[start_idx:end_idx]
    
    # 格式化用户列表文本
    total_users = len(users)
    
    # 根据列表类型设置标题
    list_titles = {
        "normal": "正常用户",
        "blocked": "屏蔽用户", 
        "banned": "封禁用户",
        "all": "用户"
    }
    list_title = list_titles.get(list_type, "用户")
    
    # 注意：用户数据在初始加载时已经转换为字典格式，直接使用即可
    user_list_text = _format_user_list(page_users, target_page, total_pages, total_users, list_title)
    
    await query.answer()
    # 使用分页用户数据来生成菜单，确保所有页面都能正确显示按钮和用户信息
    try:
        await query.edit_message_text(
            user_list_text,
            reply_markup=user_list_menu(page_users, target_page, total_pages, list_type)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            # 如果消息未修改，只更新回复标记
            await query.answer("页面已刷新")
        else:
            raise


async def user_list_type_callback(update: Update, context: CallbackContext):
    """用户列表类型回调
    
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
    await query.edit_message_text(
        "👥 请选择用户列表类型：",
        reply_markup=user_list_type_menu()
    )

async def direct_ban_user_callback(update: Update, context: CallbackContext):
    """直接封禁/解封用户回调
    
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
    
    # 提示用户输入用户ID
    if context.user_data is not None:
        context.user_data['awaiting_user_id'] = True
    
    await query.edit_message_text(
        "🆔 请输入要封禁/解封的用户ID：",
        reply_markup=back_button("user_list_type")
    )

def _format_user_list(users, current_page, total_pages, total_users, list_type="用户"):
    """格式化用户列表文本
    
    Args:
        users: 用户列表（字典形式）
        current_page: 当前页码
        total_pages: 总页数
        total_users: 总用户数
        list_type: 列表类型
        
    Returns:
        str: 格式化后的用户列表文本
    """
    # 设置北京时区
    beijing_tz = pytz.timezone('Asia/Shanghai')
    
    text = f"👥 {list_type}列表 (第{current_page+1}/{total_pages}页)\n\n"
    text += f"📊 总{list_type}数: {total_users}\n\n"
    
    for i, user in enumerate(users, start=1):
        # 计算用户在全局列表中的序号
        global_index = current_page * 10 + i
        
        # 格式化用户名
        username = f"@{user['username']}" if user['username'] else "无用户名"
        
        # 格式化姓名
        full_name = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        if not full_name:
            full_name = "无姓名"
            
        # 格式化交互时间（使用北京时间）
        if user['last_interaction']:
            # 如果时间没有时区信息，假设为UTC并转换为北京时间
            if user['last_interaction'].tzinfo is None:
                last_interaction_utc = pytz.utc.localize(user['last_interaction'])
                last_interaction = last_interaction_utc.astimezone(beijing_tz).strftime("%Y-%m-%d %H:%M")
            else:
                last_interaction = user['last_interaction'].astimezone(beijing_tz).strftime("%Y-%m-%d %H:%M")
        else:
            last_interaction = "未知"
            
        # 格式化加入时间（使用北京时间）
        if user['first_interaction']:
            # 如果时间没有时区信息，假设为UTC并转换为北京时间
            if user['first_interaction'].tzinfo is None:
                first_interaction_utc = pytz.utc.localize(user['first_interaction'])
                first_interaction_beijing = first_interaction_utc.astimezone(beijing_tz)
                days_since_join = (datetime.now(beijing_tz) - first_interaction_beijing).days
                join_info = f"{first_interaction_beijing.strftime('%Y-%m-%d')} ({days_since_join}天前)"
            else:
                first_interaction_beijing = user['first_interaction'].astimezone(beijing_tz)
                days_since_join = (datetime.now(beijing_tz) - first_interaction_beijing).days
                join_info = f"{first_interaction_beijing.strftime('%Y-%m-%d')} ({days_since_join}天前)"
        else:
            join_info = "未知"
        
        # 用户状态信息
        bot_status = "是" if user['is_bot'] else "否"
        bot_blocked_status = "🚫 已屏蔽/删除" if user.get('bot_blocked', False) else "✅ 正常"
        ban_status = "🔒 已封禁" if user.get('is_banned', False) else "✅ 未封禁"
        
        text += (
            f"{global_index}. {username}\n"
            f"   ID: {user['user_id']}\n"
            f"   姓名: {full_name}\n"
            f"   最后交互: {last_interaction} (北京时间)\n"
            f"   加入时间: {join_info} (北京时间)\n"
            f"   机器人: {bot_status}\n"
            f"   屏蔽状态: {bot_blocked_status}\n"
            f"   封禁状态: {ban_status}\n\n"
        )
    
    return text

async def ban_user_callback(update: Update, context: CallbackContext):
    """封禁/解封用户回调函数
    
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
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    # 解析操作和用户ID
    import re
    match = re.match(r'^(ban|unban)_user_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    action = match.group(1)
    target_user_id = int(match.group(2))
    
    # 防止用户操作自己
    if user.id == target_user_id:
        await query.answer("您不能对自己执行此操作", show_alert=True)
        return
    
    await query.answer()
    
    try:
        # 执行封禁/解封操作
        if action == "ban":
            # 封禁用户
            ban_record_id = db.ban_user(target_user_id, "temporary", "管理员封禁", user.id)
            if ban_record_id is not None:
                await query.edit_message_text(
                    f"✅ 用户 {target_user_id} 已被封禁",
                    reply_markup=back_button("user_list")
                )
                
                # 尝试通知被封禁的用户
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text="🔒 您已被管理员封禁，无法继续使用本机器人功能。"
                    )
                except Exception as notify_error:
                    logger.warning(f"通知被封禁用户失败: {notify_error}")
            else:
                await query.edit_message_text(
                    "❌ 封禁用户失败，请稍后再试",
                    reply_markup=back_button("user_list")
                )
        else:
            # 解封用户
            unban_event = db.unban_user(target_user_id, user.id)
            if unban_event:
                await query.edit_message_text(
                    f"✅ 用户 {target_user_id} 已被解封",
                    reply_markup=back_button("user_list")
                )
                
                # 尝试通知被解封的用户
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text="🔓 您已被管理员解封，可以继续使用本机器人功能。"
                    )
                except Exception as notify_error:
                    logger.warning(f"通知被解封用户失败: {notify_error}")
            else:
                await query.edit_message_text(
                    "❌ 解封用户失败，请稍后再试",
                    reply_markup=back_button("user_list")
                )
                
    except Exception as e:
        logger.error(f"封禁/解封用户失败: {e}")
        await query.edit_message_text(
            "❌ 操作失败，请稍后再试",
            reply_markup=back_button("user_list")
        )

async def view_user_callback(update: Update, context: CallbackContext):
    """查看用户详情回调
    
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
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    # 解析用户ID
    match = re.match(r'^view_user_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    target_user_id = int(match.group(1))
    
    await query.answer()
    
    try:
        # 获取用户信息
        with db.session_scope() as session:
            from database import User
            target_user = session.query(User).filter_by(user_id=target_user_id).first()
            
            if not target_user:
                await query.edit_message_text(
                    "❌ 用户不存在",
                    reply_markup=back_button("user_list")
                )
                return
            
            # 检查用户是否删除或屏蔽了机器人
            bot_blocked = getattr(target_user, 'bot_blocked', False)
            if not bot_blocked:
                try:
                    is_blocked = check_user_bot_blocked(context, target_user.user_id)
                    if is_blocked:
                        # 更新数据库中的状态
                        db.update_user_bot_blocked(target_user.user_id, True)
                except Exception as e:
                    logger.error(f"检测用户 {target_user.user_id} 状态失败: {e}")
            
            # 格式化用户信息
            user_info_text = _format_user_info(target_user)
            is_banned = getattr(target_user, 'is_banned', False)
            
            await query.edit_message_text(
                user_info_text,
                reply_markup=ban_user_menu(target_user.user_id, is_banned)
            )
            
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        await query.edit_message_text(
            "❌ 获取用户信息失败，请稍后再试。",
            reply_markup=back_button("user_list")
        )


async def handle_user_id_input(update: Update, context: CallbackContext):
    """处理用户输入的ID
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    message = update.message
    if message is None:
        return
        
    user = message.from_user
    if user is None:
        return
    
    # 检查是否在等待用户ID输入状态
    if context.user_data is None or not context.user_data.get('awaiting_user_id', False):
        return
    
    # 重置等待状态
    context.user_data['awaiting_user_id'] = False
    
    try:
        # 解析用户ID
        if message.text is None:
            raise ValueError("消息文本为空")
        user_id = int(message.text.strip())
        
        # 检查用户是否存在
        with db.session_scope() as session:
            from database import User
            target_user = session.query(User).filter_by(user_id=user_id).first()
            if not target_user:
                await message.reply_text(
                    f"❌ 未找到ID为 {user_id} 的用户",
                    reply_markup=back_button("user_list_type")
                )
                return
            
            # 提取用户信息
            is_banned = getattr(target_user, 'is_banned', False)
            username = getattr(target_user, 'username', None)
            display_name = f"@{username}" if username else f"ID: {user_id}"
            
            status_text = "封禁" if not is_banned else "解封"
            
            text = f"🆔 用户信息\n\n"
            text += f"用户名: {display_name}\n"
            text += f"用户ID: {user_id}\n"
            text += f"当前状态: {'🔒 已封禁' if is_banned else '✅ 未封禁'}\n\n"
            text += f"请选择操作:"
            
            await message.reply_text(
                text,
                reply_markup=ban_user_menu(user_id, is_banned)
            )
        
    except ValueError:
        await message.reply_text(
            "❌ 请输入有效的用户ID（纯数字）",
            reply_markup=back_button("user_list_type")
        )
    except Exception as e:
        logger.error(f"处理用户ID输入失败: {e}")
        await message.reply_text(
            "❌ 处理用户ID失败，请稍后再试",
            reply_markup=back_button("user_list_type")
        )

def _format_user_info(user):
    """格式化用户信息文本
    
    Args:
        user: 用户对象
        
    Returns:
        str: 格式化后的用户信息文本
    """
    # 设置北京时区
    beijing_tz = pytz.timezone('Asia/Shanghai')
    
    # 格式化用户名
    username = f"@{getattr(user, 'username', None)}" if getattr(user, 'username', None) else "无用户名"
    
    # 格式化姓名
    first_name = getattr(user, 'first_name', None) or ''
    last_name = getattr(user, 'last_name', None) or ''
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        full_name = "无姓名"
        
    # 格式化交互时间（使用北京时间）
    last_interaction = getattr(user, 'last_interaction', None)
    if last_interaction:
        # 如果时间没有时区信息，假设为UTC并转换为北京时间
        if last_interaction.tzinfo is None:
            last_interaction_utc = pytz.utc.localize(last_interaction)
            last_interaction = last_interaction_utc.astimezone(beijing_tz).strftime("%Y-%m-%d %H:%M")
        else:
            last_interaction = last_interaction.astimezone(beijing_tz).strftime("%Y-%m-%d %H:%M")
    else:
        last_interaction = "未知"
        
    # 格式化加入时间（使用北京时间）
    first_interaction = getattr(user, 'first_interaction', None)
    if first_interaction:
        # 如果时间没有时区信息，假设为UTC并转换为北京时间
        if first_interaction.tzinfo is None:
            first_interaction_utc = pytz.utc.localize(first_interaction)
            first_interaction_beijing = first_interaction_utc.astimezone(beijing_tz)
            days_since_join = (datetime.now(beijing_tz) - first_interaction_beijing).days
            join_info = f"{first_interaction_beijing.strftime('%Y-%m-%d')} ({days_since_join}天前)"
        else:
            first_interaction_beijing = first_interaction.astimezone(beijing_tz)
            days_since_join = (datetime.now(beijing_tz) - first_interaction_beijing).days
            join_info = f"{first_interaction_beijing.strftime('%Y-%m-%d')} ({days_since_join}天前)"
    else:
        join_info = "未知"
    
    # 用户状态信息
    is_bot = getattr(user, 'is_bot', False)
    bot_status = "是" if is_bot else "否"
    bot_blocked_status = "🚫 已屏蔽/删除" if getattr(user, 'bot_blocked', False) else "✅ 正常"
    ban_status = "🚫 已封禁" if getattr(user, 'is_banned', False) else "✅ 未封禁"
    
    text = (
        f"👤 用户详情\n\n"
        f"用户名: {username}\n"
        f"ID: {getattr(user, 'user_id', 'Unknown')}\n"
        f"姓名: {full_name}\n"
        f"机器人: {bot_status}\n"
        f"最后交互: {last_interaction} (北京时间)\n"
        f"加入时间: {join_info} (北京时间)\n"
        f"屏蔽状态: {bot_blocked_status}\n"
        f"封禁状态: {ban_status}\n"
    )
    
    return text

async def reviewer_list_callback(update: Update, context: CallbackContext):
    """审核员列表回调
    
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
        with db.session_scope() as session:
            from database import ReviewerApplication, User
            # 获取所有已批准的审核员申请
            reviewers = session.query(ReviewerApplication).filter_by(status='approved').all()
            
            if not reviewers:
                await query.edit_message_text(
                    "📋 审核员列表\n\n暂无审核员",
                    reply_markup=back_button("reviewer_management")
                )
                return
            
            # 计算分页信息
            total_reviewers = len(reviewers)
            reviewers_per_page = 10
            total_pages = (total_reviewers + reviewers_per_page - 1) // reviewers_per_page
            
            # 默认显示第一页
            current_page = 0
            start_idx = current_page * reviewers_per_page
            end_idx = min(start_idx + reviewers_per_page, total_reviewers)
            page_reviewers = reviewers[start_idx:end_idx]
            
            # 保存分页信息到context
            if context.user_data is not None:
                context.user_data['reviewer_list'] = reviewers
                context.user_data['reviewer_list_current_page'] = current_page
                context.user_data['reviewer_list_total_pages'] = total_pages
            
            # 构建审核员列表
            reviewer_list_text = "📋 审核员列表:\n\n"
            keyboard = []
            
            for reviewer in page_reviewers:
                # 获取用户信息
                user_info = session.query(User).filter_by(user_id=reviewer.user_id).first()
                if user_info:
                    name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                    username = f"@{getattr(user_info, 'username')}" if getattr(user_info, 'username') else "无用户名"
                    reviewer_list_text += f"• {name} ({username}) - ID: {reviewer.user_id}\n"
                    # 添加设置权限按钮
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{name} (@{getattr(user_info, 'username')})" if getattr(user_info, 'username') else name,
                            callback_data=f"view_user_{reviewer.user_id}"
                        ),
                        InlineKeyboardButton(
                            "⚙️ 权限", 
                            callback_data=f"set_perm_{reviewer.user_id}"
                        )
                    ])
            
            # 添加分页按钮
            if total_pages > 1:
                page_buttons = []
                if current_page > 0:
                    page_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"reviewer_list_page_{current_page-1}"))
                
                page_buttons.append(InlineKeyboardButton(f"{current_page+1}/{total_pages}", callback_data="noop"))
                
                if current_page < total_pages - 1:
                    page_buttons.append(InlineKeyboardButton("➡️", callback_data=f"reviewer_list_page_{current_page+1}"))
                
                keyboard.append(page_buttons)
            
            keyboard.append([InlineKeyboardButton("🔙 返回", callback_data="reviewer_management")])
            
            await query.edit_message_text(
                reviewer_list_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"获取审核员列表失败: {e}")
        await query.edit_message_text(
            "❌ 获取审核员列表失败，请稍后再试",
            reply_markup=back_button("reviewer_management")
        )


async def set_reviewer_permissions_callback(update: Update, context: CallbackContext):
    """设置审核员权限回调
    
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
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    # 解析用户ID
    import re
    match = re.match(r'^set_perm_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    target_user_id = int(match.group(1))
    
    await query.answer()
    
    try:
        with db.session_scope() as session:
            from database import ReviewerApplication, User
            # 获取审核员信息
            reviewer = session.query(ReviewerApplication).filter_by(user_id=target_user_id, status='approved').first()
            user_info = session.query(User).filter_by(user_id=target_user_id).first()
            
            if not reviewer or not user_info:
                await query.edit_message_text(
                    "❌ 审核员不存在",
                    reply_markup=back_button("reviewer_list")
                )
                return
            
            # 获取当前权限
            try:
                permissions = json.loads(getattr(reviewer, 'permissions', '') or '{}')
            except:
                permissions = {}
            
            # 构建权限显示文本
            name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
            username = f"@{getattr(user_info, 'username')}" if getattr(user_info, 'username') else "无用户名"
            
            perms_text = f"⚙️ 设置审核员权限\n\n用户: {name} ({username})\nID: {target_user_id}\n\n"
            
            # 权限选项
            perms_text += "权限列表:\n"
            perm_options = {
                'can_review': '审核投稿',
                'can_history': '查看历史',
                'can_stats': '查看统计',
                'can_users': '管理用户'
            }
            
            keyboard = []
            for perm_key, perm_name in perm_options.items():
                is_enabled = permissions.get(perm_key, True)
                status_text = "✅ 启用" if is_enabled else "❌ 禁用"
                perms_text += f"• {perm_name}: {status_text}\n"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{perm_name}: {status_text}", 
                        callback_data=f"toggle_perm_{perm_key}_{target_user_id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 返回审核员列表", callback_data="reviewer_list")])
            
            await query.edit_message_text(
                perms_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"设置审核员权限失败: {e}")
        await query.edit_message_text(
            "❌ 设置审核员权限失败，请稍后再试",
            reply_markup=back_button("reviewer_list")
        )


async def toggle_reviewer_permission_callback(update: Update, context: CallbackContext):
    """切换审核员权限回调
    
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
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    # 解析权限键和用户ID
    import re
    match = re.match(r'^toggle_perm_(\w+)_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    perm_key = match.group(1)
    target_user_id = int(match.group(2))
    
    await query.answer()
    
    try:
        with db.session_scope() as session:
            from database import ReviewerApplication
            # 获取审核员信息
            reviewer = session.query(ReviewerApplication).filter_by(user_id=target_user_id, status='approved').first()
            
            if not reviewer:
                await query.edit_message_text(
                    "❌ 审核员不存在",
                    reply_markup=back_button("reviewer_list")
                )
                return
            
            # 获取当前权限并切换
            try:
                permissions = json.loads(getattr(reviewer, 'permissions', '') or '{}')
            except:
                permissions = {}
            
            # 切换权限
            permissions[perm_key] = not permissions.get(perm_key, True)
            
            # 更新权限
            setattr(reviewer, 'permissions', json.dumps(permissions))
            session.commit()
            
            # 重新显示权限设置界面
            # 重新构造回调数据以调用设置权限函数
            new_query = update.callback_query
            if new_query is not None:
                new_query.data = f"set_perm_{target_user_id}"
                await set_reviewer_permissions_callback(update, context)
            
    except Exception as e:
        logger.error(f"切换审核员权限失败: {e}")
        await query.edit_message_text(
            "❌ 切换审核员权限失败，请稍后再试",
            reply_markup=back_button("reviewer_list")
        )


# 导出所有回调函数
__all__ = [
    'user_list_callback',
    'all_user_list_callback',
    'normal_user_list_callback',
    'blocked_user_list_callback',
    'banned_user_list_callback',
    'handle_user_list_page',
    'view_user_callback',
    'ban_user_callback',
    'reviewer_list_callback',
    'user_list_type_callback',  # 添加新函数到导出列表
    'direct_ban_user_callback',  # 添加新函数到导出列表
    'handle_user_id_input',  # 添加新函数到导出列表
    'set_reviewer_permissions_callback',  # 添加新函数到导出列表
    'toggle_reviewer_permission_callback'  # 添加新函数到导出列表
]
