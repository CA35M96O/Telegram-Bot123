#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境变量配置管理工具
Environment Variable Configuration Management Tool

此脚本帮助管理Telegram Bot的环境变量配置
This script helps manage environment variable configuration for the Telegram Bot

功能 Features:
1. 生成 .env 文件 - Generate .env file
2. 验证配置 - Validate configuration
3. 显示当前配置 - Show current configuration
4. 交互式配置设置 - Interactive configuration setup
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

def load_template() -> Dict[str, Any]:
    """加载配置模板"""
    template = {
        # 必需配置
        'required': {
            'BOT_TOKEN': {
                'description': 'Telegram Bot Token (从 @BotFather 获取)',
                'example': '1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                'required': True
            },
            'ADMIN_IDS': {
                'description': '管理员ID列表 (逗号分隔)',
                'example': '123456789,987654321',
                'required': True
            }
        },
        # 可选配置
        'optional': {
            'CHANNEL_ID': {
                'description': '频道ID',
                'example': '@your_channel',
                'default': '@mgbaoguang110'
            },
            'GROUP_IDS': {
                'description': '群组ID列表 (逗号分隔)',
                'example': '-1001234567890,-1009876543210',
                'default': '-1002473450119'
            },
            'VERIFY_GROUP_IDS': {
                'description': '验证群组ID列表 (逗号分隔)',
                'example': '-1001234567890,-1009876543210',
                'default': '-1002473450119'
            },
            'VERIFY_CHANNEL_IDS': {
                'description': '验证频道ID列表 (逗号分隔)',
                'example': '@your_channel1,@your_channel2',
                'default': '@mgbaoguang110'
            },
            'ENFORCE_GROUP_MEMBERSHIP': {
                'description': '强制群组成员检查 (true/false)',
                'example': 'true',
                'default': 'true'
            },
            'ENFORCE_CHANNEL_MEMBERSHIP': {
                'description': '强制频道成员检查 (true/false)',
                'example': 'false',
                'default': 'false'
            },
            'DB_URL': {
                'description': '数据库连接URL',
                'example': 'sqlite:///submissions.db',
                'default': 'sqlite:///submissions.db'
            },
            'PUSHPLUS_TOKEN': {
                'description': 'PushPlus通知Token',
                'example': 'your_pushplus_token',
                'default': 'aec24c9ce0454fdca2a25f410d2ec283'
            },
            'SERVER_NAME': {
                'description': '服务器名称',
                'example': '生产服务器',
                'default': '默认服务器'
            },
            'LOG_LEVEL': {
                'description': '日志级别 (DEBUG/INFO/WARNING/ERROR)',
                'example': 'INFO',
                'default': 'INFO'
            }
        }
    }
    return template

def show_current_config():
    """显示当前配置"""
    print("📊 当前环境变量配置:")
    print("=" * 50)
    
    template = load_template()
    
    # 检查必需配置
    print("🔴 必需配置:")
    for key, info in template['required'].items():
        value = os.getenv(key)
        status = "✅ 已设置" if value else "❌ 未设置"
        masked_value = "*" * 20 if value and "TOKEN" in key else value
        print(f"  {key}: {status} - {masked_value or '未设置'}")
    
    print("\n🟡 可选配置:")
    for key, info in template['optional'].items():
        value = os.getenv(key, info.get('default', ''))
        masked_value = "*" * 20 if value and "TOKEN" in key else value
        print(f"  {key}: {masked_value}")
    
    print("=" * 50)

def validate_config() -> bool:
    """验证配置"""
    print("🔍 验证配置...")
    
    template = load_template()
    errors = []
    warnings = []
    
    # 检查必需配置
    for key, info in template['required'].items():
        if not os.getenv(key):
            errors.append(f"❌ {key} 未设置 - {info['description']}")
    
    # 检查可选但重要的配置
    important_optionals = ['CHANNEL_ID', 'GROUP_IDS']
    for key in important_optionals:
        if not os.getenv(key):
            warnings.append(f"⚠️ {key} 未设置，将使用默认值")
    
    # 输出结果
    if errors:
        print("\n❌ 配置错误:")
        for error in errors:
            print(f"  {error}")
    
    if warnings:
        print("\n⚠️ 配置警告:")
        for warning in warnings:
            print(f"  {warning}")
    
    if not errors and not warnings:
        print("✅ 配置验证通过!")
        return True
    elif not errors:
        print("✅ 必需配置完整，有一些可选警告")
        return True
    else:
        print("❌ 配置验证失败")
        return False

