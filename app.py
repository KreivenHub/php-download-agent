import os
import re
import csv
from io import StringIO
import time
import random

import requests
from flask import Flask, request, jsonify
from lxml import html


app = Flask(__name__)


AGENT_SECRET_KEY = os.environ.get('AGENT_SECRET_KEY', 'YourSuperSecretKey123!@#')


request_counter = 0


@app.route('/')
def agent_handler():
    global request_counter


    if not request.args:
        return jsonify({'status': 'alive', 'timestamp': time.time()})


    request_key = request.headers.get('X-Agent-Key')
    if request_key != AGENT_SECRET_KEY:
        return jsonify({'success': False, 'message': 'Forbidden: Invalid Agent Key'}), 403


    video_id = request.args.get('id')
    video_format = request.args.get('format')

    if not video_id or not video_format:
        return jsonify({'success': False, 'message': 'Error: Missing video ID or format.'}), 400


    donor_handlers = [
        handle_genyoutube_online,
        handle_mp3youtube_cc,
    ]
    

    handler_index = request_counter % len(donor_handlers)
    selected_handler = donor_handlers[handler_index]
    request_counter += 1 

    try:

        result = selected_handler(video_id, video_format)
        return jsonify(result)
    except Exception as e:

        print(f"CRITICAL AGENT ERROR with handler {selected_handler.__name__}: {e}")
        return jsonify({'success': False, 'message': f'Agent Error: {str(e)}'}), 500


def handle_genyoutube_online(video_id, requested_format):
    youtube_url = f'https://www.youtube.com/watch?v={video_id}'
    

    analyze_url = 'http://genyoutube.online/mates/en/analyze/ajax'
    post_data_step1 = {'url': youtube_url, 'ajax': '1', 'lang': 'en', 'platform': 'youtube'}
    data_step1 = send_request(analyze_url, data=post_data_step1)

    if not isinstance(data_step1, dict) or data_step1.get('status') != 'success':
        return {'success': False, 'message': 'Donor Error (genyoutube): Failed at Step 1.', 'details': data_step1}


    html_content = data_step1.get('result', '')
    if not html_content:
        return {'success': False, 'message': 'Donor Error (genyoutube): Empty HTML content at Step 2.'}
    tree = html.fromstring(html_content)
    buttons = tree.xpath('//button[@onclick]')

    found_format_data = None
    for button in buttons:
        onclick = button.get('onclick', '')
        if onclick.startswith('download('):
            match = re.search(r"download\((.*)\)", onclick, re.DOTALL)
            if match:
                params_str = match.group(1)
                try: params = next(csv.reader(StringIO(params_str), quotechar="'"))
                except StopIteration: continue
                if len(params) == 7:
                    format_data = {
                        'youtube_url': params[0].strip(), 'title': params[1].strip(), 'hash_id': params[2].strip(),
                        'ext': params[3].strip(), 'size': params[4].strip(), 'quality': params[5].strip(),
                        'format_code': params[6].strip()
                    }
                    if (requested_format == 'mp3' and format_data['ext'] == 'mp3') or \
                       (requested_format == '720' and format_data['quality'] == '720p'):
                        found_format_data = format_data
                        break
    if not found_format_data:
        return {'success': False, 'message': f"Donor Error (genyoutube): Format ({requested_format}) not found."}


    convert_url = f"http://genyoutube.online/mates/en/convert?id={found_format_data['hash_id']}"
    post_data_step2 = {
        'id': found_format_data['hash_id'], 'platform': 'youtube', 'url': found_format_data['youtube_url'],
        'title': found_format_data['title'], 'ext': found_format_data['ext'],
        'note': found_format_data['quality'], 'format': found_format_data['format_code'],
    }
    data_step2 = send_request(convert_url, data=post_data_step2, note_header=found_format_data['quality'])

    if isinstance(data_step2, dict) and data_step2.get('status') == 'success' and data_step2.get('downloadUrlX'):
        return {'success': True, 'download_url': data_step2['downloadUrlX']}
    else:
        return {'success': False, 'message': 'Donor Error (genyoutube): Failed to get final link.', 'details': data_step2}



def handle_mp3youtube_cc(video_id, requested_format):
    youtube_url = f'https://www.youtube.com/watch?v={video_id}'
    common_headers = {
        'Origin': 'https://iframe.y2meta-uk.com',
        'Referer': 'https://iframe.y2meta-uk.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }

    try:
        key_res = requests.get('https://api.mp3youtube.cc/v2/sanity/key', headers=common_headers, timeout=10)
        key_res.raise_for_status()
        api_key = key_res.json().get('key')
        if not api_key:
            return {'success': False, 'message': 'Donor Error (y2meta): Could not extract API key.'}
    except requests.RequestException as e:
        return {'success': False, 'message': f"Donor Error (y2meta): Failed to get API key: {e}"}


    converter_url = 'https://api.mp3youtube.cc/v2/converter'
    converter_headers = {**common_headers, 'Key': api_key}
    
    post_data = {}
    if requested_format == 'mp3':
        post_data = {'link': youtube_url, 'format': 'mp3', 'audioBitrate': '320', 'filenameStyle': 'pretty'}
    elif requested_format == '720':
        post_data = {'link': youtube_url, 'format': 'mp4', 'audioBitrate': '128', 'videoQuality': '720', 'filenameStyle': 'pretty', 'vCodec': 'h264'}
    else:
        return {'success': False, 'message': 'Unsupported format requested.'}
    
    try:
        conv_res = requests.post(converter_url, headers=converter_headers, data=post_data, timeout=60)
        conv_res.raise_for_status()
        result_data = conv_res.json()
    except requests.RequestException as e:
        return {'success': False, 'message': f'Donor Error (y2meta): Converter request failed: {e}'}

    # Шаг 3: Возврат результата
    if result_data.get('status') == 'tunnel' and result_data.get('url'):
        return {'success': True, 'download_url': result_data['url']}
    else:
        return {'success': False, 'message': 'Donor Error (y2meta): Failed to get final link.', 'details': result_data}


def send_request(url, data=None, note_header=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Origin': 'http://genyoutube.online',
        'Referer': 'http://genyoutube.online/en1/',
        'X-Requested-With': 'XMLHttpRequest',
    }
    if note_header: headers['X-Note'] = note_header
    try:
        response = requests.post(url, data=data, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
       
        return None


if __name__ == '__main__':
    app.run(port=int(os.environ.get("PORT", 8080)))
