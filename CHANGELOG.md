# Deadline Survivor — Changelog

## v1.2 — "Semantic Augmentor" (in progress)

### 目标
把"修复格式 / 翻译"两个固定功能升级为**通用任务系统**。
用户可以自定义任意数量的 LLM 任务（每个任务 = 系统提示词 + 可选热键），
通过命令面板（Ctrl+Shift+Space）或托盘菜单触发。

### 重大设计决策

- **Task 抽象**：每个任务是一个字典 `{id, name, hotkey, system_prompt, builtin}`。
  老的 `repair` / `translate` 变成两个 `builtin: true` 的内置任务。
- **命令面板优先**：Windows 托盘默认折叠，每次点击两步太慢。引入 Spotlight 风格
  的浮窗（Ctrl+Shift+Space），数字键秒选任务。高频任务保留全局热键。
- **不做 JSON 格式化**：纯本地任务和 LLM 任务在 UI 里混合会让用户困惑，
  此功能延后或弃用。
- **不做"输入文本"模式**：命令面板只用于选任务，不抢剪贴板的核心定位。
- **观感优先**：项目最终用途是课堂展示，UI/动效投入比例要高。

### 落地步骤（按顺序，每步可独立测试）

1. **Task schema + 迁移 + `groq_client.run_task()`**（不动 UI，老热键正常工作）
2. **动态 hotkey listener** + 失败 toast 反馈
3. **设置对话框任务管理面板** + 实时测试按钮
4. **托盘菜单 emoji + 动态任务列表 + 滑动 toast + 图标脉冲**
5. **Preset Library**（6 个内置：修复 / 翻译 / 公式 Unicode / 公式 LaTeX / 润色 / 正式语气）
6. **命令面板**（Ctrl+Shift+Space，赛博朋克浮窗，数字键触发，模糊搜索）
7. **测试覆盖**新 schema / 迁移 / 动态 hotkey

### 显式不做的事

- ❌ 非 Groq provider（v1.0 已决策）
- ❌ 历史持久化（剪贴板可能含敏感信息）
- ❌ 任务链 / 管道
- ❌ 本地（非 LLM）任务类型
- ❌ JSON 格式化

### 进度日志

> 每完成一步在这里追加一行，方便事后回溯迭代轨迹。

- 2026-05-04 Qwen 3.6 修复 "Format Repair" 字体阴影 bug（UI 变动详询 `QWEN_UI_REPAIR.md`）。
- 2026-05-01 启动 v1.2 迭代，方案与用户确认完毕，开始 Step 1。
- 2026-05-04 v2 视觉升级（按 Claude Design 第二轮 handoff bundle 实现）：
  - **Hero Toast**（新组件 `ui/hero_toast.py`）：启动时的"封面级"通知。420×自适应，
    深玻璃渐变 + lime 多层外发光 + 顶部 hairline accent + 36×36 DS mark 带
    脉冲 live dot + Ctrl/⇧/C 键帽提示行 + 三联 stats（SESSIONS / AVG / TIME SAVED）
    带动画起势的 sparkline + LIVE pill + 5.5s 倒计时进度条。spring 入场
    动画（OutBack）。click anywhere 或 ESC 关闭。`main.py` 启动时调用
    `show_hero_toast()`，从真实 telemetry 拉数字（today_ops、avg_latency、
    chars_saved 折算"time saved"）。
  - **Toast 系统 v2**（`ui/toast.py` 全量重写）：
    - 4 种 kind：success / **processing**（新）/ error / info
    - 每种独立的 glyph 图标贴片（36×36 圆角，状态色边 + 状态色低饱和填充）
    - paintEvent 画 halo 模糊圆斑（QRadialGradient）+ 玻璃卡 + 左侧 3px 状态色
      accent 含光晕 + 底部进度条
    - **processing** kind 不自动关闭，进度条改为 indeterminate 横扫
    - 入场用 OutBack spring 缓动（v1 是 OutQuint），更弹
    - 新增 meta（小字详情）+ action_label（UNDO/RETRY/CANCEL chip 按钮）参数
    - 向后兼容：老调用 `show(title, body, kind=...)` 不动也能跑
  - **Settings v2**（增量改 `ui/tasks_page.py` + `ui/settings_dialog.py`）：
    - 选中任务行：渐变 lime tint（`#2A301E` → `#1B1F14`）+ 顶部 1px 高亮
      + 3px lime left bar，"浮起来"的视觉
    - LIVE TEST 卡：单独 objectName="liveTestCard"，QSS 给 lime 玻璃边
      + `QGraphicsDropShadowEffect` 36px 模糊 lime 光晕
    - RUN TEST 按钮：本地 lime 渐变（top-light bottom-deep）+ 28px lime 光晕
    - APPLY 按钮：dialog 全局 QSS 升级为 lime 渐变，加 lime 光晕 effect
  - **命令面板 v2**（`ui/command_palette.py` paintEvent 重写）：
    - 14 层多重外发光（v1 是 8 层），更亮更深
    - 卡身改用上深下浅渐变，"由下而上的发光感"
    - 顶部 lime hairline accent line 跨过卡顶
    - 选中行：横向 lime 渐变 + 上下 1px lime 内描边 + 3px lime left bar
  - 75 个测试全过，全部 v2 widget 构造烟测通过
