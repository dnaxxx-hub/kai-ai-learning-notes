# Web 全栈第5课：前端性能优化与 Web 安全实战

> 日期：2026-05-11 | 课程：前端路线 Phase 5
> 核心思维：让页面**更快加载** + **更流畅交互** + **更安全运行**

---

## 一、性能指标：用数据说话

### 1.1 Core Web Vitals（核心网页指标）

Google 定义的三项核心指标决定用户体验评分和 SEO 排名：

| 指标 | 全称 | 衡量内容 | 合格标准 | 良好/需改进/差 |
|------|------|---------|---------|---------------|
| **LCP** | Largest Contentful Paint | 最大内容渲染时间 | **< 2.5s** | <2.5s / 2.5-4.0s / >4.0s |
| **FID** | First Input Delay | 首次输入延迟（交互响应） | **< 100ms** | <100ms / 100-300ms / >300ms |
| **CLS** | Cumulative Layout Shift | 累计布局偏移 | **< 0.1** | <0.1 / 0.1-0.25 / >0.25 |

### 1.2 其他关键指标

| 指标 | 说明 | 推荐值 |
|------|------|--------|
| **FCP** | First Contentful Paint — 首次内容绘制 | < 1.8s |
| **TTFB** | Time to First Byte — 首字节时间 | < 800ms（服务器响应） |
| **SI** | Speed Index — 速度指数（内容视觉填充速度） | < 3.4s |
| **TBT** | Total Blocking Time — 总阻塞时间（长任务之和） | < 200ms |
| **INP** | Interaction to Next Paint — 交互到下次绘制（FID 替代者） | < 200ms |

### 1.3 如何测量

```javascript
// 1. Performance Observer API —— 生产环境
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.entryType === 'largest-contentful-paint') {
      console.log('LCP:', entry.renderTime || entry.loadTime);
    }
    if (entry.entryType === 'first-input') {
      console.log('FID:', entry.processingStart - entry.startTime);
    }
    if (entry.entryType === 'layout-shift') {
      console.log('CLS:', entry.value);
    }
  }
});

observer.observe({ type: 'largest-contentful-paint', buffered: true });
observer.observe({ type: 'first-input', buffered: true });
observer.observe({ type: 'layout-shift', buffered: true });

// 2. Performance API —— 导航时间
const perf = performance.getEntriesByType('navigation')[0];
console.log('TTFB:', perf.responseStart - perf.requestStart);
console.log('FCP:', performance.getEntriesByName('first-contentful-paint')[0]?.startTime);

// 3. 手动标记关键时间
performance.mark('start-calc');
// ... 计算逻辑 ...
performance.mark('end-calc');
performance.measure('calc-duration', 'start-calc', 'end-calc');
```

---

## 二、加载优化：让内容"快"到用户眼前

### 2.1 资源压缩

```nginx
# Nginx 启用 Gzip/Brotli 压缩
gzip on;
gzip_types text/css application/javascript application/json image/svg+xml;
gzip_comp_level 6;

# Brotli 压缩率更高（~20% 优于 gzip）
brotli on;
brotli_types text/css application/javascript;
brotli_comp_level 6;
```

**图片优化策略：**

| 格式 | 特点 | 场景 |
|------|------|------|
| WebP | Google 标准，有损/无损/透明，比 PNG 小 26% | 主力现代格式 |
| AVIF | MPEG 标准，比 WebP 再小 20%，支持 HDR | 最先进，浏览器支持度较低 |
| JPEG XL | 新一代 JPEG，无损/有损均优 | 未来主流 |

```html
<!-- Picture 元素：自适应图片格式 + 分辨率 -->
<picture>
  <source srcset="hero.avif" type="image/avif" />
  <source srcset="hero.webp" type="image/webp" />
  <img src="hero.jpg" alt="Hero" width="1200" height="600" loading="lazy" />
</picture>
```

### 2.2 代码分割（Code Splitting）

