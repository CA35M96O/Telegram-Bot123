# jobs/auto_ban.py
"""
自动封禁任务模块 - 自动封禁屏蔽机器人超过3天的用户

本模块负责处理自动封禁任务，提高系统管理效率。

主要功能：
- 自动检测屏蔽机器人超过3天的用户
- 自动封禁这些用户
- 发送封禁报告给管理员

作者: AI Assistant
版本: 1.0
最后更新: 2025-11-01
"""

# =====================================================
# 所需库导入 Required Library Imports
# =====================================================

# Python 标准库
import logging
import datetime
import time

# Telegram Bot API 组件
from telegram.ext import CallbackContext

# 项目配置和数据库
from config import ADMIN_IDS
from database import db

# =====================================================
# 日志配置和全局常量 Global Logging and Constants
# =====================================================

# 初始化日志器 - 用于记录自动封禁任务执行情况
logger = logging.getLogger(__name__)

async def setup_auto_ban_job(context: CallbackContext):
    """
    设置自动封禁任务
    
    初始化系统的自动封禁任务，包括：
    - 每天凌晨4点执行自动封禁检查
    
    选择凌晨 4:00 的原因：
    1. 用户活动最少，对系统影响最小
    2. 在清理任务之后执行，确保数据一致性
    
    Args:
        context (CallbackContext): Telegram 上下文对象，用于访问任务队列
    """
    # 确保 job_queue 存在
    if context.job_queue is None:
        logger.error("Job queue is not available")
        return
        
    # 每天凌晨4点执行自动封禁检查
    context.job_queue.run_daily(
        callback=auto_ban_blocked_users, 
        time=datetime.time(hour=4, minute=0),
        days=(0, 1, 2, 3, 4, 5, 6),
        name="daily_auto_ban"
    )
    
    logger.info("已设置自动封禁任务调度")

async def auto_ban_blocked_users(context: CallbackContext):
    """自动封禁屏蔽机器人超过3天的用户
    
    Args:
        context: Telegram context 对象
    """
    start_time = time.time()
    logger.info("开始自动封禁屏蔽机器人超过3天的用户...")
    
    try:
        # 计算3天前的时间
        three_days_ago = datetime.datetime.now() - datetime.timedelta(days=3)
        
        # 执行自动封禁操作
        banned_count = db.auto_ban_blocked_users(since=three_days_ago)
        
        # 计算执行时间
        execution_time = round(time.time() - start_time, 2)
        
        logger.info(f"自动封禁完成，共封禁 {banned_count} 个用户，耗时 {execution_time} 秒")
        
        # 发送封禁报告
        if banned_count > 0:
            await _send_auto_ban_report(context, {
                'banned_count': banned_count,
                'execution_time': execution_time,
                'status': 'success'
            })
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"自动封禁任务失败: {e}，耗时 {execution_time} 秒")
        
        # 发送错误报告
        await _send_auto_ban_report(context, {
            'banned_count': 0,
            'execution_time': execution_time,
            'status': 'error',
            'error': str(e)
        })

async def _send_auto_ban_report(context: CallbackContext, report_data: dict):
    """发送自动封禁报告 - 内部函数
    
    Args:
        context: Telegram context 对象
        report_data: 报告数据
    """
    if report_data['status'] == 'success':
        report = (
            f"🤖 自动封禁任务完成\n\n"
            f"📈 封禁数量: {report_data['banned_count']} 个用户\n"
            f"⏱️ 执行时间: {report_data['execution_time']} 秒\n"
            f"✅ 状态: 成功"
        )
    else:
        report = (
            f"⚠️ 自动封禁任务失败\n\n"
            f"⏱️ 执行时间: {report_data['execution_time']} 秒\n"
            f"❌ 状态: 失败\n"
            f"📝 错误: {report_data.get('error', '未知错误')}"
        )
    
    # 仅当封禁了用户或出现错误时发送通知
    if report_data['banned_count'] > 0 or report_data['status'] == 'error':
        successful_sends = 0
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=report)
                successful_sends += 1
            except Exception as e:
                logger.error(f"发送自动封禁报告给 {admin_id} 失败: {e}")
        
        logger.info(f"自动封禁报告已发送给 {successful_sends}/{len(ADMIN_IDS)} 个管理员")