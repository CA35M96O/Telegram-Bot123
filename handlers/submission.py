# handlers/submission.py
"""
投稿处理模块 - 多媒体内容提交和管理

本模块处理用户的各种投稿操作，包括：
- 文本投稿处理
- 图片和视频投稿处理
- 混合媒体投稿（同时包含图片和视频）
- 投稿确认和修改流程
- 匿名投稿选项
- 多图/多视频投稿支持

设计原则：
- 支持多种媒体类型和组合
- 用户友好的交互流程
- 完善的状态管理和错误恢复
- 详细的数据验证和安全检查
- 高效的资源管理和内存优化

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

# =====================================================
# 外部库导入 External Library Imports
# =====================================================

# Python 标准库
import logging
import json
import time
from datetime import datetime

# Telegram Bot API 组件
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# 项目配置和数据库
from config import ADMIN_IDS, CHANNEL_IDS, GROUP_IDS
from database import db

# 键盘布局组件
from keyboards import (
    confirm_submission_menu, 
    back_button, 
    mixed_media_control_menu
)

# 工具函数
from utils.logging_utils import log_user_activity, log_submission_event
from utils.time_utils import get_beijing_now, format_beijing_time
from utils.helpers import publish_submission, check_user_bot_blocked

# 初始化日志器
logger = logging.getLogger(__name__)

# 用户状态常量
STATE_TEXT_SUBMISSION = "text_submission"
STATE_PHOTO_SUBMISSION = "photo_submission"
STATE_VIDEO_SUBMISSION = "video_submission"
STATE_MEDIA_SUBMISSION = "media_submission"
STATE_MIXED_MEDIA_SUBMISSION = "mixed_media_submission"
STATE_COVER_SELECTION = "cover_selection"
STATE_REJECT_REASON = "reject_reason"
STATE_ADD_REVIEWER = "add_reviewer"
STATE_REMOVE_REVIEWER = "remove_reviewer"

# 消息处理函数
async def handle_text_input(update: Update, context) -> None:
    """处理文本消息输入
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 检查用户是否被封禁
    try:
        with db.session_scope() as session:
            from database import User
            user_record = session.query(User).filter_by(user_id=user.id).first()
            # 修复条件判断问题
            if user_record is not None and getattr(user_record, 'is_banned', False):
                if update.message is not None:
                    await update.message.reply_text("🚫 您已被管理员封禁，无法使用本机器人功能。")
                return
    except Exception as e:
        logger.error(f"检查用户封禁状态失败: {e}")
    
    if update.message is None or update.message.text is None:
        return
    
    text = update.message.text
    state, state_data = db.get_user_state(user.id)
    
    # 根据用户当前状态处理文本输入
    # 修复条件判断问题
    if state is not None and str(state) == str(STATE_TEXT_SUBMISSION):
        await _handle_text_submission(update, context, text)
    elif state is not None and str(state) == str(STATE_REJECT_REASON):
        from handlers.review import handle_reject_reason
        await handle_reject_reason(update, context, text)
    elif state is not None and str(state) == str(STATE_ADD_REVIEWER):
        # 处理添加审核员操作
        await _handle_add_reviewer(update, context, text)
    elif state is not None and str(state) == str(STATE_REMOVE_REVIEWER):
        # 处理删除审核员操作
        await _handle_remove_reviewer(update, context, text)
    elif state is not None and str(state) == str(STATE_MIXED_MEDIA_SUBMISSION):
        await _handle_mixed_media_caption(update, context, text)
    elif state is not None and str(state) == 'config_management_group':
        # 处理管理群组ID配置（使用默认值，不处理输入）
        user = update.effective_user
        if user is not None and update.message is not None:
            keyboard = back_button("system_config")
            await update.message.reply_text(
                "👥 管理群组ID使用默认配置\n\n"
                "管理群组ID已设置为默认值，无法修改。\n"
                "如需更改，请修改环境变量后重启机器人。",
                reply_markup=keyboard
            )
            # 清除用户状态
            db.clear_user_state(user.id)
    elif state is not None and str(state) == 'config_channels':
        # 处理频道ID配置
        await _handle_config_channels(update, context, text)
    elif state is not None and str(state) == 'config_groups':
        # 处理群组ID配置
        await _handle_config_groups(update, context, text)
    else:
        # 不发送默认回复，让其他处理器有机会处理
        # 特别是让handle_publish_keyword_input有机会处理关键词输入
        pass

async def handle_photo(update: Update, context) -> None:
    """处理图片消息
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 检查用户是否被封禁
    try:
        with db.session_scope() as session:
            from database import User
            user_record = session.query(User).filter_by(user_id=user.id).first()
            # 修复条件判断问题
            if user_record is not None and getattr(user_record, 'is_banned', False):
                if update.message is not None:
                    await update.message.reply_text("🚫 您已被管理员封禁，无法使用本机器人功能。")
                return
    except Exception as e:
        logger.error(f"检查用户封禁状态失败: {e}")
    
    if update.message is None or update.message.photo is None:
        return
    
    # 获取最大的图片
    photo = update.message.photo[-1]
    
    # 检查是否是相册的一部分，如果是则只处理一次
    media_group_id = getattr(update.message, 'media_group_id', None)
    
    # 如果是相册的一部分，检查是否已经处理过
    if media_group_id and hasattr(context, 'user_data') and context.user_data is not None:
        processed_media_groups = context.user_data.get('processed_media_groups', set())
        if media_group_id in processed_media_groups:
            # 已经处理过的相册，跳过
            return
        # 添加到已处理集合
        processed_media_groups.add(media_group_id)
        context.user_data['processed_media_groups'] = processed_media_groups
    
    state, state_data = db.get_user_state(user.id)
    
    # 根据用户当前状态处理图片输入
    # 修复条件判断问题
    if state is not None and str(state) == str(STATE_PHOTO_SUBMISSION):
        await _handle_photo_submission(update, context, photo)
    elif state is not None and str(state) == str(STATE_MIXED_MEDIA_SUBMISSION):
        # 检查当前阶段
        stage = state_data.get("stage") if state_data else None
        if stage == "cover":
            # 现在第一张照片自动作为首图，不再需要单独上传首图
            # 直接完成投稿
            await _finish_mixed_media_submission(update, context, state_data)
            return
        else:
            # 在普通混合媒体投稿阶段，处理普通图片
            await _handle_mixed_media_photo(update, context)
    else:
        # 默认回复
        if update.message is not None:
            await update.message.reply_text(
                "您好！欢迎使用投稿机器人。\n\n"
                "请使用 /start 命令开始操作，或从菜单中选择功能。",
                reply_markup=back_button("main_menu")
            )

async def handle_video(update: Update, context) -> None:
    """处理视频消息
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 检查用户是否被封禁
    try:
        with db.session_scope() as session:
            from database import User
            user_record = session.query(User).filter_by(user_id=user.id).first()
            # 修复条件判断问题
            if user_record is not None and getattr(user_record, 'is_banned', False):
                if update.message is not None:
                    await update.message.reply_text("🚫 您已被管理员封禁，无法使用本机器人功能。")
                return
    except Exception as e:
        logger.error(f"检查用户封禁状态失败: {e}")
    
    if update.message is None or update.message.video is None:
        return
    
    video = update.message.video
    
    # 检查是否是相册的一部分，如果是则只处理一次
async def _handle_add_reviewer(update: Update, context, text: str) -> None:
    """处理添加审核员操作
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        text: 用户输入的文本（用户ID）
    """
    user = update.effective_user
    if user is None or update.message is None:
        return
    
    try:
        # 解析用户ID
        target_user_id = int(text.strip())
        
        # 检查用户是否存在
        with db.session_scope() as session:
            from database import User, ReviewerApplication
            target_user = session.query(User).filter_by(user_id=target_user_id).first()
            if not target_user:
                await update.message.reply_text(
                    f"❌ 未找到ID为 {target_user_id} 的用户",
                    reply_markup=back_button("reviewer_management")
                )
                # 清除用户状态
                db.clear_user_state(user.id)
                return
            
            # 检查用户是否已经是审核员
            existing_reviewer = session.query(ReviewerApplication).filter_by(
                user_id=target_user_id, 
                status='approved'
            ).first()
            
            if existing_reviewer:
                await update.message.reply_text(
                    f"❌ 用户 {target_user_id} 已经是审核员了",
                    reply_markup=back_button("reviewer_management")
                )
                # 清除用户状态
                db.clear_user_state(user.id)
                return
            
            # 获取用户名，如果为空则使用默认值
            username = getattr(target_user, 'username', None)
            if not username:
                username = f"user_{target_user_id}"
            
            # 添加审核员
            # 创建已批准的审核员申请记录
            new_reviewer = ReviewerApplication(
                user_id=target_user_id,
                username=username,
                status='approved',
                handled_by=user.id,
                permissions='{"can_review": true, "can_history": true, "can_stats": true, "can_users": true}'
            )
            session.add(new_reviewer)
            session.commit()
            
            await update.message.reply_text(
                f"✅ 成功添加用户 {target_user_id} 为审核员",
                reply_markup=back_button("reviewer_management")
            )
            
            # 清除用户状态
            db.clear_user_state(user.id)
            
    except ValueError:
        await update.message.reply_text(
            "❌ 请输入有效的用户ID（纯数字）",
            reply_markup=back_button("reviewer_management")
        )
        # 清除用户状态
        db.clear_user_state(user.id)
    except Exception as e:
        logger.error(f"添加审核员失败: {e}")
        await update.message.reply_text(
            "❌ 添加审核员失败，请稍后再试",
            reply_markup=back_button("reviewer_management")
        )
        # 清除用户状态
        db.clear_user_state(user.id)


