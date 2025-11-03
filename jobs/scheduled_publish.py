# jobs/scheduled_publish.py
"""
定时发布模块 - 支持定时发布投稿

本模块提供定时发布功能，支持立即发布和定时发布：
- 立即发布：审核通过后立即发布到频道
- 定时发布：在指定的时间点发布投稿

作者: AI Assistant
版本: 1.0
最后更新: 2025-11-03
"""

import logging
import datetime
import json
from telegram.ext import CallbackContext
from sqlalchemy import func

# 导入时间工具
from utils.time_utils import get_beijing_now, beijing_time_add
from config import ADMIN_IDS
from database import db
from utils.logging_utils import log_system_event

logger = logging.getLogger(__name__)

class ScheduledPublishScheduler:
    """定时发布调度器"""
    
    def __init__(self):
        self.initialized = False
    
    async def setup_scheduled_publish_scheduler(self, context: CallbackContext):
        """设置定时发布调度器"""
        try:
            # 确保 job_queue 存在
            if context.job_queue is None:
                logger.error("Job queue is not available")
                return
                
            # 每分钟检查一次需要发布的投稿
            context.job_queue.run_repeating(
                self._check_and_publish_scheduled,
                interval=60,  # 每分钟
                first=30,     # 30秒后开始
                name="scheduled_publish_checker"
            )
            
            self.initialized = True
            log_system_event("SCHEDULED_PUBLISH_SCHEDULER_SETUP", "定时发布调度器已成功设置")
            logger.info("🚀 定时发布调度器已设置完成")
            
        except Exception as e:
            logger.error(f"设置定时发布调度器失败: {e}")
            log_system_event("SCHEDULED_PUBLISH_SCHEDULER_ERROR", f"设置失败: {str(e)}", "ERROR")
    
    async def setup_scheduled_publish_tasks(self, context: CallbackContext):
        """设置定时发布任务"""
        await self.setup_scheduled_publish_scheduler(context)
    
    async def _check_and_publish_scheduled(self, context: CallbackContext):
        """检查并发布定时投稿"""
        try:
            logger.debug("开始检查需要定时发布的投稿...")
            
            # 获取需要定时发布的投稿
            submissions_to_publish = self._get_submissions_for_scheduled_publish()
            
            logger.debug(f"找到 {len(submissions_to_publish)} 个需要定时发布的投稿")
            
            for submission in submissions_to_publish:
                try:
                    # 发布投稿
                    await self._publish_scheduled_submission(context, submission)
                except Exception as e:
                    logger.error(f"处理投稿 #{submission['id']} 的定时发布失败: {e}")
                    continue
            
            logger.debug("定时发布检查完成")
            
        except Exception as e:
            logger.error(f"定时发布检查失败: {e}")
    
    def _get_submissions_for_scheduled_publish(self):
        """获取需要定时发布的投稿"""
        try:
            with db.session_scope() as session:
                from database import Submission
                
                # 获取已审核通过但尚未发布的投稿（状态为approved但published_message_id为空）
                # 并且发布时间小于等于当前时间
                now = get_beijing_now()
                submissions = session.query(Submission).filter(
                    Submission.status == 'approved',
                    Submission.published_message_id.is_(None),
                    Submission.scheduled_publish_time.isnot(None),
                    Submission.scheduled_publish_time <= now
                ).all()
                
                # 将结果转换为字典列表，避免会话关闭后访问对象属性的问题
                result = []
                for submission in submissions:
                    result.append({
                        'id': submission.id,
                        'user_id': submission.user_id,
                        'username': submission.username,
                        'type': submission.type,
                        'content': submission.content,
                        'file_id': submission.file_id,
                        'file_ids': submission.file_ids,
                        'file_types': submission.file_types,
                        'tags': submission.tags,
                        'anonymous': submission.anonymous,
                        'cover_index': submission.cover_index,
                        'handled_by': submission.handled_by,
                        'handled_at': submission.handled_at,
                        'timestamp': submission.timestamp,
                        'custom_keyword': submission.custom_keyword if hasattr(submission, 'custom_keyword') else '关键词'
                    })
                
                return result
        except Exception as e:
            logger.error(f"获取需要定时发布的投稿失败: {e}")
            return []
    
    async def _publish_scheduled_submission(self, context: CallbackContext, submission):
        """发布定时投稿"""
        try:
            from utils.helpers import publish_submission
            
            # 发布投稿
            await publish_submission(context, submission)
            
            # 标记投稿已发布
            self._mark_submission_published(submission['id'])
            
            # 通知用户投稿已发布
            await self._notify_user_submission_published(context, submission)
            
            logger.info(f"定时发布投稿 #{submission['id']} 成功")
            
        except Exception as e:
            logger.error(f"发布定时投稿 #{submission['id']} 失败: {e}")
    
    def _mark_submission_published(self, submission_id: int):
        """标记投稿已发布"""
        try:
            with db.session_scope() as session:
                from database import Submission
                session.query(Submission).filter_by(id=submission_id).update({
                    'scheduled_publish_time': None  # 清除定时发布时间
                })
        except Exception as e:
            logger.error(f"标记投稿 #{submission_id} 已发布失败: {e}")
    
    async def _notify_user_submission_published(self, context: CallbackContext, submission):
        """通知用户投稿已发布"""
        try:
            user_id = submission['user_id']
            submission_id = submission['id']
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 您的投稿 #{submission_id} 已成功发布！\n\n感谢您的分享。"
            )
        except Exception as e:
            logger.error(f"通知用户投稿 #{submission['id']} 已发布失败: {e}")

# 创建全局调度器实例
scheduled_publish_scheduler = ScheduledPublishScheduler()

# 设置函数
async def setup_scheduled_publish(context: CallbackContext):
    """设置定时发布"""
    await scheduled_publish_scheduler.setup_scheduled_publish_tasks(context)

def get_next_publish_time():
    """获取下一个发布时间点
    
    发布时间点为：00:00, 06:00, 12:00, 18:00
    
    Returns:
        datetime: 下一个发布时间点
    """
    now = get_beijing_now()
    
    # 定义发布时间点（小时）
    publish_hours = [0, 6, 12, 18]
    
    # 获取当前时间的小时数
    current_hour = now.hour
    
    # 寻找下一个发布时间点
    next_hour = None
    for hour in publish_hours:
        if hour > current_hour:
            next_hour = hour
            break
    
    # 如果今天没有更晚的发布时间点了，则选择明天的第一个时间点
    if next_hour is None:
        # 明天的第一个时间点
        next_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    else:
        # 今天的下一个时间点
        next_time = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    
    return next_time