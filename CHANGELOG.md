# Deadline Survivor — Changelog

## v1.3 — "Multi-Engine" (in progress)

### 目标
把锁死 Groq 的 LLM 层升级为可插拔的 provider 系统。
用户可以在 Groq / OpenAI / DeepSeek / Kimi / GLM / Qwen / SiliconFlow / Custom
之间任意切换，每个 provider 单独存 api_key / model / base_url / timeout。

### 架构

```
ai/
├── providers/
│   ├── base.py          ← LLMProvider ABC + ChatResult / TestConnectionResult
│   ├── errors.py        ← AuthError / RateLimitError / ServerError /
│   │                      ConnectionError / ProviderTimeoutError
│   ├── groq.py          ← GroqProvider (用 groq SDK)
│   ├── openai_compat.py ← OpenAICompatProvider (用 httpx 直连
│   │                      /v1/chat/completions —— 一套代码覆盖
│   │                      OpenAI / DeepSeek / Kimi / GLM / Qwen /
│   │                      SiliconFlow / Custom)
│   └── registry.py      ← PROVIDERS spec list + build_provider() factory
├── llm_client.py        ← 新单例（取代 groq_client），run_task /
│                          chat_raw / effective_config / test_connection
└── groq_client.py       ← 兼容 shim，re-export `groq_client = llm_client`
```

### 步骤

1. **Provider 抽象层**：`ai/providers/` 全包，含 base / errors / registry
   / groq / openai_compat。所有 provider 把原生异常归一化成
   `ProviderError` 子类，其中 `ProviderTimeoutError` 同时继承
   `TimeoutError` 保证 `core/worker.py` 的 fallback 链不破。
2. **OpenAICompatProvider**：用 `httpx`（Groq SDK 已带的依赖，零新增）
   直连 `/v1/chat/completions`，一套代码服务 7 个 provider + Custom
   base_url 自定义。
3. **llm_client 单例**：`ai/llm_client.py` 取代 `ai/groq_client.py`，
   `from ai.llm_client import llm_client` 是新规范入口。
   旧 `from ai.groq_client import groq_client` 仍然可用 —— 后者改成 shim
   re-export。
4. **schema 迁移**：`core/tasks.migrate_settings()` 自动把
   v1.2 顶层 `groq_api_key` / `groq_model` / `api_timeout_seconds`
   挪到 `providers.groq.{api_key, model, timeout_s}`，并补全 8 个 provider
   的空 stub。**保留旧字段不删**（v1.2 回滚兼容）。
5. **错误分类**：401/403 → AuthError；429 → RateLimitError；
   5xx → ServerError；DNS/TLS → ConnectionError；timeout
   → ProviderTimeoutError。`utils.user_facing_message()` 给出
   toast 友好文案。
6. **Test Connection**：每个 provider 自带 `test_connection(model, timeout)`
   返回 `(ok, rtt_ms, error_kind, detail)`，给 v1.3 Engine 页的 TEST 按钮
   用（UI 还在等 Design）。
7. **chat_raw 公共入口**：LIVE TEST sandbox 之前用 `_call_api` 私有方法，
   现在改走公共 `llm_client.chat_raw()`。
8. **测试覆盖**：75 → 102 全过。新增 `test_providers.py`
   （registry / 错误分类 / OpenAICompat HTTP / GroqProvider mock SDK）；
   `test_tasks.py` 加了 6 条 TestProvidersMigration 用例。
   `test_groq_client.py` 全部重写为 LLMClient 行为测试，名字保留方便
   git history 跟踪。

### 显式不做的事（留给 v1.4+）

- ❌ Anthropic / Claude（用户决策：先做便宜的国产模型）
- ❌ Ollama 本地模型（v1.4+）
- ❌ keyring / 加密存储 API key（v1.5+）
- ❌ 任务级 model override（v1.4+）
- ❌ Settings 导入导出（v1.4+）
- ❌ 命令面板 provider 切换（v1.4+）
- ❌ 配额条 tray UI（每家 provider rate-limit headers 不统一，独立迭代）
- ❌ Tasks 页 per-task 历史 audit 列（cost data 已经写盘，UI 暂缓）
- ❌ Toast 大额成本阈值提醒（容易过度打扰，谨慎开 v1.4+）

### 已落地（先前列在"不做"里现在做了的）

- ✅ Token / 成本估算（v1.3 后期，见下方进度日志 2026-05-12）
- ✅ Tray 状态条 v3 pulse 变体（v1.3 后期）
- ✅ `supports_vision` 元数据（v1.4 视觉模式 forward-prep）