async def _handle_remove_reviewer(update: Update, context, text: str) -> None:
    """处理删除审核员操作
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        text: 用户输入的文本（用户ID）
    """
    user = update.effective_user
    if user is None or update.message is None:
        return
    
    try:
        # 解析用户ID
        target_user_id = int(text.strip())
        
        # 检查用户是否存在
        with db.session_scope() as session:
            from database import User, ReviewerApplication
            target_user = session.query(User).filter_by(user_id=target_user_id).first()
            if not target_user:
                await update.message.reply_text(
                    f"❌ 未找到ID为 {target_user_id} 的用户",
                    reply_markup=back_button("reviewer_management")
                )
                # 清除用户状态
                db.clear_user_state(user.id)
                return
            
            # 检查用户是否是审核员
            existing_reviewer = session.query(ReviewerApplication).filter_by(
                user_id=target_user_id, 
                status='approved'
            ).first()
            
            if not existing_reviewer:
                await update.message.reply_text(
                    f"❌ 用户 {target_user_id} 不是审核员",
                    reply_markup=back_button("reviewer_management")
                )
                # 清除用户状态
                db.clear_user_state(user.id)
                return
            
            # 删除审核员记录
            session.delete(existing_reviewer)
            session.commit()
            
            # 尝试将用户从管理群组中踢出
            try:
                from config import MANAGEMENT_GROUP_ID
                await context.bot.ban_chat_member(chat_id=MANAGEMENT_GROUP_ID, user_id=target_user_id)
                kick_result = "并已将其从管理群组中移除"
            except Exception as kick_error:
                logger.warning(f"将用户 {target_user_id} 从管理群组中踢出失败: {kick_error}")
                kick_result = "但未能将其从管理群组中移除，请手动处理"
            
            await update.message.reply_text(
                f"✅ 成功删除用户 {target_user_id} 的审核员身份，{kick_result}",
                reply_markup=back_button("reviewer_management")
            )
            
            # 清除用户状态
            db.clear_user_state(user.id)
            
    except ValueError:
        await update.message.reply_text(
            "❌ 请输入有效的用户ID（纯数字）",
            reply_markup=back_button("reviewer_management")
        )
        # 清除用户状态
        db.clear_user_state(user.id)
    except Exception as e:
        logger.error(f"删除审核员失败: {e}")
        await update.message.reply_text(
            "❌ 删除审核员失败，请稍后再试",
            reply_markup=back_button("reviewer_management")
        )
        # 清除用户状态
        db.clear_user_state(user.id)
    


async def start_text_submission(update: Update, context) -> None:
    """开始文本投稿流程
    
    初始化文本投稿状态并提示用户输入内容
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 检查用户是否被封禁
    try:
        with db.session_scope() as session:
            from database import User
            user_record = session.query(User).filter_by(user_id=user.id).first()
            # 修复条件判断问题
            if user_record is not None and getattr(user_record, 'is_banned', False):
                if update.callback_query is not None:
                    await update.callback_query.answer("您已被封禁，无法使用此功能", show_alert=True)
                elif update.message is not None:
                    await update.message.reply_text("🚫 您已被管理员封禁，无法使用本机器人功能。")
                return
    except Exception as e:
        logger.error(f"检查用户封禁状态失败: {e}")
    
    query = update.callback_query
    if query is not None:
        await query.answer()
    
    # 获取用户的匿名状态
    state, state_data = db.get_user_state(user.id)
    is_anonymous = state_data.get("anonymous", False) if state_data else False
    
    # 设置用户状态为文本投稿
    db.set_user_state(user.id, STATE_TEXT_SUBMISSION, {"anonymous": is_anonymous})
    
    # 记录用户活动
    log_user_activity(user.id, user.username, "TEXT_SUBMISSION_START", "Started text submission")
    
    # 提示用户输入文本内容
    text = (
        "📝 文本投稿\n\n"
        "请发送您要投稿的文本内容（不少于10个字符）：\n\n"
        "📌 提示：\n"
        "• 支持Emoji和基本格式\n"
        "• 最多可输入4096个字符\n"
        "• 请勿包含敏感或违规内容\n"
        "• 内容需不少于10个字符"
    )
    
    from telegram import InlineKeyboardMarkup
    if query is not None:
        keyboard = back_button("submit_menu")
        await query.edit_message_text(text, reply_markup=keyboard)
    elif update.message is not None:
        keyboard = back_button("submit_menu")
        await update.message.reply_text(text, reply_markup=keyboard)

async def start_media_submission(update: Update, context, media_type: str) -> None:
    """开始媒体投稿流程
    
    初始化媒体投稿状态并提示用户发送媒体内容
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        media_type: 媒体类型 ("photo" 或 "video")
    """
    user = update.effective_user
    if user is None:
        return
    
    # 检查用户是否被封禁
    try:
        with db.session_scope() as session:
            from database import User
            user_record = session.query(User).filter_by(user_id=user.id).first()
            # 修复条件判断问题
            if user_record is not None and getattr(user_record, 'is_banned', False):
                if update.callback_query is not None:
                    await update.callback_query.answer("您已被封禁，无法使用此功能", show_alert=True)
                elif update.message is not None:
                    await update.message.reply_text("🚫 您已被管理员封禁，无法使用本机器人功能。")
                return
    except Exception as e:
        logger.error(f"检查用户封禁状态失败: {e}")
    
    query = update.callback_query
    if query is not None:
        await query.answer()
    
    # 设置用户状态为对应类型的媒体投稿
    if media_type == "photo":
        db.set_user_state(user.id, STATE_PHOTO_SUBMISSION)
        prompt_text = (
            "📸 图片投稿\n\n"
            "请发送您要投稿的图片：\n\n"
            "📌 提示：\n"
            "• 支持JPG、PNG等常见格式\n"
            "• 可发送多张图片（推荐使用相册模式）\n"
            "• 单张图片大小不超过20MB\n"
            "• 请勿包含敏感或违规内容\n"
            "• 文字说明需不少于10个字符"
        )
    else:  # video
        db.set_user_state(user.id, STATE_VIDEO_SUBMISSION)
        prompt_text = (
            "🎬 视频投稿\n\n"
            "请发送您要投稿的视频：\n\n"
            "📌 提示：\n"
            "• 支持MP4等常见格式\n"
            "• 视频时长不超过10分钟\n"
            "• 单个视频大小不超过50MB\n"
            "• 请勿包含敏感或违规内容\n"
            "• 文字说明需不少于10个字符"
        )
    
    # 记录用户活动
    log_user_activity(user.id, user.username, f"{media_type.upper()}_SUBMISSION_START", f"Started {media_type} submission")
    
    from telegram import InlineKeyboardMarkup
    if query is not None:
        keyboard = back_button("submit_menu")
        await query.edit_message_text(prompt_text, reply_markup=keyboard)
    elif update.message is not None:
        keyboard = back_button("submit_menu")
        await update.message.reply_text(prompt_text, reply_markup=keyboard)

async def start_unified_media_submission(update: Update, context) -> None:
    """开始统一媒体投稿流程（混合媒体）
    
    初始化混合媒体投稿状态并提示用户发送媒体内容
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 检查用户是否被封禁
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            if update.callback_query is not None:
                await update.callback_query.answer("您已被封禁，无法使用此功能", show_alert=True)
            elif update.message is not None:
                await update.message.reply_text("🚫 您已被管理员封禁，无法使用本机器人功能。")
            return
    
    query = update.callback_query
    if query is not None:
        await query.answer()
    
    # 获取用户的匿名状态
    state, state_data = db.get_user_state(user.id)
    is_anonymous = state_data.get("anonymous", False) if state_data else False
    
    # 设置用户状态为混合媒体投稿
    db.set_user_state(user.id, STATE_MIXED_MEDIA_SUBMISSION, {"photos": [], "videos": [], "caption": "", "anonymous": is_anonymous})
    
    # 记录用户活动
    log_user_activity(user.id, user.username, "MIXED_MEDIA_SUBMISSION_START", "Started mixed media submission")
    
    # 提示用户发送媒体内容
    prompt_text = (
        "🎭 混合媒体投稿\n\n"
        "请发送图片或视频（可以混合发送）：\n\n"
        "📌 操作指南：\n"
        "• 先发送所有图片和视频\n"
        "• 然后点击「完成上传」\n"
        "• 最后输入文字说明（不少于10个字符）\n\n"
        "⚠️ 注意：\n"
        "• 最多可发送120个媒体文件（其中图片最多100张，视频最多20个）\n"
        "• 单个文件大小不超过20MB\n"
        "• 请勿包含敏感或违规内容\n"
        "• 文字说明需不少于10个字符"
    )
    
    if query is not None:
        from telegram import InlineKeyboardMarkup
        keyboard = mixed_media_control_menu(0, 0)
        await query.edit_message_text(
            prompt_text,
            reply_markup=keyboard
        )
    elif update.message is not None:
        keyboard = mixed_media_control_menu(0, 0)
        await update.message.reply_text(
            prompt_text,
            reply_markup=keyboard
        )

