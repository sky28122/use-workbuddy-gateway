# use-workbuddy-gateway

[中文](README.md) | [English](README.en.md)

面向 Codex/Qoder 的本地 WorkBuddy 网关 Skill：一键部署
`workbuddy2api`，并提供健康检查、模型查询、对话、function calling 探测和有界只读代理循环。

> 非官方项目，与腾讯、WorkBuddy、CodeBuddy 及上游项目维护者无隶属关系。

## 一键安装（Windows）

下载本仓库后，在仓库目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

安装器会校验仓库内附带的固定版本上游源码包，并自动完成 Go 环境准备、编译、随机密钥生成、回环监听配置、
Skill 安装和网关启动。首次使用时会打开上游官方 OAuth/设备授权页面；用户只需在浏览器完成授权。

如需先查看操作而不改动机器：

```powershell
.\scripts\setup.ps1 -PlanOnly
```

详细选项见 [Windows 部署说明](references/setup-windows.md)。

## 使用

```powershell
python .\scripts\wb.py check
python .\scripts\wb.py models --realm global
python .\scripts\wb.py ask global:deepseek-v4.1-flash "请概括这段内容"
python .\scripts\wb.py tools global:deepseek-v4.1-flash
python .\scripts\wb.py agent global:deepseek-v4.1-flash "检查这个目录" --root . --conversation-id demo
```

`status` 默认隐藏账号 UID 和昵称；只有明确需要时才使用 `--show-identities`。

## 安全边界

- 仅使用本人所有或已获授权的账号，并遵守目标平台服务条款。
- 默认只监听 `127.0.0.1:7863`，不要未经安全设计直接开放公网。
- 不要提交或分享 `API_KEY.txt`、`config.json`、`auths/`、日志或任何 token。
- `agent` 会把选中文件内容发送给模型。请将 `--root` 限定在不含敏感数据的目录；脚本虽会拒绝常见凭证路径，但不能替代人工判断。
- 本项目仅提供本地编排与安装工具，不提供账号、额度、代理池或平台限制绕过功能。

## 来源与许可

本项目自身代码使用 MIT License。仓库内附带了
[Sliverkiss/workbuddy2api](https://github.com/Sliverkiss/workbuddy2api)
固定提交的源码 ZIP，并保留其 MIT 许可证；具体来源与许可见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
