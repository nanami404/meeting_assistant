# 消息管理功能 TODO 清单

## 项目概述

本项目旨在实现一个完整的消息管理系统，支持管理员向指定用户发送系统消息，并允许用户在登录后通过 WebSocket 实时接收新消息，同时可查看、管理自己的消息记录。

## 功能需求分解

### 1. 消息发送功能（由管理员触发）

#### 验收标准
- 管理员可通过后端接口向一个或多个指定用户发送消息
- 系统在 `messages` 表中创建消息记录（包含标题、内容、发送者 ID 和创建时间）
- 为每个目标用户在 `message_recipients` 表中插入关联记录，初始状态为"未读"（`is_read = 0`）
- 操作不依赖接收用户是否在线，无论用户当前是否活跃均可成功发送并持久化存储

#### AI提示词
```
请帮我创建一个管理员发送消息的API接口，该接口需要：
1. 接收消息标题、内容和目标用户ID列表
2. 在messages表中创建消息记录，包含标题、内容、发送者ID（从当前管理员获取）
3. 为每个目标用户在message_recipients表中创建关联记录，状态为未读（is_read=0）
4. 需要管理员权限验证（使用require_admin依赖）
5. 使用SQLAlchemy ORM操作数据库
6. 返回创建的消息信息，包括ID、标题、内容、发送者ID、接收者ID列表和创建时间
7. 如果目标用户ID不存在，应跳过该用户并记录警告日志

接口定义：
- 方法：POST
- 路径：/api/messages/send
- 请求体：MessageCreate (title, content, recipient_ids)
- 响应：MessageResponse
- 权限：需要管理员权限
```

### 2. WebSocket 实时消息推送机制

#### 验收标准
- 用户登录后，前端主动建立 WebSocket 连接（如 `/ws/messages`）
- 连接时携带有效身份凭证（如 JWT Token）
- 后端验证身份后，将用户 WebSocket 连接注册到内存中的在线连接池（以用户 ID 为键）
- 连接建立成功后，系统立即查询该用户在 `message_recipients` 表中所有 `is_read = 0` 的消息，按创建时间升序逐条推送至前端
- 每当有新消息发送给该用户，后端在写入数据库的同时，会检查其是否处于在线连接池中；若在线，则立即将新消息内容通过 WebSocket 实时推送

#### AI提示词
```
请帮我实现一个WebSocket消息推送系统，要求：
1. 创建WebSocket端点/ws/messages
2. 验证连接时的JWT Token获取用户身份（使用get_current_user依赖或类似机制）
3. 将用户连接注册到连接池中（可使用现有的websocket/manager.py或扩展它）
4. 连接建立后立即查询并推送所有未读消息（is_read=0）给该用户
5. 实现新消息实时推送功能：当有新消息发送给在线用户时，立即推送
6. 使用FastAPI的WebSocket支持
7. 消息推送格式应包含消息ID、标题、内容、发送者ID、创建时间等信息
8. 处理连接断开情况，及时清理连接池

WebSocket连接示例：
- URL: ws://localhost:8000/ws/messages
- 连接头: Authorization: Bearer <access_token>
- 推送消息格式: JSON对象，包含消息详情
```

### 3. 消息列表查询与过滤

#### 验收标准
- 用户可通过 RESTful 接口查询自己接收到的所有消息
- 系统关联 `messages` 与 `message_recipients` 表，按消息创建时间倒序返回结果
- 支持过滤条件：
  - 不传参：返回全部消息（已读 + 未读）
  - `is_read=0`：仅返回未读消息
  - `is_read=1`：仅返回已读消息
- 接口支持分页（如 `page` 和 `size` 参数），默认每页 20 条

