const AdminApp = (() => {
  'use strict';
  const config = window.ALBERT_BLOG_SUPABASE;
  const client = window.supabase.createClient(config.url, config.publishableKey);
  const CONTENT_TYPES = { personal:'亞伯特親身旅遊', planned:'預定旅程', research:'旅遊資料整理', inspiration:'靈感收藏' };
  const TRAVEL_STATUSES = { visited:'已造訪', planned:'計畫前往', inspiration:'靈感收藏' };

  function log(message) {
    const element = document.getElementById('log');
    element.textContent = '[' + new Date().toLocaleTimeString() + '] ' + message + '\n' + element.textContent;
  }
  function escapeHTML(value) {
    return String(value == null ? '' : value).replace(/[&<>'"]/g, (character) => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;'
    })[character]);
  }
  function setSignedIn(signedIn) {
    document.getElementById('login-panel').hidden = signedIn;
    document.getElementById('session-panel').hidden = !signedIn;
    if (!signedIn) document.getElementById('posts-list').innerHTML = '';
  }
  async function ensureAdmin() {
    const { data, error } = await client.auth.getUser();
    if (error || !data.user) throw new Error('請先登入');
    if (String(data.user.email || '').toLowerCase() !== config.adminEmail.toLowerCase()) {
      await client.auth.signOut();
      throw new Error('這個帳號沒有管理權限');
    }
    return data.user;
  }
  async function login() {
    const email = document.getElementById('email-input').value.trim().toLowerCase();
    if (email !== config.adminEmail.toLowerCase()) {
      alert('請使用已授權的管理員信箱');
      return;
    }
    const { error } = await client.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.href.split('#')[0] }
    });
    if (error) {
      log('登入信件寄送失敗：' + error.message);
      alert('登入信件寄送失敗：' + error.message);
      return;
    }
    log('登入連結已寄到 ' + email);
    alert('登入連結已寄出，請到信箱點擊連結。');
  }
  async function logout() {
    await client.auth.signOut();
    setSignedIn(false);
    log('已安全登出。');
  }
  async function readDocument(key) {
    await ensureAdmin();
    const { data, error } = await client.from('travel_blog_documents').select('payload').eq('key', key).single();
    if (error) throw error;
    return data.payload;
  }
  async function writeDocument(key, payload) {
    const user = await ensureAdmin();
    const { error } = await client.from('travel_blog_documents').upsert(
      { key, payload, updated_by:user.id, updated_at:new Date().toISOString() },
      { onConflict:'key' }
    );
    if (error) throw error;
  }
  function optionHTML(values, selected) {
    return Object.keys(values).map((key) => '<option value="' + escapeHTML(key) + '"' +
      (key === selected ? ' selected' : '') + '>' + escapeHTML(values[key]) + '</option>').join('');
  }
  async function loadPosts() {
    try {
      setSignedIn(true);
      log('正在從 Supabase 讀取文章資料...');
      const posts = await readDocument('posts');
      render(posts.sort((a, b) => new Date(b.date) - new Date(a.date)));
      log('已載入 ' + posts.length + ' 篇文章。');
    } catch (error) {
      setSignedIn(false);
      log('讀取失敗：' + error.message);
    }
  }
  function render(posts) {
    document.getElementById('posts-list').innerHTML = posts.map((post) => {
      const type = CONTENT_TYPES[post.content_type] ? post.content_type : 'research';
      const travelStatus = TRAVEL_STATUSES[post.travel_status] ? post.travel_status : 'inspiration';
      return '<div class="admin-card">' +
        '<img src="' + escapeHTML(post.cover_image) + '" alt="">' +
        '<div class="meta"><div><strong>' + escapeHTML(post.title_zh) + '</strong> <span class="status ' +
        escapeHTML(post.status) + '">' + escapeHTML(post.status) + '</span></div>' +
        '<div class="admin-subline">' + escapeHTML(post.date) + ' · ' + escapeHTML(post.city_en) + ' · ' +
        escapeHTML(post.angle_en) + '</div>' +
        '<div class="classification-row"><label>文章性質<select id="type-' + escapeHTML(post.slug) + '">' +
        optionHTML(CONTENT_TYPES, type) + '</select></label>' +
        '<label>旅程狀態<select id="travel-' + escapeHTML(post.slug) + '">' +
        optionHTML(TRAVEL_STATUSES, travelStatus) + '</select></label>' +
        '<button class="btn" onclick="AdminApp.saveClassification(\'' + escapeHTML(post.slug) +
        '\')">儲存分類</button></div></div>' +
        '<div class="actions"><button class="btn secondary" onclick="AdminApp.unpublish(\'' +
        escapeHTML(post.slug) + '\')">下架</button>' +
        '<button class="btn danger" onclick="AdminApp.flagForRevision(\'' + escapeHTML(post.slug) +
        '\')">下架並請求重寫</button></div></div>';
    }).join('');
  }
  async function saveClassification(slug) {
    try {
      const type = document.getElementById('type-' + slug).value;
      const travelStatus = document.getElementById('travel-' + slug).value;
      if (!CONTENT_TYPES[type] || !TRAVEL_STATUSES[travelStatus]) throw new Error('分類值不正確');
      const posts = await readDocument('posts');
      const post = posts.find((item) => item.slug === slug);
      if (!post) throw new Error('找不到文章：' + slug);
      post.content_type = type;
      post.travel_status = travelStatus;
      await writeDocument('posts', posts);
      log('分類已儲存：' + CONTENT_TYPES[type] + '／' + TRAVEL_STATUSES[travelStatus]);
    } catch (error) {
      log('分類更新失敗：' + error.message);
      alert('分類更新失敗：' + error.message);
    }
  }
  async function unpublish(slug, alsoFlag = false) {
    try {
      const posts = await readDocument('posts');
      const post = posts.find((item) => item.slug === slug);
      if (!post) throw new Error('找不到文章：' + slug);
      post.status = 'unpublished';
      await writeDocument('posts', posts);
      if (alsoFlag) {
        const history = await readDocument('history');
        history.priority_queue = history.priority_queue || [];
        history.priority_queue.push({ city_en:post.city_en, avoid_angle_key:post.angle_key });
        await writeDocument('history', history);
        log('已下架並排入優先重寫佇列：' + post.city_en);
      } else {
        log('已下架：' + slug);
      }
      await loadPosts();
    } catch (error) {
      log('操作失敗：' + error.message);
      alert('操作失敗：' + error.message);
    }
  }
  function flagForRevision(slug) { return unpublish(slug, true); }

  client.auth.onAuthStateChange((_event, session) => {
    if (session) loadPosts();
    else setSignedIn(false);
  });
  client.auth.getSession().then(({ data }) => {
    if (data.session) loadPosts();
    else setSignedIn(false);
  });
  return { login, logout, loadPosts, saveClassification, unpublish, flagForRevision };
})();
