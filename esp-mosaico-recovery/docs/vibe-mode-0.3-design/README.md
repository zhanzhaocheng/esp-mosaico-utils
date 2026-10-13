# Vibe Mode 0.3 界面设计与功能定义（阶段 A · 第 6 版）

| 项目 | 内容 |
| --- | --- |
| 状态 | v6 设计与可交互原型已实现；本目录只包含设计工具和生成物，**不修改固件** |
| 范围 | 480×480 Vibe Mode 信息架构、页面、交互、状态、商店接口输入与阶段 B handoff |
| 语言 | 本轮为英文；Noto Sans SC 子集保留给后续中文阶段 |
| 页面图 | `mockups/`：66 个页面状态，由 `layout.json`（schema `vibe-mode-design/6`）渲染，带 60 px 屏幕圆角遮罩 |
| 原型 | `prototype/index.html`：单文件离线原型，与页面图共用 `layout.json`；右侧有测试清单和模拟开关 |
| 验证 | `build_design.py --strict`：0 layout issues；Playwright smoke：66 passed, 0 failed |

![全部页面](mockups/00-overview.png)

## 1. v6 修订

### 修掉的细节问题

- **缺字**：Archivo / Inter 子集没有 `→ ← ✓ ● ○ ★ ☆`，v5 的部分文案会显示成方框。v6 全部改成图标或现有字符（`· • … ↑ ↓ ×`），并新增“字形覆盖”严格检查（按字体 cmap 校验每一段文案）。
- **Inter 文字偏上**：子集字体的 ascent/descent 按 1000 upm 写入，但 Inter 是 2048 upm。`generate_assets.py::_metrics()` 现按 `unitsPerEm` 换算，正文垂直居中恢复正常。
- **首页**：去掉像上标的计数；收藏星改为灰色；当前应用与“↑ Update available”用橙色第二行表达，不再叠圆点和箭头。
- **详情**：去掉与主按钮冲突的页码圆点；第 1 屏底部用 “About this app ⌄” 提示第 2 屏。
- **下载报错**：ID 卡片加高到 68 px，数字缩小一档后在下方显示错误原因。
- **进度**：0% 不再画出一个点；下载/更新有 Cancel，安装中不可取消（按 AI 会提示原因）。
- **分类“Communication”** 在 136 px 图块里放不下，改为 `Chat`。

### 图形

- 点阵图形全部重画为 7×7 网格（白色 + 橙色强调 + 暗格），4× 超采样后缩小：分类图块（56/96/120）、Guide/结果主视觉（120）和空状态（80）。Sensors 改为仪表、Wi‑Fi 改为扇形，小尺寸下也能辨认。
- 文字旁线性图标统一 20 px；页头/卡片 32 px；状态栏 28 px。新增 `clock`、`lock`。
- 加载动画为 8 帧点阵环（`assets/anim/spin32-*`、`spin64-*`）。

### 页面与交互

- **Browse 底部面板**：点首页 `My apps ⌄` 从下方滑出 3×3 图块（All / Recent / Favorites + 6 个分类，带数量）；点上方空白或下拉关闭。
- **Updates / Storage 行级操作**：Updates 每行可点进详情；`Update all` 在后台逐个更新，首页状态栏显示 `↓ k/n`，断网暂停、联网继续。Storage 按大小排序，点一行直接进入该应用的 About 页删除。
- **Wi‑Fi 当前网络页**：显示信号、加密方式、IP，底部 `Hold to forget`。
- **离线续接**：查询 ID、更新、开启 Mosaico AI、批量更新在离线时都会进入 Wi‑Fi 页并显示要继续的任务；连上后自动继续，离开 Wi‑Fi 页即取消。
- **Guide 5 步**：顶部进度点 + Skip；最后一步 `Later` / `Connect`，Connect 直接进入 Wi‑Fi。
- **启动提示**：有更新时顶部横幅 `2 updates · tap to see`，点按进入 Updates。

### 新增严格检查

字形覆盖、顶层按钮触控区重叠（最后一个 scrim 之上；列表裁切行除外）、危险按钮与其他按钮间距 ≥24 px、引用的图片必须存在、商店简介在 Inter 18 / 432 px 下 ≤3 行。底部面板（role `sheet`）不参与圆角和越界检查。

