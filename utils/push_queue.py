# utils/push_queue.py
"""
推送队列模块 - 实现推送失败重试和状态跟踪

本模块提供推送消息的队列管理功能：
- 消息队列存储
- 失败重试机制
- 推送状态跟踪
- 异步处理支持

作者: AI Assistant
版本: 1.0
最后更新: 2025-10-31
"""

import json
import time
import logging
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from queue import Queue, Empty

# 注意：避免循环导入，不要在这里导入 wxpusher

logger = logging.getLogger(__name__)

@dataclass
class PushMessage:
    """推送消息数据结构"""
    id: str
    title: str
    content: str
    uids: Optional[List[str]]
    max_retries: int = 3
    retry_count: int = 0
    created_at: float = 0
    last_attempt: float = 0
    status: str = "pending"  # pending, sent, failed
    error_message: str = ""

class PushQueue:
    """推送队列管理器"""
    
    def __init__(self, max_queue_size: int = 1000):
        self.queue = Queue(maxsize=max_queue_size)
        self.processing = False
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self.worker_thread = None
        # 延迟导入以避免循环导入
        self._send_wxpusher_notification = None
        
    def _get_send_function(self):
        """延迟导入发送函数以避免循环导入"""
        if self._send_wxpusher_notification is None:
            from utils.wxpusher import send_wxpusher_notification
            self._send_wxpusher_notification = send_wxpusher_notification
        return self._send_wxpusher_notification
    
    def add_message(self, message: PushMessage) -> bool:
        """添加消息到队列"""
        try:
            # 设置创建时间
            if message.created_at == 0:
                message.created_at = time.time()
                
            self.queue.put(message, block=False)
            logger.info(f"消息已添加到推送队列: {message.id}")
            return True
        except Exception as e:
            logger.error(f"添加消息到队列失败: {e}")
            return False
    
    def start_processing(self):
        """启动队列处理"""
        with self.lock:
            if self.processing:
                logger.warning("推送队列已在处理中")
                return
            
            self.processing = True
            self._stop_event.clear()
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
            logger.info("推送队列处理已启动")
    
    def stop_processing(self):
        """停止队列处理"""
        with self.lock:
            if not self.processing:
                return
                
            self.processing = False
            self._stop_event.set()
            if self.worker_thread:
                self.worker_thread.join(timeout=5)
            logger.info("推送队列处理已停止")
    
    def _process_queue(self):
        """处理队列中的消息"""
        while self.processing and not self._stop_event.is_set():
            try:
                # 等待消息，超时1秒
                message = self.queue.get(timeout=1)
                
                # 处理消息
                self._process_message(message)
                
                # 标记任务完成
                self.queue.task_done()
                
            except Exception as e:
                if not isinstance(e, Empty):
                    logger.error(f"处理队列消息时出错: {e}")
                # 继续处理下一个消息
    
    def _process_message(self, message: PushMessage):
        """处理单个消息"""
        try:
            # 更新尝试时间
            message.last_attempt = time.time()
            
            # 获取发送函数
            send_func = self._get_send_function()
            
            # 发送推送
            success = send_func(
                title=message.title,
                content=message.content,
                uids=message.uids
            )
            
            if success:
                message.status = "sent"
                logger.info(f"推送消息发送成功: {message.id}")
            else:
                message.retry_count += 1
                message.status = "failed"
                message.error_message = "推送发送失败"
                logger.warning(f"推送消息发送失败: {message.id}, 重试次数: {message.retry_count}")
                
                # 如果还有重试机会，重新加入队列
                if message.retry_count < message.max_retries:
                    # 延迟重试（指数退避）
                    time.sleep(2 ** message.retry_count)
                    self.queue.put(message)
                    logger.info(f"推送消息已重新加入队列进行重试: {message.id}")
                else:
                    logger.error(f"推送消息重试次数已达上限，放弃发送: {message.id}")
                    
        except Exception as e:
            message.retry_count += 1
            message.status = "failed"
            message.error_message = str(e)
            logger.error(f"处理推送消息时发生异常: {message.id}, 错误: {e}")
            
            # 如果还有重试机会，重新加入队列
            if message.retry_count < message.max_retries:
                # 延迟重试（指数退避）
                time.sleep(2 ** message.retry_count)
                self.queue.put(message)
                logger.info(f"推送消息因异常已重新加入队列进行重试: {message.id}")

# 全局推送队列实例
push_queue = PushQueue()

def start_push_queue():
    """启动推送队列"""
    push_queue.start_processing()

def stop_push_queue():
    """停止推送队列"""
    push_queue.stop_processing()

def queue_push_message(title: str, content: str, uids: Optional[List[str]] = None, 
                      max_retries: int = 3) -> str:
    """将推送消息添加到队列"""
    import uuid
    
    # 创建消息
    message = PushMessage(
        id=str(uuid.uuid4()),
        title=title,
        content=content,
        uids=uids,
        max_retries=max_retries
    )
    
    # 添加到队列
    if push_queue.add_message(message):
        return message.id
    else:
        raise Exception("无法将消息添加到推送队列")

# 在模块导入时启动队列处理
start_push_queue()