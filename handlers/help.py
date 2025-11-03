# handlers/help.py
"""
帮助命令处理模块
处理 /help 命令、投稿引导功能和客服联系功能

新增功能：
- /support 命令：获取客服联系方式
- /contact 命令：同 /support，提供更多联系选项
- 智能客服链接生成
- 服务时间和时区显示
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from keyboards import back_button, main_menu
from config import (
    CUSTOMER_SUPPORT_LINK, 
    CUSTOMER_SUPPORT_USERNAME, 
    CUSTOMER_SUPPORT_NAME,
    CUSTOMER_SUPPORT_HOURS,
    CUSTOMER_SUPPORT_TIMEZONE
)
from utils.logging_utils import log_user_activity

logger = logging.getLogger(__name__)

async def help_command(update: Update, context: CallbackContext):
    """处理 /help 命令
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    help_text = (
        "📥 <b>投稿引导说明</b> 📥\n\n"
        "欢迎使用 <b>投稿机器人</b>！您可以通过本机器人向频道投稿（文字、图片、视频），"
        "也可以提交商务合作申请。以下是详细的使用指南：\n\n"
        
        "🚀 <b>开始投稿</b>\n"
        "1. 打开与机器人的私聊窗口\n"
        "2. 点击 /start 或选择「📤 我要投稿」\n"
        "3. 选择投稿类型：\n"
        "   • <b>📝 文字投稿</b>：纯文本内容\n"
        "   • <b>🎭 混合媒体投稿</b>：支持图片和视频混合上传（最多120个媒体文件）\n\n"
        
        "⚠️ <b>投稿注意事项</b>\n"
        "• 内容中<b>禁止包含任何链接、网址、Telegram用户名或二维码</b>\n"
        "• 图片和视频投稿可添加文字描述（不少于10个字符）\n"
        "• 支持<b>匿名投稿</b>，发布时不显示您的用户名\n"
        "• 所有投稿需经审核，通过后才会发布\n"
        "• 媒体文件会保留原始质量，但可能会有压缩\n"
        "• 请勿包含敏感或违规内容\n\n"
        
        "🤝 <b>商务合作</b>\n"
        "• 选择「🤝 商务合作」填写申请表单\n"
        "• 需提供：\n"
        "  - 公司/个人名称\n"
        "  - 联系方式（Telegram/邮箱/电话等）\n"
        "  - 合作描述\n"
        "• 管理员会尽快与您联系\n\n"
        
        "✅ <b>投稿成功后</b>\n"
        "• 您会收到投稿编号（如 #123）\n"
        "• 可点击「⏰ 催促审核」通知管理员（请勿频繁使用）\n"
        "• 审核通过后会收到通知，内容将发布至频道\n"
        "• 混合媒体投稿会自动分组发布\n\n"
        
        "❓ <b>常见问题</b>\n"
        "<b>Q：投稿后多久能审核？</b>\n"
        "A：通常24小时内，高峰期可能稍长。\n\n"
        "<b>Q：可以修改或撤销投稿吗？</b>\n"
        "A：投稿一旦提交无法修改，如需撤销请联系管理员。\n\n"
        "<b>Q：为什么我的投稿被拒绝了？</b>\n"
        "A：常见原因：含链接、内容不符、图片模糊、重复投稿等。\n\n"
        "<b>Q：如何成为审核员？</b>\n"
        "A：可通过「👑 申请审核员」提交申请，管理员审核通过后会邀请您加入审核群。\n\n"
        
        "📜 <b>隐私说明</b>\n"
        "• 我们不会公开您的用户ID\n"
        "• 匿名投稿不会显示用户名\n"
        "• 投稿内容仅用于频道发布，不会用于其他用途\n"
        "• 媒体文件由Telegram服务器存储，我们只保存文件ID\n\n"
        
        "💡 <b>小贴士</b>\n"
        "• 内容要积极正面，符合社区规范\n"
        "• 图片和视频建议保持清晰，避免模糊\n"
        "• 文字投稿建议控制在合理长度内\n"
        "• 使用 /privacy 查看完整的隐私政策\n\n"
        
        "如有其他问题，请联系管理员或使用 /privacy 查看隐私政策。\n\n"
        "邮件: KENNEL-CN@TUTA.IO "
        "感谢您的使用！🙏"
    )
    
    # 获取正确的消息对象（处理回调查询的情况）
    message = update.message if update.message else (update.callback_query.message if update.callback_query else None)
    
    # 分割消息以避免超过Telegram长度限制
    max_length = 4096
    if len(help_text) <= max_length and message is not None:
        await message.reply_text(
            help_text,
            parse_mode='HTML',
            reply_markup=back_button("main_menu")
        )
    else:
        # 分割消息
        parts = []
        current_part = ""
        
        # 按段落分割
        paragraphs = help_text.split('\n\n')
        
        for paragraph in paragraphs:
            # 如果当前部分加上新段落会超过限制，则开始新的部分
            if len(current_part) + len(paragraph) + 2 > max_length:
                parts.append(current_part)
                current_part = paragraph
            else:
                if current_part:
                    current_part += '\n\n' + paragraph
                else:
                    current_part = paragraph
        
        # 添加最后一部分
        if current_part:
            parts.append(current_part)
        
        # 发送各部分消息
        for i, part in enumerate(parts):
            if i == 0:
                # 第一部分带有返回按钮
                if message is not None:
                    await message.reply_text(
                        part,
                        parse_mode='HTML',
                        reply_markup=back_button("main_menu")
                    )
            else:
                # 后续部分作为回复发送，不带按钮
                if message is not None:
                    await message.reply_text(
                        part,
                        parse_mode='HTML'
                    )

