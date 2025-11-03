"""
服务器状态监控模块
用于获取和报告服务器状态信息
"""

import logging
import datetime
import psutil
import platform
import pytz
from config import SERVER_NAME, SHOW_DETAILED_STATS
# 时间工具函数
from utils.time_utils import get_beijing_now

logger = logging.getLogger(__name__)

# 设置北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

# 全局变量 - 机器人启动时间
BOT_START_TIME = get_beijing_now()
# 机器人启动后处理的总投稿数
TOTAL_SUBMISSIONS_AFTER_START = 0

def check_telegram_api_dns():
    """检查Telegram API DNS污染状态（避免循环导入）"""
    try:
        # 动态导入以避免循环依赖
        from jobs.dns_monitor import check_telegram_api_dns_with_timeout
        # 调用带超时控制的DNS检查函数
        return check_telegram_api_dns_with_timeout()
    except ImportError as e:
        logger.error(f"DNS检查模块导入失败: {e}")
        return False, ["DNS检查模块不可用"]
    except Exception as e:
        logger.error(f"DNS检查失败: {e}")
        return False, [f"DNS检查异常: {str(e)}"]

def get_server_status():
    """获取服务器状态信息
    
    Returns:
        str: 服务器状态信息文本
    """
    # 获取内存信息
    mem = psutil.virtual_memory()
    mem_total = round(mem.total / (1024 ** 3), 2)
    mem_used = round(mem.used / (1024 ** 3), 2)
    mem_percent = mem.percent
    
    # 获取CPU信息
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=False)  # 物理核心
    cpu_threads = psutil.cpu_count(logical=True)  # 逻辑核心
    
    # 获取磁盘信息 - 只显示根目录
    disk_info = []
    try:
        usage = psutil.disk_usage('/')
        disk_info.append({
            "device": '/',
            "mount": '/',
            "total": round(usage.total / (1024 ** 3), 2),
            "used": round(usage.used / (1024 ** 3), 2),
            "free": round(usage.free / (1024 ** 3), 2),
            "percent": usage.percent
        })
    except Exception as e:
        logger.error(f"获取根目录磁盘信息失败: {e}")
    
    # 获取网络信息
    net_io = psutil.net_io_counters()
    net_sent = round(net_io.bytes_sent / (1024 ** 2), 2)  # MB
    net_recv = round(net_io.bytes_recv / (1024 ** 2), 2)  # MB
    
    # 获取进程信息
    process = psutil.Process()
    bot_mem = round(process.memory_info().rss / (1024 ** 2), 2)  # MB
    
    # 获取系统信息
    os_name = platform.system()
    os_version = platform.release()
    python_version = platform.python_version()
    
    # 计算运行时间
    uptime = get_beijing_now() - BOT_START_TIME
    days, seconds = uptime.days, uptime.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    uptime_str = f"{days}天 {hours}小时 {minutes}分 {seconds}秒"
    
    # 构建状态文本
    status_text = (
        f"🖥 *{SERVER_NAME} 服务器状态*\n\n"
        f"⏱ *运行时间:* `{uptime_str}`\n"
        f"🐍 *Python 版本:* `{python_version}`\n"
        f"💻 *操作系统:* `{os_name} {os_version}`\n"
        f"🧠 *CPU 使用率:* `{cpu_percent}%` (物理核心: {cpu_count}, 逻辑核心: {cpu_threads})\n"
        f"💾 *内存使用:* `{mem_percent}%` (已用: {mem_used}GB / 总计: {mem_total}GB)\n"
    )
    
    # 添加磁盘信息 - 只显示根目录
    if disk_info:
        disk = disk_info[0]
        status_text += (
            f"\n💽 *磁盘存储空间:*\n"
            f"• `{disk['mount']}` ({disk['device']}):\n"
            f"  使用率: `{disk['percent']}%`\n"
            f"  已用: `{disk['used']}GB` / 总计: `{disk['total']}GB`\n"
            f"  可用: `{disk['free']}GB`\n"
        )
    else:
        status_text += "\n💽 *磁盘存储空间:* 无法获取磁盘信息\n"
    
    # 添加其他信息
    status_text += (
        f"\n📡 *网络流量:*\n"
        f"  发送: `{net_sent}MB`\n"
        f"  接收: `{net_recv}MB`\n"
        f"🤖 *机器人内存占用:* `{bot_mem}MB`\n"
    )
    
    # 添加DNS状态信息
    try:
        dns_polluted, dns_details = check_telegram_api_dns()
        status_text += f"\n🌐 *api.telegram.org DNS状态:* {'❌ 检测到污染' if dns_polluted else '✅ 正常'}\n"
        
        if dns_polluted and dns_details:
            status_text += "详情:\n"
            for detail in dns_details[:2]:  # 只显示前2个详情
                status_text += f"• `{detail}`\n"
    except Exception as e:
        logger.error(f"DNS污染检测失败: {e}")
        status_text += "\n⚠️ DNS状态检测失败"
    
    # 添加详细统计（可选）
    if SHOW_DETAILED_STATS:
        # 获取数据库统计
        from database import db, Submission, UserState
        session = db.get_session()
        try:
            total = session.query(Submission).count()
            pending = session.query(Submission).filter_by(status='pending').count()
            active_states = session.query(UserState).count()
            
            # 获取进程列表
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
                try:
                    # 只显示占用内存超过1%的进程
                    if proc.info['memory_percent'] > 1.0:
                        processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # 按内存占用排序
            processes = sorted(processes, key=lambda p: p.info['memory_percent'], reverse=True)[:5]
            
            # 添加详细统计信息
            status_text += (
                "\n📊 *详细统计:*\n"
                f"• 数据库记录: `{total}` (待审: `{pending}`)\n"
                f"• 活跃用户状态: `{active_states}`\n"
                "\n🔥 *内存占用前5的进程:*\n"
            )
            
            for proc in processes:
                mem_pct = round(proc.info['memory_percent'], 1)
                status_text += f"• `{proc.info['name']}`: `{mem_pct}%`\n"
                
        except Exception as e:
            logger.error(f"获取详细统计失败: {e}")
            status_text += "\n⚠️ 获取详细统计时出错"
        finally:
            session.close()
    
    return status_text

