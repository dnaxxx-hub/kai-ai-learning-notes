# HTML + CSS 基础

> 日期：2026-05-07 20:30 | 课程：前端路线 Phase 1-1
> 目标：理解"网页的基本骨架和样式"

## 核心问题

```
浏览器打开一个文件 → 怎么变成"有布局有颜色有排版的页面"？
三层结构:
- HTML: 内容骨架（"这是一段文字"）
- CSS:  视觉样式（"文字红色，字号20px"）
- JS:   交互行为（"点击弹出对话框"）
```

## 盒子模型（最重要的CSS概念）

```css
/* 每个HTML元素都是一个"盒子" */
.box {
  width: 200px;
  height: 100px;
  padding: 20px;     /* 内边距 (内容到边框) */
  border: 2px solid; /* 边框 */
  margin: 10px;      /* 外边距 (到其他元素) */
}
```

```
┌─────────────────────────────┐
│          margin             │
│  ┌─────────────────────┐    │
│  │      border         │    │
│  │  ┌─────────────┐    │    │
│  │  │  padding    │    │    │
│  │  │ 内容区域    │    │    │
│  │  │ 200×100     │    │    │
│  │  └─────────────┘    │    │
│  │                     │    │
│  └─────────────────────┘    │
└─────────────────────────────┘
```

### box-sizing

```css
/* 默认: box-sizing: content-box */
/* width = 内容宽度，padding+border另算 */

/* 推荐: box-sizing: border-box */
/* width = 内容+padding+border的总和 */
/* 不用脑算，推荐全部元素都用 */
* { box-sizing: border-box; }
```

## Flexbox — 一维布局

```css
/* 核心: 父容器 display: flex → 子元素自动排列 */

.container {
  display: flex;
  justify-content: center;     /* 主轴居中 */
  align-items: center;         /* 交叉轴居中 */
  gap: 16px;                   /* 间距 */
  flex-wrap: wrap;             /* 换行 */
}

/* 完美的居中方案 */
.centering {
  display: flex;
  justify-content: center;
  align-items: center;
  /* 以前要用 position: absolute + transform */
  /* 现在一行搞定 */
}
```

## Grid — 二维布局

```css
.container {
  display: grid;
  grid-template-columns: repeat(3, 1fr);  /* 3等分 */
  grid-template-rows: auto;
  gap: 20px;
}
```

## 定位

```css
/* 四种定位模式 */
.static   { position: static; }   /* 默认，正常流 */
.relative { position: relative; } /* 相对原位置偏移 */
.absolute { position: absolute; } /* 相对最近定位祖先 */
.fixed    { position: fixed; }    /* 相对视口固定 */

/* 配合top/left/right/bottom使用 */
```

## 今日收获
- 盒子模型 = 网页布局的基础
- box-sizing: border-box = 省心推荐
- Flexbox = 一维排列（90%的布局场景够用）
- Grid = 二维网格（复杂布局）
- 以前靠float + clearfix的时代已经过去了
