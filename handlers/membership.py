# handlers/membership.py
"""
成员资格检查模块
处理用户成员资格检查相关功能
"""

import logging
from telegram import Update
from telegram.ext import CallbackContext
from database import db
from keyboards import membership_check_menu, submission_type_menu, business_form_menu, main_menu
from utils.helpers import check_membership
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

async def membership_check_callback(update: Update, context: CallbackContext):
    """成员资格检查回调
    
    Args:
        update: Telegram update 对象
        context: Telegram context 对象
    """
    # 检查 callback_query 是否存在
    if not update.callback_query:
        logger.warning("收到一个没有 callback_query 的更新")
        return
        
    query = update.callback_query
    
    # 检查用户是否存在
    user = query.from_user if query.from_user else update.effective_user
    if not user:
        logger.warning("无法获取用户信息")
        await query.answer("无法获取用户信息，请稍后再试")
        return
    
    data = query.data
    await query.answer()
    
    user_state = db.get_user_state(user.id)
    state = None
    state_data = {}
    if user_state:
        state, state_data = user_state
    
    if data == "check_membership":
        is_member, where = await check_membership(update, context, user.id)
        
        if is_member:
            db.clear_user_state(user.id)
            
            # 将条件检查转换为字符串比较以避免类型检查错误
            if str(state) == "membership_check" and state_data.get("source") == "submit_menu":
                try:
                    await query.edit_message_text(
                        "✅ 感谢加入！您现在可以投稿了",
                        reply_markup=submission_type_menu()
                    )
                except Exception as e:
                    logger.error(f"编辑消息失败: {e}")
                    await query.answer("✅ 感谢加入！您现在可以投稿了")
            elif str(state) == "membership_check" and state_data.get("source") == "business_menu":
                form_data = {
                    "name": "",
                    "contact": "",
                    "description": ""
                }
                db.set_user_state(user.id, "business_form", form_data)
                
                text = (
                    "📩 商务合作申请\n请填写以下信息：\n\n"
                    f"🏢 公司/个人名称: [未填写]\n"
                    f"📞 联系方式: [未填写]\n"
                    f"💡 合作描述: [未填写]\n\n"
                    "请点击对应按钮开始填写："
                )
                
                try:
                    await query.edit_message_text(
                        text,
                        reply_markup=business_form_menu(form_data)
                    )
                except Exception as e:
                    logger.error(f"编辑消息失败: {e}")
                    await query.answer("📝 请填写商务合作申请信息")
            elif str(state) == "membership_check" and state_data.get("source") == "start_command":
                # 从/start命令过来的，显示主菜单
                is_admin_user = user.id in ADMIN_IDS
                menu = await main_menu(user.id, is_admin_user, context)
                try:
                    await query.edit_message_text(
                        "✅ 感谢加入！",
                        reply_markup=menu
                    )
                except Exception as e:
                    logger.error(f"编辑消息失败: {e}")
                    await query.answer("✅ 感谢加入！")
            else:
                is_admin_user = user.id in ADMIN_IDS
                menu = await main_menu(user.id, is_admin_user, context)
                try:
                    await query.edit_message_text(
                        "✅ 感谢加入！",
                        reply_markup=menu
                    )
                except Exception as e:
                    logger.error(f"编辑消息失败: {e}")
                    await query.answer("✅ 感谢加入！")
        else:
            if where == "group":
                text = "❌ 您尚未加入我们的群组！\n\n请点击下方按钮加入群组，然后点击\"我已加入\"确认："
            elif where == "channel":
                text = "❌ 您尚未加入我们的频道！\n\n请点击下方按钮加入频道，然后点击\"我已加入\"确认："
            else:
                text = "❌ 您尚未加入我们的群组！\n\n请点击下方按钮加入群组，然后点击\"我已加入\"确认："
            
            try:
                await query.edit_message_text(
                    text,
                    reply_markup=membership_check_menu(where)
                )
            except Exception as edit_error:
                # 如果消息编辑失败（比如内容相同），忽略错误
                if "Message is not modified" in str(edit_error):
                    logger.debug("消息内容相同，无需修改")
                    await query.answer("请确认您已加入所有必需的群组和频道")
                else:
                    logger.error(f"编辑消息失败: {edit_error}")
                    await query.answer("操作失败，请稍后再试")
    else:
        db.clear_user_state(user.id)
        try:
            is_admin_user = user.id in ADMIN_IDS
            menu = await main_menu(user.id, is_admin_user, context)
            await query.edit_message_text(
                "操作已取消",
                reply_markup=menu
            )
        except Exception as edit_error:
            if "Message is not modified" in str(edit_error):
                logger.debug("消息内容相同，无需修改")
                await query.answer("操作已取消")
            else:
                logger.error(f"编辑消息失败: {edit_error}")
                await query.answer("操作已取消")