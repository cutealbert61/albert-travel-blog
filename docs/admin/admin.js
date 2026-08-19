const AdminApp = (() => {
  'use strict';
  const cfg = window.ALBERT_BLOG_CONFIG;
  const API = 'https://api.github.com';
  const CONTENT_TYPES = {
    personal: '亞伯特親身旅遊',
    planned: '預定旅程',
    research: '旅遊資料整理',
    inspiration: '靈感收藏'
  };
  const TRAVEL_STATUSES = {
    visited: '已造訪',
    planned: '計畫前往',
    inspiration: '靈感收藏'
  };

  function log(message) {
    const element = document.getElementById('log');
    element.textContent = '[' + new Date().toLocaleTimeString() + '] ' + message + '\n' + element.textContent;
  }
  function escapeHTML(value) {
    return String(value == null ? '' : value).replace(/[&<>'"]/g, (character) => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;'
    })[character]);
  }
  function getToken() { return sessionStorage.getItem('albert_gh_pat'); }
  function login() {
    const value = document.getElementById('pat-input').value.trim();
    if (!value) { alert('請先貼上僅限此儲存庫的 GitHub Fine-grained Personal Access Token'); return; }
    sessionStorage.setItem('albert_gh_pat', value);
    document.getElementById('pat-input').value = '';
    loadPosts();
  }
  function logout() {
    sessionStorage.removeItem('albert_gh_pat');
    document.getElementById('posts-list').innerHTML = '';
    log('已登出，分頁權杖已清除。');
  }
  async function ghGetFile(path) {
    const url = API + '/repos/' + cfg.GITHUB_OWNER + '/' + cfg.GITHUB_REPO + '/contents/' + path + '?ref=' + cfg.BRANCH;
    const response = await fetch(url, {
      headers: { Authorization:'Bearer ' + getToken(), Accept:'application/vnd.github+json' }
    });
    if (!response.ok) throw new Error('讀取 ' + path + ' 失敗 (' + response.status + ')');
    const json = await response.json();
    const content = decodeURIComponent(escape(atob(json.content)));
    return { data:JSON.parse(content), sha:json.sha };
  }
  async function ghPutFile(path, dataObject, sha, message) {
    const content = btoa(unescape(encodeURIComponent(JSON.stringify(dataObject, null, 2))));
    const url = API + '/repos/' + cfg.GITHUB_OWNER + '/' + cfg.GITHUB_REPO + '/contents/' + path;
    const response = await fetch(url, {
      method:'PUT',
      headers: { Authorization:'Bearer ' + getToken(), Accept:'application/vnd.github+json', 'Content-Type':'application/json' },
      body:JSON.stringify({ message, content, sha, branch:cfg.BRANCH })
    });
    if (!response.ok) throw new Error('寫入 ' + path + ' 失敗 (' + response.status + ')');
    return response.json();
  }
  function optionHTML(values, selected) {
    return Object.keys(values).map((key) => '<option value="' + escapeHTML(key) + '"' + (key === selected ? ' selected' : '') + '>' + escapeHTML(values[key]) + '</option>').join('');
  }
  async function loadPosts() {
    try {
      log('正在讀取文章分類資料...');
      const { data:posts } = await ghGetFile('data/posts.json');
      render(posts.sort((a, b) => new Date(b.date) - new Date(a.date)));
      log('已載入 ' + posts.length + ' 篇文章。');
    } catch (error) {
      log('錯誤：' + error.message);
      alert('讀取失敗，請確認權杖僅授權此儲存庫，且 Contents 權限為 Read and write。');
    }
  }
  function render(posts) {
    document.getElementById('posts-list').innerHTML = posts.map((post) => {
      const type = CONTENT_TYPES[post.content_type] ? post.content_type : 'research';
      const travelStatus = TRAVEL_STATUSES[post.travel_status] ? post.travel_status : 'inspiration';
      return '<div class="admin-card">' +
        '<img src="' + escapeHTML(post.cover_image) + '" alt="">' +
        '<div class="meta"><div><strong>' + escapeHTML(post.title_zh) + '</strong> <span class="status ' + escapeHTML(post.status) + '">' + escapeHTML(post.status) + '</span></div>' +
        '<div class="admin-subline">' + escapeHTML(post.date) + ' · ' + escapeHTML(post.city_en) + ' · ' + escapeHTML(post.angle_en) + '</div>' +
        '<div class="classification-row"><label>文章性質<select id="type-' + escapeHTML(post.slug) + '">' + optionHTML(CONTENT_TYPES, type) + '</select></label>' +
        '<label>旅程狀態<select id="travel-' + escapeHTML(post.slug) + '">' + optionHTML(TRAVEL_STATUSES, travelStatus) + '</select></label>' +
        '<button class="btn" onclick="AdminApp.saveClassification(\'' + escapeHTML(post.slug) + '\')">儲存分類</button></div></div>' +
        '<div class="actions"><button class="btn secondary" onclick="AdminApp.unpublish(\'' + escapeHTML(post.slug) + '\')">下架</button>' +
        '<button class="btn danger" onclick="AdminApp.flagForRevision(\'' + escapeHTML(post.slug) + '\')">下架並請求重寫</button></div></div>';
    }).join('');
  }
  async function saveClassification(slug) {
    try {
      const type = document.getElementById('type-' + slug).value;
      const travelStatus = document.getElementById('travel-' + slug).value;
      if (!CONTENT_TYPES[type] || !TRAVEL_STATUSES[travelStatus]) throw new Error('分類值不正確');
      log('正在更新分類：' + slug);
      const [source, published] = await Promise.all([ghGetFile('data/posts.json'), ghGetFile('docs/data/posts.json')]);
      [source.data, published.data].forEach((posts) => {
        const post = posts.find((item) => item.slug === slug);
        if (!post) throw new Error('找不到文章：' + slug);
        post.content_type = type;
        post.travel_status = travelStatus;
      });
      await ghPutFile('data/posts.json', source.data, source.sha, 'admin: 更新文章分類 ' + slug);
      await ghPutFile('docs/data/posts.json', published.data, published.sha, 'admin: 同步網站文章分類 ' + slug);
      log('分類已同步到網站：' + CONTENT_TYPES[type] + '／' + TRAVEL_STATUSES[travelStatus]);
    } catch (error) {
      log('錯誤：' + error.message);
      alert('分類更新失敗：' + error.message);
    }
  }
  async function unpublish(slug, alsoFlag = false) {
    try {
      log('正在下架：' + slug);
      const [source, published] = await Promise.all([ghGetFile('data/posts.json'), ghGetFile('docs/data/posts.json')]);
      [source.data, published.data].forEach((posts) => {
        const post = posts.find((item) => item.slug === slug);
        if (!post) throw new Error('找不到文章：' + slug);
        post.status = 'unpublished';
      });
      await ghPutFile('data/posts.json', source.data, source.sha, 'admin: 下架 ' + slug);
      await ghPutFile('docs/data/posts.json', published.data, published.sha, 'admin: 同步下架 ' + slug);
      if (alsoFlag) {
        const { data:history, sha:historySha } = await ghGetFile('data/history.json');
        const post = source.data.find((item) => item.slug === slug);
        history.priority_queue.push({ city_en:post.city_en, avoid_angle_key:post.angle_key });
        await ghPutFile('data/history.json', history, historySha, 'admin: 請求重新生成 ' + post.city_en);
        log('已下架並排入優先重寫佇列：' + post.city_en);
      } else {
        log('已下架：' + slug);
      }
      loadPosts();
    } catch (error) {
      log('錯誤：' + error.message);
      alert('操作失敗：' + error.message);
    }
  }
  function flagForRevision(slug) { unpublish(slug, true); }
  if (getToken()) loadPosts();
  return { login, logout, loadPosts, saveClassification, unpublish, flagForRevision };
})();
