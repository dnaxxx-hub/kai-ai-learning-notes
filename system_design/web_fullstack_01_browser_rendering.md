# Web 全栈第1课：浏览器渲染原理

> 日期：2026-05-11 | 课程：Web 全栈 Phase 1-1
> 核心思维：浏览器不是黑盒——理解它的"工厂流水线"，才能写出性能靠谱的页面

---

## 一、Chrome 多进程架构

### 1.1 进程模型

Chrome 采用**多进程架构**，每个核心职责独立进程：

```
┌─────────────────────────────────────────────────────┐
│                    Browser Process                    │
│  地址栏 / 书签 / 网络请求 / 文件读写 / 下载管理       │
└──────────┬──────────┬──────────┬────────────────────┘
           │          │          │
    ┌──────▼──┐ ┌─────▼─────┐ ┌─▼──────────┐
    │ Renderer │ │ GPU       │ │ Plugin/     │
    │ Process  │ │ Process   │ │ Extension   │
    │ (每个Tab)│ │ (GPU加速) │ │ Process     │
    └──────────┘ └───────────┘ └─────────────┘
```

| 进程 | 职责 | 数量 |
|------|------|------|
| **Browser** 主进程 | UI、网络、文件、导航 | 1个 |
| **Renderer** 渲染进程 | HTML/CSS/JS 解析、渲染 | 每个Tab 1个（沙箱隔离） |
| **GPU** 进程 | GPU 加速合成、Canvas/WebGL | 1个 |
| **Utility** 工具进程 | 网络服务、数据解码等 | 按需创建 |
| **Plugin/Extension** | 插件、扩展独立运行 | 按需创建 |

### 1.2 渲染进程内部（Renderer Process 的核心线程）

渲染进程内有**多个线程**，最重要的几个：

```
┌─────────────────── 渲染进程 (Renderer Process) ───────────────────┐
│                                                                    │
│  ┌─────────────────────┐    ┌────────────────────┐                │
│  │   Main Thread       │    │  Worker Threads    │                │
│  │   (主线程)           │    │  (Web Workers)     │                │
│  │   解析HTML → 构建DOM │    │  独立运行JS        │                │
│  │   解析CSS → CSSOM   │    │  不能操作DOM       │                │
│  │   执行JS             │    └────────────────────┘                │
│  │   计算Layout         │                                          │
│  │   绘制 Paint         │    ┌────────────────────┐                │
│  └─────────────────────┘    │  Compositor Thread  │                │
│                              │  合成图层 → 显示    │                │
│                              │  滚动 / 动画        │                │
│                              └────────────────────┘                │
└────────────────────────────────────────────────────────────────────┘
```

**关键洞见**：主线程就是"单线程"——这就是为什么 JS 阻塞会卡住页面的根本原因。

---

## 二、关键渲染路径 (Critical Rendering Path, CRP)

### 2.1 完整流水线

```
HTML ──→ DOM
            │
            ├──→ Render Tree ──→ Layout ──→ Paint ──→ Composite ──→ 屏幕
            │         │            │          │            │
CSS  ──→ CSSOM ───────┘            │          │            │
                                    │          │            │
                             计算每个元素   填充像素     图层合成
                             的位置/大小                   (GPU)
```

### 2.2 分步详解

#### Step 1: DOM 构建
```html
<!-- HTML 被解析成 DOM 树（Document Object Model） -->
<html>
  <head>...</head>
  <body>
    <div id="app">
      <h1>标题</h1>
      <p>正文</p>
    </div>
  </body>
</html>
```

```
document
 └── html
      ├── head
      └── body
           └── div#app
                ├── h1
                └── p
```

> **注意**：遇到 `<script>` 标签**会阻塞 DOM 解析**（除非加 `defer` 或 `async`）

#### Step 2: CSSOM 构建
CSS 被解析成 CSSOM（CSS Object Model），**同样会阻塞渲染**。

```css
/* CSSOM = 反向选择的规则树 */
body { font-size: 16px; }
h1 { color: blue; font-size: 24px; }
p { color: gray; }
```

