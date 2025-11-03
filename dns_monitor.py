#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DNS监控和自动修复工具
定期检测DNS劫持并自动修复
"""

import socket
import time
import logging
import threading
from typing import List, Tuple, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DNSMonitor:
    def __init__(self):
        # Telegram相关域名和正确的IP地址
        self.telegram_hosts = {
            'api.telegram.org': ['149.154.167.220', '149.154.167.221', '149.154.167.222'],
            'core.telegram.org': ['149.154.167.220', '149.154.167.221', '149.154.167.222']
        }
        self.is_patched = False
        
    def detect_dns_hijacking(self, host: str) -> Tuple[bool, List[str]]:
        """
        检测指定域名是否被DNS劫持
        
        Args:
            host: 要检测的域名
            
        Returns:
            tuple: (是否被劫持, 解析到的IP列表)
        """
        try:
            # 使用原始getaddrinfo检查DNS解析结果
            original_getaddrinfo = socket.getaddrinfo
            result = original_getaddrinfo(host, 443)
            resolved_ips: List[str] = [str(addr[4][0]) for addr in result if addr[0] == socket.AF_INET]
            
            # 检查是否解析到正确的IP范围
            correct_ips = self.telegram_hosts.get(host, [])
            is_hijacked = not any(ip in correct_ips for ip in resolved_ips)
            
            logger.info(f"检测 {host}: 解析到 {resolved_ips}")
            return is_hijacked, resolved_ips
        except Exception as e:
            logger.error(f"DNS检测出错 {host}: {e}")
            return True, []  # 出错时认为被劫持
            
    def patch_dns(self):
        """应用DNS修复补丁"""
        if self.is_patched:
            return
            
        logger.info("应用DNS修复补丁...")
        
        # 保存原始的getaddrinfo函数
        original_getaddrinfo = socket.getaddrinfo
        
        def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            """修补的DNS解析函数"""
            # 如果是Telegram相关域名，直接返回正确的IP
            host_key = f"{host}:{port}" if port else host
            if isinstance(host, str):
                if host in self.telegram_hosts:
                    ips = self.telegram_hosts[host]
                    ip = ips[0]  # 使用第一个IP
                    logger.info(f"🔧 DNS Patch: Resolving {host} to {ip} (available IPs: {ips})")
                    return [(socket.AF_INET, socket.SOCK_STREAM, proto, '', (ip, port))]
                elif host_key in self.telegram_hosts:
                    ips = self.telegram_hosts[host_key]
                    ip = ips[0]  # 使用第一个IP
                    logger.info(f"🔧 DNS Patch: Resolving {host_key} to {ip} (available IPs: {ips})")
                    return [(socket.AF_INET, socket.SOCK_STREAM, proto, '', (ip, port))]
            # 调用原始函数
            return original_getaddrinfo(host, port, family, type, proto, flags)
        
        # 应用修补
        socket.getaddrinfo = patched_getaddrinfo
        self.is_patched = True
        logger.info("✅ DNS修复补丁已应用")
        
    def check_and_fix(self):
        """检查并修复DNS劫持"""
        hijacked_hosts = []
        
        for host in self.telegram_hosts.keys():
            is_hijacked, resolved_ips = self.detect_dns_hijacking(host)
            if is_hijacked:
                hijacked_hosts.append((host, resolved_ips))
                
        if hijacked_hosts:
            logger.warning(f"⚠️  检测到DNS劫持: {hijacked_hosts}")
            self.patch_dns()
            return True
        else:
            logger.info("✅ DNS解析正常")
            # 为了确保连接稳定，即使没有劫持也应用补丁
            self.patch_dns()
            return False
            
    def start_monitoring(self, interval: int = 300):
        """
        启动定期监控
        
        Args:
            interval: 检查间隔（秒）
        """
        def monitor_loop():
            while True:
                try:
                    logger.info("执行DNS劫持检查...")
                    self.check_and_fix()
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"监控过程中出错: {e}")
                    time.sleep(interval)
                    
        # 在后台线程中运行监控
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info(f"🚀 DNS监控已启动，检查间隔: {interval}秒")
        
        # 保持主线程运行
        try:
            monitor_thread.join()
        except KeyboardInterrupt:
            logger.info(" DNS监控已停止")

def main():
    """主函数"""
    logger.info("🔍 DNS监控和自动修复工具")
    logger.info("=" * 50)
    
    monitor = DNSMonitor()
    
    # 立即执行一次检查
    monitor.check_and_fix()
    
    # 启动定期监控 (每5分钟检查一次)
    monitor.start_monitoring(300)

if __name__ == "__main__":
    main()