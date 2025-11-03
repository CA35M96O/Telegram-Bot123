# jobs/dns_monitor.py
"""
DNS监控和自动修复任务模块 - Telegram API 可用性保障

本模块负责监控 Telegram API 的 DNS 解析状态，特别关注 api.telegram.org。
当检测到 DNS 污染时，系统会自动尝试修复并通知管理员。

主要功能：
1. DNS 污染检测 - 比较本地和公共 DNS 解析结果
2. 污染源分析 - 识别可疑的 IP 地址和解析器
3. 自动修复机制 - 刷新 DNS 缓存和更新 hosts 文件
4. 实时通知 - 通过 PushPlus 和 Telegram 发送警报
5. 状态追踪 - 避免重复通知，仅在状态改变时警报

检测策略：
- 每 10 分钟检查一次 DNS 解析状态
- 使用多重 DNS 查询验证（本地、Google DNS、DoH）
- 对比 Telegram 官方 IP 段识别异常
- 支持跨平台操作（Windows/macOS/Linux）

修复机制：
1. DNS 缓存刷新 - 清除被污染的缓存记录
2. Hosts 文件更新 - 直接指定正确的 IP 地址
3. 系统服务重启 - 重启 DNS 相关服务
4. 效果验证 - 修复后重新检查效果

作者: AI Assistant
版本: 2.0
最后更新: 2025-08-31
"""

# =====================================================
# 所需库导入 Required Library Imports
# =====================================================

# Python 标准库
import logging
import time
import socket
import subprocess
import requests
import re
import concurrent.futures

# Telegram Bot API 组件
from telegram.ext import CallbackContext

# 项目组件
from utils.pushplus import send_pushplus_notification  # PushPlus 通知服务
from config import ADMIN_IDS                          # 管理员ID配置

# =====================================================
# 日志配置和全局变量 Global Logging and Variables
# =====================================================

# 初始化日志器 - 用于记录 DNS 监控和修复活动
logger = logging.getLogger(__name__)

# 存储上次DNS状态，用于避免重复通知
# 这样可以确保只在状态变化时才发送警报，避免通知洪水
last_dns_status = None

