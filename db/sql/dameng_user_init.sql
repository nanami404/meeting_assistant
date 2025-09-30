-- =================================================================
-- Meeting Assistant System - 达梦数据库用户表初始化脚本（简化版）
-- 版本: 1.1.0
-- 创建日期: 2024-09-26
-- 描述: 基于User SQLAlchemy模型创建的用户管理表结构（仅包含基础结构）
-- 兼容版本: 达梦DM8.0及以上
-- 注意: 外键约束和检查约束将在应用层实现
-- =================================================================

-- 设置达梦数据库参数
SET IDENTITY_INSERT OFF;
SET AUTOCOMMIT OFF;

-- =================================================================
-- 1. 用户主表 (users)
-- 对应SQLAlchemy模型: User
-- =================================================================

-- 删除已存在的表（如果存在）
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE users CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        NULL; -- 忽略表不存在的错误
END;
/

-- 创建用户表
CREATE TABLE users (
    -- 主键字段
    id                  VARCHAR2(50)        NOT NULL,

    -- 基本信息字段
    name                VARCHAR2(100)       NOT NULL,
    user_name           VARCHAR2(50)        NOT NULL,
    gender              VARCHAR2(20)        DEFAULT NULL,
    phone               VARCHAR2(20)        DEFAULT NULL,
    email               VARCHAR2(255)       NOT NULL,
    id_number           VARCHAR2(18)        DEFAULT NULL,
    company             VARCHAR2(200)       DEFAULT NULL,

    -- 权限和状态字段
    role                VARCHAR2(20)        DEFAULT 'user' NOT NULL,
    status              VARCHAR2(20)        DEFAULT 'active' NOT NULL,

    -- 安全信息字段
    password_hash       VARCHAR2(255)       DEFAULT NULL,

    -- 时间戳字段（使用达梦数据库语法设置默认值）
    created_at          TIMESTAMP           DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at          TIMESTAMP           DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- 关联字段
    created_by          VARCHAR2(50)        DEFAULT NULL,
    updated_by          VARCHAR2(50)        DEFAULT NULL,

    -- 主键约束
    CONSTRAINT pk_users PRIMARY KEY (id),

    -- 唯一键约束
    CONSTRAINT uk_users_email UNIQUE (email),
    CONSTRAINT uk_users_phone UNIQUE (phone),
    CONSTRAINT uk_users_user_name UNIQUE (user_name),
    CONSTRAINT uk_users_id_number UNIQUE (id_number)
);

-- 添加表和字段注释
COMMENT ON TABLE users IS '用户信息表';
COMMENT ON COLUMN users.id IS '用户UUID主键';
COMMENT ON COLUMN users.name IS '用户姓名';
COMMENT ON COLUMN users.user_name IS '用户账号';
COMMENT ON COLUMN users.gender IS '性别：male-男性，female-女性，other-其他';
COMMENT ON COLUMN users.phone IS '手机号码';
COMMENT ON COLUMN users.email IS '邮箱地址';
COMMENT ON COLUMN users.id_number IS '4A账号/工号';
COMMENT ON COLUMN users.company IS '所属单位名称';
COMMENT ON COLUMN users.role IS '用户角色：admin-管理员，user-普通用户';
COMMENT ON COLUMN users.status IS '用户状态：active-激活，inactive-未激活，suspended-暂停';
COMMENT ON COLUMN users.password_hash IS '密码哈希值（bcrypt加密）';
COMMENT ON COLUMN users.created_at IS '创建时间';
COMMENT ON COLUMN users.updated_at IS '更新时间';
COMMENT ON COLUMN users.created_by IS '创建者用户ID';
COMMENT ON COLUMN users.updated_by IS '更新者用户ID';

-- =================================================================
-- 2. 创建索引（对应SQLAlchemy的Index定义）
-- =================================================================

-- 邮箱索引
CREATE INDEX idx_users_email ON users(email);

-- 手机号索引
CREATE INDEX idx_users_phone ON users(phone);

-- 用户账号索引
CREATE INDEX idx_users_user_name ON users(user_name);

-- 角色索引
CREATE INDEX idx_users_role ON users(role);

-- 状态索引
CREATE INDEX idx_users_status ON users(status);

-- 公司索引
CREATE INDEX idx_users_company ON users(company);

-- 创建时间索引
CREATE INDEX idx_users_created_at ON users(created_at);

-- 创建者索引
CREATE INDEX idx_users_created_by ON users(created_by);

-- 更新者索引
CREATE INDEX idx_users_updated_by ON users(updated_by);

-- 复合索引：角色+状态（常用查询优化）
CREATE INDEX idx_users_role_status ON users(role, status);

-- 复合索引：公司+状态（部门查询优化）
CREATE INDEX idx_users_company_status ON users(company, status);

-- =================================================================
-- 3. 创建自动更新时间的触发器
-- =================================================================

