# WinB ドキュメント

## 目次

- [architecture.md](architecture.md) — システム構成、データフロー、主要設計判断
- [methodology.md](methodology.md) — 特徴量設計、モデル選定、検証方法（Phase 3 以降で追加予定）
- [data-sources.md](data-sources.md) — データソース一覧、取得ルール（Phase 1 以降で追加予定）

## プロジェクトの目的

Bリーグ B1 の試合勝率を機械学習で予測し、2025-26 シーズンのウォークフォワード検証で的中率 65%+ を達成できるかを確認する。

達成可能なら、2026-27 シーズン以降のリアルタイム予測運用に進む。未達なら、特徴量・モデル・データソースの見直しサイクルに入る。

## 技術スタック

| 層 | 採用技術 |
|---|---|
| 言語 | Python 3.12 |
| コンテナ | Docker + Docker Compose |
| DB | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 + Alembic |
| ML | scikit-learn, XGBoost |
| データ取得 | requests + BeautifulSoup4 |
| 可視化 | matplotlib, seaborn |
| Notebook | Jupyter（dev 依存） |

## セットアップ手順

`../README.md` を参照。

## 環境変数

| 変数名 | 説明 | 必須/任意 |
|---|---|---|
| `POSTGRES_USER` | PostgreSQL ユーザー名 | 必須（.env） |
| `POSTGRES_PASSWORD` | PostgreSQL パスワード | 必須（.env） |
| `POSTGRES_DB` | DB 名 | 必須（.env） |
| `DATABASE_URL` | app コンテナから DB への接続URL | 自動生成（compose 側） |
| `ANTHROPIC_API_KEY` | Claude API キー | 任意（Phase 4 以降） |

値は `.env` に記載し、`.env.example` には記載しない。