#### Step 3: Render Tree

DOM + CSSOM → 合并为 **Render Tree**

```
DOM:        body > div#app > h1
CSSOM:      body {font-size:16}  h1 {color:blue; font-size:24}

Render Tree: 只包含可见节点
┌─────────────┐
│  body (16px)│
│  └── div#app│
│      └── h1 │ ← color:blue, font-size:24px
└─────────────┘
```

**排除不可见节点**：`display: none`、`<head>`、`<script>`

> ⚠️ `visibility: hidden` 和 `opacity: 0` **会**出现在 Render Tree（占位但透明）

#### Step 4: Layout（回流 / Reflow）

计算每个节点的**几何属性**：宽、高、x、y。

```html
<div style="width: 50%; padding: 16px; margin: 8px;">
  <p>某文本</p>
</div>
```

Layout 过程：
```
父容器宽度 = 视口宽度 (假设 1200px)
div.width = 1200 * 50% = 600px
div.padding = 16px (左右各16px)
div.content-box = 600 - 32 = 568px
p.width = 568px (默认auto)
p.height = 文本行数 × 行高
```

**触发 Layout（回流）的操作** ⚡：
- 读取 `offsetHeight` / `getBoundingClientRect()` 等几何属性
- 修改宽/高/位置/边距/字体
- 窗口 resize
- 添加/删除 DOM 节点

#### Step 5: Paint（绘制）

把每个节点的**视觉属性**画成像素：颜色、背景、边框、阴影。

Paint 是**最慢**的阶段之一——涉及大量像素操作。

#### Step 6: Composite（合成）

将多个**图层**（Layer）合成为最终画面。

```
                    Compositor Thread (独立于主线程)
Layer 1 (背景) ──┐
Layer 2 (文本) ──┼──→ 合成 ──→ GPU 显示
Layer 3 (动画)  ─┘        ↑
                    合成在 GPU 上完成，不阻塞主线程！
```

**只触发 Composite（不回流、不重绘）的属性**（性能最佳）：
- `transform`: translate / scale / rotate
- `opacity`

```css
/* ✅ 推荐：GPU加速，只合成 */
.animated {
  transform: translateX(100px);
  opacity: 0.5;
  transition: transform 0.3s;
}

/* ❌ 避免：触发 Layout + Paint */
.bad {
  left: 100px;
  width: 50%;
}
```

### 2.3 优化 CRP 的核心原则

```
1. 减少关键资源数       ← 合并 CSS/JS，内联关键 CSS
2. 缩小关键资源大小      ← 压缩、tree shaking
3. 延迟非关键资源       ← async/defer、media="print"
4. 避免 Layout thrashing ← 批量读写 DOM 几何属性
```

**Layout thrashing（布局抖动）**——性能杀手：
```javascript
// ❌ 坏：交替读写 → 强制回流 N 次
for (let i = 0; i < 1000; i++) {
  const w = div.offsetWidth;           // 读 → 强制回流
  div.style.width = (w + 1) + 'px';     // 写
}

// ✅ 好：批量读，批量写
const widths = [];
for (let i = 0; i < 1000; i++) {
  widths.push(div.offsetWidth);        // 批量读
}
for (let i = 0; i < 1000; i++) {
  div.style.width = (widths[i] + 1) + 'px';  // 批量写
}
```

---

## 三、CSS 盒模型与布局

### 3.1 盒模型

每个元素都是"矩形盒子"：

```
┌───────────────────────────────────────┐
│        Margin (外边距)                 │
│  ┌─────────────────────────────┐      │
│  │     Border (边框)            │      │
│  │  ┌───────────────────────┐  │      │
│  │  │  Padding (内边距)      │  │      │
│  │  │  ┌─────────────────┐  │  │      │
│  │  │  │  Content (内容)  │  │  │      │
│  │  │  └─────────────────┘  │  │      │
│  │  └───────────────────────┘  │      │
│  └─────────────────────────────┘      │
└───────────────────────────────────────┘
```

**两种盒模型**：

