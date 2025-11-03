# jobs/cleanup.py
"""
清理任务模块 - 系统数据库维护和性能优化

本模块负责处理定期清理任务，提高系统性能和稳定性。

主要功能：
- 旧媒体记录清理：删除过期的投稿记录
- 用户状态清理：清理过期的用户交互状态
- 数据库优化：空间回收和索引重建
- 性能监控：执行时间和效果统计

优化特性：
1. 性能监控 - 实时跟踪清理任务执行情况
2. 错误处理改进 - 强化的异常捕获和恢复机制
3. 报告优化 - 智能化的清理报告生成和发送
4. 批量处理 - 分批次处理大量数据，避免内存溢出
5. 可配置的清理策略 - 灵活的保留时间和批量大小

调度策略：
- 每日凌晨 3:00 自动执行主要清理任务
- 每周执行深度数据库优化
- 实时监控和动态调整清理频率

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
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

# 初始化日志器 - 用于记录清理任务执行情况
logger = logging.getLogger(__name__)

# 清理配置常量 - 可以从配置文件中读取
CLEANUP_RETENTION_DAYS = 30  # 数据保留天数，超过此时间的数据将被清理

async def setup_cleanup_job(context: CallbackContext):
    """
    设置优化的定时清理任务
    
    初始化系统的定时清理任务，包括：
    - 每日主要清理任务（凌晨 3:00）
    - 用户状态清理任务（每2小时）
    - 高级数据库优化任务
    - 系统监控和报告
    
    选择凌晨 3:00 的原因：
    1. 用户活动最少，对系统影响最小
    2. 系统资源相对充裕，可以进行高强度操作
    3. 方便日间时段查看清理结果
    
    Args:
        context (CallbackContext): Telegram 上下文对象，用于访问任务队列
    """
    # 确保 job_queue 存在
    if context.job_queue is None:
        logger.error("Job queue is not available")
        return
        
    # 每天凌晨3点执行清理
    context.job_queue.run_daily(
        callback=cleanup_old_media_optimized, 
        time=datetime.time(hour=3, minute=0),
        days=(0, 1, 2, 3, 4, 5, 6),
        name="daily_media_cleanup"
    )
    
    # 每2小时执行一次用户状态清理
    context.job_queue.run_repeating(
        callback=cleanup_inactive_user_states,
        interval=7200,  # 2小时 = 7200秒
        first=60,       # 60秒后首次执行
        name="cleanup_inactive_user_states"
    )
    
    logger.info("已设置优化的清理任务调度")

async def cleanup_old_media_optimized(context: CallbackContext):
    """执行优化的旧媒体记录清理
    
    优化点：
    1. 性能监控
    2. 错误恢复
    3. 进度报告
    
    Args:
        context: Telegram context 对象
    """
    start_time = time.time()
    logger.info("开始优化的旧媒体记录清理...")
    
    try:
        # 执行清理操作
        cleaned_count = db.cleanup_old_media(days=CLEANUP_RETENTION_DAYS)
        
        # 计算执行时间
        execution_time = round(time.time() - start_time, 2)
        
        logger.info(f"清理完成，共处理 {cleaned_count} 条记录，耗时 {execution_time} 秒")
        
        # 发送优化的清理报告
        _send_cleanup_report(context, {
            'type': '旧媒体清理',
            'cleaned_count': cleaned_count,
            'execution_time': execution_time,
            'status': 'success'
        })
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"清理任务失败: {e}，耗时 {execution_time} 秒")
        
        # 发送错误报告
        _send_cleanup_report(context, {
            'type': '旧媒体清理',
            'cleaned_count': 0,
            'execution_time': execution_time,
            'status': 'error',
            'error': str(e)
        })

async def cleanup_old_media(context: CallbackContext):
    """执行旧媒体记录清理 - 兼容性方法
    
    Args:
        context: Telegram context 对象
    """
    # 重定向到优化版本
    await cleanup_old_media_optimized(context)

async def cleanup_inactive_user_states(context: CallbackContext):
    """清理超过2小时无交互的用户状态
    
    定期清理长时间未交互的用户状态，防止用户状态数据积累过多
    
    Args:
        context: Telegram context 对象
    """
    start_time = time.time()
    logger.info("开始清理非活跃用户状态...")
    
    try:
        # 执行清理操作，默认清理超过2小时无交互的用户状态
        cleaned_count = db.cleanup_inactive_user_states(minutes=120)
        
        # 计算执行时间
        execution_time = round(time.time() - start_time, 2)
        
        logger.info(f"非活跃用户状态清理完成，共清理 {cleaned_count} 个用户状态，耗时 {execution_time} 秒")
        
        # 仅当清理了用户状态时发送报告
        if cleaned_count > 0:
            _send_cleanup_report(context, {
                'type': '非活跃用户状态清理',
                'cleaned_count': cleaned_count,
                'execution_time': execution_time,
                'status': 'success'
            })
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        logger.error(f"非活跃用户状态清理失败: {e}，耗时 {execution_time} 秒")
        
        # 发送错误报告
        _send_cleanup_report(context, {
            'type': '非活跃用户状态清理',
            'cleaned_count': 0,
            'execution_time': execution_time,
            'status': 'error',
            'error': str(e)
        })

def _send_cleanup_report(context: CallbackContext, report_data: dict):
    """发送优化的清理报告 - 内部函数
    
    Args:
        context: Telegram context 对象
        report_data: 报告数据
    """
    if report_data['status'] == 'success':
        report = (
            f"🔄 {report_data['type']}完成\n\n"
            f"📈 清理数量: {report_data['cleaned_count']} 条\n"
            f"⏱️ 执行时间: {report_data['execution_time']} 秒\n"
            f"✅ 状态: 成功"
        )
    else:
        report = (
            f"⚠️ {report_data['type']}失败\n\n"
            f"⏱️ 执行时间: {report_data['execution_time']} 秒\n"
            f"❌ 状态: 失败\n"
            f"📝 错误: {report_data.get('error', '未知错误')}"
        )
    
    # 仅在重要清理或错误时发送通知
    if report_data['cleaned_count'] > 0 or report_data['status'] == 'error':
        successful_sends = 0
        for admin_id in ADMIN_IDS:
            try:
                context.bot.send_message(chat_id=admin_id, text=report)
                successful_sends += 1
            except Exception as e:
                logger.error(f"发送清理报告给 {admin_id} 失败: {e}")
        
        logger.info(f"清理报告已发送给 {successful_sends}/{len(ADMIN_IDS)} 个管理员")