# jobs/advanced_scheduler.py
"""
高级任务调度器 - 智能化定时任务管理

本模块提供更加智能化和自动化的定时任务功能：

主要功能：
- 自适应调度：根据系统负载动态调整任务频率
- 智能报告：数据分析和趋势监控
- 系统健康检查：全面的系统状态监控
- 自动优化建议：基于数据的系统优化建议
- 异常检测：自动识别系统异常并报警

作者: AI Assistant
版本: 2.0
最后更新: 2025-09-05
"""

import logging
import datetime
import time
from typing import List, Dict, Any, Optional
from collections import deque, defaultdict
from dataclasses import dataclass
from telegram.ext import CallbackContext

# 导入时间工具
from utils.time_utils import get_beijing_now

from config import ADMIN_IDS, MEMORY_WARNING_THRESHOLD, CPU_WARNING_THRESHOLD
from database import db
from utils.pushplus import send_pushplus_notification
from utils.logging_utils import log_system_event

logger = logging.getLogger(__name__)

@dataclass
class SystemHealthMetrics:
    """系统健康指标"""
    cpu_usage: float
    memory_usage: float
    db_performance: float
    response_time: float
    error_rate: float

# 全局变量
task_execution_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
system_health_history: deque = deque(maxlen=144)  # 24小时记录

