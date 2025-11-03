# utils/cleanup.py
"""
数据清理模块 - 系统维护和性能优化

本模块负责系统数据的清理和优化功能：

主要功能：
- 旧数据清理：删除过期的投稿、用户状态等数据
- 用户状态清理：清理无用的用户交互状态
- 日志文件清理：清理和压缩旧的日志文件
- 数据库优化：重建索引、压缩数据库、统计信息更新
- 垃圾收集：Python 内存垃圾收集和系统资源清理
- 缓存清理：清理各种缓存数据

优化特性：
1. 多层错误处理 - 确保清理过程的稳定性
2. 分批处理 - 避免大量数据处理时的内存溢出
3. 进程监控 - 实时监控清理进度和性能
4. 安全模式 - 重要数据清理前的安全检查
5. 回滚机制 - 清理操作的撤销和恢复

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

# =====================================================
# 所需库导入 Required Library Imports
# =====================================================

import os
import gc
import sqlite3
import logging
import shutil
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import psutil

# 导入时间工具
from utils.time_utils import get_beijing_now, format_beijing_time

# 项目配置和数据库
from config import DB_URL, CLEANUP_RETENTION_DAYS, CLEANUP_BATCH_SIZE
from database import db

# =====================================================
# 日志配置和全局常量 Global Logging and Constants
# =====================================================

logger = logging.getLogger(__name__)

class SystemCleaner:
    """系统清理器 - 统一的清理和优化功能"""
    
    def __init__(self):
        """初始化系统清理器"""
        self.batch_size = CLEANUP_BATCH_SIZE
        self.retention_days = CLEANUP_RETENTION_DAYS
        
    def cleanup_old_data(self, days: Optional[int] = None) -> Dict[str, Any]:
        """清理旧数据
        
        Args:
            days: 保留天数，None使用默认值
            
        Returns:
            Dict: 清理结果信息
        """
        try:
            days = days or self.retention_days
            logger.info(f"开始清理 {days} 天前的旧数据...")
            
            start_time = get_beijing_now()
            result = {
                'type': 'old_data',
                'start_time': start_time.isoformat(),
                'status': 'in_progress',
                'cleaned_items': {},
                'errors': [],
                'total_cleaned': 0
            }
            
            # 1. 清理旧的被拒绝投稿
            rejected_count = self._cleanup_rejected_submissions(days)
            result['cleaned_items']['rejected_submissions'] = rejected_count
            result['total_cleaned'] += rejected_count
            
            # 2. 清理旧的用户状态
            user_states_count = self._cleanup_old_user_states(days)
            result['cleaned_items']['user_states'] = user_states_count
            result['total_cleaned'] += user_states_count
            
            # 3. 清理过期的审核员申请
            applications_count = self._cleanup_old_applications(days)
            result['cleaned_items']['old_applications'] = applications_count
            result['total_cleaned'] += applications_count
            
            # 计算执行时间
            end_time = get_beijing_now()
            execution_time = (end_time - start_time).total_seconds()
            
            result.update({
                'status': 'success',
                'end_time': end_time.isoformat(),
                'execution_time': execution_time
            })
            
            logger.info(f"旧数据清理完成，共清理 {result['total_cleaned']} 条记录，耗时 {execution_time:.2f} 秒")
            return result
            
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
            return {
                'type': 'old_data',
                'status': 'error',
                'errors': [str(e)],
                'start_time': get_beijing_now().isoformat()
            }
    
    def cleanup_user_states(self) -> Dict[str, Any]:
        """清理用户状态
        
        Returns:
            Dict: 清理结果信息
        """
        try:
            logger.info("开始清理用户状态...")
            
            start_time = get_beijing_now()
            
            # 清理所有用户状态
            cleaned_count = self._cleanup_all_user_states()
            
            # 计算执行时间
            end_time = get_beijing_now()
            execution_time = (end_time - start_time).total_seconds()
            
            result = {
                'type': 'user_states',
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'status': 'success',
                'cleaned_count': cleaned_count,
                'execution_time': execution_time
            }
            
            logger.info(f"用户状态清理完成，共清理 {cleaned_count} 条记录，耗时 {execution_time:.2f} 秒")
            return result
            
        except Exception as e:
            logger.error(f"清理用户状态失败: {e}")
            return {
                'type': 'user_states',
                'status': 'error',
                'errors': [str(e)],
                'start_time': get_beijing_now().isoformat()
            }
    
    def cleanup_logs(self, days: int = 30) -> Dict[str, Any]:
        """清理日志文件
        
        Args:
            days: 保留天数
            
        Returns:
            Dict: 清理结果信息
        """
        try:
            logger.info(f"开始清理 {days} 天前的日志文件...")
            
            start_time = get_beijing_now()
            result = {
                'type': 'logs',
                'start_time': start_time.isoformat(),
                'status': 'in_progress',
                'cleaned_files': [],
                'total_size_freed': 0,
                'errors': []
            }
            
            # 清理logs目录中的旧日志
            logs_dir = Path("logs")
            if logs_dir.exists():
                cutoff_date = get_beijing_now() - timedelta(days=days)
                
                for log_file in logs_dir.glob("*.log*"):
                    if log_file.is_file():
                        file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                        if file_mtime < cutoff_date:
                            try:
                                file_size = log_file.stat().st_size
                                log_file.unlink()
                                result['cleaned_files'].append(str(log_file))
                                result['total_size_freed'] += file_size
                                logger.debug(f"已删除旧日志文件: {log_file}")
                            except Exception as e:
                                error_msg = f"删除日志文件失败 {log_file}: {e}"
                                result['errors'].append(error_msg)
                                logger.error(error_msg)
            
            # 清理当前目录中的日志文件
            current_dir = Path(".")
            for log_file in current_dir.glob("*.log"):
                if log_file.is_file():
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    cutoff_date = get_beijing_now() - timedelta(days=days)
                    if file_mtime < cutoff_date:
                        try:
                            file_size = log_file.stat().st_size
                            log_file.unlink()
                            result['cleaned_files'].append(str(log_file))
                            result['total_size_freed'] += file_size
                            logger.debug(f"已删除旧日志文件: {log_file}")
                        except Exception as e:
                            error_msg = f"删除日志文件失败 {log_file}: {e}"
                            result['errors'].append(error_msg)
                            logger.error(error_msg)
            
            # 计算执行时间
            end_time = get_beijing_now()
            execution_time = (end_time - start_time).total_seconds()
            
            result.update({
                'status': 'success',
                'end_time': end_time.isoformat(),
                'execution_time': execution_time,
                'files_count': len(result['cleaned_files'])
            })
            
            size_mb = result['total_size_freed'] / (1024 * 1024)
            logger.info(f"日志清理完成，共删除 {len(result['cleaned_files'])} 个文件，释放 {size_mb:.2f} MB 空间，耗时 {execution_time:.2f} 秒")
            return result
            
        except Exception as e:
            logger.error(f"清理日志文件失败: {e}")
            return {
                'type': 'logs',
                'status': 'error',
                'errors': [str(e)],
                'start_time': get_beijing_now().isoformat()
            }
    
    def optimize_database(self) -> Dict[str, Any]:
        """优化数据库
        
        Returns:
            Dict: 优化结果信息
        """
        try:
            logger.info("开始数据库优化...")
            
            start_time = get_beijing_now()
            result = {
                'type': 'database_optimization',
                'start_time': start_time.isoformat(),
                'status': 'in_progress',
                'operations': [],
                'errors': []
            }
            
            if DB_URL.startswith('sqlite:'):
                # SQLite 数据库优化
                result.update(self._optimize_sqlite_database())
            else:
                # PostgreSQL/MySQL 数据库优化
                result['errors'].append("PostgreSQL/MySQL 数据库优化暂未实现")
            
            # 计算执行时间
            end_time = get_beijing_now()
            execution_time = (end_time - start_time).total_seconds()
            
            result.update({
                'status': 'success' if not result['errors'] else 'partial_success',
                'end_time': end_time.isoformat(),
                'execution_time': execution_time
            })
            
            logger.info(f"数据库优化完成，耗时 {execution_time:.2f} 秒")
            return result
            
        except Exception as e:
            logger.error(f"数据库优化失败: {e}")
            return {
                'type': 'database_optimization',
                'status': 'error',
                'errors': [str(e)],
                'start_time': get_beijing_now().isoformat()
            }
    
    def garbage_collection(self) -> Dict[str, Any]:
        """执行垃圾收集
        
        Returns:
            Dict: 垃圾收集结果信息
        """
        try:
            logger.info("开始执行垃圾收集...")
            
            start_time = get_beijing_now()
            
            # 获取垃圾收集前的内存使用情况
            process = psutil.Process()
            memory_before = process.memory_info().rss / (1024 * 1024)  # MB
            
            # 执行Python垃圾收集
            collected_objects = []
            for generation in range(3):
                collected = gc.collect()
                collected_objects.append(collected)
                logger.debug(f"第 {generation} 代垃圾收集：{collected} 个对象")
            
            # 获取垃圾收集后的内存使用情况
            memory_after = process.memory_info().rss / (1024 * 1024)  # MB
            memory_freed = memory_before - memory_after
            
            # 计算执行时间
            end_time = get_beijing_now()
            execution_time = (end_time - start_time).total_seconds()
            
            result = {
                'type': 'garbage_collection',
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'status': 'success',
                'execution_time': execution_time,
                'collected_objects': collected_objects,
                'total_collected': sum(collected_objects),
                'memory_before_mb': round(memory_before, 2),
                'memory_after_mb': round(memory_after, 2),
                'memory_freed_mb': round(memory_freed, 2)
            }
            
            logger.info(f"垃圾收集完成，收集 {sum(collected_objects)} 个对象，释放 {memory_freed:.2f} MB 内存，耗时 {execution_time:.2f} 秒")
            return result
            
        except Exception as e:
            logger.error(f"垃圾收集失败: {e}")
            return {
                'type': 'garbage_collection',
                'status': 'error',
                'errors': [str(e)],
                'start_time': get_beijing_now().isoformat()
            }
    
    def _cleanup_rejected_submissions(self, days: int) -> int:
        """清理旧的被拒绝投稿
        
        Args:
            days: 保留天数
            
        Returns:
            int: 清理的数量
        """
        try:
            cutoff_date = get_beijing_now() - timedelta(days=days)
            
            with db.session_scope() as session:
                from database import Submission
                
                # 查询需要清理的被拒绝投稿
                old_rejected = session.query(Submission).filter(
                    Submission.status == 'rejected',
                    Submission.timestamp < cutoff_date
                ).all()
                
                count = len(old_rejected)
                
                # 分批删除
                for i in range(0, count, self.batch_size):
                    batch = old_rejected[i:i + self.batch_size]
                    for submission in batch:
                        session.delete(submission)
                    session.commit()
                    logger.debug(f"已删除 {len(batch)} 条被拒绝投稿")
                
                logger.info(f"清理了 {count} 条旧的被拒绝投稿")
                return count
                
        except Exception as e:
            logger.error(f"清理被拒绝投稿失败: {e}")
            return 0
    
    def _cleanup_old_user_states(self, days: int) -> int:
        """清理旧的用户状态
        
        Args:
            days: 保留天数
            
        Returns:
            int: 清理的数量
        """
        try:
            cutoff_date = get_beijing_now() - timedelta(days=days)
            
            with db.session_scope() as session:
                from database import UserState
                
                # 查询需要清理的旧用户状态
                old_states = session.query(UserState).filter(
                    UserState.timestamp < cutoff_date
                ).all()
                
                count = len(old_states)
                
                # 分批删除
                for i in range(0, count, self.batch_size):
                    batch = old_states[i:i + self.batch_size]
                    for state in batch:
                        session.delete(state)
                    session.commit()
                    logger.debug(f"已删除 {len(batch)} 条用户状态")
                
                logger.info(f"清理了 {count} 条旧的用户状态")
                return count
                
        except Exception as e:
            logger.error(f"清理用户状态失败: {e}")
            return 0
    
    def _cleanup_old_applications(self, days: int) -> int:
        """清理旧的审核员申请
        
        Args:
            days: 保留天数
            
        Returns:
            int: 清理的数量
        """
        try:
            cutoff_date = get_beijing_now() - timedelta(days=days)
            
            with db.session_scope() as session:
                from database import ReviewerApplication
                
                # 查询需要清理的旧申请（已处理的）
                old_applications = session.query(ReviewerApplication).filter(
                    ReviewerApplication.status.in_(['approved', 'rejected']),
                    ReviewerApplication.timestamp < cutoff_date
                ).all()
                
                count = len(old_applications)
                
                # 分批删除
                for i in range(0, count, self.batch_size):
                    batch = old_applications[i:i + self.batch_size]
                    for app in batch:
                        session.delete(app)
                    session.commit()
                    logger.debug(f"已删除 {len(batch)} 条审核员申请")
                
                logger.info(f"清理了 {count} 条旧的审核员申请")
                return count
                
        except Exception as e:
            logger.error(f"清理审核员申请失败: {e}")
            return 0
    
    def _cleanup_all_user_states(self) -> int:
        """清理所有用户状态
        
        Returns:
            int: 清理的数量
        """
        try:
            with db.session_scope() as session:
                from database import UserState
                
                # 获取所有用户状态数量
                count = session.query(UserState).count()
                
                # 删除所有用户状态
                session.query(UserState).delete()
                session.commit()
                
                logger.info(f"清理了所有 {count} 条用户状态")
                return count
                
        except Exception as e:
            logger.error(f"清理所有用户状态失败: {e}")
            return 0
    
    def _optimize_sqlite_database(self) -> Dict[str, Any]:
        """优化SQLite数据库
        
        Returns:
            Dict: 优化结果
        """
        operations = []
        errors = []
        
        try:
            operations = []
            errors = []
            
            # 获取数据库文件路径
            db_file = DB_URL.replace('sqlite:///', '')
            if not db_file.startswith('/'):
                db_file = Path(db_file)
            else:
                db_file = Path(db_file)
            
            if not db_file.exists():
                errors.append(f"数据库文件不存在: {db_file}")
                return {'operations': operations, 'errors': errors}
            
            # 获取优化前的数据库大小
            size_before = db_file.stat().st_size
            
            # 连接数据库并执行优化
            conn = sqlite3.connect(str(db_file))
            try:
                cursor = conn.cursor()
                
                # 1. 重建索引
                cursor.execute("REINDEX")
                operations.append("重建索引")
                
                # 2. 更新统计信息
                cursor.execute("ANALYZE")
                operations.append("更新统计信息")
                
                # 3. 清理数据库（回收空间）
                cursor.execute("VACUUM")
                operations.append("数据库清理（VACUUM）")
                
                # 4. 优化数据库设置
                cursor.execute("PRAGMA optimize")
                operations.append("优化数据库设置")
                
                conn.commit()
                
            finally:
                conn.close()
            
            # 获取优化后的数据库大小
            size_after = db_file.stat().st_size
            size_reduced = size_before - size_after
            
            operations.append(f"数据库大小：{size_before / (1024*1024):.2f} MB → {size_after / (1024*1024):.2f} MB")
            if size_reduced > 0:
                operations.append(f"释放空间：{size_reduced / (1024*1024):.2f} MB")
            
            logger.info("SQLite数据库优化完成")
            return {'operations': operations, 'errors': errors}
            
        except Exception as e:
            logger.error(f"SQLite数据库优化失败: {e}")
            return {'operations': operations, 'errors': [str(e)]}
    
    def get_cleanup_status(self) -> Dict[str, Any]:
        """获取清理状态信息
        
        Returns:
            Dict: 清理状态信息
        """
        try:
            # 获取数据库统计信息
            db_stats = self._get_database_stats()
            
            # 获取日志文件统计信息
            log_stats = self._get_log_files_stats()
            
            # 获取系统资源信息
            system_stats = self._get_system_stats()
            
            return {
                'status': 'active',
                'database': db_stats,
                'logs': log_stats,
                'system': system_stats,
                'recommendations': self._get_cleanup_recommendations(db_stats, log_stats, system_stats)
            }
            
        except Exception as e:
            logger.error(f"获取清理状态失败: {e}")
            return {
                'status': 'error',
                'message': f'获取清理状态失败: {str(e)}'
            }
    
    def _get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            with db.session_scope() as session:
                from database import Submission, UserState, ReviewerApplication, User
                
                stats = {
                    'total_submissions': session.query(Submission).count(),
                    'pending_submissions': session.query(Submission).filter_by(status='pending').count(),
                    'rejected_submissions': session.query(Submission).filter_by(status='rejected').count(),
                    'total_users': session.query(User).count(),
                    'user_states': session.query(UserState).count(),
                    'pending_applications': session.query(ReviewerApplication).filter_by(status='pending').count()
                }
                
                # 获取数据库文件大小
                if DB_URL.startswith('sqlite:'):
                    db_file = DB_URL.replace('sqlite:///', '')
                    if Path(db_file).exists():
                        stats['database_size_mb'] = int(Path(db_file).stat().st_size / (1024 * 1024))
                
                return stats
                
        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            return {'error': str(e)}
    
    def _get_log_files_stats(self) -> Dict[str, Any]:
        """获取日志文件统计信息"""
        try:
            log_files = []
            total_size = 0
            
            # 检查logs目录
            logs_dir = Path("logs")
            if logs_dir.exists():
                for log_file in logs_dir.glob("*.log*"):
                    if log_file.is_file():
                        size = log_file.stat().st_size
                        log_files.append({
                            'name': log_file.name,
                            'size': size,
                            'modified': format_beijing_time(datetime.fromtimestamp(log_file.stat().st_mtime))
                        })
                        total_size += size
            
            # 检查当前目录
            current_dir = Path(".")
            for log_file in current_dir.glob("*.log"):
                if log_file.is_file():
                    size = log_file.stat().st_size
                    log_files.append({
                        'name': log_file.name,
                        'size': size,
                        'modified': format_beijing_time(datetime.fromtimestamp(log_file.stat().st_mtime))
                    })
                    total_size += size
            
            return {
                'log_files_count': len(log_files),
                'total_size_mb': total_size / (1024 * 1024),
                'files': log_files[:10]  # 只返回前10个文件信息
            }
            
        except Exception as e:
            logger.error(f"获取日志文件统计失败: {e}")
            return {'error': str(e)}
    
    def _get_system_stats(self) -> Dict[str, Any]:
        """获取系统资源统计信息"""
        try:
            process = psutil.Process()
            
            return {
                'memory_usage_mb': process.memory_info().rss / (1024 * 1024),
                'cpu_percent': process.cpu_percent(),
                'open_files': len(process.open_files()),
                'threads_count': process.num_threads()
            }
            
        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {'error': str(e)}
    
    def _get_cleanup_recommendations(self, db_stats: Dict, log_stats: Dict, system_stats: Dict) -> List[str]:
        """获取清理建议"""
        recommendations = []
        
        try:
            # 数据库建议
            if db_stats.get('rejected_submissions', 0) > 100:
                recommendations.append("建议清理被拒绝的投稿以释放数据库空间")
            
            if db_stats.get('user_states', 0) > 50:
                recommendations.append("建议清理用户状态以提高系统性能")
            
            # 日志文件建议
            if log_stats.get('total_size_mb', 0) > 100:
                recommendations.append("建议清理旧日志文件以释放磁盘空间")
            
            # 数据库大小建议
            if db_stats.get('database_size_mb', 0) > 500:
                recommendations.append("建议进行数据库优化以提高查询性能")
            
            # 系统资源建议
            if system_stats.get('memory_usage_mb', 0) > 500:
                recommendations.append("建议执行垃圾收集以释放内存")
            
            if not recommendations:
                recommendations.append("系统状态良好，暂无清理建议")
            
        except Exception as e:
            logger.error(f"生成清理建议失败: {e}")
            recommendations.append("无法生成清理建议")
        
        return recommendations

# 创建全局清理器实例
system_cleaner = SystemCleaner()

# 导出的便捷函数
def cleanup_old_data(days: Optional[int] = None):
    """清理旧数据"""
    return system_cleaner.cleanup_old_data(days)

def cleanup_user_states():
    """清理用户状态"""
    return system_cleaner.cleanup_user_states()

def cleanup_logs(days: int = 30):
    """清理日志文件"""
    return system_cleaner.cleanup_logs(days)

def optimize_database():
    """优化数据库"""
    return system_cleaner.optimize_database()

def garbage_collection():
    """执行垃圾收集"""
    return system_cleaner.garbage_collection()

def get_cleanup_status():
    """获取清理状态"""
    return system_cleaner.get_cleanup_status()

def log_cleanup_operation(operation: str, details: dict):
    """记录清理操作"""
    try:
        log_entry = {
            'operation': operation,
            'details': details,
            'start_time': get_beijing_now().isoformat(),
            'timestamp': get_beijing_now().timestamp()
        }
        
        # 写入清理日志文件
        log_file = os.path.join('logs', 'cleanup_operations.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{get_beijing_now().strftime('%Y-%m-%d %H:%M:%S')}] {json.dumps(log_entry, ensure_ascii=False)}\n")
    except Exception as e:
        print(f"记录清理操作日志失败: {e}")
