# data/

DB モデル定義と ETL（Extract / Transform / Load）ロジック。

## 責務
- SQLAlchemy モデル定義（`teams`, `games`, `players`, `box_scores`, `rosters`, `injuries` 等）
- Alembic マイグレーション管理
- スクレイピング結果を DB に投入するローダー
- DB からのクエリユーティリティ

## 予定モジュール
- `models.py` — SQLAlchemy ORM モデル
- `database.py` — エンジン生成、セッション管理
- `repository.py` — CRUD ラッパー（チーム取得、試合取得等）
- `migrations/` — Alembic マイグレーション

## テーブル設計方針
- 試合データは「イベント型」で保存（1試合 = 1レコード、両チームのスタッツを横に展開）
- 選手データは `players` と試合ごとの `box_scores` を分離
- ロスター（誰がその試合に出られたか）は試合単位で記録

## 依存
- sqlalchemy>=2.0, psycopg2-binary, alembic
