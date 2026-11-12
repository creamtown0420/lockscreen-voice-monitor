# Lock Screen Signals

無料でアクセス可能な公開情報源から、Glance / Unity Aura / Androidロック画面広告への反応を1日1回収集し、静的ダッシュボードに表示する個人向けプロトタイプです。

## データ取得元

- **Reddit**：第三者アーカイブ [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) の公開APIから、対象subredditの投稿とコメントを検索（遅延・欠落やタイムアウトあり）。
- **Bluesky**：公開検索API。
- **Hacker News**：Algolia検索API。
- **Google News RSS**：ニュース見出し（ユーザーの意見とは別集計）。
- **X**：対象外。課金API・Xログイン情報は使用しません。

**AIによるポジネガ判定は未実装**です。投稿の発見件数は世論調査やユーザー全体の満足度を表しません。

## GitHub Pagesで公開する

1. このリポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** に変更します。
2. **Actions → Collect free sources and publish dashboard → Run workflow** から初回実行します。
3. 成功すると `https://creamtown0420.github.io/lockscreen-voice-monitor/` に公開されます。
4. 以降、毎日 **日本時間08:17頃** に自動実行します。GitHub Actionsは遅延・スキップすることがあります。

公開設定を有効にするまでは、PagesのURLがまだ表示されない可能性があります。

## 手元で動かす

Python 3.10以降・追加パッケージ不要です。

```bash
python -m unittest discover -s tests -v
python collector.py
mkdir -p app/data
cp data/monitor.json app/data/monitor.json
python -m http.server 8000 --directory app
```

Redditを一時無効化する場合は環境変数 `LOCKSCREEN_REDDIT_ENABLED=0` を設定してください。

## 収集と保存の注意事項

- 投稿IDに基づいて重複排除し、サイトでは短い抜粋と元投稿へのリンクを表示します。ユーザー名は保存しません。
- アクティブなJSON内の投稿データは初回取得から30日を超えると削除します。ただしGitHubの**公開Git履歴に古い抜粋が残る**ため、この版には削除済み投稿への対応などの課題があります。個人の実験用プロトタイプとして扱い、本格利用前にはGitに投稿テキストを保存しない設計へ移行してください。
- Arctic Shiftは独立した無保証のアーカイブで、利用規約・データの再公開・削除要請などへの対応が必要です。無料でアクセスできることは、すべての再利用を許可する意味ではありません。
- 一部の情報源だけ失敗した場合はほかの収集を続行し、エラー情報を保存します。全情報源の取得に失敗したときは既存データを保持してジョブを失敗させます。
- GitHub Actionsの定期実行は公開リポジトリで長期間アクティビティがないと自動停止する場合があります。

## ファイル構成

- `collector.py`：情報源の取得・関連性判定・重複除去・集計
- `data/monitor.json`：蓄積データと実行状況
- `app/`：HTML/CSS/JavaScriptによる静的ダッシュボード
- `.github/workflows/collect-and-publish.yml`：日次収集とPages公開
- `tests/`：オフライン単体テスト

参考：[GitHub Pages公式ガイド](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) / [Reddit Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy)
