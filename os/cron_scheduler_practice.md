# Cron 调度器 — 纯 Python 实现

## 项目文件
- `cron_scheduler.py` — 核心（CronExpression解析/匹配 + CronScheduler运行）
- `test_cron_scheduler.py` — 19个测试

## 功能
1. **CronExpression** — 5字段cron表达式解析/匹配
   - 支持: 精确值、通配符`*`、列表`,`、范围`-`、步进`/`
   - `matches()` 检查给定时间是否匹配
   - `next_run()` 查找下一次匹配时间

2. **CronJob** — 作业状态跟踪 (run_count/error_count/last_run/enabled)

3. **CronScheduler** — 多作业调度器
   - 独立daemon线程轮询，每分钟触发匹配的作业
   - `add_job()` / `remove_job()` / `list_jobs()`
   - 每个作业在新线程中执行，不影响调度循环

## 测试 19/19 通过