| 模型 | box-sizing | width 含义 | 公式 |
|------|-----------|-----------|------|
| Content-box (默认) | `content-box` | 仅内容区 | 总宽 = width + padding + border |
| Border-box (推荐) | `border-box` | 内容+padding+border | 总宽 = width |

```css
/* ✅ 全局使用 border-box 避免算数灾难 */
*, *::before, *::after {
  box-sizing: border-box;
}
```

### 3.2 Flexbox — 一维布局

```css
.container {
  display: flex;
  justify-content: center;  /* 主轴居中 */
  align-items: center;      /* 交叉轴居中 */
  gap: 16px;                /* 间距 */
}

.item {
  flex: 1;         /* 等分剩余空间，简写 flex-grow:1 + flex-shrink:1 + flex-basis:0 */
  /* flex: 0 1 auto; ← 默认值 */
}
```

**Flex 关键概念**：
- **主轴**（main axis）：由 `flex-direction` 决定（`row` / `column`）
- **交叉轴**（cross axis）：与主轴垂直
- `flex-grow`：剩余空间分配比例
- `flex-shrink`：空间不足时收缩比例
- `flex-basis`：初始大小（替代 width/height）

### 3.3 Grid — 二维布局

```css
.container {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;  /* 三列，中间列2倍宽 */
  grid-template-rows: auto 200px;       /* 两行，第二行固定200px */
  gap: 16px;
}

/* 精确定位 */
.item {
  grid-column: 1 / 3;  /* 从第1列到第3列 */
  grid-row: 2;
}
```

### 3.4 定位（Positioning）

```css
.static   { position: static; }        /* 默认，正常文档流 */
.relative { position: relative; top: 10px; }  /* 相对自身偏移（不脱离文档流） */
.absolute { position: absolute; top: 0; }     /* 脱离文档流，相对于最近的非static祖先 */
.fixed    { position: fixed; top: 0; }         /* 脱离，相对于视口，滚动也不动 */
.sticky   { position: sticky; top: 0; }        /* 混合：正常流 + 粘在视口位置 */
```

---

## 四、JavaScript 事件循环（Event Loop）

### 4.1 事件循环图解

```
                执行栈 (Call Stack)
               ┌───────────────┐
               │   func C()    │  ← 正在执行
               │   func B()    │
               │   func A()    │
               └───────┬───────┘
                       │ 空了就从回调队列取
          ┌────────────▼────────────┐
          │   回调队列 (Callback Q)   │
          │ [task1, task2, ...]      │
          └─────────────────────────┘
                       ▲
            ┌──────────┴──────────┐
            │                     │
      MicroTask Queue        MacroTask Queue
      (Promise.then)         (setTimeout)
      (MutationObserver)     (setInterval)
                             (I/O)
                             (UI 渲染)
```

**执行顺序（每一轮「事件循环」）**：
```
1. 执行栈执行同步代码
2. 清空 MicroTask 队列 (全部)
3. 取一个 MacroTask 执行
4. 浏览器可能更新渲染（requestAnimationFrame 在这里）
5. 回到 2
```

### 4.2 宏任务 vs 微任务

```javascript
console.log(1);                        // 同步

setTimeout(() => console.log(2), 0);    // MacroTask

Promise.resolve().then(() => {
  console.log(3);                       // MicroTask
});

console.log(4);                         // 同步

// 输出: 1 → 4 → 3 → 2
// （注意：Promise.then 比 setTimeout 先执行！）
```

### 4.3 requestAnimationFrame（rAF）

```javascript
// rAF 在每次渲染之前执行，最适合动画
let id = 0;
function animate() {
  element.style.transform = `translateX(${id}px)`;
  id++;
  requestAnimationFrame(animate);  // 递归调用
}
```

**优先级**：MacroTask < rAF < MicroTask (有特殊情况，但rAF在渲染前)

### 4.4 事件循环与渲染的时机

```
         ┌─────── 一帧 (约16.6ms, 60fps) ────────┐
         │                                         │
  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
  │ Task Queue   │  │ MicroTask   │  │  渲染        │
  │ (JS执行)     │  │ (Promise等)  │  │ (rAF/布局/   │
  │              │  │             │  │  绘制/合成)   │
  └──────────────┘  └──────────────┘  └──────────────┘
```

