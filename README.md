# WinB

B.LEAGUE（B1）の試合勝率を機械学習で予測するシステム。

## 概要

- **対象**: Bリーグ B1 レギュラーシーズン + チャンピオンシップ（CS）
- **予測タイミング**: 試合数時間前（スタメン・欠場情報反映後）
- **初期目標**: 2025-26 シーズン全試合でウォークフォワード検証し、的中率 65%+ を達成できるか確認
- **技術スタック**: Python 3.12 / Docker / PostgreSQL 16 / XGBoost / scikit-learn

## セットアップ

### 前提
- Docker Desktop（Mac）
- Git

### 起動

```bash
# .env を作成
cp .env.example .env
# POSTGRES_PASSWORD などを編集

# コンテナ起動
docker compose up -d

# DB 接続確認
docker compose exec app python scripts/check_db.py
```

### シェルに入る

```bash
docker compose exec app bash
```

## ディレクトリ構成

| ディレクトリ | 役割 |
|---|---|
| `src/winb/scraper/` | bleague.jp 等からのデータ取得 |
| `src/winb/data/` | DB モデル定義、ETL |
| `src/winb/features/` | 特徴量エンジニアリング（Four Factors, ELO, 疲労, 年齢ピーク等） |
| `src/winb/models/` | ML モデル（XGBoost, Ensemble 等） |
| `src/winb/evaluation/` | ウォークフォワード検証、精度レポート |
| `src/winb/pipeline/` | ETL → 特徴量 → 予測のパイプライン |
| `docker/` | Dockerfile |
| `docs/` | 設計・運用ドキュメント |
| `notebooks/` | 実験・可視化用 Jupyter notebook |
| `scripts/` | 運用スクリプト（動作確認、定期実行等） |
| `data/` | ローカル生データ・加工データ（Git管理外） |
| `models/saved/` | 学習済みモデル保存（Git管理外） |
| `logs/` | 実行ログ（Git管理外） |

## プロジェクトフェーズ

| Phase | 内容 | 状態 |
|---|---|---|
| 0 | 規約確認 + プロジェクト初期化 | 🟡 進行中 |
| 1 | bleague.jp スクレイピング基盤 | ⚪ 未着手 |
| 2 | 過去7シーズン分のデータ収集 | ⚪ 未着手 |
| 3 | 特徴量エンジニアリング | ⚪ 未着手 |
| 4 | ベースライン XGBoost 構築 | ⚪ 未着手 |
| 5 | ウォークフォワード検証（2025-26） | ⚪ 未着手 |
| 6 | 精度レポート + 改善判断 | ⚪ 未着手 |

## 利用上の注意

- 本プロジェクトは**個人研究・非商用**の学習目的です（コードは public で公開していますが、商用利用は想定していません）
- データ取得は Bリーグ公式サイトに**負荷をかけない範囲**で実施（crawl-delay 遵守、キャッシュ活用、深夜帯実行）
- スクレイピングしたデータや学習済みモデルの配布は行いません（`data/`・`models/saved/` は Git 管理外）
- Bリーグ公式から停止要請があった場合は即時対応します

## ライセンス

Personal research project. 個人研究目的で公開。商用利用・データ再配布はご遠慮ください。

---

詳細は [`docs/README.md`](docs/README.md) を参照。
