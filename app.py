import os
import re
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import time

AGENT_SECRET_KEY = os.environ.get('AGENT_SECRET_KEY', 'YourSuperSecretKey123!@#')
app = Flask(__name__)

@app.route('/')
def handle_request():
    request_key = request.headers.get('X-Agent-Key')
    if request_key != AGENT_SECRET_KEY:
        return jsonify({'success': False, 'message': 'Forbidden: Invalid Agent Key'}), 403

    video_id = request.args.get('id')
    req_format = request.args.get('format')
    if not video_id or not req_format:
        return jsonify({'status': 'alive', 'timestamp': time.time()})

    try:
        result = handle_genyoutube_online_DIAGNOSTIC(video_id, req_format)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Agent Error: {str(e)}'}), 500

# --- ДИАГНОСТИЧЕСКАЯ ВЕРСИЯ ОБРАБОТЧИКА ---
def handle_genyoutube_online_DIAGNOSTIC(video_id, requested_format):
    youtube_url = f'https://www.youtube.com/watch?v={video_id}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
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
    
    html_content = data_step1.get('result', '')

    # --- ГЛАВНОЕ ИЗМЕНЕНИЕ: ВЫВОДИМ HTML В ЛОГ ---
    print("--- START DIAGNOSTIC HTML FROM DONOR ---")
    print(html_content)
    print("--- END DIAGNOSTIC HTML FROM DONOR ---")
    # ---------------------------------------------
    
    # Вместо парсинга просто возвращаем ошибку, чтобы увидеть лог
    return {'success': False, 'message': 'DIAGNOSTIC MODE: Check Render logs for HTML output.'}
