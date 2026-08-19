const AdminApp = (() => {
  const cfg = window.ALBERT_BLOG_CONFIG;
  const API = "https://api.github.com";

  function log(msg) {
    const el = document.getElementById("log");
    el.textContent = "[" + new Date().toLocaleTimeString() + "] " + msg + "\n" + el.textContent;
  }

  function getToken() {
    return localStorage.getItem("albert_gh_pat");
  }

  function login() {
    const val = document.getElementById("pat-input").value.trim();
    if (!val) { alert("請先貼上 GitHub Personal Access Token"); return; }
    localStorage.setItem("albert_gh_pat", val);
    loadPosts();
  }

  function logout() {
    localStorage.removeItem("albert_gh_pat");
    document.getElementById("posts-list").innerHTML = "";
    log("已登出,權杖已清除。");
  }

  async function ghGetFile(path) {
    const url = API + "/repos/" + cfg.GITHUB_OWNER + "/" + cfg.GITHUB_REPO + "/contents/" + path + "?ref=" + cfg.BRANCH;
    const res = await fetch(url, {
      headers: { Authorization: "Bearer " + getToken(), Accept: "application/vnd.github+json" },
    });
    if (!res.ok) throw new Error("讀取 " + path + " 失敗 (" + res.status + ")");
    const json = await res.json();
    const content = decodeURIComponent(escape(atob(json.content)));
    return { data: JSON.parse(content), sha: json.sha };
  }

  async function ghPutFile(path, dataObj, sha, message) {
    const content = btoa(unescape(encodeURIComponent(JSON.stringify(dataObj, null, 2))));
    const url = API + "/repos/" + cfg.GITHUB_OWNER + "/" + cfg.GITHUB_REPO + "/contents/" + path;
    const res = await fetch(url, {
      method: "PUT",
      headers: { Authorization: "Bearer " + getToken(), Accept: "application/vnd.github+json" },
      body: JSON.stringify({ message, content, sha, branch: cfg.BRANCH }),
    });
    if (!res.ok) throw new Error("寫入 " + path + " 失敗 (" + res.status + ")");
    return res.json();
  }

  async function loadPosts() {
    try {
      log("正在讀取 data/posts.json ...");
      const { data: posts } = await ghGetFile("data/posts.json");
      render(posts.sort((a, b) => new Date(b.date) - new Date(a.date)));
      log("已載入 " + posts.length + " 篇文章。");
    } catch (e) {
      log("錯誤: " + e.message);
      alert("讀取失敗,請確認權杖權限與 config.js 裡的帳號/repo 名稱是否正確。");
    }
  }

  function render(posts) {
    const container = document.getElementById("posts-list");
    container.innerHTML = posts.map((p, i) => {
      return '<div class="admin-card">' +
        '<img src="' + p.cover_image + '" alt="">' +
        '<div class="meta">' +
        '<div><strong>' + p.title_zh + '</strong> <span class="status ' + p.status + '">' + p.status + '</span></div>' +
        '<div style="font-family:var(--font-mono); font-size:12px; color:#8a7f6f;">' + p.date + ' · ' + p.city_en + ' · ' + p.angle_en + '</div>' +
        '</div>' +
        '<div class="actions">' +
        '<button class="btn secondary" onclick="AdminApp.unpublish(\'' + p.slug + '\')">下架</button>' +
        '<button class="btn danger" onclick="AdminApp.flagForRevision(\'' + p.slug + '\')">下架並請求重寫</button>' +
        '</div>' +
        '</div>';
    }).join("");
  }

  async function unpublish(slug, alsoFlag = false) {
    try {
      log("正在下架: " + slug + " ...");
      const { data: posts, sha: postsSha } = await ghGetFile("data/posts.json");
      const post = posts.find((p) => p.slug === slug);
      if (!post) throw new Error("找不到這篇文章");
      post.status = "unpublished";
      await ghPutFile("data/posts.json", posts, postsSha, "admin: 下架 " + slug);

      if (alsoFlag) {
        const { data: history, sha: historySha } = await ghGetFile("data/history.json");
        history.priority_queue.push({ city_en: post.city_en, avoid_angle_key: post.angle_key });
        await ghPutFile("data/history.json", history, historySha, "admin: 請求重新生成 " + post.city_en);
        log("已下架並排入明天優先重寫佇列: " + post.city_en);
      } else {
        log("已下架: " + slug);
      }
      loadPosts();
    } catch (e) {
      log("錯誤: " + e.message);
      alert("操作失敗: " + e.message);
    }
  }

  function flagForRevision(slug) {
    unpublish(slug, true);
  }

  // 若之前已登入過,自動載入
  if (getToken()) loadPosts();

  return { login, logout, unpublish, flagForRevision };
})();
