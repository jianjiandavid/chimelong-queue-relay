#!/usr/bin/env python3
"""
长隆海洋王国排队数据中继脚本
在 GitHub Actions 上运行，从 themeparks.wiki API 获取数据，
推送到阿里云服务器上的 /api/relay 接口
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# ==================== 配置 ====================
API_URL = 'https://api.themeparks.wiki/v1/entity/6f8764b7-172a-4fcf-8fec-10d3e44a55e4/live'
SERVER_URL = os.environ.get('SERVER_URL', 'http://8.148.181.106')
RELAY_TOKEN = os.environ.get('RELAY_TOKEN', 'chimelong2026')

SELECTED_ATTRACTIONS = [
    '冰山过山车',
    '鹦鹉过山车',
    '雨林升降塔25米',
    '雨林升降塔40米',
    '海底互动船',
    '极地转转杯',
    '超级激流'
]

def get_beijing_time():
    """获取北京时间"""
    utc = datetime.now(timezone.utc)
    bj = utc + timedelta(hours=8)
    return bj

def is_within_operating_hours():
    """检查是否在营业时间内 (10:00-19:30 北京时间)"""
    bj = get_beijing_time()
    h = bj.hour
    m = bj.minute
    if h < 10 or h > 19:
        return False
    if h == 19 and m > 30:
        return False
    return True

def fetch_api_data():
    """从 themeparks.wiki API 获取数据"""
    req = urllib.request.Request(API_URL, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode('utf-8'))

def process_data(api_data, bj_time):
    """处理API数据，筛选关注项目"""
    live_data = api_data.get('liveData', [])
    
    all_attractions = []
    for item in live_data:
        all_attractions.append({
            'name': item.get('name', ''),
            'waitTime': item.get('queue', {}).get('STANDBY', {}).get('waitTime', -1) if item.get('queue') else -1,
            'status': item.get('status', 'unknown'),
            'lastUpdated': item.get('lastUpdated', '')
        })
    
    # 筛选关注的项目
    selected = []
    for target_name in SELECTED_ATTRACTIONS:
        found = next((a for a in all_attractions if a['name'] == target_name), None)
        if found:
            selected.append(found)
        else:
            # 模糊匹配
            fuzzy = next((a for a in all_attractions if target_name in a['name'] or a['name'] in target_name), None)
            if fuzzy:
                selected.append(fuzzy)
            else:
                selected.append({
                    'name': target_name,
                    'waitTime': -1,
                    'status': 'unknown',
                    'lastUpdated': ''
                })
    
    date_str = bj_time.strftime('%Y-%m-%d')
    time_str = bj_time.strftime('%H:%M')
    
    return {
        'timestamp': bj_time.isoformat(),
        'date': date_str,
        'time': time_str,
        'attractions': selected,
        'allCount': len(all_attractions),
        'openCount': len([a for a in all_attractions if a['status'] == 'operating'])
    }

def send_to_server(data):
    """发送数据到服务器"""
    url = f'{SERVER_URL}/api/relay'
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'X-Relay-Token': RELAY_TOKEN
    })
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read().decode('utf-8'))

def main():
    print(f'=== 长隆排队数据中继 ===')
    print(f'北京时间: {get_beijing_time().strftime("%Y-%m-%d %H:%M")}')
    
    force = os.environ.get('FORCE_COLLECT', '0') == '1'
    
    if not is_within_operating_hours() and not force:
        print('当前不在营业时间内 (10:00-19:30)，跳过采集')
        return
    
    if force and not is_within_operating_hours():
        print('强制采集模式（手动触发）')
    
    print(f'获取 API 数据: {API_URL}')
    api_data = fetch_api_data()
    live_count = len(api_data.get('liveData', []))
    print(f'API 返回 {live_count} 个项目')
    
    if live_count == 0:
        print('API 返回空数据，跳过')
        return
    
    bj_time = get_beijing_time()
    processed = process_data(api_data, bj_time)
    
    print(f'筛选后 {len(processed["attractions"])} 个关注项目')
    for a in processed['attractions']:
        print(f'  {a["name"]}: {a["waitTime"]}分钟 ({a["status"]})')
    
    print(f'推送数据到服务器: {SERVER_URL}')
    result = send_to_server(processed)
    print(f'服务器响应: {result}')
    print('=== 完成 ===')

if __name__ == '__main__':
    main()
