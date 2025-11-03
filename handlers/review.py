# handlers/review.py
"""
投稿审核功能模块

本模块处理投稿的审核流程，包括：
- 待审稿件查看和处理
- 历史投稿管理
- 审核员申请处理

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
import re
import time
from datetime import datetime

# Telegram Bot API 组件
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from telegram.constants import ParseMode

from utils.helpers import publish_submission, show_submission
from utils.time_utils import get_beijing_now
from utils.logging_utils import log_admin_operation
from config import ADMIN_IDS
from database import db
from keyboards import back_button

from keyboards import (
    review_panel_menu,              # 审核面板菜单
    history_review_panel_menu,      # 历史审核面板菜单
    back_button,                    # 返回按钮
    reviewer_applications_menu,     # 审核员申请菜单
)

from utils.helpers import (
    show_submission,                # 显示投稿内容
    show_history_submission,        # 显示历史投稿
    publish_submission,             # 发布投稿
    safe_answer_callback_query      # 安全的回调查询处理
)

from utils.logging_utils import log_user_activity, log_admin_operation, log_system_event, log_submission_event
from utils.time_utils import get_beijing_now, format_beijing_time

# 初始化日志器
logger = logging.getLogger(__name__)

# 用户状态常量定义
STATE_REJECT_REASON = "reject_reason"      # 拒绝原因输入状态

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
# 面板功能处理器 Panel Function Handlers
# =====================================================

async def admin_panel_callback(update: Update, context: CallbackContext):
    """管理员面板回调"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    if not is_reviewer_or_admin(user.id):
        await query.answer("⚠️ 您不是管理员或审核员", show_alert=True)
        return
    
    await query.answer()
    try:
        if is_admin(user.id):
            from keyboards import admin_panel_menu
            await query.edit_message_text(
                "⚙️ 管理员面板\n请选择操作：",
                reply_markup=admin_panel_menu()
            )
        else:
            # 获取审核员权限设置
            from database import db
            permissions = db.get_reviewer_permissions(user.id)
            from keyboards import reviewer_panel_menu_custom
            await query.edit_message_text(
                "📋 审核员面板\n请选择操作：",
                reply_markup=reviewer_panel_menu_custom(permissions)  # type: ignore  # type: ignore
            )
    except Exception as e:
        if "Message is not modified" in str(e):
            # 如果消息未修改，则只需应答查询
            pass
        elif "message is not modified" in str(e).lower():
            # 处理不同大小写的情况
            pass
        else:
            # 如果是其他错误，则重新抛出
            raise

async def _check_reviewer_permission(query, user_id):
    """检查审核员权限
    
    Args:
        query: 回调查询对象
        user_id: 用户ID
        
    Returns:
        bool: 有权限返回True
    """
    if not is_reviewer_or_admin(user_id):
        await query.answer("⚠️ 您没有权限", show_alert=True)
        return False
    return True

def _get_pending_count():
    """获取待审稿件数量
    
    Returns:
        int: 待审稿件数量
    """
    try:
        return db.get_pending_submissions_count()
    except AttributeError:
        # 备用方法1
        logger.warning("使用备用计数方法1")
        try:
            return db.get_pending_submissions_count()
        except Exception as e1:
            logger.error(f"备用方法1也失败: {e1}")
            # 备用方法2: 直接查询
            try:
                with db.session_scope() as session:
                    from database import Submission
                    return session.query(Submission).filter_by(status='pending').count()
            except Exception as e2:
                logger.error(f"备用方法2也失败: {e2}")
                return 0
    except Exception as e:
        logger.error(f"获取待审稿件数量失败: {e}")
        # 最后的备用方法: 直接查询
        try:
            with db.session_scope() as session:
                from database import Submission
                return session.query(Submission).filter_by(status='pending').count()
        except Exception as e2:
            logger.error(f"最终备用方法也失败: {e2}")
            return 0

