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
-- 5. 插入初始用户数据
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
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwdQwZgDiocCRKxYa', -- 默认密码: admin123456
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
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwdQwZgDiocCRKxYa', -- 默认密码: admin123456
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
    DBMS_OUTPUT.PUT_LINE('索引已创建: 10个');
    DBMS_OUTPUT.PUT_LINE('触发器已创建: 1个');

    -- 显示用户数量统计
    DECLARE
        v_total_count NUMBER := 0;
        v_admin_count NUMBER := 0;
        v_active_count NUMBER := 0;
    BEGIN
        SELECT COUNT(*) INTO v_total_count FROM users;
        SELECT COUNT(*) INTO v_admin_count FROM users WHERE role = 'admin';
        SELECT COUNT(*) INTO v_active_count FROM users WHERE status = 'active';

        DBMS_OUTPUT.PUT_LINE('用户表记录数: ' || v_total_count);
        DBMS_OUTPUT.PUT_LINE('管理员数量: ' || v_admin_count);
        DBMS_OUTPUT.PUT_LINE('活跃用户数: ' || v_active_count);
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