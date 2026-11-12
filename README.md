# Lockscreen Insights

Glance / Unity AuraなどのAndroidロック画面広告に対する公開ユーザーの声を収集する、無料の個人研究向けダッシュボードです。

**サイト:** https://creamtown0420.github.io/lockscreen-voice-monitor/

## ダッシュボード

- ライトテーマ・シンプルなKPI → 時系列 → 話題別集計 → 元投稿の一覧
- 投稿をポジティブ / ネガティブ / 中立 / 判定保留に分類
- 不満の原因を「勝手に有効化」「停止・削除」「広告への不満」「性能・電池」「プライバシー」「コンテンツ」等に分類
- サービス別、情報源別、期間別、感情別、キーワード検索
- ニュース記事は**ユーザーの感情割合から除外**。元投稿は出典をクリックして確認できます。

感情の分類はPythonの無料ローカルライブラリ[VADER](https://github.com/cjhutto/vaderSentiment)＋専用ルールです。無料APIキーは不要です。英語が中心で、皮肉や外国語の判定には限界があります。中立・判定保留を無理にポジティブ／ネガティブへ含めません。

## 情報源と更新

- Reddit: [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) の公開アーカイブ（投稿＋コメント）
- Bluesky: 認証不要の公開検索API
- Hacker News: Algolia検索API
- Google News: RSS（意見とは別カテゴリ）
- Xは使用しません。

GitHub Actionsで毎日**日本時間08:17頃**に収集します。スケジュールはGitHub側で遅れることがあります。

## Redditの過去データ：2022年〜

\`backfill.py\` によって、2022年1月から現在までを**年月×サブレディット×投稿/コメント種別**に分割し、日々段階的に追加します。直近の更新は\`collector.py\`が別に行います。過去データは30日で削除せず保存を継続します。

- バックフィル1回につき最大20検索窓。データ量やタイムアウト次第で完成まで数日〜数週間かかります。
- 先に異なる年の検索窓を試し、年をまたぐ傾向も早めに確認できる構成です。
- 取得元は第三者の無保証アーカイブであり、**欠落・タイムアウト・検索上限に達した範囲**があります。履歴全件の網羅性は保証しません。進捗表示は検索窓の完了数であって、収集済み投稿の割合ではありません。
- サーバーへの過剰な負荷を避けるため、リクエスト間に待機時間を設け、429が来たら打ち切ります。
- 公開された投稿に過度に依存した一般化を避け、指標は**取得したサンプルの内訳**として表示します。

## GitHub Pages設定

Settings → Pages → Build and deployment → Source = **GitHub Actions** に設定します。

Actions → Collect free sources and publish dashboard → Run workflow で手動起動も可能です。

## 開発・テスト

Python 3.10以上、追加依存はVADERのみ（未導入時はドメインルールによる分類のみ）。

\`\`\`bash
python -m pip install vaderSentiment==3.3.2
python -m unittest discover -s tests -v
python collector.py
python backfill.py
mkdir -p app/data
cp data/monitor.json app/data/monitor.json
python -m http.server 8000 --directory app
\`\`\`

- \`collector.py\`：直近の投稿取得・重複排除・スコア付与
- \`sentiment.py\`：ルールとVADERによるトピック・感情分類
- \`backfill.py\`：Redditの段階的な過去投稿の追加
- \`data/monitor.json\`：公開された収集データ
- \`app/\`：静的ダッシュボード
- \`.github/workflows/collect-and-publish.yml\`：収集・テスト・GitHub Pages公開

## データの扱いと公開状態

**GitHub Pagesもこのリポジトリも公開状態です。** URLを秘密にしただけではアクセス制限になりません。GitHub Pagesによるパスワード不要の「秘密のURL」制限は実装されていません。

公開データには投稿の短い抜粋と元投稿リンクを含み、作者名は保存しません。古い抜粋はGit履歴に残る可能性があります。削除要求対応やデータの再利用条件・利用規約の確認などが必要なため、研究・実験用途にとどめ、本格運用前には公開Git履歴へ投稿テキストを残さない方式に移してください。