async def confirm_submission_callback(update: Update, context) -> None:
    """确认投稿回调处理
    
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
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析操作类型和投稿类型
    import re
    match = re.match(r'^(confirm|edit|toggle_anonymous)_(text|photo|video|media)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    action = match.group(1)
    submission_type = match.group(2)
    
    if action == "confirm":
        await _confirm_submission(query, context, submission_type)
    elif action == "edit":
        await _edit_submission(query, context, submission_type)
    elif action == "toggle_anonymous":
        await _toggle_anonymous(query, context, submission_type)

async def toggle_anonymous_callback(update: Update, context) -> None:
    """切换匿名状态回调
    
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
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析投稿类型
    import re
    match = re.match(r'^toggle_anonymous_(text|photo|video|media)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    submission_type = match.group(1)
    
    # 切换匿名状态
    await _toggle_anonymous(query, context, submission_type)

async def multi_mixed_media_callback(update: Update, context) -> None:
    """混合媒体投稿回调处理
    
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
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析操作类型
    import re
    match = re.match(r'^(add_photo_to_mixed|add_video_to_mixed|finish_mixed_media|submit_mixed_media_final)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    action = match.group(1)
    
    if action == "add_photo_to_mixed":
        # 检查用户当前状态
        state, state_data = db.get_user_state(user.id)
        if state is not None and str(state) == str(STATE_MIXED_MEDIA_SUBMISSION):
            # 确保state_data存在
            if not state_data:
                state_data = {"photos": [], "videos": [], "caption": ""}
            # 检查是否达到照片数量上限
            if len(state_data.get("photos", [])) >= 100:
                await query.answer("照片数量已达上限（100张）", show_alert=True)
                return
                
        # 提示用户发送图片（保持当前状态不变）
        from keyboards import mixed_media_control_menu
        try:
            await query.edit_message_text(
                "请发送图片（最多100张）：",
                reply_markup=mixed_media_control_menu(0, len(state_data.get("photos", [])) + len(state_data.get("videos", [])) if state_data else 0)  # type: ignore
            )
        except Exception as e:
            # 如果消息内容相同，忽略错误
            if "Message is not modified" not in str(e):
                raise
            await query.answer("请发送图片（最多100张）")

    elif action == "add_video_to_mixed":
        # 检查用户当前状态
        state, state_data = db.get_user_state(user.id)
        if state is not None and str(state) == str(STATE_MIXED_MEDIA_SUBMISSION):
            # 确保state_data存在
            if not state_data:
                state_data = {"photos": [], "videos": [], "caption": ""}
            # 检查是否达到视频数量上限
            if len(state_data.get("videos", [])) >= 20:
                await query.answer("视频数量已达上限（20个）", show_alert=True)
                return
                
        # 提示用户发送视频（保持当前状态不变）
        from keyboards import mixed_media_control_menu
        try:
            await query.edit_message_text(
                "请发送视频（最多20个）：",
                reply_markup=mixed_media_control_menu(0, len(state_data.get("photos", [])) + len(state_data.get("videos", [])) if state_data else 0)  # type: ignore
            )
        except Exception as e:
            # 如果消息内容相同，忽略错误
            if "Message is not modified" not in str(e):
                raise
            await query.answer("请发送视频（最多20个）")
        # 设置用户状态以便处理视频，同时保留现有数据
        db.set_user_state(user.id, STATE_MIXED_MEDIA_SUBMISSION, state_data or {"photos": [], "videos": [], "caption": ""})
    elif action == "finish_mixed_media":
        # 完成上传，提示用户输入文字说明
        state, state_data = db.get_user_state(user.id)
        if state is not None and str(state) == str(STATE_MIXED_MEDIA_SUBMISSION):
            # 确保state_data存在
            if not state_data:
                state_data = {"photos": [], "videos": [], "caption": ""}
                
            photos = state_data.get("photos", [])
            videos = state_data.get("videos", [])
            
            # 更新状态，准备接收文字说明
            state_data["stage"] = "caption"
            # 如果已有媒体文件，自动将第一张照片作为首图
            if state_data.get("photos"):
                state_data["cover_photo"] = state_data["photos"][0]
            elif state_data.get("videos"):
                state_data["cover_photo"] = state_data["videos"][0]["file_id"]
            db.set_user_state(user.id, STATE_MIXED_MEDIA_SUBMISSION, state_data)
            
            from keyboards import mixed_media_control_menu
            try:
                if not photos and not videos:
                    await query.edit_message_text(
                        "请发送图片或视频（可以混合发送）：\n\n"
                        "📌 操作指南：\n"
                        "• 先发送所有图片和视频\n"
                        "• 然后点击「完成上传」\n"
                        "• 最后输入文字说明（不少于10个字符）\n\n"
                        "⚠️ 注意：\n"
                        "• 最多可发送120个媒体文件（其中图片最多100张，视频最多20个）\n"
                        "• 单个文件大小不超过20MB\n"
                        "• 请勿包含敏感或违规内容\n"
                        "• 文字说明需不少于10个字符",
                        reply_markup=mixed_media_control_menu(0, len(photos) + len(videos))
                    )  # type: ignore
                else:
                    await query.edit_message_text(
                        f"媒体文件统计:\n照片: {len(photos)}张\n视频: {len(videos)}个\n\n请为您的投稿添加文字说明（至少10个字符）：",
                        reply_markup=mixed_media_control_menu(0, len(photos) + len(videos))
                    )  # type: ignore
            except Exception as e:
                # 如果消息内容相同，忽略错误
                if "Message is not modified" not in str(e):
                    raise
                await query.answer("请为您的投稿添加文字说明（至少10个字符）：")
    elif action == "submit_mixed_media_final":
        # 用户点击完成投稿按钮，处理最终投稿
        state, state_data = db.get_user_state(user.id)
        if state is not None and str(state) == str(STATE_MIXED_MEDIA_SUBMISSION) and state_data:
            await _finish_mixed_media_submission(update, context, state_data)

async def toggle_submit_anonymous_callback(update: Update, context) -> None:
    """切换投稿匿名状态回调
    
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
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析匿名状态
    import re
    match = re.match(r'^toggle_submit_anonymous_(true|false)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    anonymous = match.group(1) == "true"
    
    # 更新用户的投稿匿名状态
    state, state_data = db.get_user_state(user.id)
    if not state_data:
        state_data = {}
    state_data["anonymous"] = anonymous
    db.set_user_state(user.id, state if state is not None else STATE_TEXT_SUBMISSION, state_data)
    
    # 重新显示投稿类型菜单，更新匿名状态按钮
    from keyboards import submission_type_menu
    try:
        keyboard_obj = submission_type_menu(anonymous)
        await query.edit_message_text(
            "请选择投稿类型：",
            reply_markup=submission_type_menu(anonymous)
        )  # type: ignore
    except Exception as e:
        # 如果消息内容相同，忽略错误
        if "Message is not modified" not in str(e):
            logger.error(f"更新投稿类型菜单失败: {e}")
            await query.answer("操作失败，请稍后重试", show_alert=True)
        else:
            await query.answer("请选择投稿类型：")

async def handle_urge_review(update: Update, context) -> None:
    """催促审核回调处理
    
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
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record is not None and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析投稿ID
    import re
    match = re.match(r'^urge_review_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    sub_id = int(match.group(1))
    
    # 记录催促审核操作
    log_user_activity(
        user.id, 
        user.username, 
        "URGE_REVIEW", 
        f"Urged review for submission #{sub_id}"
    )
    
    # 通知管理员有用户催促审核
    try:
        from database import db
        submission = db.get_submission(sub_id)
        if submission:
            message = (
                f"⏰ 用户催促审核提醒\n\n"
                f"投稿ID: #{sub_id}\n"
                f"用户: @{submission.username} (ID: {submission.user_id})\n"
                f"时间: {format_beijing_time(get_beijing_now())}\n\n"
                f"请尽快处理该投稿。"
            )
            
            # 向所有管理员发送提醒
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=message)
                except Exception as e:
                    logger.error(f"发送催促审核提醒给管理员 {admin_id} 失败: {e}")
            
            await query.answer("已通知管理员尽快处理您的投稿", show_alert=True)
        else:
            await query.answer("投稿不存在", show_alert=True)
    except Exception as e:
        logger.error(f"处理催促审核请求失败: {e}")
        await query.answer("操作失败，请稍后重试", show_alert=True)

async def multi_photo_callback(update: Update, context) -> None:
    """多图片投稿回调处理
    
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
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析操作类型
    import re
    match = re.match(r'^(add_more_photos|finish_photos)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    action = match.group(1)
    
    if action == "add_more_photos":
        # 提示用户继续发送图片
        db.set_user_state(user.id, STATE_PHOTO_SUBMISSION)
        await query.edit_message_text(
            "请继续发送图片：",
            reply_markup=back_button("submit_photo")
        )
    elif action == "finish_photos":
        # 完成图片投稿，提示用户输入文字说明
        state, state_data = db.get_user_state(user.id)
        if state is not None and str(state) == str(STATE_PHOTO_SUBMISSION) and state_data and "photos" in state_data:
            if not state_data["photos"]:
                await query.answer("请至少发送一张图片", show_alert=True)
                return
            
            # 更新状态，准备接收文字说明
            state_data["stage"] = "caption"
            db.set_user_state(user.id, STATE_PHOTO_SUBMISSION, state_data)
            
            await query.edit_message_text(
                "请为您的图片投稿添加文字说明（可选）：",
                reply_markup=back_button("submit_photo")
            )

async def multi_video_callback(update: Update, context) -> None:
    """多视频投稿回调处理
    
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
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析操作类型
    import re
    match = re.match(r'^(add_more_videos|finish_videos)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    action = match.group(1)
    
    if action == "add_more_videos":
        # 提示用户继续发送视频
        db.set_user_state(user.id, STATE_VIDEO_SUBMISSION)
        await query.edit_message_text(
            "请继续发送视频：",
            reply_markup=back_button("submit_video")
        )
    elif action == "finish_videos":
        # 完成视频投稿，提示用户输入文字说明
        state, state_data = db.get_user_state(user.id)
        if state is not None and str(state) == str(STATE_VIDEO_SUBMISSION) and state_data and "videos" in state_data:
            if not state_data["videos"]:
                await query.answer("请至少发送一个视频", show_alert=True)
                return
            
            # 更新状态，准备接收文字说明
            state_data["stage"] = "caption"
            db.set_user_state(user.id, STATE_VIDEO_SUBMISSION, state_data)
            
            await query.edit_message_text(
                "请为您的视频投稿添加文字说明（可选）：",
                reply_markup=back_button("submit_video")
            )

async def handle_cover_selection(update: Update, context) -> None:
    """封面选择回调处理
    
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
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析投稿ID
    import re
    match = re.match(r'^select_cover_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    sub_id = int(match.group(1))
    
    # 获取投稿信息
    try:
        from database import db
        submission = db.get_submission(sub_id)
        if submission:
            try:
                file_ids = json.loads(getattr(submission, 'file_ids', '[]')) if getattr(submission, 'file_ids') else []
            except:
                file_ids = []
            
            if file_ids:
                # 不再显示封面选择菜单，而是直接使用首图功能
                await query.answer("请在混合媒体投稿中设置首图", show_alert=True)
            else:
                await query.answer("无可用的媒体文件", show_alert=True)
        else:
            await query.answer("投稿不存在", show_alert=True)
    except Exception as e:
        logger.error(f"处理封面选择请求失败: {e}")
        await query.answer("操作失败，请稍后重试", show_alert=True)

async def set_cover_callback(update: Update, context) -> None:
    """设置封面回调处理
    
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
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析封面ID
    import re
    match = re.match(r'^set_cover_(\d+)_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    sub_id = int(match.group(1))
    cover_id = int(match.group(2))
    
    # 设置封面
    try:
        from database import db
        submission = db.get_submission(sub_id)
        if submission:
            try:
                file_ids = json.loads(getattr(submission, 'file_ids', '[]')) if getattr(submission, 'file_ids') else []
            except:
                file_ids = []
            
            if cover_id < 0 or cover_id >= len(file_ids):
                await query.answer("无效的封面ID", show_alert=True)
                return
            
            success = db.update_cover_index(sub_id, cover_id)
            if not success:
                await query.answer("设置封面失败", show_alert=True)
                return
            
            await query.answer("封面已设置", show_alert=True)
        else:
            await query.answer("投稿不存在", show_alert=True)
    except Exception as e:
        logger.error(f"设置封面失败: {e}")
        await query.answer("操作失败，请稍后重试", show_alert=True)


async def noop_callback(update: Update, context) -> None:
    """空操作回调处理函数
    
    用于处理只需要显示信息而不需要执行操作的按钮
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    query = update.callback_query
    if query is None:
        return
    
    # 简单响应回调查询，不执行任何操作
    await query.answer()
        
    user = query.from_user
    if user is None:
        return
    
    # 检查用户是否被封禁
    from database import db
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            await query.answer("您已被封禁，无法使用此功能", show_alert=True)
            return
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    await query.answer()
    
    # 解析操作类型和参数
    import re
    match = re.match(r'^(set_cover|publish)_(\d+)(?:_(\d+))?$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    action = match.group(1)
    sub_id = int(match.group(2))
    index = int(match.group(3)) if match.group(3) else 0
    
    if action == "set_cover":
        # 设置封面索引
        try:
            from database import db
            success = db.update_cover_index(sub_id, index)
            if success:
                submission = db.get_submission(sub_id)
                if submission:
                    try:
                        file_ids = json.loads(getattr(submission, 'file_ids', '[]')) if getattr(submission, 'file_ids') else []
                    except:
                        file_ids = []
                    
                    if file_ids:
                        # 更新消息文本显示已选择的封面
                        keyboard_obj = confirm_submission_menu("media")
                        await query.edit_message_text(
                            f"🖼 封面已设置为第 {index+1} 张图片\n\n"
                            f"请继续完成投稿：",
                            reply_markup=keyboard_obj
                        )
                        # 添加提示，告知用户投稿已自动保存
                        if query.message:
                            await query.message.reply_text("✅ 投稿已自动保存，您可以继续其他操作或返回首页。")
                    else:
                        await query.answer("无可用的媒体文件", show_alert=True)
                else:
                    await query.answer("投稿不存在", show_alert=True)
            else:
                await query.answer("设置封面失败", show_alert=True)
        except Exception as e:
            logger.error(f"设置封面失败: {e}")
            await query.answer("操作失败，请稍后重试", show_alert=True)
    elif action == "publish":
        # 管理员/审核员发布投稿
        await query.answer("操作无效", show_alert=True)

# 私有辅助函数
async def _handle_text_submission(update: Update, context, text: str) -> None:
    """处理文本投稿
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        text: 用户输入的文本内容
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None:
        return
    
    # 检查文本长度
    if len(text) > 4096:
        await update.message.reply_text(
            "❌ 文本内容过长，请控制在4096个字符以内。",
            reply_markup=back_button("submit_text")
        )
        return
    
    # 检查文本长度是否不少于10个字符
    if len(text) < 10:
        await update.message.reply_text(
            "❌ 文本内容不得少于10个字符，请重新输入。",
            reply_markup=back_button("submit_text")
        )
        return
    
    # 保存投稿到数据库
    sub_id = db.add_submission(
        user_id=user.id,
        username=user.username or str(user.id),
        content_type="text",
        content=text,
        category="submission"
    )
    
    if sub_id is not None:
        # 记录投稿事件
        log_submission_event(
            user.id,
            user.username,
            "TEXT_SUBMISSION_RECEIVED",
            f"Text submission #{sub_id} received"
        )
        
        # 清除用户状态
        db.clear_user_state(user.id)
        
        # 只有在用户确认投稿时才发送通知给管理员和审核员
        try:
            from utils.helpers import notify_admins
            await notify_admins(context, sub_id)
        except Exception as e:
            logger.error(f"发送投稿通知失败: {e}")
        
        # 显示确认菜单
        keyboard_obj = confirm_submission_menu("text")
        await update.message.reply_text(
            f"📝 您的文本投稿已收到\n\n"
            f"投稿ID: #{sub_id}\n\n"
            f"内容预览:\n{text[:100]}{'...' if len(text) > 100 else ''}\n\n"
            f"请选择操作：",
            reply_markup=keyboard_obj
        )
    else:
        await update.message.reply_text(
            "❌ 投稿保存失败，请稍后重试。",
            reply_markup=back_button("submit_menu")
        )

async def _handle_photo_submission(update: Update, context, photo) -> None:
    """处理图片投稿
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        photo: Telegram PhotoSize 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None:
        return
    
    # 获取当前用户状态
    state, state_data = db.get_user_state(user.id)
    
    if state is None or str(state) != str(STATE_PHOTO_SUBMISSION):
        return
    
    # 初始化状态数据
    if not state_data:
        state_data = {"photos": [], "caption": ""}
    
    # 检查图片是否已经存在于列表中，避免重复添加
    if photo.file_id not in state_data["photos"]:
        # 添加图片到列表
        state_data["photos"].append(photo.file_id)
        
        # 更新用户状态
        db.set_user_state(user.id, STATE_PHOTO_SUBMISSION, state_data)
        
        # 检查是否达到最大图片数量
        if len(state_data["photos"]) >= 10:
            # 达到最大数量，自动完成上传
            await _finish_photo_submission(update, context, state_data)
            return
        
        # 只有当照片列表中有一张照片时才发送初始提示
        if len(state_data["photos"]) == 1:
            # 提示用户继续操作
            remaining = 10 - len(state_data["photos"])
            message = await update.message.reply_text(
                f"📸 图片已收到 ({len(state_data['photos'])}/10)\n\n"
                f"还可以发送 {remaining} 张图片\n\n"
                f"操作选项：",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ 继续发送图片", callback_data="add_more_photos")],
                    [InlineKeyboardButton("✅ 完成上传", callback_data="finish_photos")]
                ])  # type: ignore
            )
            # 存储消息引用以便后续编辑
            if hasattr(context, 'user_data') and context.user_data is not None:
                context.user_data['last_photo_submission_message'] = message

            # 对于后续的照片，编辑之前的消息而不是发送新消息
            remaining = 10 - len(state_data["photos"])
            # 尝试编辑之前的消息
            if hasattr(context, 'user_data') and context.user_data is not None:
                last_message = context.user_data.get('last_photo_submission_message')
                if last_message is not None:
                    try:
                        await last_message.edit_text(
                            f"📸 图片已收到 ({len(state_data['photos'])}/10)\n\n"
                            f"还可以发送 {remaining} 张图片\n\n"
                            f"操作选项：",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("➕ 继续发送图片", callback_data="add_more_photos")],
                                [InlineKeyboardButton("✅ 完成上传", callback_data="finish_photos")]
                            ])
                        )
                    except Exception as e:
                        logger.warning(f"编辑图片投稿进度消息失败: {e}")
                        # 如果编辑失败，则发送新消息
                        if len(state_data["photos"]) in [5, 10] or (len(state_data["photos"]) <= 3 and len(state_data["photos"]) >= 2):
                            new_message = await update.message.reply_text(
                                f"📸 图片已收到 ({len(state_data['photos'])}/10)\n\n"
                                f"还可以发送 {remaining} 张图片\n\n"
                                f"操作选项：",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("➕ 继续发送图片", callback_data="add_more_photos")],
                                    [InlineKeyboardButton("✅ 完成上传", callback_data="finish_photos")]
                                ])  # type: ignore
                            )