- 2026-05-02 Demo day 备战 — Apple-style About + Presenter Mode 三件套：
  - **About 页 Apple 化**：64px 巨字 v1.2 当视觉锚 / lime "Stay in flow."
    tagline / 4 列 live stats strip / 干净 specs 网格 / "CRAFTED BY · GROUP 6"
    署名。砍掉 "Semantic Augmentor" 和 "exam-week" 这种掉调性的 jargon。
  - **Demo Pack** (`core/demo_pack.py`)：6 条预录 (task_id, 触发子串, 输出,
    人造延迟) 表。`groq_client.run_task()` 在 presenter_mode 下先查这表，
    命中就 sleep + return 缓存输出，绕过 Groq；不命中正常走 API。零网络
    风险 + 演示稳定 + 输出永远完美。
  - **Stats Prefill** (`utils/telemetry.py`)：`snapshot()` 读 settings 里
    `presenter_stats.*_base` 偏移，加在真实计数上。今天 ops 默认从 47 起
    （真实 ops 还会继续累加上去）→ 看起来"日常在用"，演示中数字还会跳。
  - **`settings.json`** 加 `presenter_mode: true` + `presenter_stats: {...}`。
    单一开关全局控制，demo 后改 false 即可关闭。
  - **`DEMO_MODE.md`**：完整文档。从 demo pack 数据格式、定制方法、
    demo day checklist、到我刻意没做的事（auto-reel / fake LIVE 指示器
    等）一应俱全。
- 2026-05-02 第七轮 hotfix（选中行 ghost 终结）：
  - WA_TranslucentBackground 撤了，全局字体策略也对了，但选中行依然有 ghost。
    最后一个根因：QListWidget::item:selected 的背景仍然是 `rgba(207,255,80,0.06)`
    半透明色。Qt 的渲染管线在这种背景上画文字时，glyph rasterize 假设
    opaque 背景做 AA → 结果 layer 跟 lime tint alpha 合成 → 1-2px stem
    位置残差 → ghost。
  - 改动：把 `:hover` 和 `:selected` 的 `rgba(...)` **预合成为不透明十六进制色**
    （`#161814` / `#21261A`），跟原 alpha 视觉等效但走单 pass paint。
    数学：T.PANEL #0E0E11 + lime #CFFF50 @ alpha 0.04/0.10 → 上述结果。
    选中态依然有强烈的 2px lime border-left 做主视觉提示，所以背景对比
    弱化也不影响识别。
