#!/usr/bin/env python3
"""Anonymous, bounded City Pretty API preflight. No third-party dependencies.

This utility is supplied for reproduction; it does not turn NR research cells
into verified results unless its output is reviewed from the target environment.
"""
import argparse
import concurrent.futures
import csv
import datetime
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

PREFERRED = ('4256012034', '2004005005', '8735022018')
DEFAULT_IDS = 'S001,S006,S009,S046,S077,S079,S030,S031'
MAX_BYTES = 2_000_000

def with_query(url, **params):
    parts = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parts.query))
    query.update({k: str(v) for k, v in params.items()})
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))

def request(url, origin, timeout):
    req = urllib.request.Request(url, headers={
        'Origin': origin, 'User-Agent': 'CityPrettyResearch/9',
        'Accept': 'application/json, application/javascript, text/plain;q=0.8',
    })
    result = {'url': url, 'requested_origin': origin}
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    except Exception as exc:
        return dict(result, transport_error=f'{type(exc).__name__}: {exc}', cors_for_origin='NR')
    with response:
        result['http_status'] = response.status
        result['final_url'] = response.geturl()
        names = ('Access-Control-Allow-Origin', 'Access-Control-Allow-Credentials',
                 'Access-Control-Allow-Methods', 'Access-Control-Allow-Headers',
                 'Access-Control-Expose-Headers', 'Vary', 'Retry-After',
                 'Content-Type', 'Content-Length', 'Last-Modified', 'ETag')
        result['headers'] = {n: response.headers.get(n) for n in names if response.headers.get(n) is not None}
        acao = response.headers.get('Access-Control-Allow-Origin')
        result['cors_for_origin'] = acao in ('*', origin)
        body = response.read(MAX_BYTES + 1)
    result['truncated'] = len(body) > MAX_BYTES
    text = body[:MAX_BYTES].decode('utf-8', errors='replace')
    result['body_bytes_read'] = len(body)
    try:
        result['json'] = json.loads(text)
    except (ValueError, TypeError):
        result['text_prefix'] = text[:600]
    # Callback execution still requires an actual browser test.
    match = re.search(r'cityPrettyProbe\s*\((.*)\)\s*;?\s*$', text, re.S)
    result['jsonp_wrapper_observed'] = bool(match)
    if match:
        try:
            result['jsonp_json'] = json.loads(match.group(1))
        except ValueError:
            result['jsonp_parse_error'] = True
    return result

def inspect_source(source, origin, timeout):
    result = {'source_id': source['source_id'], 'title': source['title'], 'checks': {}}
    url = source['url']
    base = urllib.parse.urlsplit(url)._replace(query='', fragment='').geturl()
    if '/resource/' in base and base.endswith('.json'):
        result['checks']['sample'] = request(with_query(base, **{'$limit': 3}), origin, timeout)
        result['checks']['count'] = request(with_query(base, **{'$select': 'count(*)'}), origin, timeout)
        result['checks']['jsonp'] = request(with_query(base, **{'$limit': 3, '$jsonp': 'cityPrettyProbe'}), origin, timeout)
        result['preferred_parcels'] = 'NR; initial bounded samples only for Socrata'
    elif re.search(r'/(?:MapServer|FeatureServer)/\d+$', base):
        meta = request(with_query(base, f='pjson'), origin, timeout)
        result['checks']['metadata'] = meta
        schema = meta.get('json', {})
        fields = [f.get('name') for f in schema.get('fields', [])] if isinstance(schema, dict) else []
        result['native_fields'] = fields
        result['geometry_type'] = schema.get('geometryType', 'NR') if isinstance(schema, dict) else 'NR'
        query_url = base + '/query'
        result['checks']['count'] = request(with_query(query_url, where='1=1', returnCountOnly='true', f='json'), origin, timeout)
        ain = next((name for name in ('AIN', 'AIN_1') if name in fields), None)
        common = dict(outFields='*', returnGeometry='false', resultRecordCount=3, f='json')
        if ain:
            where = ain + ' IN (' + ','.join("'" + v + "'" for v in PREFERRED) + ')'
            result['checks']['preferred_samples'] = request(with_query(query_url, where=where, **common), origin, timeout)
            result['preferred_parcels'] = list(PREFERRED)
        else:
            result['preferred_parcels'] = 'No exposed AIN field; spatial or address join required'
        result['checks']['sample'] = request(with_query(query_url, where='1=1', **common), origin, timeout)
        result['checks']['jsonp'] = request(with_query(query_url, where='1=1', returnCountOnly='true', f='json', callback='cityPrettyProbe'), origin, timeout)
    else:
        result['checks']['page_or_metadata'] = request(url, origin, timeout)
        result['notes'] = 'Not a supported record-query URL; no invented layer id or download route.'
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=Path(__file__).with_name('sources.csv'))
    parser.add_argument('--source-ids', default=DEFAULT_IDS)
    parser.add_argument('--origin', default='null', help='Origin header; use actual static host origin or null for file context')
    parser.add_argument('--timeout', type=float, default=12)
    parser.add_argument('--output', type=Path, default=Path('access_results.json'))
    args = parser.parse_args()
    ids = set(args.source_ids.split(','))
    with args.sources.open(encoding='utf-8', newline='') as file:
        sources = [row for row in csv.DictReader(file) if row['source_id'] in ids]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda row: inspect_source(row, args.origin, args.timeout), sources))
    payload = {'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'origin': args.origin, 'preferred_AINs': list(PREFERRED),
               'scope': 'Anonymous GET preflight; no full county download, browser execution or license certification',
               'results': results}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(results)} source checks to {args.output}')

if __name__ == '__main__':
    main()
