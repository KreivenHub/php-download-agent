<?php
header('Content-Type: application/json');
set_time_limit(180);
libxml_use_internal_errors(true);

define('AGENT_SECRET_KEY', 'YourSuperSecretKey123!@#');

$request_key = $_SERVER['HTTP_X_AGENT_KEY'] ?? '';
if ($request_key !== AGENT_SECRET_KEY) {
    http_response_code(403);
    echo json_encode(['success' => false, 'message' => 'Forbidden: Invalid Agent Key']);
    exit;
}

if (empty($_GET['id']) && empty($_GET['format'])) {
    echo json_encode(['status' => 'alive', 'timestamp' => time()]);
    exit;
}

$videoId = $_GET['id'] ?? null;
$format = $_GET['format'] ?? null;

if (!$videoId || !$format) {
    echo json_encode(['success' => false, 'message' => 'Error: Missing video ID or format.']);
    exit;
}

$result = handle_genyoutube_online($videoId, $format);

echo json_encode($result);


function handle_genyoutube_online($videoId, $requestedFormat) {
    $youtubeUrl = 'https://www.youtube.com/watch?v=' . $videoId;

    $analyzeUrl = 'http://genyoutube.online/mates/en/analyze/ajax';
    $postDataStep1 = http_build_query([
        'url' => $youtubeUrl,
        'ajax' => '1',
        'lang' => 'en',
        'platform' => 'youtube'
    ]);

    $responseStep1 = send_curl_request_genyoutube($analyzeUrl, $postDataStep1);
    if (!$responseStep1) {
        return ['success' => false, 'message' => 'Donor Error: No response at Step 1.'];
    }

    $dataStep1 = json_decode($responseStep1, true);
    if (!isset($dataStep1['status']) || $dataStep1['status'] !== 'success') {
        return ['success' => false, 'message' => 'Donor Error: Failed at Step 1.', 'details' => $responseStep1];
    }
    
    $htmlContent = $dataStep1['result'];
    $doc = new DOMDocument();
    $doc->loadHTML($htmlContent);
    $xpath = new DOMXPath($doc);
    $buttons = $xpath->query('//button[@onclick]');
    
    $foundFormatData = null;

    foreach ($buttons as $button) {
        $onclick = $button->getAttribute('onclick');
        if (strpos($onclick, 'download(') === 0) {
            preg_match('/download\((.*)\)/s', $onclick, $matches);
            if (isset($matches[1])) {
                $params = str_getcsv($matches[1], ',', "'");
                if (count($params) === 7) {
                    $formatData = [
                        'youtube_url' => trim($params[0]), 'title' => trim($params[1]),
                        'hash_id' => trim($params[2]), 'ext' => trim($params[3]),
                        'size' => trim($params[4]), 'quality' => trim($params[5]),
                        'format_code' => trim($params[6])
                    ];

                    $isMp3Request = ($requestedFormat === 'mp3' && $formatData['ext'] === 'mp3');
                    $is720pRequest = ($requestedFormat === '720' && $formatData['quality'] === '720p');

                    if ($isMp3Request || $is720pRequest) {
                        $foundFormatData = $formatData;
                        break;
                    }
                }
            }
        }
    }

    if (!$foundFormatData) {
        return ['success' => false, 'message' => "Donor Error: Requested format ($requestedFormat) not found."];
    }

    $convertUrl = 'http://genyoutube.online/mates/en/convert?id=' . urlencode($foundFormatData['hash_id']);
    $postDataStep2 = http_build_query([
        'id' => $foundFormatData['hash_id'], 'platform' => 'youtube',
        'url' => $foundFormatData['youtube_url'], 'title' => $foundFormatData['title'],
        'ext' => $foundFormatData['ext'], 'note' => $foundFormatData['quality'],
        'format' => $foundFormatData['format_code'],
    ]);

    $responseStep2 = send_curl_request_genyoutube($convertUrl, $postDataStep2, $foundFormatData['quality']);
    if (!$responseStep2) {
        return ['success' => false, 'message' => 'Donor Error: No response at Step 4.'];
    }

    $dataStep2 = json_decode($responseStep2, true);

    if ($dataStep2 && isset($dataStep2['status']) && $dataStep2['status'] === 'success' && !empty($dataStep2['downloadUrlX'])) {
        return ['success' => true, 'download_url' => $dataStep2['downloadUrlX']];
    } else {
        return ['success' => false, 'message' => 'Donor Error: Failed to get final link.', 'details' => $responseStep2];
    }
}

function send_curl_request_genyoutube($url, $postData, $noteHeader = '') {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $postData);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);

    $headers = [
        'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Origin: http://genyoutube.online',
        'Referer: http://genyoutube.online/en1/',
        'X-Requested-With: XMLHttpRequest',
    ];
    if (!empty($noteHeader)) {
        $headers[] = 'X-Note: ' . $noteHeader;
    }
    
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $response = curl_exec($ch);
    
    if (curl_errno($ch)) {
        curl_close($ch);
        return false;
    }
    
    curl_close($ch);
    return $response;
}
