# jobs/__init__.py
"""
定时任务包初始化文件
导出所有定时任务函数
"""

from .cleanup import setup_cleanup_job, cleanup_old_media, cleanup_inactive_user_states
from .status_report import setup_periodic_report, periodic_status_report
from .dns_monitor import setup_dns_monitor_job, check_and_fix_dns
from .advanced_scheduler import setup_advanced_scheduler, advanced_scheduler  # 新增高级调度器
# 新增：导入投稿回访评价任务
from .submission_feedback import setup_submission_feedback, feedback_scheduler
# 新增：导入自动封禁任务
from .auto_ban import setup_auto_ban_job, auto_ban_blocked_users