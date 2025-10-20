---
trigger: always_on
alwaysApply: true
---
## 项目规则配置

### 文件生成规则
- 测试文件统一放置于 `/tests` 目录下
- 文档文件统一放置于 `/docs` 目录下
- 除非特别说明，不主动创建 markdown 文档

### 目录结构规范

```
meeting_assistant/
├── db/                         # 数据库相关模块
│   ├── sql/                    # SQL 初始化脚本
│   │   ├── dameng_messages_init.sql
│   │   ├── dameng_user_init.sql
│   │   ├── mysql_message_recipients_init.sql
│   │   ├── mysql_messages_init.sql
│   │   └── mysql_user_init.sql
│   ├── __init__.py
│   ├── conn_manager.py         # 数据库连接管理器
│   └── databases.py            # 数据库配置和会话管理
├── models/                     # 数据模型定义
│   ├── database/               # 数据库模型
│   │   ├── __init__.py
│   │   ├── enums.py            # 枚举类型定义
│   │   ├── meeting.py          # 会议相关数据库模型
│   │   ├── message.py          # 消息相关数据库模型
│   │   └── user.py             # 用户相关数据库模型
│   ├── schemas/                # Pydantic 数据模型
│   │   ├── __init__.py
│   │   ├── meeting.py          # 会议相关数据结构
│   │   ├── message.py          # 消息相关数据结构
│   │   ├── transcription.py    # 转录相关数据结构
│   │   └── user.py             # 用户相关数据结构
│   └── __init__.py
├── router/                     # API 路由管理
│   ├── __init__.py
│   ├── attendance_manage.py    # 考勤管理路由
│   ├── health_check.py         # 健康检查路由
│   ├── meeting_manage.py       # 会议管理路由
│   └── user_manage.py          # 用户管理路由
├── services/                   # 业务服务层
│   ├── auth_dependencies.py    # 认证依赖
│   ├── auth_service.py         # 认证服务
│   ├── document_service.py     # 文档处理服务
│   ├── email_service.py        # 邮件服务
│   ├── meeting_service.py      # 会议服务
│   ├── notification_service.py # 通知服务
│   ├── service_models.py       # 服务模型
│   ├── sign_in_service.py      # 签到服务
│   ├── speech_service.py       # 语音服务
│   └── user_service.py         # 用户服务
├── temp/                       # 临时文件
│   └── simple_password_test.py
├── test/                       # 测试工具和脚本
│   ├── databases.py
│   ├── file_server.py
│   ├── password_utils.py
│   ├── pytest_audio.py
│   └── transfer_live_audio.py
├── tests/                      # 单元测试
│   ├── test_create_update_user_api.py
│   ├── test_multi_field_search.py
│   ├── test_person_sign_move.py
│   ├── test_public_users_api.py
│   ├── test_refactor.py
│   ├── test_refactor_detailed.py
│   ├── test_reset_password_api.py
│   ├── test_simple.py
│   ├── test_token.py
│   ├── test_user_delete_hard.py
│   ├── test_user_detail_permission.py
│   └── test_users_auth_api.py
├── websocket/                  # WebSocket 相关
│   ├── __init__.py
│   └── manager.py              # WebSocket 连接管理器
├── .qoder/                     # Qoder IDE 配置
├── static/                     # 静态文件
├── docs/                       # 项目文档
├── .dockerignore
├── .env.example                # 环境变量示例配置
├── .gitignore
├── CLAUDE.md
├── Dockerfile
├── LICENSE
├── README.md
├── logging.yml                 # 日志配置
├── main.py                     # 项目入口文件
├── requirements.txt            # 项目依赖
└── schemas.py                  # 全局数据模型定义
```


### 注意事项
1. 所有测试文件必须放在 `tests` 目录中，便于统一管理和执行
2. 文档文件包括但不限于 API 文档、使用说明等，都应放在 `docs` 目录
3. 避免在项目根目录或其他位置随意创建文档文件
