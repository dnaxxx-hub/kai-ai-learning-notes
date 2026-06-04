# 前端/全栈 #9：前端性能优化与监控

> 前端性能是用户体验的基石。0.1s的延迟就能让转化率下降7%。从了解是什么在"慢"，到系统地优化构建、渲染、缓存，再到搭建监控体系感知真实用户——是本课的完整闭环。

> 前置：HTML/CSS(#1~2)、JS(#3)、TS(#4)、React核心(#5~6)、工程化(#7)、React状态与性能(#8)

---

## 一、核心性能指标 & Web Vitals

### 1.1 关键指标速览

| 指标 | 全称 | 衡量什么 | 好 | 差 | 优化方向 |
|------|------|---------|----|----|---------|
| **LCP** | Largest Contentful Paint | 最大内容渲染时间 | <2.5s | >4.0s | 关键渲染路径(preload/prefetch/preconnect) |
| **FID** | First Input Delay | 首次交互延迟 | <100ms | >300ms | 长任务拆分(Time Slicing) |
| **CLS** | Cumulative Layout Shift | 累积布局偏移 | <0.1 | >0.25 | 设置固定尺寸/字体回退 |
| **INP** | Interaction to Next Paint | 交互到下一帧(2024.3取代FID) | <200ms | >500ms | 优化事件处理/Main Thread |
| **TTFB** | Time to First Byte | 首字节时间 | <800ms | >1.8s | 服务端/CDN/缓存 |
| **FCP** | First Contentful Paint | 首次内容绘制 | <1.8s | >3.0s | 减少阻塞资源 |
| **SI** | Speed Index | 页面内容可见填充速度 | <3.4s | >5.8s | 渐进式渲染 |

### 1.2 LCP 优化：关键渲染路径

```html
<!-- preload: 提前加载关键资源（浏览器高优先级） -->
<link rel="preload" href="/fonts/Inter-Bold.woff2" as="font" crossorigin>
<link rel="preload" href="/styles/critical.css" as="style">

<!-- prefetch: 提前获取下一页资源（浏览器低优先级，空闲时下载） -->
<link rel="prefetch" href="/dashboard" as="document">

<!-- preconnect: 提前建立连接（DNS+TCP+TLS握手） -->
<link rel="preconnect" href="https://api.example.com">
<link rel="preconnect" href="https://fonts.googleapis.com">
<!-- dns-prefetch: 只做DNS解析（更轻量，兼容更老浏览器） -->
<link rel="dns-prefetch" href="https://cdn.example.com">
```

**LCP 候选元素**：`<img>`、`<image>`（SVG）、`<video>` poster、带 CSS background-image 的元素、块级文本元素（`<p>`、`<h1>` 等）。

**优化策略**：
1. 消除渲染阻塞资源（内联关键CSS，async/defer JS）
2. 压缩图片并使用响应式 srcset
3. 优化服务器响应速度（SSR → Streaming SSR）
4. preload LCP 资源
5. 使用 CDN 减少 RTT

### 1.3 CLS 优化：防抖原则

```css
/* ✅ 1. 图片/视频设置固定宽高比 */
img, video {
  aspect-ratio: 16 / 9; /* 或使用 CSS 的 aspect-ratio 替代 padding hack */
  width: 100%;
  height: auto;
}

/* ✅ 2. 字体回退 + size-adjust 防布局偏移 */
@font-face {
  font-family: 'MyFont';
  src: url('/fonts/MyFont.woff2') format('woff2');
  font-display: swap; /* 先用回退字体显示，字体加载后再替换 */
  size-adjust: 90%;   /* 调整回退字体尺寸匹配最终字体的 OFFSET */
}

/* ✅ 3. 广告/动态内容预留位置 */
.ad-slot {
  min-height: 250px;
  min-width: 300px;
}
```

### 1.4 长任务拆分（针对 FID / INP）

```js
// ❌ 阻塞主线程
function processBigData(items) {
  items.forEach(item => heavyComputation(item)); // 可能卡住 500ms+
}

// ✅ Time Slicing: 拆分到多个帧
function processBigDataSliced(items, chunkSize = 50) {
  let index = 0;
  function nextChunk() {
    const end = Math.min(index + chunkSize, items.length);
    for (; index < end; index++) {
      heavyComputation(items[index]);
    }
    if (index < items.length) {
      requestAnimationFrame(nextChunk); // 每帧只处理一小块
    }
  }
  nextChunk();
}

// ✅ 或使用 scheduler.yield()（Chrome 115+）
async function processBigDataYield(items) {
  for (const item of items) {
    heavyComputation(item);
    await scheduler.yield(); // 让出主线程
  }
}
```

---

## 二、构建优化

### 2.1 代码分割

```tsx
// ✅ 路由级代码分割（推荐的方式）
import { lazy, Suspense } from 'react';
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Analytics = lazy(() => import('./pages/Analytics'));

function App() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/analytics" element={<Analytics />} />
      </Routes>
    </Suspense>
  );
}

// ✅ 组件级代码分割（针对重型组件）
const HeavyChart = lazy(() => import(/* webpackChunkName: "chart" */ './HeavyChart'));
const MarkdownEditor = lazy(() => import(/* webpackPrefetch: true */ './MarkdownEditor'));

// ✅ 动态 import（非 React 场景）
btn.addEventListener('click', async () => {
  const { format } = await import('date-fns');
  console.log(format(new Date(), 'yyyy-MM-dd'));
});
```

### 2.2 Tree Shaking 陷阱

```json
// package.json - ✅ sideEffects 声明（告诉打包器哪些文件有副作用）
{
  "sideEffects": [
    "*.css",
    "*.global.js"
  ]
  // 或 "sideEffects": false 表示所有文件无副作用（导入未用的都会被 shake 掉）
}
```

```ts
// ❌ barrel export × 导致整个模块树的导出都保留
// components/index.ts
export { Button } from './Button';
export { Card } from './Card';    // 即使只用了 Button，Card 也可能被保留
export { Modal } from './Modal';

// ✅ 直接导入具体路径
import { Button } from '@/components/Button';
```

**bundle 体积控制清单**：

```
moment       → dayjs         (-95%, ~300KB → ~6KB)
lodash       → lodash-es     (按需导入，需 tree-shakable)
chart.js     → uplot         (-80%，更快的渲染)
antd icons   → 按需导入       (否则引入全部 → 600KB SVG!)
```

### 2.3 图片优化

```html
<!-- ✅ 响应式图片 + WebP/AVIF -->
<picture>
  <source srcset="hero.avif" type="image/avif">
  <source srcset="hero.webp" type="image/webp">
  <img
    srcset="
      hero-400w.jpg 400w,
      hero-800w.jpg 800w,
      hero-1200w.jpg 1200w
    "
    sizes="(max-width: 600px) 400px, (max-width: 1024px) 800px, 1200px"
    src="hero-800w.jpg"
    alt="Hero image"
    loading="lazy"        <!-- ✅ 原生懒加载 -->
    decoding="async"      <!-- ✅ 异步解码（不阻塞渲染） -->
    width="1200"
    height="600"
  >
</picture>
```

**TailwindCSS JIT 自动 purge 无用样式**（默认开启）：
```js
// tailwind.config.js - ✅ JIT 模式下 purge 自动生效
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  // content 里匹配到的 class 会保留，没用到的 tailwind class 自动删除
};
```

**关键 CSS 内联**（大幅减少首次渲染阻塞）：
```html
<!-- 将首屏关键样式直接内联到 <head> -->
<style>
  /* Critical CSS — 首屏可视区域的样式 */
  header { height: 64px; background: #fff; }
  .hero { min-height: 80vh; display: flex; align-items: center; }
  /* ... 仅包含首屏样式，通常 < 14KB 为佳 */
</style>
<!-- 非关键 CSS 延后加载 -->
<link rel="preload" href="/styles/full.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap">
```

---

## 三、渲染优化

### 3.1 React 18 并发特性

```tsx
import { useTransition, useDeferredValue, Suspense } from 'react';

// ✅ useTransition: 标记低优先级更新，不阻塞 UI
function SearchPage() {
  const [query, setQuery] = useState('');
  const [isPending, startTransition] = useTransition();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // 高优先级：立即更新输入框
    setQuery(e.target.value);
    // 低优先级：搜索结果可以在后台准备
    startTransition(() => {
      setSearchQuery(e.target.value);
    });
  };

  return (
    <div>
      <input value={query} onChange={handleChange} />
      {isPending && <Spinner />} {/* 过渡期间显示 spinner */}
      <Suspense fallback={<SearchSkeleton />}>
        <SearchResults query={searchQuery} />
      </Suspense>
    </div>
  );
}

// ✅ useDeferredValue: 让某个「值」的更新延迟
function ProductList({ products }: { products: Product[] }) {
  const deferredProducts = useDeferredValue(products);
  const isStale = deferredProducts !== products;

  return (
    <div style={{ opacity: isStale ? 0.7 : 1 }}>
      {/* deferredProducts 的渲染不会阻塞用户操作 */}
      {deferredProducts.map(product => <ProductCard key={product.id} product={product} />)}
    </div>
  );
}
```

### 3.2 虚拟列表处理万条数据

```tsx
// ✅ 方案一: react-window（轻量，~3KB）
import { FixedSizeList as List } from 'react-window';

function VirtualList({ items }: { items: Item[] }) {
  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => (
    <div style={style}>
      <ItemCard item={items[index]} />
    </div>
  );

  return (
    <List
      height={600}          // 可视区域高度
      itemCount={items.length}
      itemSize={80}         // 每行高度
      width="100%"
    >
      {Row}
    </List>
  );
}

// ✅ 方案二: react-virtuoso（功能更丰富，支持动态高度/分组/自动滚动）
import { Virtuoso } from 'react-virtuoso';

function ChatVirtuoso({ messages }: { messages: Message[] }) {
  return (
    <Virtuoso
      style={{ height: '100vh' }}
      totalCount={messages.length}
      itemContent={(index) => <ChatBubble message={messages[index]} />}
      followOutput="smooth"  // 新消息自动滚动
      atBottomStateChange={(atBottom) => {
        if (atBottom) markAsRead();
      }}
    />
  );
}
```

### 3.3 防抖与节流

```ts
// 防抖: 连续触发只执行最后一次（适用于搜索输入/自动保存）
function debounce<T extends (...args: any[]) => any>(fn: T, ms: number) {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// 节流: 固定时间间隔执行一次（适用于滚动/resize）
function throttle<T extends (...args: any[]) => any>(fn: T, ms: number) {
  let lastTime = 0;
  return (...args: Parameters<T>) => {
    const now = Date.now();
    if (now - lastTime >= ms) {
      lastTime = now;
      fn(...args);
    }
  };
}

// 使用
const handleSearch = debounce((value: string) => {
  searchAPI(value);
}, 300);

const handleScroll = throttle(() => {
  trackScrollPosition();
}, 200);
```

### 3.4 Web Worker（CPU 密集型任务）

```ts
// ✅ worker.ts — 分离到独立线程
// worker.ts
self.onmessage = (e: MessageEvent<{ data: number[] }>) => {
  const { data } = e.data;
  // 处理大型数据（不会阻塞主线程）
  const result = data.map(expensiveTransform);
  self.postMessage({ result });
};

// ✅ 主线程
const worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });

worker.postMessage({ data: largeArray });
worker.onmessage = (e) => {
  setProcessedData(e.data.result);
  worker.terminate(); // 完成后及时终止
};
```

---

## 四、监控体系

### 4.1 RUM (Real User Monitoring) — Web Vitals 采集

```ts
// ✅ 完整可用的 Web Vitals 采集 + 上报
import { getLCP, getFID, getCLS, getINP, getTTFB, getFCP } from 'web-vitals'; // ⚠️ 需 npm install web-vitals

type VitalMetric = {
  name: string;     // 'LCP' | 'FID' | 'CLS' | 'INP' | 'TTFB' | 'FCP'
  value: number;    // ms（CLS 为无单位分值）
  rating: 'good' | 'needs-improvement' | 'poor';
};

function getRating(name: string, value: number): VitalMetric['rating'] {
  const thresholds: Record<string, [number, number]> = {
    LCP:  [2500, 4000],
    FID:  [100,  300],
    CLS:  [0.1,  0.25],
    INP:  [200,  500],
    TTFB: [800,  1800],
    FCP:  [1800, 3000],
  };
  const [good, poor] = thresholds[name] || [Infinity, Infinity];
  if (value <= good) return 'good';
  if (value <= poor) return 'needs-improvement';
  return 'poor';
}

// ✅ 采集所有核心指标
export function initWebVitalsReport() {
  const vitals: VitalMetric[] = [];

  const report = (metric: VitalMetric) => {
    vitals.push(metric);
    console.log(`[Web Vitals] ${metric.name}: ${metric.value}ms (${metric.rating})`);

    // 批量上报：sendBeacon（即使页面关闭也能发送）
    if (vitals.length >= 3 || document.visibilityState === 'hidden') {
      const body = JSON.stringify({ vitals: [...vitals], url: location.href, ua: navigator.userAgent });
      navigator.sendBeacon('/api/vitals', body);
      vitals.length = 0; // 清空已上报
    }
  };

  // 各指标采集
  getTTFB((m) => report({ name: 'TTFB', value: m.value, rating: getRating('TTFB', m.value) }));
  getFCP((m)  => report({ name: 'FCP',  value: m.value, rating: getRating('FCP', m.value) }));
  getLCP((m)  => report({ name: 'LCP',  value: m.value, rating: getRating('LCP', m.value) }));
  getFID((m)  => report({ name: 'FID',  value: m.value, rating: getRating('FID', m.value) }));
  getCLS((m)  => report({ name: 'CLS',  value: m.value, rating: getRating('CLS', m.value) }));
  getINP((m)  => report({ name: 'INP',  value: m.value, rating: getRating('INP', m.value) }));

  // 页面关闭时确保数据发送
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && vitals.length > 0) {
      navigator.sendBeacon('/api/vitals', JSON.stringify({ vitals, url: location.href }));
    }
  });
}
```

### 4.2 自定义 Performance Observer（无需依赖）

```ts
// ✅ 纯原生 API 采集 LCP + CLS
export function observeWebVitals() {
  // 1. LCP
  const lcpObserver = new PerformanceObserver((list) => {
    const entries = list.getEntries();
    const lastEntry = entries[entries.length - 1]; // LCP 可能有多个候选
    console.log('LCP:', lastEntry.startTime, 'element:', lastEntry.element);
  });
  lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });

  // 2. CLS
  // CLS 需要通过 FCP 后开始监听，排除页面切换后的高度变化
  let clsValue = 0;
  const clsObserver = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) { // 排除用户输入导致的布局偏移
        clsValue += (entry as any).value;
      }
    }
    console.log('CLS:', clsValue);
  });
  clsObserver.observe({ type: 'layout-shift', buffered: true });

  // 3. 首次输入延迟（通过 PerformanceEventTiming）
  const fidObserver = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      const delay = entry.processingStart - entry.startTime;
      console.log('FID:', delay, 'event:', entry.name);
    }
  });
  fidObserver.observe({ type: 'first-input', buffered: true });

  // 4. 长任务监控（>50ms 的任务）
  const longTaskObserver = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      console.warn('Long Task:', entry.duration, 'ms, start:', entry.startTime);
      // 上报长的交互延迟
      if (entry.duration > 100) {
        navigator.sendBeacon('/api/longtask', JSON.stringify({
          duration: entry.duration,
          startTime: entry.startTime,
          url: location.href,
        }));
      }
    }
  });
  longTaskObserver.observe({ type: 'longtask', buffered: true });
}
```

### 4.3 Error Boundary + 错误上报

```tsx
import { Component, ErrorInfo, ReactNode } from 'react';

// ✅ Error Boundary 组件
interface Props { children: ReactNode; fallback?: ReactNode; }
interface State { hasError: boolean; error?: Error; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // ✅ 上报错误到监控服务（支持 SourceMap 还原）
    reportError({
      error: {
        name: error.name,
        message: error.message,
        stack: error.stack, // 生产环境用 SourceMap 还原
      },
      componentStack: errorInfo.componentStack,
      url: location.href,
      timestamp: Date.now(),
      userId: getUserId(), // 可选，关联用户
    });
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div role="alert">
          <h2>出错了</h2>
          <p>请刷新页面重试</p>
          <button onClick={() => this.setState({ hasError: false })}>
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ✅ 上报函数（sendBeacon 稳定性好 + 兼容 fetch）
function reportError(payload: Record<string, unknown>) {
  try {
    const body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/errors', body);
    } else {
      fetch('/api/errors', { method: 'POST', body, keepalive: true });
    }
  } catch {
    // 即使上报失败也不能影响用户体验
  }
}
```

### 4.4 SourceMap 还原堆栈（生产环境）

生产环境不要暴露 SourceMap 文件到公网，使用**内部服务**还原：

```ts
// 服务端（Node.js）：使用 source-map 包还原
import { SourceMapConsumer } from 'source-map';

async function resolveErrorStack(stack: string, sourceMapsDir: string) {
  // 解析 stack trace，提取文件名和行号
  const lines = stack.split('\n');
  const resolved = [];

  for (const line of lines) {
    const match = line.match(/at\s+(.*?)\s+\(?(.*?):(\d+):(\d+)\)?/);
    if (!match) { resolved.push(line); continue; }

    const [, func, file, lineNum, colNum] = match;
    // 查找对应的 SourceMap 文件
    const mapFile = file.replace(/\.js$/, '.js.map');
    const mapPath = path.join(sourceMapsDir, path.basename(mapFile));

    try {
      const rawMap = JSON.parse(await fs.readFile(mapPath, 'utf-8'));
      const consumer = await new SourceMapConsumer(rawMap);
      const original = consumer.originalPositionFor({
        line: parseInt(lineNum),
        column: parseInt(colNum),
      });
      resolved.push(`  at ${func} (${original.source}:${original.line}:${original.column})`);
      consumer.destroy();
    } catch {
      resolved.push(line); // 无法还原则保留原行
    }
  }
  return resolved.join('\n');
}
```

### 4.5 监控方案对比

| 方案 | 优势 | 劣势 | 适合场景 |
|------|-----|------|---------|
| **自建 RUM + Beacon** | 免费，完全可控 | 无告警/可视化/回放 | 初创项目、内部系统 |
| **Sentry** | JS Error自动捕获+SourceMap+Session Replay | 免费版有额度限制 | 绝大多数项目（推荐） |
| **Datadog RUM** | 全链路追踪（APM+RUM） | 昂贵（人均计价） | 大型企业 |
| **New Relic** | APM强 + 浏览器监控 | 学习成本高，价格不透明 | 已有 NewRelic 生态 |
| **Vercel Analytics** | 零配置（Vercel用户） | 仅限 Vercel 平台 | Vercel 部署项目 |

---

## 五、缓存策略

### 5.1 Service Worker + Cache API

```ts
// ✅ sw.ts — 完整可用的 Service Worker 缓存策略
/// <reference lib="webworker" />
const CACHE_VERSION = 'v1';
const STATIC_CACHE = `static-${CACHE_VERSION}`;

const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/styles/main.css',
  '/scripts/main.js',
  '/favicon.ico',
];

// 安装：预缓存静态资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(PRECACHE_URLS);
    })
  );
  self.skipWaiting(); // 立即激活新版本
});

// 激活：清理旧缓存
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim(); // 新 SW 立即控制所有页面
});

// ✅ 三种缓存策略
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. 不缓存 API（或使用 Network First）
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // 2. 图片资源 -> Cache First（节省带宽，极速）
  if (request.destination === 'image') {
    event.respondWith(cacheFirst(request));
    return;
  }

  // 3. 页面导航 -> Network First（保证内容最新）
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  // 4. 其他静态资源 -> Cache First
  event.respondWith(cacheFirst(request));
});

// ✅ Strategy: Cache First
async function cacheFirst(request: Request): Promise<Response> {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline', { status: 503 });
  }
}

// ✅ Strategy: Network First（有超时回退到缓存）
async function networkFirst(request: Request, timeoutMs = 3000): Promise<Response> {
  const timeout = new Promise<never>((_, reject) =>
    setTimeout(() => reject(new Error('timeout')), timeoutMs)
  );

  try {
    const response = await Promise.race([fetch(request), timeout]);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    // 离线时返回离线页面
    return caches.match('/offline.html') || new Response('Offline', { status: 503 });
  }
}
```

**注册 SW**：

```ts
// main.ts
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('/sw.js');
      console.log('SW registered:', reg.scope);

      // 检测更新
      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing;
        if (newWorker) {
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // 新版本可用，提示用户刷新
              showUpdateToast();
            }
          });
        }
      });
    } catch (err) {
      console.error('SW registration failed:', err);
    }
  });
}
```

### 5.2 HTTP 缓存

```
# Nginx 配置示例 — 静态资源强缓存 + 版本化
location /static/ {
    expires 1y;                        # Cache-Control: max-age=31536000
    add_header Cache-Control "public, immutable";
    add_header ETag "static-${file_name}-${mtime}";
}

# HTML 页面 — 协商缓存（不设 max-age）
location / {
    etag on;
    if_modified_since exact;
    add_header Cache-Control "no-cache"; # 每次请求发送 ETag/If-None-Match 验证
}

# API 响应 — 短时间缓存 + stale-while-revalidate
location /api/ {
    add_header Cache-Control "public, max-age=60, stale-while-revalidate=300";
    # max-age=60s 内直接用缓存
    # 60-300s 范围内，可以返回陈旧数据同时后台刷新
}
```

### 5.3 CDN 缓存

```
# CDN-Cache-Control 独立控制 CDN 和浏览器缓存（Akamai/Cloudflare 支持）
# 浏览器缓存 10min，CDN 缓存 1h

Cache-Control: max-age=600               # 浏览器 10min
CDN-Cache-Control: max-age=3600          # CDN 1h（优先于 Cache-Control）

# stale-while-revalidate: 允许 CDN 在缓存过期后继续服务陈旧内容 + 后台刷新
Cache-Control: max-age=300, stale-while-revalidate=600
# 如果 CDN 缓存过期，在 600s 内可以返回旧缓存同时异步去源站拉新内容
```

---

## 六、性能预算 (Performance Budget)

### 6.1 预算设置标准

```json
{
  "budgets": [
    {
      "resourceType": "total",
      "budget": 500000,         // 总资源 ≤ 500KB（未压缩）
      "aggregation": "total"
    },
    {
      "resourceType": "script",
      "budget": 300000,         // JS ≤ 300KB（gzip 后 ~100KB）
      "aggregation": "total"
    },
    {
      "resourceType": "stylesheet",
      "budget": 50000           // CSS ≤ 50KB
    },
    {
      "resourceType": "image",
      "budget": 500000,         // 图片 ≤ 500KB
      "aggregation": "total"
    },
    {
      "timing": {
        "metric": "interactive",
        "budget": 5000           // TTI ≤ 5s
      }
    },
    {
      "timing": {
        "metric": "largest-contentful-paint",
        "budget": 2500           // LCP ≤ 2.5s
      }
    }
  ]
}
```

### 6.2 工具集成

```json
// package.json — Lighthouse CI 性能预算检查
{
  "scripts": {
    "perf:audit": "lighthouse-ci https://example.com --budget-file=lighthouse-budget.json",
    "perf:analyze": "npx webpack-bundle-analyzer dist/stats.json",
    "perf:size": "npx bundlesize"
  },
  "bundlesize": [
    { "path": "./dist/js/main-*.js", "maxSize": "100 kB" },
    { "path": "./dist/js/chunk-vendor.js", "maxSize": "150 kB" },
    { "path": "./dist/css/main-*.css", "maxSize": "30 kB" },
    { "path": "./dist/**/*.png", "maxSize": "200 kB" }
  ]
}
```

### 6.3 CI 集成：PR 自动检查

```yml
# .github/workflows/perf-budget.yml
name: Performance Budget
on: [pull_request]

jobs:
  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: npm ci && npm run build
      - name: Lighthouse CI
        uses: treosh/lighthouse-ci-action@v11
        with:
          urls: |
            https://deploy-preview-${{ github.event.number }}.example.com
          budgetPath: ./lighthouse-budget.json
          uploadArtifacts: true
          temporaryPublicStorage: true
```

---

## 七、性能优化 Checklist

### 加载阶段

- [ ] **LCP < 2.5s**：preload LCP 资源（图片/字体），内联关键CSS，优化 TTFB
- [ ] **FCP < 1.8s**：消除渲染阻塞 CSS/JS，使用 `<link rel="preload">`
- [ ] **TTFB < 800ms**：CDN、边缘计算、服务端优化（缓存/直连DB→Redis）
- [ ] 图片使用 WebP/AVIF + 响应式 `srcset` + `loading="lazy"`
- [ ] 字体使用 `font-display: swap` + `size-adjust` 防布局偏移
- [ ] 第三方脚本使用 `async` 或 `defer` 加载
- [ ] 关键 CSS 内联 <14KB，非关键 CSS 延后加载

### 构建阶段

- [ ] 代码分割：路由级 `lazy()` + `Suspense`，重型组件动态 import
- [ ] Tree Shaking：`sideEffects: false`，避免 barrel export
- [ ] dayjs 替代 moment，lodash-es 替代 lodash
- [ ] bundle-analyzer 定期检查包体积
- [ ] 移除未使用的 polyfills / 无用的 npm 依赖

### 运行时

- [ ] **FID < 100ms / INP < 200ms**：长任务拆分（`requestAnimationFrame` / `scheduler.yield`）
- [ ] 虚拟列表处理 1000+ 数据（react-window / react-virtuoso）
- [ ] 防抖（input/scroll/resize）
- [ ] Web Worker 处理 CPU 密集型任务
- [ ] `useTransition` / `useDeferredValue` 标记非紧急更新
- [ ] React.memo + useMemo 仅对高频渲染组件使用（避免滥用）

### 缓存策略

- [ ] Service Worker 注册 + `Cache First` / `Network First` 策略
- [ ] 静态资源强缓存 + 版本化 hash
- [ ] HTML 协商缓存（ETag）
- [ ] API 响应使用 `stale-while-revalidate`
- [ ] CDN 配置 `CDN-Cache-Control` 独立控制

### 监控

- [ ] RUM 采集 Web Vitals（LCP/FID/CLS/INP/TTFB）
- [ ] sendBeacon 上报（页面关闭也可靠）
- [ ] Error Boundary + 错误上报
- [ ] SourceMap 上传到内部服务（不暴露到公网）
- [ ] 设置性能预算 + CI 自动检查
- [ ] 接入 Sentry 或自建监控仪表盘

### 持续改进

- [ ] 定期跑 Lighthouse 性能审计，记录分数变化
- [ ] 监控 Web Vitals P75 值（中位数掩盖了尾部延迟）
- [ ] A/B 测试性能优化效果（优化前后的转化率对比）
- [ ] 每个版本对比 bundle 大小，防止回归

---

> **一句话总结**：性能优化不是一次性工作，而是与开发流程深度绑定的持续实践。从测量开始，找到瓶颈，针对性优化，建立预算防线防止回退。
