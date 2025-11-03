# utils/monitoring_init.py
"""
监控系统初始化模块 - 启动和配置监控服务

本模块负责初始化和启动整个监控系统：

主要功能：
- 启动系统监控服务
- 初始化报警规则
- 配置通知回调
- 注册监控装饰器
- 设置定时检查任务

系统集成：
- 与现有日志系统集成
- 与Telegram机器人通知集成
- 与定时任务系统集成

作者: AI Assistant
版本: 2.0
最后更新: 2025-09-05
"""

import logging
from telegram.ext import CallbackContext

from utils.monitoring import monitoring_manager, start_monitoring
from utils.log_analyzer import log_analyzer
from utils.logging_utils import log_system_event
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

def initialize_monitoring_system(context: CallbackContext = None):
    """初始化监控系统"""
    try:
        logger.info("正在初始化监控和日志系统...")
        
        # 启动系统监控
        start_monitoring()
        
        # 设置通知回调
        if context:
            monitoring_manager.add_notification_callback(
                lambda alert: _send_telegram_alert(context, alert)
            )
        
        # 设置定时报警检查（如果有context的话）
        if context:
            # 每5分钟检查一次报警
            context.job_queue.run_repeating(
                _check_alerts_job,
                interval=300,  # 5分钟
                first=60,      # 1分钟后开始
                name="monitoring_alerts_check"
            )
            
            # 每小时分析一次日志
            context.job_queue.run_repeating(
                _analyze_logs_job,
                interval=3600,  # 1小时
                first=1800,     # 30分钟后开始
                name="log_analysis_check"
            )
        
        log_system_event("MONITORING_INITIALIZED", "监控和日志系统初始化完成")
        logger.info("✅ 监控和日志系统初始化完成")
        
        return True
        
    except Exception as e:
        logger.error(f"监控系统初始化失败: {e}")
        log_system_event("MONITORING_INIT_FAILED", f"监控系统初始化失败: {str(e)}", "ERROR")
        return False

def _send_telegram_alert(context: CallbackContext, alert):
    """发送Telegram报警通知"""
    try:
        alert_message = f"🚨 **系统报警**\n\n"
        alert_message += f"• **类型**: {alert.rule.message or alert.rule.metric_name}\n"
        alert_message += f"• **级别**: {alert.rule.level.value.upper()}\n"
        alert_message += f"• **当前值**: {alert.metric_value.value:.2f}\n"
        alert_message += f"• **阈值**: {alert.rule.threshold}\n"
        alert_message += f"• **时间**: {alert.triggered_at}\n"
        
        # 发送给所有管理员
        for admin_id in ADMIN_IDS:
            try:
                context.bot.send_message(
                    chat_id=admin_id,
                    text=alert_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"发送报警通知给管理员 {admin_id} 失败: {e}")
                
    except Exception as e:
        logger.error(f"处理Telegram报警通知失败: {e}")

def _check_alerts_job(context: CallbackContext):
    """定时检查报警任务"""
    try:
        monitoring_manager.check_and_notify_alerts()
    except Exception as e:
        logger.error(f"定时报警检查失败: {e}")

def _analyze_logs_job(context: CallbackContext):
    """定时日志分析任务"""
    try:
        # 分析最近1小时的日志
        from utils.log_analyzer import detect_log_anomalies
        
        anomalies = detect_log_anomalies(1)
        
        # 如果发现异常，发送通知
        if anomalies:
            alert_message = f"📋 **日志异常检测**\n\n"
            alert_message += f"发现 {len(anomalies)} 个日志异常：\n\n"
            
            for anomaly in anomalies[:3]:  # 只显示前3个
                alert_message += f"• **{anomaly.title}**\n"
                alert_message += f"  └ {anomaly.description}\n"
                alert_message += f"  └ 置信度: {anomaly.confidence:.1%}\n\n"
            
            # 发送给所有管理员
            for admin_id in ADMIN_IDS:
                try:
                    context.bot.send_message(
                        chat_id=admin_id,
                        text=alert_message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"发送日志异常通知给管理员 {admin_id} 失败: {e}")
                    
    except Exception as e:
        logger.error(f"定时日志分析失败: {e}")

def get_monitoring_status():
    """获取监控系统状态"""
    try:
        dashboard_data = monitoring_manager.get_monitoring_dashboard_data()
        
        status = {
            'monitoring_active': hasattr(monitoring_manager.system_monitor, 'running') and monitoring_manager.system_monitor.running,
            'active_alerts': dashboard_data.get('active_alerts', 0),
            'system_health': 'good',
            'last_update': dashboard_data.get('timestamp', 0)
        }
        
        # 判断系统健康状况
        active_alerts = dashboard_data.get('active_alerts', 0)
        if active_alerts > 5:
            status['system_health'] = 'critical'
        elif active_alerts > 2:
            status['system_health'] = 'warning'
        elif active_alerts > 0:
            status['system_health'] = 'caution'
        
        return status
        
    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        return {
            'monitoring_active': False,
            'active_alerts': 0,
            'system_health': 'unknown',
            'last_update': 0,
            'error': str(e)
        }

def shutdown_monitoring_system():
    """关闭监控系统"""
    try:
        from utils.monitoring import stop_monitoring
        stop_monitoring()
        
        log_system_event("MONITORING_SHUTDOWN", "监控系统已关闭")
        logger.info("监控系统已关闭")
        
    except Exception as e:
        logger.error(f"关闭监控系统失败: {e}")
        log_system_event("MONITORING_SHUTDOWN_FAILED", f"关闭监控系统失败: {str(e)}", "ERROR")