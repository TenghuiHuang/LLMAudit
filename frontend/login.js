const API_BASE = "";
const loginBtn = document.getElementById("loginBtn");
const msg = document.getElementById("loginMsg");

loginBtn.addEventListener("click", async () => {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();

  if (!username || !password) {
    msg.textContent = "请输入用户名和密码";
    msg.style.color = "red";
    return;
  }

  try {
    const resp = await fetch(`${API_BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    // ✅ 改成 localStorage
    localStorage.setItem("token", data.token || "mock-token");
    localStorage.setItem("username", data.username || username);

    msg.textContent = "登录成功，正在跳转...";
    msg.style.color = "green";
    setTimeout(() => (window.location.href = "/index.html"), 3000);
  } catch (err) {
    msg.textContent = "登录失败：" + err.message;
    msg.style.color = "red";
  }
});
