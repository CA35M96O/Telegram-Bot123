# handlers/history.py
"""
历史投稿管理功能模块

本模块处理历史投稿的查看和管理功能，包括：
- 历史投稿查看
- 已发布投稿的重新发布和删除

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

import logging
import json
import re
import time
import asyncio

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

from config import ADMIN_IDS, CHANNEL_IDS, GROUP_IDS
from database import db

from keyboards import (
    back_button,                   # 返回按钮
    history_review_panel_menu,     # 历史审核面板菜单
)

from utils.helpers import (
    show_history_submission,       # 显示历史投稿
    publish_submission,            # 发布投稿
    show_submission                # 显示投稿（从review.py导入）
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

# 添加缺失的处理函数
async def history_submissions_callback(update: Update, context: CallbackContext):
    """历史投稿回调"""
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
        # 修复：移除async关键字，因为session_scope是同步上下文管理器
        with db.session_scope() as session:
            from database import Submission  
            # 修复：只查询已审核的投稿（非pending状态）
            submissions = session.query(Submission).filter(Submission.status != 'pending').order_by(Submission.timestamp.desc()).limit(1000).all()
            
            if not submissions:
                try:
                    await query.edit_message_text("暂无投稿记录", reply_markup=back_button("admin_panel"))
                except:
                    try:
                        await query.answer("暂无投稿记录")
                    except:
                        pass
                return
            
            submissions_data = []
            for sub in submissions:
                # 提取所有属性值
                sub_data = {
                    'id': getattr(sub, 'id'),
                    'user_id': getattr(sub, 'user_id'),
                    'username': getattr(sub, 'username'),
                    'type': getattr(sub, 'type'),
                    'content': getattr(sub, 'content'),
                    'file_id': getattr(sub, 'file_id'),
                    'file_ids': json.loads(getattr(sub, 'file_ids', '[]')) if getattr(sub, 'file_ids') else [],
                    'file_types': json.loads(getattr(sub, 'file_types', '[]')) if hasattr(sub, 'file_types') and getattr(sub, 'file_types') else [],
                    'tags': json.loads(getattr(sub, 'tags', '[]')) if getattr(sub, 'tags') else [],
                    'status': getattr(sub, 'status'),
                    'category': getattr(sub, 'category'),
                    'anonymous': getattr(sub, 'anonymous'),
                    'cover_index': getattr(sub, 'cover_index'),
                    'reject_reason': getattr(sub, 'reject_reason'),
                    'handled_by': getattr(sub, 'handled_by'),
                    'handled_at': getattr(sub, 'handled_at'),
                    'timestamp': getattr(sub, 'timestamp'),
                    'published_message_id': getattr(sub, 'published_message_id', None),
                    'published_channel_message_ids': json.loads(getattr(sub, 'published_channel_message_ids', '[]')) if getattr(sub, 'published_channel_message_ids') else [],
                    'published_group_message_ids': json.loads(getattr(sub, 'published_group_message_ids', '[]')) if getattr(sub, 'published_group_message_ids') else [],
                }
                submissions_data.append(sub_data)
            
            # 修复：检查context.user_data是否存在
            if context.user_data is not None:
                context.user_data['history_submissions'] = submissions_data
                context.user_data['history_index'] = 0
            else:
                logger.warning("context.user_data is None, unable to store history data")
            
            # 显示第一个投稿
            try:
                await show_history_submission(context, submissions_data[0], getattr(user, 'id'), 0, len(submissions_data))
            except Exception as e:
                logger.error(f"显示历史投稿失败: {e}")
                try:
                    await query.answer("❌ 显示投稿失败")
                except:
                    pass
                return
    except Exception as e:
        logger.error(f"获取历史投稿失败: {e}")  
        await query.edit_message_text("获取历史投稿失败")


# =====================================================
# 历史投稿管理功能处理器 History Management Function Handlers
# =====================================================

async def handle_history_page(update: Update, context: CallbackContext):
    """处理历史投稿分页回调
    
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
    
    # 检查是否是跳转到页面的回调
    if data.startswith("jump_to_page_history_"):
        # 解析当前索引和总数
        parts = data.split("_")
        if len(parts) >= 5:
            current_index = int(parts[4])
            total = int(parts[5]) if len(parts) > 5 else 0
            
            # 提示用户输入页码
            if context.user_data is not None:
                context.user_data['jump_page_type'] = 'history'
                context.user_data['total_pages'] = total
            await query.answer()
            await query.edit_message_text(
                f"请输入页码 (1-{total}):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ 取消", callback_data=f"history_{current_index}")
                ]])
            )
            return
    
    # 修复：修改正则表达式以正确匹配回调数据格式
    match = re.match(r'^history_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    index = int(match.group(1))
    if context.user_data is None:
        await query.answer("操作已过期")
        return
        
    submissions = context.user_data.get('history_submissions', []) if context.user_data else []
    
    if not submissions:
        await query.answer("没有历史稿件")
        return
    
    # 修复：添加索引范围检查
    if index >= len(submissions):
        await query.answer("页码超出范围")
        return
    
    if context.user_data is not None:
        context.user_data['history_index'] = index
    submission = submissions[index]
    
    # 修复：添加await关键字
    await show_history_submission(context, submission, user.id, index, len(submissions))
    await query.answer()


# 添加处理跳转页面输入的函数
async def handle_jump_to_page_input(update: Update, context: CallbackContext):
    """处理跳转到页面的输入"""
    user = update.effective_user
    if user is None:
        return
    
    # 检查是否处于跳转页面状态
    if context.user_data is None:
        # 不在跳转状态，不处理
        return
        
    jump_type = context.user_data.get('jump_page_type') if context.user_data else None
    total_pages = context.user_data.get('total_pages', 0) if context.user_data else 0
    
    if not jump_type or total_pages <= 0:
        # 不在跳转状态，不处理
        return
    
    if update.message is None or update.message.text is None:
        return
    
    try:
        # 获取用户输入的页码
        page_number = int(update.message.text)
        
        # 验证页码范围
        if page_number < 1 or page_number > total_pages:
            await update.message.reply_text(f"页码超出范围，请输入 1 到 {total_pages} 之间的数字。")
            return
        
        # 计算索引（页码从1开始，索引从0开始）
        index = page_number - 1
        
        # 根据类型处理跳转
        if jump_type == 'review':
            pending = context.user_data.get('pending_submissions', []) if context.user_data else []
            if not pending:
                await update.message.reply_text("没有待审稿件")
                return
            
            if index >= len(pending):
                await update.message.reply_text("页码超出范围")
                return
            
            if context.user_data is not None:
                context.user_data['current_index'] = index
            submission = pending[index]
            # 修复：从正确模块导入show_submission
            from utils.helpers import show_submission
            await show_submission(context, submission, user.id, index, len(pending))
        
        elif jump_type == 'history':
            submissions = context.user_data.get('history_submissions', []) if context.user_data else []
            if not submissions:
                await update.message.reply_text("没有历史稿件")
                return
            
            if index >= len(submissions):
                await update.message.reply_text("页码超出范围")
                return
            
            if context.user_data is not None:
                context.user_data['history_index'] = index
            submission = submissions[index]
            await show_history_submission(context, submission, user.id, index, len(submissions))
        
        # 清除跳转状态
        if context.user_data is not None:
            context.user_data.pop('jump_page_type', None)
            context.user_data.pop('total_pages', None)
        
    except ValueError:
        await update.message.reply_text("请输入有效的数字页码。")


async def handle_contact_user_callback(update: Update, context: CallbackContext):
    """处理联系用户回调"""
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
    
    # 修复：修改正则表达式以匹配正确的回调数据格式
    match = re.match(r'^contact_user_(\d+)$', data)
    if not match:
        # 如果无法从回调数据中解析用户ID，则尝试从历史投稿数据中获取
        if context.user_data is None:
            await query.answer("操作已过期")
            return
            
        submissions = context.user_data.get('history_submissions', [])
        history_index = context.user_data.get('history_index', 0)
        
        if history_index >= len(submissions):
            await query.answer("数据错误")
            return
            
        submission = submissions[history_index]
        target_user_id = submission['user_id']
    else:
        target_user_id = int(match.group(1))
    
    try:
        await query.answer()
        await query.edit_message_text(
            text=(
                f"📞 联系用户\n\n"
                f"用户ID: {target_user_id}\n\n"
                "📋 联系方式：\n"
                f"• 使用用户ID: {target_user_id}\n\n"
                "💡 提示：点击下方按钮可直接发起私聊"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "💬 发起私聊", 
                    url=f"tg://user?id={target_user_id}"
                )],
                [InlineKeyboardButton(
                    "📋 复制用户ID", 
                    callback_data=f"copy_user_id_{target_user_id}"
                )],
                [InlineKeyboardButton(
                    "🔙 返回历史投稿", 
                    callback_data="history_submissions"
                )]
            ])
        )
    except Exception as e:
        logger.error(f"发送联系用户消息失败: {e}")
        # 检查是否是 Button_user_invalid 错误
        if "Button_user_invalid" in str(e):
            try:
                await query.answer("❌ 无法联系用户：用户可能已删除账号或屏蔽了机器人", show_alert=True)
            except Exception as answer_error:
                logger.error(f"发送联系用户错误消息失败: {answer_error}")
        else:
            try:
                await query.answer("❌ 联系功能暂时不可用，请手动联系用户", show_alert=True)
            except Exception as answer_error:
                logger.error(f"发送联系用户消息也失败: {answer_error}")

