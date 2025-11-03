# handlers/reviewer_application.py
"""
审核员申请处理模块
处理审核员申请相关功能
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from database import db
from keyboards import back_button
from config import ADMIN_IDS, MANAGEMENT_GROUP_ID  # 修改为 MANAGEMENT_GROUP_ID

# 时间工具函数
from utils.time_utils import get_beijing_now

logger = logging.getLogger(__name__)

async def apply_reviewer_callback(update: Update, context: CallbackContext):
    """加入管理群回调
    
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
    
    # 使用数据库会话检查是否已经是审核员
    with db.session_scope() as session:
        from database import ReviewerApplication
        existing_app = session.query(ReviewerApplication).filter_by(user_id=user.id).first()
        
        if existing_app is not None and getattr(existing_app, 'status', None) == 'approved':
            # 在会话范围内访问属性
            app_id = existing_app.id
            
            # 检查用户是否已经在管理群中
            already_in_group = False
            try:
                chat_member = await context.bot.get_chat_member(MANAGEMENT_GROUP_ID, user.id)
                if chat_member.status in ['member', 'administrator', 'creator']:
                    already_in_group = True
            except Exception as e:
                # 如果获取群成员信息失败，假设用户不在群中
                logger.warning(f"检查用户群成员状态失败: {e}")
                pass
            
            # 审核员可以重新生成邀请链接，即使已经在管理群中
            message_text = "✅ 您已经是审核员了！\n\n"
            if already_in_group:
                message_text += "您已在管理群中，但可以重新生成邀请链接分享给其他用户：\n\n"
            else:
                message_text += "您可以生成邀请链接加入管理群组：\n\n"
                
            await query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 生成邀请链接", callback_data=f"generate_invite_{app_id}")],
                    [InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]
                ])
            )
            return
    
    # 检查申请条件
    stats = db.get_user_submission_stats(user.id)
    
    # 计算加入天数 - 使用安全的属性访问方式
    join_days = 0
    with db.session_scope() as session:
        from database import User as UserModel
        user_info = session.query(UserModel).filter_by(user_id=user.id).first()
        first_interaction = getattr(user_info, 'first_interaction', None) if user_info else None
        if user_info and first_interaction:
            try:
                join_days = (get_beijing_now() - first_interaction).days
            except Exception as date_error:
                logger.warning(f"计算加入天数失败: {date_error}")
                join_days = 0
    
    # 检查条件
    conditions = {
        "join_days": join_days >= 30,
        "submission_count": stats['total'] >= 3,
        "approval_rate": stats['approval_rate'] >= 70 if stats['total'] > 0 else False
    }
    
    # 如果条件不满足，显示原因
    if not all(conditions.values()):
        reason_text = "❌ 您目前不符合审核员申请条件：\n\n"
        
        if not conditions["join_days"]:
            reason_text += f"• 加入时间不足30天（当前：{join_days}天）\n"
        if not conditions["submission_count"]:
            reason_text += f"• 投稿数量不足3篇（当前：{stats['total']}篇）\n"
        if not conditions["approval_rate"]:
            reason_text += f"• 投稿通过率不足70%（当前：{stats['approval_rate']:.1f}%）\n"
        
        reason_text += "\n请满足条件后再申请。"
        
        await query.edit_message_text(
            reason_text,
            reply_markup=back_button("main_menu")
        )
        return
    
    # 检查是否已经申请过但还在等待审核
    with db.session_scope() as session:
        from database import ReviewerApplication
        existing_app = session.query(ReviewerApplication).filter_by(
            user_id=user.id, 
            status='pending'
        ).first()
        
        if existing_app:
            await query.edit_message_text(
                "⏳ 您已提交过加入管理群申请，请等待管理员审核。",
                reply_markup=back_button("main_menu")
            )
            return
    
    # 设置状态等待输入申请理由
    db.set_user_state(user.id, "reviewer_application_reason")
    
    await query.edit_message_text(
        "📝 申请加入管理群\n\n"
        "您已满足申请条件：\n"
        f"• 加入时间: {join_days}天 ✓\n"
        f"• 投稿数量: {stats['total']}篇 ✓\n"
        f"• 通过率: {stats['approval_rate']:.1f}% ✓\n\n"
        "请简要说明您申请加入管理群的理由（至少50个字）：",
        reply_markup=back_button("main_menu")
    )

