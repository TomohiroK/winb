# scraper/

B.LEAGUE 公式サイト等からのデータ取得モジュール。

## 責務
- bleague.jp の試合日程・スタッツ・選手ページのスクレイピング
- 各チーム公式サイトのプレスリリース取得
- スクレイピング頻度制御（Crawl-delay 遵守、キャッシュ）

## 予定モジュール
- `client.py` — HTTP クライアント（User-Agent、間隔制御、リトライ）
- `bleague.py` — bleague.jp パーサー
- `teams.py` — チーム公式サイトパーサー
- `cache.py` — ローカル HTML キャッシュ管理

## 運用ルール
- **最小アクセス間隔**: 10秒（`.env` の `SCRAPER_MIN_INTERVAL_SEC` で調整可）
- **実行時間帯**: 深夜帯（日本時間 02:00〜05:00）推奨
- **User-Agent**: アプリ名 + 連絡先を明示
- **キャッシュ**: 一度取得したページは `data/cache/` に保存、同日中は再取得しない

## 依存
- requests, beautifulsoup4, lxml, tenacity（リトライ）
