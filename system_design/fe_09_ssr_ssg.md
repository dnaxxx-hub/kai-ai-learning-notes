# SSR/SSG — 四代渲染模式深度解析

## 一、四代渲染模式对比

### CSR (Client-Side Rendering)
```
HTML骨架 → JS加载 → React渲染 → 可交互
```
- **流程**: 浏览器下载空 HTML + 巨大 JS bundle，客户端完全渲染
- **FP/FCP**: 快（HTML 空壳立即显示）
- **LCP**: 慢（需等 JS 加载+执行）
- **TTI**: ≈ LCP（渲染完即交互）
- **SEO**: 差（爬虫可能不执行 JS）

### SSR (Server-Side Rendering)
```
HTML(已渲染) → 显示 → Hydration → 可交互
```
- **流程**: 服务端 renderToString 生成完整 HTML
- **FP/FCP**: 极快（服务端返回完整 HTML）
- **LCP**: 快于 CSR
- **TTI**: 慢于 FCP（需 hydration 才能交互）
- **关键问题**: TTI 滞后于 FCP，用户看到内容但无法点击

### SSG (Static Site Generation)
```
构建时生成 HTML → CDN 缓存 → 直接显示
```
- **流程**: 构建时 fetch 数据生成静态 HTML
- **性能**: 所有指标最优
- **缺陷**: 内容过期需重新构建

### ISR (Incremental Static Regeneration)
```
首次: SSG → revalidate 后: 后台刷新 → 新版本
```
- **原理**: 结合 SSG + 运行时更新
- `revalidate: 60` → 60 秒内返回缓存，60 秒后请求触发后台重建
- `on-demand revalidation` → 手动触发 revalidate

## 二、Next.js API 原理

### getServerSideProps
- 每次请求时在服务端执行
- 返回 props 注入到页面组件
- 自动序列化为 JSON（不可包含 Date/Function）

### getStaticProps
- 构建时执行一次
- 返回 JSON 嵌入页面
- `revalidate` 开启 ISR

### Incremental Static Regeneration 机制
```
请求 → 缓存命中 → 返回旧页面
        ↓ (超时)
启动重建 → 生成新页面 → 更新缓存
        ↓
下次请求 → 新页面
```
- 旧页面不会阻塞，用户始终看到缓存版本
- 重建在后台异步完成

## 三、React Hydration 过程

```
服务端: renderToString(App) → HTML 字符串
               ↓
浏览器: 显示 HTML（纯静态，无事件）
               ↓
        hydrateRoot(container, App)
               ↓
        组件树重建（复用 DOM 节点）
               ↓
        事件绑定（attach event listeners）
               ↓
        差异检查（与服务端输出对比）
               ↓
        可交互（TTI reached）
```

**hydration 三大步骤**:
1. **组件树重建**: React 在内存中重建 VDOM，但**不创建真实 DOM**（复用已有 DOM）
2. **事件绑定**: 将所有事件处理器附加到对应 DOM 节点（事件委派到 root）
3. **差异检查**: 比对服务端 HTML 与客户端首次渲染结果，不匹配则告警并覆盖

**hydration mismatch 常见原因**:
- `Date.now()` / `Math.random()`
- 浏览器特有 API (`window.localStorage`)
- 时区/语言环境差异

## 四、性能数据对比（典型值）

| 指标 | CSR | SSR | SSG | ISR |
|------|-----|-----|-----|-----|
| FP | 50ms | **150ms** | **100ms** | **100ms** |
| FCP | 2.5s | **0.8s** | **0.3s** | 0.3s |
| LCP | 4.2s | 1.5s | **0.8s** | 0.8s |
| TTI | 4.5s | 3.2s | **1.0s** | 1.0s |
| TBT | 600ms | 400ms | **50ms** | 50ms |

**SSR 核心痛点**: FCP 到 TTI 差距大（"不可交互空白期"），用户点击无反应。
**解决方案**: Streaming SSR (React 18) + Selective Hydration。
