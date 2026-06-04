# Flutter 状态管理：setState → Provider → Riverpod → BLoC

## 一、为什么需要状态管理？

Flutter 是声明式 UI 框架，UI 是状态的函数：`UI = f(state)`。当状态变化时，框架重建 UI。问题在于：

1. **状态是什么**：用户数据、UI 状态、网络状态、路由状态
2. **状态在哪里**：局部？全局？跨页面共享？
3. **谁管理状态**：Widget 自身？父 Widget？专门的 Store？

Flutter 本身只提供了最基础的状态管理——`setState()`。随着应用复杂度增长，我们需要更强大的方案。

---

## 二、setState —— 最基础的状态管理

`setState()` 是 `StatefulWidget` 原生的状态管理方式，适用于 Widget 内部的局部状态。

### 2.1 工作原理

```dart
class CounterWidget extends StatefulWidget {
  @override
  State<CounterWidget> createState() => _CounterWidgetState();
}

class _CounterWidgetState extends State<CounterWidget> {
  int _count = 0;
  
  void _increment() {
    setState(() {
      _count++;
    });
  }
  
  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: _increment,
      child: Text('$_count'),
    );
  }
}
```

### 2.2 适用场景
- Widget 内部的开关状态
- 表单输入状态
- 动画控制状态

### 2.3 局限性
- **状态提升**：当多个 Widget 共享状态时，需将状态提升到公共祖先，导致大量 Prop Drilling
- **无法跨页面**：Widget 树销毁后状态丢失
- **代码耦合**：业务逻辑和 UI 耦合在一起

---

## 三、Provider —— 最流行的入门方案

Provider 是 Google 推荐的初级状态管理方案，本质是对 `InheritedWidget` 的封装。

### 3.1 核心概念

```dart
// 1. 定义状态模型
class CounterModel extends ChangeNotifier {
  int _count = 0;
  int get count => _count;
  
  void increment() {
    _count++;
    notifyListeners(); // 通知监听者重建
  }
}

// 2. 注入状态
void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => CounterModel(),
      child: MyApp(),
    ),
  );
}

// 3. 消费状态
class CounterWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final counter = context.watch<CounterModel>();
    return Text('${counter.count}');
  }
}
```

### 3.2 Provider 类型

| Provider 类型 | 用途 |
|--------------|------|
| `Provider` | 提供不可变对象 |
| `ChangeNotifierProvider` | 提供 ChangeNotifier 监听变化 |
| `StreamProvider` | 提供 Stream 数据流 |
| `FutureProvider` | 提供一次性异步数据 |
| `MultiProvider` | 组合多个 Provider |

### 3.3 内部原理

`Provider` 底层使用 `InheritedWidget`。`context.watch<T>()` 内部调用 `context.dependOnInheritedWidgetOfExactType<T>()`，建立依赖关系。

```dart
// Provider 的简化实现
class Provider<T> extends InheritedWidget {
  final T value;
  final Create<T> create;
  
  static T of<T>(BuildContext context, {bool listen = true}) {
    if (listen) {
      return context.dependOnInheritedWidgetOfExactType<_Provider<T>>()!.value;
    } else {
      return context.findAncestorWidgetOfExactType<_Provider<T>>()!.value;
    }
  }
}
```

### 3.4 Provider 的不足
- **编译不安全**：`context.read<T>()` 在运行时推断类型
- **Context 依赖**：必须持有 BuildContext 才能访问状态
- **继承耦合**：`ChangeNotifier` 混入了框架代码
- **无法多实例**：同一类型只能有一个 Provider 实例

---

## 四、Riverpod —— Provider 的进化版

Riverpod 由 Provider 原作者设计，解决了其所有痛点。

### 4.1 核心特性

```dart
// 1. 定义 Provider——全局、编译安全
final counterProvider = StateNotifierProvider<CounterNotifier, int>((ref) {
  return CounterNotifier();
});

class CounterNotifier extends StateNotifier<int> {
  CounterNotifier() : super(0);
  
  void increment() => state++;
}

// 2. 消费
class CounterWidget extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final count = ref.watch(counterProvider);
    return Text('$count');
  }
}
```

### 4.2 Riverpod vs Provider 对比

| 特性 | Provider | Riverpod |
|------|----------|----------|
| 编译安全 | ❌ 运行时 | ✅ 编译时 |
| 脱离 Context | ❌ | ✅ `ref.read()` 可用在任何地方 |
| 多实例 | ❌ | ✅ `family` 修饰符 |
| 自动释放 | ❌ 手动处理 | ✅ `autoDispose` |
| 测试性 | 需 WidgetTester | ✅ 纯 Dart 测试 |
| Provider 依赖 | 嵌套 | ✅ `ref.watch(otherProvider)` |

### 4.3 Provider 修饰符