#### AI提示词
```
请帮我创建一个消息查询API接口，该接口需要：
1. 支持按is_read状态过滤消息（0未读，1已读，不传参返回全部）
2. 关联messages和message_recipients表查询当前用户接收的消息
3. 按消息创建时间倒序排列
4. 支持分页参数page和size，默认page=1，size=20，最大100
5. 只能查询当前用户接收的消息（recipient_id等于当前用户ID）
6. 返回消息详细信息，包括消息ID、标题、内容、发送者ID、创建时间、阅读状态等
7. 返回分页信息，包括总数量、总页数、是否有下一页、是否有上一页等

接口定义：
- 方法：GET
- 路径：/api/messages/list
- 查询参数：page, page_size, is_read
- 响应：MessageListResponse（包含消息列表和分页信息）
- 权限：需要用户登录（require_auth依赖）
```

### 4. 批量标记已读操作

#### 验收标准
- 用户可调用接口将自己所有未读消息（即 `message_recipients.is_read = 0` 且 `recipient_id` 为当前用户）一次性标记为已读
- 系统将这些记录的 `is_read` 字段更新为 `1`，并设置 `read_at` 为当前时间戳

#### AI提示词
```
请帮我创建一个批量标记消息为已读的API接口，该接口需要：
1. 将当前用户所有未读消息标记为已读（message_recipients.is_read=0且recipient_id=当前用户ID）
2. 更新message_recipients表中的is_read字段为1
3. 设置read_at字段为当前时间戳
4. 只能操作当前用户的消息记录
5. 返回操作结果统计信息，包括更新的消息数量

接口定义：
- 方法：POST
- 路径：/api/messages/mark-all-read
- 请求体：空或特定标记类型参数
- 响应：BatchOperationResponse（包含updated_count）
- 权限：需要用户登录（require_auth依赖）

扩展功能：
- 支持标记单条消息为已读
- 接口路径：/api/messages/mark-read
- 请求体：MarkReadRequest（包含message_id）
```

### 5. 消息删除操作

#### 验收标准
- 删除单条消息：用户可删除自己接收到的某一条消息，即从 `message_recipients` 表中删除对应记录（不影响其他接收者或原始消息内容）
- 删除全部消息：用户可删除自己所有的接收记录，即删除 `message_recipients` 表中所有 `recipient_id` 为当前用户的数据

#### AI提示词
```
请帮我创建消息删除API接口，需要支持：
1. 删除单条消息：根据message_id删除当前用户的接收记录
2. 删除全部消息：删除当前用户的所有消息接收记录
3. 只能删除当前用户的消息记录（recipient_id等于当前用户ID）
4. 物理删除方式（直接从数据库删除记录）
5. 返回删除成功状态和删除数量统计

接口定义：
- 方法：POST
- 路径：/api/messages/delete
- 请求体：DeleteMessageRequest（包含message_id或type参数）
- 响应：BatchOperationResponse（包含deleted_count）
- 权限：需要用户登录（require_auth依赖）

删除类型：
- type="all"：删除所有消息
- type="read"：删除已读消息
- type="unread"：删除未读消息
- message_id：删除指定消息
```

### 6. 安全与权限控制

#### 验收标准
- 所有消息相关接口（包括查询、标记、删除）必须严格校验当前用户身份
- 确保用户只能操作属于自己的 `message_recipients` 记录（即 `recipient_id` 必须等于当前用户 ID），防止越权访问
- 管理员发送接口也需验证调用者具备管理员权限

#### AI提示词
```
请帮我实现消息系统的权限控制，要求：
1. 所有消息接口都需要用户身份验证（使用require_auth依赖）
2. 用户只能操作自己的消息记录（recipient_id等于当前用户ID）
3. 管理员发送消息接口需要验证管理员权限（使用require_admin依赖）
4. 使用FastAPI的Depends依赖注入实现权限验证
5. 返回适当的HTTP错误状态码（401, 403, 404等）
6. 对于越权访问尝试，记录安全日志

安全检查点：
- 消息发送：验证管理员权限
- 消息查询：验证用户只能查询自己的消息
- 消息标记：验证用户只能标记自己的消息
- 消息删除：验证用户只能删除自己的消息
- 数据库查询：所有操作都必须添加recipient_id过滤条件
```

## 实现阶段节点

