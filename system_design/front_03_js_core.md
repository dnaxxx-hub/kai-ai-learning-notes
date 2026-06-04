# JavaScript 核心

> 日期：2026-05-07 20:32 | 课程：前端路线 Phase 2-1
> 目标：理解"前端编程语言的核心机制"

## 核心问题

```
JS是浏览器的"编程语言"
HTML是静态的，JS让页面动起来
点击 → 数据变化 → 页面更新
```

## 变量与类型

```javascript
// JS有7种基本类型 + 1种复杂类型
// 基本: string, number, boolean, null, undefined, symbol, bigint
// 复杂: object (包括array, function, date等)

// let vs const (不用var)
const PI = 3.14;    // 常量，不能重新赋值
let count = 0;      // 变量，可以改

// 动态类型：变量类型可以变
let x = 42;         // number
x = "hello";        // 变成string← 这在TS里会报错
```

## 闭包（Closure）

```javascript
// 闭包 = "函数 + 它记住的外部变量"
// 这是JS最核心也最反直觉的概念

function createCounter() {
  let count = 0;           // 外部变量
  return function() {      // 返回一个函数
    count++;               // 这个函数"记住"了count
    return count;
  };
}

const counter = createCounter();
counter(); // 1
counter(); // 2
counter(); // 3
// count没有被销毁→ 外部函数执行完了，但内部函数保留了引用
```

## 事件循环（Event Loop）

```javascript
// JS是"单线程"的 → 一次只能做一件事
// 但浏览器需要处理点击/网络请求/动画...

// 解决方案: 事件循环

// 1. 执行主线程代码
// 2. setTimeout/Promise/点击事件 → 放到任务队列
// 3. 主线程执行完 → 检查队列 → 取出下一个执行

console.log("1");
setTimeout(() => console.log("2"), 0);
Promise.resolve().then(() => console.log("3"));
console.log("4");

// 输出: 1, 4, 3, 2
// 解释: 
//   - 同步代码先执行 (1,4)
//   - 微任务先于宏任务 (Promise.then > setTimeout)
//   - 所以3在2前面
```

## DOM操作

```javascript
// DOM = Document Object Model
// 浏览器把HTML解析成一棵树 → JS可以操作这棵树

// 找到元素
const btn = document.getElementById("myButton");
const items = document.querySelectorAll(".item");

// 修改内容
btn.textContent = "点我";
btn.style.color = "red";
btn.classList.add("active");

// 事件监听
btn.addEventListener("click", () => {
  alert("被点击了！");
});
```

## 异步编程

```javascript
// 回调地狱时代（2015前）
fetchData(id, (err, data) => {
  processData(data, (err, result) => {
    saveResult(result, (err) => {
      console.log("done");
    });
  });
});

// Promise时代（ES6）
fetchData(id)
  .then(data => processData(data))
  .then(result => saveResult(result))
  .then(() => console.log("done"))
  .catch(err => console.error(err));

// async/await 时代（ES2017）— 现在的主流
async function handleData() {
  const data = await fetchData(id);
  const result = await processData(data);
  await saveResult(result);
  console.log("done");
}
```

## 今日收获
- 闭包 = 函数记住外部变量（计数器/封装私有状态）
- 事件循环 = 单线程但能处理并发（微任务 > 宏任务）
- DOM = JS控制浏览器的接口
- async/await = 写异步像写同步