```javascript
// webpack/Vite 配置：按路由分割
// vite.config.js
export default {
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          utils: ['lodash-es', 'date-fns'],
        }
      }
    }
  }
};

// React.lazy + Suspense —— 组件级懒加载
import { lazy, Suspense } from 'react';
const HeavyChart = lazy(() => import('./components/HeavyChart'));

function Dashboard() {
  return (
    <Suspense fallback={<div>Loading chart...</div>}>
      <HeavyChart />
    </Suspense>
  );
}

// 动态 import() —— 按需加载（不是所有模块都需要时）
// 只有用户点击时才加载解析器
async function loadParser() {
  const { Parser } = await import('./heavy-parser');
  return new Parser();
}
```

### 2.3 预加载/预连接/预解析

```html
<!-- preload：当前页面肯定要用的资源，尽早加载 -->
<link rel="preload" href="/fonts/Inter-Regular.woff2" as="font" crossorigin />
<link rel="preload" href="/critical.css" as="style" />

<!-- preconnect：提前建立连接（DNS + TCP + TLS） -->
<link rel="preconnect" href="https://api.example.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />

<!-- dns-prefetch：只做 DNS 解析，轻量级 preconnect -->
<link rel="dns-prefetch" href="https://cdn.example.com" />

<!-- prefetch：可能用到的资源，浏览器空闲时下载 -->
<link rel="prefetch" href="/dashboard.js" as="script" />

<!-- prerender：极可能访问的页面，完整预渲染（耗带宽） -->
<link rel="prerender" href="/next-page" />
```

**优先级关系：** `preload` > `preconnect` > `dns-prefetch` > `prefetch` > `prerender`

### 2.4 懒加载（Lazy Loading）

```javascript
// IntersectionObserver —— 图片/组件懒加载
function LazyImage({ src, alt }) {
  const imgRef = useRef(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setLoaded(true);
          observer.disconnect();
        }
      },
      { rootMargin: '200px' } // 提前 200px 加载
    );
    observer.observe(imgRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={imgRef} style={{ minHeight: 200 }}>
      {loaded
        ? <img src={src} alt={alt} />
        : <div class="skeleton" />  {/* 骨架屏占位 */}
      }
    </div>
  );
}

// 原生 loading="lazy" —— 浏览器原生支持
<img src="large-photo.jpg" loading="lazy" alt="..." />
<iframe src="widget.html" loading="lazy"></iframe>
```

### 2.5 关键 CSS（Critical CSS）

```html
<!-- 思路：首屏用内联 CSS（立刻渲染），非关键 CSS 异步加载 -->
<!DOCTYPE html>
<html>
<head>
  <!-- 内联关键 CSS —— 直接写在 HTML 中，无网络请求 -->
  <style>
    header { display: flex; align-items: center; padding: 1rem; }
    .hero { font-size: 2rem; color: #333; }
    @media (max-width: 768px) { .hero { font-size: 1.5rem; } }
  </style>
  
  <!-- 非关键 CSS 异步加载，加载完成后应用到页面 -->
  <link rel="preload" href="/full.css" as="style" 
        onload="this.onload=null; this.rel='stylesheet'" />
  <!-- 降级方案：不支持 JS 时正常加载 -->
  <noscript><link rel="stylesheet" href="/full.css" /></noscript>
</head>
```

**生成关键 CSS 的工具思路**（手动实现见代码）：

```
使用 headless 浏览器（Puppeteer）访问页面 →
截取视口高度范围内渲染所需的样式 →
提取这些样式去重并内联 →
剩余样式标记为异步加载
```

---

## 三、渲染优化：让交互"顺"滑无感

### 3.1 减少回流（Reflow / Layout Thrashing）

**浏览器渲染流水线：**
```
JavaScript → Style → Layout → Paint → Composite
                ↑           ↑
              Reflow    Repaint
```

- **Reflow（回流）**：改变尺寸/位置，触发整个流水线 — **最贵**
- **Repaint（重绘）**：改变颜色/背景，跳过 Layout — **中等**
- **Composite（合成）**：改变 transform/opacity，跳过 Layout+Paint — **最便宜**

