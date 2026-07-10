import requests
from config import Config
import time

def chat(messages, temperature=0.1, retries=2):

    headers = {
        'Authorization': f'Bearer {Config.DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': Config.DEEPSEEK_MODEL,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': 2000
    }

    # 重试循环
    for attempt in range(retries + 1):
        try:
            # 延长 timeout 到 60 秒
            response = requests.post(
                Config.DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return {
                'success': True,
                'content': data['choices'][0]['message']['content'],
                'tokens': data.get('usage', {}).get('total_tokens', 0)
            }
        except requests.exceptions.Timeout:
            if attempt < retries:
                print(f"\n   [API 预警] 请求超时，正在进行第 {attempt + 1} 次重试...")
                time.sleep(3)  # 稍微喘口气再重试
                continue
            return {'success': False, 'error': 'API请求持续超时，请稍后再试'}
        except Exception as e:
            if attempt < retries:
                time.sleep(3)
                continue
            return {'success': False, 'error': f'API请求失败: {str(e)}'}