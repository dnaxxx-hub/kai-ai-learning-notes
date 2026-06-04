# 课时4：图优化——让计算图更聪明地运行

## 概述

深度学习编译器（如 XLA、TorchInductor、TVM）的核心竞争力在于**图优化**——在不改变语义的前提下，对计算图进行等价变换，以提高执行效率。图优化策略多样，从简单的常量折叠到复杂的子图替换（JIT 编译）。本课深入几种核心图优化技术。

## 核心概念

### 1. 操作符消融（Operator Elimination）与代数化简

**操作符消融**是指删除对最终结果没有影响的计算节点。深度学习模型训练完成后，推理阶段可以进行大量消融。

**常见的消融模式**：

```python
# 图优化器：应用多种等价变换

class GraphOptimizer:
    """计算图优化器的简化实现"""
    
    def optimize(self, graph):
        graph = self.constant_folding(graph)
        graph = self.dead_code_elimination(graph)
        graph = self.algebraic_simplification(graph)
        graph = self.identity_elimination(graph)
        return graph
    
    def identity_elimination(self, graph):
        """
        消融"不做任何事"的操作：
        x + 0     →  x
        x * 1     →  x
        x * 0     →  zeros_like(x)
        relu(relu(x))  →  relu(x)  (幂等性)
        """
        for node in graph.nodes:
            if node.op == 'add' and is_constant_zero(node.inputs[1]):
                node.replace_with(node.inputs[0])
            elif node.op == 'mul' and is_constant_one(node.inputs[1]):
                node.replace_with(node.inputs[0])
            elif node.op == 'mul' and is_constant_zero(node.inputs[1]):
                node.replace_with(ConstantNode(0))
        return graph
    
    def algebraic_simplification(self, graph):
        """
        代数化简：
        neg(neg(x))     →  x
        (a + b) + c     →  a + (b + c)  (reassoc 以暴露常量折叠)
        x / c1 / c2     →  x / (c1 * c2)
        """
        for node in graph.nodes:
            # 双重取反消融
            if node.op == 'neg' and node.inputs[0].op == 'neg':
                node.replace_with(node.inputs[0].inputs[0])
            
            # 除以常量合并
            if node.op == 'div' and is_constant(node.inputs[1]):
                prev = node.inputs[0]
                if prev.op == 'div' and is_constant(prev.inputs[1]):
                    # x / c1 / c2 = x / (c1 * c2)
                    new_const = prev.inputs[1].value * node.inputs[1].value
                    node.replace_with(DivNode(prev.inputs[0], ConstantNode(new_const)))
        return graph
```

**操作符消融的实际价值**：

| 消融类型 | 示例 | 节省的运算 |
|----------|------|-----------|
| Add with zero | x + 0 | 1 次加法 |
| Mul with one | x * 1 | 1 次乘法 |
| Nop transpose | transpose(x, [0,1,2,3]) | 无意义的重排 |
| Neg-of-neg | -(-x) | 无意义 |
| Cast to same | float32(float32(x)) | 无意义 |

### 2. 常量折叠（Constant Folding）

**常量折叠**是在编译期预计算所有能确定结果的子表达式。这是图优化最基础也最有效的技术之一。

```python
class ConstantFolder:
    """
    常量折叠：在编译期计算出所有常量子表达式的值。
    消除运行时的计算开销。
    """
    def fold(self, graph):
        changed = True
        while changed:
            changed = False
            for node in list(graph.nodes):
                if self._is_foldable(node):
                    # 在编译期计算该节点的值
                    result = self._evaluate(node)
                    # 将节点替换为常量
                    graph.replace_node(node, ConstantNode(result))
                    changed = True
                    print(f"  Folded {node.op} → constant {result}")
        return graph
    
    def _is_foldable(self, node):
        """判断节点是否可以折叠"""
        # 所有输入都必须是常量
        if not all(isinstance(inp, ConstantNode) for inp in node.inputs):
            return False
        # 某些操作有副作用，不能折叠
        if node.op in {'randn', 'dropout', 'batch_norm'}:
            return False
        # shape 相关的操作（如形状推断可能在编译期不确定）
        # 但大多数情况下，如果输入是常量，可以折叠
        return True
    
    def _evaluate(self, node):
        """在编译期执行该操作"""
        const_inputs = [inp.value for inp in node.inputs]
        
        # Python 兜底执行（生产框架使用 LLVM JIT 或 Eigen 优化实现）
        if node.op == 'add':
            return const_inputs[0] + const_inputs[1]
        elif node.op == 'mul':
            return const_inputs[0] * const_inputs[1]
        elif node.op == 'matmul':
            return np.matmul(*const_inputs)
        elif node.op == 'concat':
            return np.concatenate(const_inputs, axis=node.attrs['axis'])
        # ... 更多操作映射
        raise NotImplementedError(f"Unknown op: {node.op}")

# 常量折叠示例
# 原始计算图：
#   w = [0.5, 0.3]         # 常量
#   b = [0.1, -0.2]        # 常量
#   x = Input("features")
#   temp = w * x            # 变量
#   scale = 0.9 + 0.1       # 常量可折叠！
#   y = temp * scale        # 折叠后：y = temp * 1.0 → y = temp

# 折叠后：
#   x = Input("features")
#   y = w * x               # 省去了 0.9 + 0.1 的计算
```