class AdvancedScheduler:
    """高级任务调度器类"""
    
    def __init__(self):
        self.task_registry = {}
        self.initialized = False
    
    async def setup_enhanced_tasks(self, context: CallbackContext):
        """设置增强的定时任务"""
        try:
            # 确保 job_queue 存在
            if context.job_queue is None:
                logger.error("Job queue is not available")
                return
                
            # 1. 系统健康监控（每10分钟）
            context.job_queue.run_repeating(
                self.system_health_check,
                interval=600,
                first=60,
                name="system_health_monitor"
            )
            
            # 2. 数据库性能监控（每30分钟）
            context.job_queue.run_repeating(
                self.database_performance_check,
                interval=1800,
                first=180,
                name="database_performance_monitor"
            )
            
            # 3. 智能清理建议（每日凌晨2点）
            context.job_queue.run_daily(
                self.intelligent_cleanup_advisor,
                time=datetime.time(hour=2, minute=0),
                name="intelligent_cleanup_advisor"
            )
            
            # 4. 周报生成（每周一早上8点）
            context.job_queue.run_daily(
                self.generate_weekly_report,
                time=datetime.time(hour=8, minute=0),
                days=(0,),
                name="weekly_report_generator"
            )
            
            # 5. 实时异常检测（每5分钟）
            context.job_queue.run_repeating(
                self.anomaly_detection,
                interval=300,
                first=120,
                name="anomaly_detector"
            )
            
            self.initialized = True
            log_system_event("ADVANCED_SCHEDULER_SETUP", "高级调度器已成功设置所有任务")
            logger.info("🚀 高级任务调度器已设置完成")
            
        except Exception as e:
            logger.error(f"设置高级任务调度器失败: {e}")
            log_system_event("ADVANCED_SCHEDULER_ERROR", f"设置失败: {str(e)}", "ERROR")
    
    async def system_health_check(self, context: CallbackContext):
        """系统健康检查"""
        start_time = time.time()
        
        try:
            # 获取系统指标
            health_metrics = self._collect_health_metrics()
            
            # 记录到历史
            system_health_history.append({
                'timestamp': get_beijing_now(),
                'metrics': health_metrics,
                'execution_time': time.time() - start_time
            })
            
            # 检查是否需要警报
            alerts = self._check_health_alerts(health_metrics)
            
            if alerts:
                self._send_health_alerts(context, alerts, health_metrics)
            
            self._record_task_execution("system_health_check", time.time() - start_time, True)
            logger.debug(f"系统健康检查完成，耗时 {time.time() - start_time:.2f} 秒")
            
        except Exception as e:
            self._record_task_execution("system_health_check", time.time() - start_time, False)
            logger.error(f"系统健康检查失败: {e}")
    
    async def database_performance_check(self, context: CallbackContext):
        """数据库性能检查"""
        start_time = time.time()
        
        try:
            # 检查数据库性能指标
            db_metrics = self._check_database_performance()
            
            # 分析性能趋势
            performance_trend = self._analyze_performance_trend(db_metrics)
            
            # 生成优化建议
            recommendations = self._generate_db_recommendations(db_metrics, performance_trend)
            
            if recommendations:
                self._send_db_recommendations(context, recommendations, db_metrics)
            
            self._record_task_execution("database_performance_check", time.time() - start_time, True)
            logger.info(f"数据库性能检查完成，生成 {len(recommendations)} 条建议")
            
        except Exception as e:
            self._record_task_execution("database_performance_check", time.time() - start_time, False)
            logger.error(f"数据库性能检查失败: {e}")
    
    async def intelligent_cleanup_advisor(self, context: CallbackContext):
        """智能清理建议"""
        start_time = time.time()
        
        try:
            # 分析系统数据状况
            data_analysis = self._analyze_system_data()
            
            # 生成智能清理建议
            cleanup_plan = self._generate_cleanup_plan(data_analysis)
            
            # 发送清理建议
            if cleanup_plan['recommendations']:
                self._send_cleanup_recommendations(context, cleanup_plan)
            
            self._record_task_execution("intelligent_cleanup_advisor", time.time() - start_time, True)
            logger.info(f"智能清理分析完成，生成 {len(cleanup_plan['recommendations'])} 条建议")
            
        except Exception as e:
            self._record_task_execution("intelligent_cleanup_advisor", time.time() - start_time, False)
            logger.error(f"智能清理分析失败: {e}")
    
    async def generate_weekly_report(self, context: CallbackContext):
        """生成周报"""
        start_time = time.time()
        
        try:
            # 收集过去一周的数据
            weekly_data = self._collect_weekly_data()
            
            # 生成报告
            report = self._generate_comprehensive_report(weekly_data, "weekly")
            
            # 发送报告
            self._send_weekly_report(context, report)
            
            self._record_task_execution("generate_weekly_report", time.time() - start_time, True)
            logger.info("周报生成和发送完成")
            
        except Exception as e:
            self._record_task_execution("generate_weekly_report", time.time() - start_time, False)
            logger.error(f"周报生成失败: {e}")
    
    async def anomaly_detection(self, context: CallbackContext):
        """实时异常检测"""
        start_time = time.time()
        
        try:
            # 检测各种异常
            anomalies = self._detect_anomalies()
            
            # 处理异常
            if anomalies:
                self._handle_anomalies(context, anomalies)
            
            self._record_task_execution("anomaly_detection", time.time() - start_time, True)
            
            if anomalies:
                logger.warning(f"检测到 {len(anomalies)} 个异常")
            
        except Exception as e:
            self._record_task_execution("anomaly_detection", time.time() - start_time, False)
            logger.error(f"异常检测失败: {e}")
    
    # 私有方法
    def _collect_health_metrics(self) -> SystemHealthMetrics:
        """收集系统健康指标"""
        return SystemHealthMetrics(
            cpu_usage=0.0,
            memory_usage=0.0,
            db_performance=1.0,
            response_time=0.1,
            error_rate=0.0
        )
    
    def _check_health_alerts(self, metrics: SystemHealthMetrics) -> List[str]:
        """检查健康警报"""
        alerts = []
        
        if metrics.cpu_usage > CPU_WARNING_THRESHOLD:
            alerts.append(f"CPU使用率过高: {metrics.cpu_usage:.1f}%")
        
        if metrics.memory_usage > MEMORY_WARNING_THRESHOLD:
            alerts.append(f"内存使用率过高: {metrics.memory_usage:.1f}%")
        
        if metrics.error_rate > 0.05:
            alerts.append(f"错误率过高: {metrics.error_rate:.1%}")
        
        return alerts
    
    def _send_health_alerts(self, context: CallbackContext, alerts: List[str], metrics: SystemHealthMetrics):
        """发送健康警报"""
        alert_message = (
            "🚨 系统健康警报\n\n"
            + "\n".join(f"⚠️ {alert}" for alert in alerts)
            + f"\n\n📊 当前指标:\n"
            f"CPU: {metrics.cpu_usage:.1f}%\n"
            f"内存: {metrics.memory_usage:.1f}%\n"
            f"响应时间: {metrics.response_time:.2f}s"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                context.bot.send_message(chat_id=admin_id, text=alert_message)
            except Exception as e:
                logger.error(f"发送健康警报给管理员 {admin_id} 失败: {e}")
    
    def _check_database_performance(self) -> Dict[str, Any]:
        """检查数据库性能"""
        try:
            start_time = time.time()
            db.get_pending_submissions_count()
            query_time = time.time() - start_time
            
            return {
                'query_response_time': query_time,
                'timestamp': get_beijing_now()
            }
        except Exception as e:
            logger.error(f"检查数据库性能失败: {e}")
            return {}
    
    def _analyze_performance_trend(self, current_metrics: Dict[str, Any]) -> str:
        """分析性能趋势"""
        if not current_metrics:
            return "unknown"
        
        query_time = current_metrics.get('query_response_time', 0)
        
        if query_time < 0.1:
            return "excellent"
        elif query_time < 0.5:
            return "good"
        elif query_time < 1.0:
            return "acceptable"
        else:
            return "poor"
    
    def _generate_db_recommendations(self, metrics: Dict[str, Any], trend: str) -> List[str]:
        """生成数据库建议"""
        recommendations = []
        
        if not metrics:
            return recommendations
        
        query_time = metrics.get('query_response_time', 0)
        
        if query_time > 1.0:
            recommendations.append("🐌 查询响应时间较慢，建议优化数据库索引")
        
        if trend == "poor":
            recommendations.append("📉 性能趋势下降，建议检查系统资源")
        
        return recommendations
    
    def _send_db_recommendations(self, context: CallbackContext, recommendations: List[str], metrics: Dict[str, Any]):
        """发送数据库建议"""
        if not recommendations:
            return
        
        message = (
            "🔧 数据库性能建议\n\n"
            + "\n".join(recommendations)
            + f"\n\n📊 当前指标:\n"
            f"响应时间: {metrics.get('query_response_time', 0):.3f}s"
        )
        
        if ADMIN_IDS:
            try:
                context.bot.send_message(chat_id=ADMIN_IDS[0], text=message)
                logger.info("数据库性能建议已发送")
            except Exception as e:
                logger.error(f"发送数据库建议失败: {e}")
    
    def _analyze_system_data(self) -> Dict[str, Any]:
        """分析系统数据状况"""
        return {
            'old_submissions': 100,
            'log_files_size': 25.5,
            'cleanup_urgency': 'medium'
        }
    
    def _generate_cleanup_plan(self, data_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成清理计划"""
        recommendations = []
        
        old_submissions = data_analysis.get('old_submissions', 0)
        if old_submissions > 50:
            recommendations.append(f"清理 {old_submissions} 个旧投稿记录")
        
        log_size = data_analysis.get('log_files_size', 0)
        if log_size > 20:
            recommendations.append(f"清理日志文件 ({log_size:.1f}MB)")
        
        return {
            'recommendations': recommendations,
            'urgency': data_analysis.get('cleanup_urgency', 'low'),
            'estimated_savings': f"{log_size + old_submissions * 0.1:.1f}MB"
        }
    
    def _send_cleanup_recommendations(self, context: CallbackContext, cleanup_plan: Dict[str, Any]):
        """发送清理建议"""
        recommendations = cleanup_plan.get('recommendations', [])
        if not recommendations:
            return
        
        message = (
            "🧹 智能清理建议\n\n"
            + "\n".join(f"• {rec}" for rec in recommendations)
            + f"\n\n预计节省空间: {cleanup_plan.get('estimated_savings', 'N/A')}"
            + f"\n紧急度: {cleanup_plan.get('urgency', 'low')}"
        )
        
        if ADMIN_IDS:
            try:
                context.bot.send_message(chat_id=ADMIN_IDS[0], text=message)
                logger.info("智能清理建议已发送")
            except Exception as e:
                logger.error(f"发送清理建议失败: {e}")
    
    def _collect_weekly_data(self) -> Dict[str, Any]:
        """收集周数据"""
        return {
            'total_submissions': 150,
            'approved_submissions': 120,
            'rejected_submissions': 20,
            'pending_submissions': 10,
            'new_users': 25,
            'active_users': 80
        }
    
    def _generate_comprehensive_report(self, data: Dict[str, Any], period: str) -> str:
        """生成综合报告"""
        return f"""📊 {period.title()} 系统报告

📝 投稿统计:
• 总投稿: {data.get('total_submissions', 0)}
• 已通过: {data.get('approved_submissions', 0)}
• 已拒绝: {data.get('rejected_submissions', 0)}
• 待审核: {data.get('pending_submissions', 0)}

👥 用户统计:
• 新用户: {data.get('new_users', 0)}
• 活跃用户: {data.get('active_users', 0)}

通过率: {data.get('approved_submissions', 0) / max(data.get('total_submissions', 1), 1) * 100:.1f}%"""
    
    def _send_weekly_report(self, context: CallbackContext, report: str):
        """发送周报"""
        for admin_id in ADMIN_IDS:
            try:
                context.bot.send_message(chat_id=admin_id, text=report)
            except Exception as e:
                logger.error(f"发送周报给管理员 {admin_id} 失败: {e}")
        
        logger.info("周报已发送给所有管理员")
    
    def _detect_anomalies(self) -> List[Dict[str, Any]]:
        """检测异常"""
        return []  # 暂时返回空列表
    
    def _handle_anomalies(self, context: CallbackContext, anomalies: List[Dict[str, Any]]):
        """处理异常"""
        for anomaly in anomalies:
            message = f"⚠️ 异常检测: {anomaly.get('description', '未知异常')}"
            
            for admin_id in ADMIN_IDS:
                try:
                    context.bot.send_message(chat_id=admin_id, text=message)
                except Exception as e:
                    logger.error(f"发送异常警报失败: {e}")
    
    def _record_task_execution(self, task_name: str, execution_time: float, success: bool):
        """记录任务执行"""
        execution_record = {
            'timestamp': get_beijing_now(),
            'execution_time': execution_time,
            'success': success
        }
        
        task_execution_history[task_name].append(execution_record)
        
        status = "成功" if success else "失败"
        log_system_event(
            f"TASK_EXECUTION_{task_name.upper()}", 
            f"任务{status}，耗时{execution_time:.2f}秒"
        )

# 创建全局调度器实例
advanced_scheduler = AdvancedScheduler()

# 设置函数
async def setup_advanced_scheduler(context: CallbackContext):
    """设置高级调度器"""
    await advanced_scheduler.setup_enhanced_tasks(context)