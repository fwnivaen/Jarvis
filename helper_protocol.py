"""Size-bounded authenticated local subprocess frames. Never log frames or keys."""
import hashlib
import hmac
import json

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 200000


def frame(key, sequence, kind, data):
    body = {'v': PROTOCOL_VERSION, 'seq': sequence, 'kind': kind, 'data': data}
    raw = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(raw.encode()) > MAX_FRAME_BYTES:
        raise ValueError('Helper frame exceeds limit.')
    return json.dumps({'body':body, 'mac':hmac.new(key.encode(),raw.encode(),hashlib.sha256).hexdigest()})+'\n'


def parse(key, expected_sequence, line):
    if not line or len(line.encode()) > MAX_FRAME_BYTES:
        raise ValueError('Invalid helper frame.')
    value=json.loads(line)
    body=value['body']
    raw=json.dumps(body,sort_keys=True,separators=(',', ':'),allow_nan=False)
    if (body['v'] != PROTOCOL_VERSION or body['seq'] != expected_sequence
            or not hmac.compare_digest(value['mac'], hmac.new(key.encode(),raw.encode(),hashlib.sha256).hexdigest())):
        raise ValueError('Unauthenticated or replayed helper frame.')
    return body
