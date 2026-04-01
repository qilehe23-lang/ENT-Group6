import keyboard
import pyperclip
import pyautogui
import time
import re
import sys
from openai import OpenAI



# 是否启用 AI 大模型？(True = 启用，False = 仅使用本地正则修复)
USE_AI = False 

# 你的 API Key (支持 OpenAI, DeepSeek, Kimi 等所有兼容 OpenAI 格式的接口)
API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" 
BASE_URL = "https://api.openai.com/v1"
# 识别操作系统，自动设置快捷键
is_mac = sys.platform == 'darwin'
TRIGGER_HOTKEY = 'cmd+shift+e' if is_mac else 'ctrl+shift+e' # 触发快捷键
PASTE_HOTKEY = ['command', 'v'] if is_mac else ['ctrl', 'v'] # 系统的粘贴快捷键


def clean_with_regex(text):
    """本地正则清理引擎：速度极快，无需联网"""
    print("正在使用 [本地正则] 修复文本...")
    
    # 1. 修复连字符换行 (例如: "func- \n tion" -> "function")
    cleaned = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    
    # 2. 将单个换行符替换为空格，但保留双换行符（真实的段落）
    cleaned = re.sub(r'(?<!\n)\n(?!\n)', ' ', cleaned)
    
    # 3. 去除多余的连续空格
    cleaned = re.sub(r' +', ' ', cleaned)
    
    return cleaned.strip()

def clean_with_ai(text):
    """AI 大模型处理引擎：理解语义，完美重组"""
    print("正在使用 [AI 模型] 修复文本...")
    try:
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[
                {"role": "system", "content": "你是一个无形的剪贴板排版助手。请修复用户发送的 PDF 提取文本。去除多余的换行符和乱码，拼合断开的单词，保留原有的段落和列表逻辑。不要输出任何解释，直接返回修复后的纯文本。"},
                {"role": "user", "content": text}
            ],
            temperature=0.1 # 温度设低，保证输出稳定
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI 处理失败: {e}。将降级使用本地正则处理。")
        return clean_with_regex(text)


def process_clipboard():
    """当按下快捷键时触发的主函数"""
    print("\n--- 检测到快捷键，开始处理 ---")
    
    # 1. 获取当前剪贴板的原始文本
    raw_text = pyperclip.paste()
    if not raw_text:
        print("剪贴板为空，跳过处理。")
        return

    # 2. 根据配置选择处理引擎
    if USE_AI and API_KEY.startswith("sk-"):
        final_text = clean_with_ai(raw_text)
    else:
        final_text = clean_with_regex(raw_text)

    
    pyperclip.copy("") # 先清空剪贴板，破坏原有的颜色、字体格式
    time.sleep(0.05)   # 等待 50 毫秒
    
    # 4. 写入真正干净的纯文本
    pyperclip.copy(final_text)
    print("处理完成！已写入纯文本。")
    
    # 5. 等待操作系统同步剪贴板（非常关键，给电脑一点反应时间）
    time.sleep(0.2) 
    
   
    if is_mac:
        keyboard.send('cmd+v')
    else:
        keyboard.send('ctrl+v')
        
    print("已自动在当前软件中触发粘贴。")


if __name__ == "__main__":
    print(f"✅ 智能剪贴板已启动，在后台运行中。")
    print(f"👉 选中 PDF 文本 -> 按下 Ctrl+C -> 将光标移至 Word/笔记中 -> 按下 {TRIGGER_HOTKEY}")
    
    # 注册全局快捷键
    keyboard.add_hotkey(TRIGGER_HOTKEY, process_clipboard,suppress=True)
    
    # 保持程序运行，监听键盘
    keyboard.wait()