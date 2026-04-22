# models/

機械学習モデルの学習・推論・保存。

## 責務
- ベースラインモデル（Logistic Regression）
- XGBoost 本体
- Ensemble（Voting、Stacking）
- モデル保存・ロード
- CS 用補正パラメータの適用

## 予定モジュール
- `baseline.py` — ロジスティック回帰
- `xgb.py` — XGBoost 学習・推論
- `ensemble.py` — Voting / Stacking
- `calibration.py` — Isotonic / Platt スケーリング
- `cs_adjustment.py` — CS 用補正（ホームアドバンテージ増、K値低下等）
- `registry.py` — モデルファイル保存・ロード（`models/saved/`）

## 設計ポイント
- **1モデル共通学習 + CS補正**: レギュラー・CS を同一モデルで学習し、CS 用パラメータを後段で適用
- **キャリブレーション必須**: 確率予測の質が大事（Log Loss 最適化）
- **シード固定**: 再現性のため `random_state=42`

## 依存
- scikit-learn, xgboost
