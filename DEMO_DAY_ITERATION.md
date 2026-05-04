# Deadline Survivor — Demo Day Iteration Story

## 产品定位
一个 Windows 后台工具，拦截剪贴板，通过 LLM 修复断行格式或翻译文本，然后自动粘贴回原窗口。

## 技术栈选择理由

| 技术 | 为什么选它 | 为什么不选别的 |
|------|-----------|---------------|
| **PyQt5** | 系统托盘 + 全局热键 + 自定义 UI 一站式 | Electron 太重（>100MB），tkinter 做不出这种 UI |
| **ctypes + RegisterHotKey** | 无需管理员权限，系统级热键 | `keyboard` 库需要 admin，用户不接受 |
| **Groq API** | 推理速度极快（~300ms），demo 体验流畅 | OpenAI 太慢（>2s），用户等待时以为卡死 |
| **PyInstaller onefile** | 单文件 .exe，双击即用 | 用户不想装 Python 环境 |
| **Python 3.14** | 团队熟悉，开发效率高 | Rust/Go 学习曲线陡峭，赶 demo 来不及 |

---

## 迭代历程总览

### v0.2 — "Intelligent Semantic Clipboard" (2026-04-15)
**起点：** P1 已完成热键监听（ctypes + RegisterHotKey，无需管理员权限），但只有占位符逻辑（读取剪贴板 → 反转字符串 → 粘贴回去）

**实现的功能：**
- **Feature 1 — Groq API 集成**：替换反转字符串逻辑，调用 `llama3-8b-8192` 模型，严格 System Prompt 确保只输出原始修复文本（无对话 filler）
- **Feature 2 — 设置 UI**：PyQt5 系统托盘图标 + 设置窗口，用户可自定义触发快捷键，保存到 `settings.json`
- **Feature 3 — 错误处理与降级**：API 超时（>3 秒）或失败时，优雅粘贴原文本，可选 Windows toast 通知
- **Feature 4 — PyInstaller 打包准备**：确保项目可打包为单文件 .exe

**关键架构决策：**
- `groq_client.py`：直接用 Groq SDK 的 `timeout` 参数（内部基于 httpx），超时时抛 `TimeoutError`，Worker 捕获后降级粘贴原文
- `tray_icon.py`：纯动态生成图标（无需外部 `.ico` 文件），三种状态可视化反馈（空闲紫/处理橙/成功绿/错误红）
- `DEBUG_MODE`：API Key 未配置时自动切换 Mock 模式，本地修复逻辑真实可用，适合无网演示
- **测试发现并修复真实 bug**：`paste()` 里的 `time.sleep(0.15)` 在 `try` 块外面，导致异常未被捕获。测试 `test_paste_exception_does_not_raise` 用 `side_effect=Exception` 让 sleep 抛异常，断言"不应崩溃"时发现了这个 bug。把 sleep 挪进 try 里，测试绿了，bug 消失了。

**测试覆盖：** 39 个单元测试全部通过（test_clipboard_handler / test_groq_client / test_hotkey_listener）

### v1.0 — "BYOK" Baseline (2026-04-20)
- 单文件 PyInstaller 打包，50 单测全过
- Bring Your Own Key 策略：发布 exe 不含 `.env`，首启用 BYOK 对话框
- 核心功能：Ctrl+C → Ctrl+Shift+C（修复）/ Ctrl+Shift+T（翻译）→ 自动粘贴

### v1.1 — "Bulletproof" (2026-04-25)
- 剪贴板历史 & 恢复（10 槽位内存 deque）
- Atomic SendInput paste（修复输入法切换 bug）
- Auto Ctrl+C（用户不用先手动复制）
- Settings 反馈修复（解决"改了 API key 不知道是否生效"的问题）

### v1.2 — "Semantic Augmentor" (2026-05-01 ~ 进行中)
- 从"两个固定功能"升级为**通用任务系统**
- 命令面板（Ctrl+Shift+Space，Spotlight 风格）
- Preset Library（6 个内置任务）
- 动态热键注册 + 失败 toast 反馈
- 设置对话框任务管理面板 + LIVE TEST
- 7 轮字体阴影 hotfix

---

## 最有代表性的三点迭代（用户反馈驱动）

### 1. Auto Ctrl+C — "用户经常忘了先复制"

