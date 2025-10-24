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
    -- 主键字段（通过IDENTITY实现自增）
    `id` BIGINT NOT NULL AUTO_INCREMENT,

    -- 消息内容相关字段
    `title` VARCHAR(100) NOT NULL,
    `content` TEXT NOT NULL,

    -- 关联字段
    `sender_id` VARCHAR(36) NOT NULL COMMENT '发送者ID（UUID）',

    -- 状态字段
    `is_read` TINYINT(1) DEFAULT 0 NOT NULL COMMENT '是否已读(0未读/1已读)',

    -- 时间戳字段
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,

    -- 主键约束
    PRIMARY KEY (`id`),

    -- 索引
    KEY `idx_messages_sender_id` (`sender_id`),
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