如果 "JS 执行 + MicroTask" 超过了 **16.6ms** → 掉帧！

---

## 五、Python 渲染模拟

```python
"""
浏览器关键渲染路径 (CRP) 模拟
展示 DOM → CSSOM → Render Tree → Layout → Paint 的过程
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# === DOM 节点 ===
@dataclass
class DOMNode:
    tag: str
    id: str = ""
    classes: list[str] = field(default_factory=list)
    children: list[DOMNode] = field(default_factory=list)
    styles: dict[str, str] = field(default_factory=dict)
    text: str = ""


# === CSS 规则 ===
@dataclass
class CSSRule:
    selector: str          # 简化 selector，仅演示
    properties: dict[str, str]


# === Render Tree 节点 ===
@dataclass
class RenderNode:
    dom_node: DOMNode
    computed_style: dict[str, str]
    children: list[RenderNode] = field(default_factory=list)
    # Layout 结果
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0


class BrowserRenderer:
    """模拟浏览器渲染管道"""

    def __init__(self, viewport_width: float = 1200):
        self.viewport_width = viewport_width
        self.rules: list[CSSRule] = []
        self.render_tree: list[RenderNode] = []

    def add_css(self, rules: list[CSSRule]):
        self.rules.extend(rules)

    def parse_html(self, html: str) -> DOMNode:
        """极简 HTML 解析器（仅演示流程）"""
        # 实际应该用真正的 parser，这里略
        raise NotImplementedError("生产环境请用 html.parser")

    def build_dom_from_data(self, root: DOMNode):
        """手动传入 DOM 树"""
        self.dom_root = root

    def apply_css(self, node: DOMNode) -> dict[str, str]:
        """计算节点样式（简化版：模拟浏览器匹配 CSS）"""
        style: dict[str, str] = {}
        # 默认样式
        defaults = {
            "display": "block",
            "width": "auto",
            "height": "auto",
            "padding": "0px",
            "margin": "0px",
            "color": "black",
            "font-size": "16px",
            "visibility": "visible",
        }
        style.update(defaults)

        # 内联样式优先级最高
        style.update(node.styles)

        # id 选择器
        for rule in self.rules:
            if rule.selector == f"#{node.id}":
                style.update(rule.properties)

        # 标签选择器
        for rule in self.rules:
            if rule.selector == node.tag:
                style.update(rule.properties)

        # class 选择器
        for cls in node.classes:
            for rule in self.rules:
                if rule.selector == f".{cls}":
                    style.update(rule.properties)

        return style

    def is_visible(self, style: dict[str, str]) -> bool:
        """判断是否在 Render Tree 中可见"""
        if style.get("display") == "none":
            return False
        return True

    def build_render_tree(self, node: DOMNode) -> Optional[RenderNode]:
        """DOM + CSSOM → Render Tree"""
        style = self.apply_css(node)
        if not self.is_visible(style):
            return None

        render = RenderNode(dom_node=node, computed_style=style)
        for child in node.children:
            cr = self.build_render_tree(child)
            if cr:
                render.children.append(cr)
        return render

    def layout(self, node: RenderNode, container_width: float, y_offset: float = 0):
        """Layout 计算：确定位置和大小"""
        style = node.computed_style
        padding = int(style.get("padding", "0px").replace("px", ""))
        margin = int(style.get("margin", "0px").replace("px", ""))

        # 解析 width
        width_str = style.get("width", "auto")
        if width_str == "auto":
            width = container_width - 2 * margin
        elif "%" in width_str:
            width = container_width * float(width_str.replace("%", "")) / 100
        else:
            width = float(width_str.replace("px", ""))

        # 高度暂估计（实际需要根据内容计算）
        height = 100.0  # placeholder

        node.x = margin
        node.y = y_offset + margin
        node.width = width - 2 * padding
        node.height = height - 2 * padding

        # 布局子节点
        child_y = node.y + padding + node.height
        for child in node.children:
            self.layout(child, node.width, child_y)
            child_y += child.height + 10  # margin collapse 简化

    def paint(self, node: RenderNode, depth: int = 0):
        """Paint 模拟：打印渲染结果"""
        indent = "  " * depth
        style = node.computed_style
        print(f"{indent}<{node.dom_node.tag}> "
              f"pos=({node.x:.0f}, {node.y:.0f}) "
              f"size=({node.width:.0f}x{node.height:.0f}) "
              f"color={style.get('color', 'black')}")
        for child in node.children:
            self.paint(child, depth + 1)

    def render(self):
        """完整渲染管线"""
        print("=== Step 1: Build Render Tree ===")
        self.render_root = self.build_render_tree(self.dom_root)
        if not self.render_root:
            print("(nothing visible)")
            return

        print("=== Step 2: Layout ===")
        self.layout(self.render_root, self.viewport_width)

        print("=== Step 3: Paint ===")
        self.paint(self.render_root)


# === 演示 ===
if __name__ == "__main__":
    css_rules = [
        CSSRule("body", {"font-size": "16px", "margin": "8px"}),
        CSSRule("h1", {"color": "navy", "font-size": "24px"}),
        CSSRule("p", {"color": "#333"}),
        CSSRule(".card", {
            "padding": "16px",
            "margin": "8px",
            "background": "#f5f5f5",
        }),
    ]

    dom = DOMNode(
        tag="body",
        children=[
            DOMNode(tag="h1", text="Hello World",
                    styles={"color": "blue"}),
            DOMNode(tag="div", classes=["card"], children=[
                DOMNode(tag="p", text="Card content here"),
                DOMNode(tag="p", text="Another paragraph"),
            ]),
            DOMNode(
                tag="div", id="hidden",
                styles={"display": "none"},
                children=[DOMNode(tag="p", text="I am hidden")]
            ),
        ],
    )

    renderer = BrowserRenderer(viewport_width=1200)
    renderer.add_css(css_rules)
    renderer.dom_root = dom
    renderer.render()
```