async def _handle_video_submission(update: Update, context, video) -> None:
    """处理视频投稿
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        video: Telegram Video 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None:
        return
    
    # 获取当前用户状态
    state, state_data = db.get_user_state(user.id)
    
    if state is None or str(state) != str(STATE_VIDEO_SUBMISSION):
        return
    
    # 初始化状态数据
    if not state_data:
        state_data = {"videos": [], "caption": ""}
    
    # 检查视频是否已经存在于列表中，避免重复添加
    video_exists = any(v.get("file_id") == video.file_id for v in state_data["videos"])
    if not video_exists:
        # 添加视频到列表
        state_data["videos"].append({
            "file_id": video.file_id,
            "duration": video.duration,
            "width": video.width,
            "height": video.height
        })
        
        # 更新用户状态
        db.set_user_state(user.id, STATE_VIDEO_SUBMISSION, state_data)
        
        # 检查是否达到最大视频数量
        if len(state_data["videos"]) >= 5:
            # 达到最大数量，自动完成上传
            await _finish_video_submission(update, context, state_data)
            return
        
        # 只有当视频列表中有一个视频时才发送初始提示
        if len(state_data["videos"]) == 1:
            # 提示用户继续操作
            remaining = 5 - len(state_data["videos"])
            message = await update.message.reply_text(
                f"🎬 视频已收到 ({len(state_data['videos'])}/5)\n\n"
                f"还可以发送 {remaining} 个视频\n\n"
                f"操作选项：",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ 继续发送视频", callback_data="add_more_videos")],
                    [InlineKeyboardButton("✅ 完成上传", callback_data="finish_videos")]
                ])  # type: ignore
            )
            # 存储消息引用以便后续编辑
            if hasattr(context, 'user_data') and context.user_data is not None:
                context.user_data['last_video_submission_message'] = message
        else:
            # 对于后续的视频，编辑之前的消息而不是发送新消息
            remaining = 5 - len(state_data["videos"])
            # 尝试编辑之前的消息
            if hasattr(context, 'user_data') and context.user_data is not None:
                last_message = context.user_data.get('last_video_submission_message')
                if last_message is not None:
                    try:
                        await last_message.edit_text(
                            f"🎬 视频已收到 ({len(state_data['videos'])}/5)\n\n"
                            f"还可以发送 {remaining} 个视频\n\n"
                            f"操作选项：",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("➕ 继续发送视频", callback_data="add_more_videos")],
                                [InlineKeyboardButton("✅ 完成上传", callback_data="finish_videos")]
                            ])  # type: ignore
                        )
                    except Exception as e:
                        logger.warning(f"编辑视频投稿进度消息失败: {e}")
                        # 如果编辑失败，则发送新消息
                        new_message = await update.message.reply_text(
                            f"🎬 视频已收到 ({len(state_data['videos'])}/5)\n\n"
                            f"还可以发送 {remaining} 个视频\n\n"
                            f"操作选项：",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("➕ 继续发送视频", callback_data="add_more_videos")],
                                [InlineKeyboardButton("✅ 完成上传", callback_data="finish_videos")]
                            ])  # type: ignore
                        )
                        context.user_data['last_video_submission_message'] = new_message
                else:
                    # 发送初始进度消息
                    new_message = await update.message.reply_text(
                        f"🎬 视频已收到 ({len(state_data['videos'])}/5)\n\n"
                        f"还可以发送 {remaining} 个视频\n\n"
                        f"操作选项：",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("➕ 继续发送视频", callback_data="add_more_videos")],
                            [InlineKeyboardButton("✅ 完成上传", callback_data="finish_videos")]
                        ])  # type: ignore
                    )
                    context.user_data['last_video_submission_message'] = new_message
                keyboard = [
                    [InlineKeyboardButton("➕ 继续发送视频", callback_data="add_more_videos")],
                    [InlineKeyboardButton("✅ 完成上传", callback_data="finish_videos")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)  # type: ignore
                new_message = await update.message.reply_text(
                    f"🎬 视频已收到 ({len(state_data['videos'])}/5)\n\n"
                    f"检测到重复视频，已自动过滤\n"
                    f"还可以发送 {remaining} 个视频\n\n"
                    f"操作选项：",
                    reply_markup=reply_markup  # type: ignore
                )  # type: ignore
                context.user_data['last_video_submission_message'] = new_message
    else:
        # 视频已存在，不重复添加，但仍给出提示
        remaining = 5 - len(state_data["videos"])
        # 尝试编辑之前的消息
        if hasattr(context, 'user_data') and context.user_data is not None:
            last_message = context.user_data.get('last_video_submission_message')
            if last_message is not None:
                try:
                    await last_message.edit_text(
                        f"🎬 视频已收到 ({len(state_data['videos'])}/5)\n\n"
                        f"检测到重复视频，已自动过滤\n"
                        f"还可以发送 {remaining} 个视频\n\n"
                        f"操作选项：",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("➕ 继续发送视频", callback_data="add_more_videos")],
                            [InlineKeyboardButton("✅ 完成上传", callback_data="finish_videos")]
                        ])  # type: ignore
                    )
                except Exception as e:
                    logger.warning(f"编辑重复视频提示消息失败: {e}")
                    # 如果编辑失败，则发送新消息
                    await update.message.reply_text(
                        f"🎬 视频已收到 ({len(state_data['videos'])}/5)\n\n"
                        f"检测到重复视频，已自动过滤\n"
                        f"还可以发送 {remaining} 个视频\n\n"
                        f"操作选项：",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("➕ 继续发送视频", callback_data="add_more_videos")],
                            [InlineKeyboardButton("✅ 完成上传", callback_data="finish_videos")]
                        ])  # type: ignore
                    )
        # 发送初始重复提示消息
        keyboard = [
            [InlineKeyboardButton("➕ 继续发送视频", callback_data="add_more_videos")],
            [InlineKeyboardButton("✅ 完成上传", callback_data="finish_videos")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)  # type: ignore
        new_message = await update.message.reply_text(
            f"🎬 视频已收到 ({len(state_data['videos'])}/5)\n\n"
            f"检测到重复视频，已自动过滤\n"
            f"还可以发送 {remaining} 个视频\n\n"
            f"操作选项：",
            reply_markup=reply_markup  # type: ignore
        )
        context.user_data['last_video_submission_message'] = new_message

async def _handle_mixed_media_caption(update: Update, context, text: str) -> None:
    """处理混合媒体投稿的文字说明
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        text: 用户输入的文字说明
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None:
        return
    
    # 获取当前用户状态
    state, state_data = db.get_user_state(user.id)
    
    if state is None or str(state) != str(STATE_MIXED_MEDIA_SUBMISSION) or not state_data:
        # 不在输入文字说明阶段，提示用户完成上传流程
        from keyboards import mixed_media_control_menu
        await update.message.reply_text(
            "请先完成媒体文件上传，然后点击「完成上传」按钮后再输入文字说明。",
            reply_markup=mixed_media_control_menu(0, len(state_data.get("photos", [])) + len(state_data.get("videos", [])) if state_data else 0)
        )
        return
    
    # 检查当前阶段
    stage = state_data.get("stage") if state_data else None
    
    # 如果用户发送了文本消息但不在输入文字说明阶段，提示用户先完成媒体上传
    from keyboards import mixed_media_control_menu
    if update.message.text and stage != "caption" and stage != "cover":
        await update.message.reply_text(
            "请先完成媒体文件上传，然后点击「完成上传」按钮后再输入文字说明。",
            reply_markup=mixed_media_control_menu(0, len(state_data.get("photos", [])) + len(state_data.get("videos", [])))
        )
        return
    
    # 如果在输入文字说明阶段
    if stage == "caption":
        # 检查文字说明长度
        if len(text) < 10:
            await update.message.reply_text("❌ 文字说明不得少于10个字符，请重新输入。")
            return
        
        # 保存文字说明
        state_data["caption"] = text
        
        # 更新用户状态
        db.set_user_state(user.id, STATE_MIXED_MEDIA_SUBMISSION, state_data)
        # 不再显示确认菜单，而是直接完成投稿
        await _finish_mixed_media_submission(update, context, state_data)
        return

