import os
import json
import asyncio
import websockets
import glob
from core.deepseek import DeepSeek
import re
from core.predictor import EmotionClassifier  # 导入情绪分类器
from core.VitsTTS import VitsTTS              # 导入语音生成
from core.logger import logger
from core.langDetect import LangDetect
import dotenv

dotenv.load_dotenv()
# 获取日志级别已应用于logger初始化，无需额外操作
deepseek = DeepSeek()
emotion_classifier = EmotionClassifier()
langDetect = LangDetect()
tts_engine = VitsTTS(
    #enbale=False      #如果你没有配置simple-voice-api，请去掉这一行最开始的#号
)
temp_voice_dir = "./frontend/public/audio"
os.makedirs(temp_voice_dir, exist_ok=True)

# ANSI 颜色代码
COLOR_USER = "\033[92m"  # 绿色
COLOR_AI = "\033[96m"    # 青蓝色
COLOR_EMOTION = "\033[93m" # 黄色（用于情绪显示）
COLOR_RESET = "\033[0m"  # 重置颜色

def analyze_emotions(text):
    """分析文本中每个【】标记的情绪，并提取日语和中文部分"""
    # 改进后的正则表达式，更灵活地匹配各种情况
    emotion_segments = re.findall(r'(【(.*?)】)([^【】]*)', text)
    
    results = []
    for i, (full_tag, emotion_tag, following_text) in enumerate(emotion_segments, 1):
        # 统一处理括号（兼容中英文括号）
        following_text = following_text.replace('(', '（').replace(')', '）')
        
        # 提取日语部分（<...>），改进匹配模式
        japanese_match = re.search(r'<(.*?)>', following_text)
        japanese_text = japanese_match.group(1).strip() if japanese_match else ""
        
        # 提取动作部分（（...）），改进匹配模式
        motion_match = re.search(r'（(.*?)）', following_text)
        motion_text = motion_match.group(1).strip() if motion_match else ""
        
        # 清理后的文本（移除日语部分和动作部分）
        cleaned_text = re.sub(r'<.*?>|（.*?）', '', following_text).strip()
        
        # 清理日语文本中的动作部分
        if japanese_text:
            japanese_text = re.sub(r'（.*?）', '', japanese_text).strip()
        
        # 跳过完全空的文本
        if not any([following_text, japanese_text, motion_text]):
            continue
        
        # 改进语言检测和处理
        try:
            if japanese_text and cleaned_text:
                # 如果两者都有内容，才进行语言检测和交换
                lang_jp = langDetect.detect_language(japanese_text)
                lang_clean = langDetect.detect_language(cleaned_text)
                
                if (lang_jp in ['Chinese', 'Chinese_ABS'] and lang_clean in ['Japanese', 'Chinese']) and \
                    lang_clean != 'Chinese_ABS':
                        cleaned_text, japanese_text = japanese_text, cleaned_text


        except Exception as e:
            # 语言检测失败时保持原样
            logger.warning(f"语言检测错误: {e}")
        
        # 对情绪标签单独预测，增加错误处理
        try:
            predicted = emotion_classifier.predict(emotion_tag)
            prediction_result = {
                "label": predicted["label"],
                "confidence": predicted["confidence"]
            }
        except Exception as e:
            logger.error(f"情绪预测错误 '{emotion_tag}': {e}")
            prediction_result = {
                "label": "unknown",
                "confidence": 0.0
            }
        
        results.append({
            "index": i,
            "original_tag": emotion_tag,
            "following_text": cleaned_text,
            "motion_text": motion_text,
            "japanese_text": japanese_text,
            "predicted": prediction_result["label"],
            "confidence": prediction_result["confidence"],
            "voice_file": os.path.join(temp_voice_dir, f"part_{i}.{tts_engine.format}")
        })
    
    return results

async def generate_voice_files(text_segments):
    """异步生成所有语音文件"""
    tasks = []
    for segment in text_segments:
        if segment["japanese_text"]:  # 确保有实际内容
            task = text_to_speech(
                segment["japanese_text"], 
                segment["voice_file"]
            )
            tasks.append(task)
    await asyncio.gather(*tasks)

def play_voice_files(text_segments):
    """顺序播放生成的语音文件"""
    for segment in text_segments:
        if os.path.exists(segment["voice_file"]):
            logger.info(f"\n播放: 【{segment['original_tag']}】{segment['following_text']}")
            logger.info(f"\n日文翻译: {segment['japanese_text']}")
            logger.info(f"预测情绪: {segment['predicted']} (置信度: {segment['confidence']:.2%})")
            # 使用 pydub 播放音频，避免文件占用问题
            