- 2026-05-02 第六轮 hotfix（选中行残留 ghost + LIVE TEST 可见性 + BUILTIN 语义）：
  - **选中行 Format Repair 还有 ghost**：根因不是字体了，而是 _TaskRow 的
    `WA_TranslucentBackground` 属性。这个 attr 让 widget 走 Qt 的 alpha
    compositing paint path，跟标准路径用不同的 glyph 子像素位置。
    未选中行后面没东西 → 没影响；选中行后面是半透明 lime tint →
    text 渲染要做 alpha 混合 → ghost 重现。去掉 translucent attr，
    widget 默认不画背景（autoFillBackground 默认 False），lime 选中
    高光自然透过来，文字走标准路径，无 ghost。
  - **LIVE TEST 的 RUN TEST 按钮看不出是按钮**：之前用 objectName="accentBtn"
    依赖 dialog 全局 QSS 级联，但 QScrollArea 包裹下 QSS 偶发不传。
    改成本地 `setStyleSheet(...)` 直接定义 lime 实底 + hover 反馈 +
    放大到 80×140，带箭头前缀 "▸  RUN TEST"。同步 READ CLIPBOARD
    也加本地 QSS 兜底 + 同高度，两行视觉平衡。LIVE TEST 卡片右上角
    annotation 改为 "1) read clipboard → 2) run test" 一句话流程说明。
  - **BUILTIN 标签语义不明**：用户问"这是干啥的"。加 tooltip 说明
    "Built-in core task — cannot be deleted, but the hotkey and system
    prompt are still editable."
- 2026-05-02 第五轮 hotfix（字体方案 + ghost 真正根治）：
  - 第四轮把字体换成 Segoe UI 用户反馈"更丑了"，要求恢复 Inter Tight 的品牌感。
  - 重新分析 ghost 根因：之前一直默认"hinting 越强小字越清晰"是对的，
    所以一直在用 `PreferFullHinting`。但 **Inter Tight 的 TT hinting 表是为
    FreeType auto-hinter 调的**，Qt-on-Windows 走的是 DirectWrite/GDI+ 经典
    hinting 算法 —— 两套 hinting 哲学冲突，强制 grid snap 后 glyph stem 留
    1-2px 的位置残差，从视觉上读出来就是"text 下方 1px 的鬼影"。
  - 改动：所有渲染路径里 `setHintingPreference(PreferFullHinting)` →
    `setHintingPreference(PreferNoHinting)`。让 glyph 在浮点位置上做平滑
    AA，绕开 hinting 算法的不兼容。
  - 字体方案恢复：T.SANS = Inter Tight, T.MONO = JetBrains Mono。
  - HiDPI PassThrough 保留（这是个独立的好东西，不撤）。
- 2026-05-02 第四轮 hotfix（2K 屏幕字体阴影根治）：
  - 之前 hotfix 在每 QLabel 设 strategy 不够 —— 即使全局 `QApplication.setFont()`，
    dialog 的 QSS（`QLineEdit { font-family: ... }` 这类）仍会重置 widget 字体
    属性（QSS 不支持 styleStrategy 字段，所以 PreferAntialias|NoSubpixelAntialias
    在 QSS 应用时被丢回默认 ClearType）。叠加 2K 屏幕的分数 DPI 缩放，glyph 落
    在子像素位置 → ghost shadow。
  - **改动 1**：主字体从 Inter Tight / JetBrains Mono 换到 **Segoe UI / Cascadia Mono**
    （Windows 原生，DirectWrite 优化过的 family）。Bundled 字体保留为 fallback。
    系统字体在 Qt-on-Windows 渲染管线里走的路径不同，绕开 Inter Tight 的 weight
    解析 / strategy reset 问题。
  - **改动 2**：`main.py` 加 `Qt.HighDpiScaleFactorRoundingPolicy.PassThrough`
    （Qt 5.14+），让 Qt 在分数 Windows 缩放（125% / 150%）下不再取整 scale
    factor，glyph 落在原生像素网格上。必须在 `QApplication()` 构造之前调用。
