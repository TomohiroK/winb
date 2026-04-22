# データソース

Bリーグ公式サイト（`bleague.jp`）のページ構造調査結果と、WinB プロジェクトで利用するデータ取得戦略。

調査日: 2026-04-22
調査対象: B1 2025-26 シーズン

---

## 1. 規約・運用方針

| 項目 | 状態 |
|---|---|
| robots.txt | 一般クローラー制限なし（SEO系ボットのみ Disallow） |
| 利用規約 | 直接的な規約ページは発見できず |
| プライバシーポリシー | `https://www.bleague.jp/privacy/` 存在、スクレイピング明示禁止なし |
| 採用方針 | 個人研究・非商用・控えめなアクセスで進める（B 方針） |

### 運用ルール
- **最小アクセス間隔**: 10秒以上（`SCRAPER_MIN_INTERVAL_SEC=10`）
- **実行時間帯**: 深夜帯（JST 02:00〜05:00）を優先
- **User-Agent**: アプリ名 + 連絡手段を明示
- **キャッシュ**: 取得済み HTML は `data/cache/` に保存、同日中は再取得しない
- **停止要請対応**: Bリーグ公式から要請があれば即時停止

---

## 2. URL 構造とデータ取得可否

### 2.1 静的HTML（requests + BeautifulSoup で取得可能）

| URL | 取得可能データ |
|---|---|
| `/schedule/?tab=1&year=YYYY&mon=MM` | 日程一覧、ScheduleKey、会場、時刻、カード |
| `/schedule/?tab=1&club=XXX` | チーム別日程 |
| `/schedule/?tab=1&year=YYYY&mon=MM&event=...` | 大会種別フィルタ（B1リーグ、CS等） |
| `/club_detail/?TeamID=XXX` | チーム詳細、ロスター、シーズン成績、チームスタッツ |
| `/roster_detail/?PlayerID=XXX` | 選手詳細（生年月日、身長、体重、ポジション、国籍、今季スタッツ） |
| `/record/?club1=XXX&club2=YYY` | チーム対戦成績（H2H） |
| `/game_detail/?ScheduleKey=XXX&tab=1` | 試合情報（カード、時刻、会場） |
| `/standings/` | 順位表（未確認、静的の想定） |
| `/leaders/` | 成績トップ（未確認） |
| `/career_stats/` | 通算成績（未確認） |

### 2.2 JavaScript 動的読み込み（Playwright 等が必要）

| URL | データ | 対策 |
|---|---|---|
| `/game_detail/?ScheduleKey=XXX&tab=4` | ボックススコア（選手ごとの試合スタッツ、クォータースコア） | Playwright、または XHR API を特定 |
| `/stats/` | リーグ全体のランキング（選手別・チーム別） | 同上（但し `club_detail` で代替可能） |
| ショットチャート | 各試合のシュート位置データ | 同上。本プロジェクトでは優先度低 |

---

## 3. 主要クエリパラメータ

| パラメータ | 用途 | 値の例 |
|---|---|---|
| `ScheduleKey` | 試合ID | `505443` 等の6桁 |
| `TeamID` | チームID | `692` (仙台), `745` (越谷) |
| `PlayerID` | 選手ID | `51000531` (ジャレット・カルバー) |
| `tab` | 試合詳細タブ | `1`=情報, `2`=レポート, `3`=速報, `4`=ボックススコア |
| `year` | シーズン年 | `2025`, `2024` |
| `mon` | 月 | `04`, `05`（2桁） |
| `club` | チームフィルタ | 2文字コード（`SE`=仙台, `AN`=秋田 等） |
| `event` | 大会種別 | B1リーグ、CS、オールスター 等 |
| `club1` / `club2` | 対戦相手 | TeamID の数値 |

---

## 4. 取得対象データの役割マップ

| データ種別 | 取得元URL | 特徴量への用途 |
|---|---|---|
| 試合結果（スコア） | `/schedule/` または `/game_detail/?tab=1` | HOME_WIN ラベル、ELO 更新 |
| チームスタッツ（シーズン累計） | `/club_detail/` | Four Factors 基礎、直近N試合集計の母数 |
| 試合ごとチームスタッツ | `/game_detail/?tab=4`（JS） | 直近10試合ローリング |
| 選手ごと試合スタッツ（ボックススコア） | `/game_detail/?tab=4`（JS） | 出場時間加重集計、欠場判定 |
| 選手プロフィール（年齢・国籍） | `/roster_detail/` | 年齢ピーク、外国籍3年フィルタ |
| ロスター | `/club_detail/` | チーム構成、新加入外国籍識別 |
| H2H | `/record/?club1=X&club2=Y` | H2H 勝率、H2H 得点差 |

