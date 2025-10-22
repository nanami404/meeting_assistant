# 标准库
import os
import tempfile
from pathlib import Path
import asyncio
from typing import Optional, IO


# 第三方库
import speech_recognition as sr
from pydub import AudioSegment
from loguru import logger

# 自定义库

# 字符串常量
STR_AUDIO_PARSE_ERROR = "无法解析音频文件：{}"
STR_FILE_NOT_FOUND = "音频文件不存在：{}"
STR_UNSUPPORTED_FORMAT = "不支持的音频格式，需转换为未压缩WAV"
STR_RECOGNITION_SUCCESS = "音频识别成功"

STR_REQUEST_ERROR = "Could not request results; {}"
STR_LISTENING_TIMEOUT = "Listening timeout"
STR_COULD_NOT_UNDERSTAND_AUDIO = "Could not understand audio"

class SpeechService(object):
    def __init__(self) -> None:
        self.recognizer = sr.Recognizer()
        self.microphone = None

        # Try to initialize microphone (optional for development)
        try:
            self.microphone = sr.Microphone()
            # Adjust for ambient noise
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
        except Exception as e:
            print(f"Warning: Could not initialize microphone: {e}")
            print("Audio recording from microphone will not be available, but file upload will still work.")

    async def transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio data in bytes format"""
        result = None  # 统一结果变量
        parent_dir = Path(__file__).parent.parent
        custom_temp_dir = parent_dir / "temp_audio"
        custom_temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file_path: Optional[str] = None
        converted_path: Optional[str] = None

        try:
            # 1. 检查音频数据
            if not audio_data or len(audio_data) == 0:
                logger.info("音频数据为空")
                print("音频数据为空")

            # 2. 创建临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", dir=str(custom_temp_dir), delete=False,
                                             mode="wb") as temp_file:
                temp_file_path = temp_file.name
                logger.info(f"transcribe_audio函数对应的音频文件: {temp_file_path}")
                print(f"transcribe_audio函数对应的音频文件: {temp_file_path}")
                temp_file.write(audio_data)

            # 3. 验证文件
            if not os.path.exists(temp_file_path) or os.path.getsize(temp_file_path) == 0:
                print("临时文件创建失败或为空")
                logger.warning("临时文件创建失败或为空")
                return result  # 第二个return

            print(f"File exists, size: {os.path.getsize(temp_file_path)} bytes")

            # 4. 转换音频格式
            converted_path = self._convert_to_compatible_wav(temp_file_path)
            if not converted_path:
                logger.warning("音频格式转换失败")
                print("音频格式转换失败")
                return result  # 第三个return

            # 5. 语音识别
            try:
                with sr.AudioFile(converted_path) as source:
                    self.recognizer.energy_threshold = 300
                    self.recognizer.dynamic_energy_threshold = True
                    audio = self.recognizer.record(source)

                # 优先使用Google中文识别
                try:
                    result = self.recognizer.recognize_google(audio, language='zh-CN')
                    logger.info("Google识别成功")
                    print("Google识别成功")
                except sr.UnknownValueError:
                    print("Google无法理解音频，尝试英语识别")
                    try:
                        result = self.recognizer.recognize_google(audio, language='en-US')
                        print("英语识别成功")
                    except sr.RequestError as e:
                        print(f"英语识别服务请求失败: {e}")
                except sr.RequestError as e:
                    print(f"Google服务请求失败: {e}")

            except Exception as e:
                print(f"识别过程中发生错误: {e}")

        except Exception as e:
            print(f"Error transcribing audio: {e}")
        finally:
            # 清理临时文件
            files_to_clean = [temp_file_path, converted_path]
            for file_path in files_to_clean:
                if file_path and os.path.exists(file_path):
                    try:
                        os.unlink(file_path)
                    except Exception as e:
                        print(f"清理文件 {file_path} 失败: {e}")

        return result  # 最终统一返回

    def _convert_to_compatible_wav(self, input_path: str) -> Optional[str]:
        """将音频转换为 speech_recognition 兼容的PCM WAV格式"""
        output_path = None
        try:
            # 检查pydub是否安装
            try:
                from pydub import AudioSegment
            except ImportError:
                print("pydub未安装，无法进行音频格式转换")
                return input_path  # 返回原文件

            # 创建输出路径
            output_path = input_path + "_converted.wav"

            # 尝试pydub转换
            audio = AudioSegment.from_file(input_path)
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            audio.export(
                output_path,
                format="wav",
                codec="pcm_s16le",
                parameters=["-ac", "1", "-ar", "16000"]
            )
            print(f"音频已转换为兼容格式: {output_path}")
            return output_path

        except Exception as e:
            print(f"音频转换失败: {e}")
            # 清理可能的不完整文件
            if output_path and os.path.exists(output_path):
                os.remove(output_path)
            # 尝试ffmpeg转换，若失败则返回原文件
            return self._convert_with_ffmpeg(input_path) or input_path

    def _convert_with_ffmpeg(self, input_path: str) -> Optional[str]:
        """使用ffmpeg命令行工具转换音频"""
        try:
            output_path = input_path + "_ffmpeg.wav"

            import subprocess
            # 使用ffmpeg转换为标准PCM WAV
            cmd = [
                'ffmpeg', '-i', input_path,
                '-ac', '1',  # 单声道
                '-ar', '16000',  # 16kHz采样率
                '-acodec', 'pcm_s16le',  # 16位PCM编码
                '-y',  # 覆盖输出文件
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and os.path.exists(output_path):
                print(f"FFmpeg转换成功: {output_path}")
                return output_path
            else:
                print(f"FFmpeg转换失败: {result.stderr}")
                return None

        except Exception as e:
            print(f"FFmpeg转换出错: {e}")
            return None

    def _check_audio_format(self, file_path: str) -> bool:
        """检查音频文件格式"""
        result = False
        try:
            import wave
            with wave.open(file_path, 'rb') as wav_file:
                # 检查是否是PCM格式
                comp_type = wav_file.getcomptype()
                if comp_type == 'NONE':
                    # 检查参数
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    frame_rate = wav_file.getframerate()

                    print(f"音频参数: {channels}声道, {sample_width}字节/样本, {frame_rate}Hz采样率")

                    # 检查是否是speech_recognition兼容的格式
                    if channels <= 2 and sample_width == 2 and frame_rate >= 8000:
                        result = True
                    else:
                        print("音频参数不兼容")
                else:
                    print(f"音频使用压缩格式: {comp_type}")

        except Exception as e:
            print(f"音频格式检查失败: {e}")

        return result

    def transcribe_audio_file(self, file_path: str) -> Optional[str]:
        """解析并转写音频文件（处理格式兼容问题）"""
        result: Optional[str] = None
        temp_wav_path: Optional[str] = None

        try:
            # 1. 验证文件是否存在
            if not os.path.exists(file_path):
                print(STR_FILE_NOT_FOUND.format(file_path))
                return result

            # 2. 强制转换为标准WAV格式（未压缩PCM编码，16kHz采样率，单声道）
            # 这是 speech_recognition 兼容性最好的格式
            audio_segment = AudioSegment.from_file(file_path)
            # 转换参数：单声道、16kHz采样率、16位深度（确保兼容性）
            standard_wav = audio_segment.set_channels(1).set_frame_rate(16000).set_sample_width(2)

            # 3. 创建临时WAV文件（确保格式正确）
            with tempfile.NamedTemporaryFile[IO[bytes]](suffix=".wav", delete=False) as temp_file:
                temp_wav_path = temp_file.name
                # 导出为PCM编码的WAV（指定codec确保兼容性）
                standard_wav.export(temp_wav_path, format="wav", codec="pcm_s16le")

            # 4. 验证临时文件是否生成
            if not os.path.exists(temp_wav_path):
                print(STR_FILE_NOT_FOUND.format(temp_wav_path))
                return result

            # 5. 解析音频文件（捕获具体解析错误）
            recognizer = self.recognizer
            with sr.AudioFile(temp_wav_path) as source:
                # 可选：调整识别器对音频的敏感度（减少噪音干扰）
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                # 读取完整音频
                audio = recognizer.record(source)

            # 6. 识别音频内容
            result = recognizer.recognize_google(audio, language="zh-CN")
            print(STR_RECOGNITION_SUCCESS)

        except sr.UnknownValueError:
            print(STR_COULD_NOT_UNDERSTAND_AUDIO)
        except sr.RequestError as e:
            print(STR_REQUEST_ERROR.format(e))
        except Exception as e:
            print(f"处理音频时发生错误：{str(e)}")
        finally:
            # 清理临时文件
            if temp_wav_path and os.path.exists(temp_wav_path):
                os.unlink(temp_wav_path)

        return result

    async def transcribe_live_audio(self, duration_seconds: int = 5) -> Optional[str]:
        """Transcribe live audio from microphone"""
        # 检查麦克风可用性
        if not self.microphone:
            print("Microphone not available")
            return None

        # 获取音频输入
        audio = self._record_audio(duration_seconds)
        if not audio:
            return None

        # 语音识别处理
        return await self._recognize_audio_with_retry(audio)

    def _record_audio(self, duration_seconds: int) -> Optional[sr.AudioData]:
        """录制音频并返回AudioData对象，失败则返回None"""
        try:
            with self.microphone as source:
                print("Listening...")
                return self.recognizer.listen(
                    source,
                    timeout=1,
                    phrase_time_limit=duration_seconds
                )
        except sr.WaitTimeoutError:
            print("Listening timeout")
        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
        except Exception as e:
            print(f"音频录制过程中发生错误: {e}")
        return None

    async def _recognize_audio_with_retry(self, audio: sr.AudioData) -> Optional[str]:
        """带重试机制的音频识别"""
        for attempt in range(3):
            try:
                result = self.recognizer.recognize_google(
                    audio,
                    language=getattr(self, 'language', 'zh-CN')
                )
                print(f"语音识别成功: {result}")
                return result
            except sr.UnknownValueError:
                print(f"第{attempt + 1}次尝试: 无法理解音频内容")
            except sr.RequestError as e:
                print(f"第{attempt + 1}次尝试: 请求语音识别服务失败: {e}")

            # 最后一次尝试失败后不再等待
            if attempt < 2:
                await asyncio.sleep(1)

        print("三次尝试均失败")
        return None

    def extract_keywords(self, text: str) -> list[tuple[str, str]]:
        """提取文本中的关键词

        参数:
            text: 要分析的文本

        返回:
            包含(类型, 关键词)元组的列表，按出现顺序排列
        """
        keywords = []
        # 使用集合快速查找
        found_keywords = set()

        for word in text:
            if word in self.ACTION_KEYWORDS and word not in found_keywords:
                keywords.append(('action', word))
                found_keywords.add(word)
            elif word in self.DECISION_KEYWORDS and word not in found_keywords:
                keywords.append(('decision', word))
                found_keywords.add(word)
        return keywords

    def identify_speaker(self, audio_data: bytes) -> str:
        """Identify speaker from audio (placeholder implementation)"""
        # This is a placeholder for speaker identification
        # In production, you would use speaker recognition models
        # For now, return a generic speaker ID
        return f"speaker_{hash(audio_data) % 1000}"
