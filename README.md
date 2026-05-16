# 提示詞 · GPT Image 2 Prompt Library

精選 **176 則** GPT Image 2 / ChatGPT 生圖提示詞，繁體中文整理，依用途分章，一鍵複製。

🌐 <https://prompts.aqualux.dev>

## 用法

```bash
# 本地預覽
python3 -m http.server 8765

# 改資料後重建
python3 build.py
```

## 結構

| 檔案 | 用途 |
|---|---|
| `index.html` | 產出網頁，**`build.py` 自動產生，不要手改** |
| `template.html` | 樣式 / 結構模板（手改這個） |
| `build.py` | 把 `prompts.json` + `template.html` 拼成 `index.html` |
| `prompts.json` | 176 則 prompts，11 個分類 |
| `favicon.svg` / `og-image.png` | 站點圖示 |
| `_screenshots/` | 設計 review 階段的 4 風格截圖（archive） |
| `demo-*/` | 設計 review 階段的 4 風格 demo（archive） |
| `_sample-data.json` | 設計 review 階段用的 18 則 sample（archive） |

## 部署

Netlify 接 GitHub repo，每次 `git push` 自動部署。

```bash
# 改完 prompts.json 後
python3 build.py
git add . && git commit -m "..." && git push
```

## 來源

- [YouMind awesome-gpt-image-2](https://github.com/YouMind-OpenLab/awesome-gpt-image-2) (CC BY 4.0)
- [bnext 90908](https://www.bnext.com.tw/article/90908/chatgpt-image-2-prompt-guide-complete)

設計風格：無印良品 / Kenya Hara 東方極簡 — 襯線標題、漢字章節編號、紙色 prompt 卡、單一柔灰藍 accent。

## License

Code: MIT · Prompts: CC BY 4.0（保留原始來源歸屬）
