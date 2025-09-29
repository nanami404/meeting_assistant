#-*-coding:utf-8 -*-
"""
语音识别客户端
实时采集麦克风音频，通过WebSocket发送到ASR服务端进行转录
整合实时音频解析能力，替换原transcribe_live_audio函数功能
"""
# 内部库
import time
import argparse
import asyncio
import json
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional
import logging

# 第三方库
import pyaudio
import websockets
from websockets.exceptions import ConnectionClosed

# 配置日志（同时输出到文件和控制台）
logger = logging.getLogger("voice_assistant")
logger.setLevel(logging.INFO)

# 文件处理器（写入日志文件）
file_handler = logging.FileHandler("../services/voice_assistant.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)

# 控制台处理器（实时打印）
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(levelname)s: %(message)s")
console_handler.setFormatter(console_formatter)

# 添加处理器到日志器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 字符串常量（统一管理提示信息）
STR_MICROPHONE_UNAVAILABLE = "麦克风设备不可用"
STR_RECORDING_START = "开始录音... (按 Ctrl+C 停止，默认录制5秒，可通过--duration调整)"
STR_RECORDING_STOP = "录音已停止，等待最终转录结果..."
STR_CONNECT_TIMEOUT = "连接ASR服务端超时（10秒）"
STR_CONNECT_FAIL = "ASR服务端连接失败"
STR_AUDIO_INIT_FAIL = "音频设备初始化失败"
STR_FINAL_RESULT = "最终转录结果："
STR_NO_RESULT = "未获取到有效转录结果"


class LiveAudioTranscriber:
    """
    实时音频转录器
    替代原transcribe_live_audio函数，通过麦克风采集音频，WebSocket发送到ASR服务端解析
    """

    def __init__(
        self,
        server_url: str,
        record_duration: int = 5,  # 默认录制时长（秒）
        callback: Optional[Callable[[dict[str, Any]], Coroutine[Any, Any, None]]] = None,
    ):
        """
        初始化实时音频转录器

        Args:
            server_url: ASR服务端WebSocket地址（如 ws://192.168.18.246:10095）
            record_duration: 单次录音时长（秒），默认5秒
            callback: 异步回调函数，用于自定义处理识别结果（可选）
        """
        # WebSocket配置
        self.server_url = server_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.receive_task: Optional[asyncio.Task] = None  # 接收结果的异步任务

        # 音频采集配置（适配ASR服务端要求：16kHz采样率、单声道、16位PCM）
        self.audio = None  # pyaudio实例
        self.stream = None  # 音频流
        self.sample_rate = 16000  # 关键：ASR服务端常用采样率
        self.channels = 1  # 单声道（减少数据量，提升实时性）
        self.chunk_size = 1024  # 每次读取的音频块大小（平衡延迟和性能）
        self.format = pyaudio.paInt16  # 16位PCM编码（ASR标准格式）

        # 录音控制
        self.is_recording = False  # 录音状态标记
        self.record_duration = record_duration  # 录制时长（秒）
        self.record_thread: Optional[threading.Thread] = None  # 录音线程（避免阻塞主线程）

        # 转录结果
        self.current_result = ""  # 实时中间结果
        self.final_result = ""  # 最终转录结果
        self.loop: Optional[asyncio.AbstractEventLoop] = None  # 异步事件循环

        # ASR服务端配置（按服务端要求调整）
        self.asr_config = {
            "chunk_size": [5, 10, 5],  # 服务端分块配置
            "wav_name": "live_microphone_audio",  # 音频标识
            "is_speaking": True,  # 标记正在说话（用于服务端流处理）
            "wav_format": "pcm",  # 音频格式（PCM原始数据）
            "chunk_interval": 10,  # 分块间隔（毫秒）
            "itn": True,  # 开启智能文本规范化（数字、日期等格式处理）
            "mode": "2pass",  # 双通模式（实时+离线校正，提升准确率）
            "hotwords": json.dumps(  # 热词配置（提升特定词汇识别率）
                {"阿里巴巴": 20, "会议纪要": 30, "转录": 25}, ensure_ascii=False
            ),
        }

        # 自定义回调（可选）
        self.callback = callback

    async def _connect_to_asr_server(self) -> None:
        """连接到ASR服务端WebSocket"""
        try:
            # 10秒超时控制，避免无限等待
            self.websocket = await asyncio.wait_for(
                websockets.connect(self.server_url), timeout=10.0
            )
            logger.info(f"✅ 成功连接到ASR服务端：{self.server_url}")
        except asyncio.TimeoutError:
            logger.error(f"❌ {STR_CONNECT_TIMEOUT}")
            raise ConnectionError(STR_CONNECT_TIMEOUT)
        except Exception as e:
            logger.error(f"❌ {STR_CONNECT_FAIL}: {str(e)}")
            raise ConnectionError(f"{STR_CONNECT_FAIL}: {str(e)}")

    def _init_microphone(self) -> None:
        """初始化麦克风设备，创建音频流"""
        try:
            # 初始化pyaudio
            self.audio = pyaudio.PyAudio()

            # 检查麦克风设备数量
            device_count = self.audio.get_device_count()
            if device_count == 0:
                logger.error(f"❌ {STR_MICROPHONE_UNAVAILABLE}（未检测到任何音频输入设备）")
                raise OSError(STR_MICROPHONE_UNAVAILABLE)

            # 获取默认麦克风信息
            default_mic = self.audio.get_default_input_device_info()
            logger.info(f"🎤 使用默认麦克风：{default_mic['name']}（采样率：{self.sample_rate}Hz）")

            # 创建音频输入流（关键：参数需与ASR服务端匹配）
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,  # 输入模式（麦克风采集）
                frames_per_buffer=self.chunk_size,
                exception_on_overflow=False  # 避免音频溢出报错（高负载时）
            )
        except Exception as e:
            logger.error(f"❌ {STR_AUDIO_INIT_FAIL}: {str(e)}")
            self._cleanup_audio()  # 出错时清理资源
            raise OSError(f"{STR_AUDIO_INIT_FAIL}: {str(e)}")

    def _cleanup_audio(self) -> None:
        """清理音频资源（关闭流、终止pyaudio）"""
        # 关闭音频流
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
            logger.info("🔇 音频流已关闭")

        # 终止pyaudio实例
        if self.audio:
            self.audio.terminate()
            logger.info("🔇 PyAudio实例已终止")

    async def _send_asr_config(self) -> None:
        """向ASR服务端发送初始化配置（必须在发送音频前执行）"""
        if not self.websocket or not self.websocket.open:
            raise ConnectionError("WebSocket连接已关闭，无法发送配置")

        try:
            config_json = json.dumps(self.asr_config, ensure_ascii=False)
            await self.websocket.send(config_json)
            logger.info("📤 ASR服务端配置已发送")
        except Exception as e:
            logger.error(f"❌ 发送ASR配置失败：{str(e)}")
            raise

    async def _send_audio_chunk(self, audio_chunk: bytes) -> None:
        """向ASR服务端发送单块音频数据（实时流传输）"""
        if not self.websocket or not self.websocket.open:
            self.is_recording = False  # 连接断开时停止录音
            logger.warning("⚠️ WebSocket连接已断开，停止发送音频数据")
            return

        try:
            await self.websocket.send(audio_chunk)
            # 日志可选：调试时开启，查看数据发送情况
            # logger.debug(f"📤 发送音频块（大小：{len(audio_chunk)}字节）")
        except ConnectionClosed as e:
            self.is_recording = False
            logger.error(f"⚠️ WebSocket连接已关闭（代码：{e.code}，原因：{e.reason}）")
        except Exception as e:
            self.is_recording = False
            logger.error(f"❌ 发送音频块失败：{str(e)}")

    async def _send_recording_end_signal(self) -> None:
        """向ASR服务端发送录音结束信号（触发最终结果计算）"""
        if not self.websocket or not self.websocket.open:
            return

        try:
            end_signal = json.dumps({"is_speaking": False}, ensure_ascii=False)
            await self.websocket.send(end_signal)
            logger.info("📤 录音结束信号已发送，等待最终结果...")
        except Exception as e:
            logger.error(f"❌ 发送结束信号失败：{str(e)}")
            raise

    async def _receive_and_process_results(self) -> None:
        """接收ASR服务端返回的结果，并处理（实时结果+最终结果）"""
        if not self.websocket or not self.websocket.open:
            return

        try:
            # 循环接收服务端消息（直到连接关闭）
            async for message in self.websocket:
                # 解析JSON结果（服务端返回格式需匹配）
                try:
                    result_data = json.loads(message)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ 解析ASR结果失败（JSON格式错误）：{str(e)}")
                    continue

                # 1. 自定义回调处理（优先执行用户自定义逻辑）
                if self.callback:
                    await self.callback(result_data)

                # 2. 内置结果处理（区分实时中间结果和最终结果）
                await self._process_result(result_data)

        except ConnectionClosed as e:
            logger.info(f"🔌 WebSocket连接已关闭（代码：{e.code}，原因：{e.reason}）")
        except Exception as e:
            logger.error(f"❌ 接收ASR结果时出错：{str(e)}")

    async def _process_result(self, result_data: dict[str, Any]) -> None:
        """
        内置结果处理逻辑
        服务端返回格式需包含：mode（结果类型）、text（识别文本）
        """
        result_mode = result_data.get("mode", "")
        result_text = result_data.get("text", "").strip()

        # 处理实时中间结果（2pass-online：双通实时模式）
        if result_mode == "2pass-online" and result_text:
            self.current_result = result_text
            # 实时打印（覆盖当前行，提升体验）
            print(f"\r🔄 实时识别：{self.current_result}", end="", flush=True)
            logger.info(f"🔄 实时识别结果：{self.current_result}")

        # 处理最终结果（2pass-offline：双通离线校正模式）
        elif result_mode == "2pass-offline" and result_text:
            self.final_result = result_text
            # 换行打印最终结果（避免覆盖实时结果）
            print(f"\n✅ {STR_FINAL_RESULT}{self.final_result}")
            logger.info(f"✅ {STR_FINAL_RESULT}{self.final_result}")

            # 处理分句信息（如果服务端返回）
            if "stamp_sents" in result_data:
                logger.info("📝 分句时间戳信息：")
                for sent in result_data["stamp_sents"]:
                    start_ms = sent.get("start", 0)
                    end_ms = sent.get("end", 0)
                    sent_text = sent.get("text_seg", "")
                    logger.info(f"  - {start_ms}-{end_ms}ms：{sent_text}")

    def _record_audio_in_thread(self) -> None:
        """
        麦克风录音线程函数（单独线程运行，避免阻塞异步事件循环）
        按指定时长录制，自动停止并发送结束信号
        """
        logger.info(STR_RECORDING_START)
        print(STR_RECORDING_START)

        # 记录录音开始时间（用于控制录制时长）
        start_time = time.time()
        audio_error_count = 0  # 音频错误计数（避免无限报错）

        # 循环录音（直到达到时长或停止标记）
        while self.is_recording:
            # 1. 检查是否达到录制时长
            if time.time() - start_time >= self.record_duration:
                self.is_recording = False
                print(f"\n⏹️ {STR_RECORDING_STOP}")
                logger.info(STR_RECORDING_STOP)
                break

            # 2. 检查音频流状态
            if not self.stream or not self.stream.is_active():
                audio_error_count += 1
                logger.warning(f"⚠️ 音频流异常（第{audio_error_count}次），尝试继续...")
                if audio_error_count >= 5:
                    self.is_recording = False
                    logger.error("❌ 音频流连续异常5次，停止录音")
                    break
                time.sleep(0.1)
                continue

            # 3. 读取音频块（非阻塞，避免线程卡死）
            try:
                audio_chunk = self.stream.read(self.chunk_size, exception_on_overflow=False)
            except IOError as e:
                audio_error_count += 1
                logger.error(f"⚠️ 读取麦克风数据失败（第{audio_error_count}次）：{str(e)}")
                if audio_error_count >= 5:
                    self.is_recording = False
                    logger.error("❌ 麦克风读取连续失败5次，停止录音")
                    break
                time.sleep(0.1)
                continue

            # 4. 发送音频块到服务端（通过异步事件循环）
            if self.loop and self.is_recording:
                try:
                    # 线程安全地将协程提交到事件循环
                    asyncio.run_coroutine_threadsafe(
                        self._send_audio_chunk(audio_chunk),
                        self.loop
                    )
                except RuntimeError as e:
                    self.is_recording = False
                    logger.error(f"⚠️ 提交音频发送任务失败：{str(e)}")
                    break

            # 5. 控制录音速度（匹配采样率，避免数据堆积）
            time.sleep(self.chunk_size / self.sample_rate)

        # 录音停止后，发送结束信号
        if self.loop and self.websocket and self.websocket.open:
            asyncio.run_coroutine_threadsafe(
                self._send_recording_end_signal(),
                self.loop
            )

    async def start_transcription(self) -> Optional[str]:
        """
        启动实时音频转录（核心方法，替代原transcribe_live_audio）
        Returns: 最终转录结果（str）或None（失败时）
        """
        # 重置结果（避免上一次结果残留）
        self.current_result = ""
        self.final_result = ""

        try:
            # 1. 获取当前异步事件循环
            self.loop = asyncio.get_running_loop()

            # 2. 连接ASR服务端
            await self._connect_to_asr_server()

            # 3. 初始化麦克风
            self._init_microphone()

            # 4. 发送ASR配置
            await self._send_asr_config()

            # 5. 启动结果接收任务（异步）
            self.receive_task = self.loop.create_task(self._receive_and_process_results())

            # 6. 启动录音线程（单独线程，避免阻塞）
            self.is_recording = True
            self.record_thread = threading.Thread(target=self._record_audio_in_thread)
            self.record_thread.daemon = True  # 守护线程：主程序退出时自动结束
            self.record_thread.start()

            # 7. 等待录音线程结束（超时时间=录制时长+5秒缓冲）
            self.record_thread.join(timeout=self.record_duration + 5)


            # 8. 等待最终结果返回（最多等待5秒，避免无限阻塞）
            if not self.final_result:
                logger.info("⌛ 等待ASR服务端返回最终结果...")
                # 循环检查最终结果，每0.5秒查一次，最多等5秒
                wait_start = time.time()
                while time.time() - wait_start < 5:  # 超时时间：5秒
                    if self.final_result:  # 一旦获取到最终结果，立即退出循环
                        break
                    await asyncio.sleep(0.5)  # 短暂休眠，减少CPU占用

                # 超时仍未获取最终结果，用实时结果兜底
                if not self.final_result:
                    logger.warning("⚠️ 获取最终结果超时，使用实时结果兜底")
                    self.final_result = self.current_result or STR_NO_RESULT

            # 9. 取消结果接收任务（避免残留异步任务）
            if self.receive_task and not self.receive_task.done():
                self.receive_task.cancel()
                try:
                    await self.receive_task  # 等待任务取消完成
                except asyncio.CancelledError:
                    logger.info("🔚 结果接收任务已取消")

            # 10. 返回最终结果（优先服务端最终结果，其次实时结果，最后提示无结果）
            return self.final_result

        except Exception as e:
            logger.error(f"❌ 实时转录过程出错：{str(e)}")
            # 异常时用“无结果”提示
            self.final_result = STR_NO_RESULT
            return self.final_result

        finally:
            # 11. 无论成功/失败，都清理资源（关键：避免内存泄漏）
            logger.info("🧹 清理转录资源...")
            self.is_recording = False  # 强制停止录音
            self._cleanup_audio()  # 清理音频设备（关闭流、终止PyAudio）
            # 断开WebSocket连接
            if self.websocket and self.websocket.open:
                await self._disconnect_from_asr_server()

        async def _disconnect_from_asr_server(self) -> None:
            """断开与ASR服务端的WebSocket连接"""
            if self.websocket and self.websocket.open:
                try:
                    await self.websocket.close(code=1000, reason="转录结束")  # 1000=正常关闭
                    logger.info("🔌 已断开与ASR服务端的连接")
                except Exception as e:
                    logger.error(f"⚠️ 断开WebSocket连接时出错：{str(e)}")

