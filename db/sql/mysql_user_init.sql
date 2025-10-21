-- =================================================================
-- Meeting Assistant System - MySQL用户表初始化脚本（简化版）
-- 版本: 1.1.0
-- 创建日期: 2024-09-26
-- 描述: 基于User SQLAlchemy模型创建的用户管理表结构（仅包含基础结构）
-- =================================================================

-- 设置字符集和SQL模式
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO';

-- =================================================================
-- 1. 用户主表 (users)
-- 对应SQLAlchemy模型: User
-- =================================================================
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    -- 主键字段
    `id` VARCHAR(255) NOT NULL COMMENT '用户ID主键（字符串类型）',

    -- 基本信息字段
    `name` VARCHAR(100) NOT NULL COMMENT '用户姓名',
    `user_name` VARCHAR(50) NOT NULL COMMENT '用户账号',
    `gender` VARCHAR(20) DEFAULT NULL COMMENT '性别：male-男性，female-女性，other-其他',
    `phone` VARCHAR(20) DEFAULT NULL COMMENT '手机号码',
    `email` VARCHAR(255) DEFAULT NULL COMMENT '邮箱地址',
    `company` VARCHAR(200) DEFAULT NULL COMMENT '所属单位名称',

    -- 权限和状态字段
    `user_role` VARCHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user' COMMENT '用户角色：admin-管理员，user-普通用户',
    `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '用户状态：active-激活，inactive-未激活，suspended-暂停',

    -- 安全信息字段
    `password_hash` VARCHAR(255) DEFAULT NULL COMMENT '密码哈希值（bcrypt加密）',

    -- 时间戳字段
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    -- 关联字段
    `created_by` VARCHAR(255) DEFAULT NULL COMMENT '创建者用户ID',
    `updated_by` VARCHAR(255) DEFAULT NULL COMMENT '更新者用户ID',

    -- 主键约束
    PRIMARY KEY (`id`),

    -- 唯一键约束
    UNIQUE KEY `uk_users_user_name` (`user_name`),

    -- 普通索引（对应SQLAlchemy的Index定义）
    KEY `idx_users_user_name` (`user_name`),
    KEY `idx_users_role` (`user_role`),
    KEY `idx_users_status` (`status`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户信息表';

-- =================================================================
-- 2. 更新现有meetings表，添加用户关联字段
-- =================================================================
-- 检查meetings表是否存在created_by字段，如果不存在则添加
SET @sql = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'meetings'
     AND COLUMN_NAME = 'created_by') = 0,
    'ALTER TABLE `meetings`
     ADD COLUMN `created_by` VARCHAR(255) DEFAULT NULL COMMENT "创建者用户ID" AFTER `updated_at`,
     ADD COLUMN `updated_by` VARCHAR(255) DEFAULT NULL COMMENT "更新者用户ID" AFTER `created_by`,
     ADD KEY `idx_meetings_created_by` (`created_by`),
     ADD KEY `idx_meetings_updated_by` (`updated_by`)',
    'SELECT "meetings表用户字段已存在" as message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- =================================================================
-- 4. 插入初始用户数据
-- =================================================================
-- 插入系统管理员（如果不存在）
INSERT IGNORE INTO `users` (
    `id`,
    `name`,
    `user_name`,
    `email`,
    `user_role`,
    `status`,
    `password_hash`,
    `created_at`,
    `updated_at`
) VALUES (
    '1',
    '系统管理员',
    'admin',
    'admin@meeting-system.com',
    'admin',
    'active',
    '$2b$12$FeZo7nHnCkI9UhlSZgtyoOKAtIoScX5dAwT6n4EqxItVtG.XdfB6a', -- 默认密码: Admin123456
    NOW(),
    NOW()
);

-- 插入测试普通用户（如果不存在）
INSERT IGNORE INTO `users` (
    `id`,
    `name`,
    `user_name`,
    `email`,
    `gender`,
    `phone`,
    `company`,
    `user_role`,
    `status`,
    `password_hash`,
    `created_by`,
    `created_at`,
    `updated_at`
) VALUES (
    '2',
    '测试用户',
    'demo_user',
    'demo@meeting-system.com',
    'other',
    '13800138000',
    '示例科技有限公司',
    'user',
    'active',
    '$2b$12$dqxaCN4B14D9jOolnaI1rujOK.ho/g4lLtSqZ4VKSjyJy7lgxT6F6', -- 默认密码: 123456
    '1', -- 引用系统管理员的ID（此处UUID假设为'1'，可以调整为系统生成的UUID）
    NOW(),
    NOW()
);

-- 重新启用外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- =================================================================
-- 初始化完成提示
-- =================================================================
SELECT
    'MySQL用户表初始化完成！' as `消息`,
    (SELECT COUNT(*) FROM `users`) as `用户表记录数`,
    (SELECT COUNT(*) FROM `users` WHERE `user_role` = 'admin') as `管理员数量`,
    (SELECT COUNT(*) FROM `users` WHERE `status` = 'active') as `活跃用户数`;

-- 显示用户列表
SELECT
    `id`,
    `name`,
    `email`,
    `user_role`,
    `status`,
    `created_at`
FROM `users`
ORDER BY `created_at` DESC;