async def support_command(update: Update, context: CallbackContext):
    """处理 /support 命令 - 客服联系功能
    
    功能描述：
    - 提供客服联系链接和用户名
    - 显示服务时间和时区信息
    - 提供多种联系方式选项
    - 记录用户操作日志
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    user = update.effective_user
    if user is None:
        return
    
    # 记录用户访问客服功能的日志
    if user.id is not None and user.username is not None:
        log_user_activity(
            user.id,
            user.username,
            "SUPPORT_COMMAND",
            f"用户访问客服联系功能"
        )
    
    # 构建客服信息文本
    support_text = (
        f"🎆 **{CUSTOMER_SUPPORT_NAME}**\n\n"
        f"📞 **联系方式：**\n"
        f"• 客服用户名：{CUSTOMER_SUPPORT_USERNAME}\n"
        f"• 直接链接：[{CUSTOMER_SUPPORT_NAME}]({CUSTOMER_SUPPORT_LINK})\n\n"
        
        f"🕰 **服务时间：**\n"
        f"• {CUSTOMER_SUPPORT_HOURS} ({CUSTOMER_SUPPORT_TIMEZONE})\n\n"
        
        f"💬 **您可以咨询：**\n"
        f"• 投稿问题和审核进度\n"
        f"• 账号和权限相关问题\n"
        f"• 技术故障和使用帮助\n"
        f"• 商务合作和其他建议\n\n"
        
        f"📝 **温馨提示：**\n"
        f"• 请尽量在服务时间内联系，回复更及时\n"
        f"• 遇到紧急情况可以随时留言\n"
        f"• 请描述清楚您的问题，方便快速处理"
    )
    
    # 构建客服联系键盘
    support_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💬 直接联系客服", 
                url=CUSTOMER_SUPPORT_LINK
            )
        ],
        [
            InlineKeyboardButton(
                "📞 复制用户名", 
                callback_data="copy_support_username"
            ),
            InlineKeyboardButton(
                "🔗 复制链接", 
                callback_data="copy_support_link"
            )
        ],
        [
            InlineKeyboardButton(
                "🌐 查看帮助", 
                callback_data="help_menu"
            ),
            InlineKeyboardButton(
                "📝 投稿指南", 
                callback_data="submission_guide"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 返回主菜单", 
                callback_data="main_menu"
            )
        ]
    ])
    
    # 发送客服信息
    if update.message is not None:
        await update.message.reply_text(
            support_text,
            parse_mode='Markdown',
            reply_markup=support_keyboard,
            disable_web_page_preview=True
        )

async def contact_command(update: Update, context: CallbackContext):
    """处理 /contact 命令 - 联系我们功能（与/support相同）
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    # 直接调用 support_command 函数
    await support_command(update, context)

