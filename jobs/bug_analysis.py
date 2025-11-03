# jobs/bug_analysis.py
"""
Bug分析定时任务模块

本模块提供定时分析bug日志并生成报告的功能。

主要功能：
- 定期分析各类bug日志
- 生成bug分析报告
- 发送bug统计通知
- 提供bug趋势分析

作者: AI Assistant
版本: 2.1
最后更新: 2025-09-15
"""

import os
import json
import datetime
import asyncio
import logging
from datetime import timedelta
# 导入时间工具
from utils.time_utils import get_beijing_now

from telegram.ext import JobQueue, CallbackContext
from config import ADMIN_IDS, MANAGEMENT_GROUP_ID
from utils.bug_analyzer import bug_analyzer
from utils.logging_utils import log_system_event, log_admin_operation
from utils.time_utils import get_beijing_now, format_beijing_time

# 初始化logger
logger = logging.getLogger(__name__)

async def setup_bug_analysis_jobs(context: CallbackContext):
    """设置Bug分析任务"""
    try:
        # 确保 job_queue 存在
        if context.job_queue is None:
            logger.error("Job queue is not available")
            return
            
        # 每天凌晨3点执行Bug分析
        context.job_queue.run_daily(
            analyze_and_report_bugs,
            time=get_beijing_now().replace(hour=3, minute=0, second=0, microsecond=0).time(),
            name="daily_bug_analysis"
        )
        
        # 每天上午9点发送Bug报告
        context.job_queue.run_daily(
            send_daily_bug_report,
            time=get_beijing_now().replace(hour=9, minute=0, second=0, microsecond=0).time(),
            name="daily_bug_report"
        )
        
        logger.info("✅ Bug分析任务已设置完成")
    except Exception as e:
        logger.error(f"设置Bug分析任务失败: {e}")

async def analyze_and_report_bugs(context):
    """分析并报告Bug"""
    try:
        # 获取昨天和今天的日期字符串
        yesterday = (get_beijing_now() - timedelta(days=1)).strftime("%Y-%m-%d")
        today = get_beijing_now().strftime("%Y-%m-%d")
        
        # 分析最近7天的bug日志
        report = bug_analyzer.analyze_recent_bugs(days=7)
        
        # 发送简报
        await send_bug_summary_to_admins(context, report, "每日Bug分析简报")
        
        logger.info("Bug分析完成")
    except Exception as e:
        logger.error(f"Bug分析失败: {e}")

