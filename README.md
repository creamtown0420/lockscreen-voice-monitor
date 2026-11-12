# Lockscreen Monitor

**ダッシュボード：** https://creamtown0420.github.io/lockscreen-voice-monitor/

Glance / Unity Auraなどのロック画面広告に関する公開投稿を、無料の情報源から自動収集する個人向けの分析ダッシュボードです。

## 画面と集計

- サイドバー、4つのKPI（総数・ポジ・ネガ・中立/保留）、時系列、感情構成比、取得元内訳、投稿検索テーブルというシンプルな構成
- 期間・サービス・情報源・感情で絞り込み。閲覧中も30分ごと、タブ復帰時にデータを読み直します
- ニュースは別表示で、ユーザー投稿の感情割合には含めません
- 感情の割合は「取得できたユーザー投稿」を分母とします。世論調査や全ユーザーの満足度ではありません

## VADERによる無料の感情分析

sentiment.py は、SNS向けの無料辞書・ルールベースライブラリ VADER 3.3.2 と独自のルールで、肯定・否定・中立・判定保留を推定します。VADERは生成AIではありません。

- VADERの compound は −1〜+1。明確な独自キーワードがなければ、現在は −0.45以下を否定、+0.55以上を肯定に分類
- hate、annoying、re-enableなど独自ルールで不満表現を追加
- サポートの定型返信やスマホ本体への肯定評価を、Glanceへの肯定的意見と誤認しないよう補正
- 英語以外、皮肉、長文の文脈判断などに限界があります。投稿の評価は必ず元投稿で確認できます

## 毎日の自動収集

情報源は Reddit（Arctic Shift）、Bluesky、Hacker News、Google News RSS。Xは使用しません。

GitHub Actionsが毎日**日本時間08:17頃**に、新着取得 → VADER分類 → 過去データ追加 → 重複排除と保存 → Pages公開を実行します。時刻の遅れ・スキップはGitHub側の仕様です。Actionsから手動実行もできます。

## 2022年以降のReddit履歴

backfill.pyは年月・subreddit・投稿/コメント別の検索範囲で過去データを追加し、1回につき最大20検索範囲を処理します。

- 結果が上限件数に達した検索範囲は**収集完了とみなさず**、次回の取得開始時刻（checkpoint）を記録して翌日以降に続きを取得
- 過去バージョンで誤って完了扱いにした上限到達範囲も再開対象に戻す
- 期限で投稿を削除せず、IDで重複排除。検索失敗時は再試行対象として残し、HTTP 429ならその日の履歴検索を停止
- アーカイブのクエリが遅い場合は、投稿の日時指定検索に切り替えてPython側で絞り込む
- 検索完了を示す進捗は**Reddit全投稿の取得率ではありません**。アーカイブの欠落、検索タイムアウト、同じ秒に投稿されたデータの取りこぼしは残り得ます

## 開発・動作確認

Python 3.10以降。追加パッケージは vaderSentiment 3.3.2 です。ローカルでは以下を実行します。

    python -m pip install vaderSentiment==3.3.2
    python -m unittest discover -s tests -v
    python collector.py
    python backfill.py
    mkdir -p app/data
    cp data/monitor.json app/data/monitor.json
    python -m http.server 8000 --directory app

主要ファイル：collector.py（新着）、sentiment.py（分類）、backfill.py（履歴）、data/monitor.json（データと進捗）、app/（表示）、.github/workflows/collect-and-publish.yml（日次実行）。

**重要：GitHub Pagesおよびリポジトリは公開です。** 秘密のURLによるアクセス制限はまだ実装していません。データの抜粋はGit履歴に残るため、削除要求や再利用条件への対応が必要です。