## 2. 480×480 设计系统

### 物理与几何

| 项目 | v6 值 |
| --- | --- |
| 屏幕 | 480×480，显示宽 38.8 mm |
| 像素尺寸 | `PX_MM = 38.8 / 480 = 0.0808 mm` |
| 屏幕圆角 | `SCREEN_R = 60` |
| 页面外边距 | 常规 16 px；危险操作左右/底边至少 24 px |
| 列表行 | 72 px 内容 + 8 px 间隔（80 px 节距） |
| 卡片圆角 | 18–20 px |
| 页面动效 | 48 px 位移，260 ms，`cubic-bezier(.32,.72,0,1)`；底部面板 300 ms |

### 字号

| 语义键 | 字体 | 允许字号 |
| --- | --- | --- |
| `sans` | Inter Regular 400 | 16 / 18 / 24 |
| `medium` | Archivo Extended Medium 500 | 18 / 22 / 28 |
| `dot` | Archivo Extended SemiBold 600 | 18 / 22 / 28 / 40 / 88 |

`dot` 只是历史兼容键名，不表示点阵文字。

### 触控与图标

| 对象 | 规则 |
| --- | --- |
| 默认触控 | ≥84×84 px |
| 密集例外 | 列表行、数字键盘键 ≥72 px；原生键盘沿用设备规范 |
| 页头圆形按钮 | 可见圆 64 px，透明命中区 84 px |
| 危险操作 | 高 96 px、距屏幕边 24 px、距其他按钮 ≥24 px；按住 600 ms |
| 线性图标 | 按钮/标题 32 px；文字旁 ≥20 px |
| 点阵图形 | 分类、引导、空状态、结果和加载动画使用预渲染位图 |

## 3. 页面与状态（66 个）

| 区域 | 状态 |
| --- | --- |
| Guide | 5 步 |
| Home | My apps、Favorites、分类、三种空状态、AI 提示、后台更新中、Browse 面板、快速切换 |
| Download | 空、输入中、查询中、报错 |
| Develop | Agent 已连接、等待 Agent（原型另有 USB 未插） |
| Detail | current、local、remote、update、nospace；About（本机 / 商店）；长按删除中；全屏 QR |
| Progress | Agent、download、install、update |
| Result | installed、saved、updated、failed、nospace、battery |
| Help | 主题列表；点按直接全屏 QR |
| Wi‑Fi | 已连接、未连接、待续任务、连接中、当前网络、密码（输入 / 连接中 / 错误） |
| Device | 设置列表、Wi‑Fi link、Updates（可更新 / 进行中 / 已最新 / 离线）、Storage（正常 / 将满） |
| Shared | City、City 输入、Mosaico AI（mosaico / own / none）、Own key |
| 运行 | Launching、App running |

机器可读定义见 `layout.json`；命名对象和坐标见 `layout-tables.md`。

## 4. 交互表