CREATE OR REPLACE TRIGGER tr_users_before_update
    BEFORE UPDATE ON users
    FOR EACH ROW
BEGIN
    -- 自动更新updated_at字段
    :NEW.updated_at := CURRENT_TIMESTAMP;
END;
/

-- =================================================================
-- 3. 用户会议关联表 (user_meeting_associations)
-- 实现用户与会议的多对多关系（简化版）
-- =================================================================

-- 删除已存在的表（如果存在）
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE user_meeting_associations CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        NULL; -- 忽略表不存在的错误
END;
/

-- 创建用户会议关联表
CREATE TABLE user_meeting_associations (
    -- 主键字段（自增序列）
    id                  NUMBER(19)          NOT NULL,
    
    -- 必要关联字段
    user_id             VARCHAR2(50)        NOT NULL,
    meeting_id          VARCHAR2(50)        NOT NULL,
    
    -- 额外字段
    notes               CLOB                DEFAULT NULL,
    
    -- 时间戳字段
    created_at          TIMESTAMP           DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at          TIMESTAMP           DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- 关联字段
    created_by          VARCHAR2(50)        DEFAULT NULL,
    updated_by          VARCHAR2(50)        DEFAULT NULL,
    
    -- 主键约束
    CONSTRAINT pk_user_meeting_associations PRIMARY KEY (id),
    
    -- 唯一约束（确保同一用户在同一会议中只有一条记录）
    CONSTRAINT uk_uma_user_meeting UNIQUE (user_id, meeting_id)
);

-- 添加表和字段注释
COMMENT ON TABLE user_meeting_associations IS '用户会议关联表（多对多关系，简化版）';
COMMENT ON COLUMN user_meeting_associations.id IS '唯一ID（自增主键）';
COMMENT ON COLUMN user_meeting_associations.user_id IS '用户ID，关联users表';
COMMENT ON COLUMN user_meeting_associations.meeting_id IS '会议ID，关联meetings表';
COMMENT ON COLUMN user_meeting_associations.notes IS '备注信息（如请假原因、特殊说明等）';
COMMENT ON COLUMN user_meeting_associations.created_at IS '创建时间';
COMMENT ON COLUMN user_meeting_associations.updated_at IS '更新时间';
COMMENT ON COLUMN user_meeting_associations.created_by IS '创建者用户ID';
COMMENT ON COLUMN user_meeting_associations.updated_by IS '更新者用户ID';

-- 创建自增序列
CREATE SEQUENCE seq_user_meeting_associations
    START WITH 1
    INCREMENT BY 1
    NOCACHE
    NOCYCLE;

-- 创建触发器实现自增主键
CREATE OR REPLACE TRIGGER tr_uma_before_insert
    BEFORE INSERT ON user_meeting_associations
    FOR EACH ROW
BEGIN
    IF :NEW.id IS NULL THEN
        SELECT seq_user_meeting_associations.NEXTVAL INTO :NEW.id FROM DUAL;
    END IF;
END;
/

-- 创建自动更新时间的触发器
CREATE OR REPLACE TRIGGER tr_uma_before_update
    BEFORE UPDATE ON user_meeting_associations
    FOR EACH ROW
BEGIN
    -- 自动更新updated_at字段
    :NEW.updated_at := CURRENT_TIMESTAMP;
END;
/

-- 创建索引
CREATE INDEX idx_uma_user_id ON user_meeting_associations(user_id);
CREATE INDEX idx_uma_meeting_id ON user_meeting_associations(meeting_id);
CREATE INDEX idx_uma_created_at ON user_meeting_associations(created_at);
CREATE INDEX idx_uma_created_by ON user_meeting_associations(created_by);
CREATE INDEX idx_uma_updated_by ON user_meeting_associations(updated_by);

-- =================================================================
-- 4. 更新现有meetings表，添加用户关联字段
-- =================================================================

-- 检查meetings表是否存在，如果存在则添加用户关联字段
DECLARE
    v_count NUMBER;
    v_col_count NUMBER;
BEGIN
    -- 检查meetings表是否存在
    SELECT COUNT(*) INTO v_count
    FROM USER_TABLES
    WHERE TABLE_NAME = UPPER('meetings');

    IF v_count > 0 THEN
        -- 检查created_by字段是否存在
        SELECT COUNT(*) INTO v_col_count
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = UPPER('meetings')
        AND COLUMN_NAME = UPPER('created_by');

        -- 如果字段不存在则添加
        IF v_col_count = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE meetings ADD (
                created_by VARCHAR2(50) DEFAULT NULL,
                updated_by VARCHAR2(50) DEFAULT NULL
            )';

            -- 添加字段注释
            EXECUTE IMMEDIATE 'COMMENT ON COLUMN meetings.created_by IS ''创建者用户ID''';
            EXECUTE IMMEDIATE 'COMMENT ON COLUMN meetings.updated_by IS ''更新者用户ID''';

            -- 添加索引
            EXECUTE IMMEDIATE 'CREATE INDEX idx_meetings_created_by ON meetings(created_by)';
            EXECUTE IMMEDIATE 'CREATE INDEX idx_meetings_updated_by ON meetings(updated_by)';
        END IF;
    END IF;
