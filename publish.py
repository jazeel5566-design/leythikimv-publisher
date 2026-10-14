#!/usr/bin/env python3
"""Post one day of the Ley Thiki MV series to Instagram (official publishing API, standard library only).

  python publish.py                 post today's day (Maldives time) if it is approved and not posted yet
  python publish.py --day 3         post a specific day
  python publish.py --extra NAME    post a one-off post from schedule.json "extras" (must have "approved": true)
  python publish.py --dry-run       show exactly what would be sent; nothing is posted
  python publish.py --check         test the access token: prints the account it belongs to; nothing is posted

Environment:
  IG_ACCESS_TOKEN  long-lived Instagram user token with instagram_business_content_publish   (required unless --dry-run)
  MEDIA_BASE_URL   public address of the media/ folder, e.g. https://raw.githubusercontent.com/<user>/<repo>/main/media
  IG_USER_ID       Instagram account id (default "me")
  IG_API_BASE      default https://graph.instagram.com
A day posts only if it is listed in schedule.json "approved_days". Progress is saved to state.json after every
step, so a re-run never posts the same thing twice."""
import argparse, datetime, json, os, pathlib, sys, time, urllib.error, urllib.parse, urllib.request

HERE = pathlib.Path(__file__).parent
MV = datetime.timezone(datetime.timedelta(hours=5))  # Maldives time

def api(method, path, params, dry):
    base = os.environ.get('IG_API_BASE', 'https://graph.instagram.com')
    shown = {k: (v if len(str(v)) < 90 else str(v)[:87] + '...') for k, v in params.items()}
    if dry:
        print(f'  DRY {method} /{path} {json.dumps(shown, ensure_ascii=False)}')
        return {'id': f'dry-{abs(hash(json.dumps(params, sort_keys=True))) % 10**8}', 'status_code': 'FINISHED'}
    q = dict(params, access_token=os.environ['IG_ACCESS_TOKEN'])
    url = f'{base}/{path}'
    data = None
    if method == 'GET':
        url += '?' + urllib.parse.urlencode(q)
    else:
        data = urllib.parse.urlencode(q).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        raise RuntimeError(f'{method} /{path} failed ({e.code}): {body}') from None

def container(user, params, dry, alt=None):
    """Create a media container; if the alt text is refused, retry once without it."""
    if alt:
        try:
            return api('POST', f'{user}/media', dict(params, alt_text=alt), dry)['id']
        except RuntimeError as e:
            print(f'  ! alt text not accepted, retrying without it: {e}')
    return api('POST', f'{user}/media', params, dry)['id']

def wait_ready(cid, dry):
    for _ in range(30):
        s = api('GET', cid, {'fields': 'status_code'}, dry).get('status_code')
        if s == 'FINISHED':
            return
        if s in ('ERROR', 'EXPIRED'):
            raise RuntimeError(f'container {cid} status {s}')
        time.sleep(4)
    raise RuntimeError(f'container {cid} not ready after 2 minutes')

def publish(user, cid, dry):
    wait_ready(cid, dry)
    return api('POST', f'{user}/media_publish', {'creation_id': cid}, dry)['id']

def main():
    a = argparse.ArgumentParser(); a.add_argument('--day', type=int); a.add_argument('--dry-run', action='store_true')
    a.add_argument('--check', action='store_true')
    a.add_argument('--extra')
    o = a.parse_args(); dry = o.dry_run
    if o.check:
        if not os.environ.get('IG_ACCESS_TOKEN'): sys.exit('IG_ACCESS_TOKEN is not set')
        me = api('GET', os.environ.get('IG_USER_ID', 'me'), {'fields': 'user_id,username,account_type'}, False)
        print(f"✓ Token works. Account: @{me.get('username')} ({me.get('account_type')}), id {me.get('user_id')}")
        return
    sched = json.loads((HERE / 'schedule.json').read_text(encoding='utf-8'))
    sp = HERE / 'state.json'
    state = json.loads(sp.read_text(encoding='utf-8')) if sp.exists() else {}
    if o.extra:
        d = sched.get('extras', {}).get(o.extra)
        if not d: sys.exit(f'No extra post named {o.extra}')
        if not d.get('approved') and not dry: sys.exit(f'Extra post {o.extra} is not approved — not posting.')
        return post(d, f'extra:{o.extra}', o.extra, state, sp, dry)
    day = o.day
    if day is None:
        if not sched.get('start_date'):
            print('No start_date in schedule.json yet — nothing to do.'); return
        today = datetime.datetime.now(MV).date()
        day = (today - datetime.date.fromisoformat(sched['start_date'])).days + 1
        print(f'Maldives date {today} → day {day}')
    d = sched['days'].get(str(day))
    if not d:
        print(f'Day {day} is not in the schedule — nothing to do.'); return
    if day not in sched.get('approved_days', []):
        msg = f'Day {day} is not approved — not posting.'
        if dry or o.day is None and day < 1:
            print(msg); return
        sys.exit(msg)   # fail loudly so a missed approval is noticed
    return post(d, str(day), f'Day {day}', state, sp, dry)

def post(d, key, label, state, sp, dry):
    base = os.environ.get('MEDIA_BASE_URL', '').rstrip('/')
    if not base:
        if not dry: sys.exit('MEDIA_BASE_URL is not set')
        base = 'https://example.invalid/media'
    if not dry and not os.environ.get('IG_ACCESS_TOKEN'):
        sys.exit('IG_ACCESS_TOKEN is not set')
    user = os.environ.get('IG_USER_ID', 'me')
    st = state.setdefault(key, {})
    def save():
        if not dry: sp.write_text(json.dumps(state, indent=1), encoding='utf-8')
    for f in [x['file'] for x in d['carousel']] + d.get('stories', []):
        if not (HERE / 'media' / f).exists(): sys.exit(f'Missing media file: {f}')

    if not st.get('carousel_id') and not dry:
        # second safety net: never trust the record alone — look at what is already on the account
        recent = api('GET', f'{user}/media', {'fields': 'id,caption,timestamp', 'limit': '25'}, False).get('data', [])
        key_text = d['caption'].strip()[:120]
        same = [m for m in recent if (m.get('caption') or '').strip()[:120] == key_text]
        if same:
            st['carousel_id'] = same[0]['id']; st['stories'] = d.get('stories', []); save()
            print(f'{label}: an identical post is already on Instagram ({same[0]["id"]}, {same[0].get("timestamp")}) — not posting again.')
            return
    if st.get('carousel_id'):
        print(f'{label}: carousel already posted ({st["carousel_id"]})')
    else:
        print(f'{label}: carousel with {len(d["carousel"])} slides')
        kids = [container(user, {'image_url': f'{base}/{x["file"]}', 'is_carousel_item': 'true'}, dry, x.get('alt')) for x in d['carousel']]
        cid = api('POST', f'{user}/media', {'media_type': 'CAROUSEL', 'children': ','.join(kids), 'caption': d['caption']}, dry)['id']
        st['carousel_id'] = publish(user, cid, dry); save()
        print(f'  ✓ carousel published: {st["carousel_id"]}')
    done = st.setdefault('stories', [])
    for f in d.get('stories', [])[len(done):]:
        sid = publish(user, container(user, {'image_url': f'{base}/{f}', 'media_type': 'STORIES'}, dry), dry)
        done.append(sid); save()
        print(f'  ✓ story published: {f}')
    print(f'{label}: done' + (' (dry run — nothing was posted)' if dry else ''))

if __name__ == '__main__':
    try:
        main()
    except RuntimeError as e:
        sys.exit(f'FAILED: {e}')