### 进度日志

- 2026-05-10 Step 1-3 完成（不依赖 UI 部分）：providers 抽象 + OpenAI 兼容
  provider + llm_client 单例 + migrate_settings v1.3 升级 + 102 单测全过。
  UI 改造（Engine 页 provider 选择器 + TEST 按钮）等待 Design 给设计稿。
- 2026-05-10 Step 4-5 完成（Engine 页 UI 落地）：按 v3 设计稿实现，新建
  `ui/engine_page.py`（~870 LOC），改造 `_page_engine`：
  - **Provider grid 4×2** — 8 个 168×124 frosted-glass tile，4 状态
    （idle / hover / configured / selected）。Tile 全自绘 paintEvent
    避免 v1.2 ghost shadow 那条坑路径。每 provider 一个原创 SVG monogram
    （非厂商 logo）。
  - **ConfigCard** — API Key（password + SHOW/HIDE + VALID 指示）+
    Base URL 覆盖 + Model 下拉（可编辑，从 registry 拉
    available_models）+ Timeout 秒数。卡片有 lime drop-shadow glow。
  - **TestPanel "诊断剧场"** — 4 状态：idle / probing / success /
    error。probing 时 32 条动画 bar + lime sweep 横扫，RTT 实时 +0.1s
    ticking；success 显示大号 lime RTT + drop-shadow glow + model 卡；
    error 4 类（401/429/NET/T-O）按 magenta/amber 双色调分离。
  - **`_TestConnectionWorker(QThread)`** — 包 `llm_client.test_connection`，
    避免主线程冻结。Cancel 按钮可中断。
  - **OFFLINE MOCK MODE 复活**：v3 设计没画但保留为 footer 的低视觉
    复选框（power user 需要无 key 离线测）。
  - 调整：API key hint 改成 "Stored locally in settings.json · never
    sent in logs"（不假装有 keyring）；AUTOSAVE chip 改 "MANUAL · ⌘S
    TO APPLY"；5 阶段 stage chips 简化为单条 stage 文案；speed t/s
    指示去掉（无数据来源）。
  - 砍掉的范围：Hero 标题栏 / 左 rail 重做 / Tray 状态条三变体
    （都不在 Engine 页范畴；后续单独迭代）。
  - 102 单测继续全过；dialog 真实 event loop 渲染验证通过。
- 2026-05-11 真机测试反馈批量修复：
  - **About 页两处 v1.2 漏改 → v1.3**（`settings_dialog.py:560` 大字
    版本号 + `:614` "RELEASED 2026 · v1.2"）。pitch 文案
    "Eight tasks behind one keystroke" → "Eight engines, one keystroke"。
    `hero_toast.py` 两处默认参数 `version="v1.2"` 同步改 v1.3，build_meta
    改 "build 311 · multi-engine"。`main.py:324` 启动日志同步。
  - **First-run dialog v1.3 改造**：之前还在写 v1.2 flat schema
    （顶层 `groq_api_key`），改为调 `migrate_settings()` 写完整 v1.3
    schema（`active_provider="groq"` + `providers.groq.api_key=<key>`
    + 8 个 provider 空 stub）。同时保留 legacy `groq_api_key` 顶层
    （v1.2 回滚兼容）。Welcome blurb 也改为 provider-agnostic：
    "ships with eight engines... Groq is the fastest free option...
    switch any time in Settings → Engine"。
  - **Engine 页底部丑横向滚动条修复**：`setHorizontalScrollBarPolicy
    (Qt.ScrollBarAlwaysOff)` 完全禁用横向；纵向 scrollbar 重写 QSS
    （margin 收紧、handle 圆角 4px、add-line/sub-line/add-page/sub-page
    全置透明）。
  - **Model 下拉箭头方块 dot bug**：Qt 默认 `QComboBox::down-arrow` 用
    per-style pixmap，dark 主题下不响应 QSS 颜色覆盖，渲染成黑方块。
    新建 `_ChevronComboBox` 子类，paintEvent 在右侧自绘 8×4px 双线
    chevron；QSS 把原生箭头 `image: none; width:0; height:0` 隐藏，
    padding 右侧留 28px 给 chevron。同步 popup item min-height + padding。