- 2026-05-02 第三轮 hotfix（用户测试反馈第二批）：
  - **字体阴影还在 → 改全局 QApplication.setFont**：之前在每个 _mk_label
    helper 里设 strategy 不够稳 —— Qt 内部 widget（QStackedWidget、
    QScrollArea viewport 等）会用自己的 default font 重置回 ClearType。
    现在 `load_fonts()` 在注册 TTF 后调 `QApplication.instance().setFont(base)`
    强制全局 baseline：`PreferAntialias | NoSubpixelAntialias` +
    `PreferFullHinting`。每个 widget 都从这继承，无法被内部重置覆盖。
    验证：`app.font().styleStrategy() == 2176` (PreferAntialias|NoSubpixelAntialias)，
    `hintingPreference() == 3` (PreferFullHinting)。
  - **任务页右侧滚动条丑**：QScrollArea 之前用默认 Windows 滚动条样式。
    改成 6px 宽暗条 + ScrollBarAsNeeded（内容够时不显示）+ 横向滚动条
    强制关闭（ScrollBarAlwaysOff，编辑区永远不需要横滚）。
- 2026-05-02 第二轮 hotfix（用户测试反馈）：
  - **LIVE TEST 卡死 UI**：`_run_test_cb` 之前在主线程同步调 `_call_api()`,
    Groq SDK 是 sync httpx → 整个 Qt 事件循环冻结到 timeout（默认 3s）。
    改造：新增 `_TestWorker(QThread)` 在后台跑，主线程通过 `succeeded` /
    `failed` / `finished` 信号收尾。同时挡掉重复点击 RUN TEST。
  - **任务列表 ↑↓ 排序按钮拥挤**：移除（保留 FROM PRESET / + NEW /
    DUPLICATE / DELETE）。需要重排的用户可直接编辑 settings.json。
    `_move` 旧方法 + `move_requested` 信号留着无害（未来可换 drag-to-reorder）。
  - **公式 preset 表达力不足**：扩展 Formula → Unicode prompt：
    - 加了 Unicode 数学符号速查（上下标 / 希腊字母 / 运算符 / 集合逻辑 / 根号分数）
    - 明确说明 Unicode 表达不了的结构（嵌套根号 / 复合分式）→ 写
      `√(a+b)` 风格 + 末尾追加 `⚠ For complex notation, try the
      Formula → LaTeX task instead.` 提示用户切到 LaTeX preset
    - 强调保留分号、逗号等原始标点
    Formula → LaTeX 同步增强（积分 / 求和 / 极限 / 矩阵 / 向量等模板）。
- 2026-05-02 Hotfix 三处用户反馈：
  - **字体阴影 (Fix A)**：之前 `QFont.setWeight(DemiBold)` 走 Qt 的 weight 解析
    在 v5/Inter Tight 组合下偶发 mis-resolve → 触发 faux-bold 1px 叠印 ghost。
    改为 `setStyleName("SemiBold")` 直接按 TTF 子家族名取面，绕开整个解析链。
    叠加 `setHintingPreference(PreferFullHinting)` 让 9-11px 的 mono 小字在
    Windows 上对齐整数像素网格 → 不再糊。
    settings_dialog / tasks_page / command_palette 三处 helper 同步更新。
  - **命令面板 1-9 / ↑↓ 被搜索框吃掉 (Fix B)**：搜索 QLineEdit 的 keyPressEvent
    在 palette 之前消费事件。装 `installEventFilter`，在事件抵达 QLineEdit 之前
    先看是不是导航键（↑↓/Enter/Esc/1-9 + 搜索框为空时），是的话直接吃掉，
    其余字符正常 fall through 给搜索框模糊匹配。
  - **命令面板焦点回不去 (Fix C)**：palette 一旦获焦，原应用失焦；如果立刻
    emit task_chosen → dispatch → copy_selection() 则 Ctrl+C 会被注入到
    palette 自己（已 hide 但未真正释放焦点的窗口），剪贴板读不到选中文本。
    改成：
      `hide()` → `SetForegroundWindow(prev_hwnd)` （Win32 ctypes 还回去）
      → `QTimer.singleShot(60ms)` 等 OS 真正切换焦点 → 再 emit task_chosen
    `show_with()` 时用 `GetForegroundWindow()` 抓 prev_hwnd 入档。
