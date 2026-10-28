# Match Lens

サッカーのチームスタッツ（Excel）を読み込み、試合別・時系列のグラフと、得点・失点の要因分析（相関・重回帰）を自動で作るダッシュボードです。
GitHub でコードを管理し、Firebase（Hosting・Authentication・Firestore）で動かします。

## アクセス制限の仕組み

| 層 | 誰が見られるか | 中身 |
| --- | --- | --- |
| Firebase Hosting | URL を知っている人（ログイン画面のみ） | アプリのコード。試合データは含まない |
| Firebase Authentication | Google アカウントでログインした人 | ログイン情報のみ |
| Firestore | **許可した 1 アカウントだけ** | アップロードした試合データ |

- Firestore のセキュリティルール（`firestore.rules`）で、メールアドレスが `ALLOWED_EMAIL` と一致し、確認済みのアカウントだけに読み書きを許可しています。それ以外はすべて拒否されます。
- 許可するメールアドレスはリポジトリに書かず、GitHub のシークレットからデプロイ時に埋め込みます。
- ルールは `npm run test:rules`（Firestore エミュレーター）で検証し、CI でデプロイ前に毎回実行します。
- 試合データ（`*.xlsx`、`src/sample-data.json`）と分析結果（`analysis/results.txt`）は `.gitignore` で除外しています。

## 初回セットアップ

1. [Firebase コンソール](https://console.firebase.google.com/) でプロジェクトを作成する。
2. **Authentication** → ログイン方法 → **Google** を有効にする。
3. **Firestore Database** → データベースを作成（本番環境モード）。
4. **Hosting** → 「始める」でホスティングを有効にする（CLI の手順はスキップしてよい）。
5. **プロジェクトの設定** → マイアプリ → **ウェブアプリを追加**（Hosting の `/__/firebase/init.js` がこの設定を配信する）。
6. [Google Cloud コンソールの IAM](https://console.cloud.google.com/iam-admin/serviceaccounts) でデプロイ用のサービスアカウントを作り、ロール **Firebase 管理者**（`roles/firebase.admin`）を付けて、JSON キーを発行する。
7. GitHub のリポジトリ → Settings → Secrets and variables → Actions に、次の 3 つを登録する。

   | 名前 | 値 |
   | --- | --- |
   | `FIREBASE_PROJECT_ID` | Firebase のプロジェクト ID |
   | `FIREBASE_SERVICE_ACCOUNT` | 手順 6 の JSON キーの中身すべて |
   | `ALLOWED_EMAIL` | アクセスを許可する Google アカウントのメールアドレス |

8. `main` に反映する（または Actions タブから「Match Lens — test and deploy」を手動実行する）。
9. `https://<プロジェクトID>.web.app` を開き、許可したアカウントでログインして、データ取込からチームスタッツの Excel を読み込む。データは Firestore に保存され、次回から自動で表示されます。

## 開発

```bash
npm ci
npm run test:rules                               # セキュリティルールのテスト（Java が必要）
ALLOWED_EMAIL=you@example.com python3 build.py --firebase   # build/ に配信物とルールを生成
python3 build.py --sample src/sample-data.json   # データ同梱の単体版 index.html（Git には入れない）
```

分析スクリプト（Python 3、`openpyxl` `pandas` `numpy` `scipy` `statsmodels`）:

```bash
python3 analysis/regression.py チームスタッツ.xlsx > analysis/results.txt
```

## 対応フォーマット

2 種類の形式に対応し、どちらも複数ファイルをまとめて読み込めます。

- **データ提供元の書き出し形式**：1 行目が「日付・試合・大会・期間・グループのデータベース・スキーム」と「指標 / 内訳」（例：`パス / 正確`）の見出し。ファイルごとに収録指標が違っていても、読み込み時に自動で MECE に整理します。
  - 行を日付・試合・チームで突き合わせて統合し、複数ファイルにある同じ指標は値を照合して 1 列にまとめる（不一致は記録）
  - 見出しを合計・成功・成功率(%) などの内訳に展開し、名称の揺れをそろえる（例：与えたゴール → 失点、ファール → ファウル）
  - 内訳の和が総数に一致しない指標には算出列を追加（パス方向の「方向分類外」、競り合いの「その他」）
  - 各指標を 6 つの大分類のどれか 1 つに振り分け、基準にない指標は名前のキーワードで分類、分類できなければ「7 その他（未分類）」に入れる
  - 失点と相手のゴールなど、対になる値の不整合を検出して注記に残す
- **追加読み込み**：データ取込の「今のデータに追加して統合」を選ぶと、すでに読み込んだデータに新しいファイルの試合・指標をつなげます（値が食い違う場合は新しいファイルを優先し、注記に記録）。シーズン途中の試合の追加にも使えます。
- **ファイルをまたいだ演算（算出KPI）**：統合後のデータから、決定率・シュート1本あたりxG・xG差・セットプレー起点シュート比率・リカバリー（高）比率・空中戦の割合など 12 指標を計算し、「8 算出指標（KPI）」として概要・試合別・推移比較に表示します。元の指標と二重に数えないよう独立した大分類にしています。
- **整理済みの 4 段見出し形式**：1 シートに、大分類 → 小分類（A 列が「日付」の行）→ 指標名 → 内訳（合計・成功・成功率(%) など）の 4 段見出しがあり、その下に 1 試合につき「自チーム」「対戦相手」の 2 行が並ぶ形式。「平均」で始まる行か空行で終わります。
