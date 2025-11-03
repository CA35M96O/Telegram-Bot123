# utils/pushplus.py
"""
PushPlus 通知功能模块
用于发送微信通知
"""

import logging
import json
import time
import requests
import datetime
from config import PUSHPLUS_TOKEN, PUSHPLUS_TOPIC, SERVER_NAME
# 时间工具函数
from utils.time_utils import get_beijing_now

logger = logging.getLogger(__name__)

def send_pushplus_notification(title, content):
    """发送PushPlus通知
    
    Args:
        title: 通知标题
        content: 通知内容
        
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    if not PUSHPLUS_TOKEN:
        logger.warning("未配置PushPlus Token，跳过通知")
        return False
        
    # 确保内容不为空
    if not content or content.isspace():
        content = " "  # 使用空格代替空内容
        
    # 限制标题长度（PushPlus限制约100字符）
    title = title[:100]
    
    url = "http://www.pushplus.plus/send"
    
    # 构建请求数据
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "txt"
    }
    
    # 添加群组主题（群组编码）
    if PUSHPLUS_TOPIC:
        data["topic"] = PUSHPLUS_TOPIC
        
    try:
        # 添加明确的请求头
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; TelegramBot/1.0)"
        }
        
        # 发送请求（带重试机制）
        for attempt in range(3):
            try:
                response = requests.post(
                    url, 
                    json=data, 
                    headers=headers,
                    timeout=10
                )
                
                # 记录请求和响应信息用于调试
                logger.debug(f"PushPlus 请求数据: {json.dumps(data)}")
                logger.debug(f"PushPlus 响应状态: {response.status_code}")
                logger.debug(f"PushPlus 响应内容: {response.text}")
                
                # 检查响应状态
                if response.status_code != 200:
                    logger.error(f"PushPlus 响应状态异常: {response.status_code}")
                    continue  # 重试
                    
                # 尝试解析 JSON 响应
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    logger.error("PushPlus 返回无效的 JSON 响应")
                    return False
                
                # 检查 PushPlus 返回的状态码
                if result.get("code") == 200:
                    logger.info(f"PushPlus 通知发送成功: {title}")
                    return True
                else:
                    error_msg = result.get("msg", "未知错误")
                    logger.error(f"PushPlus 通知失败: {error_msg}")
                    return False
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"PushPlus 网络请求异常 (尝试 {attempt+1}/3): {str(e)}")
                time.sleep(2)  # 等待2秒后重试
            except Exception as e:
                logger.error(f"处理 PushPlus 通知时发生异常: {str(e)}")
                break  # 非网络错误不重试
    
    except Exception as e:
        logger.error(f"处理 PushPlus 通知时发生未捕获异常: {str(e)}")
    
    return False

def pushplus_notify(notification_type, submission_id):
    """发送投稿通知
    
    Args:
        notification_type: 通知类型（submission或business）
        submission_id: 投稿ID
        
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    # 创建标题（包含类型和ID）
    if notification_type == "submission":
        title = f"📬 投稿 #{submission_id}"
        content = f"新投稿等待审核\nID: #{submission_id}"
    else:  # business
        title = f"🤝 合作 #{submission_id}"
        content = f"新商务合作请求\nID: #{submission_id}"
    
    # 发送通知（使用更完整的内容）
    return send_pushplus_notification(title, content)

def pushplus_urge_notify(submission_id, username):
    """发送催促审核通知
    
    Args:
        submission_id: 投稿ID
        username: 用户名
        
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    title = f"⏰ 投稿催促 #{submission_id}"
    content = f"用户 @{username} 催促审核投稿 #{submission_id}\n请尽快处理！"
    
    return send_pushplus_notification(title, content)

def send_startup_notification():
    """发送机器人启动通知
    
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    start_time = get_beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    return send_pushplus_notification(
        "🤖 机器人启动通知",
        f"投稿机器人已成功启动\n启动时间: {start_time}\n服务器: {SERVER_NAME}"
    )