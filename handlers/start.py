# handlers/start.py
"""
启动和主菜单处理模块 - 机器人入口点和导航

本模块处理机器人的启动流程和主菜单导航功能：
- /start 命令处理和欢迎消息
- 主菜单显示和导航
- 投稿类型选择菜单
- 商务合作菜单和表单处理
- 帮助和联系信息展示

设计原则：
- 简洁明了的用户界面
- 清晰的功能导航结构
- 个性化的用户体验
- 高效的交互响应

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

# =====================================================
# 外部库导入 External Library Imports
# =====================================================

# Python 标准库
import logging

# Telegram Bot API 组件
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# 项目配置和数据库
from config import ADMIN_IDS, UNLOCK_LINK
from database import db

# 键盘布局组件
from keyboards import main_menu, back_button, submission_type_menu, business_menu, business_form_menu

# 工具函数
from utils.logging_utils import log_user_activity
from utils.time_utils import get_beijing_now
from utils.helpers import check_membership

# 初始化日志器
logger = logging.getLogger(__name__)

# =====================================================
# 命令处理函数 Command Handler Functions
# =====================================================

async def start(update: Update, context) -> None:
    """处理 /start 命令
    
    当用户首次启动机器人或使用 /start 命令时触发
    执行用户注册、权限检查和欢迎消息发送
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 记录用户活动
    log_user_activity(user.id, user.username, "BOT_START", "User started the bot")
    
    # 检查用户是否被封禁
    try:
        with db.session_scope() as session:
            from database import User
            user_record = session.query(User).filter_by(user_id=user.id).first()
            if user_record is not None and getattr(user_record, 'is_banned', False):
                if update.message is not None:
                    await update.message.reply_text("🚫 您已被管理员封禁，无法使用本机器人功能。")
                return
    except Exception as e:
        logger.error(f"检查用户封禁状态失败: {e}")
    
    # 检查用户是否已加入指定的群组和频道
    is_member, where = await check_membership(update, context, user.id)
    if not is_member:
        # 用户未加入必需的群组或频道，显示加入提示
        from keyboards import membership_check_menu
        if update.message is not None:
            menu = membership_check_menu(where)  # type: ignore
            await update.message.reply_text(
                "👋 欢迎使用投稿机器人！\n\n"
                "为了维护社区秩序，使用本机器人需要您加入我们的群组和频道。\n\n"
                "请先加入以下群组和频道，然后点击「我已加入」按钮：",
                reply_markup=menu
            )
        return
    
    # 检查用户是否已在数据库中，如果不在则添加
    db.add_or_update_user(user)
    
    # 构建欢迎消息
    welcome_text = (
        "👋 欢迎使用投稿机器人！\n\n"
        "在这里您可以：\n"
        "📤 发布文字、图片、视频等内容\n"
        "🤝 申请商务合作\n"
        "👤 查看个人中心和投稿历史\n"
        "❓ 获取帮助信息\n\n"
        "请选择您要进行的操作："
    )
    
    # 判断用户是否为管理员或审核员
    from handlers.admin import is_reviewer_or_admin
    is_admin_user = is_reviewer_or_admin(user.id)
    
    # 显示主菜单
    if update.message is not None:
        menu = await main_menu(user.id, is_admin_user, context)  # type: ignore
        await update.message.reply_text(
            welcome_text,
            reply_markup=menu
        )

async def help_command(update: Update, context) -> None:
    """处理 /help 命令
    
    显示机器人使用帮助信息
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 记录用户活动
    log_user_activity(user.id, user.username, "HELP_REQUEST", "User requested help")
    
    help_text = (
        "📖 机器人使用帮助\n\n"
        "📌 基本操作：\n"
        "• 使用 /start 命令重新打开主菜单\n"
        "• 点击菜单按钮进行相应操作\n"
        "• 遇到问题可联系管理员\n\n"
        "📝 投稿说明：\n"
        "• 支持文字、图片、视频投稿\n"
        "• 文字投稿不少于10个字符\n"
        "• 图片和视频需清晰无违规内容\n\n"
        "🤝 商务合作：\n"
        "• 提供公司/个人名称\n"
        "• 填写有效联系方式\n"
        "• 详细描述合作内容\n\n"
        "⚠️ 注意事项：\n"
        "• 请勿发布违法不良信息\n"
        "• 遵守社区规范和法律法规\n"
        "• 违规用户将被封禁处理"
    )
    
    if update.message is not None:
        menu = back_button("main_menu")  # type: ignore
        await update.message.reply_text(help_text, reply_markup=menu)

async def support_command(update: Update, context) -> None:
    """处理 /support 命令
    
    显示技术支持信息和联系方式
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 记录用户活动
    log_user_activity(user.id, user.username, "SUPPORT_REQUEST", "User requested support")
    
    support_text = (
        "🛠️ 技术支持\n\n"
        "如遇到使用问题，请联系技术支持：\n"
        f"🔗 {UNLOCK_LINK}\n\n"
        "或者发送邮件至：\n"
        "📧 support@example.com\n\n"
        "我们会在24小时内回复您的问题。"
    )
    
    if update.message is not None:
        menu = back_button("main_menu")  # type: ignore
        await update.message.reply_text(support_text, reply_markup=menu)