### 阶段一：数据库模型与初始化
1. 创建消息相关的数据库模型（基于现有的 `messages` 和 `message_recipients` 表结构）
   - 创建 [models/database/message.py](file:///d:/work/meeting_assistant/models/database/message.py) 文件，定义 `Message` 和 `MessageRecipient` 数据库模型
   - `Message` 模型对应 `messages` 表，包含字段：id, title, content, sender_id, created_at, updated_at
   - `MessageRecipient` 模型对应 `message_recipients` 表，包含字段：id, message_id, recipient_id, is_read, read_at, created_at
2. 创建相应的Pydantic模型（用于API接口数据验证和序列化）
   - 创建 [models/schemas/message.py](file:///d:/work/meeting_assistant/models/schemas/message.py) 文件，定义消息相关的数据结构
   - 定义 `MessageCreate`, `MessageUpdate`, `MessageResponse` 等Pydantic模型
   - 定义 `MessageRecipientCreate`, `MessageRecipientUpdate`, `MessageRecipientResponse` 等Pydantic模型

### 阶段二：核心服务层实现
1. 创建消息服务类 `MessageService`
   - 实现消息发送功能（管理员）
   - 实现消息查询功能（用户）
   - 实现消息标记已读功能（用户）
   - 实现消息删除功能（用户）
2. 扩展WebSocket连接管理器以支持消息推送
   - 在现有连接管理器中添加消息推送方法
   - 实现用户连接时推送未读消息功能
   - 实现新消息实时推送功能

#### AI提示词
```
请帮我创建MessageService类，需要实现以下功能：
1. 消息发送：create_message(current_user_id, message_data: MessageCreate)
   - 验证用户为管理员
   - 在messages表中创建消息记录
   - 为每个recipient_id在message_recipients表中创建记录
   - 返回创建的消息信息

2. 消息查询：get_user_messages(current_user_id, page, page_size, is_read)
   - 查询当前用户的消息接收记录
   - 关联messages表获取消息详情
   - 支持分页和已读状态过滤
   - 按创建时间倒序排列

3. 标记已读：mark_messages_as_read(current_user_id, message_id=None, mark_all=False)
   - 标记单条消息为已读或标记所有未读消息为已读
   - 更新message_recipients表中的is_read和read_at字段
   - 返回更新数量

4. 删除消息：delete_messages(current_user_id, message_id=None, delete_type=None)
   - 删除单条消息或按类型删除消息
   - 从message_recipients表中删除记录
   - 返回删除数量

所有方法都需要：
- 使用SQLAlchemy ORM操作数据库
- 正确处理数据库事务
- 添加适当的日志记录
- 处理异常情况并返回适当的错误
```

### 阶段三：API路由层实现
1. 创建消息管理路由文件 `router/message_manage.py`
2. 实现管理员发送消息接口
3. 实现用户查询消息接口
4. 实现用户标记已读接口
5. 实现用户删除消息接口

#### AI提示词
```
请帮我创建消息管理路由文件router/message_manage.py，需要实现以下接口：

1. 管理员发送消息接口
   - 路径：POST /api/messages/send
   - 使用MessageService.create_message方法
   - 需要管理员权限验证
   - 请求体：MessageCreate
   - 响应：MessageResponse

2. 用户查询消息接口
   - 路径：GET /api/messages/list
   - 使用MessageService.get_user_messages方法
   - 需要用户权限验证
   - 查询参数：page, page_size, is_read
   - 响应：MessageListResponse

3. 用户标记已读接口
   - 路径：POST /api/messages/mark-read
   - 路径：POST /api/messages/mark-all-read
   - 使用MessageService.mark_messages_as_read方法
   - 需要用户权限验证
   - 请求体：MarkReadRequest
   - 响应：BatchOperationResponse

4. 用户删除消息接口
   - 路径：POST /api/messages/delete
   - 使用MessageService.delete_messages方法
   - 需要用户权限验证
   - 请求体：DeleteMessageRequest
   - 响应：BatchOperationResponse

要求：
- 使用FastAPI框架
- 正确处理依赖注入（数据库会话、当前用户）
- 实现统一的响应格式
- 添加适当的异常处理
- 遵循项目现有的代码风格
```

### 阶段四：WebSocket实时推送实现
1. 扩展WebSocket连接管理器以支持消息推送
2. 实现用户连接时推送未读消息功能
3. 实现新消息实时推送功能

#### AI提示词
```
请帮我扩展WebSocket连接管理器以支持消息推送功能：

1. 修改websocket/manager.py文件，添加以下方法：
   - send_message_to_user(user_id, message_data): 向指定用户发送消息
   - send_unread_messages_on_connect(user_id): 用户连接时发送未读消息
   - broadcast_new_message(message_data, recipient_ids): 向多个用户广播新消息

2. 实现用户连接时推送未读消息功能：
   - 在WebSocket连接建立后，查询用户未读消息
   - 按创建时间顺序逐条推送
   - 推送格式应包含消息完整信息

3. 实现新消息实时推送功能：
   - 当有新消息创建时，检查接收者是否在线
   - 如果在线，立即推送消息
   - 推送格式应与历史消息保持一致

要求：
- 不影响现有WebSocket功能
- 正确处理连接断开情况
- 添加适当的错误处理和日志记录
- 优化性能，避免阻塞主线程
```

### 阶段五：权限控制与安全
1. 实现消息相关接口的权限验证
2. 确保数据访问安全
3. 添加必要的日志记录

#### AI提示词
```
请帮我实现消息系统的权限控制和安全措施：

1. 权限验证：
   - 确保所有消息接口都有适当的权限检查
   - 管理员发送消息接口需要管理员权限
   - 用户操作接口需要登录用户权限
   - 用户只能访问自己的消息数据

2. 数据安全：
   - 在数据库查询中添加用户ID过滤条件
   - 防止SQL注入和其他安全漏洞
   - 验证输入参数的有效性
   - 处理边界情况和异常输入

3. 日志记录：
   - 记录重要的操作日志（消息发送、删除等）
   - 记录安全相关事件（越权访问尝试等）
   - 使用项目中现有的日志系统（loguru）

4. 错误处理：
   - 实现统一的错误响应格式
   - 适当隐藏敏感信息
   - 返回用户友好的错误消息
```

### 阶段六：测试与验证
1. 编写单元测试验证各功能
2. 进行集成测试验证完整流程
3. 验证WebSocket实时推送功能
4. 测试权限控制机制

#### AI提示词
```
请帮我为消息管理系统编写测试用例：

1. 单元测试：
   - 测试MessageService各方法的功能
   - 测试数据库操作的正确性
   - 测试边界条件和异常情况

2. 接口测试：
   - 测试管理员发送消息接口
   - 测试用户查询消息接口
   - 测试标记已读接口
   - 测试删除消息接口

3. WebSocket测试：
   - 测试用户连接时推送未读消息
   - 测试新消息实时推送
   - 测试连接断开处理

4. 权限测试：
   - 测试管理员权限验证
   - 测试用户权限验证
   - 测试越权访问防护

5. 集成测试：
   - 测试完整的消息发送和接收流程
   - 测试消息状态变更流程
   - 测试消息删除流程

要求：
- 使用pytest框架
- 遵循项目现有的测试风格
- 使用测试数据库
- 添加适当的测试数据
- 验证所有验收标准
```

## 验收标准汇总

### 服务器端WebSocket推送验收标准
1. 服务器能够通过WebSocket向在线用户推送最新的未读消息
2. 用户连接时能接收到历史未读消息
3. 新消息能够实时推送到在线用户

### 个人端WebSocket接收验收标准
1. 个人端能够通过WebSocket连接到服务器
2. 能够接收服务器推送的最新消息
3. 能够处理不同类型的推送消息（历史消息、新消息等）

### 个人端功能验收标准
1. 用户能够查询自己接收到的所有消息
2. 支持按已读/未读状态过滤消息
3. 支持分页查询
4. 能够将未读消息标记为已读
5. 能够删除单条或全部消息
6. 所有操作都有适当的权限控制