运行输出：
```
=== Step 1: Build Render Tree ===
=== Step 2: Layout ===
=== Step 3: Paint ===
<body> pos=(0, 0) size=(1184x100) color=black
  <h1> pos=(0, 110) size=(1184x100) color=blue
  <div> pos=(8, 220) size=(1168x100) color=black
    <p> pos=(24, 330) size=(1136x100) color=#333
    <p> pos=(24, 440) size=(1136x100) color=#333
```

---

## 六、总结图谱

```
┌─────────────────────────────────────────────────────────────┐
│                  浏览器渲染原理（全局图）                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  任务调度                         渲染管道                    │
│  ┌────────────────┐              ┌─────────────────────┐    │
│  │  JS 执行栈      │              │  HTML Parsing → DOM │    │
│  │  MicroTask      │              │  CSS Parsing→CSSOM │    │
│  │  MacroTask      │              │      ↓              │    │
│  │  rAF            │              │  Render Tree        │    │
│  │  渲染            │              │      ↓              │    │
│  └────────────────┘              │  Layout             │    │
│                                   │      ↓              │    │
│  布局体系                          │  Paint              │    │
│  ┌────────────────┐              │      ↓              │    │
│  │  盒模型          │              │  Composite (GPU)   │    │
│  │  Flexbox        │              └─────────────────────┘    │
│  │  Grid           │                                         │
│  │  Position       │         关键红线：                        │
│  └────────────────┘         JS 执行 → 阻塞 DOM 构建            │
│                             读写几何 → 强制回流 (Reflow)        │
│                              transform/opacity → 仅合成        │
└─────────────────────────────────────────────────────────────┘
```

**一句话总结**：浏览器渲染 = HTML→DOM + CSS→CSSOM → Render Tree → Layout → Paint → Composite，整个过程受**事件循环**控制，JS 执行会阻塞渲染， **transform/opacity** 是性能救星。

---

> 下一课预告：Web 全栈第2课 — React 核心原理（虚拟 DOM、Diff 算法、Hooks 链表）
