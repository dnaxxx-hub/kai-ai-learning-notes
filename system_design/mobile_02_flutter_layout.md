# Flutter 布局系统：Constraints-go-down/Sizes-go-up

## 一、布局的核心原则

Flutter 布局系统遵循一个黄金法则：**Constraints go down, Sizes go up, Parent sets position.**

这句话的含义是：
1. 父节点向下传递约束（Constraints）给子节点
2. 子节点在约束范围内计算自己的尺寸并向上报告
3. 父节点确定子节点的位置

这个机制确保了布局的确定性，不会出现 CSS 中那种"子节点撑大父节点"的不确定性。

### 1.1 Constraints 对象

```dart
class BoxConstraints extends Constraints {
  final double minWidth;
  final double maxWidth;
  final double minHeight;
  final double maxHeight;
  
  // 常用构造函数
  BoxConstraints.tight(Size size);      // min == max
  BoxConstraints.loose(Size size);      // min = 0, max = size
  BoxConstraints.expand();              // 尽可能大
}
```

- **tight**：`min == max`，子节点没有选择余地
- **loose**：`min = 0`，子节点可以自由选择尺寸
- **expand**：在所有可用空间中扩展

---

## 二、常用布局 Widget 详解

### 2.1 Container

`Container` 是组合型 Widget，内部创建了一系列 Widget 来满足配置：

```
Container → ConstrainedBox → Align（或 Center）→ Padding → decoratedBox → child
```

```dart
Container(
  width: 100,    // 实际创建 tight width constraint
  height: 100,   // 实际创建 tight height constraint
  padding: EdgeInsets.all(8),
  margin: EdgeInsets.all(8),
  color: Colors.blue,  // 通过 decoration 实现
  child: Text('Hello'),
)
```

**注意**：`Container` 在 `width` 和 `height` 未设置时表现不同——如果父节点传递 tight 约束则充满，否则尽可能小。

### 2.2 Row 和 Column（Flex 布局）

`Row` 和 `Column` 都是 `Flex` 的子类，区别在于主轴方向。

#### 布局流程
1. 先布局不受 `Flexible` 包裹的"非弹性"子节点
2. 计算剩余空间
3. 按 `flex` 系数分配剩余空间给弹性子节点
4. 在交叉轴上对齐

```dart
Row(
  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
  crossAxisAlignment: CrossAxisAlignment.center,
  children: [
    Text('固定宽度'),       // 先布局，按 intrinsic 宽度
    Expanded(              // flex: 1，占据剩余空间
      flex: 2,
      child: Text('弹性'),
    ),
  ],
)
```

#### MainAxisAlignment
- `start`：从主轴起点排列
- `end`：从主轴终点排列
- `center`：居中
- `spaceBetween`：首尾对齐，子节点间距相等
- `spaceAround`：子节点间间距相等，首尾间距减半
- `spaceEvenly`：所有间距相等

### 2.3 Stack

`Stack` 允许子节点重叠，通过 `Positioned` 控制位置。

```dart
Stack(
  alignment: Alignment.center,
  clipBehavior: Clip.none,
  children: [
    Container(width: 200, height: 200, color: Colors.red),
    Positioned(
      top: 10,
      right: 10,
      child: Icon(Icons.star),
    ),
  ],
)
```

**布局规则**：
- `Positioned` 子节点：根据 top/right/bottom/left 定位
- 非 Positioned 子节点：根据 Stack.alignment 对齐
- fit 属性控制非 Positioned 子节点是否延伸

### 2.4 Expanded vs Flexible

| 特性 | Expanded | Flexible |
|------|----------|----------|
| 强制子节点填满分配空间 | 是 | 否 |
| 子节点可小于分配空间 | 否 | 是 |
| 内部 TightFit | `tight` | `loose` |

```dart
Row(
  children: [
    Flexible(
      flex: 1,
      child: Container(color: Colors.red),
    ),
    Expanded(
      flex: 2,
      child: Container(color: Colors.blue),
    ),
  ],
)
```

`Expanded` 内部创建了 `Flexible(fit: FlexFit.tight)`，而 `Flexible` 默认为 `FlexFit.loose`。

---

## 三、CustomMultiChildLayout

当标准布局无法满足需求时，`CustomMultiChildLayout` 提供了完全自定义的多子节点布局能力。

### 3.1 工作原理

它需要两个要素：
1. **MultiChildLayoutDelegate**：自定义布局逻辑
2. **LayoutId**：为每个子节点指定 ID

