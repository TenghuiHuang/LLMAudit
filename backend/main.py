# file: backend/main.py
"""
FastAPI 后端入口
运行示例：
    cd backend
    python -m uvicorn main:app --host 0.0.0.0 --port 8000
"""

import os
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from model_server import ContractClassifierServer

# ==========================
# 模型配置（请按实际路径修改）
# ==========================
DEFAULT_BASE = "/home/huangtenghui/LLMAudit/model/llama-3.2-1B"
DEFAULT_ADAPTER = "/home/huangtenghui/LLMAudit/SLoRA"

# ==========================
# 模型服务单例
# ==========================
model_server = ContractClassifierServer(DEFAULT_BASE, DEFAULT_ADAPTER)

# ==========================
# lifespan 生命周期事件
# ==========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    print("[🚀] 正在加载模型，请稍候...")
    success, msg = await loop.run_in_executor(None, model_server.load_model)
    if not success:
        app.state.model_load_error = msg
        print(f"[⚠️] 模型加载失败: {msg}")
    else:
        print("[✅] 模型已成功加载")

    yield  # 应用运行中

    try:
        model_server.release()
        print("[🧹] 模型资源已释放")
    except Exception as e:
        print(f"[⚠️] 模型释放时出错: {e}")

# ==========================
# 创建应用
# ==========================
app = FastAPI(title="SCAudit Model API", lifespan=lifespan)


# 开发阶段允许所有来源跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# 数据模型
# ==========================
class PredictRequest(BaseModel):
    text: str
    threshold: Optional[float] = 0.5
    max_length: Optional[int] = 512

class ReloadRequest(BaseModel):
    base_path: Optional[str] = None
    adapter_path: Optional[str] = None

# ==========================
# API 路由
# ==========================
@app.get("/api/status")
def status():
    """检查模型加载状态"""
    return model_server.status()

@app.post("/api/predict")
async def predict(req: PredictRequest):
    """智能合约漏洞检测"""
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="text is empty")

    loop = asyncio.get_event_loop()
    try:
        matched, probs = await loop.run_in_executor(
            None, model_server.predict, req.text, req.threshold, req.max_length
        )
        return {"labels": matched, "probs": probs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reload")
async def reload_model(req: ReloadRequest):
    """热重载模型"""
    new_base = req.base_path or model_server.base_model_path
    new_adapter = req.adapter_path or model_server.adapter_path
    loop = asyncio.get_event_loop()
    success, msg = await loop.run_in_executor(
        None, model_server.load_model, new_base, new_adapter
    )
    if not success:
        raise HTTPException(status_code=500, detail=f"reload failed: {msg}")
    return {"status": "reloaded", "base": new_base, "adapter": new_adapter}


from fastapi import Request
from fastapi.responses import JSONResponse
import json

USER_DB = os.path.join(os.path.dirname(__file__), "users.json")

# 初始化用户数据库
if not os.path.exists(USER_DB):
    with open(USER_DB, "w", encoding="utf-8") as f:
        json.dump({"admin": {"password": "123456", "theme": "light"}}, f, ensure_ascii=False, indent=2)

def load_users():
    with open(USER_DB, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USER_DB, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


@app.post("/api/register")
async def register_user(req: Request):
    """创建新账户"""
    data = await req.json()
    username = data.get("username")
    password = data.get("password")

    # 参数检查
    if not username or not password:
        return JSONResponse(status_code=400, content={"error": "用户名和密码不能为空"})

    users = load_users()

    # 检查是否已存在
    if username in users:
        return JSONResponse(status_code=400, content={"error": "用户名已存在"})

    # 写入新账户
    users[username] = {"password": password, "theme": "light"}
    save_users(users)
    print(f"[🆕] 新用户注册成功: {username}")

    # 注册成功后直接返回登录凭证
    token = f"token-{username}"
    response = JSONResponse(content={
        "message": "注册成功",
        "username": username,
        "theme": "light",
        "token": token
    })
    response.set_cookie(key="username", value=username, httponly=False, max_age=3600, path="/")
    return response



@app.post("/api/login")
async def login(req: Request):
    data = await req.json()
    username = data.get("username")
    password = data.get("password")

    users = load_users()
    user = users.get(username)
    if not user or user["password"] != password:
        return JSONResponse(status_code=401, content={"error": "用户名或密码错误"})

    # ✅ 增加 token
    token = f"token-{username}"
    response = JSONResponse(content={"username": username, "theme": user.get("theme", "light"), "token": token})
    response.set_cookie(key="username", value=username, httponly=False, max_age=3600, path="/")
    return response



@app.post("/api/theme")
async def update_theme(req: Request):
    data = await req.json()
    username = data.get("username")
    theme = data.get("theme")
    token = data.get("token")

    if not username or not theme:
        return JSONResponse(status_code=400, content={"error": "参数缺失"})

    # ✅ 简化 token 校验逻辑，允许 token 不传也能保存（便于前端调试）
    if token and token != f"token-{username}":
        return JSONResponse(status_code=401, content={"error": "无效的用户身份"})

    users = load_users()
    if username not in users:
        return JSONResponse(status_code=404, content={"error": "用户不存在"})

    users[username]["theme"] = theme
    save_users(users)
    print(f"[🎨] 用户 {username} 已更新主题为: {theme}")

    return {"message": "主题已更新", "theme": theme}




@app.post("/api/logout")
async def logout_user(req: Request):
    data = await req.json()
    username = data.get("username")
    token = data.get("token")

    if not username:
        return JSONResponse(status_code=400, content={"error": "缺少用户名"})
    response = JSONResponse(content={"message": "退出成功"})
    response.delete_cookie("username")
    print(f"[🚪] 用户 {username} 已退出登录")
    return response



@app.post("/api/change_password")
async def change_password(req: Request):
    """用户修改密码"""
    data = await req.json()
    username = data.get("username")
    old_pwd = data.get("old_password")
    new_pwd = data.get("new_password")
    token = data.get("token")

    # 参数检查
    if not username or not old_pwd or not new_pwd:
        return JSONResponse(status_code=400, content={"error": "缺少必要参数"})

    # ✅ 校验 token（如果前端传入）
    if token and token != f"token-{username}":
        return JSONResponse(status_code=401, content={"error": "无效的用户身份"})

    users = load_users()
    user = users.get(username)
    if not user:
        return JSONResponse(status_code=404, content={"error": "用户不存在"})

    if user["password"] != old_pwd:
        return JSONResponse(status_code=403, content={"error": "旧密码错误"})

    users[username]["password"] = new_pwd
    save_users(users)
    print(f"[🔑] 用户 {username} 修改了密码")

    return {"message": "密码修改成功，请重新登录"}

from fastapi import Request

@app.get("/api/userinfo")
async def get_userinfo(request: Request):
    username = request.cookies.get("username")
    if not username:
        return {"username": None}
    return {"username": username}


# ========================== 
# # 前端网页挂载（终极修正版） 
# # ========================== 
from fastapi.responses import FileResponse

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))

if os.path.exists(frontend_dir):
    # ✅ 让所有前端文件（HTML、CSS、JS）都可直接访问
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    # ✅ 默认访问 / 时显示登录页
    @app.get("/")
    async def serve_login():
        return FileResponse(os.path.join(frontend_dir, "login.html"))
else:
    @app.get("/")
    async def root_info():
        return {
            "message": "✅ SCAudit Model API is running",
            "available_endpoints": {
                "/api/status": "检查模型状态",
                "/api/predict": "检测智能合约漏洞（POST）",
                "/api/reload": "重新加载模型（POST）",
            },
        }
