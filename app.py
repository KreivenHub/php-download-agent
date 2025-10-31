import os
import re
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

# --- Настройки ---
AGENT_SECRET_KEY = os.environ.get('AGENT_SECRET_KEY', 'YourSuperSecretKey123!@#')

app = Flask(__name__)

# --- Основной маршрут, который будет принимать запросы ---
@app.route('/')
def handle_request():
    request_key = request.headers.get('X-Agent-Key')
    if request_key != AGENT_SECRET_KEY:
        return jsonify({'success': False, 'message': 'Forbidden: Invalid Agent Key'}), 403

    video_id = request.args.get('id')
    req_format = request.args.get('format')
    if not video_id or not req_format:
        return jsonify({'status': 'alive', 'timestamp': __import__('time').time()})

    try:
        result = handle_genyoutube_online(video_id, req_format)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Agent Error: {str(e)}'}), 500

# --- Обработчик для донора genyoutube.online ---
def handle_genyoutube_online(video_id, requested_format):
    youtube_url = f'https://www.youtube.com/watch?v={video_id}'
    
    donor_format = ''
    if requested_format == 'mp3':
        donor_format = 'mp3'
    elif requested_format == '720':
        donor_format = 'mp4'
    else:
        return {'success': False, 'message': f'Unsupported format: {requested_format}'}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Origin': 'http://genyoutube.online',
        'Referer': 'http://genyoutube.online/en1/',
        'X-Requested-With': 'XMLHttpRequest',
    }

    # === ШАГ 1: Анализ видео ===
    analyze_url = 'http://genyoutube.online/mates/en/analyze/ajax'
    analyze_payload = {'url': youtube_url, 'ajax': '1', 'lang': 'en', 'platform': 'youtube'}
    
    try:
        r1 = requests.post(analyze_url, data=analyze_payload, headers=headers)
        r1.raise_for_status()
        data_step1 = r1.json()
    except requests.RequestException as e:
        return {'success': False, 'message': f'Donor Error: Step 1 request failed: {e}'}
        
    if data_step1.get('status') != 'success':
        return {'success': False, 'message': 'Donor Error: Failed at Step 1.', 'details': data_step1}
    
    # === ИЗМЕНЕНИЕ: Умный поиск формата с запасным вариантом ===
    html_content = data_step1.get('result', '')
    soup = BeautifulSoup(html_content, 'lxml')
    buttons = soup.find_all('button', onclick=True)
    
    exact_match = None
    fallback_match = None # Для аудио-альтернативы (m4a)

    for button in buttons:
        onclick_attr = button.get('onclick', '')
        if onclick_attr.startswith('download('):
            params_match = re.findall(r"'([^']*)'", onclick_attr)
            if len(params_match) == 7:
                format_data = {
                    'youtube_url': params_match[0], 'title': params_match[1],
                    'hash_id': params_match[2], 'ext': params_match[3],
                    'size': params_match[4], 'quality': params_match[5],
                    'format_code': params_match[6]
                }
                
                # Ищем точное совпадение
                if (donor_format == 'mp3' and format_data['ext'] == 'mp3'):
                    exact_match = format_data
                
                if (donor_format == 'mp4' and '720p' in format_data['quality']):
                    exact_match = format_data

                # Если ищем MP3, сохраняем M4A как запасной вариант
                if (donor_format == 'mp3' and format_data['ext'] == 'm4a'):
                    if not fallback_match: # Сохраняем только первый найденный M4A
                         fallback_match = format_data

    # Выбираем лучший из найденных вариантов: сначала точное совпадение, потом запасное
    found_format_data = exact_match if exact_match else fallback_match
    
    if not found_format_data:
        return {'success': False, 'message': f"Donor Error: Requested format ({requested_format}) or a suitable alternative not found."}
    # === КОНЕЦ ИЗМЕНЕНИЯ ===

    # === ШАГ 4 и 5: Запрос на конвертацию (код без изменений) ===
    convert_url = f"http://genyoutube.online/mates/en/convert?id={found_format_data['hash_id']}"
    convert_payload = {
        'id': found_format_data['hash_id'], 'platform': 'youtube',
        'url': found_format_data['youtube_url'], 'title': found_format_data['title'],
        'ext': found_format_data['ext'], 'note': found_format_data['quality'],
        'format': found_format_data['format_code'],
    }
    
    try:
        r2 = requests.post(convert_url, data=convert_payload, headers=headers)
        r2.raise_for_status()
        data_step2 = r2.json()
    except requests.RequestException as e:
        return {'success': False, 'message': f'Donor Error: Step 4 request failed: {e}'}

    if data_step2.get('status') == 'success' and data_step2.get('downloadUrlX'):
        return {'success': True, 'download_url': data_step2['downloadUrlX']}
    else:
        return {'success': False, 'message': 'Donor Error: Failed to get final link.', 'details': data_step2}

# Эта часть нужна для локального тестирования, Render ее игнорирует
if __name__ == '__main__':
    app.run(debug=True)
