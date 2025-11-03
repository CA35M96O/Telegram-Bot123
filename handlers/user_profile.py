# handlers/user_profile.py
"""
个人中心处理模块
处理用户个人中心相关功能
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from database import db
from keyboards import user_profile_menu, back_button
from utils.time_utils import get_beijing_now

logger = logging.getLogger(__name__)

async def user_profile_callback(update: Update, context: CallbackContext):
    """个人中心回调
    
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
    
    # 使用数据库会话获取用户信息和投稿统计
    with db.session_scope() as session:
        from database import User
        user_info = session.query(User).filter_by(user_id=user.id).first()
        
        if not user_info:
            await query.edit_message_text("用户信息不存在")
            return
        
        # 计算加入天数
        join_days = 0
        first_interaction = getattr(user_info, 'first_interaction', None)
        if first_interaction:
            try:
                from utils.time_utils import to_beijing_time
                # 确保first_interaction是北京时间
                first_interaction_beijing = to_beijing_time(first_interaction)
                join_days = (get_beijing_now() - first_interaction_beijing).days
            except Exception as date_error:
                logger.warning(f"计算加入天数失败: {date_error}")
                join_days = 0
        
        # 获取投稿统计
        stats = db.get_user_submission_stats(user.id)
        
        # 获取用户身份信息
        from handlers.admin import is_admin, is_reviewer
        user_role = "👑 管理员" if is_admin(user.id) else ("✅ 审核员" if is_reviewer(user.id) else "普通用户")
        
        # 获取WxPusher UID信息
        wxpusher_uid = getattr(user_info, 'wxpusher_uid', None)
        wxpusher_status = "已设置" if wxpusher_uid else "未设置"
        
        profile_text = (
            f"👤 个人中心\n\n"
            f"🆔 用户ID: {user.id}\n"
            f"👤 用户名: @{user.username or '无'}\n"
            f"📛 姓名: {user.full_name}\n"
            f"💼 身份: {user_role}\n"
            f"📅 加入天数: {join_days}天\n"
            f"🔔 微信推送: {wxpusher_status}\n\n"
            f"📊 投稿统计:\n"
            f"• 总投稿数: {stats['total']}\n"
            f"• 已通过: {stats['approved']}\n"
            f"• 待审核: {stats['pending']}\n"
            f"• 已拒绝: {stats['rejected']}\n"
            f"• 通过率: {stats['approval_rate']:.1f}%"
        )
        
        await query.edit_message_text(
            profile_text,
            reply_markup=user_profile_menu()  # type: ignore
        )

async def my_submission_stats_callback(update: Update, context: CallbackContext):
    """我的投稿统计回调
    
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
    
    with db.session_scope() as session:
        from database import Submission
        
        # 获取用户的所有投稿
        submissions = session.query(Submission).filter_by(user_id=user.id).order_by(
            Submission.timestamp.desc()
        ).all()
        
        if not submissions:
            await query.edit_message_text(
                "您还没有任何投稿记录",
                reply_markup=back_button("user_profile")  # type: ignore
            )
            return
        
        # 按类型统计
        text_count = session.query(Submission).filter_by(
            user_id=user.id, 
            type='text'
        ).count()
        
        photo_count = session.query(Submission).filter_by(
            user_id=user.id, 
            type='photo'
        ).count()
        
        video_count = session.query(Submission).filter_by(
            user_id=user.id, 
            type='video'
        ).count()
        
        business_count = session.query(Submission).filter_by(
            user_id=user.id, 
            category='business'
        ).count()
        
        stats = db.get_user_submission_stats(user.id)
        
        stats_text = (
            f"📊 您的投稿统计\n\n"
            f"📝 文本投稿: {text_count}\n"
            f"🖼 图片投稿: {photo_count}\n"
            f"🎬 视频投稿: {video_count}\n"
            f"🤝 商务合作: {business_count}\n\n"
            f"✅ 已通过: {stats['approved']}\n"
            f"⏳ 待审核: {stats['pending']}\n"
            f"❌ 已拒绝: {stats['rejected']}\n"
            f"📈 通过率: {stats['approval_rate']:.1f}%"
        )
        
        await query.edit_message_text(
            stats_text,
            reply_markup=back_button("user_profile")
        )

async def wxpusher_settings_callback(update: Update, context: CallbackContext):
    """WxPusher推送设置回调
    
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
    
    # 获取用户当前的WxPusher UID
    with db.session_scope() as session:
        from database import User
        user_info = session.query(User).filter_by(user_id=user.id).first()
        
        if not user_info:
            await query.edit_message_text("用户信息不存在")
            return
        
        wxpusher_uid = getattr(user_info, 'wxpusher_uid', None) or ""
        
        settings_text = (
            "🔔 WxPusher微信推送设置\n\n"
            "通过WxPusher服务，您可以将重要的通知推送到您的微信上。\n\n"
            "操作步骤：\n"
            "1. 关注WxPusher公众号\n"
            "2. 获取您的UID\n"
            "3. 在下方输入您的UID\n\n"
            "当前状态: " + ("已设置" if wxpusher_uid else "未设置")
        )
        
        # 使用新的菜单函数
        from keyboards import wxpusher_settings_menu
        menu = wxpusher_settings_menu(wxpusher_uid)
        
        await query.edit_message_text(
            settings_text,
            reply_markup=menu  # type: ignore
        )