```dart
// 参数化 Provider（多实例）
final userProvider = FutureProvider.family<User, String>((ref, id) {
  return fetchUser(id);
});

// 自动释放
final cacheProvider = FutureProvider.autoDispose((ref) {
  final dispose = ref.onDispose(() => print('cleaned up'));
  return fetchData();
});
```

### 4.4 适用场景
- 中等复杂度应用
- 需要良好测试性的项目
- 需要脱离 BuildContext 访问状态

---

## 五、BLoC —— 企业级状态管理

BLoC（Business Logic Component）通过 Stream 分离业务逻辑和 UI。

### 5.1 核心概念

```dart
// 1. 定义事件
abstract class CounterEvent {}
class Increment extends CounterEvent {}

// 2. 定义状态
class CounterState {
  final int count;
  CounterState(this.count);
}

// 3. 实现 BLoC
class CounterBloc extends Bloc<CounterEvent, CounterState> {
  CounterBloc() : super(CounterState(0)) {
    on<Increment>((event, emit) {
      emit(CounterState(state.count + 1));
    });
  }
}

// 4. UI 使用
BlocProvider(
  create: (_) => CounterBloc(),
  child: BlocBuilder<CounterBloc, CounterState>(
    builder: (context, state) {
      return Text('${state.count}');
    },
  ),
)
```

### 5.2 BLoC 的优势
- **可测试性极高**：BLoC 是纯 Dart 类，不依赖 Flutter
- **事件驱动**：清晰的单向数据流
- **可回溯**：记录所有事件和状态，方便调试
- **团队规范**：架构强制分离关注点

### 5.3 BLoC 复杂度

```dart
// 实际项目中 BLoC 的复杂度
class LoginBloc extends Bloc<LoginEvent, LoginState> {
  final AuthRepository authRepo;
  
  LoginBloc(this.authRepo) : super(LoginInitial()) {
    on<LoginSubmitted>(_onLoginSubmitted);
  }
  
  Future<void> _onLoginSubmitted(
    LoginSubmitted event,
    Emitter<LoginState> emit,
  ) async {
    emit(LoginLoading());
    try {
      final user = await authRepo.login(event.username, event.password);
      emit(LoginSuccess(user));
    } catch (e) {
      emit(LoginFailure(e.toString()));
    }
  }
}

// 每个业务功能需要：
// - 1 个 Event 文件
// - 1 个 State 文件
// - 1 个 BLoC 文件
// - 测试文件
```

### 5.4 适用场景
- 大型企业级应用
- 需要严格的可回溯调试
- 团队有明确的架构规范
- 需要跨平台复用业务逻辑

---

## 六、方案对比总结

| 维度 | setState | Provider | Riverpod | BLoC |
|------|----------|----------|----------|------|
| 学习曲线 | ★☆☆☆☆ | ★★★☆☆ | ★★★★☆ | ★★★★★ |
| 代码量 | 少 | 中等 | 中等 | 多 |
| 可测试性 | 低 | 中等 | 高 | 最高 |
| Context 依赖 | 需要 | 需要 | 不需要 | 部分需要 |
| 类型安全 | 天然 | 运行时 | 编译时 | 编译时 |
| 调试工具 | Flutter DevTools | DevTools | Riverpod Lint | Bloc DevTools |
| 适合规模 | 单页 | 小-中 | 中 | 大-超大 |
| 性能 | 最优 | 良好 | 良好 | 依赖 Stream |

---

## 七、选择策略

### 7.1 决策树

```
应用是否需要共享状态？
├── 否 → setState 就够用
└── 是 → 应用规模多大？
    ├── 小（1-3 个页面）→ Provider
    ├── 中（4-10 个页面）→ Riverpod
    └── 大（10+ 页面，多团队）→ BLoC
```

### 7.2 混合使用
实际项目可以混合多种方案：
- 全局共享状态用 Riverpod/BLoC
- 页面内局部状态用 setState
- 表单状态用 Provider 或 setState
- 网络请求状态用 FutureProvider/StreamBuilder

### 7.3 常见陷阱
1. **过度工程**：简单应用使用 BLoC 增加不必要的复杂度
2. **滥用全局状态**：能局部就不要全局
3. **忽视 dispose**：Stream 和 ChangeNotifier 必须正确释放
4. **在 build 中创建 Provider**：每次重建都创建新实例

---

## 八、总结

- **setState** 最基础、最简单，适合 Widget 内部状态
- **Provider** 封装了 InheritedWidget，适合入门和小型项目
- **Riverpod** 解决了 Provider 的痛点，编译安全、无 Context 依赖
- **BLoC** 是企业级方案，可测试性最强，但代码量也最大
- 选择方案时考虑：团队能力、应用规模、可测试性需求
- 不存在银弹，可以在同一项目中混合使用不同方案

状态管理没有绝对的好坏，只有适合不适合。下一课将探讨 Flutter 与原生平台的通信机制。