def check_telegram_api_dns():
    """专门检查api.telegram.org的DNS污染情况
    
    Returns:
        tuple: (是否被污染, 污染详情) 
    """
    target_domain = "api.telegram.org"
    pollution_details = []
    
    try:
        # 设置socket超时
        socket.setdefaulttimeout(3)
        
        # 使用本地DNS解析
        local_ips = socket.gethostbyname_ex(target_domain)[2]
        
        # 检查解析结果是否包含异常IP（非Telegram官方IP）
        telegram_ips = [
            "149.154.160.0", "149.154.161.0", "149.154.162.0", "149.154.163.0",
            "149.154.164.0", "149.154.165.0", "149.154.166.0", "149.154.167.0",
            "91.108.4.0", "91.108.56.0"
        ]
        
        # 检查是否有非Telegram IP
        suspicious_ips = []
        for ip in local_ips:
            is_telegram_ip = False
            for telegram_ip in telegram_ips:
                if ip.startswith(telegram_ip.rsplit('.', 1)[0] + '.'):
                    is_telegram_ip = True
                    break
            
            if not is_telegram_ip:
                suspicious_ips.append(ip)
        
        if suspicious_ips:
            pollution_details.append(f"{target_domain}: 解析到可疑IP {suspicious_ips}")
            return True, pollution_details
        
        # 使用公共DNS解析（Google DNS）进行验证
        try:
            # 使用Google DNS解析
            resolver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            resolver.sendto(b'\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00' + 
                           bytes(target_domain, 'utf-8') + b'\x00\x00\x01\x00\x01', 
                           ('8.8.8.8', 53))
            resolver.settimeout(3)
            response, _ = resolver.recvfrom(1024)
            
            # 解析响应
            if response:
                # 简单解析DNS响应，获取IP地址
                public_ips = []
                # 查找响应中的IP地址（简化版）
                for i in range(len(response) - 4):
                    if response[i:i+2] == b'\xc0\x0c' and response[i+2:i+4] == b'\x00\x01':
                        # 找到IP地址
                        ip = response[i+6:i+10]
                        if len(ip) == 4:
                            public_ips.append('.'.join(str(b) for b in ip))
                
                # 比较本地和公共DNS解析结果
                if public_ips and set(local_ips) != set(public_ips):
                    pollution_details.append(f"{target_domain}: 本地={local_ips}, 公共DNS={public_ips}")
                    return True, pollution_details
        except:
            # 如果公共DNS查询失败，尝试使用HTTP方式
            try:
                # 使用DNS over HTTPS (Google)
                doh_url = f"https://dns.google/resolve?name={target_domain}&type=A"
                response = requests.get(doh_url, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if 'Answer' in data:
                        public_ips = [answer['data'] for answer in data['Answer'] if answer['type'] == 1]
                        if public_ips and set(local_ips) != set(public_ips):
                            pollution_details.append(f"{target_domain}: 本地={local_ips}, DoH={public_ips}")
                            return True, pollution_details
            except:
                # 如果所有方法都失败，记录警告
                pollution_details.append(f"{target_domain}: 无法验证DNS")
    
    except Exception as e:
        pollution_details.append(f"{target_domain}: 检查失败 - {str(e)}")
        return True, pollution_details  # 如果检查失败，假设有问题
    
    return False, pollution_details

def check_telegram_api_dns_with_timeout():
    """带超时控制的DNS检查函数"""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(check_telegram_api_dns)
            # 设置5秒超时
            return future.result(timeout=5)
    except concurrent.futures.TimeoutError:
        logger.warning("DNS检查超时")
        return False, ["DNS检查超时"]
    except Exception as e:
        logger.error(f"DNS检查异常: {e}")
        return False, [f"DNS检查异常: {str(e)}"]

def fix_dns_pollution():
    """尝试修复DNS污染
    
    Returns:
        tuple: (是否成功修复, 修复详情)
    """
    import platform
    fix_details = []
    success = False
    
    try:
        # 方法1: 刷新DNS缓存
        try:
            if platform.system() == "Windows":
                result = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10, text=True)
                fix_details.append("已刷新Windows DNS缓存")
                if result.returncode == 0:
                    success = True
            elif platform.system() == "Darwin":  # macOS
                result1 = subprocess.run(["sudo", "dscacheutil", "-flushcache"], capture_output=True, timeout=10, text=True)
                result2 = subprocess.run(["sudo", "killall", "-HUP", "mDNSResponder"], capture_output=True, timeout=10, text=True)
                fix_details.append("已刷新macOS DNS缓存")
                if result1.returncode == 0 and result2.returncode == 0:
                    success = True
            else:  # Linux
                result1 = subprocess.run(["sudo", "systemctl", "restart", "systemd-resolved"], capture_output=True, timeout=10, text=True)
                result2 = subprocess.run(["sudo", "systemctl", "restart", "nscd"], capture_output=True, timeout=10, text=True)
                fix_details.append("已刷新Linux DNS缓存")
                if result1.returncode == 0 and result2.returncode == 0:
                    success = True
        except Exception as e:
            fix_details.append(f"刷新DNS缓存失败: {str(e)}")
        
        # 方法2: 修改hosts文件，直接指定api.telegram.org的正确IP
        try:
            # Telegram API的官方IP地址
            telegram_ips = [
                "149.154.167.220",  # 主要API地址
                "149.154.167.221",
                "149.154.167.222"
            ]
            
            hosts_path = "/etc/hosts" if platform.system() != "Windows" else r"C:\Windows\System32\drivers\etc\hosts"
            
            # 读取当前hosts文件
            with open(hosts_path, "r") as f:
                hosts_content = f.read()
            
            # 移除旧的api.telegram.org条目
            new_hosts_content = re.sub(r'^.*api\.telegram\.org.*$', '', hosts_content, flags=re.MULTILINE)
            
            # 添加新的正确条目
            for ip in telegram_ips:
                new_hosts_content += f"\n{ip} api.telegram.org"
            
            # 写入新的hosts文件
            with open(hosts_path, "w") as f:
                f.write(new_hosts_content.strip())
            
            fix_details.append("已更新hosts文件，指定api.telegram.org的正确IP")
            success = True
        except Exception as e:
            fix_details.append(f"更新hosts文件失败: {str(e)}")
        
        # 等待DNS设置生效
        time.sleep(2)
        
    except Exception as e:
        fix_details.append(f"修复DNS污染时发生错误: {str(e)}")
    
    return success, fix_details

