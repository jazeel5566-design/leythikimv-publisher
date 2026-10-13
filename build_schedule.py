#!/usr/bin/env python3
"""Rebuild media/ (JPEG copies) and schedule.json from the studio's rendered output and slide data.
Run from the studio root on the Mac:  .venv/bin/python projects/2026-10-13-anaemia-awareness-series/publisher/build_schedule.py
Keeps start_date, post_time and approved_days from the existing schedule.json."""
import json, pathlib, re, subprocess, sys
HERE = pathlib.Path(__file__).parent; PROJ = HERE.parent; ROOT = PROJ.parent.parent
OUT = ROOT / 'output' / 'anaemia-series'
sys.path.insert(0, str(PROJ))
import build
from week1 import WEEK1
build.DAYS.update(WEEK1)

def plain(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()

def alt(slide, lang):
    c = slide[lang]; parts = [plain(c.get('kicker')), plain(c['h'])]
    parts += [plain(c.get(k)) for k in ('sub', 'lede', 'body')]
    parts += [f'{plain(b)} {plain(l)}' for b, l in c.get('stats', [])]
    parts += [plain(' — '.join(x for x in r[:2] if x)) for r in c.get('rows', [])]
    parts.append(plain(c.get('note')))
    return ('Ley Thiki MV. ' + '. '.join(p.rstrip('.') for p in parts if p) + '.')[:990]

def captions():
    cap = {}
    d1 = (OUT / 'day01' / 'captions.md').read_text(encoding='utf-8')
    en = d1.split('CAPTION — ENGLISH')[1].split('CAPTION — DHIVEHI')[0].strip()
    dv = d1.split('CAPTION — DHIVEHI (DRAFT)')[1].split('ALT TEXT')[0].strip()
    cap[1] = (en, dv)
    wk = (OUT / 'week1-captions.md').read_text(encoding='utf-8')
    for m in re.finditer(r'^DAY (\d+) ·.*?^EN: (.*?)\n^DV \(DRAFT\): (.*?)\n', wk, re.S | re.M):
        cap[int(m.group(1))] = (m.group(2).strip(), m.group(3).strip())
    return cap

def main():
    sp = HERE / 'schedule.json'
    old = json.loads(sp.read_text(encoding='utf-8')) if sp.exists() else {}
    cap = captions(); days = {}
    for n in sorted(build.DAYS):
        src = OUT / f'day{n:02d}'
        if not src.is_dir() or n not in cap: continue
        dst = HERE / 'media' / f'day{n:02d}'; dst.mkdir(parents=True, exist_ok=True)
        for png in sorted(src.glob('*.png')):
            jpg = dst / (png.stem + '.jpg')
            if not jpg.exists() or jpg.stat().st_mtime < png.stat().st_mtime:
                subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '92', str(png), '--out', str(jpg)], check=True, capture_output=True)
        slides = build.DAYS[n]['slides']; k = len(slides)
        car = [dict(file=f'day{n:02d}/day{n:02d}_s{i}_feed_{lang}.jpg', alt=alt(s, lang)) for lang in ('en', 'dv') for i, s in enumerate(slides, 1)]
        stories = [f'day{n:02d}/day{n:02d}_s{i}_story_{lang}.jpg' for lang in ('en', 'dv') for i in range(1, k + 1)]
        en, dv = cap[n]
        en_body, _, en_tags = en.rpartition('#Anaemia'); dv_body = dv.split('#')[0].strip()
        caption = f'{en_body.strip()}\n\n{dv_body}\n\nEnglish slides first, then ދިވެހި — keep swiping.\nInformation only — see a doctor for advice.\n\n#Anaemia{en_tags}'
        days[str(n)] = dict(title=plain(slides[0]['en']['h']), carousel=car, stories=stories, caption=caption)
    sched = dict(account='@leythikimv', start_date=old.get('start_date'), post_time_maldives=old.get('post_time_maldives', '20:00'),
                 approved_days=old.get('approved_days', []), days=days)
    sp.write_text(json.dumps(sched, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'schedule.json: days {", ".join(days)} · approved {sched["approved_days"]} · start {sched["start_date"]}')

if __name__ == '__main__':
    main()
