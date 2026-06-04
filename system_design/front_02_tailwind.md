# TailwindCSS：实用优先的CSS框架

> 日期：2026-05-07 20:31 | 课程：前端路线 Phase 1-2
> 目标：理解"为什么不用写CSS文件也能做网站"

## 核心思想

```html
<!-- 传统CSS: 
     先写class名 → 再到CSS文件里写一堆样式 -->

<!-- 传统做法 -->
<button class="btn-primary">提交</button>
<!-- .btn-primary { background: blue; padding: 8px 16px; border-radius: 4px; color: white; } -->

<!-- Tailwind: 直接用class写样式 -->
<button class="bg-blue-500 px-4 py-2 rounded text-white">提交</button>
```

## 为什么Tailwind火了

```css
/* 传统CSS的问题: */

/* 1. 命名灾难 */
.header-title {}
.header-title-wrapper {}
.header-title-wrapper-inner {}

/* 2. 上下文依赖 */
.button { color: blue; }
.footer .button { color: gray; }
/* 不知道最后效果是什么，因为会影响哪里不确定 */

/* 3. CSS文件越来越大 */
/* 加一个新功能 → 加一个新class → 但旧的没人敢删 */
```

## Tailwind的设计

```html
<!-- 所有样式 = 预定义的class名 -->

<!-- 布局 -->
<div class="flex justify-between items-center gap-4">

<!-- 间距 -->
<div class="p-4 m-2">  <!-- padding: 1rem; margin: 0.5rem -->

<!-- 颜色 -->
<div class="bg-blue-500 text-white hover:bg-blue-600">

<!-- 响应式 -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
<!-- mobile: 1列, md以上: 2列, lg以上: 4列 -->

<!-- 暗色模式 -->
<div class="bg-white dark:bg-gray-800 text-black dark:text-white">
```

## 原子化CSS

```css
/* Tailwind的class = 原子化的CSS属性 */

/* 一个class = 一个CSS声明 */
.m-4 { margin: 1rem; }
.p-2 { padding: 0.5rem; }
.flex { display: flex; }
.text-center { text-align: center; }

/* 组合class = 组合样式 */
/* <div class="m-4 p-2 flex text-center"> */
```

## 优势

| 特性 | 传统CSS | Tailwind |
|------|---------|----------|
| 命名 | 需要想名字 | 不用想 |
| 文件 | 多个CSS文件 | 一个出口文件 |
| 重构 | 不敢删CSS | 删class就行 |
| 团队 | 命名风格不统一 | 统一设计系统 |
| 大小 | 越来越大 | Purge后极小 |

## 配合原始HTML（无构建工具）
```html
<!-- CDN直接用 Tailwind -->
<script src="https://cdn.tailwindcss.com"></script>
```

## 今日收获
- Tailwind = class就是样式，不写CSS文件
- **原子化CSS = 一个属性一个class**
- 不用命名，不用全局污染，不用维护CSS文件
- 响应式 = md: lg: 前缀
- 暗色模式 = dark: 前缀
- 适合：团队协作/快速原型/个人项目
