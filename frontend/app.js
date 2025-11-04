const API_BASE = ""; // 同域访问，空字符串即可

const inputText = document.getElementById("inputText");
const detectBtn = document.getElementById("detectBtn");
const resultsDiv = document.getElementById("results");
const progressDiv = document.getElementById("progress");
const thresholdInput = document.getElementById("threshold");
const reloadBtn = document.getElementById("reloadBtn");
const themeToggle = document.getElementById("themeToggle");

// ========== 登录状态检查 ==========
// === 延迟检查登录状态（避免跳回 bug） ===
setTimeout(() => {
  const username = localStorage.getItem("username");
  const token = localStorage.getItem("token");

  console.log("🔍 登录检测中 =>", { username, token });

  if (!username || !token) {
    console.warn("⚠️ 未检测到登录状态，跳转登录页");
    window.location.href = "/login.html";
  } else {
    console.log(`✅ 已登录用户: ${username}`);
  }
}, 3000); // 延迟 300ms 再检查，确保 localStorage 已写入





function setProgress(text) {
  progressDiv.textContent = text;
}

async function predict() {
  const text = inputText.value.trim();
  if (!text) return alert("请输入智能合约源码！");
  resultsDiv.innerHTML = "";
  setProgress("检测中...");

  try {
    const resp = await fetch(`${API_BASE}/api/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        threshold: parseFloat(thresholdInput.value || 0.5)
      }),
    });

    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    showResults(data);
    setProgress("检测完成 ✅");
  } catch (err) {
    setProgress("检测失败: " + err.message);
  }
}

// 在文件顶部（若还没定义）加一个简单的 HTML 转义函数，防 XSS
function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showResults(data) {
  resultsDiv.innerHTML = "";
  const { labels = [], probs = [] } = data;
  if (labels.length === 0) {
    resultsDiv.innerHTML = "<div class='small'>未检测到高于阈值的漏洞。</div>";
    return;
  }

  labels.forEach((label, i) => {
    // 将 label 按冒号分成 title 和 description（只分第一个冒号）
    const parts = label.split(/:(.+)/); // 注意：保留冒号后所有内容
    const title = parts[0] ? parts[0].trim() : "";
    const desc = parts[1] ? parts[1].trim() : "";

    const card = document.createElement("div");
    card.className = "card";

    // 安全地构建 HTML：标题加粗，描述常规文字
    const safeTitle = escapeHtml(title);
    const safeDesc = escapeHtml(desc);

    card.innerHTML = `
      <div class="vuln-title"><strong>${safeTitle}</strong></div>
      ${safeDesc ? `<div class="vuln-desc">${safeDesc}</div>` : ""}
    `;

    resultsDiv.appendChild(card);
  });
}



detectBtn.addEventListener("click", predict);

reloadBtn.addEventListener("click", async () => {
  const adapter = prompt("输入新的 adapter 路径（留空不修改）:");
  const base = prompt("输入新的 base 模型路径（留空不修改）:");
  const payload = {};
  if (adapter) payload.adapter_path = adapter;
  if (base) payload.base_path = base;
  setProgress("重新加载中...");
  try {
    const resp = await fetch(`${API_BASE}/api/reload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(await resp.text());
    alert("模型已重载成功 ✅");
    setProgress("模型已切换");
  } catch (err) {
    setProgress("切换失败: " + err.message);
  }
});


function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeToggle.textContent = theme === "dark" ? "🌞 切换主题" : "🌙 切换主题";
  localStorage.setItem("theme", theme);

  const username = localStorage.getItem("username");
  const token = localStorage.getItem("token");

  if (username) {
    fetch("/api/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, theme, token }), // ✅ 确保 token 一起传
    }).catch((err) => console.error("更新主题失败:", err));
  }
}



themeToggle.addEventListener("click", () => {
  const cur = localStorage.getItem("theme") || "light";
  applyTheme(cur === "dark" ? "light" : "dark");
});
(function initTheme() {
  const t = localStorage.getItem("theme") || "light";
  applyTheme(t);
})();

const logoutBtn = document.getElementById("logoutBtn");

if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    const username = localStorage.getItem("username");
    const token = localStorage.getItem("token");

    try {
      // 可选：通知后端记录退出
      await fetch("/api/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, token }),
      });
    } catch (err) {
      console.warn("退出登录上报失败:", err);
    }

    // ✅ 清除本地登录信息
    localStorage.removeItem("username");
    localStorage.removeItem("token");
    localStorage.removeItem("theme");

    // ✅ 跳转回登录页
    window.location.replace("/login.html");
  });
}





const changePwdBtn = document.getElementById("changePwdBtn");

if (changePwdBtn) {
  changePwdBtn.addEventListener("click", async () => {
    const username = localStorage.getItem("username");
    const token = localStorage.getItem("token");

    if (!username) {
      alert("请先登录！");
      window.location.href = "/login.html";
      return;
    }

    const oldPwd = prompt("请输入当前密码：");
    if (!oldPwd) return;
    const newPwd = prompt("请输入新密码：");
    if (!newPwd) return;

    try {
      const resp = await fetch("/api/change_password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, old_password: oldPwd, new_password: newPwd, token }),
      });

      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "修改失败");

      alert(data.message || "密码修改成功，请重新登录");
      // ✅ 修改成功后清除登录信息
      localStorage.removeItem("username");
      localStorage.removeItem("token");
      localStorage.removeItem("theme");
      window.location.replace("/login.html");
    } catch (err) {
      alert("❌ 修改失败：" + err.message);
    }
  });
}