**发现：**
> 用户测试时发现，很多人选了文本直接按 Ctrl+Shift+C，发现没反应，才意识到要先 Ctrl+C。
> "我以为选了文本就能直接用，还要先复制一步太麻烦了。"

**Before：**
```
用户操作：选中文本 → Ctrl+C → Ctrl+Shift+C → 修复 → 自动粘贴
失败场景：选中文本 → Ctrl+Shift+C → 剪贴板是旧的 → 修复了错误的内容
```

**After：**
```python
# core/app_controller.py — _dispatch() 新增自动 Ctrl+C
def _dispatch(self, task: Task) -> None:
    copy_selection()  # 主动模拟 Ctrl+C，无选中时是 no-op
    text = read()
    # ... 后续处理
```

**结果：**
- 用户操作简化为：选中文本 → Ctrl+Shift+C → 自动完成
- 步骤从 4 步减到 2 步
- 错误率大幅下降（不再修复旧剪贴板内容）

---

### 2. 安全底线与基础体验 — "AI 改错了怎么办？" (v1.1 - The "Bulletproof" Update)

**发现：**
> 用户不敢用，因为怕 AI 幻觉把原文改坏，改完就找不回来了。
> "万一它把我的论文改错了，我连原始版本都找不回来，不敢用啊。"
> 另外，偶尔按 Ctrl+Shift+C 会误切输入法，体验很割裂。

**Before：**
- AI 处理后原文直接覆盖，无法回退
- 粘贴用高层级按键模拟，偶尔触发 IME 切换
- 用户心理负担重，"不敢用"

**After：**
```python
# core/history.py — 剪贴板历史 & 恢复
class ClipboardHistory:
    def __init__(self, capacity=10):
        self._buffer = deque(maxlen=capacity)  # 内存 deque，不写盘
    
    def push(self, text: str, feature: str):
        self._buffer.append(HistoryEntry(text, feature))
    
    def restore_last(self) -> HistoryEntry | None:
        return self._buffer.pop() if self._buffer else None

# core/clipboard_handler.py — 原子化 SendInput 粘贴
def paste():
    # 用 SendInput + KEYEVENTF_SCANCODE，绕过 IME 钩子
    # 扫描码在 VK 翻译层之下处理，不会误切输入法
    inputs = create_scan_code_inputs()
    ctypes.windll.user32.SendInput(len(inputs), inputs, sizeof(INPUT))
```

**结果：**
- 托盘菜单新增 `↶ Restore Last Original (N)`，pop 语义，重复点击逐步回退
- 彻底解决 AI 幻觉导致的数据丢失风险
- 输入法切换 bug 修复，Ctrl+Shift+C 不再误触 IME
- 用户心理负担消除，"敢用了"

---

### 3. 核心能力扩充 — "从单一工具到多功能助手" (v1.2 - The "Brain" Upgrade)

**发现：**
> 用户问："只能修复格式和翻译吗？我想用它润色论文、转 LaTeX 公式、写正式邮件……"
> 老架构只有两个硬编码功能（repair / translate），加新功能要改代码。
> "每次想加个新用途都要找你们改，太麻烦了。"

**Before：**
- 只有两个固定功能：Format Repair / Translate
- 加新功能要改 `groq_client.py` 和 `main.py`
- 用户无法自定义，扩展性为零

**After：**
```python
# core/tasks.py — Task 抽象，每个任务 = 系统提示词 + 可选热键
@dataclass
class Task:
    id: str              # 唯一标识
    name: str            # 显示名称
    icon: str            # emoji 图标
    hotkey: str          # 可选全局热键
    system_prompt: str   # LLM 的系统提示词
    builtin: bool        # 是否内置

# ui/tasks_page.py — Prompt 管理器
class TaskEditorColumn(QWidget):
    # IDENTITY: 任务名 + emoji
    # HOTKEY: 全局热键捕获
    # SYSTEM PROMPT: 多行编辑器，实时字符计数
    # LIVE TEST: 读剪贴板 → 跑测试 → 看结果
```

**结果：**
- 用户可在设置界面自定义任意数量的 LLM 任务
- 每个任务独立配置：`[任务名] + [专属 Prompt] + [独立快捷键]`
- 内置 6 个 Preset（修复 / 翻译 / 公式 Unicode / 公式 LaTeX / 润色 / 正式语气）
- 从"单一格式修复器"进化为"通用快捷助手"
- 用户反馈："现在想加什么功能自己配就行，不用等你们更新了"

