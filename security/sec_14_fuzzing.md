# Fuzzing 技术

## AFL 原理

AFL (American Fuzzy Lop) 是基于代码覆盖率指导的灰盒模糊测试工具。

### 核心机制

1. **遗传变异引擎**: 对种子文件进行位翻转、字节加减、拼接等变异操作
2. **覆盖率反馈**: 通过编译期插桩追踪 `edge coverage`（基本块转移）
3. **确定性 + 随机阶段**: 先做确定性的小变异，再做随机拼接
  
### Bitmap 覆盖率

- AFL 维护 64KB bitmap (`MAP_SIZE = 2^16`)
- 每个 edge 映射到一个 bitmap 位: `cur_location ^ (prev_location >> 1)`
- 新路径 → 保留该输入 → 加入队列 → 继续变异

```bash
# 编译插桩
afl-gcc -o prog prog.c   # LLVM模式: afl-clang-fast

# 运行 fuzz
afl-fuzz -i seeds/ -o findings/ -- ./prog @@
```

### 执行流程

```
种子队列 → 变异 → 执行目标 → 新覆盖率? → 是→加入队列
                        ↓ 否
                    继续变异下一轮
```

## LibFuzzer

LibFuzzer 是 in-process 的覆盖引导 fuzzer，链接目标函数直接调用。

```c
// 目标函数签名
int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    process_data(Data, Size);
    return 0;
}
```

### 种子语料库（Seed Corpus）

```bash
# 编译 + fuzz
clang -fsanitize=fuzzer,address -o fuzz_target target.c

# 初始种子目录
mkdir corpus/
echo "initial" > corpus/seed1

# 运行
./fuzz_target corpus/ -max_len=4096 -runs=100000
```

### 特色

- **进程内**: 无 fork 开销，吞吐量高
- **持久模式**: 循环复用同一进程
- **与 AddressSanitizer 深度集成**
- **字典支持**: `-dict=protocol.dict`

## 覆盖率反馈

### Edge Coverage

传统 block coverage 只能知道某条代码是否被执行过，edge coverage 记录 block 的转移对（from→to），极大增加了路径区分粒度。

```
基本块:  A → B → C
Edge:    (A,B) 和 (B,C) 分别跟踪
```

### SanitizerCoverage

编译器内置的插桩，为 LibFuzzer/AFL 提供覆盖率回调：

```bash
-fsanitize-coverage=trace-pc-guard,trace-cmp  # PC Guard + cmp 追踪
```

## 人工种子（Corpus Minimization）

种子文件质量直接影响 fuzz 效果。

### 种子编写策略

| 策略 | 描述 | 示例 |
|------|------|------|
| **空输入** | 最基础的种子 | 空文件 |
| **魔数** | 触发文件头检查 | `\x89PNG`、`\xff\xd8` |
| **边界值** | 触发整数溢出 | `0`, `-1`, `INT_MAX` |
| **协议模板** | 符合协议结构 | HTTP header、TLS ClientHello |

### Minimize（最小化）

```bash
# AFL 自动最小化
afl-tmin -i large_input -o minimized_input -- ./prog @@

# LibFuzzer
./fuzz_target -merge=1 corpus/ new_corpus/  # 合并新种子到 corpus
./fuzz_target corpus/ -minimize_crash=1     # 最小化 crash
```

## 碰撞检测（Unique Crashes）

同一漏洞的不同输入视为重复 crash，需要去重。

### 去重方法

| 方法 | 描述 |
|------|------|
| **Backtrace 匹配** | 比较 stack trace 是否相同 |
| **ASan 报告** | AddressSanitizer 输出的 hash 或异常类型 |
| **代码位置** | crash 发生的函数/行号 |

### 利用 AddressSanitizer

```bash
# 编译带 ASan 的 fuzz 目标
clang -fsanitize=address,fuzzer -g -O1 -o target target.c
```

ASan 检测: OOB、UAF、double-free、stack-buffer-overflow、leak。

```bash
# 查找 crash 原因
./target crash_file  # ASan 自动输出：
# ERROR: AddressSanitizer: heap-buffer-overflow on address...
```

## OSS-Fuzz

Google 运营的持续 fuzzing 服务，维护超过 500+ 开源项目的 fuzzing。

### 流程

1. 开发者提交 Docker build 脚本（编译目标 + 种子）
2. OSS-Fuzz 自动构建 → 24/7 持续 fuzz
3. 发现 crash → 自动向项目 issue tracker 报告
4. 开发者修复 → 验证 → close

### 参与 OSS-Fuzz

```dockerfile
FROM gcr.io/oss-fuzz-base/base-builder
RUN git clone https://github.com/project/lib ...
WORKDIR $SRC/lib
COPY build.sh $SRC/
COPY seeds/ $SRC/seeds/
```

```bash
# build.sh
#!/bin/bash
$CC $CFLAGS -c fuzz_target.c -o fuzz_target.o
$CXX $CXXFLAGS fuzz_target.o -o $OUT/fuzz_target
cp seeds/*.bin $OUT/seeds/
```

### 覆盖率统计

```
https://storage.googleapis.com/<project>-coverage/latest/index.html
```

提供代码行/函数覆盖率热力图，帮助开发者发现未测试的代码路径。
