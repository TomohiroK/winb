# pipeline/

スクレイピング → 特徴量生成 → 学習 → 予測 の統合パイプライン。

## 責務
- 各段階のオーケストレーション
- 冪等な実行（何度流しても結果が同じ）
- 失敗時のリトライ・再開
- ログ出力

## 予定モジュール
- `daily_update.py` — 日次データ更新（前日の試合結果取得・DB投入）
- `weekly_retrain.py` — 週次再学習パイプライン
- `predict_slate.py` — 本日の試合予測
- `backfill.py` — 過去シーズン一括取得

## 実行例（将来）
```bash
# 過去シーズン取得
docker compose exec app python -m winb.pipeline.backfill --seasons 2018-19,2021-22,2022-23,2023-24,2024-25

# 日次更新
docker compose exec app python -m winb.pipeline.daily_update

# 本日の予測
docker compose exec app python -m winb.pipeline.predict_slate --date 2026-04-22
```

## 依存
- 他の winb サブパッケージ全般