async def contact_command(update: Update, context) -> None:
    """处理 /contact 命令
    
    显示联系管理员信息
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 记录用户活动
    log_user_activity(user.id, user.username, "CONTACT_REQUEST", "User requested contact")
    
    contact_text = (
        "📞 联系我们\n\n"
        "如需联系管理员，请通过以下方式：\n"
        f"🔗 {UNLOCK_LINK}\n\n"
        "或者发送邮件至：\n"
        "📧 admin@example.com\n\n"
        "感谢您的反馈和建议！"
    )
    
    if update.message is not None:
        menu = back_button("main_menu")  # type: ignore
        await update.message.reply_text(contact_text, reply_markup=menu)

# =====================================================
# 回调处理函数 Callback Handler Functions
# =====================================================

async def main_menu_callback(update: Update, context) -> None:
    """主菜单回调处理
    
    处理用户点击主菜单按钮的回调请求
    
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
    
    # 检查用户是否被封禁
    try:
        with db.session_scope() as session:
            from database import User
            user_record = session.query(User).filter_by(user_id=user.id).first()
            if user_record is not None and getattr(user_record, 'is_banned', False):
                await query.answer("您已被封禁，无法使用此功能", show_alert=True)
                return
    except Exception as e:
        logger.error(f"检查用户封禁状态失败: {e}")
    
    # 判断用户是否为管理员或审核员
    from handlers.admin import is_reviewer_or_admin
    is_admin_user = is_reviewer_or_admin(user.id)
    
    # 显示主菜单
    menu = await main_menu(user.id, is_admin_user, context)  # type: ignore
    await query.edit_message_text(
        "请选择您要进行的操作：",
        reply_markup=menu
    )

async def submission_menu_callback(update: Update, context) -> None:
    """投稿菜单回调处理
    
    处理用户点击投稿菜单按钮的回调请求
    
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
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            # 用户被封禁，检查封禁状态
            ban_status = db.check_ban_status(user.id)
            if ban_status["is_banned"]:
                ban_message = "您已被永久封禁，无法使用此功能" if ban_status.get("type") == "permanent" else "您已被封禁，无法使用此功能"
                await query.answer(ban_message, show_alert=True)
                return
    
    await query.answer()
    
    # 获取用户的匿名状态
    state, state_data = db.get_user_state(user.id)
    is_anonymous = state_data.get("anonymous", False) if state_data else False
    
    # 显示投稿类型菜单
    menu = submission_type_menu(is_anonymous)  # type: ignore
    await query.edit_message_text(
        "请选择投稿类型：",
        reply_markup=menu
    )

async def media_menu_callback(update: Update, context) -> None:
    """媒体菜单回调处理函数
    
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
    with db.session_scope() as session:
        from database import User
        user_record = session.query(User).filter_by(user_id=user.id).first()
        if user_record and getattr(user_record, 'is_banned', False):
            # 用户被封禁，检查封禁状态
            ban_status = db.check_ban_status(user.id)
            if ban_status["is_banned"]:
                ban_message = "您已被永久封禁，无法使用此功能" if ban_status.get("type") == "permanent" else "您已被封禁，无法使用此功能"
                await query.answer(ban_message, show_alert=True)
                return
        
    await query.answer()
    
    # 直接进入混合媒体投稿流程
    from handlers.submission import start_unified_media_submission
    await start_unified_media_submission(update, context)

async def business_menu_callback(update: Update, context) -> None:
    """商务合作菜单回调处理
    
    处理用户点击商务合作菜单按钮的回调请求
    
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
    
    # 初始化商务合作表单数据
    if context.user_data is not None:
        context.user_data['business_form'] = {
            'name': '',
            'contact': '',
            'description': ''
        }
    
    # 显示商务合作菜单
    form_data = context.user_data.get('business_form', {}) if context.user_data else {}
    menu = business_form_menu(form_data)  # type: ignore
    await query.edit_message_text(
        "🤝 商务合作申请\n\n"
        "请填写以下信息：",
        reply_markup=menu  # type: ignore
    )