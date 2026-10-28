"""Match Lens のビルド

  python3 build.py --sample src/sample-data.json   → index.html（サンプルデータ同梱の単体版。データを含むため Git に入れない）
  ALLOWED_EMAIL=you@example.com python3 build.py --firebase
                                                    → build/public/index.html（データを含まない Firebase 版）
                                                      build/firestore.rules（許可アカウントを埋め込んだルール）
"""
import argparse, json, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).parent
FIREBASE_SDK = '10.12.2'
FIREBASE_HEAD = '\n'.join(
    [f'<script src="https://www.gstatic.com/firebasejs/{FIREBASE_SDK}/firebase-{m}-compat.js"></script>' for m in ('app', 'auth', 'firestore')]
    + ['<script src="/__/firebase/init.js"></script>'])   # Firebase Hosting が配信するプロジェクト設定


def template():
    return (ROOT / 'src/template.html').read_text(encoding='utf-8')


def build_sample(data_path):
    data = pathlib.Path(data_path).read_text(encoding='utf-8')
    json.loads(data)
    html = template().replace('__HEAD_EXTRA__', '').replace('__DATA__', data.replace('</', '<\\/'))
    out = ROOT / 'index.html'
    out.write_text(html, encoding='utf-8')
    print('wrote', out, len(html), 'bytes')


def build_firebase():
    email = os.environ.get('ALLOWED_EMAIL', '').strip()
    if not re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", email):
        sys.exit('ALLOWED_EMAIL に、アクセスを許可する Google アカウントのメールアドレスを設定してください。')
    src = template().replace('__HEAD_EXTRA__', FIREBASE_HEAD).replace('__DATA__', 'null')
    head, body = src.split('<header class="nav">', 1)
    html = ('<!doctype html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="robots" content="noindex, nofollow">\n'
            + head + '</head>\n<body>\n<header class="nav">' + body + '\n</body>\n</html>\n')
    out = ROOT / 'build/public'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(html, encoding='utf-8')
    (out / 'robots.txt').write_text('User-agent: *\nDisallow: /\n', encoding='utf-8')
    rules = (ROOT / 'firestore.rules').read_text(encoding='utf-8').replace('__ALLOWED_EMAIL__', email)
    (ROOT / 'build/firestore.rules').write_text(rules, encoding='utf-8')
    print('wrote', out / 'index.html', len(html), 'bytes, and build/firestore.rules')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--sample', metavar='JSON', help='サンプルデータ（シートの配列 JSON）を同梱した単体版を作る')
    g.add_argument('--firebase', action='store_true', help='Firebase Hosting 用の配信物とルールを作る')
    a = ap.parse_args()
    build_firebase() if a.firebase else build_sample(a.sample)
