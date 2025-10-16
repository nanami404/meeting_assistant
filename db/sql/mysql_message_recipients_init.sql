-- =================================================================
-- Meeting Assistant System - MySQL消息接收者表初始化脚本
-- 版本: 1.0.0
-- 创建日期: 2025-10-16
-- 描述: 创建消息接收者表(message_recipients)，支持多接收者消息功能
-- 功能: 扩展现有messages表的单接收者模式为多接收者支持
-- 注意: 外键约束将在应用层实现
-- =================================================================

-- 设置字符集和SQL模式
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO';

-- =================================================================
-- 1. 消息接收者表 (message_recipients)
-- =================================================================
DROP TABLE IF EXISTS `message_recipients`;
CREATE TABLE `message_recipients` (
    -- 主键字段
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID（自增）',

    -- 关联字段
    `message_id` BIGINT NOT NULL COMMENT '消息ID（外键指向 messages.id）',
    `recipient_id` BIGINT NOT NULL COMMENT '接收者ID',

    -- 状态字段
    `is_read` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已读(0未读/1已读)',
    `read_at` TIMESTAMP NULL COMMENT '阅读时间（可选）',

    -- 时间戳字段
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（关联时间）',

    -- 主键约束
    PRIMARY KEY (`id`),

    -- 唯一约束：防止重复发送
    UNIQUE KEY `uk_message_recipient` (`message_id`, `recipient_id`),

    -- 索引
    KEY `idx_message_recipients_recipient_id` (`recipient_id`),
    KEY `idx_message_recipients_is_read` (`is_read`),
    KEY `idx_message_recipients_message_id` (`message_id`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息接收者关联表';

-- =================================================================
-- 2. 数据完整性说明
-- =================================================================
-- 注意事项：
-- 1. message_id 应该关联 messages.id，但外键约束在应用层实现
-- 2. recipient_id 应该关联用户表的id，但外键约束在应用层实现
-- 3. 唯一约束 uk_message_recipient 确保同一消息不会对同一用户重复记录
-- 4. is_read 字段：0表示未读，1表示已读
-- 5. read_at 字段：只有在is_read=1时才设置具体时间，未读时保持NULL
-- 6. 索引设计考虑了以下查询场景：
--    - 查询某消息的所有接收者
--    - 查询某用户的所有消息
--    - 查询用户的未读消息
--    - 统计消息的阅读情况
--    - 按时间范围查询消息

-- =================================================================
-- 3. 使用示例
-- =================================================================
-- 插入消息接收者记录：
-- INSERT INTO message_recipients (message_id, recipient_id) VALUES (1, 100), (1, 101), (1, 102);
--
-- 标记消息为已读：
-- UPDATE message_recipients SET is_read = 1, read_at = CURRENT_TIMESTAMP 
-- WHERE message_id = 1 AND recipient_id = 100;
--
-- 查询用户未读消息：
-- SELECT mr.*, m.title, m.content FROM message_recipients mr 
-- JOIN messages m ON mr.message_id = m.id 
-- WHERE mr.recipient_id = 100 AND mr.is_read = 0;
--
-- 统计消息阅读情况：
-- SELECT message_id, COUNT(*) as total_recipients, 
--        SUM(is_read) as read_count, 
--        (COUNT(*) - SUM(is_read)) as unread_count
-- FROM message_recipients GROUP BY message_id;

-- 重新启用外键检查
SET FOREIGN_KEY_CHECKS = 1;