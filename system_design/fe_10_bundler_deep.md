# 打包器原理 — Webpack 深度解析

## 一、Webpack 核心概念

### Entry → Module → Chunk → Bundle

```
Entry('src/index.js') → 解析依赖 → Module Graph
     ↓
Modules（每个文件是一个 Module）
     ↓
Chunk（按 splitChunks / 动态 import 分组）
     ↓
Bundle（输出文件）
```

- **Entry**: 打包入口，支持多入口（multi-entry）→ 多 chunk
- **Module**: 每个文件被包装为 Module，包含 ID、依赖列表、转换后的代码
- **Chunk**: 逻辑代码块，一个 chunk 可包含多个 module
- **Bundle**: 物理输出文件

## 二、Loader 链（Pitch + Normal）

```
请求 'a.js!b.js!c.js' → resolve 为 .scss
        ↓
Loader chain: [sass-loader, css-loader, style-loader]
        ↓ pitch(←)          normal(→)
style-loader.pitch(css-loader.pitch(sass-loader.pitch()))
        ↓                         ↓
style-loader.normal ← css-loader.normal ← sass-loader.normal ← 源文件
```

**Pitch 阶段**（从左到右）:
- 可**熔断**：如果 pitch 返回了值，跳过后续 loader 的 pitch，**直接返回**执行 normal
- 典型应用: `style-loader` 利用 pitch 熔断

**Normal 阶段**（从右到左）:
- 每个 loader 接收上一个的输出
- 最终输出 JS 字符串（webpack 可理解的模块）

## 三、Plugin — tapable 事件系统

### Tapable Hooks
```
compiler.hooks: {
    run, emit, done, compilation, make, ...
}
compilation.hooks: {
    buildModule, seal, optimizeChunks, ...
}
```

**Hook 类型**:
| Hook | 执行方式 | 适用 |
|------|---------|------|
| SyncHook | 同步串行 | 简单监听 |
| AsyncSeriesHook | 异步串行 | emit, run |
| AsyncParallelHook | 异步并行 | make |
| SyncBailHook | 熔断 | 返回非 undefined 则停止 |

**Tap 注册**:
```js
compiler.hooks.emit.tapAsync('MyPlugin', (compilation, cb) => { ... })
compiler.hooks.done.tap('MyPlugin', stats => { ... })
```

## 四、Tree Shaking — 死代码消除

**条件**: ESM (import/export) 静态分析

**过程**:
```
1. 收集所有 export 定义（ModuleConcatenationPlugin）
2. 追踪每个 import 是否被使用
3. 标记未使用的 export（`/* unused */`）
4. TerserPlugin 删除死代码
```

**sideEffects: false**:
- package.json 中声明该包没有副作用
- 允许 webpack 完全删除未使用的导出
- 如果为 `true`，即使未使用的 import 也会保留（可能执行副作用代码）

**关键**: tree shaking 发生在 **模块层面** 而非语句层面。只有未使用的 export 能被删除，已 import 但未使用的**模块级别副作用**不会被删。

## 五、Code Splitting

- **动态 import()**: `import('./a').then(m => ...)` → 自动 split chunk
- **splitChunks**: 提取公共模块到独立 chunk
  - `minSize`: chunk 最小体积
  - `minChunks`: 被引用次数 ≥ n 时提取
  - `cacheGroups`: 分组规则（vendors / default）

## 六、HMR (Hot Module Replacement)

### 协议流程
```
WebSocket 连接 ←→ Webpack Dev Server
     ↓
模块变更通知（JSON diff: 变更的模块 ID）
     ↓
WebSocket 推送: {type: 'hash', data: hash}
     ↓
Client 请求 manifest（hot-update.json）
     ↓
Client 请求变更模块（hot-update.js）
     ↓
HMR Runtime 调用 module.hot.accept()
     ↓
执行新模块 → 替换旧模块 → 更新 UI
```

**WebSocket 消息类型**:
- `hash`: 新的编译 hash
- `ok`: 编译成功
- `invalid`: 文件变更，重新编译
- `errors`/`warnings`: 编译错误

**React HMR** (react-refresh):
- 保留组件状态（通过 React 树挂载点）
- 替换组件函数 → 触发重渲染
- 不触发完整页面刷新
