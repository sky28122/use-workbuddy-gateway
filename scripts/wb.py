#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WorkBuddy 本机网关 CLI（仅用标准库）。

子命令：
  check                       网关/账号池/模型数一次性体检，非 0 退出码表示不可用
  status                      账号池明细（含 realm / credits / 冷却 / 禁用）
  models [--realm cn|global]  列模型 id 与能力位
  ask MODEL "提示词"           非流式对话；--stream 走 SSE；--file 从文件读提示词
  tools MODEL                 探测该模型是否支持 function calling
  agent MODEL "任务"           把模型当子执行者跑多轮工具循环（内置只读 list_dir/read_file，
                               路径严格限制在 --root 内；--conversation-id 可钉住同一账号复用缓存）

密钥来源优先级：WB2API_KEY 环境变量 > WB2API_KEYFILE 指向的文件 >
一键安装器的标准安装目录。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("WB2API_BASE", "http://127.0.0.1:7863")


def default_key_files():
    """Return portable key locations without assuming an author's machine."""
    paths = []
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        paths.append(
            os.path.join(
                local_app_data,
                "workbuddy-gateway",
                "workbuddy2api",
                "API_KEY.txt",
            )
        )
    paths.append(
        os.path.join(
            os.path.expanduser("~"),
            ".workbuddy-gateway",
            "workbuddy2api",
            "API_KEY.txt",
        )
    )
    return paths


def api_key():
    env = os.environ.get("WB2API_KEY", "").strip()
    if env:
        return env
    explicit = os.environ.get("WB2API_KEYFILE", "").strip()
    candidates = ([explicit] if explicit else []) + default_key_files()
    for path in candidates:
        if path and os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.startswith("api_key"):
                        return line.split("=", 1)[1].strip()
    sys.exit(
        "FAIL 找不到网关密钥：请设置 WB2API_KEY 或 WB2API_KEYFILE，"
        "或先运行 scripts/setup.ps1。"
    )


def request_headers(path):
    headers = {"Content-Type": "application/json"}
    if path != "/healthz":
        headers["Authorization"] = "Bearer " + api_key()
    return headers