```dart
class MyLayoutDelegate extends MultiChildLayoutDelegate {
  @override
  void performLayout(Size size) {
    // 通过 LayoutId 定位子节点
    if (hasChild('header')) {
      final headerSize = layoutChild('header', BoxConstraints.loose(size));
      positionChild('header', Offset(0, 0));
    }
    
    if (hasChild('body')) {
      final bodySize = layoutChild('body', BoxConstraints(
        maxWidth: size.width,
        maxHeight: size.height - 100,
      ));
      positionChild('body', Offset(0, 100));
    }
  }
  
  @override
  bool shouldRelayout(MyLayoutDelegate oldDelegate) => false;
}

// 使用
CustomMultiChildLayout(
  delegate: MyLayoutDelegate(),
  children: [
    LayoutId(id: 'header', child: HeaderWidget()),
    LayoutId(id: 'body', child: BodyWidget()),
  ],
)
```

### 3.2 典型应用场景
- 浮动按钮（FAB 定位）
- 自定义对话气泡
- 套娃布局（子节点围绕中心排列）
- 瀑布流

---

## 四、布局过程详解

### 4.1 布局剪枝
Flutter 的布局是深度优先的。当一个父节点布局完成，子节点才开始布局。但并非所有节点都需要重新布局：

```dart
class RenderObject {
  bool _needsLayout = true;
  
  void markNeedsLayout() {
    if (!_needsLayout) {
      _needsLayout = true;
      parent?.markNeedsLayout(); // 向上传递
    }
  }
}
```

当某个节点标记为 `_needsLayout`，其所有父节点也会被标记，但兄弟节点不受影响。

### 4.2 LayoutBuilder

`LayoutBuilder` 根据父节点传递的约束动态构建 Widget：

```dart
LayoutBuilder(
  builder: (context, constraints) {
    if (constraints.maxWidth < 600) {
      return MobileView();
    } else {
      return DesktopView();
    }
  },
)
```

**注意**：`LayoutBuilder` 在每次约束变化时重建，不能在其中执行耗时操作。

### 4.3 IntrinsicWidth / IntrinsicHeight

有时 Widget 需要根据子节点的"固有尺寸"来确定自己的尺寸，而不是由父节点约束决定：

```dart
IntrinsicHeight(
  child: Row(
    children: [
      Text('短文本'),
      Text('这是一段较长的文本\n有换行'),
    ],
  ),
)
```

**性能警告**：`IntrinsicHeight` 和 `IntrinsicWidth` 需要两次布局，避免在性能敏感的位置使用。

---

## 五、布局约束传递的经典案例

### 案例 1：无限宽度的误区
```dart
Row(
  children: [
    Text('Hello'),
    ListView(), // 错误！ListView 需要有限的高度
  ],
)
```
`Row` 给子节点的垂直约束是 `maxHeight = 0` 到 `parentHeight`，但 `ListView` 要求有限高度。解决方案是用 `Expanded` 包裹，或使用 `SizedBox` 限制高度。

### 案例 2：Column 中的 unbounded height
```dart
Column(
  children: [
    Expanded(child: Text('A')),
    Expanded(child: Text('B')),
    ListView(), // 同样可能出错
  ],
)
```

### 案例 3：Center 的行为
```dart
Center(
  child: Container(color: Colors.red), // 这个 Container 大小是 0×0
)
```
`Center` 传递 loose 约束（0 到可用空间），而 `Container` 没有子节点也没有固定尺寸，于是选择了最小尺寸 `0×0`。解决方案：给 Container 添加 `width` 和 `height`。

---

## 六、布局性能优化

### 6.1 避免不必要的布局
- 使用 `const` Widget
- 使用 `RepaintBoundary` 隔离重绘
- 避免在列表中使用 `IntrinsicHeight`

### 6.2 Overdraw 检测
Flutter 提供性能图层来检测布局与绘制问题：
- 打开 Performance Overlay（`showPerformanceOverlay: true`）
- 检查格子层：红/绿色格子指示是否超时
- 使用 Timeline 工具分析布局耗时

### 6.3 减少布局嵌套
- 使用 `Column` + `Row` 替代多个嵌套的 `Padding` + `Align`
- 使用 `Container` 的 `padding` 属性而非额外套 `Padding`
- 合并不必要的 Widget 层级

---

## 七、总结

- Flutter 布局是**单次传递**的：父节点决定约束，子节点决定尺寸
- `Constraints go down, Sizes go up, Parent sets position` 是铁律
- `Row/Column/Flex` 是最常用的布局 Widget，理解 `Expanded` vs `Flexible` 的区别至关重要
- `Stack` 提供重叠布局，`Positioned` 精准控制位置
- `CustomMultiChildLayout` 提供无限自定义空间
- 使用 `LayoutBuilder` 做响应式布局
- 避免 `IntrinsicHeight/Width` 在性能关键路径上
- 理解每种布局 Widget 传递的约束类型（tight/loose/expand）是避免布局错误的关键

下一课将探讨 Flutter 的状态管理：从 setState 到 BLoC 的演化路径。