async def handle_history_view_videos(update: Update, context: CallbackContext):
    """
    处理查看历史投稿中的所有视频回调（混合媒体专用）
    
    这个函数专门用于处理混合媒体投稿中的视频查看。
    它会从投稿的所有文件中筛选出视频文件并发送给管理员。
    
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
    
    match = re.match(r'^history_view_videos_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    sub_id = int(match.group(1))
    
    # 修复：移除async关键字，因为session_scope是同步上下文管理器
    with db.session_scope() as session:
        from database import Submission
        submission = session.query(Submission).filter_by(id=sub_id).first()
        
        if not submission or not getattr(submission, 'file_ids'):
            await query.answer("❌ 投稿无效或无媒体文件")
            return
        
        try:
            file_ids = json.loads(getattr(submission, 'file_ids', '[]')) if getattr(submission, 'file_ids') else []
            file_types = json.loads(getattr(submission, 'file_types', '[]')) if hasattr(submission, 'file_types') and getattr(submission, 'file_types') else []
            
            # 筛选出视频文件
            video_files = []
            for i, file_id in enumerate(file_ids):
                # 如果有 file_types 信息，使用它来判断
                if i < len(file_types) and file_types[i] == 'video':
                    # 验证文件ID是否有效
                    if file_id and isinstance(file_id, str) and len(file_id) > 0:
                        video_files.append(file_id)
                else:
                    # 如果没有 file_types 信息，尝试通过文件信息判断
                    try:
                        file_obj = await context.bot.get_file(file_id)
                        file_path = getattr(file_obj, 'file_path') or ""
                        if any(ext in file_path.lower() for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']):
                            # 验证文件ID是否有效
                            if file_id and isinstance(file_id, str) and len(file_id) > 0:
                                video_files.append(file_id)
                    except Exception:
                        # 如果无法判断，且主类型是 video，则假设是视频
                        if getattr(submission, 'type') == "video":
                            # 验证文件ID是否有效
                            if file_id and isinstance(file_id, str) and len(file_id) > 0:
                                video_files.append(file_id)
            
            if len(video_files) == 0:
                await query.answer("❌ 此投稿中没有视频文件")
                return
            
            # 先响应回调查询，避免查询过期
            await query.answer(f"正在发送{len(video_files)}个视频文件...")
            
            # 发送所有视频文件
            for i, file_id in enumerate(video_files):
                try:
                    await context.bot.send_video(
                        chat_id=getattr(user, 'id'),
                        video=file_id,
                        caption=f"历史投稿 #{sub_id} 的视频 {i+1}/{len(video_files)}"
                    )
                    # 减少延迟以避免发送太快
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"发送视频文件失败: {e}")
                    # 如果发送失败，记录错误但继续发送其他文件
                    continue
        except Exception as e:
            logger.error(f"处理视频文件失败: {e}")
            await query.answer("❌ 处理失败")

async def handle_history_view_photos(update: Update, context: CallbackContext):
    """处理查看历史投稿中的所有图片回调
    
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
        try:
            await query.answer("无效的操作")
        except:
            pass
        return
    
    # 匹配两种格式的回调数据: view_extra_photos_123 和 history_view_photos_123
    match = re.match(r'^(?:view_extra|history_view)_photos_(\d+)$', data)
    if not match:
        try:
            await query.answer("无效的操作")
        except:
            pass
        return
        
    sub_id = int(match.group(1))
    
    try:
        # 修复：移除async关键字，因为session_scope是同步上下文管理器
        with db.session_scope() as session:
            from database import Submission
            submission = session.query(Submission).filter_by(id=sub_id).first()
            
            if not submission:
                try:
                    await query.answer("❌ 投稿不存在")
                except:
                    pass
                return
                
            # 使用getattr安全获取属性
            submission_type = getattr(submission, 'type', '')
            file_ids_attr = getattr(submission, 'file_ids', None)
            
            if not submission_type or submission_type not in ["photo", "video", "media"] or not file_ids_attr:
                try:
                    await query.answer("❌ 投稿无效或无媒体文件")
                except:
                    pass
                return
            
            try:
                file_ids = json.loads(file_ids_attr) if file_ids_attr else []
                file_types = json.loads(getattr(submission, 'file_types', '[]')) if hasattr(submission, 'file_types') and getattr(submission, 'file_types') else []
                
                if len(file_ids) <= 0:
                    try:
                        await query.answer("❌ 没有媒体文件")
                    except:
                        pass
                    return
                
                # 检查是否为混合媒体投稿
                is_mixed_media = False
                if file_types:
                    has_photos = 'photo' in file_types
                    has_videos = 'video' in file_types
                    is_mixed_media = has_photos and has_videos
                
                # 筛选要发送的文件
                files_to_send = []
                if is_mixed_media:
                    # 混合媒体投稿：只发送图片
                    for i, file_id in enumerate(file_ids):
                        if i < len(file_types) and file_types[i] == 'photo':
                            # 验证文件ID是否有效
                            if file_id and isinstance(file_id, str) and len(file_id) > 0:
                                files_to_send.append(file_id)
                else:
                    # 单一类型投稿：发送所有文件
                    for file_id in file_ids:
                        # 验证文件ID是否有效
                        if file_id and isinstance(file_id, str) and len(file_id) > 0:
                            files_to_send.append(file_id)
                
                if len(files_to_send) == 0:
                    media_type = "图片" if is_mixed_media else ("图片" if submission_type == "photo" else "视频")
                    try:
                        await query.answer(f"❌ 此投稿中没有{media_type}文件")
                    except:
                        pass
                    return
                
                # 先响应回调查询，避免查询过期
                media_type = "图片" if is_mixed_media or submission_type == "photo" or (submission_type == "media" and not is_mixed_media) else "视频"
                try:
                    await query.answer(f"正在发送{media_type}文件...")
                except:
                    pass  # 忽略响应错误
                
                # 发送文件
                for i, file_id in enumerate(files_to_send):
                    try:
                        if is_mixed_media or submission_type == "photo" or (submission_type == "media" and not is_mixed_media):
                            await context.bot.send_photo(
                                chat_id=getattr(user, 'id'),
                                photo=file_id,
                                caption=f"历史投稿 #{sub_id} 的图片 {i+1}/{len(files_to_send)}"
                            )
                        else:
                            await context.bot.send_video(
                                chat_id=getattr(user, 'id'),
                                video=file_id,
                                caption=f"历史投稿 #{sub_id} 的视频 {i+1}/{len(files_to_send)}"
                            )
                        # 减少延迟以避免发送太快
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.error(f"发送媒体文件失败: {e}")
                        # 如果发送失败，记录错误但继续发送其他文件
                        continue
            except Exception as e:
                logger.error(f"处理媒体文件失败: {e}")
                try:
                    await query.answer("❌ 处理失败")
                except:
                    pass
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        try:
            await query.answer("❌ 数据库错误")
        except:
            pass

