# Vite / Rollup — 新一代构建工具

## 一、Vite 开发模式 — ESM 原生

### 核心原理
```
传统: npm run dev → 整个项目打包（Webpack Dev Server）
Vite: npm run dev → 启动 Server + esbuild 预构建 + 浏览器按需请求
```

**三步走**:
1. **esbuild 预构建**: 将 CJS 依赖转换为 ESM，合并分散的依赖（减少请求数）
2. **按需编译**: 浏览器请求 `src/App.vue` 时，Vite 即时编译并返回
3. **304 缓存**: 依赖请求返回 304 Not Modified（利用 HTTP 缓存）

**对比传统打包器**:
| 操作 | Webpack | Vite |
|------|---------|------|
| 启动 | 构建全部模块 ❌ | 零启动 ✅ |
| HMR | 重建模块链 | 仅重新编译单个文件 |
| 冷启动 | 秒级 | 毫秒级 |
| 大项目 | 10-30s | <1s |

### esbuild 预构建细节
- **功能**: 将 CJS → ESM，合并多文件依赖（如 lodash 按需 → 单文件）
- **配置文件**: `node_modules/.vite/deps/`
- **触发条件**: 依赖变更或 `vite.config` 变化时重新预构建

## 二、Rollup 构建模式 — 生产环境

Vite 构建时调用 Rollup 打包，原因:
- esbuild 的 tree-shaking 不够彻底
- Rollup 输出更干净、更小

**Rollup 优势**:
- **ESM 输出**: 原生支持 ES module 输出格式
- **Tree Shaking 更彻底**: 基于函数级别的死代码删除（比 webpack 的模块级别更精细）
- **Scope Hoisting**: 将模块合并为单个作用域（减少运行时开销）
- **更小的输出**: 不使用 webpack module runtime

## 三、Vite 插件体系

### Rollup 兼容钩子
| 钩子 | 触发时机 | 用途 |
|------|---------|------|
| resolveId | 模块解析 | 别名、Virtual Module |
| load | 模块加载 | Virtual Module 返回内容 |
| transform | 模块转换 | JSX/TS/Vue 编译 |
| moduleParsed | 解析完成 | 分析模块依赖 |

### Vite 独有钩子
| 钩子 | 触发时机 | 用途 |
|------|---------|------|
| config | Vite 配置解析前 | 修改配置 |
| configResolved | 配置解析后 | 读取最终配置 |
| configureServer | Dev Server 启动 | 添加中间件 |
| handleHotUpdate | HMR 触发 | 自定义 HMR 逻辑 |

**中间件示例**:
```js
configureServer(server) {
  server.middlewares.use('/api', proxyMiddleware)
}
```

## 四、与同类工具对比

| 特性 | Vite | Snowpack | Turbopack | Rspack |
|------|------|----------|-----------|--------|
| 开发模式 | ESM + esbuild | ESM | Rust 编译 | Rust 编译 |
| 构建 | Rollup | 无（推其他工具） | Turbopack(custom) | Rspack(custom) |
| 生态 | 成熟 | 基本停止维护 | 实验中 | 可用 |
| 语言 | Node/Go | JS | Rust | Rust |
| 插件兼容 | Rollup 兼容 | 自定义 | webpack 部分 | webpack 兼容 |

**Snowpack** 已停止维护 → 建议使用 Vite。

**Turbopack** 是 Vercel 推出的 Rust 打包器，开发模式极快但生产构建仍不够成熟。

**Rspack** 字节跳动出品，兼容 webpack 配置和插件，迁移成本低。

**总结**: Vite 是目前最成熟的新一代构建工具选择。
