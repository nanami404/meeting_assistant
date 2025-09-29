from test.transfer_live_audio import LiveAudioTranscriber
import pytest
import json
import asyncio

pytestmark = pytest.mark.asyncio

async def test_transcription():
    """测试实时转录功能"""
    # 1. 初始化转录器（指定ASR服务地址和录音时长）
    transcriber = LiveAudioTranscriber(
        server_url="ws://192.168.18.246:10095",  # 替换为你的ASR服务地址
        record_duration=15,  # 录音5秒
        # 可选：自定义回调（打印服务端原始结果，方便调试）
        callback=lambda res: print(f"[调试] 服务端原始结果：{json.dumps(res, ensure_ascii=False)}")
    )

    # 2. 启动转录
    print("=== 开始测试实时转录 ===")
    final_result = await transcriber.start_transcription()

    # 3. 输出测试结果
    print("\n=== 测试结果 ===")
    if final_result:
        print(f"最终转录文本：{final_result}")
    else:
        print("未获取到转录结果")

# 执行测试
if __name__ == "__main__":
    try:
        asyncio.run(test_transcription())
    except Exception as e:
        print(f"测试出错：{str(e)}")