- 2026-05-11 Provider grid 右侧截断 bug 修复：
  - **症状**：v1.3 Engine 页底部横向滚动条禁用后，4 个 168px tile
    + 3 gap (10) + body padding (26+26) = 754px > engine page 实际可用
    687px → 多出 67px 被截。
  - **修法**：tile `setFixedSize` 改 `setFixedHeight(124) +
    setMinimumWidth(140) + QSizePolicy.Expanding`；grid 4 列
    `setColumnStretch(col, 1)` 平分宽度；body padding 26 → 18。
    实测每 tile 自适应到 153px，grid 643px ≤ 651px 可用，余 8px 安全边。
- 2026-05-11 真机另一台电脑发现的"重复 BUILTIN 标签" bug：
  - **症状**：v1.2 打包 exe 在别人机器上点 Format Repair 出现两个
    BUILTIN 标签（dev 机看不到）。
  - **根因**：`QListWidget.setItemWidget(item, new_widget)` 跨 Qt /
    Windows / DPI 组合下**不可靠地删除旧 widget** —— 旧 _TaskRow
    保留在 widget 树里，dev 机上新 widget 完全覆盖看不出来；用户机
    DPI/字体回退使旧 widget BUILTIN 标签从新 widget 边缘漏出。
  - **触发链**：每次 `_refresh_row` 都泄漏一个旧 _TaskRow。
    `_on_select(idx)` → `editor.load_task()` → `finally` 块的
    `_on_prompt_changed()` → `_maybe_emit()` → `_on_editor_changed`
    → `_refresh_row` → `setItemWidget` 留下孤儿。
  - **实测**：5 次 refresh 后页面 9 个 BUILTIN（应该 2 个）。
  - **修法**：`tasks_page._refresh_row` 显式 `removeItemWidget(item)`
    → `old.setParent(None)` → `old.deleteLater()` → 然后 setItemWidget
    新 widget。`reload()` 同样防御式回收（clear() 同样不可靠）。
  - 修复后 5 次 refresh + 10 次切换 + 2 次 reload → 始终 2 个 BUILTIN。
- 2026-05-11 v1.4 forward-prep · supports_vision 元数据：
  - `ProviderSpec` 加 `supports_vision: bool = False`。OpenAI / GLM /
    Qwen / SiliconFlow / Custom 标 True（vision-capable 模型族）；
    Groq / DeepSeek / Kimi 标 False（当前主线模型只接受文本）。
  - **当前没有任何代码读这个字段** —— 纯元数据预留。v1.4 视觉模式
    上线时 Engine 页 model 下拉过滤 / 📷 角标 / 剪贴板图片捕获判断
    都从这里读。
- 2026-05-11 Tray pulse 状态条（v3 设计 TrayPulse 变体）：
  - 新建 `_PulseStrip`（320×38）+ `_SparkBars`（15 条 amplitude-alpha
    bar）+ `_PipDot`（halo 圆点，颜色随 key 状态切换）三个 widget。
  - 布局：`[●] Provider [▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮] 87ms`，挂在 tray menu **最顶部**
    （via `QWidgetAction`），`_TelemetryHeader` 保留在下方做累计统计。
  - `menu.aboutToShow` 时同时刷 pulse + telemetry header。
  - 防御式：上游任何异常都不让 tray crash（tray 是用户交互入口，
    硬死会让用户以为整个 app 挂了）。
- 2026-05-12 Token / 成本估算（"必做"两层 — TestPanel 校准 + Tray $today）：
  - 新建 `ai/pricing.py`（~190 LOC）— 8 provider × N model 单价表
    （USD/M tokens），含 CNY → USD `_cny()` 单点换算（汇率 7.30）。
    `estimate_cost()` 用"最长子串匹配"找定价（写一次 `"llama-3.1-8b"`
    catch 所有 `-instant`/`-instruct` 变体）。
    Format helpers：`format_cost_short`（tray 用 `$0.08`/`<$0.01`）、
    `format_cost_per_probe`（test panel 用 `≈ $0.000016`）、
    `project_cost_per_1k`（projection `≈ $0.016`）。
  - 数据流改造：provider chat 已有 `prompt_tokens` / `completion_tokens`
    → llm_client `_call_provider` 计算成本 → side-channel 写入
    `llm_client.last_usage`（新 `LastUsage` dataclass，不动 run_task
    返回签名以免 10+ 处 caller / shim 全炸）→ main.py
    `_on_worker_success` 读出来喂给 `telemetry.record_op()`（kwarg
    扩展）→ `telemetry.snapshot()` 暴露 `today_cost` / `total_cost` /
    `total_tokens`，跨日 `today_cost` 跟 `today_ops` 一起重置。
  - **TestPanel success 右栏改造**：从一句话变成 3 行 mono：
    `{tps} t/s · {tot} tok` / `≈ ${x} / probe` / `≈ ${y} / 1k repairs`。
    未知 model（custom endpoint）→ `—` + "(model not in pricing table)"
    解释，**不显示 $0** 避免误读为"免费"。`is_estimate=True` + 价格 0
    （如 GLM-4-flash）→ "≈ free"，与未知区分开。
  - **Tray `_TelemetryHeader` 第 3 列**：`SAVED 18420c` (demo day vanity
    指标) → `$ TODAY $0.08`（更可操作）。
  - **TestConnectionResult 扩展**：加 `prompt_tokens` / `completion_tokens`
    字段；GroqProvider + OpenAICompatProvider 在 `test_connection`
    里把这俩 thread 进去（test 也调底层 chat，已经有数据）。
  - **未知 model 不计入 today_cost**：避免 custom endpoint 的 $0 拉低
    真实账单可信度。
  - 新增 `tests/test_pricing.py` 17 测：lookup 长前缀优先 / unknown
    路径 / 边界（负数/0）/ format helpers / 表 schema 完整性。
    总测试 102 → 119 全过。
