# utils/bug_logger.py
"""
Bug日志记录模块 - 专门用于记录各类bug和错误

本模块提供细粒度的bug分类记录功能，将不同类型的bug分别记录到单独的文件中。

主要功能：
1. 数据库相关Bug日志 - 记录所有数据库操作错误
2. 网络相关Bug日志 - 记录网络连接和API调用错误
3. 媒体处理Bug日志 - 记录图片、视频等媒体处理错误
4. 权限相关Bug日志 - 记录用户权限和认证错误
5. 系统资源Bug日志 - 记录内存、CPU等系统资源错误
6. 第三方服务Bug日志 - 记录外部服务调用错误
7. 用户输入Bug日志 - 记录用户输入验证和处理错误
8. 定时任务Bug日志 - 记录定时任务执行错误

设计目的：
- 精细化分类不同类型的bug
- 便于快速定位和解决特定类型的问题
- 支持bug统计和分析
- 提供bug追踪和报告功能

作者: AI Assistant
版本: 2.1
最后更新: 2025-09-15
"""

import logging
import os
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any
from config import LOG_FILE_MAX_SIZE, LOG_BACKUP_COUNT, ENABLE_FILE_LOGGING

class BugLogger:
    """Bug日志记录器类"""
    
    def __init__(self, logs_dir: str = "logs"):
        """
        初始化Bug日志记录器
        
        Args:
            logs_dir: 日志目录路径
        """
        self.logs_dir = logs_dir
        self.loggers = {}
        self._setup_bug_loggers()
    
    def _setup_bug_loggers(self):
        """设置各类bug的日志记录器"""
        if not ENABLE_FILE_LOGGING:
            return
            
        # 确保日志目录存在
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
        
        # 定义各类bug的日志配置
        bug_types = {
            "database": {
                "filename": "bugs_database.log",
                "description": "数据库相关Bug"
            },
            "network": {
                "filename": "bugs_network.log", 
                "description": "网络相关Bug"
            },
            "media": {
                "filename": "bugs_media.log",
                "description": "媒体处理Bug"
            },
            "permission": {
                "filename": "bugs_permission.log",
                "description": "权限相关Bug"
            },
            "resource": {
                "filename": "bugs_resource.log",
                "description": "系统资源Bug"
            },
            "external": {
                "filename": "bugs_external.log",
                "description": "第三方服务Bug"
            },
            "input": {
                "filename": "bugs_input.log",
                "description": "用户输入Bug"
            },
            "scheduler": {
                "filename": "bugs_scheduler.log",
                "description": "定时任务Bug"
            }
        }
        
        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 为每种bug类型创建日志记录器
        for bug_type, config in bug_types.items():
            logger_name = f"bug_{bug_type}"
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)
            
            # 避免重复添加处理器
            if not logger.handlers:
                handler = RotatingFileHandler(
                    os.path.join(self.logs_dir, config["filename"]),
                    maxBytes=LOG_FILE_MAX_SIZE // 2,  # Bug日志文件小一些
                    backupCount=LOG_BACKUP_COUNT,
                    encoding='utf-8'
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)
            
            self.loggers[bug_type] = {
                "logger": logger,
                "description": config["description"]
            }
    
    def log_database_bug(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        记录数据库相关bug
        
        Args:
            error: 异常对象
            context: 上下文信息
        """
        logger = self.loggers.get("database", {}).get("logger")
        if not logger:
            return
            
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"DATABASE_ERROR: {str(error)}{context_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def log_network_bug(self, error: Exception, url: str = "", context: Optional[Dict[str, Any]] = None):
        """
        记录网络相关bug
        
        Args:
            error: 异常对象
            url: 请求的URL
            context: 上下文信息
        """
        logger = self.loggers.get("network", {}).get("logger")
        if not logger:
            return
            
        url_info = f" | URL: {url}" if url else ""
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"NETWORK_ERROR: {str(error)}{url_info}{context_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def log_media_bug(self, error: Exception, media_type: str = "", file_id: str = "", context: Optional[Dict[str, Any]] = None):
        """
        记录媒体处理相关bug
        
        Args:
            error: 异常对象
            media_type: 媒体类型 (photo/video/document等)
            file_id: 文件ID
            context: 上下文信息
        """
        logger = self.loggers.get("media", {}).get("logger")
        if not logger:
            return
            
        media_info = f" | Media: {media_type}" if media_type else ""
        file_info = f" | FileID: {file_id}" if file_id else ""
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"MEDIA_ERROR: {str(error)}{media_info}{file_info}{context_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def log_permission_bug(self, error: Exception, user_id: int = "", operation: str = "", context: Optional[Dict[str, Any]] = None):
        """
        记录权限相关bug
        
        Args:
            error: 异常对象
            user_id: 用户ID
            operation: 尝试的操作
            context: 上下文信息
        """
        logger = self.loggers.get("permission", {}).get("logger")
        if not logger:
            return
            
        user_info = f" | User: {user_id}" if user_id else ""
        operation_info = f" | Operation: {operation}" if operation else ""
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"PERMISSION_ERROR: {str(error)}{user_info}{operation_info}{context_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def log_resource_bug(self, error: Exception, resource_type: str = "", usage: str = "", context: Optional[Dict[str, Any]] = None):
        """
        记录系统资源相关bug
        
        Args:
            error: 异常对象
            resource_type: 资源类型 (memory/cpu/disk等)
            usage: 资源使用情况
            context: 上下文信息
        """
        logger = self.loggers.get("resource", {}).get("logger")
        if not logger:
            return
            
        resource_info = f" | Resource: {resource_type}" if resource_type else ""
        usage_info = f" | Usage: {usage}" if usage else ""
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"RESOURCE_ERROR: {str(error)}{resource_info}{usage_info}{context_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def log_external_bug(self, error: Exception, service: str = "", context: Optional[Dict[str, Any]] = None):
        """
        记录第三方服务相关bug
        
        Args:
            error: 异常对象
            service: 第三方服务名称
            context: 上下文信息
        """
        logger = self.loggers.get("external", {}).get("logger")
        if not logger:
            return
            
        service_info = f" | Service: {service}" if service else ""
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"EXTERNAL_ERROR: {str(error)}{service_info}{context_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def log_input_bug(self, error: Exception, user_id: int = "", input_data: str = "", context: Optional[Dict[str, Any]] = None):
        """
        记录用户输入相关bug
        
        Args:
            error: 异常对象
            user_id: 用户ID
            input_data: 输入数据
            context: 上下文信息
        """
        logger = self.loggers.get("input", {}).get("logger")
        if not logger:
            return
            
        user_info = f" | User: {user_id}" if user_id else ""
        input_info = f" | Input: {input_data[:100]}..." if len(input_data) > 100 else f" | Input: {input_data}" if input_data else ""
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"INPUT_ERROR: {str(error)}{user_info}{input_info}{context_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def log_scheduler_bug(self, error: Exception, job_name: str = "", context: Optional[Dict[str, Any]] = None):
        """
        记录定时任务相关bug
        
        Args:
            error: 异常对象
            job_name: 任务名称
            context: 上下文信息
        """
        logger = self.loggers.get("scheduler", {}).get("logger")
        if not logger:
            return
            
        job_info = f" | Job: {job_name}" if job_name else ""
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"SCHEDULER_ERROR: {str(error)}{job_info}{context_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def log_unknown_bug(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        记录未知类型bug
        
        Args:
            error: 异常对象
            context: 上下文信息
        """
        logger = logging.getLogger("bug_unknown")
        if not logger.handlers and ENABLE_FILE_LOGGING:
            # 为未知bug创建单独的日志文件
            handler = RotatingFileHandler(
                os.path.join(self.logs_dir, "bugs_unknown.log"),
                maxBytes=LOG_FILE_MAX_SIZE // 2,
                backupCount=LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"UNKNOWN_ERROR: {str(error)}{context_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")

# 创建全局Bug日志记录器实例
bug_logger = BugLogger()