# Infinite Canvas Windows 桌面版

这是对原项目的本地桌面封装，保留 FastAPI 后端和现有画布前端。桌面入口使用 Windows WebView2，安装后无需系统 Python。

## 本地开发运行

```powershell
python -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv-desktop\Scripts\python.exe desktop_app.py
```

## 构建

```powershell
.\build_windows.bat -SkipInstaller
```

便携版输出到 `dist\InfiniteCanvas\InfiniteCanvas.exe`。如已安装 Inno Setup，并去掉 `-SkipInstaller`，安装包会输出到 `dist-installer`。

## 用户数据

默认数据目录为 `%LOCALAPPDATA%\InfiniteCanvas`，包括画布、素材、输出、工作流和 API 配置。卸载应用不会删除该目录。

可在启动前设置 `INFINITE_CANVAS_DATA_ROOT`，将数据放到自定义目录。首次桌面启动会把项目目录中已有的数据复制到用户目录；已有文件不会被覆盖。

桌面模式只监听 `127.0.0.1` 的随机端口，并禁用原项目会直接覆盖程序文件的更新和回滚接口。升级桌面版请使用新的安装包。

## 许可证

本桌面封装继续受仓库根目录 `LICENSE` 约束：保留原作者来源、保持二次开发代码开源，未经授权不得封装为商业产品。
