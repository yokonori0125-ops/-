"""Match Lens のビルド

  python3 build.py --sample src/sample-data.json   → index.html（サンプルデータ同梱の単体版。データを含むため Git に入れない）
  ADMIN_EMAIL=you@example.com python3 build.py --firebase
                                                    → build/public/index.html（データを含まない Firebase 版）
                                                      build/firestore.rules（管理者のメールアドレスを埋め込んだ招待制のルール）
"""
import argparse, json, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).parent
FIREBASE_SDK = '10.12.2'
FIREBASE_HEAD = '\n'.join(
    [f'<script src="https://www.gstatic.com/firebasejs/{FIREBASE_SDK}/firebase-{m}-compat.js"></script>' for m in ('app', 'auth', 'firestore')]
    + ['<script>window.MATCHLENS_CLOUD = true;</script>'])   # 設定は起動時に /__/firebase/init.json から読む


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
    # 管理者（招待リンクを発行できる人）。リポジトリには書かず、ルールにだけ埋め込む（アプリ本体には入れない）
    email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", email):
        sys.exit('ADMIN_EMAIL に、管理者の Google アカウントのメールアドレスを設定してください。')
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
    rules = (ROOT / 'firestore.rules').read_text(encoding='utf-8').replace('__ADMIN_EMAIL__', email)
    (ROOT / 'build/firestore.rules').write_text(rules, encoding='utf-8')
    print('wrote', out / 'index.html', len(html), 'bytes, and build/firestore.rules')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--sample', metavar='JSON', help='サンプルデータ（シートの配列 JSON）を同梱した単体版を作る')
    g.add_argument('--firebase', action='store_true', help='Firebase Hosting 用の配信物とルールを作る')
    a = ap.parse_args()
    build_firebase() if a.firebase else build_sample(a.sample)
