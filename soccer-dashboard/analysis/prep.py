"""Sheet (array-of-arrays JSON) → tidy DataFrame: 12 team-match rows."""
import json, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]

def clean(v):
    return '' if v is None else ' '.join(str(v).split())

def read_aoa(path):
    """シートを行の配列にする。.xlsx（最初のシート）またはシート配列の .json を受け付ける"""
    path = pathlib.Path(path)
    if path.suffix.lower() == '.xlsx':
        import datetime, openpyxl
        ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
        fix = lambda v: v.strftime('%Y-%m-%d') if isinstance(v, (datetime.date, datetime.datetime)) else v
        return [[fix(v) for v in r] for r in ws.iter_rows(values_only=True)]
    return json.loads(path.read_text(encoding='utf-8'))

def load(path=ROOT / 'src/sample-data.json'):
    aoa = read_aoa(path)
    hr = next(i for i, r in enumerate(aoa) if r and clean(r[0]) == '日付')
    cat_r, grp_r, met_r, sub_r = (aoa[hr - 1], aoa[hr], aoa[hr + 1], aoa[hr + 2])
    width = max(map(len, (cat_r, grp_r, met_r, sub_r)))
    g = lambda r, c: clean(r[c]) if c < len(r) else ''
    cols, ncat, grp, met = {}, 0, '', ''
    for c in range(width):
        cv, gv, mv, sv = g(cat_r, c), g(grp_r, c), g(met_r, c), g(sub_r, c)
        if cv: ncat += 1; grp = met = ''
        if gv: grp = gv; met = ''
        if mv: met = mv
        if ncat <= 1:
            if gv: cols[gv] = c
            continue
        if met or sv:
            cols[f'{met or grp}|{sv}'] = c
    rows = []
    for r in aoa[hr + 3:]:
        if not r or not clean(r[0]) or clean(r[0]).startswith('平均'):
            break
        rows.append({k: (r[c] if c < len(r) else None) for k, c in cols.items()})
    df = pd.DataFrame(rows)
    num = [k for k in df.columns if '|' in k]
    df[num] = df[num].apply(pd.to_numeric, errors='coerce')
    # 同一試合の相手行を付与（失点・被xGなど）
    def other(row, key):
        same = df[(df['日付'] == row['日付']) & (df['試合'] == row['試合']) & (df['チーム'] != row['チーム'])]
        return same.iloc[0][key]
    df['GF'] = df['ゴール|']
    df['GA'] = df.apply(lambda r: other(r, 'ゴール|'), axis=1)
    df['xG'] = df['xG|']
    df['xGA'] = df.apply(lambda r: other(r, 'xG|'), axis=1)
    df['own'] = (df['区分'] == '自チーム').astype(int)
    df['jleague'] = df['チーム'].isin(['Kyoto Sanga', 'Gamba Osaka', 'Kashima Antlers']).astype(int)
    df['opp_jleague'] = df.apply(lambda r: other(r, 'jleague'), axis=1)
    df['match'] = df['日付'] + ' ' + df['試合']
    return df