def get_server_status_with_stats():
    """获取服务器状态信息（包含投稿统计）
    
    Returns:
        str: 包含投稿统计的服务器状态信息文本
    """
    global TOTAL_SUBMISSIONS_AFTER_START
    
    # 基础状态信息
    status_text = get_server_status()
    
    # 添加投稿统计
    from database import db, Submission
    session = db.get_session()
    try:
        # 计算运行时间
        uptime = get_beijing_now() - BOT_START_TIME
        hours, remainder = divmod(uptime.total_seconds(), 3600)
        minutes, _ = divmod(remainder, 60)
        
        # 获取投稿统计
        total = session.query(Submission).count()
        pending = session.query(Submission).filter_by(status='pending').count()
        approved = session.query(Submission).filter_by(status='approved').count()
        rejected = session.query(Submission).filter_by(status='rejected').count()
        
        # 计算启动后的投稿量
        new_submissions = total - TOTAL_SUBMISSIONS_AFTER_START
        if TOTAL_SUBMISSIONS_AFTER_START == 0:  # 首次运行
            TOTAL_SUBMISSIONS_AFTER_START = total
            new_submissions = 0
        
        # 添加统计信息
        stats_text = (
            "\n\n📊 *投稿统计:*\n"
            f"• 总投稿数: `{total}`\n"
            f"• 待审稿件: `{pending}`\n"
            f"• 已发布: `{approved}`\n"
            f"• 已拒绝: `{rejected}`\n"
            f"• 启动后新增: `{new_submissions}`\n"
            f"• 运行时间: `{int(hours)}小时{int(minutes)}分钟`"
        )
        
        return status_text + stats_text
        
    except Exception as e:
        logger.error(f"获取投稿统计失败: {e}")
        return status_text + "\n\n⚠️ 获取投稿统计时出错"
    finally:
        session.close()