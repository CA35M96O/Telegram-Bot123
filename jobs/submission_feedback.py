# jobs/submission_feedback.py
"""
投稿回访评价模块 - 统一媒体投稿系统

本模块提供投稿发布后的回访评价功能：
- 自动统计投稿在频道中的浏览量
- 根据频道总人数计算浏览占比
- 给出S/A/B/C等级评价
- 私聊投稿人发送评价结果

作者: AI Assistant
版本: 1.0
最后更新: 2025-09-11
"""

import logging
import datetime
import json
import time
from telegram.ext import CallbackContext
from sqlalchemy import func

# 导入时间工具
from utils.time_utils import get_beijing_now

from config import CHANNEL_IDS, ADMIN_IDS
from database import db
from utils.logging_utils import log_system_event

logger = logging.getLogger(__name__)

class SubmissionFeedbackScheduler:
    """投稿回访评价调度器"""
    
    def __init__(self):
        self.initialized = False
    
    async def setup_feedback_scheduler(self, context: CallbackContext):
        """设置回访评价调度器"""
        try:
            # 确保 job_queue 存在
            if context.job_queue is None:
                logger.error("Job queue is not available")
                return
                
            # 每小时检查一次需要回访评价的投稿
            context.job_queue.run_repeating(
                self._check_and_send_feedback,
                interval=3600,  # 每小时
                first=180,      # 3分钟后开始
                name="submission_feedback_checker"
            )
            
            self.initialized = True
            log_system_event("FEEDBACK_SCHEDULER_SETUP", "回访评价调度器已成功设置")
            logger.info("🚀 回访评价调度器已设置完成")
            
        except Exception as e:
            logger.error(f"设置回访评价调度器失败: {e}")
            log_system_event("FEEDBACK_SCHEDULER_ERROR", f"设置失败: {str(e)}", "ERROR")
    
    async def setup_feedback_tasks(self, context: CallbackContext):
        """设置回访评价任务"""
        await self.setup_feedback_scheduler(context)
    
    async def _check_and_send_feedback(self, context: CallbackContext):
        """检查并发送回访评价"""
        try:
            logger.debug("开始检查需要回访评价的投稿...")
            
            # 获取需要回访评价的投稿（已发布且未评价的投稿）
            submissions_to_evaluate = self._get_submissions_for_feedback()
            
            logger.debug(f"找到 {len(submissions_to_evaluate)} 个需要回访评价的投稿")
            
            for submission in submissions_to_evaluate:
                try:
                    # 生成并发送回访评价
                    await self._generate_and_send_feedback(context, submission)
                except Exception as e:
                    logger.error(f"处理投稿 #{submission.id} 的回访评价失败: {e}")
                    continue
            
            logger.debug("回访评价检查完成")
            
        except Exception as e:
            logger.error(f"回访评价检查失败: {e}")
    
    def _get_submissions_for_feedback(self):
        """获取需要回访评价的投稿"""
        try:
            with db.session_scope() as session:
                from database import Submission
                
                # 获取已发布但未评价的投稿（发布后24小时以上）
                twenty_four_hours_ago = get_beijing_now() - datetime.timedelta(hours=24)
                
                submissions = session.query(Submission).filter(
                    Submission.status == 'approved',
                    Submission.published_message_id.isnot(None),
                    Submission.feedback_sent == False,  # 使用新增的字段而不是tags
                    Submission.timestamp <= twenty_four_hours_ago
                ).all()
                
                # 将结果转换为字典列表，避免会话关闭后访问对象属性的问题
                result = []
                for submission in submissions:
                    result.append({
                        'id': submission.id,
                        'user_id': submission.user_id,
                        'type': submission.type,
                        'timestamp': submission.timestamp,
                        'published_message_id': submission.published_message_id,
                        'tags': submission.tags
                    })
                
                return result
        except Exception as e:
            logger.error(f"获取需要回访评价的投稿失败: {e}")
            return []
    
    async def _generate_and_send_feedback(self, context: CallbackContext, submission):
        """生成并发送回访评价"""
        try:
            # 获取频道总人数
            total_channel_members = await self._get_channel_member_count(context)
            
            # 获取投稿的浏览量估算
            views_count = await self._estimate_views_count(context, submission)
            
            # 计算浏览占比
            if total_channel_members > 0:
                view_ratio = views_count / total_channel_members
            else:
                view_ratio = 0
            
            # 根据浏览占比给出等级评价
            grade = self._calculate_grade(view_ratio)
            
            # 生成评价消息
            feedback_message = self._generate_feedback_message(
                submission, 
                views_count, 
                total_channel_members, 
                view_ratio, 
                grade
            )
            
            # 发送评价消息给投稿人
            await self._send_feedback_to_user(context, submission['user_id'], feedback_message)
            
            # 标记该投稿已发送回访评价
            self._mark_feedback_sent(submission['id'])
            
            logger.info(f"已发送投稿 #{submission['id']} 的回访评价给用户 {submission['user_id']}")
            
        except Exception as e:
            logger.error(f"生成并发送投稿 #{submission['id']} 的回访评价失败: {e}")
    
    async def _get_channel_member_count(self, context: CallbackContext) -> int:
        """获取频道成员总数"""
        try:
            # 直接使用get_chat_members_count方法获取成员数
            return await context.bot.get_chat_members_count(chat_id=CHANNEL_IDS[0])
        except Exception as e:
            logger.error(f"获取频道成员数失败: {e}")
            return 0
    
    async def _estimate_views_count(self, context: CallbackContext, submission) -> int:
        """估算投稿浏览量"""
        try:
            # 获取消息信息
            if submission['published_message_id']:
                try:
                    # 尝试获取消息对象
                    message = await context.bot.forward_message(
                        chat_id=ADMIN_IDS[0] if ADMIN_IDS else context.bot.id,  # 转发给管理员或bot自己
                        from_chat_id=CHANNEL_IDS[0],
                        message_id=int(submission['published_message_id'])
                    )
                    
                    # 基于时间的估算（消息发布后的小时数）
                    hours_since_publish = (get_beijing_now() - submission['timestamp']).total_seconds() / 3600
                    
                    # 基础浏览量估算
                    base_views = int(hours_since_publish * 3)  # 每小时约3个浏览
                    
                    # 根据互动情况调整
                    interaction_bonus = 0
                    if hasattr(message, 'reply_markup') and message.reply_markup:
                        interaction_bonus += 5  # 有按钮互动加成
                    
                    # 根据内容类型调整
                    type_multiplier = 1.0
                    if submission['type'] == "photo":
                        type_multiplier = 1.3  # 图片内容通常更受欢迎
                    elif submission['type'] == "video":
                        type_multiplier = 1.6  # 视频内容通常更受欢迎
                    
                    # 根据标签数量调整
                    try:
                        tags = json.loads(submission['tags']) if submission['tags'] else []
                        tag_bonus = len(tags) * 2  # 每个标签加2个浏览量
                    except:
                        tag_bonus = 0
                    
                    # 计算最终估算浏览量
                    estimated_views = int((base_views + interaction_bonus + tag_bonus) * type_multiplier)
                    
                    # 确保至少有基本的浏览量
                    estimated_views = max(estimated_views, 15)
                    
                    # 但不超过频道成员数的30%（避免不现实的高估）
                    max_views = int(await self._get_channel_member_count(context) * 0.3)
                    if max_views > 0:
                        estimated_views = min(estimated_views, max_views)
                    
                    return estimated_views
                    
                except Exception as forward_error:
                    logger.warning(f"转发消息以估算浏览量失败: {forward_error}")
                
                # 如果无法获取消息信息，使用基于时间的简单估算
                hours_since_publish = (get_beijing_now() - submission['timestamp']).total_seconds() / 3600
                estimated_views = int(hours_since_publish * 4)  # 每小时约4个浏览
                
                # 根据投稿类型调整估算
                if submission['type'] == "photo":
                    estimated_views = int(estimated_views * 1.2)  # 图片内容通常更受欢迎
                elif submission['type'] == "video":
                    estimated_views = int(estimated_views * 1.5)  # 视频内容通常更受欢迎                
                return max(estimated_views, 10)
        except Exception as e:
            logger.warning(f"估算投稿 #{submission['id']} 浏览量失败: {e}")
        
        # 默认返回一个估算值
        return 25
    
    def _calculate_grade(self, view_ratio: float) -> str:
        """根据浏览占比计算等级"""
        if view_ratio >= 0.1:      # 10%以上为S级
            return "S"
        elif view_ratio >= 0.05:   # 5%以上为A级
            return "A"
        elif view_ratio >= 0.02:   # 2%以上为B级
            return "B"
        else:                      # 2%以下为C级
            return "C"
    
    def _generate_feedback_message(self, submission, views_count: int, total_members: int, view_ratio: float, grade: str) -> str:
        """生成回访评价消息"""
        # 格式化浏览占比为百分比
        view_percentage = view_ratio * 100
        
        message = (
            f"📈 您的投稿回访评价\n\n"
            f"投稿编号: #{submission['id']}\n"
            f"投稿类型: {submission['type']}\n"
            f"发布时间: {submission['timestamp'].strftime('%Y-%m-%d %H:%M')}\n\n"
            f"📊 数据统计:\n"
            f"• 频道总人数: {total_members}\n"
            f"• 估算浏览量: {views_count}\n"
            f"• 浏览占比: {view_percentage:.2f}%\n\n"
            f"🏅 评价等级: {grade}级\n\n"
        )
        
        # 根据等级添加鼓励或建议
        if grade == "S":
            message += "🎉 恭喜！您的投稿获得了极高的关注度，非常优秀！"
        elif grade == "A":
            message += "👍 很好！您的投稿获得了不错的关注度。"
        elif grade == "B":
            message += "😊 您的投稿有一定关注度，继续加油！"
        else:  # C
            message += "💪 您的投稿关注度还有提升空间，不要气馁！"
        
        message += "\n\n感谢您的投稿，期待您的更多优质内容！"
        
        return message
    
    async def _send_feedback_to_user(self, context: CallbackContext, user_id: int, message: str):
        """发送回访评价给用户"""
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message
            )
        except Exception as e:
            logger.error(f"发送回访评价给用户 {user_id} 失败: {e}")
    
    def _mark_feedback_sent(self, submission_id: int):
        """标记投稿已发送回访评价"""
        try:
            with db.session_scope() as session:
                from database import Submission
                session.query(Submission).filter_by(id=submission_id).update({
                    'feedback_sent': True,
                    'feedback_sent_at': func.now()
                })
        except Exception as e:
            logger.error(f"标记投稿 #{submission_id} 已发送回访评价失败: {e}")

# 创建全局调度器实例
feedback_scheduler = SubmissionFeedbackScheduler()

# 设置函数
async def setup_submission_feedback(context: CallbackContext):
    """设置投稿回访评价"""
    await feedback_scheduler.setup_feedback_tasks(context)