### 3. 死代码消除（Dead Code Elimination, DCE）

**死代码消除**是指删除对输出完全没有影响的节点。死代码可能来源于：
1. 模型修改后未清理的遗留节点
2. 无用分支的结果
3. 编译期某些优化后暴露的冗余节点

```python
class DeadCodeEliminator:
    """
    死代码消除：标记-清理算法。
    只保留从输出反向可达的节点。
    """
    def eliminate(self, graph):
        # 阶段1：标记（从输出反向传播）
        marked = set()
        def mark(node):
            if node in marked:
                return
            marked.add(node)
            for input_node in node.inputs:
                mark(input_node)
        
        # 从所有输出节点开始标记
        for output in graph.outputs:
            mark(output)
        
        # 阶段2：清理（移除未标记的节点）
        eliminated = []
        for node in list(graph.nodes):
            if node not in marked:
                eliminated.append(node)
                graph.remove_node(node)
        
        if eliminated:
            print(f"Eliminated {len(eliminated)} dead nodes:")
            for n in eliminated:
                print(f"  - {n.op}({n.name})")
        
        return graph

# DCE 示例场景
def dead_code_example():
    """
    场景：训练模式下计算的辅助损失，推理时不需要。
    """
    # 前向计算图（训练）
    #     input → conv1 → relu → conv2 → relu → output
    #          ↘                            ↗
    #            auxiliary_loss (推理时不需要)
    
    # DCE 后（推理图）：
    #     input → conv1 → relu → conv2 → relu → output
    #   auxiliary_loss 及其相关节点被移除
    
    # 另一个常见例子：
    #   for i in range(100):
    #       x = relu(x)
    #       log_x = log(x)    # 从未被使用的节点
    #   return x              # 只有 x 被使用
    pass
```

### 4. 子图替换与 JIT 编译

**子图替换**（Subgraph Substitution）是最强大的图优化技术。它模式匹配计算图中的固定模式（pattern），用等价的、更高效的子图替换。

```python
# 子图替换系统：模式匹配 + 等价变换

class SubgraphPattern:
    """定义一个可匹配的子图模式"""
    def __init__(self, pattern_fn):
        self.pattern_fn = pattern_fn
    
    def matches(self, graph, anchor_node):
        """检查 anchor_node 是否匹配此模式"""
        return self.pattern_fn(graph, anchor_node)

class SubgraphReplacer:
    """
    子图替换引擎。
    通过模式匹配发现可优化的子图模式，替换为高效实现。
    """
    def __init__(self):
        self.patterns = []
    
    def register_pattern(self, pattern, replacement_fn, name=""):
        """注册一个替换模式"""
        self.patterns.append((pattern, replacement_fn, name))
    
    def apply(self, graph):
        """对所有节点应用子图替换"""
        applied = 0
        for node in list(graph.nodes):
            for pattern, replacement, name in self.patterns:
                if pattern.matches(graph, node):
                    replacement(graph, node)
                    applied += 1
                    print(f"  Applied: {name}")
        return applied
    
    def register_common_patterns(self):
        """注册常见的深度学习图优化模式"""
        
        # Pattern: BatchNorm + ReLU 融合
        pattern_bn_relu = SubgraphPattern(
            lambda g, n: n.op == 'relu' and n.inputs[0].op == 'batch_norm'
        )
        def replace_bn_relu(graph, node):
            bn_node = node.inputs[0]
            fused_kernel = FusedOp('batch_norm_relu', 
                                    bn_node.inputs, node.attrs)
            graph.replace_subgraph([bn_node, node], fused_kernel)
        
        self.register_pattern(pattern_bn_relu, replace_bn_relu, 
                              "fuse_bn_relu")
        
        # Pattern: Conv + Bias + ReLU 融合
        pattern_conv_bias_relu = SubgraphPattern(
            lambda g, n: (
                n.op == 'relu' and 
                n.inputs[0].op == 'add' and
                n.inputs[0].inputs[0].op == 'conv'
            )
        )
        def replace_conv_bias_relu(graph, node):
            add_node = node.inputs[0]
            conv_node = add_node.inputs[0]
            fused_kernel = FusedOp('conv_bias_relu',
                                    conv_node.inputs + [add_node.inputs[1]],
                                    {**conv_node.attrs, **node.attrs})
            graph.replace_subgraph([conv_node, add_node, node], fused_kernel)
        
        self.register_pattern(pattern_conv_bias_relu, replace_conv_bias_relu,
                              "fuse_conv_bias_relu")
        
        # Pattern: MatMul + Add (Bias) 融合
        pattern_mm_add = SubgraphPattern(
            lambda g, n: n.op == 'add' and n.inputs[0].op == 'matmul'
        )
        def replace_mm_add(graph, node):
            matmul_node = node.inputs[0]
            bias_node = node.inputs[1]
            fused = FusedOp('matmul_add',
                            matmul_node.inputs + [bias_node],
                            matmul_node.attrs)
            graph.replace_subgraph([matmul_node, node], fused)
        
        self.register_pattern(pattern_mm_add, replace_mm_add,
                              "fuse_matmul_add")
```

