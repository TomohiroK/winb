# WinB — Claude エージェント向け必読ガイド

**このファイルは winb リポジトリに触るたびに最初に読む。**
作業開始時にざっと目を通してから着手すること。フェーズが進むたびに更新する（末尾「更新ルール」参照）。

---

## 1. 一番最初に意識すること（毎回）

### 🔴 このプロジェクトは Docker ローカル運用専用

- 本番環境・ステージング環境は **存在しない**
- クラウドデプロイも **しない**（個人研究用）
- **全ての実行は Docker Compose 内の `app` コンテナで行う**

```bash
# 基本の作業フロー
docker compose up -d                           # 初回 / 停止後
docker compose ps                              # コンテナの生存確認
docker compose exec -T app pytest -q           # テスト実行
docker compose exec -T app python scripts/...  # スクリプト実行
docker compose exec -T app alembic upgrade head
```

### Docker が落ちていたとき

`Cannot connect to the Docker daemon` → **Docker Desktop が停止中**
- 「デプロイエラー」や「CI エラー」ではない
- ユーザーに **「Docker Desktop を起動してください」** と依頼する
- 勝手に `docker daemon` 系のコマンドを叩かない

### host で Python を直接叩かない

- `pip install`, `pytest`, `python scripts/...` を **ホスト側で実行しない**
- 必ず `docker compose exec -T app ...` 経由
- ホスト側 `python` は混在汚染の元

---

## 2. スタック（現在）

| レイヤ | 採用 |
|---|---|
| OS / ランタイム | macOS (Apple Silicon) + Docker Desktop |
| 言語 | Python 3.12 (slim-bookworm) |
| ORM | SQLAlchemy 2.0 (Mapped[] 型ヒント) |
| DB | PostgreSQL 16-alpine（`db` コンテナ、ホスト側は `:5433` で公開） |
| マイグレーション | Alembic |
| ML | scikit-learn, xgboost（予定、Phase 4〜） |
| スクレイピング | requests + beautifulsoup4 + lxml + tenacity |
| テスト | pytest（全実行は Docker 内） |

## 3. ディレクトリ構成（現在）

```
winb/
├── CLAUDE.md                          ← 👈 このファイル（最初に読む）
├── README.md
├── docker-compose.yml                  ← app + db の2サービス
├── docker/app/Dockerfile
├── pyproject.toml                      ← コンテナに ro マウント
├── alembic.ini                         ← コンテナに ro マウント（URL は env から注入）
├── alembic/
│   ├── env.py                          ← winb.data.Base.metadata を import
│   └── versions/                       ← マイグレーションファイル
├── src/winb/
│   ├── scraper/
│   │   ├── client.py                   ← BleagueClient（レート制御+キャッシュ）
│   │   └── bleague.py                  ← parse_schedule / club_detail / roster_detail / game_info
│   ├── data/
│   │   ├── database.py                 ← get_engine, session_scope
│   │   ├── models.py                   ← 9テーブル ORM 定義
│   │   └── adapters.py                 ← upsert_* + persist_club_detail
│   ├── features/  (未実装, Phase 2)
│   ├── models/    (未実装, Phase 3)
│   ├── evaluation/(未実装, Phase 4)
│   └── pipeline/  (未実装)
├── scripts/
│   ├── check_db.py                     ← DB 接続確認
│   └── inspect_html*.py                ← HTML 構造調査
├── tests/
│   ├── conftest.py                     ← 共通 session fixture
│   ├── fixtures/bleague/               ← 実 HTML 4ファイル（パーサーテスト用）
│   └── test_*.py
├── docs/
│   ├── README.md
│   ├── architecture.md
│   └── data-sources.md
└── data/         ← ローカル出力（.gitignore 対象）
    └── cache/    ← スクレイパーの HTML キャッシュ
```

---

## 4. よく使うコマンド（丸暗記）

```bash
# コンテナ起動 / 停止
docker compose up -d
docker compose down            # ボリュームは残す
docker compose down -v         # DBも含めて全削除（！注意！）

# シェル
docker compose exec app bash

# テスト
docker compose exec -T app pytest -q
docker compose exec -T app pytest tests/test_scraper_bleague.py -v

# DB 確認
docker compose exec -T app python scripts/check_db.py
docker compose exec -T db psql -U winb -d winb -c '\dt'

# Alembic
docker compose exec -T app alembic revision --autogenerate -m "msg"
docker compose exec -T app alembic upgrade head
docker compose exec -T app alembic downgrade -1
docker compose exec -T app alembic history

# スクレイパー実行 / 構造調査
docker compose exec -T app python scripts/inspect_html.py
```

---

## 5. データソースのルール