def _delete_published_content(context, submission):
    """删除已发布的内容
    
    Args:
        context: Telegram context 对象
        submission: 投稿对象
        
    Returns:
        int: 删除的消息数量
    """
    deleted_count = 0
    
    try:
        # 删除频道中的消息
        if submission.published_message_id:
            try:
                context.bot.delete_message(
                    chat_id=CHANNEL_IDS[0],
                    message_id=int(submission.published_message_id)
                )
                deleted_count += 1
                logger.info(f"已删除频道消息 {submission.published_message_id}")
            except Exception as e:
                if "message to delete not found" in str(e).lower():
                    logger.info(f"频道消息 {submission.published_message_id} 已不存在，无需删除")
                elif "message can't be deleted" in str(e).lower():
                    logger.warning(f"没有权限删除频道消息 {submission.published_message_id}")
                else:
                    logger.warning(f"删除频道消息 {submission.published_message_id} 失败: {e}")
        
        # 删除群组中的消息
        if submission.published_group_message_ids:
            try:
                message_ids = json.loads(submission.published_group_message_ids)
                for message_id in message_ids:
                    try:
                        context.bot.delete_message(
                            chat_id=GROUP_IDS[0],  # 假设只删除第一个群组中的消息
                            message_id=int(message_id)
                        )
                        deleted_count += 1
                        logger.info(f"已删除群组消息 {message_id}")
                    except Exception as e:
                        if "message to delete not found" in str(e).lower():
                            logger.info(f"群组消息 {message_id} 已不存在，无需删除")
                        elif "message can't be deleted" in str(e).lower():
                            logger.warning(f"没有权限删除群组消息 {message_id}")
                        else:
                            logger.warning(f"删除群组消息 {message_id} 失败: {e}")
            except Exception as e:
                logger.warning(f"解析群组消息ID列表失败: {e}")
                
    except Exception as e:
        logger.error(f"删除已发布内容失败: {e}")
    
    return deleted_count