**JIT 编译集成**：当子图替换模式太复杂或不确定时，可以使用 JIT（Just-In-Time）编译即时生成优化代码：

```python
class JITSubgraphCompiler:
    """
    JIT 子图编译：将匹配的子图编译为高效的融合 kernel。
    典型代表：PyTorch JIT (TorchScript) + NNC/TorchInductor
    """
    def __init__(self):
        self.cache = {}  # subgraph_signature → compiled_function
    
    def compile_subgraph(self, subgraph):
        """将子图编译为融合 kernel（Triton/LLVM）"""
        signature = self._compute_signature(subgraph)
        
        if signature in self.cache:
            return self.cache[signature]
        
        # 1. 分析子图的张量形状和数据类型
        # 2. 生成融合的 Triton kernel 或 LLVM IR
        # 3. 编译为可调用对象
        
        compiled = self._emit_and_compile(subgraph)
        self.cache[signature] = compiled
        return compiled
    
    def _emit_and_compile(self, subgraph):
        """
        代码生成示意：将子图转换为高效代码。
        实际上可能是 Triton 代码、CUDA 代码或 LLVM IR。
        """
        # 生成简单循环代码（伪代码）
        ops = []
        for node in subgraph.nodes:
            if node.op == 'mul':
                ops.append(f"out[i] = a[i] * b[i]")
            elif node.op == 'add':
                ops.append(f"out[i] = a[i] + b[i]")
            elif node.op == 'relu':
                ops.append(f"out[i] = max(0, out[i])")
        
        # 生成单个融合 kernel
        fused_code = f"""
        __global__ void fused_kernel(float* input, float* output, int n) {{
            int i = blockIdx.x * blockDim.x + threadIdx.x;
            if (i < n) {{
                {ops[0]}
                for op in ops[1:]:
                    {op}
            }}
        }}
        """
        
        # 编译并返回（实际使用 NVRTC 或 TVM）
        return CompiledFunction(fused_code)

# 使用示例
@torch.compile  # PyTorch 2.0+ 的 JIT 子图编译
def compiled_model(x, w, b):
    """@torch.compile 会自动进行子图替换和融合"""
    return torch.relu(x @ w + b)
```

## 实用技巧

### 图优化 Pass 的顺序依赖

```python
class OptimizationPipeline:
    """
    图优化 Pass 的执行管线。
    不同 Pass 之间有依赖关系，顺序影响最终效果。
    """
    def __init__(self):
        self.passes = []
    
    def add_pass(self, name, pass_fn):
        self.passes.append((name, pass_fn))
    
    def run(self, graph):
        """执行所有优化 Pass"""
        for name, pass_fn in self.passes:
            print(f"Running pass: {name}")
            pass_fn(graph)
            print(f"  Graph: {len(graph.nodes)} nodes")
        return graph

# 推荐的 Pass 执行顺序
def build_optimization_pipeline():
    pipeline = OptimizationPipeline()
    
    # 1. 代数化简（暴露更多常量折叠机会）
    pipeline.add_pass("algebraic_simplification", 
                       AlgebraicSimplifier().simplify)
    
    # 2. 常量折叠（需要先有代数化简暴露常量）
    pipeline.add_pass("constant_folding", 
                       ConstantFolder().fold)
    
    # 3. 死代码消除（常量折叠后可能出现死代码）
    pipeline.add_pass("dead_code_elimination",
                       DeadCodeEliminator().eliminate)
    
    # 4. 子图替换（JIT 编译）
    pipeline.add_pass("subgraph_replacement",
                       SubgraphReplacer().apply)
    
    return pipeline
```

## 延伸阅读

- [The Deep Learning Compiler: A Comprehensive Survey (Li et al., 2020)](https://arxiv.org/abs/2002.03794)
- [XLA: Optimizing Compiler for Machine Learning](https://www.tensorflow.org/xla)
- [PyTorch TorchDynamo and TorchInductor](https://pytorch.org/docs/stable/torch.compiler.html)

## 关键总结

1. **操作符消融** 删除等价恒等操作（x+0, x\*1 等），减少无意义计算
2. **常量折叠** 在编译期预计算常量子表达式，消除运行时开销
3. **死代码消除** 使用标记-清理算法移除从未被使用的节点
4. **代数化简** 通过交换律和结合律重排计算顺序，暴露更多优化机会
5. **子图替换 + JIT** 是高级优化手段，模式匹配后生成融合 kernel
6. **Pass 顺序** 至关重要：代数化简 → 常量折叠 → DCE → 子图替换
