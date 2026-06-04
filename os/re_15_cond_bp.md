# 逆向工程 — 第十五课：条件断点

## BreakpointManager 架构

```
BreakpointManager
├── bps: Dict[str, Breakpoint]
│   └── Breakpoint
│       ├── id / addr / type (SW|HW)
│       ├── hit_count / conditions
│       │   ├── hit_cond: ">5" | ">=10" | "==3" | "once"
│       │   └── expr: "RCX > 0" | "RAX > 0x1000 and RDX == 0"
│       ├── log_msg: 可选日志模板
│       ├── group: 分组管理
│       ├── enabled / oneshot
│       ├── set() / remove() / hit()
│       └── check_break() → bool
├── groups: Dict[str, List[Breakpoint]]
└── save() / load() → JSON
```

## 条件类型

| 条件 | 描述 | 示例 |
|------|------|------|
| hit>N | 命中 N 次后中断 | `hit>3` |
| hit>=N | 命中 ≥ N 次中断 | `hit>=10` |
| hit==N | 命中等 N 次中断 | `hit==5` |
| once | 命中一次 + 自动移除 | `oneshot` |
| expr | 寄存器/内存条件 | `RCX > 0 and RAX > 0x1000` |
| log | 不中断，仅日志 | `log: "malloc(%x)"` |

## 分组管理

```python
bps = BreakpointManager()

# 创建分组
bps.add_bp("main_entry",  0x140001000, group="code")
bps.add_bp("strlen_check", 0x140001200, group="code", hit_cond=">5")
bps.add_bp("mallloc_log", 0x140001300, group="heap", log_msg="malloc")
bps.add_bp("data_watch",  0x140001400, group="data", oneshot=True)

# 批量操作
bps.disable_group("code")   # 关闭整个 code 组
bps.enable_all()            # 恢复全部
bps.save("bps.json")        # 断点持久化
bps.load("bps.json")        # 断点恢复
```

## 集成到调试器

```
在 re_12 DebugSession 中插入:

class DebugSession:
    def __init__(self):
        ...
        self.bp_mgr = BreakpointManager()

    def set_conditional_bp(self, bp_id, addr, **kwargs):
        """设置条件断点"""
        bp = Breakpoint(bp_id, addr, **kwargs)
        self.bp_mgr.add_bp(bp_id, addr, **kwargs)
        # 实际调用 set_swbp 或 set_hwbp

    def _handle_breakpoint(self, thread_id, context):
        for bp in self.bp_mgr.get_triggered_bps(context):
            if bp.check_break(context):
                if bp.log_msg:
                    log(bp.log_msg.format(context=context))
                if bp.is_oneshot:
                    self.remove_bp(bp.id)
                if bp.should_break:
                    return PAUSE
        return CONTINUE
```

## 验证

| 测试 | 结果 |
|------|------|
| 基础断点 (无条件) | 每次命中都中断 ✅ |
| hit>5 条件 | 前 4 次跳过，第 5 次起中断 ✅ |
| oneshot | 命中一次后自动禁用 ✅ |
| log 模式 | 不中断，仅输出日志 ✅ |
| 分组禁用/启用 | 批量开关 ✅ |
| JSON 持久化 | 保存/读取一致 ✅ |
| 表达式条件 | 按寄存器值过滤 ✅ |
