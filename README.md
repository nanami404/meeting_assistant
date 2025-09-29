# Meeting Assistant

一个基于 FastAPI 的智能会议助手系统，提供会议管理、实时语音转录、文档生成和邮件通知功能。

## ✨ 主要功能

- 🎯 **会议管理** - 完整的会议CRUD操作，支持多角色参会人员管理
- 🎤 **实时语音转录** - 支持多种音频格式，实时语音识别和转录
- 📄 **智能文档生成** - 自动生成会议通知、会议纪要，支持Word和PDF格式
- 📧 **邮件服务** - 自动发送会议通知邮件
- 🔌 **实时通信** - WebSocket支持，实时转录结果广播

## 🚀 快速开始

### 环境要求

- Python 3.12+
- MySQL 8.0+
- FFmpeg（音频处理）

### 安装和运行

1. **克隆项目**
   ```bash
   git clone https://github.com/nanami404/meeting.git
   cd meeting
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，配置数据库连接等信息
   ```

4. **运行应用**
   ```bash
   python main.py
   ```

   应用将在 `http://localhost:8000` 启动，API文档可在 `http://localhost:8000/docs` 查看。

## 📁 项目结构

```
├── main.py                 # 应用入口
├── schemas.py              # 数据模型
├── requirements.txt        # 依赖包
├── Dockerfile             # Docker配置
├── db/                    # 数据库层
├── services/              # 业务逻辑层
├── router/                # API路由层
├── websocket/             # WebSocket通信
├── static/                # 静态文件
├── test/                  # 测试文件
└── doc/                   # 详细文档
```

## 🔧 环境配置

创建 `.env` 文件并配置以下参数：

```env
# JWT Configuration
JWT_SECRET=123456
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_MINUTES=43200
JWT_ISSUER=meeting-assistant
JWT_AUDIENCE=meeting-assistant-clients

# 数据库配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=meeting_db

# API配置
API_HOST=0.0.0.0
API_PORT=8000

# CORS配置
CORS_ORIGINS=http://localhost:3000

# 邮件配置
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_password
```

## 📚 API 文档

启动应用后，访问以下链接查看完整的API文档：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 主要API端点

- `POST /meetings/` - 创建会议
- `GET /meetings/` - 获取会议列表
- `GET /meetings/{meeting_id}` - 获取会议详情
- `POST /meetings/{meeting_id}/transcriptions` - 保存转录记录
- `WS /ws/{client_id}` - WebSocket连接

## 🛠️ 技术栈

- **后端**: FastAPI + SQLAlchemy + MySQL
- **异步**: Uvicorn + asyncio
- **语音识别**: SpeechRecognition + Google Speech API
- **文档生成**: python-docx + ReportLab
- **实时通信**: WebSocket
- **容器化**: Docker

## 📖 详细文档

更多详细信息请查看：
- [完整项目文档](./doc/README.md)
- [用户管理计划](./doc/USER_MANAGEMENT_MVP_PLAN.md)
- [API接口说明](http://localhost:8000/docs)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进项目。

## 📄 许可证

本项目采用 MIT 许可证。

---

*如有问题或需要技术支持，请提交 Issue 到项目仓库。*