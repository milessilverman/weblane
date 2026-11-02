#!/usr/bin/env python3
"""Read-only public HTTP source check. Python standard library; no credentials.

This does not grant reuse rights, certify countywide completeness, or update the
research CSV. Run in the intended GitHub Actions runner to obtain runner evidence.
"""
import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT='CityPrettySourceVerifier/1.0 (public metadata and three-record checks)'
MAX_BYTES=4_000_000

def now():
    return datetime.now(timezone.utc).isoformat()

def url_with(base, params):
    parsed=urllib.parse.urlsplit(base)
    query=dict(urllib.parse.parse_qsl(parsed.query))
    query.update(params)
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))

def request(url, timeout, method='GET', headers=None):
    req=urllib.request.Request(url,method=method,headers={'User-Agent':USER_AGENT,**(headers or {})})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as response:
                body=response.read(MAX_BYTES+1) if method!='HEAD' else b''
                if len(body)>MAX_BYTES:
                    raise ValueError('Response exceeds metadata/sample byte limit')
                return dict(url=url,final_url=response.url,http_status=response.status,
                            content_type=response.headers.get('Content-Type'),
                            content_length=response.headers.get('Content-Length'),
                            last_modified=response.headers.get('Last-Modified'),body=body)
        except urllib.error.HTTPError as error:
            if error.code in (429,502,503,504) and attempt==0:
                time.sleep(2)
                continue
            raise

def fetch_json(url, timeout, evidence_file):
    r=request(url,timeout)
    obj=json.loads(r.pop('body').decode('utf-8-sig'))
    evidence_file.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    if isinstance(obj,dict) and 'error' in obj:
        raise ValueError('ArcGIS error: '+json.dumps(obj['error'],ensure_ascii=False))
    return obj,r

def as_identifier_text(attrs, fields):
    result=dict(attrs)
    for name in fields:
        if name in result and result[name] is not None:
            result[name]=str(result[name])
    return result

def check_arcgis(item, timeout, evidence_dir):
    base=item['url']
    meta,transport=fetch_json(url_with(base,{'f':'pjson'}),timeout,evidence_dir/'metadata.json')
    if not isinstance(meta,dict) or not isinstance(meta.get('fields'),list) or not meta.get('geometryType'):
        raise ValueError('Response is not a feature-layer schema')
    field_names=[field['name'] for field in meta['fields']]
    missing=[x for x in item.get('expected_fields',[]) if x not in field_names]
    oid=meta.get('objectIdField') or next((f['name'] for f in meta['fields'] if f.get('type')=='esriFieldTypeOID'),None)
    requested=list(dict.fromkeys([x for x in item.get('sample_fields',[]) if x in field_names]+([oid] if oid else [])))
    where=item.get('where','1=1')
    params={'f':'pjson','where':where,'outFields':','.join(requested) or '*','returnGeometry':'false','resultRecordCount':3}
    if oid and meta.get('advancedQueryCapabilities',{}).get('supportsOrderBy'):
        params['orderByFields']=oid+' ASC'
    features,feature_transport=fetch_json(url_with(base+'/query',params),timeout,evidence_dir/'samples_raw.json')
    raw_records=[f['attributes'] for f in features.get('features',[])]
    if len(raw_records)!=3:
        raise ValueError(f'Expected three real records, received {len(raw_records)}. Check filter, access and source scope.')
    count,count_transport=fetch_json(url_with(base+'/query',{'f':'pjson','where':where,'returnCountOnly':'true'}),timeout,evidence_dir/'count_raw.json')
    if not isinstance(count.get('count'),int):
        raise ValueError('Count response missing integer count')
    identifiers=item.get('identifier_fields',[])+([oid] if oid else [])
    result={'machine_check':'PASS' if not missing else 'SCHEMA_MISMATCH',
            'geometry':meta['geometryType'],'maxRecordCount':meta.get('maxRecordCount','NR'),
            'editingInfo':meta.get('editingInfo','NR'),'fields':field_names,
            'missing_expected_fields':missing,'records':[as_identifier_text(r,identifiers) for r in raw_records],
            'feature_count':count['count'],'count_scope':item['count_scope'],
            'transport':{'metadata':transport,'samples':feature_transport,'count':count_transport},
            'minimum_positive_area':'NR','licence_clearance':'NOT_CHECKED'}
    area=item.get('area_field')
    if area and area in field_names and meta.get('advancedQueryCapabilities',{}).get('supportsOrderBy'):
        minparams={**params,'where':f'({where}) AND {area}>0','outFields':','.join(dict.fromkeys(requested+[area])),
                   'orderByFields':area+' ASC','resultRecordCount':1}
        try:
            smallest,_=fetch_json(url_with(base+'/query',minparams),timeout,evidence_dir/'minimum_area_raw.json')
            values=[x['attributes'] for x in smallest.get('features',[])]
            result['minimum_positive_area']=values[0] if values else 'NR'
            result['minimum_area_note']='Smallest positive stored field in query scope; not an inclusion policy or independently measured acreage.'
        except Exception as exc:
            result['minimum_area_error']=str(exc)
    return result

