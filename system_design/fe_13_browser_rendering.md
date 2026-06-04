# 浏览器渲染管线 — Critical Rendering Path

## 一、核心路径 (CRP)

```
HTML → DOM         → Render Tree → Layout → Paint → Composite
CSS  → CSSOM  ↗
```

**六阶段详解**:

### 1. DOM 构建
- 字节 → 字符 → Tokenizer → Nodes → DOM Tree
- 阻塞渲染：`<script>` 会暂停 DOM 解析（除非 `defer/async`）
- 非阻塞：`<link>` 不会阻塞 DOM

### 2. CSSOM 构建
- CSS 被解析为 Style Rules
- **阻塞渲染**：CSSOM 未就绪时 Render Tree 无法构建
- `media` 属性可使 CSS 非阻塞：`<link media="print">`

### 3. Render Tree
- DOM + CSSOM → 只含**可见节点**
- `display:none` 节点被忽略（`visibility:hidden` 会保留）
- 每个节点包含：几何信息 + 样式

### 4. Layout (回流)
- 计算每个可见元素的几何位置（x, y, width, height）
- 相对单位 → 像素值
- **最耗性能**的一步

### 5. Paint (绘制)
- 将 Layout 结果转换为像素
- 填充颜色、绘制文字、边框、阴影
- 分层进行（Paint Layers）

### 6. Composite (合成)
- 将多个 Paint Layer 合成为最终屏幕图像
- GPU 加速在此阶段

## 二、Layout — 回流与重绘

### Reflow (回流)
**定义**: 重新计算元素几何属性（尺寸/位置）

**触发条件**:
- 增删 DOM 节点
- 修改尺寸（width/height/padding/margin）
- 修改位置（top/left/flex 属性）
- 获取布局信息（`offsetHeight/getBoundingClientRect()` → 强制同步布局）
- 字体变化
- 窗口 resize

**性能影响**: 触发 reflow 后，必须**重新执行 Layout → Paint → Composite**

### Repaint (重绘)
**定义**: 仅重新绘制外观，不涉及布局

**触发条件**:
- 更改颜色/背景/阴影/边框颜色
- `visibility: hidden` / `outline`

**性能**: 比 reflow 轻量（跳过 Layout 阶段）

### 层叠上下文 (Stacking Context)
**创建条件**: `position:relative/absolute + z-index`、`opacity < 1`、`transform`、`filter`、`will-change`

**渲染优化**: 提升为独立图层 → Paint 不互相影响

## 三、Composite — 合成层 & GPU 加速

### 合成层 (Compositor Layer)
```
普通元素 → Paint → Composite (CPU)
合成层   → Paint → Composite (GPU)
```

**创建合成层的 CSS 属性**:
- `will-change: transform | opacity`
- `transform: translateZ(0)` / `translate3d()`
- `opacity` 动画
- `position: fixed`
- `<video>` / `<canvas>` / `<iframe>`

**GPU 加速原理**:
1. 图层被上传为 GPU 纹理
2. 合成器独立变换各图层（无需 CPU 重绘）
3. 仅 composite 阶段更新 → 60fps 流畅

**动画最优化策略**:
```
好: transform + opacity（仅 composite）
差: width/height（reflow）
中: color/background（repaint）
```

## 四、Performance API 关键指标

| 指标 | 全称 | 衡量内容 | 达标值 |
|------|------|---------|-------|
| **FP** | First Paint | 首个像素渲染 | < 1.8s |
| **FCP** | First Contentful Paint | 首段文本/图片 | < 1.8s |
| **LCP** | Largest Contentful Paint | 最大内容渲染 | < 2.5s |
| **CLS** | Cumulative Layout Shift | 布局偏移总和 | < 0.1 |
| **INP** | Interaction to Next Paint | 交互响应延迟 | < 200ms |
| **TBT** | Total Blocking Time | 主线程阻塞总和 | < 200ms |

### LayoutShift API
```js
new PerformanceObserver(list => {
  for (const entry of list.getEntries()) {
    // entry.value = layout shift score
    if (!entry.hadRecentInput) CLS += entry.value
  }
}).observe({type: 'layout-shift', buffered: true})
```

### 优化策略总结
- **LCP 优化**: 预加载 LCP 资源 (`<link rel="preload">`)、优化图片格式
- **CLS 优化**: 预留图片尺寸 (`width/height`)、避免动态插入内容
- **INP 优化**: 拆分长任务（`yield`/`setTimeout`）、Web Worker
- **TBT 优化**: 代码分割、延迟非关键 JS（`defer`/`async`）