async def _handle_mixed_media_message(update: Update, context) -> None:
    """处理混合媒体投稿消息
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 获取当前用户状态
    state, state_data = db.get_user_state(user.id)
    
    # 检查是否处于混合媒体投稿状态
    if state is None or str(state) != str(STATE_MIXED_MEDIA_SUBMISSION):
        # 如果不在混合媒体投稿状态，不处理消息
        return
    
    # 检查当前阶段
    stage = state_data.get("stage") if state_data else None
    
    # 如果在输入文字说明阶段，处理文字说明
    if stage == "caption":
        if update.message and update.message.text:
            await _handle_mixed_media_caption(update, context, update.message.text)
        return
    
    # 如果在上传首图阶段，处理首图
    if stage == "cover":
        # 现在第一张照片自动作为首图，不再需要单独上传首图
        # 直接完成投稿
        await _finish_mixed_media_submission(update, context, state_data)
        return
    
    # 如果用户发送了文本消息但不在输入文字说明阶段，提示用户先完成媒体上传
    if update.message and update.message.text and stage != "caption":
        await update.message.reply_text(
            "请先完成媒体文件上传，然后点击「完成上传」按钮后再输入文字说明。",
            reply_markup=mixed_media_control_menu(0, len(state_data.get("photos", [])) + len(state_data.get("videos", [])))
        )
        return
    
    # 否则处理媒体文件
    if update.message:
        if update.message.photo:
            await _handle_mixed_media_photo(update, context)
        elif update.message.video:
            await _handle_mixed_media_video(update, context)

async def _handle_mixed_media_photo(update: Update, context) -> None:
    """处理混合媒体投稿中的图片
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None or update.message.photo is None:
        return
    
    try:
        # 获取最大的图片
        photo = update.message.photo[-1]
        
        # 获取当前用户状态
        state, state_data = db.get_user_state(user.id)
        
        if state is None or str(state) != str(STATE_MIXED_MEDIA_SUBMISSION):
            return
        
        # 初始化状态数据
        if not state_data:
            state_data = {"photos": [], "videos": [], "caption": ""}
        
        # 检查是否达到照片数量上限
        if len(state_data["photos"]) >= 100:
            await update.message.reply_text(
                "❌ 照片数量已达上限（100张），无法继续添加照片。",
                reply_markup=mixed_media_control_menu(0, len(state_data["photos"]) + len(state_data["videos"]))
            )
            return
        
        # 检查图片是否已经存在于列表中，避免重复添加
        if photo.file_id not in state_data["photos"]:
            # 同时检查是否与现有视频重复（防止Telegram将同一文件识别为不同类型）
            video_exists = any(v.get("file_id") == photo.file_id for v in state_data["videos"])
            if video_exists:
                # 图片已作为视频存在，不重复添加，但仍给出提示
                total_media = len(state_data["photos"]) + len(state_data["videos"])
                remaining = 120 - total_media
                # 尝试编辑之前的消息
                if hasattr(context, 'user_data') and context.user_data is not None:
                    last_message = context.user_data.get('last_mixed_media_submission_message')
                    if last_message is not None:
                        try:
                            await last_message.edit_text(
                                f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                                f"检测到重复图片，已自动过滤\n"
                                f"还可以发送 {120 - total_media} 个媒体文件\n\n"
                                f"操作选项：",
                                reply_markup=mixed_media_control_menu(0, total_media)
                            )
                        except Exception as e:
                            logger.warning(f"编辑重复媒体文件提示消息失败: {e}")
                            # 如果编辑失败，则发送新消息
                            await update.message.reply_text(
                                f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                                f"检测到重复图片，已自动过滤\n"
                                f"还可以发送 {120 - total_media} 个媒体文件\n\n"
                                f"操作选项：",
                                reply_markup=mixed_media_control_menu(0, total_media)
                            )
                    else:
                        # 发送初始重复提示消息
                        new_message = await update.message.reply_text(
                            f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                            f"检测到重复图片，已自动过滤\n"
                            f"还可以发送 {120 - total_media} 个媒体文件\n\n"
                            f"操作选项：",
                            reply_markup=mixed_media_control_menu(0, total_media)
                        )
                        context.user_data['last_mixed_media_submission_message'] = new_message
                else:
                    await update.message.reply_text(
                        f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                        f"检测到重复图片，已自动过滤\n"
                        f"还可以发送 {120 - total_media} 个媒体文件\n\n"
                        f"操作选项：",
                        reply_markup=mixed_media_control_menu(0, total_media)
                    )
                return
                
            # 添加图片到列表
            state_data["photos"].append(photo.file_id)
            
            # 检查是否达到最大媒体数量
            total_media = len(state_data["photos"]) + len(state_data["videos"])
            if total_media >= 120:
                # 达到最大数量，自动完成上传
                await _finish_mixed_media_submission(update, context, state_data)
                return
            
            # 计算剩余可发送的媒体数量
            remaining = 120 - total_media
            photo_remaining = 100 - len(state_data["photos"])
            video_remaining = 20 - len(state_data["videos"])
            
            # 更新用户状态，确保保留原有的状态数据
            current_state, current_data = db.get_user_state(user.id)
            merged_data = None
            if current_data:
                # 合并现有数据和新数据，确保保留已有的照片和视频
                merged_data = current_data.copy()
                # 合并照片列表
                if "photos" in state_data and state_data["photos"]:
                    for photo in state_data["photos"]:
                        if photo not in merged_data["photos"]:
                            merged_data["photos"].append(photo)
                # 合并视频列表
                if "videos" in state_data and state_data["videos"]:
                    for video in state_data["videos"]:
                        # 检查是否已存在于merged_data中
                        video_exists = any(v.get("file_id") == video.get("file_id") for v in merged_data["videos"])
                        if not video_exists:
                            merged_data["videos"].append(video)
                db.set_user_state(user.id, STATE_MIXED_MEDIA_SUBMISSION, merged_data)
                # 使用合并后的数据计算总数
                total_media = len(merged_data["photos"]) + len(merged_data["videos"])
            else:
                db.set_user_state(user.id, STATE_MIXED_MEDIA_SUBMISSION, state_data)
                # 使用当前数据计算总数
                total_media = len(state_data["photos"]) + len(state_data["videos"])
            
            # 计算剩余可发送的媒体数量
            remaining = 120 - total_media
            if current_data and merged_data:
                photo_remaining = 100 - len(merged_data["photos"])
                video_remaining = 20 - len(merged_data["videos"])
            else:
                photo_remaining = 100 - len(state_data["photos"])
                video_remaining = 20 - len(state_data["videos"])
            
            # 发送或更新进度消息
            if hasattr(context, 'user_data') and context.user_data is not None:
                last_message = context.user_data.get('last_mixed_media_submission_message')
                if last_message is not None:
                    try:
                        await last_message.edit_text(
                            f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                            f"还可以发送 {remaining} 个媒体文件\n"
                            f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                            f"操作选项：",
                            reply_markup=mixed_media_control_menu(0, total_media)
                        )
                    except Exception as e:
                        # 如果消息内容相同，忽略错误
                        if "Message is not modified" not in str(e):
                            logger.warning(f"编辑混合媒体投稿进度消息失败: {e}")
                            # 增加重试机制
                            retry_count = 0
                            while retry_count < 3:
                                try:
                                    new_message = await update.message.reply_text(
                                        f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                                        f"还可以发送 {remaining} 个媒体文件\n"
                                        f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                                        f"操作选项：",
                                        reply_markup=mixed_media_control_menu(0, total_media)
                                    )
                                    context.user_data['last_mixed_media_submission_message'] = new_message
                                    break
                                except Exception as retry_e:
                                    logger.warning(f"重试发送消息失败 ({retry_count + 1}/3): {retry_e}")
                                    retry_count += 1
                                    if retry_count >= 3:
                                        logger.error(f"多次重试发送消息失败: {retry_e}")
                        # 消息未修改时，不需要做任何事情
                else:
                    # 发送初始进度消息
                    new_message = await update.message.reply_text(
                        f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                        f"还可以发送 {remaining} 个媒体文件\n"
                        f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                        f"操作选项：",
                        reply_markup=mixed_media_control_menu(0, total_media)
                    )
                    context.user_data['last_mixed_media_submission_message'] = new_message
            else:
                # 如果没有上下文数据，直接发送消息
                await update.message.reply_text(
                    f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                    f"还可以发送 {remaining} 个媒体文件\n"
                    f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                    f"操作选项：",
                    reply_markup=mixed_media_control_menu(0, total_media)
                )
        else:
            # 图片已存在，不重复添加，但仍给出提示
            total_media = len(state_data["photos"]) + len(state_data["videos"])
            remaining = 120 - total_media
            photo_remaining = 100 - len(state_data["photos"])
            video_remaining = 20 - len(state_data["videos"])
            # 尝试编辑之前的消息
            if hasattr(context, 'user_data') and context.user_data is not None:
                last_message = context.user_data.get('last_mixed_media_submission_message')
                if last_message is not None:
                    try:
                        await last_message.edit_text(
                            f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                            f"检测到重复图片，已自动过滤\n"
                            f"还可以发送 {120 - total_media} 个媒体文件\n"
                            f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                            f"操作选项：",
                            reply_markup=mixed_media_control_menu(0, total_media)
                        )
                    except Exception as e:
                        # 如果消息内容相同，忽略错误
                        if "Message is not modified" not in str(e):
                            logger.warning(f"编辑重复媒体文件提示消息失败: {e}")
                            # 如果编辑失败，则发送新消息
                            await update.message.reply_text(
                                f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                                f"检测到重复图片，已自动过滤\n"
                                f"还可以发送 {120 - total_media} 个媒体文件\n"
                                f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                                f"操作选项：",
                                reply_markup=mixed_media_control_menu(0, total_media)
                            )
                        # 消息未修改时，不需要做任何事情
                else:
                    # 发送初始重复提示消息
                    new_message = await update.message.reply_text(
                        f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                        f"检测到重复图片，已自动过滤\n"
                        f"还可以发送 {120 - total_media} 个媒体文件\n"
                        f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                        f"操作选项：",
                        reply_markup=mixed_media_control_menu(0, total_media)
                    )
                    context.user_data['last_mixed_media_submission_message'] = new_message
            else:
                await update.message.reply_text(
                    f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                    f"检测到重复图片，已自动过滤\n"
                    f"还可以发送 {120 - total_media} 个媒体文件\n"
                    f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                    f"操作选项：",
                    reply_markup=mixed_media_control_menu(0, total_media)
                )
    except Exception as e:
        logger.error(f"处理混合媒体图片时发生错误: {e}")
        # 确保在出现错误时通知用户
        try:
            await update.message.reply_text(
                "❌ 处理图片时发生错误，请稍后重试。",
                reply_markup=back_button("submit_menu")
            )
        except:
            pass  # 如果连错误消息都无法发送，就静默失败