- 取得先: **bleague.jp のみ**（個人研究・非商用・頒布なし）
- 最小アクセス間隔: **10 秒**（`.env` の `SCRAPER_MIN_INTERVAL_SEC`）
- User-Agent: `WinB-ResearchBot/0.1 (personal research; contact: ...)`
- 取得結果は `data/cache/` にローカル永続化（ディスクには載るが Git には載らない）
- 詳細ルール: `docs/data-sources.md`
- 停止要請があれば即止める

### JS 動的レンダリングが必要なページ（対応未実装）

| 用途 | URL | 対応策（Phase 2 以降） |
|---|---|---|
| ボックススコア | `/game_detail/?ScheduleKey=X&tab=4` | Playwright or XHR API 特定 |
| 選手別ランキング | `/stats/` | 同上（優先度低、club_detail で代替可能） |

---

## 6. スキーマの現在（重要な設計判断）

### 自然キー
- `teams.team_id`: bleague.jp 由来（3桁、Integer）
- `players.player_id`: bleague.jp 由来（**8-10桁、BigInteger**）
  - 過去: Integer（32-bit）で上限超え事故 → 2026-04-24 修正済み
- `games.schedule_key`: bleague.jp 由来（6桁、String）

### 外国籍選手の3年以内データのみ採用（Phase 2 実装予定）
- 特徴量抽出時に `game_date - timedelta(days=365*3)` でカット
- DB スキーマ自体は切らない（生データは持っておく）

### 日本人選手の年齢ピーク曲線（Phase 2 実装予定）
- ポジション別ピーク年齢をコード側に持つ
- RosterSeasonStat ＋ Player.birth_date + positions で計算

### CS（チャンピオンシップ）は1モデル + 補正
- 別テーブルにはしない
- `games.is_cs` フラグ + モデル側で補正パラメータ適用

---

## 7. Phase 進捗

| Phase | 内容 | 状態 |
|---|---|---|
| 0 | 規約確認・プロジェクト初期化 | ✅ |
| 1a | スクレイパー HTTP クライアント（`scraper/client.py`） | ✅ |
| 1b | 4 パーサー（`scraper/bleague.py`） | ✅ |
| 1c | ORM 9 テーブル + Alembic（`data/models.py`） | ✅ |
| 1d | パーサー→ORM アダプター（`data/adapters.py`） | ✅ |
| **1e** | **2025-26 シーズンの試験取得（1月分 → シーズン全体）** | ⏳ **次**|
| 2 | 特徴量エンジニアリング（Four Factors, ELO, 疲労, 年齢ピーク） | ⬜ |
| 3 | ベースラインモデル（XGBoost） | ⬜ |
| 4 | ウォークフォワード検証（2025-26 シーズン丸ごと） | ⬜ |
| 5 | 精度レポート（セグメント分析 / キャリブレーション） | ⬜ |

---

## 8. テスト状況（直近）

```
80 passed, 1 skipped  (2026-04-24)
- scraper.client:   17
- scraper.bleague:  32
- data.models:      11
- data.adapters:    18
- smoke:             2
- integration:       1 (skipped)
```

**テストは全て Docker 内で実行**。`tests/conftest.py` の `session` fixture が PostgreSQL と transaction rollback を使う。

---

## 9. ルール（作業時の原則）

### コミット
- メッセージ 1行目は **英語・命令形・50字以内**
- 本文で「なぜ」を説明
- 1機能 = 1コミット
- `.env` 等のクレデンシャルは絶対にコミットしない（`.gitignore` 済み）

### ローカル検証 → push の順序（永久ルール）
- `docker compose exec app pytest -q` が通ってから commit
- 通ってから push
- これを破るとユーザーに怒られる（過去実績あり）

### 小さく進める
- 1つ実装→テスト→コミット→push を回す
- 大規模変更を 1 コミットに詰め込まない

### パーサーの HTML fixture
- 実 HTML は `tests/fixtures/bleague/` に保存（Git 管理）
- 1.5MB 程度、個人研究範囲で合理的

---

## 10. 更新ルール（このファイルの運用）

**フェーズを終えるたび、または重要な設計判断が入るたびに、このファイルを更新する。**

更新タイミング:
- ✅ 新しいモジュール（`src/winb/*`）を追加したとき → Section 3 / 6 / 7 を更新
- ✅ DB スキーマを変えたとき → Section 6 を更新
- ✅ テスト件数や Phase 進捗が変わったとき → Section 7 / 8 を更新
- ✅ 運用の鉄則が判明したとき → Section 9 に追記
- ✅ ユーザーから指摘を受けた恒久的なルール → Section 1 または 9 に明記

迷ったら書いておく。次の自分（= 次のセッションの Claude）が一瞬で状況把握できる状態を保つ。