```javascript
// ❌ 坏实践 —— 每读一次就触发回流
const el = document.getElementById('box');
for (let i = 0; i < 100; i++) {
  el.style.width = el.offsetWidth + 1 + 'px';  // 每次读都强制回流！
}

// ✅ 好实践 —— 批量读写，先读后写
const width = el.offsetWidth;   // 读一次
el.style.width = width + 100 + 'px';

const height = document.body.clientHeight;
el.style.height = height + 200 + 'px';

// 或者用 requestAnimationFrame 集中写
requestAnimationFrame(() => {
  el.style.width = newWidth + 'px';
  el.style.height = newHeight + 'px';
});
```

**触发回流的常见操作：**
- 读取 `offsetWidth/Height`、`clientWidth/Height`、`getBoundingClientRect()`
- 修改 `width/height/padding/margin/border/top/left`
- 修改字体、添加/删除 DOM 节点
- 改变 `display: none` → `block`

**优化策略：**

```css
/* 1. 使用 transform 替代 top/left 做动画（只触发合成） */
.element { transform: translateX(100px); }  /* 不要用 left: 100px */

/* 2. 使用 opacity 替代 visibility（只触发合成） */
.element { opacity: 0.5; }  /* 不会触发回流 */

/* 3. 强制创建独立渲染层 */
.element { will-change: transform; }
```

### 3.2 requestAnimationFrame：动画优化

```javascript
// ❌ 坏实践 —— 不精确的时间间隔
let pos = 0;
setInterval(() => {
  pos += 5;
  el.style.transform = `translateX(${pos}px)`;
}, 16);  // ~60fps 但难以同步帧

// ✅ requestAnimationFrame —— 与浏览器 VSync 同步
function animate(timestamp) {
  pos += 5;
  el.style.transform = `translateX(${pos}px)`;
  
  if (pos < 500) {
    requestAnimationFrame(animate);  // 下一帧自动调用
  }
}
requestAnimationFrame(animate);

// 兼容节流：控制动画播放速率（30fps）
let lastFrame = 0;
function throttledAnimate(timestamp) {
  if (timestamp - lastFrame >= 33) {  // ~30fps
    lastFrame = timestamp;
    updateFrame();
  }
  requestAnimationFrame(throttledAnimate);
}
```

### 3.3 will-change：告诉浏览器即将变化

```css
/* will-change 让浏览器提前优化 —— 创建独立层 */
.card {
  will-change: transform;
  /* 不用也可以，但浏览器需要检测到变化才创建层 */
}

/* ⚠️ 不要滥用 —— 太多 will-change 会消耗大量内存 */
/* ❌ * { will-change: transform; } */
/* ✅ 在交互即将发生时通过 JS 临时添加 */
.element.addEventListener('mouseenter', () => {
  element.style.willChange = 'transform';
});
element.addEventListener('animationend', () => {
  element.style.willChange = 'auto';  // 用完清除
});
```

### 3.4 防抖（Debounce）vs 节流（Throttle）

```javascript
// === 防抖 —— 只在"停止触发后"执行一次 ===
// 场景：搜索输入（用户停下来了才请求）、窗口 resize 完毕

function debounce(fn, delay = 300) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

const search = debounce(async (query) => {
  const results = await fetch(`/api/search?q=${query}`);
  renderResults(results);
}, 400);  // 用户停下 400ms 后才搜索

// === 节流 —— 固定频率执行（不管触发多频繁） ===
// 场景：滚动事件、鼠标移动、疯狂点击

function throttle(fn, interval = 200) {
  let lastTime = 0;
  return function (...args) {
    const now = Date.now();
    if (now - lastTime >= interval) {
      lastTime = now;
      fn.apply(this, args);
    }
  };
}

const onScroll = throttle(() => {
  checkInfiniteScroll();  // 每 200ms 检查一次，不卡死
}, 200);

// === 增强版：带 trailing 和 leading ===
function throttleEnhanced(fn, interval, { leading = true, trailing = true } = {}) {
  let lastTime = 0;
  let timer = null;
  
  return function (...args) {
    const now = Date.now();
    if (!lastTime && !leading) lastTime = now;
    
    const remaining = interval - (now - lastTime);
    if (remaining <= 0) {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      lastTime = now;
      fn.apply(this, args);
    } else if (trailing && !timer) {
      timer = setTimeout(() => {
        lastTime = leading ? Date.now() : 0;
        timer = null;
        fn.apply(this, args);
      }, remaining);
    }
  };
}
```