def _get_pending_submissions_data():
    """获取待审稿件数据
    
    Returns:
        list: 待审稿件数据列表
    """
    try:
        # 尝试使用优化方法
        pending_submissions = db.get_pending_submissions_paginated(limit=20, offset=0)
        return _extract_submission_data_batch(pending_submissions)
    except AttributeError:
        # 备用方法1: 使用get_pending_submissions
        logger.warning("使用备用查询方法1")
        try:
            pending_submissions = db.get_pending_submissions()
            # 限制数量为20个
            return _extract_submission_data_batch(pending_submissions[:20])
        except Exception as e1:
            logger.error(f"备用方法1也失败: {e1}")
            # 备用方法2: 直接查询
            try:
                with db.session_scope() as session:
                    from database import Submission
                    pending = session.query(Submission).filter_by(status='pending').limit(20).all()
                    return _extract_submission_data_batch(pending)
            except Exception as e2:
                logger.error(f"备用方法2也失败: {e2}")
                return []
    except Exception as e:
        logger.error(f"获取待审稿件数据失败: {e}")
        # 最后的备用方法: 直接查询
        try:
            with db.session_scope() as session:
                from database import Submission
                pending = session.query(Submission).filter_by(status='pending').limit(20).all()
                return _extract_submission_data_batch(pending)
        except Exception as e2:
            logger.error(f"最终备用方法也失败: {e2}")
            return []

async def _handle_no_pending_submissions(query):
    """处理无待审稿件情况
    
    Args:
        query: 回调查询对象
    """
    await query.answer()
    await query.edit_message_text(
        "🎉 没有待审稿件！",
        reply_markup=back_button("admin_panel")
    )

def _setup_pending_context(context, pending_data, pending_count):
    """设置待审稿件上下文
    
    Args:
        context: Telegram context对象
        pending_data: 待审稿件数据
        pending_count: 待审稿件总数
    """
    context.user_data['pending_submissions'] = pending_data
    context.user_data['current_index'] = 0
    context.user_data['total_pending'] = pending_count

def _safe_json_loads(json_str, default=None):
    """安全的JSON解析
    
    Args:
        json_str: JSON字符串
        default: 默认值
        
    Returns:
        解析结果或默认值
    """
    if not json_str:
        return default or []
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default or []

def _extract_submission_data_batch(submissions):
    """批量提取投稿数据 - 内部函数
    
    优化点：
    1. 批量处理JSON解析
    2. 错误处理集中化
    3. 内存优化
    
    Args:
        submissions: 投稿列表
        
    Returns:
        list: 处理后的投稿数据
    """
    pending_data = []
    
    for submission_data in submissions:
        try:
            # 由于数据已在数据库层提取，这里只需处理JSON解析
            file_ids = _safe_json_loads(submission_data.get('file_ids'), [])
            tags = _safe_json_loads(submission_data.get('tags'), [])
            file_types = _safe_json_loads(submission_data.get('file_types'), [])
            
            # 构建最终数据结构
            processed_data = {
                'id': submission_data['id'],
                'user_id': submission_data['user_id'],
                'username': submission_data['username'],
                'type': submission_data['type'],
                'content': submission_data['content'],
                'file_id': submission_data['file_id'],
                'file_ids': file_ids,
                'file_types': file_types,
                'tags': tags,
                'status': submission_data['status'],
                'category': submission_data['category'],
                'anonymous': submission_data['anonymous'],
                'cover_index': submission_data['cover_index'] or 0,
                'reject_reason': submission_data['reject_reason'],
                'handled_by': submission_data['handled_by'],
                'handled_at': submission_data['handled_at'],
                'timestamp': submission_data['timestamp']
            }
            pending_data.append(processed_data)
        except Exception as e:
            logger.error(f"处理投稿数据失败: {e}")
            continue
    
    return pending_data

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
                        await query.edit_message_text(
                            "🎉 没有待审稿件！",
                            reply_markup=back_button("admin_panel")
                        )
                    except Exception as e:
                        logger.error(f"发送无待审稿件消息失败: {e}")
                return
            
            for submission in pending:
                try:
                    # 由于数据已在数据库层提取，这里直接使用
                    file_ids = _safe_json_loads(getattr(submission, 'file_ids', None), [])
                    tags = _safe_json_loads(getattr(submission, 'tags', None), [])
                    file_types = _safe_json_loads(getattr(submission, 'file_types', None), [])
                    
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
                except Exception as e:
                    logger.error(f"处理投稿 {getattr(submission, 'id', 'unknown')} 数据失败: {e}")
                    continue
        
        if context.user_data is not None:
            context.user_data['pending_submissions'] = pending_data
            context.user_data['current_index'] = 0
            context.user_data['total_pending'] = len(pending_data)
        
        if pending_data and query is not None:
            try:
                await show_submission(context, pending_data[0], user.id, 0, len(pending_data))
                logger.info("使用备用方法成功处理管理员面板请求")
            except Exception as e:
                logger.error(f"显示投稿失败: {e}")
                if query is not None:
                    try:
                        await query.answer("系统错误，请稍后再试", show_alert=True)
                    except:
                        pass
        elif query is not None:
            try:
                await query.answer()
                await query.edit_message_text(
                    "🎉 没有待审稿件！",
                    reply_markup=back_button("admin_panel")
                )
            except Exception as e:
                logger.error(f"发送无待审稿件消息失败: {e}")
        
    except Exception as fallback_error:
        logger.error(f"备用方法也失败: {fallback_error}")
        if query is not None:
            try:
                await query.answer("系统错误，请稍后再试", show_alert=True)
            except:
                pass  # 忽略应答错误

