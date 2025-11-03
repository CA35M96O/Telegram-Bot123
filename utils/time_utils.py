# utils/time_utils.py
"""
时间工具模块 - 统一处理系统中的时间相关操作

本模块提供统一的时间处理功能，确保系统中所有时间操作都使用北京时间。
主要功能包括：
- 获取当前北京时间
- 时间格式化和解析
- 时区转换
- 时间比较和计算

作者: AI Assistant
版本: 1.0
创建时间: 2025-08-31
"""

import datetime
import pytz
from typing import Union, Optional

# 定义北京时间时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

def get_beijing_now() -> datetime.datetime:
    """获取当前的北京时间
    
    Returns:
        datetime.datetime: 带时区的当前北京时间
    """
    return datetime.datetime.now(BEIJING_TZ)

def get_beijing_now_naive() -> datetime.datetime:
    """获取不带时区信息的当前北京时间（用于兼容旧代码）
    
    Returns:
        datetime.datetime: 不带时区的当前北京时间
    """
    return datetime.datetime.now(BEIJING_TZ).replace(tzinfo=None)

def to_beijing_time(dt: Union[datetime.datetime, str]) -> datetime.datetime:
    """将时间转换为北京时间
    
    Args:
        dt: 可以是datetime对象或时间字符串
        
    Returns:
        datetime.datetime: 北京时间
    """
    if isinstance(dt, str):
        # 尝试解析时间字符串
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S,%f'):
            try:
                dt = datetime.datetime.strptime(dt, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"无法解析时间字符串: {dt}")
    
    # 如果是naive datetime，假设是UTC时间
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    
    # 转换为北京时间
    return dt.astimezone(BEIJING_TZ)

def format_beijing_time(dt: Optional[datetime.datetime] = None, 
                       fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """格式化北京时间为字符串
    
    Args:
        dt: 时间对象，如果为None则使用当前时间
        fmt: 格式字符串
        
    Returns:
        str: 格式化后的时间字符串
    """
    if dt is None:
        dt = get_beijing_now()
    elif dt.tzinfo is None:
        # 如果是naive datetime，假设是UTC时间
        dt = pytz.utc.localize(dt)
    
    # 确保是北京时间
    beijing_dt = dt.astimezone(BEIJING_TZ)
    return beijing_dt.strftime(fmt)

def beijing_time_from_timestamp(timestamp: float) -> datetime.datetime:
    """从时间戳创建北京时间
    
    Args:
        timestamp: Unix时间戳
        
    Returns:
        datetime.datetime: 北京时间
    """
    # 从时间戳创建UTC时间
    utc_dt = datetime.datetime.fromtimestamp(timestamp, pytz.utc)
    # 转换为北京时间
    return utc_dt.astimezone(BEIJING_TZ)

def beijing_time_from_timestamp_naive(timestamp: float) -> datetime.datetime:
    """从时间戳创建不带时区的北京时间（用于兼容旧代码）
    
    Args:
        timestamp: Unix时间戳
        
    Returns:
        datetime.datetime: 不带时区的北京时间
    """
    beijing_dt = beijing_time_from_timestamp(timestamp)
    return beijing_dt.replace(tzinfo=None)

def is_beijing_business_hours() -> bool:
    """检查当前是否是北京时间的工作时间（9:00-22:00）
    
    Returns:
        bool: 是否是工作时间
    """
    now = get_beijing_now()
    hour = now.hour
    return 9 <= hour < 22

def get_beijing_time_range_today() -> tuple:
    """获取今天的北京时间范围
    
    Returns:
        tuple: (开始时间, 结束时间)
    """
    now = get_beijing_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=1)
    return start, end

def get_beijing_time_range_yesterday() -> tuple:
    """获取昨天的北京时间范围
    
    Returns:
        tuple: (开始时间, 结束时间)
    """
    now = get_beijing_now()
    yesterday = now - datetime.timedelta(days=1)
    start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=1)
    return start, end

def get_beijing_time_range_days_ago(days: int) -> tuple:
    """获取指定天数前的北京时间范围
    
    Args:
        days: 天数
        
    Returns:
        tuple: (开始时间, 结束时间)
    """
    now = get_beijing_now()
    target_day = now - datetime.timedelta(days=days)
    start = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=1)
    return start, end

def beijing_time_diff(dt1: datetime.datetime, dt2: datetime.datetime) -> datetime.timedelta:
    """计算两个北京时间之间的差值
    
    Args:
        dt1: 第一个时间
        dt2: 第二个时间
        
    Returns:
        datetime.timedelta: 时间差
    """
    # 确保两个时间都是北京时间
    if dt1.tzinfo is None:
        dt1 = to_beijing_time(dt1)
    if dt2.tzinfo is None:
        dt2 = to_beijing_time(dt2)
    
    return dt1 - dt2

def beijing_time_add(dt: datetime.datetime, **kwargs) -> datetime.datetime:
    """对北京时间进行加减运算
    
    Args:
        dt: 原始时间
        **kwargs: 时间增量参数（days, hours, minutes, seconds等）
        
    Returns:
        datetime.datetime: 计算后的时间
    """
    # 确保是北京时间
    if dt.tzinfo is None:
        dt = to_beijing_time(dt)
    
    return dt + datetime.timedelta(**kwargs)

def get_beijing_time_string_for_display(dt: Optional[datetime.datetime] = None) -> str:
    """获取用于显示的北京时间字符串
    
    Args:
        dt: 时间对象，如果为None则使用当前时间
        
    Returns:
        str: 格式化的时间字符串，包含"北京时间"标识
    """
    if dt is None:
        dt = get_beijing_now()
    
    time_str = format_beijing_time(dt, '%Y-%m-%d %H:%M:%S')
    return f"{time_str} (北京时间)"

def parse_beijing_time(time_str: str, fmt: str = '%Y-%m-%d %H:%M:%S') -> datetime.datetime:
    """解析北京时间字符串
    
    Args:
        time_str: 时间字符串
        fmt: 格式字符串
        
    Returns:
        datetime.datetime: 北京时间对象
    """
    # 解析为naive datetime
    naive_dt = datetime.datetime.strptime(time_str, fmt)
    # 设置为北京时间
    return BEIJING_TZ.localize(naive_dt)