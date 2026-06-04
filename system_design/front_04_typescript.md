# TypeScript：JS的"带上枷锁跳舞"

> 日期：2026-05-07 20:33 | 课程：前端路线 Phase 2-2
> 目标：理解"为什么要给JS加类型"

## 核心问题

```javascript
// JS的问题: 太自由了

function add(a, b) {
  return a + b;
}

add(1, 2)         // 3 ✅
add("1", "2")     // "12" ❌ 字符串拼接了
add([], {})       // "[object Object]" ❌ 完全离谱

// JS只有在运行时才知道出错了
// TS: 在写代码时就发现这些问题
```

## TypeScript做了什么

```typescript
// TS = JS + 类型系统

// 明确参数类型
function add(a: number, b: number): number {
  return a + b;
}

add(1, 2);     // ✅ 编译通过
add("1", "2"); // ❌ 编辑器就报错：类型不对
```

## 核心特性

### 1. 基础类型

```typescript
let name: string = "kai";
let age: number = 28;
let isActive: boolean = true;
let items: string[] = ["a", "b"];

// 联合类型
let id: string | number;
id = "abc";   // ✅
id = 123;     // ✅
id = true;    // ❌ boolean不能赋给string|number
```

### 2. Interface（接口）

```typescript
interface User {
  id: number;
  name: string;
  email: string;
  avatar?: string;      // 可选属性
  readonly createdAt: Date;  // 只读
}

const user: User = {
  id: 1,
  name: "羽",
  email: "yu@example.com",
  createdAt: new Date(),
};
```

### 3. 泛型

```typescript
// 不用any，用泛型保持类型关系

function firstElement<T>(arr: T[]): T | undefined {
  return arr[0];
}

const num = firstElement([1, 2, 3]);    // num: number
const str = firstElement(["a", "b"]);   // str: string
// 类型被保留下来了
```

### 4. 工具类型

```typescript
interface Todo {
  title: string;
  description: string;
  completed: boolean;
}

type PartialTodo = Partial<Todo>;
// { title?: string; description?: string; completed?: boolean; }

type PickedTodo = Pick<Todo, "title" | "completed">;
// { title: string; completed: boolean; }

type OmittedTodo = Omit<Todo, "description">;
// { title: string; completed: boolean; }
```

## 为什么前端都用TS

```
1. 编译时报错（运行时更少bug）
2. IDE智能提示
3. 代码更"可读"（类型=文档）
4. 重构更安全（改接口 → 所有用到的地方都报错）
5. 生态已经全面TS化（React/Vue/Next.js...）

6. 唯一的"缺点": 要多写一点类型
   但写类型节省的debug时间远大于写类型的时间
```

## 今日收获
- TS = JS + 类型系统
- 基础：number/string/boolean 和 interface/type
- 泛型 = 保持类型关系（比any安全很多倍）
- 工具类型 = Partial/Pick/Omit 很常用
- **现代前端项目几乎100%用TS**（React/Next/Vue/Angular）