- 2026-05-12 决策：配额条 tray UI 不做。每家 provider 配额信号不统一
  （Groq RPM/TPM、OpenAI 付费无配额、GLM-4-flash 才有日配额、SiliconFlow
  按模型分），需要 per-provider 解析 rate-limit headers 单独迭代，
  超出 v1.3 范围。

- 2026-05-12 流式输出（v1.3 最后一项）：
  - **新接口** `LLMProvider.chat_stream(..., on_chunk: StreamCallback) ->
    ChatResult`。`StreamCallback` = `Callable[[str], bool]`：返回 True
    继续 / False 取消（provider 必须遵守）。基类有默认实现 = 调
    `chat()` 一次性 emit 整段 —— 任何 provider 不实现真流式也满足契约。
  - **GroqProvider** `chat_stream=True` + `stream_options={"include_usage":
    True}`，遍历 chunks，每个 delta `content` 推到 on_chunk。最终 chunk
    带 usage 信息，无缝走现有 cost telemetry 管线。on_chunk 返回 False
    时显式 `stream.close()` 终止上游生成。
  - **OpenAICompatProvider** raw httpx SSE 解析：`client.stream("POST",
    ...)` + `iter_lines()`，跳过 `:`-comment 行 / 非 `data:` 字段；
    `data: [DONE]` 终止；usage 在最后 chunk 里 piggy-back（设置
    `stream_options.include_usage`）。401/429/5xx 在读 body 之前即抛
    typed error，不浪费连接。Cancel 通过 break + with-block 自动关连接
    通知上游停止。
  - **`llm_client.run_task_streaming(task, text, on_chunk)`**：与
    `run_task` 平行的入口。Demo override 命中和 mock 模式都兜底 emit
    一次完整结果（保证 UI 行为一致）。设置开关
    `streaming_enabled: bool` （默认 False，experimental）。
  - **`ClipboardWorker` 加 `streaming` flag 和 `chunk` 信号**：流式模式
    下 `processor_fn(text, on_chunk)`，on_chunk 内部 `self.chunk.emit
    (fragment)` —— Qt 自动 queued connection 跨线程到主线程。
    `request_cancel()` 主线程 API：set flag → 下一个 chunk 回 False
    → provider 关流 → worker 走"用户取消"降级路径（粘贴原文 + 发
    error 信号 "Cancelled by user"）。**不会残留半截 LLM 输出
    在剪贴板**（粘贴原文是 worker 的硬不变量）。
  - **Toast 流式 lifecycle**：`Toast.update_body(text)` 公共方法
    （tail-truncate 240 char，PlainText 防 `<` 被当 HTML），保留
    `_msg_label` 引用以便后续更新。`_ToastManager` 加 `_streaming_toast`
    单一活跃流追踪 + `start_streaming(title, chip)` /
    `update_streaming(text)` / `end_streaming()` 三件套。`end_streaming`
    在 `_on_worker_finished` 兜底（任何路径都关）+ 各完成 slot 单独关。
  - **main.py `_dispatch` 路由**：dispatch 时 snapshot
    `llm_client.streaming_enabled` 决定 streaming 路径，避免中途 toggle
    设置导致半流。`_pending["stream_buf"]` 累积全文，`_on_worker_chunk`
    每次拼接后传给 `update_streaming(buf)` —— toast 拿全文自己
    tail-truncate（不在主线程做字符串切片）。
  - **Engine 页 footer 加 `STREAM OUTPUT` 复选框**：对齐 OFFLINE MOCK
    MODE 视觉，tooltip 解释 "Show tokens as the model generates them
    (live preview toast). Experimental — falls back to one-shot mode
    for demo/mock paths."。读写 `settings["streaming_enabled"]`。
  - **测试**：新增 `tests/test_streaming.py` 9 测：
    - 默认 fallback emit 一次完整 chunk
    - OpenAICompat SSE 顺序保留 + usage 解析
    - 畸形 SSE 行跳过不致死
    - on_chunk 返 False 立即停（"AB" 不会变成 "ABCD"）
    - 401 在 stream 前即抛 AuthError
    - run_task_streaming 路由：mock 模式发一次 / 真 provider 走 chat_stream
    - streaming_enabled 默认 False / 读 settings
    总测试 119 → 128 全过。
  - **决策回顾**：
    - 非取消式即时停 vs 等待自然完成 → 用了"on_chunk 返 False + 显式
      close"。理由：成本最小（不付未生成的 token）+ 用户感知响应
      最快（toast 立刻消失）。
    - 流中粘贴 vs 等流完粘贴 → 等完成。理由：剪贴板 + Ctrl+V 是单次
      事件，无法增量送达另一个应用；半截输出粘出去会破坏用户文档。
    - 处理 toast 在哪（旁边 toast / drawer / 替换主 toast）→ 替换。
      理由：我们之前根本没有 processing toast 在主流程，streaming 是
      第一个用例 —— 不要为它新建概念。

