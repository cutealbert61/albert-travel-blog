# 亞伯特的生活旅遊日誌 Albert's Travel Journal

每天晚上 7 點(台灣時間)自動產生一篇中英雙語、1500字以上的深度旅遊日誌,搭配真實照片,自動發布到公開網站。

---

## 一、這個系統長什麼樣子

```
albert-travel-blog/
├── .github/workflows/daily-post.yml   ← 每天自動執行的排程
├── data/
│   ├── locations.json    ← 城市 × 主題角度資料庫(你可以自己增加城市)
│   ├── history.json      ← 記錄已寫過的組合,避免重複
│   └── posts.json        ← 所有文章的清單(首頁讀這個)
├── scripts/
│   ├── generate_post.py  ← 核心產文腳本
│   └── post_template.html
├── site/                 ← 這個資料夾就是你的公開網站
│   ├── index.html
│   ├── posts/            ← 每天新增的文章會存在這裡
│   └── assets/
└── admin/                ← 管理後台(下架文章/請求重寫)
    ├── index.html
    ├── admin.js
    └── config.js          ← 只需要改這個檔案一次
```

---

## 二、第一次設定步驟(大約15-20分鐘,做一次就好)

### 步驟 1:建立 GitHub 帳號與新 Repository
1. 到 https://github.com 註冊帳號(如果還沒有)
2. 右上角 `+` → `New repository`
3. Repository name 建議填 `albert-travel-blog`,設為 **Public**(要公開網站必須是 Public,免費版 Pages 才能用)
4. 建立空的 repository 即可,不用勾選任何初始檔案

### 步驟 2:把這個專案上傳上去
在你的電腦打開終端機(或用 GitHub Desktop 這種圖形化工具也可以),在這個資料夾內執行:
```bash
git init
git add .
git commit -m "初始化亞伯特的生活旅遊日誌"
git branch -M main
git remote add origin https://github.com/你的帳號/albert-travel-blog.git
git push -u origin main
```

### 步驟 3:申請 Anthropic API Key(讓機器人會寫文章)
1. 到 https://console.anthropic.com 註冊/登入
2. 左側選單找到 API Keys → Create Key,複製起來(只會顯示一次,先存好)
3. 儲值一點額度(這個用量非常小,一天一篇文章大約台幣1-3元等級,一個月落在幾十元台幣)

### 步驟 4:申請 Unsplash API Key(讓機器人會抓真實照片,完全免費)
1. 到 https://unsplash.com/developers 註冊開發者帳號
2. New Application → 依指示填寫(選「Demo」等級即可,個人使用免費額度足夠一天一篇)
3. 複製 **Access Key**

### 步驟 5:把兩把金鑰放進 GitHub Secrets(安全存放,不會外洩)
1. 到你的 repository 頁面 → `Settings` → 左側 `Secrets and variables` → `Actions`
2. 點 `New repository secret`,新增兩筆:
   - Name: `ANTHROPIC_API_KEY`　Value: 貼上步驟3的金鑰
   - Name: `UNSPLASH_ACCESS_KEY`　Value: 貼上步驟4的金鑰

### 步驟 6:啟用 GitHub Pages(讓網站真正公開上線)
1. `Settings` → 左側 `Pages`
2. Source 選 `Deploy from a branch`
3. Branch 選 `main`,資料夾選 `/site`,按 Save
4. 等 1-2 分鐘,頁面會顯示你的公開網址,格式類似:
   `https://你的帳號.github.io/albert-travel-blog/`

### 步驟 7:設定管理後台
打開 `admin/config.js`,把裡面兩行改成你自己的資料:
```js
GITHUB_OWNER: "你的GitHub帳號",
GITHUB_REPO: "albert-travel-blog",
```
存檔後 commit + push 上去。

管理後台網址會是:`https://你的帳號.github.io/albert-travel-blog/admin/index.html`

要使用管理後台時,需要一把「GitHub Personal Access Token」(只有你自己操作用,不會存在任何地方):
1. GitHub 右上角頭像 → `Settings` → 左側最下面 `Developer settings` → `Personal access tokens` → `Tokens (classic)` → `Generate new token`
2. 勾選 `repo` 權限,設定一個你記得住的到期時間
3. 產生後複製起來,每次要用管理後台時貼上去登入即可(它只存在瀏覽器分頁關閉就消失)

### 步驟 8:手動測試跑一次,確認一切正常
1. 到 repository 頁面 → `Actions` 分頁
2. 左側點 `Daily Travel Post` → 右邊 `Run workflow` → `Run workflow`(不用等到晚上7點,可以馬上手動觸發測試)
3. 等 1-2 分鐘,跑完後重新整理你的網站首頁,應該就會看到第一篇文章了 🎉

之後每天台灣時間晚上 7 點,它就會自動生成新的一篇,不需要你再做任何事。

---

## 三、日常使用

- **想下架某篇文章**:打開管理後台 → 貼 PAT 登入 → 找到那篇 → 按「下架」
- **想要某篇重寫成不同角度**:按「下架並請求重寫」→ 明天自動產生的那篇會換一個新角度重新介紹該城市
- **想增加更多城市或主題角度**:直接編輯 `data/locations.json`,加進去 commit 上去即可,腳本會自動抓最新清單
- **想改變發布時間**:編輯 `.github/workflows/daily-post.yml` 裡的 cron 時間(注意是 UTC 時間,台灣時間要 -8 小時)

---

## 四、我的優化建議(目前先不做,但你之後可以考慮)

1. **RSS 訂閱**:之後可以加一個 `feed.xml`,讓讀者可以訂閱新文章通知,不用一直回來看
2. **搜尋/分類頁**:文章多了之後,首頁可以加上依洲別或主題角度篩選
3. **留言功能**:目前是純靜態網站沒有留言區,若想要可以接第三方留言服務(例如 giscus,免費、基於 GitHub Discussions)
4. **自訂網域**:之後如果想要 `albert-travel.com` 這種自己的網址而不是 github.io,可以買網域後在 Pages 設定裡綁定,我可以再協助設定
5. **管理後台安全性**:目前用「貼上你自己的 PAT」這個最簡單的做法,不需要額外花錢架伺服器;如果之後想要更方便(例如密碼登入不用每次貼權杖),可以加一個免費的 Cloudflare Worker 來處理,我也可以協助升級

如果上面有任何一項你想先做,或設定過程卡住,都可以直接跟我說。