| # | 场景 | 行为 |
| --- | --- | --- |
| 1 | AI 单击 | 子页松开即返回；首页单击提示 “Press AI twice to switch apps”（最多 3 次，学会后不再提示） |
| 2 | 快速切换 | 首页 AI 双击（350 ms 内）打开，从当前应用的下一个开始；单击选下一个；按住 600 ms 或点卡片打开 |
| 3 | 快速切换空闲 | 4 s 无操作自动关闭；点卡片外关闭 |
| 4 | 边缘返回 | 从左侧 24 px 内右滑：页面跟手，≥96 px 或快速甩动提交，否则弹回 |
| 5 | 详情两屏 | 上滑 / 点 About this app 进第 2 屏；下滑或返回回第 1 屏 |
| 6 | Browse 面板 | 点 My apps 打开；点上方空白或下拉关闭；切换筛选后列表回到顶部 |
| 7 | 危险操作 | 按住 600 ms，进度画在按钮内，文字变 “Keep holding…”；提前松手取消；单击提示 “Hold to confirm” |
| 8 | 退格 | 点按删一位；按住 600 ms 清空 |
| 9 | 密码 | 提交后留在原页显示 Connecting…；错误也留在原页，键盘变暗不可输入 |
| 10 | 离线续接 | 见第 1 节；离开 Wi‑Fi 页提示 Cancelled |
| 11 | 空间预检 | 下载前计算剩余 NAND；不足时主按钮为 Free up space |
| 12 | 低电量 | 阻止切换/安装，显示 Battery low 结果页 |
| 13 | 安装完成 | 3 s 倒计时点后自动打开；可 Stay here / Open now |
| 14 | 后台更新 | 逐个更新；状态栏 `↓ k/n`；断网暂停 |
| 15 | 删除后 | 返回原列表并保持滚动位置 |
| 16 | 键盘 | 字母按下显示放大气泡；密码和 key 默认遮蔽，可切换显示 |
| 17 | 回到 Vibe Mode | 应用运行中按住 AI 并双击开关机键；松开 AI 前不响应按键 |
| 18 | 横幅 | 顶部滑入；带操作的横幅可点按（如 updates → Updates 页） |

## 5. 主要流程

1. **打开应用**：Home → 应用行 → Detail → Open app（非当前应用先切换，再倒计时打开）。
2. **按 ID 下载**：Download → 输入 ID → Go → Detail → Download & open / Save → 进度 → 结果。
3. **离线下载**：Go → Wi‑Fi（显示 “Connect to look up 238114”）→ 选网络 → 密码 → 连上后自动继续查询。
4. **批量更新**：横幅或 Device → App updates → Update all → 后台进行，可继续使用。
5. **释放空间**：Free up space 或 Device → App storage → 选应用 → Hold to delete。
6. **Mosaico AI**：首次联网自动开启；可 Hold to turn off；Turn on Mosaico AI 离线时先去 Wi‑Fi。
7. **帮助**：Help → 主题 → 全屏二维码。

## 6. 英文文案

固定文案在 `tools/build_design.py` 中按真实字体测宽并检查字形覆盖。

| 区域 | 文案 |
| --- | --- |
| Home | `My apps` · `Current app` · `↑ Update available` · `↑ 2` · `↓ 1/2` |
| Detail | `Open app` · `Update` · `QR code` · `Download & open` · `Save` · `Update & open` · `Free up space` · `About this app` |
| Danger | `Hold to delete` · `Hold to forget` · `Hold to turn off` · `Hold to remove key` · `Keep holding…` |
| Updates | `Update all` · `Keep using Vibe Mode` · `All up to date` · `Can't check now` |
| Storage | `<used> MB of 64 MB used` · `LARGEST FIRST · TAP TO DELETE` |
| Result | `App installed` · `Saved to My apps` · `Update complete` · `Couldn't download` · `Not enough storage` · `Battery low` |
| Mosaico AI | `Mosaico AI is on` · `Using your own key` · `Mosaico AI is off` · `Turn on Mosaico AI` · `Use my own key` |
| Guide | `Get started` · `Back` · `Next` · `Later` · `Connect` |

应用名、SSID 和商店简介动态截断；商店简介限制 ASCII ≤120 字节，且在详情第 2 屏 ≤3 行。

## 7. 资源

`tools/generate_assets.py` 每次执行都会：

1. 从 `--mosaico-fonts` 重建 Archivo Extended 500/600 与 Inter 400（按 upm 写入正确的行高度量）；默认路径为：
   `/Users/zhanzhaocheng/project/esp-mosaico/design/mosaico-ui/src/assets/fonts`
2. 可选从 `--google-fonts` 更新 Noto Sans SC 中文阶段子集。
3. 按 `ICON_OUTPUTS` 生成 20/28/32 px 线性图标（白 / 灰 / 橙 / 黑 / 暗色变体）。
4. 按 `PICTOGRAMS` 生成 `assets/mosaic/` 点阵图块与主视觉。
5. 生成 `assets/anim/` 加载动画帧、`assets/qr/` 二维码和 `assets/ui/` 列表渐隐。

字体许可证：