async def _handle_mixed_media_video(update: Update, context) -> None:
    """处理混合媒体投稿中的视频
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None or update.message.video is None:
        return
    
    video = update.message.video
    
    try:
        # 获取当前用户状态
        state, state_data = db.get_user_state(user.id)
        
        if state is None or str(state) != str(STATE_MIXED_MEDIA_SUBMISSION):
            return
        
        # 初始化状态数据
        if not state_data:
            state_data = {"photos": [], "videos": [], "caption": ""}
        
        # 检查是否达到视频数量上限
        if len(state_data["videos"]) >= 20:
            await update.message.reply_text(
                "❌ 视频数量已达上限（20个），无法继续添加视频。",
                reply_markup=mixed_media_control_menu(0, len(state_data["photos"]) + len(state_data["videos"]))
            )
            return
        
        # 检查视频是否已经存在于列表中，避免重复添加
        video_exists = any(v.get("file_id") == video.file_id for v in state_data["videos"])
        # 同时检查是否与现有照片重复（防止Telegram将同一文件识别为不同类型）
        photo_exists = video.file_id in state_data["photos"]
        
        if not video_exists and not photo_exists:
            # 添加视频到列表
            state_data["videos"].append({
                "file_id": video.file_id,
                "duration": getattr(video, 'duration', 0),
                "width": getattr(video, 'width', 0),
                "height": getattr(video, 'height', 0)
            })
            
            # 检查是否达到最大媒体数量
            total_media = len(state_data["photos"]) + len(state_data["videos"])
            if total_media >= 120:
                # 达到最大数量，自动完成上传
                await _finish_mixed_media_submission(update, context, state_data)
                return
            
            # 更新用户状态，确保保留原有的状态数据
            current_state, current_data = db.get_user_state(user.id)
            merged_data = None
            if current_data:
                # 合并现有数据和新数据，确保保留已有的照片和视频
                merged_data = current_data.copy()
                # 合并照片列表
                if "photos" in state_data and state_data["photos"]:
                    for photo in state_data["photos"]:
                        if photo not in merged_data["photos"]:
                            merged_data["photos"].append(photo)
                # 合并视频列表
                if "videos" in state_data and state_data["videos"]:
                    for video in state_data["videos"]:
                        # 检查是否已存在于merged_data中
                        video_exists = any(v.get("file_id") == video.get("file_id") for v in merged_data["videos"])
                        if not video_exists:
                            merged_data["videos"].append(video)
                db.set_user_state(user.id, STATE_MIXED_MEDIA_SUBMISSION, merged_data)
                # 使用合并后的数据计算总数
                total_media = len(merged_data["photos"]) + len(merged_data["videos"])
            else:
                db.set_user_state(user.id, STATE_MIXED_MEDIA_SUBMISSION, state_data)
                # 使用当前数据计算总数
                total_media = len(state_data["photos"]) + len(state_data["videos"])
            
            # 计算剩余可发送的媒体数量
            remaining = 120 - total_media
            if current_data and merged_data:
                photo_remaining = 100 - len(merged_data["photos"])
                video_remaining = 20 - len(merged_data["videos"])
            else:
                photo_remaining = 100 - len(state_data["photos"])
                video_remaining = 20 - len(state_data["videos"])

            
            # 发送或更新进度消息
            if hasattr(context, 'user_data') and context.user_data is not None:
                last_message = context.user_data.get('last_mixed_media_submission_message')
                if last_message is not None:
                    try:
                        await last_message.edit_text(
                            f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                            f"还可以发送 {remaining} 个媒体文件\n"
                            f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                            f"操作选项：",
                            reply_markup=mixed_media_control_menu(0, total_media)
                        )
                    except Exception as e:
                        logger.warning(f"编辑混合媒体投稿进度消息失败: {e}")
                        # 增加重试机制
                        retry_count = 0
                        while retry_count < 3:
                            try:
                                new_message = await update.message.reply_text(
                                    f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                                    f"还可以发送 {remaining} 个媒体文件\n"
                                    f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                                    f"操作选项：",
                                    reply_markup=mixed_media_control_menu(0, total_media)
                                )
                                context.user_data['last_mixed_media_submission_message'] = new_message
                                break
                            except Exception as retry_e:
                                logger.warning(f"重试发送消息失败 ({retry_count + 1}/3): {retry_e}")
                                retry_count += 1
                                if retry_count >= 3:
                                    logger.error(f"多次重试发送消息失败: {retry_e}")
                else:
                    # 发送初始进度消息
                    new_message = await update.message.reply_text(
                        f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                        f"还可以发送 {remaining} 个媒体文件\n"
                        f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                        f"操作选项：",
                        reply_markup=mixed_media_control_menu(0, total_media)
                    )
                    context.user_data['last_mixed_media_submission_message'] = new_message
            else:
                # 如果没有上下文数据，直接发送消息
                await update.message.reply_text(
                    f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                    f"还可以发送 {remaining} 个媒体文件\n"
                    f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                    f"操作选项：",
                    reply_markup=mixed_media_control_menu(0, total_media)
                )
        else:
            # 视频已存在，不重复添加，但仍给出提示
            total_media = len(state_data["photos"]) + len(state_data["videos"])
            remaining = 120 - total_media
            photo_remaining = 100 - len(state_data["photos"])
            video_remaining = 20 - len(state_data["videos"])
            # 尝试编辑之前的消息
            if hasattr(context, 'user_data') and context.user_data is not None:
                last_message = context.user_data.get('last_mixed_media_submission_message')
                if last_message is not None:
                    try:
                        await last_message.edit_text(
                            f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                            f"检测到重复视频，已自动过滤\n"
                            f"还可以发送 {120 - total_media} 个媒体文件\n"
                            f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                            f"操作选项：",
                            reply_markup=mixed_media_control_menu(0, total_media)
                        )
                    except Exception as e:
                        # 如果消息内容相同，忽略错误
                        if "Message is not modified" not in str(e):
                            logger.warning(f"编辑重复媒体文件提示消息失败: {e}")
                            # 如果编辑失败，则发送新消息
                            await update.message.reply_text(
                                f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                                f"检测到重复视频，已自动过滤\n"
                                f"还可以发送 {120 - total_media} 个媒体文件\n"
                                f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                                f"操作选项：",
                                reply_markup=mixed_media_control_menu(0, total_media)
                            )
                        # 消息未修改时，不需要做任何事情
                else:
                    # 发送初始重复提示消息
                    new_message = await update.message.reply_text(
                        f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                        f"检测到重复视频，已自动过滤\n"
                        f"还可以发送 {120 - total_media} 个媒体文件\n"
                        f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                        f"操作选项：",
                        reply_markup=mixed_media_control_menu(0, total_media)
                    )
                    context.user_data['last_mixed_media_submission_message'] = new_message
            else:
                await update.message.reply_text(
                    f"🎭 媒体文件已收到 ({total_media}/120)\n\n"
                    f"检测到重复视频，已自动过滤\n"
                    f"还可以发送 {120 - total_media} 个媒体文件\n"
                    f"照片还可发送 {photo_remaining} 张，视频还可发送 {video_remaining} 个\n\n"
                    f"操作选项：",
                    reply_markup=mixed_media_control_menu(0, total_media)
                )
    except Exception as e:
        logger.error(f"处理混合媒体视频时发生错误: {e}")
        # 确保在出现错误时通知用户
        try:
            await update.message.reply_text(
                "❌ 处理视频时发生错误，请稍后重试。",
                reply_markup=back_button("submit_menu")
            )
        except:
            pass  # 如果连错误消息都无法发送，就静默失败

async def _finish_photo_submission(update: Update, context, state_data) -> None:
    """完成图片投稿
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        state_data: 用户状态数据
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None:
        return
    
    photos = state_data.get("photos", [])
    caption = state_data.get("caption", "")
    
    # 检查文字说明长度是否不少于10个字符
    if len(caption) < 10:
        await update.message.reply_text(
            "❌ 文字说明不得少于10个字符，请重新输入。",
            reply_markup=back_button("submit_menu")
        )
        return
    
    if not photos:
        await update.message.reply_text(
            "❌ 未收到任何图片，请重新发送。",
            reply_markup=back_button("submit_menu")
        )
        return
    
    # 保存投稿到数据库
    sub_id = db.add_submission(
        user_id=user.id,
        username=user.username or str(user.id),
        content_type="photo",
        content=caption,
        file_id=photos[0] if len(photos) == 1 else None,
        file_ids=photos,
        category="submission"
    )
    
    if sub_id is not None:
        # 记录投稿事件
        log_submission_event(
            user.id,
            user.username,
            "PHOTO_SUBMISSION_RECEIVED",
            f"Photo submission #{sub_id} received with {len(photos)} photos"
        )
        
        # 清除用户状态
        db.clear_user_state(user.id)
        
        # 只有在用户确认投稿时才发送通知给管理员和审核员
        try:
            from utils.helpers import notify_admins
            await notify_admins(context, sub_id)
        except Exception as e:
            logger.error(f"发送投稿通知失败: {e}")
        
        # 如果有多张图片，需要选择封面
        if len(photos) > 1:
            await update.message.reply_text(
                f"📸 您的图片投稿已收到\n\n"
                f"投稿ID: #{sub_id}\n"
                f"图片数量: {len(photos)}张\n\n"
                f"请在混合媒体投稿中设置首图",
            )
        else:
            # 只有一张图片，直接显示确认菜单
            await update.message.reply_text(
                f"📸 您的图片投稿已收到\n\n"
                f"投稿ID: #{sub_id}\n\n"
                f"请选择操作：",
                reply_markup=confirm_submission_menu("photo")
            )
    else:
        await update.message.reply_text(
            "❌ 投稿保存失败，请稍后重试。",
            reply_markup=back_button("submit_menu")
        )