def req(path, payload=None, timeout=180, stream=False):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(
        BASE + path, data=data,
        headers=request_headers(path),
    )
    try:
        return urllib.request.urlopen(r, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        sys.exit("FAIL HTTP %s %s\n%s" % (e.code, path, body))
    except urllib.error.URLError as e:
        sys.exit(
            "FAIL 连不上 %s（%s）\n"
            "网关未启动？请运行安装目录中的 start-workbuddy2api.cmd，"
            "或重新执行 scripts/setup.ps1。" % (BASE, e.reason)
        )


def fmt_flags(m):
    return "tool=%s img=%s reason=%s ctx=%s" % (
        bool(m.get("supports_tool_call")), bool(m.get("supports_images")),
        bool(m.get("supports_reasoning")), m.get("context_length"))


def cmd_check(_a):
    h = json.load(req("/healthz", timeout=10))
    s = json.load(req("/status", timeout=20))
    ms = json.load(req("/v1/models", timeout=60))["data"]
    cn = sum(1 for m in ms if m["id"].startswith("cn:"))
    gl = sum(1 for m in ms if m["id"].startswith("global:"))
    rt = s.get("realm_totals", {})
    print("gateway  OK   %s  healthy=%s/%s" % (h.get("service"), h.get("healthy"), h.get("total")))
    print("pool     cn %s/%s  global %s/%s  cooling=%s disabled=%s  redis=%s" % (
        rt.get("cn", {}).get("healthy"), rt.get("cn", {}).get("total"),
        rt.get("global", {}).get("healthy"), rt.get("global", {}).get("total"),
        s.get("cooling"), s.get("disabled"), s.get("redis_mode")))
    print("models   cn=%d global=%d total=%d" % (cn, gl, len(ms)))
    bad = [a for a in s.get("accounts", []) if a.get("disabled") or a.get("manual_disabled")]
    if bad:
        print("warn     被禁用账号 %d 个；运行 status 查看脱敏状态" % len(bad))
    if not s.get("total"):
        sys.exit("FAIL 账号池为空，任何对话都发不出去")


def cmd_status(a):
    s = json.load(req("/status", timeout=20))
    for index, account in enumerate(s.get("accounts", []), start=1):
        if a.show_identities:
            label = "%s %-22s" % (
                str(account.get("uid"))[:8],
                str(account.get("nickname"))[:22],
            )
        else:
            label = "account-%02d" % index
        print("%-10s %-22s realm=%-7s credits=%-8s disabled=%s cooling=%s" % (
            label,
            "" if a.show_identities else "[identity hidden]",
            account.get("realm"),
            account.get("credits"),
            bool(account.get("disabled") or account.get("manual_disabled")),
            bool(account.get("cooling")),
        ))
    print("total=%s healthy=%s cooling=%s disabled=%s sticky=%s" % (
        s.get("total"), s.get("healthy"), s.get("cooling"), s.get("disabled"), s.get("sticky_sessions")))


def cmd_models(a):
    ms = json.load(req("/v1/models", timeout=60))["data"]
    if a.realm:
        ms = [m for m in ms if m["id"].startswith(a.realm + ":")]
    for m in sorted(ms, key=lambda x: x["id"]):
        print("%-42s %s" % (m["id"], fmt_flags(m)))
    print("count=%d" % len(ms))


def build_messages(model, prompt, system):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return {"model": model, "messages": msgs, "stream": False}


def cmd_ask(a):
    prompt = a.prompt or ""
    if a.file:
        prompt = open(a.file, encoding="utf-8").read()
    if not prompt.strip():
        sys.exit("FAIL 提示词为空（用位置参数或 --file）")
    body = build_messages(a.model, prompt, a.system)
    t0 = time.time()
    if not a.stream:
        j = json.load(req("/v1/chat/completions", body))
        m = j["choices"][0]["message"]
        if m.get("reasoning_content") and a.show_reasoning:
            print("--- reasoning ---\n" + m["reasoning_content"][:2000])
        print(m.get("content") or "")
        u = j.get("usage") or {}
        print("\n[credit=%s tokens=%s+%s 耗时=%.1fs]" % (
            u.get("credit"), u.get("prompt_tokens"), u.get("completion_tokens"), time.time() - t0))
        return
    body["stream"] = True
    out, frames = [], 0
    with req("/v1/chat/completions", body, stream=True) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            frames += 1
            try:
                d = json.loads(line[5:].strip())
            except ValueError:
                continue
            for ch in d.get("choices") or []:
                c = (ch.get("delta") or {}).get("content")
                if c:
                    out.append(c)
                    sys.stdout.write(c)
                    sys.stdout.flush()
    print("\n[frames=%d 耗时=%.1fs]" % (frames, time.time() - t0))


def cmd_tools(a):
    tools = [{"type": "function", "function": {
        "name": "ping", "description": "回显一个值",
        "parameters": {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}}}]
    body = {"model": a.model, "tool_choice": "required", "stream": False, "tools": tools,
            "messages": [{"role": "user", "content": "调用 ping 工具，value 填 hello"}]}
    j = json.load(req("/v1/chat/completions", body))
    ch = j["choices"][0]
    tcs = ch["message"].get("tool_calls") or []
    print("%s finish_reason=%s tool_calls=%d %s" % (
        a.model, ch.get("finish_reason"), len(tcs),
        [t["function"]["name"] + "(" + t["function"]["arguments"][:40] + ")" for t in tcs]))
    if not tcs:
        print("=> 该模型未产出工具调用，不要用它跑 agent 循环")


# ---------- 子代理循环：内置两个只读工具，路径严格限制在 --root 内 ----------

AGENT_TOOLS = [
    {"type": "function", "function": {
        "name": "list_dir", "description": "列出 root 内某目录的条目（只读）",
        "parameters": {"type": "object", "properties": {"path": {"type": "string",
            "description": "相对 root 的路径，空串表示 root"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "读取 root 内文本文件，返回前 2000 字符（只读）",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]

SENSITIVE_PARTS = {".git", ".ssh", "auths", "credentials", "secrets"}
SENSITIVE_NAME_FRAGMENTS = (
    ".env",
    "api_key",
    "apikey",
    "credential",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "session",
    "token",
    "cookie",
)
SENSITIVE_EXACT_NAMES = {"auth.json", "config.json"}


def _is_sensitive_path(rel):
    """Reject common credential locations before a file reaches the model."""
    normalized = str(rel).replace("\\", "/").strip("/").lower()
    parts = [part for part in normalized.split("/") if part]
    if any(part in SENSITIVE_PARTS for part in parts):
        return True
    name = parts[-1] if parts else ""
    if name in SENSITIVE_EXACT_NAMES:
        return True
    if name.endswith((".key", ".p12", ".pem")):
        return True
    return any(fragment in name for fragment in SENSITIVE_NAME_FRAGMENTS)


def _inside(root, rel):
    fp = os.path.realpath(os.path.join(root, str(rel)))
    try:
        common = os.path.commonpath([fp, root])
    except ValueError as error:
        raise ValueError("越界路径被拒绝: %r（只允许 root 之内）" % (rel,)) from error
    if common != root:
        raise ValueError("越界路径被拒绝: %r（只允许 root 之内）" % (rel,))
    return fp


def _exec_tool(root, name, args):
    try:
        rel = args.get("path", "")
        if _is_sensitive_path(rel):
            return json.dumps(
                {"error": "敏感路径被拒绝，不能发送给模型"},
                ensure_ascii=False,
            )
        if name == "list_dir":
            fp = _inside(root, rel)
            ents = [
                entry
                for entry in sorted(os.listdir(fp))
                if not _is_sensitive_path(
                    os.path.relpath(os.path.join(fp, entry), root)
                )
            ]
            return json.dumps({"dir": os.path.relpath(fp, root), "count": len(ents),
                               "entries": ents[:60]}, ensure_ascii=False)
        if name == "read_file":
            fp = _inside(root, args["path"])
            with open(fp, encoding="utf-8", errors="replace") as handle:
                head = handle.read()[:2000]
            return json.dumps({"path": args["path"],
                               "head": head},
                              ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    return json.dumps({"error": "unknown tool " + name}, ensure_ascii=False)


def cmd_agent(a):
    """把网关模型当子执行者跑：自主多轮 + 只读工具，直到 finish_reason=stop。"""
    root = os.path.realpath(a.root)
    msgs = [{"role": "system", "content": a.system}, {"role": "user", "content": a.prompt}]
    for turn in range(1, a.max_turns + 1):
        body = {"model": a.model, "messages": msgs, "tools": AGENT_TOOLS,
                "tool_choice": "auto", "stream": False}
        if a.conversation_id:
            body["metadata"] = {"conversation_id": a.conversation_id}
        t0 = time.time()
        j = json.load(req("/v1/chat/completions", body))
        ch = j["choices"][0]
        m = ch["message"]
        u = j.get("usage") or {}
        tcs = m.get("tool_calls") or []
        print("[轮%d] %.1fs finish=%s credit=%s cache_hit=%s tools=%d" % (
            turn, time.time() - t0, ch.get("finish_reason"), u.get("credit"),
            u.get("prompt_cache_hit_tokens"), len(tcs)))
        if m.get("content"):
            print("  文本:", m["content"][:400].replace("\n", " "))
        if not tcs:
            print("\n=== 最终答案 ===")
            print(m.get("content") or "(空)")
            return
        msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": tcs})
        for tc in tcs:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except ValueError:
                args = {}
            out = _exec_tool(root, tc["function"]["name"], args)
            print("  调用", tc["function"]["name"], args, "->", out[:160].replace("\n", " "))
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
    print("FAIL 到达 --max-turns=%d 仍未收敛，剩下的判断交给你自己" % a.max_turns)
    sys.exit(3)



def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="WorkBuddy 本机网关 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    status = sub.add_parser("status")
    status.add_argument(
        "--show-identities",
        action="store_true",
        help="显示账号 UID/昵称；默认脱敏，避免日志泄露个人信息",
    )
    status.set_defaults(fn=cmd_status)
    m = sub.add_parser("models"); m.add_argument("--realm", choices=["cn", "global"])
    m.set_defaults(fn=cmd_models)
    a = sub.add_parser("ask"); a.add_argument("model"); a.add_argument("prompt", nargs="?")
    a.add_argument("--system"); a.add_argument("--file"); a.add_argument("--stream", action="store_true")
    a.add_argument("--show-reasoning", action="store_true"); a.set_defaults(fn=cmd_ask)
    t = sub.add_parser("tools"); t.add_argument("model"); t.set_defaults(fn=cmd_tools)
    g = sub.add_parser("agent")
    g.add_argument("model"); g.add_argument("prompt")
    g.add_argument("--root", default=os.getcwd(), help="工具可访问的目录根，默认当前目录")
    g.add_argument("--system", default="你是主 agent 派发的子执行者，只能用给定工具。信息够了就直接给中文结论，不要再调工具。")
    g.add_argument("--max-turns", type=int, default=6)
    g.add_argument("--conversation-id", help="固定会话键，让多轮钉住同一个账号、复用上游 prompt cache")
    g.set_defaults(fn=cmd_agent)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