- 2026-05-02 Step 7 完成（测试覆盖）：
  - 新增 `tests/test_tasks.py` 16 个测试 — Task 数据类 / migrate_settings 各路径
    / hotkey 冲突探测 / display_name / Preset Library
  - 新增 `tests/test_hotkey_parser.py` 12 个测试 — parse_hotkey 各种合法/非法输入
  - 总测试数 47 → 75，全过
- 2026-05-02 Step 6 完成（命令面板）：
  - 新增 `ui/command_palette.py`（CommandPalette + 内部 _TaskRow + _fuzzy_score）
  - frameless 居中浮窗，1px lime 边 + 8 层 lime 渐变发光环
  - 顶部搜索框含闪烁 lime 光标条；模糊匹配（contiguous + subsequence + word-boundary 加分）
  - 行内显示数字 1-9 + 任务 emoji + display_name + prompt 摘要 + 内置/自定义 tag + 热键 KeyCap
  - 键盘：↑↓ 导航 / Enter 触发 / 1-9 跳转 / Esc 关闭 / 失焦自动关
  - 入场 160ms ease-out 渐显，出场 120ms ease-in 渐消
  - 接入 `main.py` AppController：默认 hotkey=ctrl+shift+space，settings 里
    `command_palette_hotkey` 字段可改；listener bindings 里加内部 id `_palette`
- 2026-05-02 Step 5 完成（Preset Library）：
  - `core/tasks.py` 新增 `PRESETS`（6 个）+ `preset_to_task()` 工厂
    - Formula → Unicode（粘 Word/微信）/ Formula → LaTeX（粘 Markdown）
    - Polish / Formal Tone / Simplify / Summarize
    - 每个都带 mock_template，DEBUG_MODE 下能区分
  - `ui/tasks_page.py` TaskListColumn 加"FROM PRESET ▾"按钮 + 弹出菜单
  - 选中 preset 后追加成不预绑热键的自定义任务
- 2026-05-02 字体阴影修复：
  - 把 settings_dialog 和 tasks_page 的 mono_label/sans_label 从 QSS-based
    切到 QFont-based（避免 Qt 的 QSS font-weight 解析失败时的 faux-bold 1px 叠印）
  - 同时强制 `QFont.PreferAntialias | QFont.NoSubpixelAntialias` —— 关掉
    Windows ClearType 子像素渲染，避免深底 + lime 半透明高光下的 RGB 颜色光晕
  - _TaskRow 设置 `WA_TransparentForMouseEvents + WA_TranslucentBackground`
    让 QListWidget 的选中态 lime 高光直接显示，避免 widget 自绘背景的合成 fringing