- 2026-05-12 流式输出 v4 UI 升级（design v4 handoff · "phrase cycler"）：
  - **架构调整 — toast 接管 buffer**：v1.3 初版的"主线程拼全文 → toast
    tail-truncate"模型废弃。新协议：`ClipboardWorker.chunk` 信号每次
    携带 raw fragment → `main.py._on_worker_chunk` 直接调
    `toast_manager().feed_chunk(fragment)` → Toast 内部维护
    `_stream_buf` 并跑 commit 规则。**main.py 不再拼字符串**
    （`_pending["stream_buf"]` 字段移除）。
  - **commit 规则下沉到独立模块** `ui/phrase_commit.py`（~65 LOC，
    Qt-free）：纯函数 `try_commit_phrase(buf) -> (phrase|None, new_buf)`：
    - R1 — Latin 句末标点 `[.,;:!?—]` + 空格/EOF → 提交至该标点
    - R2 — 缓冲区 ≥ 6 个完整单词 → 切到最后一个空格
    - R3 — 缓冲区无任何空白且 ≥ 24 字符 → 优先切到最后一个 CJK 标点
      `[，。！？；]`，否则切到 24 字符位
    放在独立模块两个好处：(1) 单测不需要 Qt；(2) toast widget 干净
    re-export，避免 widget 文件涨到 1500+ LOC 还要写正则。
  - **`_PhraseStack` widget**（设计稿 § 03 visual spec）：固定高度 40px，
    QStackedWidget 风格的"已提交 phrase"垂直堆叠，每次 commit 上一条
    上浮淡出，新一条从下方推入。最多保留 N 条历史（旧的 deleteLater）。
  - **`_GhostLine` widget**：低饱和 INK2 mono，display `_stream_buf`
    实时尾部，作为"还没被 R1/R2/R3 切下来的草稿"的视觉指示，让用户
    感知到"模型还在写"。
  - **telemetry 行**（toast 顶部右侧）：3 个 mono stat label —
    `{phrases} phrase · {tokens} tok · {rate} t/s`，phrase / token 在
    每次 feed_chunk 内 setText（O(1)），t/s 由 200ms `_rate_timer`
    单独刷（避免每 chunk 都做 monotonic 除法）。流终止时 `_rate_timer.stop()`
    避免 toast dismiss 后还在跑。
  - **RACE 边界处理**：`Toast.flush_pending(cancelled=False)` 把残余
    `_stream_buf` 作为最后一个 phrase 一次性 commit；`cancelled=True`
    丢弃 buffer（timeout / error / 用户取消 — 半截输出不能伪装成"完整
    一句话"留在 phrase stack 里）。`_on_worker_success` 调
    `end_streaming(cancelled=False)`，`_on_worker_timeout` /
    `_on_worker_error` 调 `cancelled=True`。`_on_worker_finished` 兜底
    再调一次（任何路径未关 toast 都被这条扫掉，已关的就是 no-op）。
  - **back-compat**：`toast_manager().update_streaming(text)` 保留为
    `feed_chunk(text)` 的 shim，避免还没切到新协议的调用方破。
  - **测试**：`tests/test_streaming.py` 从 9 测扩到 21 测（+12）：
    - phrase_commit R1/R2/R3 三条规则的 happy path
    - R1 优先级（句末标点先于词数阈值）
    - R2 至少 6 词 + 切在最后空格
    - R3 CJK 标点 / 24 字符兜底 / 缓冲区有空白时不触发
    - 空 buffer / 只有空白 / 纯单字符等边界
    - 多个标点连续时只切第一段（懒匹配）
    总测试 128 → 140 全过。
  - **决策回顾**：
    - 为什么把 buffer 从 main.py 挪到 Toast？v4 设计要 ghost line +
      phrase commit 规则 + 计数器 + 速率，全都基于 buffer 状态。把
      buffer 放在主线程意味着每次 chunk 都要把状态对象传给 toast，
      接口面变厚；放在 toast 内则 toast 完全自治 —— main.py 只管
      "有 fragment 来了就转交"，单一职责。
    - 为什么 commit 规则放在 `phrase_commit.py` 而不是 `toast.py`？
      规则是纯逻辑（输入 → 输出），跟渲染无关；放外面让单测不需要
      PyQt5 stub。把 21 测试里的 commit-rule 测试与 widget 测试解耦。
    - 为什么 phrase 计数器在 lime 色，token / rate 不是？lime 强调
      "用户感知到的产出（commit 出来的完整短语）"，token / rate 是
      技术指标 —— 信息层级用色彩分离，不靠字号。