def interactive_setup():
    """交互式配置设置"""
    print("🛠️ 交互式配置设置")
    print("=" * 50)
    
    template = load_template()
    config = {}
    
    print("请填写以下配置项 (按 Enter 使用默认值):\n")
    
    # 必需配置
    print("🔴 必需配置:")
    for key, info in template['required'].items():
        while True:
            current = os.getenv(key, '')
            prompt = f"{key} - {info['description']}"
            if current:
                prompt += f" (当前: {current[:10] + '...' if len(current) > 10 else current})"
            prompt += ": "
            
            value = input(prompt).strip()
            if value:
                config[key] = value
                break
            elif current:
                config[key] = current
                break
            else:
                print(f"  ❌ {key} 是必需的，请输入值")
    
    # 可选配置
    print("\n🟡 可选配置 (按 Enter 跳过):")
    for key, info in template['optional'].items():
        current = os.getenv(key, info.get('default', ''))
        prompt = f"{key} - {info['description']}"
        if current:
            prompt += f" (默认: {current})"
        prompt += ": "
        
        value = input(prompt).strip()
        if value:
            config[key] = value
        elif current:
            config[key] = current
    
    return config

def generate_env_file(config: Dict[str, str], filename: str = '.env'):
    """生成 .env 文件"""
    env_path = Path(filename)
    
    # 备份现有文件
    if env_path.exists():
        backup_path = f"{filename}.backup"
        import shutil
        shutil.copy(env_path, backup_path)
        print(f"📋 已备份现有配置到: {backup_path}")
    
    # 写入新配置
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write("# Telegram Bot Environment Configuration\n")
        f.write("# Generated by config_env.py\n")
        f.write(f"# Generated at: {__import__('datetime').datetime.now()}\n\n")
        
        # 按类别写入
        f.write("# ===== Required Configuration =====\n")
        template = load_template()
        
        for key in template['required'].keys():
            if key in config:
                f.write(f"{key}={config[key]}\n")
        
        f.write("\n# ===== Optional Configuration =====\n")
        for key in template['optional'].keys():
            if key in config:
                f.write(f"{key}={config[key]}\n")
    
    print(f"✅ 配置已保存到: {env_path.absolute()}")

def load_env_file(filename: str = '.env'):
    """加载 .env 文件"""
    env_path = Path(filename)
    if not env_path.exists():
        return False
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
    
    return True

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Telegram Bot 环境变量配置管理')
    parser.add_argument('--show', action='store_true', help='显示当前配置')
    parser.add_argument('--validate', action='store_true', help='验证配置')
    parser.add_argument('--setup', action='store_true', help='交互式配置设置')
    parser.add_argument('--generate-template', action='store_true', help='生成配置模板')
    parser.add_argument('--load-env', type=str, default='.env', help='加载环境变量文件')
    
    args = parser.parse_args()
    
    # 尝试加载现有的 .env 文件
    if Path(args.load_env).exists():
        load_env_file(args.load_env)
        print(f"📁 已加载环境变量文件: {args.load_env}")
    
    if args.show:
        show_current_config()
    elif args.validate:
        validate_config()
    elif args.setup:
        config = interactive_setup()
        print(f"\n📝 即将生成配置文件...")
        generate_env_file(config)
        print("\n🔍 验证生成的配置...")
        load_env_file()
        validate_config()
    elif args.generate_template:
        # 创建模板文件
        template_config = {}
        template = load_template()
        
        for key, info in {**template['required'], **template['optional']}.items():
            if 'default' in info:
                template_config[key] = info['default']
            else:
                template_config[key] = info.get('example', f'your_{key.lower()}_here')
        
        generate_env_file(template_config, '.env.example')
        print("✅ 已生成配置模板: .env.example")
    else:
        # 默认显示帮助和当前配置
        parser.print_help()
        print("\n")
        show_current_config()

if __name__ == '__main__':
    main()