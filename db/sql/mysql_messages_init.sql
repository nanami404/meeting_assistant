-- =================================================================
-- Meeting Assistant System - MySQL消息表初始化脚本
-- 版本: 1.0.0
-- 创建日期: 2025-10-14
-- 描述: 创建消息表(messages)，参考 /doc/TODO.md#L11-22 字段定义
-- 注意: 外键约束将在应用层实现
-- =================================================================

-- 设置字符集和SQL模式
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO';

-- =================================================================
-- 1. 消息表 (messages)
-- =================================================================
DROP TABLE IF EXISTS `messages`;
CREATE TABLE `messages` (
    -- 主键字段
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID（自增）',

    -- 消息内容相关字段
    `title` VARCHAR(100) NULL COMMENT '消息标题',
    `content` TEXT NOT NULL COMMENT '消息内容',

    -- 关联字段
    `sender_id` BIGINT NOT NULL COMMENT '发送者ID',
    `receiver_id` BIGINT NOT NULL COMMENT '接收者ID',

    -- 状态字段
    `is_read` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已读(0未读/1已读)',

    -- 时间戳字段
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    -- 主键约束
    PRIMARY KEY (`id`),

    -- 索引
    KEY `idx_messages_sender_id` (`sender_id`),
    KEY `idx_messages_receiver_id` (`receiver_id`),
    KEY `idx_messages_is_read` (`is_read`),
    KEY `idx_messages_created_at` (`created_at`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息表';

-- 重新启用外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- =================================================================
-- 初始化完成提示
-- =================================================================
SELECT
    'MySQL消息表初始化完成！' as `消息`,
    (SELECT COUNT(*) FROM `messages`) as `消息表记录数`;