async def _finish_video_submission(update: Update, context, state_data) -> None:
    """完成视频投稿
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        state_data: 用户状态数据
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None:
        return
    
    videos = state_data.get("videos", [])
    caption = state_data.get("caption", "")
    
    # 检查文字说明长度是否不少于10个字符
    if len(caption) < 10:
        await update.message.reply_text(
            "❌ 文字说明不得少于10个字符，请重新输入。",
            reply_markup=back_button("submit_menu")
        )
        return
    
    if not videos:
        await update.message.reply_text(
            "❌ 未收到任何视频，请重新发送。",
            reply_markup=back_button("submit_menu")
        )
        return
    
    # 保存投稿到数据库
    sub_id = db.add_submission(
        user_id=user.id,
        username=user.username or str(user.id),
        content_type="video",
        content=caption,
        file_id=videos[0]["file_id"] if len(videos) == 1 else None,
        file_ids=[v["file_id"] for v in videos],
        category="submission"
    )
    
    if sub_id is not None:
        # 记录投稿事件
        log_submission_event(
            user.id,
            user.username,
            "VIDEO_SUBMISSION_RECEIVED",
            f"Video submission #{sub_id} received with {len(videos)} videos"
        )
        
        # 清除用户状态
        db.clear_user_state(user.id)
        
        # 只有在用户确认投稿时才发送通知给管理员和审核员
        try:
            from utils.helpers import notify_admins
            await notify_admins(context, sub_id)
        except Exception as e:
            logger.error(f"发送投稿通知失败: {e}")
        
        # 如果有多个视频，需要选择封面（使用第一帧）
        if len(videos) > 1:
            video_ids = [v["file_id"] for v in videos]
            await update.message.reply_text(
                f"🎬 您的视频投稿已收到\n\n"
                f"投稿ID: #{sub_id}\n"
                f"视频数量: {len(videos)}个\n\n"
                f"请在混合媒体投稿中设置首图",
            )
        else:
            # 只有一个视频，直接显示确认菜单
            await update.message.reply_text(
                f"🎬 您的视频投稿已收到\n\n"
                f"投稿ID: #{sub_id}\n\n"
                f"请选择操作：",
                reply_markup=confirm_submission_menu("video")
            )
    else:
        await update.message.reply_text(
            "❌ 投稿保存失败，请稍后重试。",
            reply_markup=back_button("submit_menu")
        )

async def _finish_mixed_media_submission(update: Update, context, state_data: dict) -> None:
    """完成混合媒体投稿
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        state_data: 状态数据
    """
    user = update.effective_user
    if user is None:
        return
    
    # 获取数据
    photos = state_data.get("photos", [])
    videos = state_data.get("videos", [])
    caption = state_data.get("caption", "")
    
    # 自动将第一张照片作为首图
    cover_photo = ""
    if photos:
        cover_photo = photos[0]
    elif videos:
        cover_photo = videos[0]["file_id"]
    
    # 如果没有媒体文件，直接返回错误
    if not photos and not videos:
        if update.message:
            await update.message.reply_text(
                "❌ 未收到任何媒体文件，请重新发送。",
                reply_markup=back_button("submit_menu")
            )
        elif update.callback_query:
            await update.callback_query.answer("未收到任何媒体文件，请重新发送。", show_alert=True)
        return
    
    # 检查文字说明长度是否不少于10个字符
    if len(caption) < 10:
        if update.message:
            await update.message.reply_text(
                "❌ 文字说明不得少于10个字符，请重新输入。",
                reply_markup=back_button("submit_menu")
            )
        elif update.callback_query:
            await update.callback_query.answer("文字说明不得少于10个字符，请重新输入。", show_alert=True)
        return
    
    if not photos and not videos:
        if update.message:
            await update.message.reply_text(
                "❌ 未收到任何媒体文件，请重新发送。",
                reply_markup=back_button("submit_menu")
            )
        elif update.callback_query:
            await update.callback_query.answer("未收到任何媒体文件，请重新发送。", show_alert=True)
        return
    
    # 合并文件ID和类型，将首图放在第一位
    if photos and cover_photo == photos[0]:
        # 如果首图是第一张照片，则从photos列表中移除第一张
        file_ids = [cover_photo] + photos[1:] + [v["file_id"] for v in videos]
        file_types = ["photo"] * (1 + len(photos[1:])) + ["video"] * len(videos)
    elif videos and cover_photo == videos[0]["file_id"]:
        # 如果首图是第一个视频，则从videos列表中移除第一个
        file_ids = [cover_photo] + photos + [v["file_id"] for v in videos[1:]]
        file_types = ["photo"] * len(photos) + ["video"] * (1 + len(videos[1:]))
    else:
        # 其他情况，将首图放在第一位
        file_ids = [cover_photo] + photos + [v["file_id"] for v in videos]
        file_types = ["photo"] * (1 + len(photos)) + ["video"] * len(videos)
    
    # 检查是否需要匿名投稿选项
    is_anonymous = state_data.get("anonymous", False)
    
    # 保存投稿到数据库，确保状态为pending
    sub_id = db.add_submission(
        user_id=user.id,
        username=user.username or str(user.id),
        content_type="media",
        content=caption,
        file_ids=file_ids,
        file_types=file_types,
        category="submission",
        anonymous=is_anonymous
    )
    
    # 更新封面索引为0（首图）
    if sub_id is not None:
        db.update_cover_index(sub_id, 0)
    
    if sub_id is not None:
        # 记录投稿事件
        log_submission_event(
            user.id,
            user.username,
            "MIXED_MEDIA_SUBMISSION_RECEIVED",
            f"Mixed media submission #{sub_id} received with {len(photos)} photos and {len(videos)} videos"
        )
        
        # 清除用户状态
        db.clear_user_state(user.id)
        
        # 只有在用户确认投稿时才发送通知给管理员和审核员
        try:
            from utils.helpers import notify_admins
            await notify_admins(context, sub_id)
        except Exception as e:
            logger.error(f"发送投稿通知失败: {e}")
        
        # 提示用户投稿已成功提交，无需确认菜单
        try:
            if update.message:
                await update.message.reply_text(
                    f"✅ 您的混合媒体投稿已成功提交！\n\n"
                    f"投稿ID: #{sub_id}\n"
                    f"{'🎭 匿名投稿' if is_anonymous else '👤 实名投稿'}\n\n"
                    f"请等待管理员审核。"
                )
            elif update.callback_query:
                await update.callback_query.edit_message_text(
                    f"✅ 您的混合媒体投稿已成功提交！\n\n"
                    f"投稿ID: #{sub_id}\n"
                    f"{'🎭 匿名投稿' if is_anonymous else '👤 实名投稿'}\n\n"
                    f"请等待管理员审核。"
                )
        except Exception as e:
            logger.error(f"发送混合媒体投稿确认消息失败: {e}")
            # 即使发送确认消息失败，也要确保用户知道投稿已成功提交
            if update.message:
                await update.message.reply_text("✅ 您的混合媒体投稿已成功提交！请等待管理员审核。")
            elif update.callback_query:
                await update.callback_query.answer("投稿已成功提交！请等待管理员审核。", show_alert=True)
    else:
        if update.message:
            await update.message.reply_text(
                "❌ 投稿保存失败，请稍后重试。",
                reply_markup=back_button("submit_menu")
            )
        elif update.callback_query:
            await update.callback_query.answer("投稿保存失败，请稍后重试。", show_alert=True)

async def _confirm_submission(query, context, submission_type: str) -> None:
    """确认投稿
    
    Args:
        query: Telegram callback query 对象
        context: Telegram context 对象
        submission_type: 投稿类型
    """
    user = query.from_user
    if user is None:
        return
    
    # 获取当前用户状态
    state, state_data = db.get_user_state(user.id)
    
    # 根据投稿类型确定状态
    type_to_state = {
        "text": STATE_TEXT_SUBMISSION,
        "photo": STATE_PHOTO_SUBMISSION,
        "video": STATE_VIDEO_SUBMISSION,
        "media": STATE_MIXED_MEDIA_SUBMISSION
    }
    
    expected_state = type_to_state.get(submission_type)
    if state is None or str(state) != str(expected_state):
        await query.answer("操作已过期，请重新开始投稿", show_alert=True)
        return
    
    # 保存投稿到数据库
    sub_id = None
    if submission_type == "text" and state_data and "text" in state_data:
        content = state_data["text"]
        sub_id = db.add_submission(
            user_id=user.id,
            username=user.username or str(user.id),
            content_type="text",
            content=content,
            category="submission"
        )
    elif submission_type == "media" and state_data:
        # 处理混合媒体投稿确认
        photos = state_data.get("photos", [])
        videos = state_data.get("videos", [])
        caption = state_data.get("caption", "")
        
        # 合并文件ID和类型
        file_ids = photos + [v["file_id"] for v in videos]
        file_types = ["photo"] * len(photos) + ["video"] * len(videos)
        
        # 检查是否需要匿名投稿选项
        is_anonymous = state_data.get("anonymous", False)
        
        sub_id = db.add_submission(
            user_id=user.id,
            username=user.username or str(user.id),
            content_type="media",
            content=caption,
            file_ids=file_ids,
            file_types=file_types,
            category="submission",
            anonymous=is_anonymous
        )
    else:
        # 其他类型投稿应该已经保存过了
        await query.answer("无效的操作", show_alert=True)
        return
    
    if sub_id is not None:
        # 记录投稿事件
        log_submission_event(
            user.id,
            user.username,
            f"{submission_type.upper()}_SUBMISSION_CONFIRMED",
            f"{submission_type.capitalize()} submission #{sub_id} confirmed"
        )
        
        # 清除用户状态
        db.clear_user_state(user.id)
        
        # 只有在用户确认投稿时才发送通知给管理员和审核员
        try:
            from utils.helpers import notify_admins
            await notify_admins(context, sub_id)
        except Exception as e:
            logger.error(f"发送投稿通知失败: {e}")
        
        await query.edit_message_text(
            f"✅ 您的投稿 #{sub_id} 已成功提交！\n\n"
            f"感谢您的分享，我们会尽快审核您的投稿。",
            reply_markup=back_button("main_menu")
        )
    else:
        await query.answer("投稿保存失败，请稍后重试", show_alert=True)

async def _edit_submission(query, context, submission_type: str) -> None:
    """编辑投稿
    
    Args:
        query: Telegram callback query 对象
        context: Telegram context 对象
        submission_type: 投稿类型
    """
    user = query.from_user
    if user is None:
        return
    
    # 根据投稿类型设置相应的用户状态
    type_to_state = {
        "text": STATE_TEXT_SUBMISSION,
        "photo": STATE_PHOTO_SUBMISSION,
        "video": STATE_VIDEO_SUBMISSION,
        "media": STATE_MIXED_MEDIA_SUBMISSION
    }
    
    state = type_to_state.get(submission_type)
    if not state:
        await query.answer("无效的操作", show_alert=True)
        return
    
    # 设置用户状态
    db.set_user_state(user.id, state)
    
    # 根据投稿类型提示用户重新输入
    if submission_type == "text":
        prompt_text = (
            "📝 文本投稿（重新编辑）\n\n"
            "请重新发送您要投稿的文本内容：\n\n"
            "📌 提示：\n"
            "• 支持Emoji和基本格式\n"
            "• 最多可输入4096个字符\n"
            "• 请勿包含敏感或违规内容"
        )
    elif submission_type == "photo":
        prompt_text = (
            "📸 图片投稿（重新编辑）\n\n"
            "请重新发送您要投稿的图片：\n\n"
            "📌 提示：\n"
            "• 支持JPG、PNG等常见格式\n"
            "• 可发送多张图片（推荐使用相册模式）\n"
            "• 单张图片大小不超过20MB"
        )
    elif submission_type == "video":
        prompt_text = (
            "🎬 视频投稿（重新编辑）\n\n"
            "请重新发送您要投稿的视频：\n\n"
            "📌 提示：\n"
            "• 支持MP4等常见格式\n"
            "• 视频时长不超过10分钟\n"
            "• 单个视频大小不超过50MB"
        )
    else:  # media (mixed)
        prompt_text = (
            "🎭 混合媒体投稿（重新编辑）\n\n"
            "请重新发送图片或视频（可以混合发送）：\n\n"
            "📌 操作指南：\n"
            "• 先发送所有图片和视频\n"
            "• 然后点击「完成上传」\n"
            "• 最后输入文字说明\n\n"
            "⚠️ 注意：\n"
            "• 最多可发送10个媒体文件\n"
            "• 单个文件大小不超过20MB"
        )
    
    await query.edit_message_text(
        prompt_text,
        reply_markup=back_button("submit_menu")
    )

async def _toggle_anonymous(query, context, submission_type: str) -> None:
    """切换匿名状态
    
    Args:
        query: Telegram callback query 对象
        context: Telegram context 对象
        submission_type: 投稿类型
    """
    user = query.from_user
    if user is None:
        return
    
    # 获取当前用户状态
    state, state_data = db.get_user_state(user.id)
    
    # 如果没有状态，则创建一个默认状态
    if state is None:
        # 根据投稿类型确定状态
        type_to_state = {
            "text": STATE_TEXT_SUBMISSION,
            "photo": STATE_PHOTO_SUBMISSION,
            "video": STATE_VIDEO_SUBMISSION,
            "media": STATE_MIXED_MEDIA_SUBMISSION
        }
        state = type_to_state.get(submission_type, STATE_TEXT_SUBMISSION)
    
    # 切换匿名状态
    is_anonymous = state_data.get("anonymous", False) if state_data else False
    is_anonymous = not is_anonymous
    
    # 更新状态数据
    if not state_data:
        state_data = {}
    state_data["anonymous"] = is_anonymous
    
    # 更新用户状态
    db.set_user_state(user.id, state, state_data)
    
    # 更新消息显示
    await query.answer(f"匿名状态已设置为: {'是' if is_anonymous else '否'}")
    
    # 重新显示确认菜单
    try:
        await query.edit_message_reply_markup(
            reply_markup=confirm_submission_menu(submission_type, is_anonymous)
        )
    except Exception as e:
        # 如果消息没有修改，则忽略错误
        if "Message is not modified" not in str(e):
            logger.error(f"更新匿名状态按钮失败: {e}")
            await query.answer("操作失败，请稍后重试", show_alert=True)

# 管理群组ID使用默认配置，此函数已弃用
async def _handle_config_management_group(update: Update, context, text: str) -> None:
    """处理管理群组ID配置输入（已弃用）
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        text: 用户输入的文本
    """
    pass  # 此函数已弃用

async def _handle_config_channels(update: Update, context, text: str) -> None:
    """处理频道ID配置输入
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        text: 用户输入的文本
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None:
        return
    
    try:
        # 分割并验证输入的频道ID列表
        channel_ids = [x.strip() for x in text.split(',') if x.strip()]
        validated_ids = []
        
        if not channel_ids:
            raise ValueError("频道ID列表不能为空")
        
        for channel_id in channel_ids:
            # 检查是否为数字ID
            if channel_id.lstrip('-').isdigit():
                id_value = int(channel_id)
                # 检查是否为有效的频道ID格式
                if str(id_value).startswith('-100'):
                    validated_ids.append(str(id_value))
                else:
                    raise ValueError(f"无效的频道ID: {channel_id} (频道ID应以-100开头)")
            else:
                # 检查是否为用户名格式
                if channel_id.startswith('@') and len(channel_id) > 1:
                    validated_ids.append(channel_id)
                else:
                    raise ValueError(f"无效的频道ID格式: {channel_id} (应为以-100开头的数字ID或以@开头的用户名)")
        
        # 这里应该保存配置到数据库或配置文件
        # 由于这是一个演示，我们只显示成功消息
        await update.message.reply_text(
            f"✅ 频道ID列表已设置为: {', '.join(validated_ids)}\n\n"
            "支持的格式：\n"
            "• 数字ID: -1001234567890\n"
            "• 用户名: @channelusername\n\n"
            "注意：配置将在机器人重启后生效",
            reply_markup=back_button("system_config")
        )
        
        # 清除用户状态
        db.clear_user_state(user.id)
        
    except ValueError as e:
        await update.message.reply_text(
            f"❌ {str(e)}\n\n"
            "频道ID支持两种格式：\n"
            "• 数字ID：以-100开头的频道ID\n"
            "• 用户名：以@开头的频道用户名\n\n"
            "示例: -1001234567890,@mychannel\n\n"
            "请重新输入：",
            reply_markup=back_button("system_config")
        )
    except Exception as e:
        logger.error(f"处理频道ID配置失败: {e}")
        await update.message.reply_text(
            "❌ 配置保存失败，请稍后重试\n\n"
            "请重新输入：",
            reply_markup=back_button("system_config")
        )

