开发文档：消息通知功能实现

一、功能概述
实现一个完整的消息通知系统，包含以下核心功能：
1. 用户消息中心：个人用户可查看所有消息
2. 消息发送接口：支持向指定用户发送通知
3. 消息状态管理：区分已读/未读状态

二、数据库设计

1. 消息表(messages)
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | bigint | 是 | 主键ID（自增） |
| title | varchar(100) | 是 | 消息标题 |
| content | text | 是 | 消息内容 |
| sender_id | bigint | 是 | 发送者ID |
| receiver_id | bigint | 是 | 接收者ID |
| is_read | tinyint(1) | 是 | 是否已读(0未读/1已读) |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

三、API接口设计

1. 发送消息接口
- 路径：/api/messages/send
- 方法：POST
- 参数：
  - title: 消息标题
  - content: 消息内容
  - receiver_id: 接收者ID
- 返回：操作结果

2. 获取用户消息列表
- 路径：/api/messages/list
- 方法：GET
- 参数：
  - page: 页码
  - page_size: 每页数量
  - is_read: 是否已读(可选)
- 返回：分页消息列表

3. 标记消息为已读
- 路径：/api/messages/mark-read
- 方法：POST
- 参数：
  - message_id: 消息ID
- 返回：操作结果

4. 全部标记消息为已读
- 路径：/api/messages/mark-all-read
- 方法：POST
- 参数：
  - 无（对当前登录用户的所有未读消息）
- 返回：操作结果

5. 删除单条消息
- 路径：/api/messages/delete
- 方法：POST
- 参数：
  - message_id: 消息ID
- 返回：操作结果

6. 批量删除消息（按类型）
- 路径：/api/messages/delete-by-type
- 方法：POST
- 参数：
  - type: 删除类型（read：删除所有已读；unread：删除所有未读；all：删除全部）
- 返回：删除条数

四、功能实现要点

1. 消息发送功能
- 实现消息发送服务类
- 支持同步发送
- 记录发送日志

2. 消息中心功能
- 按用户ID查询消息
- 支持分页查询
- 默认按创建时间倒序排列
- 区分已读/未读状态

3. 状态与清理功能
- 全部标记已读：针对当前用户批量更新 is_read = 1（仅未读）
- 删除单条消息：校验消息归属后删除
- 批量删除消息：按类型（read/unread/all）限定当前用户范围执行

五、测试验证方案

1. 单元测试
- 测试消息发送功能
- 测试消息查询功能
- 测试状态变更功能
- 测试全部标记已读功能
- 测试删除单条消息功能
- 测试按类型批量删除功能