async def handle_support_callbacks(update: Update, context: CallbackContext):
    """处理客服相关的回调按钮
    
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
    
    if data == "copy_support_username":
        # 复制客服用户名
        try:
            await query.answer(f"已复制客服用户名: {CUSTOMER_SUPPORT_USERNAME}", show_alert=True)
        except Exception as e:
            logger.error(f"复制客服用户名失败: {e}")
            await query.answer("复制失败，请手动复制", show_alert=True)
    
    elif data == "copy_support_link":
        # 复制客服链接
        try:
            await query.answer(f"已复制客服链接: {CUSTOMER_SUPPORT_LINK}", show_alert=True)
        except Exception as e:
            logger.error(f"复制客服链接失败: {e}")
            await query.answer("复制失败，请手动复制", show_alert=True)
    
    elif data == "help_menu":
        # 显示帮助菜单
        help_text = "❓ 请选择您需要的帮助类型："
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 投稿指南", callback_data="help_submission")],
            [InlineKeyboardButton("👑 审核帮助", callback_data="help_review")],
            [InlineKeyboardButton("⚙️ 管理帮助", callback_data="help_admin")],
            [InlineKeyboardButton("👤 个人资料", callback_data="help_profile")],
            [InlineKeyboardButton("💬 常见问题", callback_data="help_faq")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(help_text, reply_markup=keyboard)
    
    elif data.startswith("help_"):
        # 处理具体帮助内容
        help_type = data.split("_")[1]
        
        help_contents = {
            "submission": {
                "title": "📝 投稿指南",
                "content": (
                    "📥 **投稿流程**\n\n"
                    "1. 点击「📤 我要投稿」开始投稿\n"
                    "2. 选择投稿类型（文字/图片/视频/混合媒体）\n"
                    "3. 按提示发送内容和描述\n"
                    "4. 确认投稿并提交\n"
                    "5. 等待审核结果通知\n\n"
                    
                    "⚠️ **注意事项**\n"
                    "• 内容中禁止包含链接、网址或Telegram用户名\n"
                    "• 图片和视频投稿可添加文字描述\n"
                    "• 支持匿名投稿\n"
                    "• 所有投稿需经审核后才会发布\n\n"
                    
                    "🎭 **混合媒体投稿**\n"
                    "• 支持图片和视频混合上传\n"
                    "• 最多可上传100张图片和20个视频\n"
                    "• 系统会自动分组发布\n"
                    "• 首个媒体作为主消息，其余发布在留言区"
                )
            },
            "review": {
                "title": "👑 审核帮助",
                "content": (
                    "📋 **审核流程**\n\n"
                    "1. 点击「📬 待审稿件」查看待审核投稿\n"
                    "2. 浏览投稿内容（文字/图片/视频）\n"
                    "3. 选择操作：\n"
                    "   • ✅ 通过：投稿符合要求\n"
                    "   • ❌ 拒绝：投稿不符合要求\n"
                    "   • 📞 联系：需要更多信息\n"
                    "4. 拒绝时需填写具体原因\n\n"
                    
                    "🏷️ **标签管理**\n"
                    "• 为通过的投稿添加标签\n"
                    "• 便于后续分类和统计\n"
                    "• 可自定义标签内容\n\n"
                    
                    "💡 **审核建议**\n"
                    "• 保持公平公正\n"
                    "• 拒绝时给出明确理由\n"
                    "• 及时处理待审稿件\n"
                    "• 注意内容的合规性"
                )
            },
            "admin": {
                "title": "⚙️ 管理帮助",
                "content": (
                    "🔧 **管理功能**\n\n"
                    "👥 **审核员管理**\n"
                    "• 添加和删除审核员\n"
                    "• 处理审核员申请\n"
                    "• 生成邀请链接\n\n"
                    
                    "📊 **数据统计**\n"
                    "• 查看实时投稿统计\n"
                    "• 分析历史数据趋势\n"
                    "• 监控系统运行状态\n\n"
                    
                    "💾 **系统维护**\n"
                    "• 数据备份和恢复\n"
                    "• 清理过期数据\n"
                    "• 优化数据库性能\n\n"
                    
                    "📢 **广播通知**\n"
                    "• 向所有用户发送通知\n"
                    "• 紧急消息推送\n"
                    "• 系统维护公告"
                )
            },
            "profile": {
                "title": "👤 个人资料",
                "content": (
                    "🧾 **个人中心功能**\n\n"
                    "📊 **投稿统计**\n"
                    "• 查看个人投稿记录\n"
                    "• 统计各类投稿数量\n"
                    "• 分析通过率和趋势\n\n"
                    
                    "⚙️ **偏好设置**\n"
                    "• 通知设置\n"
                    "• 界面显示选项\n"
                    "• 使用习惯优化\n\n"
                    
                    "👑 **审核员功能**\n"
                    "• 加入管理群\n"
                    "• 生成邀请链接\n"
                    "• 查看审核历史"
                )
            },
            "faq": {
                "title": "💬 常见问题",
                "content": (
                    "❓ **常见问题解答**\n\n"
                    
                    "**Q: 投稿后多久能审核？**\n"
                    "A: 通常24小时内，高峰期可能稍长。\n\n"
                    
                    "**Q: 可以修改或撤销投稿吗？**\n"
                    "A: 投稿一旦提交无法修改，如需撤销请联系管理员。\n\n"
                    
                    "**Q: 为什么我的投稿被拒绝了？**\n"
                    "A: 常见原因：含链接、内容不符、图片模糊、重复投稿等。\n\n"
                    
                    "**Q: 如何成为审核员？**\n"
                    "A: 可通过「👑 加入管理群」提交申请，管理员审核通过后会邀请您加入管理群。\n\n"
                    
                    "**Q: 混合媒体投稿是什么？**\n"
                    "A: 支持图片和视频混合上传，系统会自动分组发布。\n\n"
                    
                    "**Q: 匿名投稿会显示什么？**\n"
                    "A: 匿名投稿发布时会显示为「匿名用户」。"
                )
            }
        }
        
        if help_type in help_contents:
            content = help_contents[help_type]
            await query.edit_message_text(
                f"{content['title']}\n\n{content['content']}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 返回帮助菜单", callback_data="help_menu")],
                    [InlineKeyboardButton("🏠 返回主菜单", callback_data="main_menu")]
                ])
            )
        else:
            await query.edit_message_text(
                "❌ 未找到相关帮助内容",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 返回帮助菜单", callback_data="help_menu")],
                    [InlineKeyboardButton("🏠 返回主菜单", callback_data="main_menu")]
                ])
            )
