# features/

特徴量エンジニアリング。試合データと選手データからモデル入力特徴量を生成する。

## 責務
- チーム単位特徴量（Four Factors、ELO、直近N試合平均等）
- 選手単位特徴量（年齢ピークスコア、出場時間加重）
- チーム集約（主力の出場時間加重平均）
- 疲労・連戦・ホーム/アウェイ特徴量
- CS 固有特徴量（シリーズ戦績、eliminate game）

## 予定モジュール
- `four_factors.py` — Dean Oliver's Four Factors（eFG%, TOV%, ORB%, FT Rate）
- `elo.py` — Bリーグ版 ELO（K=20、ホームアドバンテージ +100、シーズン間 regression）
- `rolling.py` — 直近N試合のローリング平均
- `fatigue.py` — B2B、3-in-4、rest days、連戦
- `roster.py` — 選手集約（年齢ピーク、外国籍安定度）
- `age_peak.py` — ポジション別の年齢ピーク曲線
- `cs_features.py` — CS シリーズ特徴量

## 設計ポイント
- **時系列リーク禁止**: 試合 N の特徴量は N-1 以前のデータのみで計算
- **外国籍は3年以内**: `player_stats_cutoff = game_date - timedelta(days=365*3)`
- **年齢ピーク**: 日本人選手のみ適用。ポジション別にカーブを変える

## 依存
- pandas, numpy
