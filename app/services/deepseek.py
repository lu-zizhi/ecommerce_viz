import requests
from config import Config


def chat(messages, temperature=0.1):
    """
    调用 DeepSeek API
    messages: 对话消息列表，格式 [{'role': 'user', 'content': '...'}]
    temperature: 越低越稳定，NL2VIS场景用0.1保证输出稳定
    """
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

    try:
        response = requests.post(
            Config.DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return {
            'success': True,
            'content': data['choices'][0]['message']['content']
        }
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'API请求超时，请重试'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'API请求失败: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': f'未知错误: {str(e)}'}