def check_socrata(item,timeout,evidence_dir):
    # Start with bounded SoQL. If rejected, try bare public endpoint (default page).
    # Bare response is never treated as a complete database or a complete count.
    try:
        records,transport=fetch_json(url_with(item['url'],{'$limit':3}),timeout,evidence_dir/'response_raw.json')
    except Exception:
        records,transport=fetch_json(item['url'],timeout,evidence_dir/'response_raw.json')
    if not isinstance(records,list) or len(records)<3:
        raise ValueError('No three real Socrata records recovered')
    return {'machine_check':'PASS','records':records[:3],'transport':transport,
            'feature_count':'NR','count_scope':item['count_scope'],'licence_clearance':'NOT_CHECKED',
            'note':'Records may represent amenities at the same park; default response length is not a county park count.'}

def check_file(item,timeout,evidence_dir):
    r=request(item['url'],timeout,method='HEAD')
    r.pop('body',None)
    if 'login' in r['final_url'].lower() or 'text/html' in (r['content_type'] or '').lower():
        raise ValueError('File request returned HTML/login rather than a file header')
    return {'machine_check':'HEAD_ONLY','transport':r,'records':'NR','licence_clearance':'NOT_CHECKED',
            'note':'Headers do not prove complete download, valid archive or parsed schema; no bulk bytes downloaded.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(Path(__file__).with_name('verification_targets.json')))
    parser.add_argument('--out',required=True,help='New result directory; existing files are never overwritten')
    parser.add_argument('--only',help='Comma-separated target IDs')
    parser.add_argument('--timeout',type=int,default=15)
    parser.add_argument('--validate-config',action='store_true')
    args=parser.parse_args()
    targets=json.loads(Path(args.config).read_text(encoding='utf-8'))
    ids=[x['id'] for x in targets]
    if len(ids)!=len(set(ids)):
        parser.error('Duplicate target IDs')
    for target in targets:
        if not target['url'].startswith('https://') or target['kind'] not in ('arcgis','socrata','file'):
            parser.error('Invalid target '+target['id'])
    if args.only:
        selected=set(args.only.split(','))
        if selected-set(ids):
            parser.error('Unknown target IDs: '+','.join(sorted(selected-set(ids))))
        targets=[x for x in targets if x['id'] in selected]
    if args.validate_config:
        print(json.dumps({'config_valid':True,'targets':len(targets)}))
        return 0
    destination=Path(args.out)
    destination.mkdir(parents=True,exist_ok=False)
    results=[]
    methods={'arcgis':check_arcgis,'socrata':check_socrata,'file':check_file}
    for item in targets:
        evidence_dir=destination/item['id']
        evidence_dir.mkdir()
        record={'id':item['id'],'url':item['url'],'checked_at':now(),'runner_claim':'This execution host only; no inference about other networks.'}
        try:
            record.update(methods[item['kind']](item,args.timeout,evidence_dir))
        except Exception as error:
            record.update(machine_check='NR',records='NR',feature_count='NR',error=type(error).__name__+': '+str(error))
        results.append(record)
        print(json.dumps({'id':item['id'],'machine_check':record['machine_check']},ensure_ascii=False),flush=True)
    report={'run_at':now(),'scope':'Unauthenticated read-only metadata/sample checks. Not a licence or completeness audit.','results':results}
    (destination/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if all(x['machine_check']=='PASS' for x in results) else 1

if __name__=='__main__':
    sys.exit(main())
