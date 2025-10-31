import os
import re
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import time


AGENT_SECRET_KEY = os.environ.get('AGENT_SECRET_KEY', '1234567')

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
        result = handle_genyoutube_online(video_id, req_format)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Agent Error: {str(e)}'}), 500


def handle_genyoutube_online(video_id, requested_format):
    youtube_url = f'https://www.youtube.com/watch?v={video_id}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Origin': 'http://genyoutube.online',
        'Referer': 'http://genyoutube.online/en1/',
        'X-Requested-With': 'XMLHttpRequest',
    }

   
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
    soup = BeautifulSoup(html_content, 'lxml')
    buttons = soup.find_all('button', onclick=True)
    
    found_format_data = None
    for button in buttons:
        onclick_attr = button.get('onclick', '')
        if onclick_attr.startswith('download('):
            params_match = re.search(r"download\((.*)\)", onclick_attr, re.DOTALL)
            if params_match:
               
                params = [p.strip().strip("'") for p in params_match.group(1).split(',')]
                
                if len(params) == 7:
                    format_data = {
                        'youtube_url': params[0], 'title': params[1],
                        'hash_id': params[2], 'ext': params[3],
                        'size': params[4], 'quality': params[5],
                        'format_code': params[6]
                    }
                    
                   
                    is_mp3_request = (requested_format == 'mp3' and format_data['ext'] == 'mp3')
                    is_720p_request = (requested_format == '720' and format_data['quality'] == '720p')

                    if is_mp3_request or is_720p_request:
                        found_format_data = format_data
                        break
    
    if not found_format_data:
        return {'success': False, 'message': f"Donor Error: Requested format ({requested_format}) not found."}
    

    convert_url = f"http://genyoutube.online/mates/en/convert?id={found_format_data['hash_id']}"
    convert_payload = {
        'id': found_format_data['hash_id'], 'platform': 'youtube',
        'url': found_format_data['youtube_url'], 'title': found_format_data['title'],
        'ext': found_format_data['ext'], 'note': found_format_data['quality'],
        'format': found_format_data['format_code'],
    }
    
    convert_headers = headers.copy()
    if found_format_data['quality']:
        convert_headers['X-Note'] = found_format_data['quality']
        
    try:
        r2 = requests.post(convert_url, data=convert_payload, headers=convert_headers)
        r2.raise_for_status()
        data_step2 = r2.json()
    except requests.RequestException as e:
        return {'success': False, 'message': f'Donor Error: Step 4 request failed: {e}'}

    if data_step2.get('status') == 'success' and data_step2.get('downloadUrlX'):
        return {'success': True, 'download_url': data_step2['downloadUrlX']}
    else:
        return {'success': False, 'message': 'Donor Error: Failed to get final link.', 'details': data_step2}


if __name__ == '__main__':
    app.run()
