# handlers/business.py
"""
商务合作处理模块
处理商务合作申请相关功能
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from config import ADMIN_IDS
from database import db
from keyboards import back_button
from utils.logging_utils import log_user_activity, log_admin_operation

logger = logging.getLogger(__name__)

# 商务合作表单字段
BUSINESS_FIELDS = {
    "name": "公司/个人名称",
    "contact": "联系方式",
    "desc": "合作描述"
}

def business_menu():
    """商务合作菜单
    
    Returns:
        InlineKeyboardMarkup: 商务合作菜单键盘
    """
    keyboard = [
        [InlineKeyboardButton("🏢 公司/个人名称", callback_data="business_name")],
        [InlineKeyboardButton("📞 联系方式", callback_data="business_contact")],
        [InlineKeyboardButton("📝 合作描述", callback_data="business_desc")],
        [InlineKeyboardButton("✅ 提交申请", callback_data="business_submit")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def business_form_menu(form_data):
    """商务合作表单菜单
    
    Args:
        form_data: 表单数据
        
    Returns:
        InlineKeyboardMarkup: 商务合作表单菜单键盘
    """
    keyboard = []
    
    for field, label in BUSINESS_FIELDS.items():
        value = form_data.get(field, "")
        status = "✅" if value else "📝"
        keyboard.append([InlineKeyboardButton(f"{status} {label}", callback_data=f"business_{field}")])
    
    keyboard.append([InlineKeyboardButton("✅ 提交申请", callback_data="business_submit")])
    keyboard.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def business_field_callback(update: Update, context: CallbackContext):
    """商务合作字段回调
    
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
        import asyncio
        asyncio.create_task(query.answer("无效的操作"))
        return
    
    import asyncio
    asyncio.create_task(query.answer())
    
    field = str(data).split("_")[1]
    
    if field in BUSINESS_FIELDS:
        user_data = context.user_data
        if user_data is not None:
            user_data["editing_field"] = field
        
        instructions = {
            "name": "请输入公司/个人名称：",
            "contact": "请输入联系方式（如Telegram、邮箱、电话等）：",
            "desc": "请详细描述合作内容："
        }
        
        if query.message is not None:
            import asyncio
            asyncio.create_task(query.message.edit_text(
                instructions.get(field, f"请输入{BUSINESS_FIELDS[field]}："),
                reply_markup=back_button("business_menu")
            ))
    
    # 记录用户活动
    log_user_activity(user.id, user.username, "BUSINESS_FIELD_EDIT", f"Editing field: {field}")

def submit_business_callback(update: Update, context: CallbackContext):
    """提交商务合作回调
    
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
    
    import asyncio
    asyncio.create_task(query.answer())
    
    state, form_data = db.get_user_state(user.id)
    
    if str(state) != "business_form":
        form_data = {}
    
    # 检查必填字段
    missing_fields = []
    for field, label in BUSINESS_FIELDS.items():
        if not form_data.get(field):
            missing_fields.append(label)
    
    if missing_fields:
        if query.message is not None:
            import asyncio
            asyncio.create_task(query.message.edit_text(
                f"❌ 以下信息不能为空：\n" + "\n".join(f"• {field}" for field in missing_fields),
                reply_markup=business_form_menu(form_data)
            ))
        return
    
    # 保存到数据库
    sub_id = db.add_submission(
        user_id=user.id,
        username=user.username or user.full_name,
        content_type="text",
        content=f"公司/个人名称: {form_data['name']}\n联系方式: {form_data['contact']}\n合作描述: {form_data['desc']}",
        category="business"
    )
    
    if sub_id is not None:
        # 通知管理员
        business_text = (
            f"🤝 新的商务合作申请 #{sub_id}\n\n"
            f"用户: @{user.username or user.full_name} (ID: {user.id})\n\n"
            f"公司/个人名称: {form_data['name']}\n"
            f"联系方式: {form_data['contact']}\n"
            f"合作描述: {form_data['desc']}"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                context.bot.send_message(chat_id=admin_id, text=business_text)
            except Exception as e:
                logger.error(f"通知管理员失败: {e}")
        
        # 记录管理员操作
        log_admin_operation(
            user.id,
            user.username,
            "BUSINESS_SUBMISSION",
            sub_id,
            "Submitted business cooperation application"
        )
        
        if query.message is not None:
            import asyncio
            asyncio.create_task(query.message.edit_text(
                "✅ 商务合作申请已提交！\n\n管理员会尽快与您联系。",
                reply_markup=back_button("main_menu")
            ))
        
        # 清除用户状态
        db.clear_user_state(user.id)
    else:
        if query.message is not None:
            import asyncio
            asyncio.create_task(query.message.edit_text(
                "❌ 提交失败，请稍后再试。",
                reply_markup=business_form_menu(form_data)
            ))