**防抖 vs 节流总结：**

| 特性 | 防抖 (Debounce) | 节流 (Throttle) |
|------|:---:|:---:|
| 执行时机 | 停止触发后 | 固定间隔 |
| 连续触发时执行次数 | 1次 | N次（取决于时长） |
| 适用场景 | 搜索联想、窗口resize | 滚动加载、鼠标追踪 |
| 能否保证一定执行 | 能（trailing） | 能（interval 内至少1次） |

---

## 四、Web 安全实战

### 4.1 XSS（跨站脚本攻击）—— 防御全路径

#### 攻击路径

| 类型 | 触发方式 | 示例 |
|------|---------|------|
| **反射型** | URL 参数中注入，服务器未处理直接返回 | `?q=<script>alert('xss')</script>` |
| **存储型** | 恶意脚本存入数据库，用户访问时执行 | 评论区写入 `<script>stealCookie()</script>` |
| **DOM型** | 客户端 JS 将用户输入直接插入 DOM | `innerHTML = userInput` |

#### 防御矩阵

```javascript
// 1. 输出编码 —— 对用户输入做转义
function escapeHtml(str) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
  };
  return str.replace(/[&<>"']/g, (ch) => map[ch]);
}

// 2. 使用安全 API（不要用 innerHTML）
// ❌ document.body.innerHTML = userComment;
// ✅ 
document.body.textContent = userComment;  // 自动转义所有 HTML
document.createElement('div').appendChild(
  document.createTextNode(userComment)    // 更安全
);

// 3. React/Vue 等框架默认做了输出编码
// 但要注意 dangerouslySetInnerHTML / v-html —— 必须配合 DOMPurify
import DOMPurify from 'dompurify';
function SafeRichText({ html }) {
  return <div dangerouslySetInnerHTML={{
    __html: DOMPurify.sanitize(html, { ALLOWED_TAGS: ['b', 'i', 'em'] })
  }} />;
}
```

#### CSP（Content Security Policy）白名单防线

```nginx
# HTTP 响应头 —— 最严格的 XSS 防御（比输出编码更底层）
# 浏览器会拒绝执行不在白名单中的任何脚本

# 严格模式（推荐）—— 只允许哈希匹配的内联脚本
Content-Security-Policy: 
  default-src 'self';
  script-src 'self' 'sha384-ABC123...' 'strict-dynamic';
  style-src 'self' 'unsafe-inline';   # 样式允许内联（多数UI框架需要）
  img-src 'self' https://cdn.example.com data:;
  connect-src 'self' https://api.example.com;
  font-src 'self' https://fonts.gstatic.com;
  object-src 'none';                   # 禁止 <object>/<embed>
  frame-ancestors 'none';             # 禁止 iframe 嵌入（防点击劫持）
  base-uri 'self';                    # 禁止篡改 <base> 标签
  upgrade-insecure-requests;           # 自动升级 HTTP → HTTPS

# 宽松模式（开发过渡）
Content-Security-Policy: script-src 'self' 'unsafe-inline' 'unsafe-eval';
```

### 4.2 CSRF（跨站请求伪造）

#### 攻击原理

```
用户登录 bank.com，拿到 cookie
用户在未登出的情况下访问了 attacker.com（另一个标签页）
attacker.com 的页面里有一个隐藏的表单/图片请求：
  <img src="https://bank.com/transfer?to=hacker&amount=10000" />
浏览器自动携带 bank.com 的 cookie 发送请求 → 转账成功
```

#### 防御方案