async def handle_reviewer_application_reason(update: Update, context: CallbackContext):
    """处理加入管理群申请理由输入
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
        
    if update.message is None:
        return
        
    text = update.message.text
    if text is None:
        return
    
    # 检查字数是否足够
    if len(text) < 50:
        await update.message.reply_text(
            "❌ 申请理由太短，请至少输入50个字。\n\n"
            "请重新输入您的加入管理群理由：",
            reply_markup=back_button("main_menu")
        )
        return
    
    # 获取用户统计数据
    stats = db.get_user_submission_stats(user.id)
    join_days = 0
    with db.session_scope() as session:
        from database import User as UserModel
        user_info = session.query(UserModel).filter_by(user_id=user.id).first()
        first_interaction = getattr(user_info, 'first_interaction', None) if user_info else None
        if user_info and first_interaction:
            try:
                join_days = (get_beijing_now() - first_interaction).days
            except Exception as date_error:
                logger.warning(f"计算加入天数失败: {date_error}")
                join_days = 0
    
    # 添加申请
    app_id = db.add_reviewer_application(user.id, getattr(user, 'username', None) or getattr(user, 'full_name', None) or str(user.id), text)
    
    if app_id is not None:
        # 清除用户状态
        db.clear_user_state(user.id)
        
        # 通知所有管理员
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"👑 新的加入管理群申请\n\n"
                        f"用户: @{getattr(user, 'username', None) or getattr(user, 'full_name', None) or '未知用户'} (ID: {user.id})\n"
                        f"加入时间: {join_days}天\n"
                        f"投稿总数: {stats['total']}\n"
                        f"通过数量: {stats['approved']}\n"
                        f"通过率: {stats['approval_rate']:.1f}%\n\n"
                        f"申请理由:\n{text}\n\n"
                        f"请前往管理员面板处理此申请。"
                    )
                )
            except Exception as e:
                logger.error(f"通知管理员失败: {e}")
        
        await update.message.reply_text(
            "✅ 您的加入管理群申请已提交，请等待管理员审核。",
            reply_markup=back_button("main_menu")
        )
    else:
        await update.message.reply_text(
            "❌ 提交加入管理群申请失败，请稍后再试。",
            reply_markup=back_button("main_menu")
        )

async def generate_invite_callback(update: Update, context: CallbackContext):
    """生成管理群邀请链接回调
    
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
        return
        
    await query.answer()
    
    # 提取申请ID
    app_id = int(data.split('_')[-1])
    
    # 使用数据库会话检查申请
    with db.session_scope() as session:
        from database import ReviewerApplication
        application = session.query(ReviewerApplication).filter_by(id=app_id).first()
        
        # 检查申请是否存在且已批准，并且申请人是当前用户
        if (not application or 
            getattr(application, 'status', None) != 'approved' or 
            getattr(application, 'user_id', None) != user.id):
            await query.edit_message_text("❌ 无效的请求或权限不足。")
            return
    
    # 首先检查用户是否已经在管理群中
    try:
        chat_member = await context.bot.get_chat_member(MANAGEMENT_GROUP_ID, user.id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            # 用户已经在管理群中，不需要生成链接
            await query.edit_message_text(
                "✅ 您已经在管理群中，无需生成新的管理群邀请链接。",
                reply_markup=back_button("main_menu")
            )
            return
    except Exception as e:
        # 如果获取群成员信息失败，假设用户不在群中
        logger.warning(f"检查用户群成员状态失败: {e}")
        # 继续生成链接
    
    # 创建一次性邀请链接
    try:
        # 创建管理群组的邀请链接，设置只能使用一次
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=MANAGEMENT_GROUP_ID,  # 修改为管理群组ID
            member_limit=1
        )
        
        # 更新申请记录中的邀请链接
        db.update_application_invite_link(app_id, invite_link.invite_link)
        
        # 发送邀请链接给用户
        await query.edit_message_text(
            f"🔗 您的管理群邀请链接已生成：\n\n"
            f"{invite_link.invite_link}\n\n"
            f"⚠️ 请注意：\n"
            f"• 此链接只能使用一次\n"
            f"• 请勿分享给他人\n"
            f"• 加入后您将没有邀请其他用户的权限\n"
            f"• 链接将在24小时后失效",
            reply_markup=back_button("main_menu")
        )
        
    except Exception as e:
        logger.error(f"创建邀请链接失败: {e}")
        await query.edit_message_text(
            "❌ 生成管理群邀请链接失败，请稍后再试或联系管理员。",
            reply_markup=back_button("main_menu")
        )