async def delete_published_submission_callback(update: Update, context: CallbackContext):
    """删除已发布投稿回调
    
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
    
    # 解析投稿ID
    match = re.match(r'^delete_submission_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    submission_id = int(match.group(1))
    
    # 先回答回调查询，避免超时
    try:
        await query.answer("🔄 正在删除投稿...")
    except Exception as e:
        logger.warning(f"回答回调查询失败: {e}")
    
    try:
        # 修复：移除async关键字，因为session_scope是同步上下文管理器
        with db.session_scope() as session:
            from database import Submission
            submission = session.query(Submission).filter_by(id=submission_id).first()
            
            if not submission:
                await query.answer("❌ 投稿不存在", show_alert=True)
                return
            
            # 删除已发布到频道和群组的内容
            deleted_count = _delete_published_content(context, submission)
            
            # 不再删除数据库记录，只清除已发布消息ID
            setattr(submission, 'published_message_id', None)
            setattr(submission, 'published_group_message_ids', '[]')
            session.commit()
            
            await query.answer(f"✅ 已删除 {deleted_count} 条已发布内容，数据库记录已保留", show_alert=True)
            
            # 返回到历史投稿列表
            # 重新加载历史投稿列表
            # 修复：只查询已审核的投稿（非pending状态）
            submissions = session.query(Submission).filter(Submission.status != 'pending').order_by(Submission.timestamp.desc()).limit(1000).all()
            
            if not submissions:
                await query.edit_message_text("暂无投稿记录", reply_markup=back_button("admin_panel"))
                return
            
            submissions_data = []
            for sub in submissions:
                try:
                    file_ids = json.loads(getattr(sub, 'file_ids', '[]')) if getattr(sub, 'file_ids') else []
                except:
                    file_ids = []
                
                try:
                    tags = json.loads(getattr(sub, 'tags', '[]')) if getattr(sub, 'tags') else []
                except:
                    tags = []
                    
                try:
                    file_types = json.loads(getattr(sub, 'file_types', '[]')) if hasattr(sub, 'file_types') and getattr(sub, 'file_types') else []
                except:
                    file_types = []
                
                submission_data = {
                    'id': getattr(sub, 'id'),
                    'user_id': getattr(sub, 'user_id'),
                    'username': getattr(sub, 'username'),
                    'type': getattr(sub, 'type'),
                    'content': getattr(sub, 'content'),
                    'file_id': getattr(sub, 'file_id'),
                    'file_ids': file_ids,
                    'file_types': file_types,
                    'tags': tags,
                    'status': getattr(sub, 'status'),
                    'category': getattr(sub, 'category'),
                    'anonymous': getattr(sub, 'anonymous'),
                    'cover_index': getattr(sub, 'cover_index'),
                    'reject_reason': getattr(sub, 'reject_reason'),
                    'handled_by': getattr(sub, 'handled_by'),
                    'handled_at': getattr(sub, 'handled_at'),
                    'timestamp': getattr(sub, 'timestamp')
                }
                submissions_data.append(submission_data)
            
            if context.user_data is not None:
                context.user_data['history_submissions'] = submissions_data
                context.user_data['history_index'] = 0
            
            # 修复：添加await关键字
            await show_history_submission(context, submissions_data[0], user.id, 0, len(submissions_data))
            
    except Exception as e:
        logger.error(f"删除投稿失败: {e}")
        # 尝试发送错误消息给用户
        try:
            await query.answer("❌ 删除投稿失败，请稍后重试", show_alert=True)
        except:
            pass

async def republish_submission_callback(update: Update, context: CallbackContext):
    """重新发布投稿回调
    
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
    
    # 解析投稿ID
    match = re.match(r'^republish_submission_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    submission_id = int(match.group(1))
    
    # 先回答回调查询，避免超时
    try:
        await query.answer("🔄 正在重新发布投稿...")
    except Exception as e:
        if "Query is too old" in str(e):
            logger.debug("回调查询已超时，继续执行重新发布操作")
        else:
            logger.warning(f"回答回调查询失败: {e}")
    
    try:
        # 修复：移除async关键字，因为session_scope是同步上下文管理器
        with db.session_scope() as session:
            from database import Submission
            submission = session.query(Submission).filter_by(id=submission_id).first()
            
            if not submission:
                # 尝试编辑消息，如果失败则发送新消息
                try:
                    await query.edit_message_text("❌ 投稿不存在", reply_markup=back_button("admin_panel"))
                except Exception as e:
                    if "Query is too old" in str(e):
                        logger.debug("回调查询已超时，无法编辑消息")
                        await context.bot.send_message(
                            chat_id=user.id,
                            text="❌ 投稿不存在",
                            reply_markup=back_button("admin_panel")
                        )
                    else:
                        logger.warning(f"编辑消息失败: {e}")
                        await context.bot.send_message(
                            chat_id=user.id,
                            text="❌ 投稿不存在",
                            reply_markup=back_button("admin_panel")
                        )
                return
            
            # 检查投稿状态，只有已通过的投稿才能重新发布
            if getattr(submission, 'status') != 'approved':
                try:
                    await query.edit_message_text("❌ 只有已通过的投稿才能重新发布", reply_markup=back_button("admin_panel"))
                except Exception as e:
                    if "Query is too old" in str(e):
                        logger.debug("回调查询已超时，无法编辑消息")
                        await context.bot.send_message(
                            chat_id=user.id,
                            text="❌ 只有已通过的投稿才能重新发布",
                            reply_markup=back_button("admin_panel")
                        )
                    else:
                        logger.warning(f"编辑消息失败: {e}")
                        await context.bot.send_message(
                            chat_id=user.id,
                            text="❌ 只有已通过的投稿才能重新发布",
                            reply_markup=back_button("admin_panel")
                        )
                return
            
            # 重新发布投稿
            try:
                # 准备投稿数据
                try:
                    file_ids = json.loads(getattr(submission, 'file_ids', '[]')) if getattr(submission, 'file_ids') else []
                except:
                    file_ids = []
                
                try:
                    tags = json.loads(getattr(submission, 'tags', '[]')) if getattr(submission, 'tags') else []
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
                    'cover_index': getattr(submission, 'cover_index'),
                    'reject_reason': getattr(submission, 'reject_reason'),
                    'handled_by': getattr(submission, 'handled_by'),
                    'handled_at': getattr(submission, 'handled_at'),
                    'timestamp': getattr(submission, 'timestamp')
                }
                
                # 发布投稿
                await publish_submission(context, submission_data)
                
                # 通知用户
                try:
                    await query.answer("✅ 投稿已重新发布", show_alert=True)
                except Exception as answer_error:
                    if "Query is too old" in str(answer_error):
                        logger.debug("回调查询已超时，忽略答复")
                    else:
                        logger.warning(f"回答回调查询失败: {answer_error}")
                
                # 重新加载历史投稿列表
                # 修复：只查询已审核的投稿（非pending状态）
                submissions = session.query(Submission).filter(Submission.status != 'pending').order_by(Submission.timestamp.desc()).limit(1000).all()
                
                if not submissions:
                    await query.edit_message_text("暂无投稿记录", reply_markup=back_button("admin_panel"))
                    return
                
                submissions_data = []
                for sub in submissions:
                    try:
                        file_ids = json.loads(getattr(sub, 'file_ids', '[]')) if getattr(sub, 'file_ids') else []
                    except:
                        file_ids = []
                    
                    try:
                        tags = json.loads(getattr(sub, 'tags', '[]')) if getattr(sub, 'tags') else []
                    except:
                        tags = []
                        
                    try:
                        file_types = json.loads(getattr(sub, 'file_types', '[]')) if hasattr(sub, 'file_types') and getattr(sub, 'file_types') else []
                    except:
                        file_types = []
                    
                    submission_data = {
                        'id': getattr(sub, 'id'),
                        'user_id': getattr(sub, 'user_id'),
                        'username': getattr(sub, 'username'),
                        'type': getattr(sub, 'type'),
                        'content': getattr(sub, 'content'),
                        'file_id': getattr(sub, 'file_id'),
                        'file_ids': file_ids,
                        'file_types': file_types,
                        'tags': tags,
                        'status': getattr(sub, 'status'),
                        'category': getattr(submission, 'category'),
                        'anonymous': getattr(submission, 'anonymous'),
                        'cover_index': getattr(submission, 'cover_index'),
                        'reject_reason': getattr(submission, 'reject_reason'),
                        'handled_by': getattr(submission, 'handled_by'),
                        'handled_at': getattr(submission, 'handled_at'),
                        'timestamp': getattr(submission, 'timestamp')
                    }
                    submissions_data.append(submission_data)
                
                if context.user_data is not None:
                    context.user_data['history_submissions'] = submissions_data
                    context.user_data['history_index'] = 0
                
                # 修复：添加await关键字
                await show_history_submission(context, submissions_data[0], user.id, 0, len(submissions_data))
                
            except Exception as e:
                logger.error(f"重新发布投稿失败: {e}")
                try:
                    await query.answer("❌ 重新发布投稿失败，请稍后重试", show_alert=True)
                except:
                    pass
    except Exception as e:
        logger.error(f"处理重新发布投稿请求失败: {e}")
        # 尝试发送错误消息给用户
        try:
            await query.answer("❌ 处理请求失败，请稍后重试", show_alert=True)
        except:
            pass
