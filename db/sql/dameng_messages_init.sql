-- =================================================================
-- Meeting Assistant System - 达梦数据库消息表初始化脚本
-- 版本: 1.0.0
-- 创建日期: 2025-10-14
-- 描述: 创建消息表(messages)，参考 /doc/TODO.md#L11-22 字段定义，兼容DM8语法
-- 注意: 外键约束将在应用层实现
-- =================================================================

-- 事务设置
SET AUTOCOMMIT OFF;

-- =================================================================
-- 1. 消息表 (messages)
-- =================================================================

-- 删除已存在的表（如果存在）
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE messages CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        NULL; -- 忽略表不存在的错误
END;
/

-- 创建消息表（字段与MySQL版本保持一致，类型适配DM8）
CREATE TABLE messages (
    -- 主键字段（通过IDENTITY实现自增）
    id            BIGINT    IDENTITY(1,1)     NOT NULL,

    -- 消息内容相关字段
    title         VARCHAR2(100)      NOT NULL,
    content       CLOB               NOT NULL,

    -- 关联字段
    sender_id     NUMBER(19)         NOT NULL,

    -- 状态字段
    is_read       NUMBER(1)          DEFAULT 0 NOT NULL,

    -- 时间戳字段
    created_at    TIMESTAMP          DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at    TIMESTAMP          DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- 主键约束
    CONSTRAINT pk_messages PRIMARY KEY (id)
);

-- 添加表和字段注释
COMMENT ON TABLE messages IS '消息表';
COMMENT ON COLUMN messages.id IS '主键ID（自增）';
COMMENT ON COLUMN messages.title IS '消息标题';
COMMENT ON COLUMN messages.content IS '消息内容';
COMMENT ON COLUMN messages.sender_id IS '发送者ID';
COMMENT ON COLUMN messages.is_read IS '是否已读(0未读/1已读)';
COMMENT ON COLUMN messages.created_at IS '创建时间';
COMMENT ON COLUMN messages.updated_at IS '更新时间';

-- 普通索引（与MySQL版本保持一致）
CREATE INDEX idx_messages_sender_id   ON messages(sender_id);
CREATE INDEX idx_messages_is_read     ON messages(is_read);
CREATE INDEX idx_messages_created_at  ON messages(created_at);

-- 自动更新时间触发器（模拟MySQL ON UPDATE CURRENT_TIMESTAMP）
CREATE OR REPLACE TRIGGER tr_messages_before_update
    BEFORE UPDATE ON messages
    FOR EACH ROW
BEGIN
    :NEW.updated_at := CURRENT_TIMESTAMP;
END;
/

-- 事务提交
COMMIT;

-- =================================================================
-- 初始化完成提示
-- =================================================================
SELECT
    '达梦数据库消息表初始化完成！' AS "消息",
    (SELECT COUNT(*) FROM messages) AS "消息表记录数"
FROM dual;

-- 显示消息列表（若有数据）
SELECT
    id,
    title,
    sender_id,
    is_read,
    created_at
FROM messages
ORDER BY created_at DESC;