```javascript
// 1. SameSite Cookie 属性（最简单的防线）
// Set-Cookie 响应头
Set-Cookie: session_id=abc123; SameSite=Strict; Secure; HttpOnly

// SameSite 可选值：
//   Strict：所有跨站请求都不携带 cookie（最安全）
//   Lax：GET 请求等"安全"方法允许跨站携带（默认值）
//   None：允许所有跨站携带（需要 Secure 属性）

// 2. CSRF Token（经典方案）
// 服务器生成随机 token 嵌入页面
// 每次请求需要携带此 token，攻击者无法获取
function generateCsrfToken() {
  return crypto.randomUUID();
}

// 3. 自定义请求头
// 通过 AJAX 发送，设置 X-Requested-With: XMLHttpRequest
// 浏览器会先发 OPTIONS 预检请求，攻击者无法伪造
fetch('/api/transfer', {
  method: 'POST',
  headers: {
    'X-Requested-With': 'XMLHttpRequest',
    'X-CSRF-Token': csrfToken,
  },
  credentials: 'same-origin',  // 只带同源 cookie
});
```

### 4.3 HTTPS + HSTS

```nginx
# Nginx HTTPS 配置
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/ssl/certs/example.com.pem;
    ssl_certificate_key /etc/ssl/private/example.com.key;
    
    # 加密套件 —— 禁用不安全算法
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    
    # HSTS —— 告诉浏览器"以后只用 HTTPS 访问我"
    # 浏览器会记住这个域名，下次直接 HTTPS，跳过 HTTP → HTTPS 重定向
    add_header Strict-Transport-Security 
        "max-age=63072000; includeSubDomains; preload" always;
    # max-age=2年，包含子域，申请预加载列表
    
    # 重定向 HTTP → HTTPS
    if ($scheme = http) {
        return 301 https://$host$request_uri;
    }
}
```

### 4.4 子资源完整性（SRI）

```html
<!-- 
  SRI：确保 CDN 上的脚本没有被篡改
  浏览器下载文件后计算哈希，与指定的哈希比对
  不匹配则拒绝执行
-->
<script 
  src="https://cdn.example.com/react@18.2.0/umd/react.production.min.js"
  integrity="sha384-7Q+SmR5p6+5aX7sR1F5B5F5zY5F5z5F5z5Y5fA9+..."
  crossorigin="anonymous">
</script>

<script 
  src="https://cdn.example.com/lodash@4.17.21/lodash.min.js"
  integrity="sha384-7Q+SmR5p6+5aX7sR1F5B5F5zY5F5z5F5z5Y5fA9+..."
  crossorigin="anonymous">
</script>

<!-- 
  生成 SRI 哈希：
  openssl dgst -sha384 -binary file.js | openssl base64 -A
  # 或 
  cat file.js | openssl dgst -sha384 -binary | openssl enc -base64 -A
-->
```

### 4.5 CSP 完整配置实战

```nginx
# ========== 渐进式 CSP 配置策略 ==========

# 阶段 1：仅报告模式（Report-Only）—— 先观察不拦截
Content-Security-Policy-Report-Only: 
  default-src 'self';
  script-src 'self';
  report-uri /csp-violations;

# 阶段 2：严格模式（推荐）
Content-Security-Policy: 
  # 默认来源：仅同源
  default-src 'self';
  
  # 脚本：自身 + 带 nonce 的内联 + 严格动态
  script-src 'self' 'nonce-{random}' 'strict-dynamic';
  
  # 样式：自身 + 内联（大部分框架需要）
  style-src 'self' 'unsafe-inline';
  
  # 图片：自身 + CDN + base64 data URL
  img-src 'self' https: data: blob:;
  
  # 网络请求（fetch/XMLHttpRequest）
  connect-src 'self' https://api.example.com wss://ws.example.com;
  
  # 字体
  font-src 'self' https://fonts.gstatic.com;
  
  # 媒体
  media-src 'self';
  
  # 对象（一般设为 none，阻止 Flash 等）
  object-src 'none';
  
  # 框架嵌入（防点击劫持）
  frame-ancestors 'none';
  
  # 基础 URI（防 <base> 劫持）
  base-uri 'self';
  
  # 自动升级不安全请求
  upgrade-insecure-requests;
  
  # 报告违规
  report-uri /csp-report;

# 阶段 3：使用 nonce 替代 hash（更方便）
# 每次页面请求生成不同的 nonce 值
```

