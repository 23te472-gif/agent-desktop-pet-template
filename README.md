# Agent Desktop Pet · 开源源码副本

本项目基于原版桌宠及其 Live2D 鲸鱼娘形象与旧版界面进行二次开发，扩展和优化原有功能，并新增龙娘形象支持。

Windows 桌面助手：Agent 状态、提醒收件箱、勿扰、陪伴互动、额度气泡，以及可选的外部工具中心入口。包含环绕互动、分组“更多”、冷白蓝/暖白绿和窄柔边。

这是**自备模型与运行库的源码模板**。本仓库不附带角色模型及相关素材，使用时需自行准备并遵守原作者授权。不包含个人配置、登录信息或第三方二进制。缺少资源时会在创建窗口和取得单实例锁之前列出缺失项并退出。

## 安装与启动

Windows 10/11 x64，64 位 CPython 3.12，以及 Microsoft Edge WebView2 Runtime。

1. 在可写位置解压，运行 `安装依赖.cmd`，或执行：

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. 自行准备下述前端运行库与有权使用的模型。
3. 运行 `诊断.cmd`；检查通过后运行 `启动桌宠.cmd`。例如 `启动桌宠.cmd --show-banner`。
4. 后台启动：`powershell -NoProfile -File .\pet-launcher.ps1`。设置页的桌面快捷方式与可选自启复用该入口，只在使用者明确点击时创建。

脚本使用项目 `.venv`，不查找 Codex 的内置 Python。也可显式设置 `AGENT_PET_PYTHON` 为自行配置的 Python 绝对路径，再使用 PowerShell 启动器。运行代码后不向源码目录保存用户配置。

## 自备模型与前端库

创建 `web/model/`，将自己的 Cubism 3/4 模型完整放入，主 `.model3.json` 以 `settings.json` 命名，保持相对文件引用正确。最小结构参见 `examples/model-settings.example.json`，该示例不是可运行模型。原角色扩展未提供时，设置页禁用该选项。

自备以下本地库；不使用在线 `latest` 脚本：

- `web/lib/pixi-v6.min.js`：PixiJS 6.5.10。
- `web/lib/pixi-live2d-display-cubism4.min.js`：pixi-live2d-display 0.4.0。
- `web/lib/live2dcubismcore.min.js`：从 Live2D 官方 SDK 获取与模型兼容的 Core，阅读相应许可。

可使用 npm 准备前两项（只有准备库时需要 Node.js）：

```powershell
npm install --ignore-scripts --no-audit --no-fund --no-save --package-lock=false pixi.js@6.5.10 pixi-live2d-display@0.4.0
New-Item -ItemType Directory -Force web/lib | Out-Null
Copy-Item node_modules/pixi.js/dist/browser/pixi.min.js web/lib/pixi-v6.min.js
Copy-Item node_modules/pixi-live2d-display/dist/cubism4.min.js web/lib/pixi-live2d-display-cubism4.min.js
```

模型的表情名、动作组和道具参数由其作者定义；替换角色后，应调整设置中的表情映射、动作白名单及角色底部交互区。通用快捷工具栏独立于角色的道具按钮。

## 源码、个人数据与外部工具

| 内容 | 保存位置 |
| --- | --- |
| 程序、前端与通用界面图形 | 本项目目录 |
| 用户设置、桌宠位置、设置窗口尺寸、提醒/亲密度、DPAPI 凭据 | `%LOCALAPPDATA%/AgentDesktopPet/` |
| WebView2 缓存 | 数据目录的 `cache/webview2/` |
| 运行日志、进程号、退出/清缓存请求、状态桥 | 数据目录；均不进入源码包 |
| 个人工具中心 | 独立项目，按需配置，不打包或自动打开 |

运行 `python maintenance.py --paths` 可查看本机实际目录。设置 `AGENT_PET_DATA_DIR` 为与源码目录互不包含的绝对路径，可使用完全独立的测试配置。不要把源码解压进个人数据或缓存目录。单实例锁和快捷方式名称按数据目录区分，与旧安装版分开。

移动源码目录会继续使用同一用户数据目录。运行中的数据目录不要手动删除；窗口位置是有用途的偏好，不是缓存。需要重置时先退出桌宠并备份对应 JSON。

工具入口默认为空。将 `assistant_tools.example.json` 复制到数据目录并命名为 `assistant_tools.json`，按需配置 `id="center"`、`kind="app"`、`name`、Python 脚本的绝对 `path` 和准确窗口 `title`。默认不附其他个人软件路径，未配置时界面会提示。

API 额度查询默认关闭。启用 Codex 查询使用当前使用者自行安装、登录的客户端；DeepSeek 密钥由使用者在本机输入并用当前 Windows 用户 DPAPI 加密。密文也属于个人数据，不应分享。状态适配器读取当前用户已有的 Agent 记录，不代表离线模型或不消耗配额。

`status-bridge.py` 与桌宠读取同一个数据目录的 `status/`。示例：

```powershell
python status-bridge.py --agent demo --state working --title "测试任务"
```

## 维护与诊断

- `run.py --check`：只检查资源和依赖，不读取 Agent 记录、查询余额或开启窗口。
- `run.py --paths` / `maintenance.py --paths`：显示本机目录；不要把带个人路径的输出原样提交到公共 issue。
- `maintenance.py --stop`：只向当前数据配置发送正常退出请求，不强杀进程。
- 设置中的清缓存只删除已校验的 `cache/webview2/`，等旧进程正常退出后处理；重解析点或未退出的进程会阻止清理。
- 调用栈快照默认关闭；仅调试时设置 `AGENT_PET_DEBUG_STACKS=1`。日志可能包含任务标题或本机路径，分享前应自行检查。

## 验证与许可

本副本完成语法、数据目录隔离、缺资源退出、换目录与静态隐私检查。未在全新 Windows 机器上重新下载依赖、安装模型并执行完整图形端到端测试；第三方图形兼容性仍需使用者本机验证。

代码许可保留原 [LICENSE](LICENSE)，未替换其作者占位行。第三方和素材边界见 [THIRD-PARTY.md](THIRD-PARTY.md)。通用 SVG 及其 PNG 界面图形属于程序 UI；原角色图片、托盘角色图标与模型未包含。Microsoft WebView2 Runtime：[官方入口](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)；Live2D SDK：[官方入口](https://www.live2d.com/en/sdk/download/web/)。