async def set_wxpusher_uid_callback(update: Update, context: CallbackContext):
    """设置WxPusher UID回调
    
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
    
    # 设置用户状态为等待输入WxPusher UID
    db.set_user_state(user.id, "enter_wxpusher_uid", {})
    
    # 获取用户当前的WxPusher UID
    with db.session_scope() as session:
        from database import User
        user_info = session.query(User).filter_by(user_id=user.id).first()
        
        if not user_info:
            await query.edit_message_text("用户信息不存在")
            return
        
        wxpusher_uid = getattr(user_info, 'wxpusher_uid', None) or ""
        
        instruction_text = (
            "📝 请输入您的WxPusher UID\n\n"
            "如何获取UID：\n"
            "1. 关注WxPusher公众号\n"
            "2. 在公众号中回复「uid」获取\n"
            "3. 将获取到的UID发送给我\n\n"
            "当前UID: " + (wxpusher_uid if wxpusher_uid else "未设置") + "\n\n"
            "请直接发送UID给我，或点击下方取消按钮。"
        )
        
        # 创建取消按钮
        keyboard = [
            [InlineKeyboardButton("❌ 取消", callback_data="wxpusher_settings")]
        ]
        
        await query.edit_message_text(
            instruction_text,
            reply_markup=InlineKeyboardMarkup(keyboard)  # type: ignore
        )

async def handle_wxpusher_uid_input(update: Update, context: CallbackContext):
    """处理用户输入的WxPusher UID
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    if update.message is None or update.message.text is None:
        return
    
    # 获取用户状态
    state, state_data = db.get_user_state(user.id)
    state_check = bool(state is None or state != "enter_wxpusher_uid")
    if state_check:
        return
    
    # 获取输入的UID
    wxpusher_uid = update.message.text.strip()
    
    # 验证UID格式（简单验证）
    if len(wxpusher_uid) < 10:  # UID通常比较长
        await update.message.reply_text(
            "❌ UID格式似乎不正确，请重新输入或点击取消按钮返回。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ 取消", callback_data="wxpusher_settings")]
            ])  # type: ignore
        )
        return
    
    # 保存到数据库
    with db.session_scope() as session:
        from database import User
        session.query(User).filter_by(user_id=user.id).update({
            'wxpusher_uid': wxpusher_uid
        })
        session.commit()
    
    # 清除用户状态
    db.clear_user_state(user.id)
    
    # 通知用户设置成功
    await update.message.reply_text(
        f"✅ WxPusher UID设置成功！\n\n"
        f"您现在可以通过微信接收重要通知了。\n"
        f"UID: {wxpusher_uid}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 返回个人中心", callback_data="user_profile")]
        ])  # type: ignore
    )

async def test_wxpusher_callback(update: Update, context: CallbackContext):
    """测试WxPusher推送功能
    
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
    
    # 获取用户当前的WxPusher UID
    with db.session_scope() as session:
        from database import User
        user_info = session.query(User).filter_by(user_id=user.id).first()
        
        if not user_info:
            await query.edit_message_text("用户信息不存在")
            return
        
        wxpusher_uid = getattr(user_info, 'wxpusher_uid', None)
        
        # 检查是否设置了UID
        if not wxpusher_uid:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ 设置UID", callback_data="set_wxpusher_uid")],
                [InlineKeyboardButton("🔙 返回", callback_data="wxpusher_settings")]
            ])
            await query.edit_message_text(
                "❌ 您尚未设置WxPusher UID，请先设置UID再进行测试。",
                reply_markup=keyboard  # type: ignore
            )
            return
        
        # 导入测试函数
        from utils.wxpusher import test_wxpusher_notification
        
        # 发送测试通知
        success = test_wxpusher_notification([wxpusher_uid])
        
        if success:
            message_text = "✅ 测试消息已成功发送！\n\n请检查您的微信是否收到了推送通知。"
        else:
            message_text = "❌ 测试消息发送失败！\n\n请检查以下几点：\n1. UID是否正确\n2. 是否已关注WxPusher公众号\n3. 网络连接是否正常"
        
        # 添加时间戳以确保消息内容不同
        message_text += f"\n\n🕒 最后测试时间: {datetime.now().strftime('%H:%M:%S')}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 重新测试", callback_data="test_wxpusher")],
            [InlineKeyboardButton("✏️ 重新设置UID", callback_data="set_wxpusher_uid")],
            [InlineKeyboardButton("🔙 返回", callback_data="wxpusher_settings")]
        ])
        try:
            await query.edit_message_text(
                message_text,
                reply_markup=keyboard  # type: ignore
            )
        except Exception as e:
            logger.error(f"更新测试结果消息失败: {e}")
            # 如果更新消息失败，发送新消息
            # 检查 query.message 是否存在
            if query.message is not None:
                await query.message.reply_text(
                    message_text,
                    reply_markup=keyboard  # type: ignore
                )
            else:
                # 如果 query.message 不存在，尝试通过 context.bot 发送消息
                try:
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=message_text,
                        reply_markup=keyboard  # type: ignore
                    )
                except Exception as send_error:
                    logger.error(f"发送新消息也失败了: {send_error}")
                    await query.answer("操作完成，但无法更新消息界面，请重新打开功能界面。")