# =====================================================
# 审核功能处理器 Review Function Handlers
# =====================================================

async def admin_pending_callback(update: Update, context: CallbackContext):
    """管理员查看待审稿件回调"""
    query = update.callback_query
    if query is None:
        return
        
    user = query.from_user
    if user is None:
        return
    
    # 权限检查
    if not await _check_reviewer_permission(query, user.id):
        return
    
    try:
        # 检查待审稿件
        pending_count = _get_pending_count()
        if pending_count == 0:
            await _handle_no_pending_submissions(query)
            return
        
        # 获取待审稿件数据
        pending_data = _get_pending_submissions_data()
        if not pending_data:
            await _handle_no_pending_submissions(query)
            return
        
        # 设置用户上下文并显示首个投稿
        _setup_pending_context(context, pending_data, pending_count)
        await show_submission(context, pending_data[0], user.id, 0, len(pending_data))
        
    except Exception as e:
        logger.error(f"管理员面板错误: {e}")
        await _admin_pending_fallback(update, context)

async def handle_review_page(update: Update, context: CallbackContext):
    """处理分页查看回调"""
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
    if data.startswith("jump_to_page_review_"):
        # 解析当前索引和总数
        parts = data.split("_")
        if len(parts) >= 5:
            current_index = int(parts[4])
            total = int(parts[5]) if len(parts) > 5 else 0
            
            # 提示用户输入页码
            if context.user_data is not None:
                context.user_data['jump_page_type'] = 'review'
                context.user_data['total_pages'] = total
            await query.answer()
            await query.edit_message_text(
                f"请输入页码 (1-{total}):",
                reply_markup=InlineKeyboardMarkup([[  # type: ignore
                    InlineKeyboardButton("❌ 取消", callback_data=f"review_{current_index}")
                ]])  # type: ignore
            )
            return
    
    match = re.match(r'^review_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    index = int(match.group(1))
    if context.user_data is None:
        await query.answer("操作已过期")
        return
        
    pending = context.user_data.get('pending_submissions', []) if context.user_data else []
    
    if not pending:
        await query.answer("没有待审稿件")
        return
    
    if context.user_data is not None:
        context.user_data['current_index'] = index
    submission = pending[index]
    
    await show_submission(context, submission, user.id, index, len(pending))
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

async def handle_review_callback(update: Update, context: CallbackContext):
    """处理审核操作回调"""
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
    
    match = re.match(r'^(approve|reject|contact)_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    action = match.group(1)
    sub_id = int(match.group(2))
    
    with db.session_scope() as session:
        from database import Submission
        submission = session.query(Submission).filter_by(id=sub_id).first()
        
        if not submission:
            await query.answer("❌ 投稿不存在")
            return
        
        submission_status = getattr(submission, 'status', 'pending')
        if submission_status and submission_status != 'pending':
            await query.answer(f"❌ 此投稿已经是{ '已通过' if submission_status == 'approved' else '已拒绝' }状态")
            return
        
        if action == "approve":
            # 获取投稿数据用于检查关键词
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
            
            # 设置用户状态为输入关键词
            logger.info(f"[DEBUG] Setting user state for user {user.id} to enter_publish_keyword with sub_id {sub_id}")
            db.set_user_state(user.id, "enter_publish_keyword", {"sub_id": sub_id, "immediate_publish": True})
            
            try:
                await query.answer()
            except Exception as answer_error:
                if "Query is too old" in str(answer_error):
                    logger.debug("回调查询已超时，忽略答复")
                else:
                    logger.warning(f"回答回调查询失败: {answer_error}")
            
            await query.edit_message_text(
                text=f"🔑 发布投稿 #{sub_id}\n\n请输入发布关键词以确认发布（将替换内容末尾【关键词】中的内容）：",
                reply_markup=InlineKeyboardMarkup([  # type: ignore
                    [InlineKeyboardButton("❌ 取消发布", callback_data=f"cancel_publish_{sub_id}")]
                ])  # type: ignore
            )
            return
        
        elif action == "reject":
            db.set_user_state(user.id, STATE_REJECT_REASON, {"sub_id": sub_id, "handler_id": user.id})
            
            try:
                await query.answer()
            except Exception as answer_error:
                if "Query is too old" in str(answer_error):
                    logger.debug("回调查询已超时，忽略答复")
                else:
                    logger.warning(f"回答回调查询失败: {answer_error}")
            
            await query.edit_message_text(
                "❌ 拒绝投稿\n\n请填写拒绝原因（将发送给用户）：",
                reply_markup=InlineKeyboardMarkup([  # type: ignore
                    [InlineKeyboardButton("🔙 取消", callback_data=f"cancel_reject_{sub_id}")]
                ])  # type: ignore
            )
            
        elif action == "contact":
            user_id = getattr(submission, 'user_id')
            username = getattr(submission, 'username')
            
            try:
                await query.answer()
            except Exception as answer_error:
                if "Query is too old" in str(answer_error):
                    logger.debug("回调查询已超时，忽略答复")
                else:
                    logger.warning(f"回答回调查询失败: {answer_error}")
            
            try:
                await query.edit_message_text(
                    text=(
                        f"📞 联系用户\n\n"
                        f"投稿ID: #{sub_id}\n"
                        f"用户: @{username}\n"
                        f"用户ID: {user_id}\n\n"
                        "📋 联系方式：\n"
                        f"• 直接点击用户名: @{username}\n"
                        f"• 使用用户ID: {user_id}\n\n"
                        "💡 提示：点击下方按钮可直接发起私聊"
                    ),
                    reply_markup=InlineKeyboardMarkup([  # type: ignore
                        [InlineKeyboardButton(
                            "💬 发起私聊", 
                            url=f"https://t.me/{username}" if username else f"tg://user?id={user_id}"
                        )],
                        [InlineKeyboardButton(
                            "📋 复制用户ID", 
                            callback_data=f"copy_user_id_{user_id}"
                        )],
                        [InlineKeyboardButton(
                            "🔙 返回审核", 
                            callback_data=f"review_{context.user_data.get('current_index', 0) if context.user_data else 0}"
                        )]
                    ])  # type: ignore
                )
            except Exception as send_error:
                logger.error(f"发送联系用户消息失败: {send_error}")
                # 检查是否是 Button_user_invalid 错误
                if "Button_user_invalid" in str(send_error):
                    try:
                        await query.answer("❌ 无法联系用户：用户可能已删除账号或屏蔽了机器人", show_alert=True)
                    except Exception as answer_error:
                        logger.error(f"发送联系用户错误消息失败: {answer_error}")
                else:
                    try:
                        await query.answer("❌ 联系功能暂时不可用，请手动联系用户", show_alert=True)
                    except Exception as answer_error:
                        logger.error(f"发送联系用户消息也失败: {answer_error}")
                        await query.answer("❌ 联系功能暂时不可用，请手动联系用户", show_alert=True)

async def handle_copy_user_id_callback(update: Update, context: CallbackContext):
    """处理复制用户ID回调"""
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
    
    match = re.match(r'^copy_user_id_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    user_id = match.group(1)
    
    await query.answer(
        text=f"用户ID: {user_id}\n\n💡 长按此消息可复制ID",
        show_alert=True
    )

async def handle_view_extra_videos(update: Update, context: CallbackContext):
    """处理查看待审投稿中的所有视频回调（混合媒体专用）
    
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
    
    # 匹配两种格式的回调数据: view_extra_videos_123 和 history_view_videos_123
    match = re.match(r'^(?:view_extra|history_view)_videos_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    sub_id = int(match.group(1))
    
    with db.session_scope() as session:
        from database import Submission
        submission = session.query(Submission).filter_by(id=sub_id).first()
        
        if not submission:
            await query.answer("❌ 投稿不存在")
            return
            
        # 使用getattr安全获取属性值
        submission_type = getattr(submission, 'type', '')
        file_ids_attr = getattr(submission, 'file_ids', None)
        
        if not submission_type or submission_type not in ["photo", "video", "media"] or not file_ids_attr:
            await query.answer("❌ 投稿无效或无媒体文件")
            return
        
        try:
            file_ids = json.loads(file_ids_attr) if file_ids_attr else []
            file_types = json.loads(getattr(submission, 'file_types', '[]')) if hasattr(submission, 'file_types') and getattr(submission, 'file_types') else []
            
            # 筛选出视频文件
            video_files = []
            for i, file_id in enumerate(file_ids):
                # 对于media类型，检查file_types；对于其他类型，根据投稿类型判断
                if submission_type == "media":
                    if i < len(file_types) and file_types[i] == 'video':
                        # 验证文件ID是否有效
                        if file_id and isinstance(file_id, str) and len(file_id) > 0:
                            video_files.append(file_id)
                else:
                    # 非media类型投稿
                    if submission_type == "video":
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
                        caption=f"投稿 #{sub_id} 的视频 {i+1}/{len(video_files)}"
                    )
                    time.sleep(0.5)  # 避免发送太快
                except Exception as e:
                    logger.error(f"发送视频文件失败: {e}")
                    # 如果发送失败，记录错误但继续发送其他文件
                    continue
        except Exception as e:
            logger.error(f"处理视频文件失败: {e}")
            await query.answer("❌ 处理失败")

async def handle_view_extra_photos(update: Update, context: CallbackContext):
    """处理查看全部媒体回调
    
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
    
    # 匹配两种格式的回调数据: view_extra_photos_123 和 history_view_photos_123
    match = re.match(r'^(?:view_extra|history_view)_photos_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    sub_id = int(match.group(1))
    
    with db.session_scope() as session:
        from database import Submission
        submission = session.query(Submission).filter_by(id=sub_id).first()
        
        if not submission:
            await query.answer("❌ 投稿不存在")
            return
            
        # 使用getattr安全获取属性值
        submission_type = getattr(submission, 'type', '')
        file_ids_attr = getattr(submission, 'file_ids', None)
        
        if not submission_type or submission_type not in ["photo", "video", "media"] or not file_ids_attr:
            await query.answer("❌ 投稿无效或无媒体文件")
            return
        
        try:
            file_ids = json.loads(file_ids_attr) if file_ids_attr else []
            file_types = json.loads(getattr(submission, 'file_types', '[]')) if hasattr(submission, 'file_types') and getattr(submission, 'file_types') else []
            
            if len(file_ids) <= 0:
                await query.answer("❌ 没有媒体文件")
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
                await query.answer(f"❌ 此投稿中没有{media_type}文件")
                return
            
            # 先响应回调查询，避免查询过期
            media_type = "图片" if submission_type == "photo" or (submission_type == "media" and not is_mixed_media) or is_mixed_media else "视频"
            await query.answer(f"正在发送{media_type}文件...")
            
            # 发送文件
            for i, file_id in enumerate(files_to_send):
                try:
                    if submission_type == "photo" or (submission_type == "media" and not is_mixed_media) or is_mixed_media:
                        await context.bot.send_photo(
                            chat_id=getattr(user, 'id'),
                            photo=file_id,
                            caption=f"投稿 #{sub_id} 的图片 {i+1}/{len(files_to_send)}"
                        )
                    else:  # 单一视频类型
                        await context.bot.send_video(
                            chat_id=getattr(user, 'id'),
                            video=file_id,
                            caption=f"投稿 #{sub_id} 的视频 {i+1}/{len(files_to_send)}"
                        )
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"发送媒体文件失败: {e}")
                    # 如果发送失败，记录错误但继续发送其他文件
                    continue
        except Exception as e:
            logger.error(f"处理媒体文件失败: {e}")
            await query.answer("❌ 处理失败")

async def cancel_reject_callback(update: Update, context: CallbackContext):
    """取消拒绝操作回调
    
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
    
    match = re.match(r'^cancel_reject_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    sub_id = int(match.group(1))
    
    db.clear_user_state(user.id)
    
    await query.answer("已取消拒绝操作")
    await query.edit_message_text(
        "❌ 拒绝操作已取消",
        reply_markup=back_button("admin_panel")
    )

async def handle_reject_reason(update: Update, context: CallbackContext, text: str):
    """处理拒绝原因输入
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
        text: 拒绝原因文本
    """
    user = update.effective_user
    if user is None:
        return
    
    if not is_reviewer_or_admin(user.id):
        return
    
    state, state_data = db.get_user_state(user.id)
    
    # 修复条件判断问题 - 使用正确的逻辑判断用户状态
    state_valid = (state is not None) and (str(state) == str(STATE_REJECT_REASON))
    state_data_valid = (state_data is not None) and ("sub_id" in state_data)
    if not (state_valid and state_data_valid):
        if update.message is not None:
            await update.message.reply_text("操作已过期")
        return
    
    sub_id = state_data["sub_id"]
    handler_id = state_data.get("handler_id", user.id)
    
    with db.session_scope() as session:
        from database import Submission
        submission = session.query(Submission).filter_by(id=sub_id).first()
        if submission:
            setattr(submission, 'status', "rejected")
            setattr(submission, 'reject_reason', text)
            setattr(submission, 'handled_by', handler_id)
            setattr(submission, 'handled_at', get_beijing_now())
            session.commit()
            
            try:
                await context.bot.send_message(
                    chat_id=getattr(submission, 'user_id'),
                    text=f"❌ 您的投稿 #{sub_id} 已被拒绝\n\n原因: {text}"
                )
            except Exception as e:
                logger.error(f"通知用户失败: {e}")
    
    db.clear_user_state(user.id)
    
    if update.message is not None:
        await update.message.reply_text(
            f"✅ 投稿 #{sub_id} 已拒绝",
            reply_markup=back_button("admin_panel")
        )

async def reviewer_applications_callback(update: Update, context: CallbackContext):
    """审核员申请列表回调 - 重构优化版本
    
    拆分出的子功能：
    1. 权限检查
    2. 申请数据获取
    3. 用户信息格式化
    4. 界面显示
    
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
    
    # 权限检查
    if not is_admin(user.id):
        await query.answer("⚠️ 您不是管理员", show_alert=True)
        return
    
    await query.answer()
    
    # 获取申请数据
    applications = db.get_pending_applications()
    if not applications:
        await query.edit_message_text(
            "🎉 没有待处理的加入管理群申请！",
            reply_markup=back_button("admin_panel")
        )
        return
    
    # 设置上下文并显示第一个申请
    if context.user_data is not None:
        context.user_data['reviewer_applications'] = applications
        context.user_data['application_index'] = 0
    app = applications[0]
    
    stats = db.get_user_submission_stats(app.user_id)
    join_days = 0
    with db.session_scope() as session:
        from database import User as UserModel
        user_info = session.query(UserModel).filter_by(user_id=app.user_id).first()
        if user_info is not None and getattr(user_info, 'first_interaction', None) is not None:
            try:
                join_days = (get_beijing_now() - user_info.first_interaction).days
            except Exception as date_error:
                logger.warning(f"计算加入天数失败: {date_error}")
                join_days = 0
    
    text = (
        f"👑 审核员申请 #{app.id}\n\n"
        f"用户: @{app.username} (ID: {app.user_id})\n"
        f"加入时间: {join_days}天\n"
        f"投稿总数: {stats['total']}\n"
        f"通过数量: {stats['approved']}\n"
        f"通过率: {stats['approval_rate']:.1f}%\n\n"
        f"申请时间: {app.timestamp}\n\n"
        f"申请理由:\n{app.reason}\n\n"
        f"请选择操作："
    )
    
    await query.edit_message_text(
        text,
        reply_markup=reviewer_applications_menu(applications, 0)  # type: ignore  # type: ignore
    )

async def handle_application_page(update: Update, context: CallbackContext):
    """处理申请分页回调
    
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
        await query.answer("⚠️ 您没有权限", show_alert=True)
        return
    
    match = re.match(r'^application_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
        
    index = int(match.group(1))
    if context.user_data is None:
        await query.answer("操作已过期")
        return
        
    applications = context.user_data.get('reviewer_applications', [])
    
    if not applications:
        await query.answer("没有申请")
        return
    
    context.user_data['application_index'] = index
    app = applications[index]
    
    stats = db.get_user_submission_stats(app.user_id)
    join_days = 0
    with db.session_scope() as session:
        from database import User as UserModel
        user_info = session.query(UserModel).filter_by(user_id=app.user_id).first()
        if user_info is not None and getattr(user_info, 'first_interaction', None) is not None:
            try:
                join_days = (get_beijing_now() - user_info.first_interaction).days
            except Exception as date_error:
                logger.warning(f"计算加入天数失败: {date_error}")
                join_days = 0
    
    text = (
        f"👑 审核员申请 #{app.id}\n\n"
        f"用户: @{app.username} (ID: {app.user_id})\n"
        f"加入时间: {join_days}天\n"
        f"投稿总数: {stats['total']}\n"
        f"通过数量: {stats['approved']}\n"
        f"通过率: {stats['approval_rate']:.1f}%\n\n"
        f"申请时间: {app.timestamp}\n\n"
        f"申请理由:\n{app.reason}\n\n"
        f"请选择操作："
    )
    
    await query.edit_message_text(
        text,
        reply_markup=reviewer_applications_menu(applications, index)  # type: ignore  # type: ignore
    )
    await query.answer()

async def handle_application_decision(update: Update, context: CallbackContext):
    """处理审核员申请决定
    
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
    
    # 只有管理员可以处理申请
    if not is_admin(user.id):
        await query.answer("🚫 权限不足", show_alert=True)
        return
    
    await query.answer()
    
    data = query.data
    if data is None:
        await query.answer("无效的操作")
        return
    
    # 解析申请ID和操作类型
    import re
    match = re.match(r'^(approve|reject)_application_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    action = match.group(1)
    app_id = int(match.group(2))
    
    if action == "approve":
        # 更新申请状态
        try:
            with db.session_scope() as session:
                from database import ReviewerApplication
                application = session.query(ReviewerApplication).filter_by(id=app_id).first()
                if application:
                    setattr(application, 'status', "approved")
                    setattr(application, 'handled_by', user.id)
                    setattr(application, 'handled_at', get_beijing_now())
                    # 如果申请被批准，创建审核员记录
                    reviewer = ReviewerApplication(
                        user_id=application.user_id,
                        added_by=user.id,
                        permissions='all'
                    )
                    session.add(reviewer)
                    session.commit()
                    await query.answer("✅ 申请已批准", show_alert=True)
                else:
                    await query.answer("❌ 申请不存在", show_alert=True)
        except Exception as e:
            logger.error(f"批准审核员申请失败: {e}")
            await query.answer("❌ 操作失败", show_alert=True)
    else:  # reject
        # 更新申请状态
        try:
            with db.session_scope() as session:
                from database import ReviewerApplication
                application = session.query(ReviewerApplication).filter_by(id=app_id).first()
                if application:
                    setattr(application, 'status', "rejected")
                    setattr(application, 'handled_by', user.id)
                    setattr(application, 'handled_at', get_beijing_now())
                    session.commit()
                    await query.answer("❌ 申请已拒绝", show_alert=True)
                else:
                    await query.answer("❌ 申请不存在", show_alert=True)
        except Exception as e:
            logger.error(f"拒绝审核员申请失败: {e}")
            await query.answer("❌ 操作失败", show_alert=True)
    
    # 返回审核员申请列表
    await reviewer_applications_callback(update, context)

# 在文件中添加处理关键词输入的函数
async def handle_publish_keyword_input(update: Update, context: CallbackContext):
    """处理发布关键词输入"""
    user = update.effective_user
    if user is None:
        return
    
    # 检查用户是否为管理员或审核员
    if not is_reviewer_or_admin(user.id):
        # 非管理员和非审核员用户不处理关键词输入
        logger.info(f"[DEBUG] User {user.id} is not admin or reviewer, ignoring keyword input")
        return
    
    if update.message is None or update.message.text is None:
        # 消息或文本为空，不处理
        return
    
    # 添加调试日志
    logger.info(f"[DEBUG] handle_publish_keyword_input called by user {user.id} with message: {update.message.text}")
    
    # 获取用户状态
    state, state_data = db.get_user_state(user.id)
    logger.info(f"[DEBUG] Current state: {state}, state_data: {state_data}")
    
    if str(state) != "enter_publish_keyword" or not state_data or "sub_id" not in state_data:
        logger.info(f"[DEBUG] Invalid state for user {user.id}, state: {state}")
        return
    
    sub_id = state_data["sub_id"]
    immediate_publish = state_data.get("immediate_publish", False)
    keyword = update.message.text.strip()
    
    logger.info(f"[DEBUG] Keyword: '{keyword}', sub_id: {sub_id}")
    logger.info(f"[DEBUG] Full state_data: {state_data}")
    
    if not sub_id:
        await update.message.reply_text("❌ 无效的投稿ID")
        db.clear_user_state(user.id)  # 清除无效状态
        return
    
    # 检查关键词是否正确
    with db.session_scope() as session:
        from database import Submission
        submission = session.query(Submission).filter_by(id=sub_id).first()
        if not submission:
            await update.message.reply_text("❌ 投稿不存在")
            db.clear_user_state(user.id)  # 清除无效状态
            return
        
        # 获取投稿数据
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
            'timestamp': getattr(submission, 'timestamp'),
            'custom_keyword': keyword  # 添加自定义关键词
        }
        
        # 更新投稿状态为已批准
        setattr(submission, 'status', 'approved')
        setattr(submission, 'handled_by', user.id)
        setattr(submission, 'handled_at', get_beijing_now())
        setattr(submission, 'custom_keyword', keyword)  # 保存自定义关键词
        
        # 如果是立即发布
        if immediate_publish:
            # 立即发布投稿
            from utils.helpers import publish_submission
            try:
                await publish_submission(context, submission_data)
                session.commit()  # 提交数据库更改
                
                # 通知用户投稿已发布
                try:
                    await context.bot.send_message(
                        chat_id=submission_data['user_id'],
                        text=f"✅ 您的投稿 #{sub_id} 已通过审核并成功发布！\n\n感谢您的分享。"
                    )
                except Exception as e:
                    logger.error(f"通知用户投稿发布失败: {e}")
                
                await update.message.reply_text(f"✅ 投稿 #{sub_id} 已立即发布")
            except Exception as e:
                logger.error(f"立即发布投稿失败: {e}")
                await update.message.reply_text(f"❌ 投稿 #{sub_id} 发布失败，请稍后重试")
        else:
            # 定时发布投稿
            from jobs.scheduled_publish import get_next_publish_time
            scheduled_time = get_next_publish_time()
            scheduled_time_str = scheduled_time.strftime('%Y-%m-%d %H:%M')
            
            # 保存定时发布时间
            setattr(submission, 'scheduled_publish_time', scheduled_time)
            session.commit()  # 提交数据库更改
            
            # 通知用户投稿已安排发布
            try:
                await context.bot.send_message(
                    chat_id=submission_data['user_id'],
                    text=f"✅ 您的投稿 #{sub_id} 已通过审核，将在 {scheduled_time_str} 发布！\n\n感谢您的分享。"
                )
            except Exception as e:
                logger.error(f"通知用户投稿定时发布失败: {e}")
            
            await update.message.reply_text(
                f"✅ 投稿 #{sub_id} 已安排在 {scheduled_time_str} 发布"
            )
        
        # 清除用户状态
        db.clear_user_state(user.id)

async def handle_cancel_publish_callback(update: Update, context: CallbackContext):
    """处理取消发布回调"""
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
    
    # 解析投稿ID
    import re
    match = re.match(r'^cancel_publish_(\d+)$', data)
    if not match:
        await query.answer("无效的操作")
        return
    
    sub_id = int(match.group(1))
    
    # 获取投稿信息
    with db.session_scope() as session:
        from database import Submission
        submission = session.query(Submission).filter_by(id=sub_id).first()
        if not submission:
            await query.answer("投稿不存在", show_alert=True)
            return
        
        # 检查投稿状态
        if getattr(submission, 'status') != 'approved':
            await query.answer("只有已批准的投稿才能取消发布", show_alert=True)
            return
        
        # 更新投稿状态为待审核
        setattr(submission, 'status', 'pending')
        setattr(submission, 'handled_by', None)
        setattr(submission, 'handled_at', None)
        setattr(submission, 'custom_keyword', None)
        setattr(submission, 'scheduled_publish_time', None)
        
        try:
            session.commit()
            await query.answer("✅ 发布已取消，投稿状态已重置为待审核", show_alert=True)
        except Exception as e:
            logger.error(f"取消发布失败: {e}")
            await query.answer("❌ 取消发布失败，请稍后重试", show_alert=True)
