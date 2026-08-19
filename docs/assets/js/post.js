'use strict';
(function() {
  const contentTypes = {
    personal:{ label:'亞伯特親身旅遊', icon:'✓' }, planned:{ label:'預定旅程', icon:'◷' },
    research:{ label:'旅遊資料整理', icon:'▤' }, inspiration:{ label:'靈感收藏', icon:'✦' }
  };
  const travelStatuses = {
    visited:{ label:'已造訪', icon:'●' }, planned:{ label:'計畫前往', icon:'◐' }, inspiration:{ label:'靈感收藏', icon:'○' }
  };
  async function syncClassification() {
    try {
      const slug = decodeURIComponent(window.location.pathname.split('/').pop().replace(/\.html$/, ''));
      const response = await fetch('../data/posts.json?_=' + Date.now());
      if (!response.ok) return;
      const posts = await response.json();
      const post = posts.find(function(item) { return item.slug === slug; });
      if (!post) return;
      const typeKey = contentTypes[post.content_type] ? post.content_type : 'research';
      const statusKey = travelStatuses[post.travel_status] ? post.travel_status : 'inspiration';
      const typeBadge = document.querySelector('.content-badge');
      const statusBadge = document.querySelector('.travel-badge');
      if (typeBadge) { typeBadge.className = 'content-badge ' + typeKey; typeBadge.textContent = contentTypes[typeKey].icon + ' ' + contentTypes[typeKey].label; }
      if (statusBadge) { statusBadge.className = 'travel-badge ' + statusKey; statusBadge.textContent = travelStatuses[statusKey].icon + ' ' + travelStatuses[statusKey].label; }
      const disclosure = document.querySelector('.content-disclosure');
      if (disclosure) {
        const messages = {
          personal:'內容性質說明：本篇為亞伯特親身旅遊紀錄。',
          planned:'內容性質說明：本篇為預定旅程規劃，尚非親身造訪紀錄。',
          research:'內容性質說明：本篇為旅遊資料整理，並非亞伯特親身造訪紀錄；行程敘事用於呈現規劃情境。',
          inspiration:'內容性質說明：本篇為旅遊靈感收藏，並非亞伯特親身造訪紀錄。'
        };
        disclosure.textContent = messages[typeKey];
      }
    } catch (error) { console.error('分類同步失敗', error); }
  }
  const blocks = document.querySelectorAll('[data-lang-block]');
  const buttons = document.querySelectorAll('[data-language]');
  function setLanguage(language) {
    blocks.forEach(function(block) { block.classList.toggle('active', block.dataset.langBlock === language); });
    buttons.forEach(function(button) { button.classList.toggle('active', button.dataset.language === language); });
    try { localStorage.setItem('albert_blog_language', language); } catch (error) {}
  }
  buttons.forEach(function(button) {
    button.addEventListener('click', function() { setLanguage(button.dataset.language); });
  });
  let saved = 'zh';
  try { saved = localStorage.getItem('albert_blog_language') || 'zh'; } catch (error) {}
  setLanguage(saved === 'en' ? 'en' : 'zh');
  const pageUrl = encodeURIComponent(window.location.href);
  const line = document.getElementById('line-share');
  const facebook = document.getElementById('facebook-share');
  if (line) line.href = 'https://social-plugins.line.me/lineit/share?url=' + pageUrl;
  if (facebook) facebook.href = 'https://www.facebook.com/sharer/sharer.php?u=' + pageUrl;
  const copy = document.getElementById('copy-link');
  if (copy) {
    copy.addEventListener('click', async function() {
      try { await navigator.clipboard.writeText(window.location.href); this.textContent = '已複製'; }
      catch (error) { window.prompt('複製以下連結', window.location.href); }
    });
  }
  const progress = document.getElementById('reading-progress');
  const topButton = document.getElementById('back-to-top');
  function onScroll() {
    const height = document.documentElement.scrollHeight - window.innerHeight;
    if (progress) progress.style.width = (height > 0 ? Math.min(100, window.scrollY / height * 100) : 0) + '%';
    if (topButton) topButton.classList.toggle('visible', window.scrollY > 600);
  }
  window.addEventListener('scroll', onScroll, { passive:true });
  if (topButton) topButton.addEventListener('click', function() { window.scrollTo({ top:0, behavior:'smooth' }); });
  onScroll();
  syncClassification();
})();
