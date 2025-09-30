-- =================================================================
-- Meeting Assistant System - MySQL用户表初始化脚本（简化版）
-- 版本: 1.1.0
-- 创建日期: 2024-09-26
-- 描述: 基于User SQLAlchemy模型创建的用户管理表结构（仅包含基础结构）
-- 注意: 外键约束和检查约束将在应用层实现
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
    `id` VARCHAR(50) NOT NULL COMMENT '用户UUID主键',

    -- 基本信息字段
    `name` VARCHAR(100) NOT NULL COMMENT '用户姓名',
    `user_name` VARCHAR(50) NOT NULL COMMENT '用户账号',
    `gender` VARCHAR(20) DEFAULT NULL COMMENT '性别：male-男性，female-女性，other-其他',
    `phone` VARCHAR(20) DEFAULT NULL COMMENT '手机号码',
    `email` VARCHAR(255) NOT NULL COMMENT '邮箱地址',
    `id_number` VARCHAR(18) DEFAULT NULL COMMENT '4A账号/工号',
    `company` VARCHAR(200) DEFAULT NULL COMMENT '所属单位名称',

    -- 权限和状态字段
    `role` VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '用户角色：admin-管理员，user-普通用户',
    `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '用户状态：active-激活，inactive-未激活，suspended-暂停',

    -- 安全信息字段
    `password_hash` VARCHAR(255) DEFAULT NULL COMMENT '密码哈希值（bcrypt加密）',

    -- 时间戳字段
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    -- 关联字段
    `created_by` VARCHAR(50) DEFAULT NULL COMMENT '创建者用户ID',
    `updated_by` VARCHAR(50) DEFAULT NULL COMMENT '更新者用户ID',

    -- 主键约束
    PRIMARY KEY (`id`),

    -- 唯一键约束
    UNIQUE KEY `uk_users_email` (`email`),
    UNIQUE KEY `uk_users_phone` (`phone`),
    UNIQUE KEY `uk_users_user_name` (`user_name`),
    UNIQUE KEY `uk_users_id_number` (`id_number`),

    -- 普通索引（对应SQLAlchemy的Index定义）
    KEY `idx_users_email` (`email`),
    KEY `idx_users_phone` (`phone`),
    KEY `idx_users_user_name` (`user_name`),
    KEY `idx_users_role` (`role`),
    KEY `idx_users_status` (`status`),
    KEY `idx_users_company` (`company`),
    KEY `idx_users_created_at` (`created_at`),
    KEY `idx_users_created_by` (`created_by`),
    KEY `idx_users_updated_by` (`updated_by`)

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
     ADD COLUMN `created_by` VARCHAR(50) DEFAULT NULL COMMENT "创建者用户ID" AFTER `updated_at`,
     ADD COLUMN `updated_by` VARCHAR(50) DEFAULT NULL COMMENT "更新者用户ID" AFTER `created_by`,
     ADD KEY `idx_meetings_created_by` (`created_by`),
     ADD KEY `idx_meetings_updated_by` (`updated_by`)',
    'SELECT "meetings表用户字段已存在" as message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- =================================================================
-- 3. 用户会议关联表 (user_meeting_associations)
-- 实现用户与会议的多对多关系（简化版）
-- =================================================================
DROP TABLE IF EXISTS `user_meeting_associations`;
CREATE TABLE `user_meeting_associations` (
    -- 主键字段（自增long类型）
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '唯一ID（自增主键）',
    
    -- 必要关联字段
    `user_id` VARCHAR(50) NOT NULL COMMENT '用户ID，关联users表',
    `meeting_id` VARCHAR(50) NOT NULL COMMENT '会议ID，关联meetings表',
    
    -- 额外字段
    `notes` TEXT DEFAULT NULL COMMENT '备注信息（如请假原因、特殊说明等）',
    
    -- 时间戳字段
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 关联字段
    `created_by` VARCHAR(50) DEFAULT NULL COMMENT '创建者用户ID',
    `updated_by` VARCHAR(50) DEFAULT NULL COMMENT '更新者用户ID',
    
    -- 主键约束
    PRIMARY KEY (`id`),
    
    -- 唯一约束（确保同一用户在同一会议中只有一条记录）
    UNIQUE KEY `uk_uma_user_meeting` (`user_id`, `meeting_id`),
    
    -- 普通索引
    KEY `idx_uma_user_id` (`user_id`),
    KEY `idx_uma_meeting_id` (`meeting_id`),
    KEY `idx_uma_created_at` (`created_at`),
    KEY `idx_uma_created_by` (`created_by`),
    KEY `idx_uma_updated_by` (`updated_by`)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户会议关联表（多对多关系，简化版）';

-- =================================================================
-- 4. 插入初始用户数据
-- =================================================================
-- 插入系统管理员（如果不存在）
INSERT IGNORE INTO `users` (
    `id`,
    `name`,
    `user_name`,
    `email`,
    `role`,
    `status`,
    `password_hash`,
    `created_at`,
    `updated_at`
) VALUES (
    'admin-user-system-00000000001',
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
    `id_number`,
    `company`,
    `role`,
    `status`,
    `password_hash`,
    `created_by`,
    `created_at`,
    `updated_at`
) VALUES (
    'demo-user-test-000000000002',
    '测试用户',
    'demo_user',
    'demo@meeting-system.com',
    'other',
    '13800138000',
    '20240001',
    '示例科技有限公司',
    'user',
    'active',
    '$2b$12$dqxaCN4B14D9jOolnaI1rujOK.ho/g4lLtSqZ4VKSjyJy7lgxT6F6', -- 默认密码: 123456
    'admin-user-system-00000000001',
    NOW(),
    NOW()
);

-- =================================================================
-- 5. 插入用户会议关联示例数据
-- =================================================================
-- 注意：这里假设meetings表中已有一些会议数据，实际使用时需要根据具体的meeting_id进行调整
-- 示例：创建用户与会议的关联记录

-- 插入示例关联数据（如果meetings表中有对应的会议记录）
-- INSERT IGNORE INTO `user_meeting_associations` (
--     `user_id`,
--     `meeting_id`,
--     `notes`,
--     `created_by`,
--     `created_at`,
--     `updated_at`
-- ) VALUES 
-- -- 系统管理员关联会议
-- (
--     'admin-user-system-00000000001',
--     'meeting-example-id-001',  -- 需要替换为实际的meeting_id
--     '会议组织者',
--     'admin-user-system-00000000001',
--     NOW(),
--     NOW()
-- ),
-- -- 测试用户关联会议
-- (
--     'demo-user-test-000000000002',
--     'meeting-example-id-001',  -- 需要替换为实际的meeting_id
--     '会议参与者',
--     'admin-user-system-00000000001',
--     NOW(),
--     NOW()
-- );

-- 重新启用外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- =================================================================
-- 初始化完成提示
-- =================================================================
SELECT
    'MySQL用户表初始化完成！' as `消息`,
    (SELECT COUNT(*) FROM `users`) as `用户表记录数`,
    (SELECT COUNT(*) FROM `users` WHERE `role` = 'admin') as `管理员数量`,
    (SELECT COUNT(*) FROM `users` WHERE `status` = 'active') as `活跃用户数`,
    (SELECT COUNT(*) FROM `user_meeting_associations`) as `用户会议关联记录数`;

-- 显示用户列表
SELECT
    `id`,
    `name`,
    `email`,
    `role`,
    `status`,
    `created_at`
FROM `users`
ORDER BY `created_at` DESC;

-- =================================================================
-- 用户会议关联表信息
-- =================================================================
-- user_meeting_associations 表用于管理用户与会议的多对多关联关系
-- 
-- 表结构说明：
-- - id: 自增主键（BIGINT类型）
-- - user_id: 用户ID，关联users表
-- - meeting_id: 会议ID，关联meetings表
-- - notes: 备注信息（如请假原因、特殊说明等）
-- - created_at: 创建时间
-- - updated_at: 更新时间
-- - created_by: 创建者用户ID
-- - updated_by: 更新者用户ID
-- 
-- 索引优化：
-- - 主键索引：id
-- - 唯一索引：user_id + meeting_id（防止重复关联）
-- - 单字段索引：user_id, meeting_id（查询优化）
-- - 复合索引：created_at（时间范围查询）
-- 
-- 使用场景：
-- - 查询用户参与的所有会议
-- - 查询会议的所有参与者
-- - 记录用户与会议的关联备注信息
-- - 追踪关联记录的创建和更新历史

SELECT
    'user_meeting_associations表已创建，支持用户与会议的多对多关联' as `关联表状态`;