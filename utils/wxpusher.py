# utils/wxpusher.py
"""
WxPusher 通知功能模块
用于发送微信通知
"""

import logging
import json
import time
import requests
from config import WXPUSHER_TOKEN, SERVER_NAME
# 时间工具函数
from utils.time_utils import get_beijing_now
# 推送队列
from utils.push_queue import queue_push_message

logger = logging.getLogger(__name__)

def send_wxpusher_notification(title, content, uids=None):
    """发送WxPusher通知
    
    Args:
        title: 通知标题
        content: 通知内容
        uids: 接收者UID列表，如果为None则使用全局配置
        
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    if not WXPUSHER_TOKEN:
        logger.warning("未配置WxPusher Token，跳过通知")
        return False
        
    # 确保内容不为空
    if not content or content.isspace():
        content = " "  # 使用空格代替空内容
        
    url = "http://wxpusher.zjiecode.com/api/send/message"
    
    # 构建请求数据
    data = {
        "appToken": WXPUSHER_TOKEN,
        "content": content,
        "summary": title[:96],  # 限制摘要长度
        "contentType": 3  # markdown格式
    }
    
    # 添加接收者UID
    if uids:
        data["uids"] = uids if isinstance(uids, list) else [uids]
        
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
                logger.debug(f"WxPusher 请求数据: {json.dumps(data)}")
                logger.debug(f"WxPusher 响应状态: {response.status_code}")
                logger.debug(f"WxPusher 响应内容: {response.text}")
                
                # 检查响应状态
                if response.status_code != 200:
                    logger.error(f"WxPusher 响应状态异常: {response.status_code}")
                    continue  # 重试
                    
                # 尝试解析 JSON 响应
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    logger.error("WxPusher 返回无效的 JSON 响应")
                    return False
                
                # 检查 WxPusher 返回的状态码
                if result.get("code") == 1000:
                    # 检查每个UID的发送状态
                    success_count = 0
                    data_list = result.get("data", [])
                    for item in data_list:
                        if item.get("code") == 1001:  # 每个UID的成功状态码
                            success_count += 1
                        else:
                            error_msg = item.get("status", "未知错误")
                            logger.warning(f"UID {item.get('uid', 'Unknown')} 发送失败: {error_msg}")
                    
                    if success_count == len(data_list):
                        logger.info(f"WxPusher 通知发送成功: {title}")
                        return True
                    else:
                        logger.warning(f"WxPusher 通知部分发送失败: {title}")
                        return False
                else:
                    error_msg = result.get("msg", "未知错误")
                    logger.error(f"WxPusher 通知失败: {error_msg}")
                    return False
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"WxPusher 网络请求异常 (尝试 {attempt+1}/3): {str(e)}")
                time.sleep(2)  # 等待2秒后重试
            except Exception as e:
                logger.error(f"处理 WxPusher 通知时发生异常: {str(e)}")
                break  # 非网络错误不重试
    
    except Exception as e:
        logger.error(f"处理 WxPusher 通知时发生未捕获异常: {str(e)}")
    
    return False

def wxpusher_notify(notification_type, submission_id, uids=None):
    """发送投稿通知
    
    Args:
        notification_type: 通知类型（submission或business）
        submission_id: 投稿ID
        uids: 接收者UID列表
        
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
    return send_wxpusher_notification(title, content, uids)

def wxpusher_urge_notify(submission_id, username, uids=None):
    """发送催促审核通知
    
    Args:
        submission_id: 投稿ID
        username: 用户名
        uids: 接收者UID列表
        
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    title = f"⏰ 投稿催促 #{submission_id}"
    content = f"用户 @{username} 催促审核投稿 #{submission_id}\n请尽快处理！"
    
    return send_wxpusher_notification(title, content, uids)

def test_wxpusher_notification(uids=None):
    """测试WxPusher通知功能
    
    Args:
        uids: 接收者UID列表
        
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    if not WXPUSHER_TOKEN:
        logger.warning("未配置WxPusher Token，跳过通知")
        return False
    
    title = f"🔔 WxPusher推送测试"
    content = f"这是一条测试消息，用于验证您的WxPusher配置是否正确。\n\n服务器: {SERVER_NAME}\n时间: {get_beijing_now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return send_wxpusher_notification(title, content, uids)

# 新增：通过队列发送推送通知（支持重试）
def queue_wxpusher_notification(title, content, uids=None, max_retries=3):
    """通过队列发送WxPusher通知（支持重试）
    
    Args:
        title: 通知标题
        content: 通知内容
        uids: 接收者UID列表
        max_retries: 最大重试次数
        
    Returns:
        str: 消息ID
    """
    try:
        message_id = queue_push_message(
            title=title,
            content=content,
            uids=uids,
            max_retries=max_retries
        )
        logger.info(f"WxPusher通知已加入队列: {message_id}")
        return message_id
    except Exception as e:
        logger.error(f"将WxPusher通知加入队列失败: {e}")
        # 如果队列失败，直接发送
        success = send_wxpusher_notification(title, content, uids)
        return "direct_send" if success else "failed"