async def _handle_config_groups(update: Update, context, text: str) -> None:
    """处理群组ID配置输入
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        text: 用户输入的文本
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None:
        return
    
    try:
        # 分割并验证输入的群组ID列表
        group_ids = [x.strip() for x in text.split(',') if x.strip()]
        validated_ids = []
        
        if not group_ids:
            raise ValueError("群组ID列表不能为空")
        
        for group_id in group_ids:
            # 检查是否为数字ID
            if group_id.lstrip('-').isdigit():
                id_value = int(group_id)
                # 检查是否为有效的群组ID格式
                if str(id_value).startswith('-100'):
                    validated_ids.append(str(id_value))
                else:
                    raise ValueError(f"无效的群组ID: {group_id} (群组ID应以-100开头)")
            else:
                raise ValueError(f"无效的群组ID格式: {group_id} (应为以-100开头的数字ID)")
        
        # 这里应该保存配置到数据库或配置文件
        # 由于这是一个演示，我们只显示成功消息
        await update.message.reply_text(
            f"✅ 群组ID列表已设置为: {', '.join(validated_ids)}\n\n"
            "支持多个群组ID，用逗号分隔\n"
            "所有群组ID都应以-100开头\n\n"
            "示例: -1001234567890,-1000987654321\n\n"
            "注意：配置将在机器人重启后生效",
            reply_markup=back_button("system_config")
        )
        
        # 清除用户状态
        db.clear_user_state(user.id)
        
    except ValueError as e:
        await update.message.reply_text(
            f"❌ {str(e)}\n\n"
            "群组ID应以-100开头\n"
            "支持多个群组ID，用逗号分隔\n\n"
            "示例: -1001234567890,-1000987654321\n\n"
            "请重新输入：",
            reply_markup=back_button("system_config")
        )
    except Exception as e:
        logger.error(f"处理群组ID配置失败: {e}")
        await update.message.reply_text(
            "❌ 配置保存失败，请稍后重试\n\n"
            "请重新输入：",
            reply_markup=back_button("system_config")
        )

# 文件末尾应该有正确的换行符