async def check_and_fix_dns(context: CallbackContext):
    """检查并修复DNS污染，特别关注api.telegram.org
    
    Args:
        context: Telegram context 对象
    """
    global last_dns_status
    
    logger.info("开始api.telegram.org DNS污染检查...")
    
    # 检查DNS污染，使用带超时的版本
    is_polluted, details = check_telegram_api_dns_with_timeout()
    
    # 只在状态变化时发送通知
    if is_polluted != last_dns_status:
        last_dns_status = is_polluted
        
        if is_polluted:
            logger.warning(f"检测到api.telegram.org DNS污染: {details}")
            
            # 发送微信通知
            notification_text = f"⚠️ 检测到api.telegram.org DNS污染\n详情:\n"
            for detail in details:
                notification_text += f"• {detail}\n"
            
            # 发送PushPlus通知
            send_pushplus_notification("🌐 api.telegram.org DNS污染警报", notification_text)
            
            # 尝试自动修复
            success, fix_details = fix_dns_pollution()
            
            if success:
                logger.info("api.telegram.org DNS污染修复成功")
                fix_text = "✅ api.telegram.org DNS污染已自动修复\n修复操作:\n"
                for detail in fix_details:
                    fix_text += f"• {detail}\n"
                
                # 发送PushPlus修复通知
                send_pushplus_notification("✅ api.telegram.org DNS污染已修复", fix_text)
                
                # 验证修复是否成功
                time.sleep(3)
                is_still_polluted, _ = check_telegram_api_dns_with_timeout()
                if not is_still_polluted:
                    fix_text += "\n✅ 验证: 修复成功，api.telegram.org DNS解析已恢复正常"
                else:
                    fix_text += "\n❌ 验证: 修复后仍然检测到DNS污染"
                
                # 更新修复通知
                send_pushplus_notification("✅ api.telegram.org DNS污染修复结果", fix_text)
            else:
                logger.error("api.telegram.org DNS污染修复失败")
                fix_text = "❌ api.telegram.org DNS污染自动修复失败\n尝试的操作:\n"
                for detail in fix_details:
                    fix_text += f"• {detail}\n"
                
                # 发送PushPlus修复失败通知
                send_pushplus_notification("❌ api.telegram.org DNS污染修复失败", fix_text)
        else:
            logger.info("api.telegram.org DNS检查正常，未发现污染")
    else:
        # 状态未变化，只记录日志
        if is_polluted:
            logger.info("api.telegram.org DNS污染状态未变化（持续污染中）")
        else:
            logger.info("api.telegram.org DNS状态正常（持续正常）")

async def setup_dns_monitor_job(context: CallbackContext):
    """设置DNS监控任务
    
    Args:
        context: Telegram context 对象
    """
    # 确保 job_queue 存在
    if context.job_queue is None:
        logger.error("Job queue is not available")
        return
        
    # 每10分钟检查一次DNS
    context.job_queue.run_repeating(
        check_and_fix_dns,
        interval=600,  # 600秒 = 10分钟
        first=10  # 10秒后开始第一次检查
    )
    logger.info("api.telegram.org DNS监控任务已设置（每10分钟检查一次）")