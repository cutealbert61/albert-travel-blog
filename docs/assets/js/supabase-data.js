'use strict';
(function() {
  const config = window.ALBERT_BLOG_SUPABASE;
  if (!config) throw new Error('Supabase 設定尚未載入');

  async function getDocument(key) {
    const query = new URLSearchParams({ key: 'eq.' + key, select: 'payload,updated_at' });
    const response = await fetch(config.url + '/rest/v1/travel_blog_documents?' + query.toString(), {
      headers: { apikey: config.publishableKey },
      cache: 'no-store'
    });
    if (!response.ok) throw new Error('Supabase 資料讀取失敗 (' + response.status + ')');
    const rows = await response.json();
    if (!rows.length) throw new Error('找不到資料：' + key);
    return rows[0].payload;
  }

  window.ALBERT_BLOG_DATA = Object.freeze({ getDocument });
})();