---

## 砍掉的功能（用户不用，所以不做）

| 功能 | 为什么砍 | 证据 |
|------|---------|------|
| **JSON 格式化** | 纯本地任务和 LLM 任务混在一起会让用户困惑 | DESIGN_BACKLOG.md 明确标记"延后或弃用" |
| **输入文本模式** | 命令面板只用于选任务，不抢剪贴板的核心定位 | 用户测试时没人用过"手动输入文本"功能 |
| **非 Groq provider** | 校园 demo 场景不需要多 provider 支持 | v1.0 已决策，接受为限制 |
| **历史持久化** | 剪贴板可能含敏感信息，写盘有风险 | 用户担心隐私，改为内存 deque |
| **任务链/管道** | 复杂度太高，demo 用不上 | 用户反馈"一个任务就够了" |

---

## Demo Day Checklist

### 核心演示流程（控制在 6 分钟内）
1. **开场（30s）**：一句话介绍产品定位
2. **核心用例（2min）**：
   - 从 PDF 复制一段断行文本
   - Ctrl+Shift+C → 自动修复 → 粘贴回 Word
   - 展示修复前后对比
3. **翻译演示（1min）**：
   - 选中文本 → Ctrl+Shift+T → 自动翻译 → 粘贴
4. **命令面板（1min）**：
   - Ctrl+Shift+Space → 搜索 "LaTeX" → 数字键 1 触发
   - 展示公式转 LaTeX 效果
5. **迭代故事（1.5min）**：
   - 讲上述三点用户反馈驱动的迭代
   - 强调"我们听了用户的话"
6. **Q&A 准备（预留）**

### 技术亮点准备
- **为什么选 Groq**：推理速度 ~300ms，用户等待时不会以为卡死
- **为什么不用 Electron**：太重（>100MB），PyQt5 单文件 .exe 仅 ~30MB
- **为什么不用 `keyboard` 库**：需要管理员权限，用户不接受
- **线程模型**：主线程（Qt）+ 后台线程（API 调用）+ daemon 线程（热键监听），互不阻塞

### 可能的问题及回答
- **Q: 如果 API 超时怎么办？**
  A: 3 秒超时后自动粘贴原文本，用户不会丢失内容。toast 会提示超时。

- **Q: 支持其他 LLM 吗？**
  A: 目前只支持 Groq，因为 demo 场景需要极快的推理速度。未来可以扩展。

- **Q: 剪贴板内容会上传吗？**
  A: 只发送给 Groq API 处理，不持久化到本地。历史恢复功能只在内存中保留 10 条。

- **Q: 为什么叫 Deadline Survivor？**
  A: 帮用户在 deadline 前快速修复格式/翻译，不用手动调整，"幸存"下来。

---

## 附录：完整迭代时间线

| 日期 | 版本 | 关键改动 |
|------|------|---------|
| 2026-04-20 | v1.0 | BYOK baseline，50 单测，单文件打包 |
| 2026-04-25 | v1.1 | Auto Ctrl+C，SendInput paste，Settings 反馈，剪贴板历史 |
| 2026-05-01 | v1.2 Step 1 | Task schema + 迁移 + run_task() |
| 2026-05-01 | v1.2 Step 2 | 动态 hotkey listener + 失败 toast |
| 2026-05-01 | v1.2 Step 3 | 设置对话框任务管理面板 + LIVE TEST |
| 2026-05-01 | v1.2 Step 4 | 托盘菜单 emoji + 动态任务列表 + 滑动 toast |
| 2026-05-02 | v1.2 Step 5 | Preset Library（6 个内置） |
| 2026-05-02 | v1.2 Step 6 | 命令面板（Ctrl+Shift+Space） |
| 2026-05-02 | v1.2 Step 7 | 测试覆盖（75 个测试全过） |
| 2026-05-02 | Hotfix 1-7 | 字体阴影 7 轮调试 + LIVE TEST 不卡死 + BUILTIN tooltip |
| 2026-05-04 | Qwen 修复 | Format Repair 阴影终结（_TaskRow 自绘背景） |