### v1.3 收尾

所有计划项已完成。剩余未做项全部 explicit 推到 v1.4+（见上方"显式不
做的事"）。总测试 47 → 75 → 102 → 119 → 128 → 140 全过。

---

## v1.2 — "Semantic Augmentor" (released 2026-05-05)

### v1.2 ship-day fixes (2026-05-05)
- **Toast paintEvent 崩溃修复**：`ui/toast.py` 的 `drawEllipse` 在 PyQt5 + Python 3.14
  下不再隐式 float→int，整个 paintEvent 抛 `TypeError`，托盘连同主进程一起死掉。
  改用 `QRectF(...)` 重载，并把 halo / 左侧 accent edge / 进度条都包进
  `setClipPath(card_path)` 内，匹配设计稿 `.toast{overflow:hidden}` 行为，
  消除左上角溢出的硬边阴影斑。
- **Toast 视觉对齐设计稿**：title 改用自写 `_ElidedLabel` 防止超长被硬截断；
  meta 行支持 `·` 分隔点；row padding/spacing 改成设计稿的 16/14/30/12 + 14。
- **Toast caller 修正**：`tray_icon.show_success` 不再把 `feature_name`（含 emoji）
  既塞进 title 又塞进 chip。emoji 由左侧彩色 glyph tile + lime accent edge 表达
  状态，title 去 emoji，chip 改成短状态标签（`PASTED` / `FALLBACK`）。
- **设置页 Tasks 布局**：去掉 body 外 padding 和 list/editor 之间的 14px gap，
  按设计稿 `.split` 让两栏直接相邻、靠 list-col 的 `border-right` 分隔，
  解决"右半栏被推太靠右"的视觉断裂。
- **TARGET LANGUAGE 标签全名**：之前源码就是 `"TARGET LANG"`（不是 UI 截断），
  补全为 `"TARGET LANGUAGE"`。
- **Live test 翻译目标语言修复**：之前 `_TestWorker` 直接把原始剪贴板文本作为
  `user_message` 调 `_call_api`，跳过了 `run_task` 里的
  `Translate the following text to {lang}:` 包装，LLM 自己挑语言（多半西语）。
  修：`_TestWorker` 接受 `task` 参数；dialog 的 `_run_test` 检测
  `task.id == TASK_TRANSLATE` 时手动注入与生产路径一致的 user_message 包装。
- **Hero Toast 时长**：5.5s → 8s，给用户更充裕时间看 stats 和快捷键提示。
- **打包**：`build.spec` 补上 `assets/fonts/*.ttf` 数据，frozen 后字体不再回退
  到系统 stack。`dist/settings.json` 重新写一份空 key 的版本，确认无 `dist/.env`。

## v1.2 — "Semantic Augmentor" (development log)

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