---

## 5. スクレイピング戦略

### 2段階アプローチ

**Stage 1（Phase 1 で実装）**: 静的HTML取得
- `requests` + `BeautifulSoup` + `lxml`
- 対象: 日程、チーム、選手、順位、H2H
- シンプルで高速、保守性高い

**Stage 2（Phase 1 後半 or Phase 2 で実装）**: JS動的HTML取得
- `Playwright`（Chromium ヘッドレス）
- 対象: ボックススコア、ショットチャート、リーグランキング
- Docker イメージに Playwright を追加（イメージサイズ +200MB 程度）

### 優先順位
1. **最優先**: 日程 + 試合結果（スコア） → これだけで ELO と勝敗ラベルは揃う
2. **次優先**: チームスタッツ、選手プロフィール（静的HTML）
3. **後回し**: ボックススコア詳細（JS必要）、ショットチャート

---

## 6. チーム略称マップ（推定、要検証）

`/schedule/?club=SE` のような 2文字コード。`club_detail` の TeamID とのマッピング表を `teams` テーブルに持つ。

| 略称 | チーム名 | TeamID（要調査） |
|---|---|---|
| SE | 仙台89ERS | 692 |
| AN | 秋田ノーザンハピネッツ | (TBD) |
| KY | 越谷アルファーズ | 745 |
| ... | ... | ... |

完全なマッピングは Phase 1 で `/club_detail/` を全チーム取得して構築する。

---

## 7. 発見したリスクと課題

| # | 課題 | 影響 | 対策 |
|---|---|---|---|
| 1 | ボックススコア取得に JS レンダリング必須 | 選手ごとスタッツ取得が複雑化 | Playwright 導入、または XHR API の特定 |
| 2 | B1/B2 の URL 切り替えが不明確（JS制御の可能性） | B1 のみ絞り込みが難しい | `event` パラメータの検証 or HTML class で判別 |
| 3 | 過去シーズン取得は UI 操作が必要 | 過去5-7シーズンの取得に手間 | `year` パラメータが実際に機能するか検証 |
| 4 | 利用規約が直接見つからない | 法的グレーゾーン | アクセス頻度を抑制、問題発生時は即停止 |
| 5 | sitemap.xml が gz 圧縮 | URL 全量把握が困難 | 解凍して解析（優先度低） |

---

## 8. 次のステップ（Phase 1 着手時）

1. `scraper/client.py` — HTTP クライアント（User-Agent、間隔制御、リトライ、キャッシュ）
2. `scraper/bleague.py` — 各ページのパーサー
   - `parse_schedule()` — 日程一覧
   - `parse_club_detail()` — チームページ
   - `parse_roster_detail()` — 選手ページ
   - `parse_game_info()` — 試合情報（tab=1）
3. チームID・選手IDマスタの構築
4. 2025-26 シーズンの試合データを試験取得（小規模）
5. JS レンダリング部分は Playwright 追加検討

---

## 9. 発見 URL の網羅リスト

### トップレベル
- `https://www.bleague.jp/`
- `https://www.bleague.jp/schedule/`
- `https://www.bleague.jp/stats/`
- `https://www.bleague.jp/standings/`
- `https://www.bleague.jp/leaders/`
- `https://www.bleague.jp/record/`
- `https://www.bleague.jp/career_stats/`
- `https://www.bleague.jp/glossary/`
- `https://www.bleague.jp/privacy/`

### 詳細ページ
- `https://www.bleague.jp/game_detail/?ScheduleKey=XXX&tab=[1-4]`
- `https://www.bleague.jp/club_detail/?TeamID=XXX`
- `https://www.bleague.jp/roster_detail/?PlayerID=XXX`

### 外部
- `https://www.bleague.jp/robots.txt`
- `https://www.bleague.jp/sitemap.xml` (gz圧縮)
