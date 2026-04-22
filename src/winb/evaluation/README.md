# evaluation/

モデルの精度検証とレポート生成。

## 責務
- ウォークフォワード検証（時系列データリーク防止）
- 精度指標の算出（Accuracy, Log Loss, Brier Score, Calibration Error）
- セグメント別分析（レギュラー vs CS、確信度帯別、時期別）
- 月次レポート生成
- 外した試合の特徴抽出（改善材料）

## 予定モジュール
- `walk_forward.py` — 週次再学習でのウォークフォワード検証
- `metrics.py` — 精度指標の計算
- `calibration_report.py` — キャリブレーション分析
- `segment_analysis.py` — セグメント別精度
- `miss_analysis.py` — 外した試合の要因分析
- `report.py` — レポート生成（Markdown / HTML）

## 2025-26 シーズン検証の設計
- **訓練期間**: 2018-19 〜 2024-25（5-6 シーズン分、COVID 影響年は要検討）
- **検証期間**: 2025-26 全試合（レギュラー + CS）
- **再学習頻度**: 週次（毎週月曜朝に再学習 → その週の試合を予測）
- **リーク防止**: 予測対象試合より前のデータのみ使用

## 目標指標
| 指標 | 目標 |
|---|---|
| Accuracy（レギュラー） | 65%+ |
| Accuracy（CS） | 55%+ |
| Log Loss | 0.60 以下 |
| Calibration Error | 5% 以下 |

## 依存
- scikit-learn（metrics）、pandas、matplotlib（可視化）
