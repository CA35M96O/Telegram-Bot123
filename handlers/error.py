# handlers/error.py
"""
错误处理模块
处理机器人运行时的错误
"""

import logging
import traceback
from telegram import Update
from telegram.ext import CallbackContext
from keyboards import main_menu

logger = logging.getLogger(__name__)

async def error_handler(update: object, context: CallbackContext) -> None:
    """错误处理函数
    
    Args:
        update: Telegram update 对象 (可能是任何类型的更新)
        context: Telegram context 对象
    """
    error = context.error
    
    # 忽略特定错误
    if "Conflict: terminated by other getUpdates request" in str(error):
        logger.warning(f"忽略多个实例冲突错误: {error}")
        return
        
    if "no text in the message to edit" in str(error):
        logger.warning(f"忽略媒体消息编辑错误: {error}")
        return
    
    # 记录完整的错误堆栈
    logger.error(f"更新 {update} 导致错误: {error}")
    logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    # 数据库相关错误
    if "database" in str(error).lower() or "sql" in str(error).lower():
        logger.error("数据库相关错误发生")
    
    # 如果update是Update对象且有消息，尝试回复用户
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ 发生错误，请稍后再试",
                reply_markup=await main_menu()
            )
        except Exception as e:
            logger.error(f"发送错误消息失败: {e}")