### 4.6 其他重要安全头

```nginx
# X-Content-Type-Options：禁止 MIME 嗅探（防内容类型注入）
add_header X-Content-Type-Options "nosniff" always;

# X-Frame-Options：禁止 iframe 嵌入（老版本浏览器兼容）
add_header X-Frame-Options "DENY" always;

# Referrer-Policy：控制 Referer 头携带的信息
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# Permissions-Policy：限制浏览器 API
add_header Permissions-Policy 
  "camera=(), microphone=(), geolocation=(self 'https://example.com')" always;
```

---

## 五、Web 性能/安全检查工具（Python 实现）

详见配套代码：`memory/learning/code/web_audit_tool.py`

### 功能模块

| 模块 | 类/函数 | 功能 |
|------|---------|------|
| 性能模拟 | `WebVitalSimulator` | 模拟生成 LCP/FID/CLS 数据，评估评级 |
| 关键路径 | `CriticalPathAnalyzer` | 解析页面资源依赖，识别阻塞资源 |
| CSP 生成 | `CSPGenerator` | 按规则生成 CSP 策略字符串 |
| CSP 验证 | `CSPValidator` | 解析 CSP 头，检查安全弱点 |
| XSS 扫描 | `XSSScanner` | 检测常见 XSS 注入模式 |
| 综合报告 | `WebAuditReport` | 生成完整的性能+安全检查报告 |

### 使用示例

```bash
# 生成 CSP 策略
python web_audit_tool.py csp --origin https://example.com --strict

# 验证 CSP 头
python web_audit_tool.py validate-csp "default-src 'self'"

# 扫描 XSS 模式
python web_audit_tool.py xss --url https://example.com

# 生成完整审计报告
python web_audit_tool.py audit --url https://example.com --output report.json
```

---

## 六、核心要点总结

### 性能优化 check list

- [ ] 压缩 JS/CSS，使用 Tree Shaking 去除无用代码
- [ ] 图片使用 WebP/AVIF 格式，配合 `<picture>` 自适应
- [ ] 代码分割：按路由/按需 `import()` + React.lazy
- [ ] 内联关键 CSS，异步加载非关键 CSS
- [ ] 图片/组件使用 IntersectionObserver 懒加载
- [ ] 使用 `<link rel="preload">` 提前加载关键资源
- [ ] 用 `<link rel="preconnect">` 预热第三方连接
- [ ] 动画使用 transform/opacity（只触发合成层）
- [ ] 批量 DOM 读写避免 Layout Thrashing
- [ ] 搜索/滚动添加防抖/节流

### 安全防护 check list

- [ ] 所有用户输出做 HTML 编码转义
- [ ] 不要使用 `innerHTML`，用 `textContent` / `createTextNode`
- [ ] 设置 CSP 头（`Content-Security-Policy`）
- [ ] 设置 Strict-Transport-Security（HSTS）
- [ ] 设置 SameSite Cookie（Strict/Lax）
- [ ] 使用 CSRF Token 保护敏感接口
- [ ] 所有外部脚本添加 SRI integrity 字段
- [ ] 设置 X-Content-Type-Options: nosniff
- [ ] 设置 X-Frame-Options: DENY
- [ ] HTTPS 全站部署 + 自动重定向

---

## 七、与其他课程的联系

| 课程 | 关联点 |
|------|--------|
| [HTML/CSS 基础](front_01_html_css.md) | 语义化标签利于性能，图片加载属性 |
| [JS 核心](front_03_js_core.md) | 事件循环与长任务，异步加载模式 |
| [Vite 工程化](front_07_engineering.md) | 代码分割配置，压缩优化配置 |
| [HTTP/HTTPS](network_02_dns_http.md) | TTFB 优化，HTTPS 完整流程 |
| [CDN](network_03_cdn.md) | 资源分发加速，负载均衡 |
