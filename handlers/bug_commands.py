# handlers/bug_commands.py
"""
Bug分析命令处理模块

本模块提供与Bug分析相关的命令处理功能。

主要功能：
- /bugstats - 获取Bug统计信息
- /bugreport - 生成Bug分析报告
- /bugtrend - 查看Bug趋势
- /bugcategories - 查看Bug分类统计

作者: AI Assistant
版本: 2.1
最后更新: 2025-09-15
"""

import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler
from config import ADMIN_IDS
from utils.bug_analyzer import bug_analyzer
from utils.logging_utils import log_admin_operation, log_system_event
from utils.time_utils import get_beijing_now

# 初始化logger
logger = logging.getLogger(__name__)

async def bug_stats_command(update: Update, context: CallbackContext) -> None:
    """
    处理/bugstats命令 - 获取Bug统计信息
    
    Args:
        update: Telegram更新对象
        context: 回调上下文
    """
    # 检查update和user是否存在
    if not update or not update.effective_user:
        return
        
    user_id = update.effective_user.id
    
    # 检查是否是管理员
    if user_id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("⚠️ 此命令仅限管理员使用。")
        return
    
    try:
        # 分析最近7天的bug日志
        report = bug_analyzer.analyze_recent_bugs(days=7)
        
        # 构建统计消息
        message = f"📊 *Bug统计信息*\n\n"
        message += f"📅 分析时间: {report['analysis_time']}\n"
        message += f"📈 分析周期: 最近{report['analysis_period_days']}天\n\n"
        
        # 总体统计
        total_bugs = report['total_bugs']
        message += f"🐛 Bug总数: *{total_bugs}*\n\n"
        
        # 按类别统计
        message += "📂 *按类别统计:*\n"
        for category, count in report['bugs_by_category'].items():
            if count > 0:
                percentage = (count / total_bugs) * 100 if total_bugs > 0 else 0
                message += f"  • {get_category_emoji(category)} {get_category_name(category)}: {count} ({percentage:.1f}%)\n"
        
        # 按严重性统计
        message += "\n⚠️ *按严重性统计:*\n"
        for severity, count in report['bugs_by_severity'].items():
            if count > 0:
                percentage = (count / total_bugs) * 100 if total_bugs > 0 else 0
                message += f"  • {get_severity_emoji(severity)} {get_severity_name(severity)}: {count} ({percentage:.1f}%)\n"
        
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
        
        # 添加操作按钮
        keyboard = [
            [
                InlineKeyboardButton("📄 生成详细报告", callback_data="bug_report"),
                InlineKeyboardButton("📈 查看趋势", callback_data="bug_trend")
            ],
            [
                InlineKeyboardButton("📂 分类统计", callback_data="bug_categories"),
                InlineKeyboardButton("🔍 搜索Bug", callback_data="bug_search")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 发送消息
        if update.message:
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        # 记录管理员操作
        if update.effective_user:
            log_admin_operation(
                admin_id=user_id,
                admin_username=update.effective_user.username or "",
                operation="查看Bug统计",
                target="系统",
                details=f"分析周期: {report['analysis_period_days']}天, Bug总数: {total_bugs}"
            )
        
    except Exception as e:
        if update.message:
            await update.message.reply_text(f"❌ 获取Bug统计信息失败: {e}")
        log_system_event("BUG_STATS_ERROR", f"获取Bug统计信息失败: {e}")

async def bug_report_command(update: Update, context: CallbackContext) -> None:
    """
    处理/bugreport命令 - 生成Bug分析报告
    
    Args:
        update: Telegram更新对象
        context: 回调上下文
    """
    # 检查update和user是否存在
    if not update or not update.effective_user:
        return
        
    user_id = update.effective_user.id
    
    # 检查是否是管理员
    if user_id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("⚠️ 此命令仅限管理员使用。")
        return
    
    try:
        # 获取参数，默认分析最近30天
        days = 30
        if context.args and context.args[0].isdigit():
            days = int(context.args[0])
            if days < 1:
                days = 1
            elif days > 365:
                days = 365
        
        # 分析bug日志
        report = bug_analyzer.analyze_recent_bugs(days=days)
        
        # 保存报告
        report_path = bug_analyzer.generate_bug_report_filename()
        
        # 发送简报
        message = f"📊 *Bug分析报告*\n\n"
        message += f"📅 分析时间: {report['analysis_time']}\n"
        message += f"📈 分析周期: 最近{report['analysis_period_days']}天\n\n"
        
        # 总体统计
        total_bugs = report['total_bugs']
        message += f"🐛 Bug总数: *{total_bugs}*\n\n"
        
        # 按类别统计
        message += "📂 *按类别统计:*\n"
        for category, count in report['bugs_by_category'].items():
            if count > 0:
                percentage = (count / total_bugs) * 100 if total_bugs > 0 else 0
                message += f"  • {get_category_emoji(category)} {get_category_name(category)}: {count} ({percentage:.1f}%)\n"
        
        # 按严重性统计
        message += "\n⚠️ *按严重性统计:*\n"
        for severity, count in report['bugs_by_severity'].items():
            if count > 0:
                percentage = (count / total_bugs) * 100 if total_bugs > 0 else 0
                message += f"  • {get_severity_emoji(severity)} {get_severity_name(severity)}: {count} ({percentage:.1f}%)\n"
        
        # 主要建议
        if report['recommendations']:
            message += "\n💡 *改进建议:*\n"
            for i, recommendation in enumerate(report['recommendations'][:3], 1):  # 只显示前3条建议
                message += f"  {i}. {recommendation}\n"
        
        message += f"\n📄 详细报告已生成"
        
        # 发送消息
        if update.message:
            await update.message.reply_text(
                message,
                parse_mode='Markdown'
            )
        
        # 记录管理员操作
        if update.effective_user:
            log_admin_operation(
                admin_id=user_id,
                admin_username=update.effective_user.username or "",
                operation="生成Bug报告",
                target="系统",
                details=f"分析周期: {days}天, Bug总数: {total_bugs}"
            )
        
    except Exception as e:
        if update.message:
            await update.message.reply_text(f"❌ 生成Bug分析报告失败: {e}")
        log_system_event("BUG_REPORT_ERROR", f"生成Bug分析报告失败: {e}")

async def bug_trend_command(update: Update, context: CallbackContext) -> None:
    """
    处理/bugtrend命令 - 查看Bug趋势
    
    Args:
        update: Telegram更新对象
        context: 回调上下文
    """
    # 检查update和user是否存在
    if not update or not update.effective_user:
        return
        
    user_id = update.effective_user.id
    
    # 检查是否是管理员
    if user_id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("⚠️ 此命令仅限管理员使用。")
        return
    
    try:
        # 获取参数，默认分析最近14天
        days = 14
        if context.args and context.args[0].isdigit():
            days = int(context.args[0])
            if days < 1:
                days = 1
            elif days > 90:
                days = 90
        
        # 分析bug日志
        report = bug_analyzer.analyze_recent_bugs(days=days)
        
        # 构建趋势消息
        message = f"📈 *Bug趋势分析*\n\n"
        message += f"📅 分析时间: {report['analysis_time']}\n"
        message += f"📈 分析周期: 最近{report['analysis_period_days']}天\n\n"
        
        # 每日趋势
        if report['daily_trend']:
            message += "📊 *每日Bug数量:*\n"
            for day, count in report['daily_trend']:
                message += f"  • {day}: {count} 个Bug\n"
            
            # 计算趋势
            if len(report['daily_trend']) >= 2:
                first_day, first_count = report['daily_trend'][0]
                last_day, last_count = report['daily_trend'][-1]
                
                if first_count > 0:
                    change_percent = ((last_count - first_count) / first_count) * 100
                    message += f"\n📈 *整体趋势:*\n"
                    message += f"  • 从 {first_count} 到 {last_count} 个Bug\n"
                    
                    if change_percent > 0:
                        message += f"  • 📈 增加 {change_percent:.1f}%\n"
                    elif change_percent < 0:
                        message += f"  • 📉 减少 {abs(change_percent):.1f}%\n"
                    else:
                        message += f"  • ➡️ 保持不变\n"
        
        # 发送消息
        if update.message:
            await update.message.reply_text(
                message,
                parse_mode='Markdown'
            )
        
        # 记录管理员操作
        if update.effective_user:
            log_admin_operation(
                admin_id=user_id,
                admin_username=update.effective_user.username or "",
                operation="查看Bug趋势",
                target="系统",
                details=f"分析周期: {days}天"
            )
        
    except Exception as e:
        if update.message:
            await update.message.reply_text(f"❌ 查看Bug趋势失败: {e}")
        log_system_event("BUG_TREND_ERROR", f"查看Bug趋势失败: {e}")

async def bug_categories_command(update: Update, context: CallbackContext) -> None:
    """
    处理/bugcategories命令 - 查看Bug分类统计
    
    Args:
        update: Telegram更新对象
        context: 回调上下文
    """
    # 检查update和user是否存在
    if not update or not update.effective_user:
        return
        
    user_id = update.effective_user.id
    
    # 检查是否是管理员
    if user_id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("⚠️ 此命令仅限管理员使用。")
        return
    
    try:
        # 分析最近30天的bug日志
        report = bug_analyzer.analyze_recent_bugs(days=30)
        
        # 构建分类统计消息
        message = f"📂 *Bug分类统计*\n\n"
        message += f"📅 分析时间: {report['analysis_time']}\n"
        message += f"📈 分析周期: 最近{report['analysis_period_days']}天\n\n"
        
        # 按类别详细统计
        message += "📊 *详细统计:*\n"
        for category, count in report['bugs_by_category'].items():
            if count > 0:
                percentage = (count / report['total_bugs']) * 100 if report['total_bugs'] > 0 else 0
                message += f"{get_category_emoji(category)} {get_category_name(category)}: {count} ({percentage:.1f}%)\n"
                
                # 显示该类别下的Top错误
                category_details = report['category_details'].get(category, {})
                top_errors = category_details.get('top_errors', [])
                if top_errors:
                    message += "  常见错误:\n"
                    for error_type, error_count in top_errors[:3]:  # 只显示前3个
                        error_percentage = (error_count / count) * 100 if count > 0 else 0
                        message += f"    • {error_type}: {error_count} ({error_percentage:.1f}%)\n"
                message += "\n"
        
        # 发送消息
        if update.message:
            await update.message.reply_text(
                message,
                parse_mode='Markdown'
            )
        
        # 记录管理员操作
        if update.effective_user:
            log_admin_operation(
                admin_id=user_id,
                admin_username=update.effective_user.username or "",
                operation="查看Bug分类统计",
                target="系统",
                details=f"分析周期: {report['analysis_period_days']}天, Bug总数: {report['total_bugs']}"
            )
        
    except Exception as e:
        if update.message:
            await update.message.reply_text(f"❌ 查看Bug分类统计失败: {e}")
        log_system_event("BUG_CATEGORIES_ERROR", f"查看Bug分类统计失败: {e}")

def get_category_emoji(category: str) -> str:
    """获取分类对应的emoji"""
    emojis = {
        'database': '🗄️',
        'network': '🌐',
        'media': '🎬',
        'permission': '🔐',
        'resource': '💾',
        'external': '🔌',
        'input': '📝',
        'scheduler': '⏰',
        'unknown': '❓'
    }
    return emojis.get(category.lower(), '📁')

def get_category_name(category: str) -> str:
    """获取分类对应的中文名称"""
    names = {
        'database': '数据库错误',
        'network': '网络错误',
        'media': '媒体错误',
        'permission': '权限错误',
        'resource': '资源错误',
        'external': '外部服务错误',
        'input': '输入错误',
        'scheduler': '定时任务错误',
        'unknown': '未知错误'
    }
    return names.get(category.lower(), category)

def get_severity_emoji(severity: str) -> str:
    """获取严重性对应的emoji"""
    emojis = {
        'critical': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }
    return emojis.get(severity.lower(), '⚪')

def get_severity_name(severity: str) -> str:
    """获取严重性对应的中文名称"""
    names = {
        'critical': '严重',
        'high': '高',
        'medium': '中',
        'low': '低'
    }
    return names.get(severity.lower(), severity)

async def bug_daily_report(update: Update, context: CallbackContext):
    """生成每日Bug报告"""
    try:
        # 获取昨天和今天的日期字符串
        yesterday = (get_beijing_now() - timedelta(days=1)).strftime("%Y-%m-%d")
        today = get_beijing_now().strftime("%Y-%m-%d")
        
        # 读取日志文件并统计Bug数量
        bug_stats = {}
        log_files = ['bugs_database.log', 'bugs_network.log', 'bugs_media.log', 
                    'bugs_permission.log', 'bugs_resource.log', 'bugs_external.log',
                    'bugs_input.log', 'bugs_scheduler.log', 'bugs_unknown.log']
        
        for log_file in log_files:
            try:
                file_path = os.path.join('logs', log_file)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        yesterday_count = 0
                        today_count = 0
                        for line in f:
                            if yesterday in line:
                                yesterday_count += 1
                            if today in line:
                                today_count += 1
                        bug_stats[log_file] = {
                            'yesterday': yesterday_count,
                            'today': today_count
                        }
            except Exception as e:
                logger.error(f"读取日志文件 {log_file} 失败: {e}")
        
        # 生成报告文本
        report = f"🐛 Bug每日报告 ({today})\n\n"
        report += f"📅 昨天 ({yesterday}): {sum(s['yesterday'] for s in bug_stats.values())} 个Bug\n"
        report += f"📅 今天: {sum(s['today'] for s in bug_stats.values())} 个Bug\n\n"
        
        if update.message:
            await update.message.reply_text(report)
    except Exception as e:
        logger.error(f"生成每日Bug报告失败: {e}")
        if update.message:
            await update.message.reply_text("生成报告时发生错误")

def setup_bug_handlers(application):
    """
    设置Bug分析相关的命令处理器
    
    Args:
        application: Telegram应用对象
    """
    # 添加命令处理器
    application.add_handler(CommandHandler("bugstats", bug_stats_command))
    application.add_handler(CommandHandler("bugreport", bug_report_command))
    application.add_handler(CommandHandler("bugtrend", bug_trend_command))
    application.add_handler(CommandHandler("bugcategories", bug_categories_command))
    
    # 添加回调处理器
    # application.add_handler(CallbackQueryHandler(bug_callback_handler, pattern="^bug_"))
    
    log_system_event("BUG_HANDLERS_SETUP", "Bug分析命令处理器已设置")