import os
import re
import csv
from io import StringIO
import time

import requests
from flask import Flask, request, jsonify
from lxml import html

app = Flask(__name__)

AGENT_SECRET_KEY = os.environ.get('AGENT_SECRET_KEY', 'YourSuperSecretKey123!@#') 

def send_request(url, data=None, note_header=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Origin': 'http://genyoutube.online',
        'Referer': 'http://genyoutube.online/en1/',
        'X-Requested-With': 'XMLHttpRequest',
    }
    if note_header:
        headers['X-Note'] = note_header

    try:
        response = requests.post(url, data=data, headers=headers, timeout=60)
        response.raise_for_status()
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error during request to {url}: {e}")
        return None

def handle_genyoutube_online(video_id, requested_format):
    youtube_url = f'https://www.youtube.com/watch?v={video_id}'

    analyze_url = 'http://genyoutube.online/mates/en/analyze/ajax'
    post_data_step1 = {'url': youtube_url, 'ajax': '1', 'lang': 'en', 'platform': 'youtube'}
    data_step1 = send_request(analyze_url, data=post_data_step1)

    if not isinstance(data_step1, dict) or data_step1.get('status') != 'success':
        return {'success': False, 'message': 'Donor Error: Failed at Step 1.', 'details': data_step1}

    html_content = data_step1.get('result', '')
    if not html_content:
        return {'success': False, 'message': 'Donor Error: Empty HTML content at Step 2.'}
        
    tree = html.fromstring(html_content)
    buttons = tree.xpath('//button[@onclick]')

    found_format_data = None
    for button in buttons:
        onclick = button.get('onclick', '')
        if onclick.startswith('download('):
            match = re.search(r"download\((.*)\)", onclick, re.DOTALL)
            if match:
                params_str = match.group(1)
                try:
                    params = next(csv.reader(StringIO(params_str), quotechar="'"))
                except StopIteration:
                    continue

                if len(params) == 7:
                    format_data = {
                        'youtube_url': params[0].strip(), 'title': params[1].strip(),
                        'hash_id': params[2].strip(), 'ext': params[3].strip(),
                        'size': params[4].strip(), 'quality': params[5].strip(),
                        'format_code': params[6].strip()
                    }

                    is_mp3_request = (requested_format == 'mp3' and format_data['ext'] == 'mp3')
                    is_720p_request = (requested_format == '720' and format_data['quality'] == '720p')

                    if is_mp3_request or is_720p_request:
                        found_format_data = format_data
                        break

    if not found_format_data:
        return {'success': False, 'message': f"Donor Error: Requested format ({requested_format}) not found in HTML response."}

    convert_url = f"http://genyoutube.online/mates/en/convert?id={found_format_data['hash_id']}"
    post_data_step2 = {
        'id': found_format_data['hash_id'], 'platform': 'youtube',
        'url': found_format_data['youtube_url'], 'title': found_format_data['title'],
        'ext': found_format_data['ext'], 'note': found_format_data['quality'],
        'format': found_format_data['format_code'],
    }

    data_step2 = send_request(convert_url, data=post_data_step2, note_header=found_format_data['quality'])

    if isinstance(data_step2, dict) and data_step2.get('status') == 'success' and data_step2.get('downloadUrlX'):
        return {'success': True, 'download_url': data_step2['downloadUrlX']}
    else:
        return {'success': False, 'message': 'Donor Error: Failed to get final link.', 'details': data_step2}

@app.route('/')
def agent_handler():
    # Проверка "прогрева" от UptimeRobot (запрос без параметров)
    if not request.args:
        return jsonify({'status': 'alive', 'timestamp': time.time()})

    # Проверка секретного ключа
    request_key = request.headers.get('X-Agent-Key')
    if request_key != AGENT_SECRET_KEY:
        return jsonify({'success': False, 'message': 'Forbidden: Invalid Agent Key'}), 403

    # Получение параметров
    video_id = request.args.get('id')
    video_format = request.args.get('format')

    if not video_id or not video_format:
        return jsonify({'success': False, 'message': 'Error: Missing video ID or format.'}), 400

    result = handle_genyoutube_online(video_id, video_format)
    return jsonify(result)

if __name__ == '__main__':
    app.run(port=int(os.environ.get("PORT", 8080)))
