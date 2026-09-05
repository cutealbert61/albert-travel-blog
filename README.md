# 亞伯特的生活旅遊日誌

公開網站：<https://cutealbert61.github.io/albert-travel-blog/>

## 儲存原則

- GitHub Pages 只保留 HTML、CSS、JavaScript、RSS、Sitemap 與網站產生程式。
- Supabase Database 是文章清單、城市、分類、歷史紀錄、每週計畫與網站主題的唯一資料來源。
- Supabase Storage 的 `travel-blog-media` 保存公開文章圖片。
- Supabase Storage 的 `travel-blog-backups` 私密保存每次發布版本。
- 本專案不使用 GPT Sites。

## 自動發布

每日排程會：

1. 從 Supabase 讀取文章資料與產生紀錄。
2. 產生新文章並把 Unsplash 圖片轉存至 Supabase。
3. 將文章資料寫回 Supabase。
4. 只把新產生的靜態文章頁提交到 GitHub Pages。
5. 把該次 GitHub 版本壓縮備份至 Supabase 私人儲存空間。

GitHub Actions 需要以下 Repository Secrets：

- `ANTHROPIC_API_KEY`
- `UNSPLASH_ACCESS_KEY`
- `TRAVEL_BLOG_WRITE_TOKEN`
- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`

## 管理後台

管理後台：<https://cutealbert61.github.io/albert-travel-blog/admin/>

登入連結只會寄到 `cutealbert61@gmail.com`。登入後可修改文章分類、下架文章或排入重新產生佇列，所有變更均直接寫入 Supabase，不再使用 GitHub Personal Access Token。

## Supabase 資源

- Database tables
  - `travel_blog_documents`
  - `travel_blog_media`
  - `travel_blog_releases`
- Storage buckets
  - `travel-blog-media`：公開讀取，管理員或受保護的發布流程可寫入。
  - `travel-blog-backups`：私人備份，僅管理員可存取。
- Edge Function
  - `travel-blog-admin`：供 GitHub Actions 進行受權限保護的資料、圖片與備份寫入。

所有公開資料表均啟用 Row Level Security。瀏覽器只使用 Supabase publishable key；高權限金鑰不會放進 GitHub Pages。