END;
/

-- =================================================================
-- 5. 插入用户会议关联示例数据
-- =================================================================
-- 注意：这里假设meetings表中已有一些会议数据，实际使用时需要根据具体的meeting_id进行调整
-- 示例：创建用户与会议的关联记录

-- 插入示例关联数据（如果meetings表中有对应的会议记录）
-- INSERT INTO user_meeting_associations (
--     user_id,
--     meeting_id,
--     notes,
--     created_by,
--     created_at,
--     updated_at
-- ) VALUES 
-- -- 系统管理员关联会议
-- (
--     'admin-user-system-00000000001',
--     'meeting-example-id-001',  -- 需要替换为实际的meeting_id
--     '会议组织者',
--     'admin-user-system-00000000001',
--     CURRENT_TIMESTAMP,
--     CURRENT_TIMESTAMP
-- );
-- 
-- INSERT INTO user_meeting_associations (
--     user_id,
--     meeting_id,
--     notes,
--     created_by,
--     created_at,
--     updated_at
-- ) VALUES 
-- -- 测试用户关联会议
-- (
--     'demo-user-test-000000000002',
--     'meeting-example-id-001',  -- 需要替换为实际的meeting_id
--     '会议参与者',
--     'admin-user-system-00000000001',
--     CURRENT_TIMESTAMP,
--     CURRENT_TIMESTAMP
-- );

-- =================================================================
-- 6. 插入初始用户数据
-- =================================================================

-- 插入系统管理员
INSERT INTO users (
    id,
    name,
    user_name,
    email,
    role,
    status,
    password_hash,
    created_at,
    updated_at
) VALUES (
    'admin-user-system-00000000001',
    '系统管理员',
    'admin',
    'admin@meeting-system.com',
    'admin',
    'active',
    '$2b$12$FeZo7nHnCkI9UhlSZgtyoOKAtIoScX5dAwT6n4EqxItVtG.XdfB6a', -- 默认密码: Admin123456
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

-- 插入测试普通用户
INSERT INTO users (
    id,
    name,
    user_name,
    email,
    gender,
    phone,
    id_number,
    company,
    role,
    status,
    password_hash,
    created_by,
    created_at,
    updated_at
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
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

-- =================================================================
-- 提交事务并初始化完成
-- =================================================================

COMMIT;

-- 启用DBMS_OUTPUT以显示消息
SET SERVEROUTPUT ON;

-- 显示初始化结果
BEGIN
    DBMS_OUTPUT.PUT_LINE('=== 达梦数据库用户表初始化完成！===');
    DBMS_OUTPUT.PUT_LINE('');

    DBMS_OUTPUT.PUT_LINE('=== 初始化统计 ===');
    DBMS_OUTPUT.PUT_LINE('users表已创建');
    DBMS_OUTPUT.PUT_LINE('user_meeting_associations表已创建');
    DBMS_OUTPUT.PUT_LINE('索引已创建: 15个');
    DBMS_OUTPUT.PUT_LINE('触发器已创建: 3个');
    DBMS_OUTPUT.PUT_LINE('序列已创建: 1个');

    -- 显示用户数量统计
    DECLARE
        v_total_count NUMBER := 0;
        v_admin_count NUMBER := 0;
        v_active_count NUMBER := 0;
        v_uma_count NUMBER := 0;
    BEGIN
        SELECT COUNT(*) INTO v_total_count FROM users;
        SELECT COUNT(*) INTO v_admin_count FROM users WHERE role = 'admin';
        SELECT COUNT(*) INTO v_active_count FROM users WHERE status = 'active';
        SELECT COUNT(*) INTO v_uma_count FROM user_meeting_associations;

        DBMS_OUTPUT.PUT_LINE('用户表记录数: ' || v_total_count);
        DBMS_OUTPUT.PUT_LINE('管理员数量: ' || v_admin_count);
        DBMS_OUTPUT.PUT_LINE('活跃用户数: ' || v_active_count);
        DBMS_OUTPUT.PUT_LINE('用户会议关联记录数: ' || v_uma_count);
    END;
END;
/

-- 显示用户列表
SELECT
    id,
    name,
    email,
    role,
    status,
    created_at
FROM users
ORDER BY created_at DESC;

-- =================================================================
-- 用户会议关联表信息
-- =================================================================
-- user_meeting_associations 表用于管理用户与会议的多对多关联关系
-- 
-- 表结构说明：
-- - id: 自增主键（NUMBER(19)类型，通过序列实现）
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

BEGIN
    DBMS_OUTPUT.PUT_LINE('user_meeting_associations表已创建，支持用户与会议的多对多关联');
END;
/