- 2026-05-01 Step 4a + 4b 完成：
  - 新增 `ui/toast.py`（_ToastManager 单例 + Toast 浮窗 widget）
    - frameless / WA_ShowWithoutActivating / WA_TransparentForMouseEvents：
      不抢焦、不进 Alt-Tab、不影响下方点击
    - 滑入：translateX(+24→0) + opacity(0→1) ease-out 240ms
    - 滑出：translateX 反向 + 淡出 ease-in 180ms
    - 同屏最多 3 个，超额自动加速淡出最旧的；移除后下面的滑动 reflow
    - 三色边条：success=lime / error=magenta / info=ink3 / warn=amber
    - 含可选 chip 标签（任务名 + 时长）
  - `ui/tray_icon.py` 把 `showMessage()` / `show_success/timeout/api_error`
    全部路由到 toast_manager（系统通知不再使用）
  - `ui/widgets.py` 重写 PixelGlyph：
    - 以 layered 结构（plate + glyph + accent）替代单色像素列表
    - 全 16×16 dark plate (#0A0A0A) 保证任何 taskbar 背景下有 silhouette
    - DS 5×7 双字 wordmark 出现在 IDLE / PROCESSING（dim INK2）
    - IDLE 加 2×2 lime live dot；PROCESSING 加 amber bottom bar
    - SUCCESS / ERROR 用粗 check / X 替换 wordmark
- 2026-05-01 Step 3 完成：
  - 新建 `ui/tasks_page.py`（TaskListColumn + TaskEditorColumn + LIVE TEST）
  - `ui/settings_dialog.py`：
    - 标题栏去掉 "build 211" 和 "DBL-CLICK TRAY" 提示，version → v1.2
    - 状态 pill 改为反映真实状态（LIVE / MOCK / NO KEY）
    - rail 排序：01 Engine / 02 Tasks（NEW）/ 03 Translation / 04 About
    - 移除 hotkey 行 + 老 Sandbox 类（每任务 LIVE TEST 取代之）
    - `_save()` 把 Tasks 页 serialize 回 settings.json，drop 老 hotkeys 字段
  - `core/tasks.py` 默认值英文化（Format Repair / Translate）+ `display_name()`
    在 translate 任务上拼 "→ {target_lang}"
  - 47 个老单元测试 + PyQt5 真实构造烟测均通过
- 2026-05-01 Step 2 完成：
  - `core/hotkey_listener.py` 重写为 `DynamicHotkeyListener` + `parse_hotkey()`
    + v1.1 `HotkeyListener` 兼容 shim
  - 注册逐条独立，单条失败上报（task_id, ok, err_msg）不影响其他热键
  - `main.py` 接 `_bridge.hotkey_register_result` 信号，失败弹 toast
  - `update_bindings()` 支持运行时换绑（保存设置后无缝重注册）
  - 老测试里 3 个摸 v1.1 内部字段的删掉，47 个全过
  - 解析器烟测：标准组合 / 命名键 / F 键 / 空与无修饰键拒绝均符合预期
- 2026-05-01 Step 1 完成：
  - 新增 `core/tasks.py`（Task dataclass、`migrate_settings()`、`load_tasks()` 等）
  - `ai/groq_client.py` 加 `run_task(task, text)` 通用入口；`repair_format/translate`
    保留为兼容 shim（旧 sandbox/测试不破）
  - `main.py` 启动时跑 schema 迁移并回写盘；`AppController._dispatch` 接收 Task
  - 50 个老单元测试全部通过；迁移逻辑空 dict / v1.1 输入 / 幂等三场景手测通过

---

## v1.1 — "Bulletproof" (released)

- **Clipboard history & restore**：每次 dispatch 前快照原文，10 槽位内存
  deque。托盘 `↶ Restore Last Original (N)` pop 语义，重复点击逐步回退。
  从不写盘（剪贴板可能含敏感信息）。
- **Atomic SendInput paste**：`paste()` 改用 `SendInput` + `KEYEVENTF_SCANCODE`，
  绕过 IME 钩子（扫描码在 VK 翻译层之下处理），修复 Ctrl+Shift+C 误触
  输入法切换的老 bug。`GetAsyncKeyState` 注入前清残留修饰键。UIPI 失败
  退到 `keybd_event`。
- **Auto Ctrl+C**：`_dispatch()` 调 `copy_selection()`，单按 Ctrl+Shift+C/T
  即可工作。共用 paste 的 chord-injection 工具，同样清残留键避免触发自身
  hotkey。
- **Settings 反馈修复**：mock_translate 注入 target language；`effective_config()`
  暴露运行时配置；保存后 toast 显示 key 前缀 / model / target；reload 日志
  打 key 长度。

## v1.0 — "BYOK" baseline

- 单文件 PyInstaller 打包；50 单测全过
- Bring Your Own Key：发布 exe 不含 `.env`，首启用 BYOK 对话框
- 不支持非 Groq provider（接受作为校园演示限制）
