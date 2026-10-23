# Agent 桌宠 · 源码模板

Windows 桌面 Live2D 助手模板，包含透明置顶角色窗口、任务状态卡、提醒收件箱、陪伴目标、游戏安静模式，以及蓝白圆角快捷栏。快捷栏保留独立 `Form.TopMost` 浮窗与单图标平滑过渡。

**这是需要自备模型与第三方运行库的源码模板，不是带角色的即开即用安装包。** 首次缺少资源时会在创建窗口、获取单实例锁之前列出缺失项并退出，不会留下空白透明窗口。

## 环境与安装

1. Windows 10/11 x64，安装 Windows x64 CPython 3.12（包含 `py` 启动器）。安装 Microsoft Edge WebView2 Runtime：[微软官方页面](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)。
2. 将本目录解压到可写位置。双击 `安装依赖.cmd`，它会创建目录内的 `.venv` 并安装 `requirements.txt`。也可在本目录手动执行：

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. 安装下面的 JavaScript 库及模型。
4. 双击 `诊断.cmd`，完成缺失项后双击 `启动桌宠.cmd`。前台启动支持参数，例如 `启动桌宠.cmd --show-banner`。后台启动可执行 `powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File .\pet-launcher.ps1`。

依赖安装、下载与桌宠运行均由使用者在本机执行；仓库不携带第三方 DLL、Python 安装包或内嵌浏览器。

## 第三方组件安装

安装 Node.js 后，在本目录的 PowerShell 执行固定版本安装（只需用于准备前端库，运行桌宠不需要 Node）：

```powershell
npm install --ignore-scripts --no-audit --no-fund --no-save --package-lock=false pixi.js@6.5.10 pixi-live2d-display@0.4.0
New-Item -ItemType Directory -Force web/lib | Out-Null
Copy-Item node_modules/pixi.js/dist/browser/pixi.min.js web/lib/pixi-v6.min.js
Copy-Item node_modules/pixi-live2d-display/dist/cubism4.min.js web/lib/pixi-live2d-display-cubism4.min.js
```

上游：[PixiJS](https://github.com/pixijs/pixijs/tree/v6.5.10)、[pixi-live2d-display 0.4.0](https://github.com/guansss/pixi-live2d-display/tree/v0.4.0)。PixiJS 使用 MIT；显示适配器包含 Cubism Framework 内容，不能将整个打包文件的所有内容都视作本项目 MIT。请保留下载包中的各项许可证；本模板不代为分发这些库。

从 [Live2D 官方 SDK for Web 页面](https://www.live2d.com/en/sdk/download/web/)阅读并接受相应许可，自行取得与 Cubism 4 模型兼容的 `Core/live2dcubismcore.min.js`，复制为 `web/lib/live2dcubismcore.min.js`。Core 不属于本项目 MIT；本模板不自动下载，也不随包提供。请不要使用浮动 `latest` 在线脚本替代本地文件。不同 SDK/Core 版本是否兼容需在用户本机验证。

## 自备模型

创建 `web/model/`，放入您有权使用的 Cubism 3/4 模型完整目录（`.moc3`、纹理、动作、表情等）。将模型的 `.model3.json` 复制为该目录下的 `settings.json`，保留其中相对文件路径；无需更改原文件名引用。`web/model-settings.example.json` 仅展示最小结构，**不是可运行模型**。

```text
web/model/
  settings.json
  your-model.moc3
  your-model.cdi3.json         # 可选显示名称；FileReferences.DisplayInfo 指向它
  textures/texture_00.png
  ...                        # settings.json 引用的动作、表情等
```

原实现对表情名称、`Idle`/`Show` 动作组、角色底部三个交互区及部分道具参数有约定。这些约定保留在 `settings_store.py`、`web/pet.js`、`run.py` 中。替换模型后，可在设置页调整表情映射与动作白名单；没有同名表情/参数时相应互动可能不生效，底部交互区可能需要按新角色调整。快捷栏不依赖角色自带的三个按钮。

不包含原角色、宝可梦素材、模型贴图、截图或原图标。托盘使用 Windows 系统图标作为缺省值；如需自定义，使用您有权使用的 `web/icon.ico`。

## 本机数据与可选功能

- 默认读取当前 Windows 用户的 Codex 本地记录，其他 Agent 可在设置中切换。状态适配器依赖上游应用记录格式，版本变化可能影响识别。状态记录、任务标题及用量仅在本机处理；勿将运行后的日志、截图或数据目录提交到公共仓库。
- 额度查询默认关闭。手动开启 Codex 模式会启动本机已登录 CLI 的 `app-server` 读取额度；DeepSeek 模式只访问 `https://api.deepseek.com/user/balance`，需要在本机 API 设置中自行输入官方密钥。密钥由 Windows DPAPI 绑定当前用户加密；仓库不含密钥或账户配置。
- 常用工具默认是空列表。复制 `assistant_tools.example.json` 为 `assistant_tools.json`，按需写入您本机的绝对路径：文件夹项为 `id/name/kind="folder"/path`；应用项为 `kind="app"`，另需准确的 `title`，`path` 指向 Python 入口。只添加可信脚本。工具由当前 Python 环境运行，需要自行安装其依赖。
- 运行后配置、位置、陪伴记录、日志和 WebView2 缓存保存在本目录；用户状态 JSON 全部被 `.gitignore` 排除。更新代码前自行备份。模板单实例锁按安装目录区分，避免与其他目录的桌宠共用锁。
- 创建桌面快捷方式、开机自启和清缓存由设置页手动操作；后台启动器依赖 `.venv`。清缓存只处理本目录的 `.webview2`。

## 验证与限制

发布副本经过 Python 语法编译、纯逻辑模块导入与临时目录测试、默认配置检查、缺失模型预检查及文件清单审查。未启动桌宠窗口、未查询账户、未读取真实用户配置；未在干净 Windows 上完成依赖下载及带模型的端到端测试。模型、Core 和 WebView2 的图形兼容性需使用者本机验证。

`诊断.cmd` 仅检查本地资源/依赖，不查询 Agent 或账户。开发调试可运行 `run.py --state-only`，但其输出会包含您本机状态，不要直接发到公共 issue。

源码许可见 [LICENSE](LICENSE)，第三方范围与归属见 [THIRD-PARTY.md](THIRD-PARTY.md)。保留原许可证的作者占位文字，没有据此推定或新增版权人。