# 语音合成（TTS）函数
async def text_to_speech(text, output_file):
    """生成单个语音文件"""
    await tts_engine.generate_voice(text, output_file, True)

def create_responses(emotion_segments, user_message):
    # 构造多条回复
    responses = []
    for segment in emotion_segments:
        # 提取文件名（去掉目录部分）
        audio_file = os.path.basename(segment['voice_file'])
        
        response = {
            "type": "reply",
            "emotion": segment['predicted'],
            "originalTag": segment['original_tag'],
            "message": segment['following_text'],
            "motionText": segment['motion_text'],
            "audioFile": audio_file,
            "originalMessage": user_message,
            "isMultiPart": True,  # 标记是多部分消息
            "partIndex": len(responses),  # 当前部分索引
            "totalParts": len(emotion_segments)  # 总部分数
        }
        responses.append(response)
    
    return responses

async def process_ai_response(ai_response, user_message):
    """处理AI回复并分析情绪"""
    # 0. 清理临时语音文件夹中的所有.wav文件
    if os.path.exists(temp_voice_dir):
        wav_files = glob.glob(os.path.join(temp_voice_dir, "*.wav"))
        for file in wav_files:
            try:
                os.remove(file)
            except Exception as e:
                logger.warning(f"删除文件 {file} 时出错: {e}")

    # 1. 打印原始回复
    logger.info(f"\n钦灵: {ai_response}")
    
    # 2. 分析情绪片段
    emotion_segments = analyze_emotions(ai_response)
    if not emotion_segments:
        logger.error("未检测到有效情绪片段，请检查deepseek.py中的apikey是否正确填写")
        return
    
    # 3. 生成语音文件
    logger.info("\n生成语音文件中...")
    await generate_voice_files(emotion_segments)

    # 4. 构造消息包
    responses = create_responses(emotion_segments, user_message)

    # 5. 播放并显示分析结果
    logger.info("\n语音分析结果:")
    play_voice_files(emotion_segments)

    return responses
    
    

async def handle_client(websocket):
    logger.info("Python 服务: 新的连接建立")
    
    try:
        async for message in websocket:
            data = json.loads(message)
            logger.debug(f"Python 收到消息: {data}")
            
            if data.get('type') == 'message':
                user_message = data.get('content', '')
                # 记录对话日志
                with open(os.path.join("logs", "conversation.log"), 'a', encoding='utf-8') as f:
                    f.write(f"用户: {user_message}\n\n")
                    
                ai_response = deepseek.process_message(user_message)
                
                # 记录对话日志
                with open(os.path.join("logs", "conversation.log"), 'a', encoding='utf-8') as f:
                    f.write(f"钦灵: {ai_response}\n\n")
                
                try:
                    responses = await process_ai_response(ai_response, user_message)
                    if responses:  # 确保responses不是None
                        for response in responses:
                            await websocket.send(json.dumps(response))
                            await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"\n处理AI响应时出错: {str(e)}")
                    await websocket.send(json.dumps({"error": str(e)}))
                
    except websockets.exceptions.ConnectionClosedOK:
        logger.info("Python 服务: 连接正常关闭")
    except Exception as e:
        logger.error(f"Python 服务: 发生错误 - {e}")

async def main():
    # 显式创建事件循环（兼容 Docker 和 Windows）
    logger.info("main函数加载中")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 修改主机地址为 0.0.0.0（允许 Docker 外部访问）
    # 修改 WebSocket 服务器配置
    bind_addr = os.environ.get("BACKEND_BIND_ADDR", "0.0.0.0")
    bind_port = os.environ.get("BACKEND_PORT", 8765)
    server = await websockets.serve(
        handle_client,
        bind_addr,
        bind_port,
        ping_interval=None,
        # 添加以下配置
        ping_timeout=None,
        close_timeout=None,
        max_size=2**25,  # 32MB
        # 放宽跨域限制
        origins=None  # 允许所有来源
    )
    
    logger.info(f"Python WebSocket 服务运行在 ws://{bind_addr}:{bind_port}")
    await server.wait_closed()

if __name__ == "__main__":
    logger.info("程序启动！")
    asyncio.run(main())
