# jobs/status_report.py
"""
状态报告任务模块
处理定期状态报告任务
"""

import logging
from telegram.ext import CallbackContext
from utils.pushplus import send_pushplus_notification
from utils.server_status import get_server_status_with_stats
from config import SERVER_NAME

logger = logging.getLogger(__name__)

async def periodic_status_report(context: CallbackContext):
    """每4小时发送服务器状态报告
    
    Args:
        context: Telegram context 对象
    """
    try:
        # 获取状态报告内容
        report = get_server_status_with_stats()
        
        # 发送通知
        title = f"🔄 {SERVER_NAME} 状态报告（每4小时）"
        success = send_pushplus_notification(title, report)
        
        if success:
            logger.info("已发送每4小时状态报告")
        else:
            logger.warning("发送状态报告失败")
    except Exception as e:
        logger.error(f"更新 {context} 导致错误: {str(e)}")
        logger.error("错误堆栈: ", exc_info=True)

async def setup_periodic_report(context: CallbackContext):
    """设置每4小时状态报告任务
    
    Args:
        context: Telegram context 对象
    """
    try:
        # 确保 job_queue 存在
        if context.job_queue is None:
            logger.error("Job queue is not available")
            return
            
        # 每4小时执行一次（首次延迟5秒）
        context.job_queue.run_repeating(
            periodic_status_report,
            interval=14400,  # 14400秒 = 4小时
            first=5,
            name="periodic_status_report"
        )
        logger.info("已设置每4小时状态报告任务")
    except Exception as e:
        logger.error(f"设置每4小时状态报告任务失败: {str(e)}")