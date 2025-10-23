import hashlib
import time


def calculate_md5(app_id, app_secret, timestamp):
    """
    计算 md5(appId + appsecret + timestamp) 的哈希值

    参数:
        app_id (str): 应用ID
        app_secret (str): 应用密钥
        timestamp (str): 时间戳字符串

    返回:
        str: 计算得到的32位小写MD5哈希值
    """
    # 拼接字符串
    combined_str = app_id + app_secret + timestamp

    # 创建MD5哈希对象
    md5_hash = hashlib.md5()

    # 更新哈希对象内容（需要先转换为字节流）
    md5_hash.update(combined_str.encode('utf-8'))

    # 获取16进制表示的哈希值
    return md5_hash.hexdigest()


# 使用示例
if __name__ == "__main__":
    # 示例参数
    app_id = "tainsureAssistant"
    app_secret = "sek9*2JxL8K6p#Lp=ia!-yX@0H0DDoJDDR8d#YGjml!p"
    timestamp = str(int(time.time() * 1000))    # 示例时间戳
    print(timestamp)

    # 计算MD5
    result = calculate_md5(app_id, app_secret, timestamp)
    print(f"计算结果: {result}")