- `assets/fonts/OFL-Archivo.txt`
- `assets/fonts/OFL-Inter.txt`
- `assets/fonts/OFL-NotoSansSC.txt`（中文阶段来源）

## 8. 本地数据与 sysmeta

应用文件仍位于：

```text
/nand/apps/<app_id>/app.json
/nand/apps/<app_id>/manifest.json
/nand/apps/<app_id>/<components>
/nand/apps/.<app_id>.part/
```

使用或新增以下 `sysmeta` 键：

| Key | 内容 |
| --- | --- |
| `vibe_apps/favorites` | 收藏 ID，最多 64 个 |
| `vibe_apps/recent` | 最近打开 ID，CURRENT 不重复写入，按最近优先 |
| `vibe_prefs/filter` | 上次列表筛选 |
| `vibe_prefs/ai_hint` | AI 提示次数与是否已学会双击 |
| `vibe_prefs/ai_opt_out` | 用户主动关闭 Mosaico AI 后不再自动开启 |
| `vibe_prefs/guide_done` | 首次引导已完成 |
| `shared/city` | 所有应用可读的城市 |
| `shared/ai_token` | 所有应用可读的 token/key |
| `shared/ai_token_kind` | `mosaico` / `own` / `none` |
| `wifi/*` | 已有 Wi‑Fi 配置 |

`shared/ai_token_kind=none`、未主动关闭且首次在线时自动申领 Mosaico token；成功后原子写入 token 和 kind。社区应用可读共享 token，产品应优先发放限额、可吊销、按设备区分的 token。

## 9. Mosaico Ideas 商店接口需求

| 编号 | 需求 |
| --- | --- |
| R1 | 按纯数字 ID 查询最新版；设备无商店会话和配对步骤 |
| R2 | 请求携带 MAC、Vibe 版本、兼容字段、reason 和本地版本 |
| R3 | 返回 ASCII 显示名、版本、official、分类、≤120 字节简介 |
| R4 | 返回稳定详情 URL，建议 ≤53 字节以保持 QR version 3-L |
| R5 | 返回 System Update manifest 与 HTTPS 组件 URL |
| R6 | 区分不存在、下架、不兼容、无权限、限流、维护和网络错误 |
| R7 | ID 号段由服务端管理，设备只验证纯数字 |
| R8 | 第三方 NAND 风险在商店网页提示 |
| R9 | 支持按 ID 的下载/安装统计 |
| R10 | 代理 token（Mosaico AI）的发放、配额、吊销与续期；设备首次联网可自动申领 |
| R11 | 批量查询本地应用的最新版本（供 Updates / Update all） |
| R12 | 更新响应提供稳定 operation/release ID、ETag/长度并支持 HTTPS Range，以便断线续传和同版本恢复 |
| R13 | 返回下载大小、落盘大小和安装临时空间需求；设备可在传输前完成 NAND 空间预检 |

设备端仍要求 TLS 校验、HTTPS-only、最多 3 次 HTTPS 重定向、流式 SHA-256 校验和原子目录替换。

## 10. 阶段 B handoff

本轮不修改固件。阶段 B 实现时需：

- 保持 `layout.json` 中的对象名、行高和 `prototype.interactions` 常量。
- 用 GSP 原生 StackView/列表/键盘实现；详情两屏为纵向 snap；Browse 为底部面板覆盖层。
- 将按住进度绑定 600 ms 定时器，离页/松手时取消。
- 后台更新、续接任务、空间预检、token 自动申领和 sysmeta 写入做成可恢复事务。
- 在真机复核 38.8 mm 下的字号、R60 裁切、QR 扫描、触摸、AI GPIO、NAND 容量和帧率。

## 11. 再生成与验证

```sh
cd esp-mosaico-recovery/docs/vibe-mode-0.3-design

.venv/bin/python tools/generate_assets.py
.venv/bin/python tools/build_design.py --strict
.venv/bin/python tools/build_prototype.py
node tools/prototype_smoke.js [截图目录]
```

预期：

```text
66 states rendered; 0 layout issues
66 passed, 0 failed
```

如 Playwright 不在默认 Node 搜索路径中：

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright node tools/prototype_smoke.js
```