async def send_bug_summary_to_admins(context, report, title):
    """
    发送Bug分析简报给管理员
    
    Args:
        context: 回调上下文
        report: Bug分析报告
        title: 报告标题
    """
    try:
        # 构建简报消息
        message = f"📊 *{title}*\n\n"
        message += f"📅 分析时间: {report['analysis_time']}\n"
        message += f"📈 分析周期: 最近{report['analysis_period_days']}天\n\n"
        
        # 总体统计
        total_bugs = report['total_bugs']
        message += f"🐛 Bug总数: *{total_bugs}*\n\n"
        
        # 按类别统计
        message += "📂 *按类别统计:*\n"
        for category, count in report['bugs_by_category'].items():
            if count > 0:
                message += f"  • {get_category_emoji(category)} {get_category_name(category)}: {count}\n"
        
        # 按严重性统计
        message += "\n⚠️ *按严重性统计:*\n"
        for severity, count in report['bugs_by_severity'].items():
            if count > 0:
                message += f"  • {get_severity_emoji(severity)} {get_severity_name(severity)}: {count}\n"
        
        # 趋势分析
        if report['daily_trend']:
            yesterday = (get_beijing_now() - timedelta(days=1)).strftime("%Y-%m-%d")
            today = get_beijing_now().strftime("%Y-%m-%d")
            
            yesterday_count = 0
            today_count = 0
            
            for day, count in report['daily_trend']:
                if day == yesterday:
                    yesterday_count = count
                elif day == today:
                    today_count = count
            
            if yesterday_count > 0 or today_count > 0:
                message += "\n📈 *趋势分析:*\n"
                message += f"  • 昨天: {yesterday_count} 个Bug\n"
                message += f"  • 今天: {today_count} 个Bug\n"
                
                if yesterday_count > 0:
                    change_percent = ((today_count - yesterday_count) / yesterday_count) * 100
                    if change_percent > 0:
                        message += f"  • 📈 较昨日增加: {change_percent:.1f}%\n"
                    elif change_percent < 0:
                        message += f"  • 📉 较昨日减少: {abs(change_percent):.1f}%\n"
                    else:
                        message += f"  • ➡️ 与昨日持平\n"
        
        # 主要建议
        if report['recommendations']:
            message += "\n💡 *改进建议:*\n"
            for i, recommendation in enumerate(report['recommendations'][:3], 1):  # 只显示前3条建议
                message += f"  {i}. {recommendation}\n"
        
        message += f"\n📄 详细报告已保存到日志目录"
        
        # 发送给所有管理员
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode='Markdown'
                )
                log_admin_operation(
                    admin_id=admin_id,
                    admin_username="",
                    operation="发送Bug分析简报",
                    target=f"Admin_{admin_id}",
                    details=f"标题: {title}, Bug总数: {total_bugs}"
                )
            except Exception as e:
                log_system_event("BUG_SUMMARY_SEND_ERROR", f"发送Bug分析简报失败: {e}")
        
        # 发送到管理群组
        try:
            await context.bot.send_message(
                chat_id=MANAGEMENT_GROUP_ID,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            log_system_event("BUG_SUMMARY_GROUP_SEND_ERROR", f"发送Bug分析简报到群组失败: {e}")
            
    except Exception as e:
        log_system_event("BUG_SUMMARY_ERROR", f"生成Bug分析简报失败: {e}")

async def send_daily_bug_report(context):
    """发送每日Bug报告"""
    try:
        # 分析最近7天的bug日志
        report = bug_analyzer.analyze_recent_bugs(days=7)
        
        # 发送详细报告
        await send_bug_report_to_admins(context, report, "每日Bug分析报告")
        
        logger.info("每日Bug报告发送完成")
    except Exception as e:
        logger.error(f"发送每日Bug报告失败: {e}")

async def send_bug_report_to_admins(context, report, title):
    """
    发送详细Bug分析报告给管理员
    
    Args:
        context: 回调上下文
        report: Bug分析报告
        title: 报告标题
    """
    try:
        # 构建详细报告消息
        message = f"📊 *{title}*\n\n"
        message += f"📅 分析时间: {report['analysis_time']}\n"
        message += f"📈 分析周期: 最近{report['analysis_period_days']}天\n\n"
        
        # 总体统计
        total_bugs = report['total_bugs']
        message += f"🐛 Bug总数: *{total_bugs}*\n\n"
        
        # 按类别详细统计
        message += "📂 *按类别详细统计:*\n"
        for category, count in report['bugs_by_category'].items():
            if count > 0:
                percentage = (count / total_bugs) * 100 if total_bugs > 0 else 0
                message += f"  • {get_category_emoji(category)} {get_category_name(category)}: {count} ({percentage:.1f}%)\n"
                
                # 添加该类别的Top 3错误
                category_details = report['category_details'].get(category, {})
                top_errors = category_details.get('top_errors', [])
                if top_errors:
                    message += "    *主要错误:*\n"
                    for error_type, error_count in top_errors[:3]:
                        error_percentage = (error_count / count) * 100 if count > 0 else 0
                        message += f"      - {error_type}: {error_count} ({error_percentage:.1f}%)\n"
        
        # 按严重性详细统计
        message += "\n⚠️ *按严重性详细统计:*\n"
        for severity, count in report['bugs_by_severity'].items():
            if count > 0:
                percentage = (count / total_bugs) * 100 if total_bugs > 0 else 0
                message += f"  • {get_severity_emoji(severity)} {get_severity_name(severity)}: {count} ({percentage:.1f}%)\n"
        
        # 趋势分析
        if report['daily_trend']:
            message += "\n📈 *每日趋势:*\n"
            # 只显示最近7天的数据
            recent_days = report['daily_trend'][-7:]
            for day, count in recent_days:
                message += f"  • {day}: {count} 个Bug\n"
        
        # 所有建议
        if report['recommendations']:
            message += "\n💡 *改进建议:*\n"
            for i, recommendation in enumerate(report['recommendations'], 1):
                message += f"  {i}. {recommendation}\n"
        
        message += f"\n📄 详细报告已保存到日志目录"
        
        # 发送给所有管理员
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode='Markdown'
                )
                log_admin_operation(
                    admin_id=admin_id,
                    admin_username="",
                    operation="发送Bug分析报告",
                    target=f"Admin_{admin_id}",
                    details=f"标题: {title}, Bug总数: {total_bugs}"
                )
            except Exception as e:
                log_system_event("BUG_REPORT_SEND_ERROR", f"发送Bug分析报告失败: {e}")
            
    except Exception as e:
        log_system_event("BUG_REPORT_ERROR", f"生成Bug分析报告失败: {e}")

def get_category_emoji(category):
    """获取Bug类别的emoji"""
    emoji_map = {
        "database": "🗄️",
        "network": "🌐",
        "media": "🎬",
        "permission": "🔐",
        "resource": "💾",
        "external": "🔌",
        "input": "📝",
        "scheduler": "⏰",
        "unknown": "❓"
    }
    return emoji_map.get(category, "🐛")

def get_category_name(category):
    """获取Bug类别的中文名称"""
    name_map = {
        "database": "数据库",
        "network": "网络",
        "media": "媒体处理",
        "permission": "权限",
        "resource": "系统资源",
        "external": "第三方服务",
        "input": "用户输入",
        "scheduler": "定时任务",
        "unknown": "未知类型"
    }
    return name_map.get(category, "其他")

def get_severity_emoji(severity):
    """获取Bug严重性的emoji"""
    emoji_map = {
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴"
    }
    return emoji_map.get(severity, "⚪")

def get_severity_name(severity):
    """获取Bug严重性的中文名称"""
    name_map = {
        "low": "低级",
        "medium": "中级",
        "high": "高级",
        "critical": "严重"
    }
    return name_map.get(severity, "未知")