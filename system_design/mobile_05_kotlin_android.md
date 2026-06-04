# Kotlin Android 开发：基础、Jetpack Compose 与生命周期

## 一、Kotlin 语言基础回顾

### 1.1 为什么是 Kotlin？
2017 年 Google 宣布 Kotlin 成为 Android 官方语言，2019 年 Kotlin-first。相比 Java，Kotlin 的现代语法大幅减少了样板代码。

### 1.2 核心特性

```kotlin
// 空安全
var name: String? = null  // 可为空
val length = name?.length ?: 0  // 安全调用 + Elvis 操作符

// 数据类
data class User(val id: Long, val name: String, val email: String)

// 扩展函数
fun Context.showToast(message: String) {
    Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
}

// 协程
viewModelScope.launch {
    val result = withContext(Dispatchers.IO) { fetchData() }
    updateUI(result)
}

// sealed class（受限密封类）
sealed class UiState<out T> {
    object Loading : UiState<Nothing>()
    data class Success<T>(val data: T) : UiState<T>()
    data class Error(val message: String) : UiState<Nothing>()
}
```

### 1.3 Kotlin 协程基础
协程是 Kotlin 异步编程的核心，被 Jetpack 全线支持：

```kotlin
// 协程构建器
GlobalScope.launch { }      // 启动新协程
viewModelScope.launch { }   // ViewModel 生命周期绑定
lifecycleScope.launch { }   // Activity/Fragment 生命周期绑定

// 调度器
Dispatchers.Main    // 主线程（UI）
Dispatchers.IO      // IO 线程（网络、文件）
Dispatchers.Default // CPU 密集型
```

---

## 二、Jetpack Compose 声明式 UI

### 2.1 Compose vs View 系统

| 维度 | View 系统 | Jetpack Compose |
|------|-----------|-----------------|
| UI 范式 | 命令式（操作 View 实例） | 声明式（UI = f(state)） |
| 布局 | XML + 代码 | 纯 Kotlin 代码 |
| 数据绑定 | DataBinding/ViewBinding | State + recomposition |
| 列表 | RecyclerView + Adapter | LazyColumn |
| 动画 | Animator/Animation | animate*AsState |
| 学习曲线 | 熟悉 | 全新范式 |

### 2.2 Compose 核心概念

```kotlin
@Composable
fun Greeting(name: String) {
    var count by remember { mutableStateOf(0) }
    
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Text("Hello, $name!")
        Text("Count: $count")
        
        Button(onClick = { count++ }) {
            Text("Increment")
        }
    }
}
```

#### 关键概念
- **@Composable**：标记函数为可组合，只能在 Composable 作用域调用
- **remember**：在重组时保持状态
- **mutableStateOf**：创建可观察状态
- **recomposition**：状态变化时自动重新执行 Composable 函数

### 2.3 Compose 布局

```kotlin
@Composable
fun ProfileCard(user: User) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        elevation = 4.dp
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            AsyncImage(
                model = user.avatarUrl,
                contentDescription = "Avatar",
                modifier = Modifier.size(48.dp)
            )
            Spacer(modifier = Modifier.width(16.dp))
            Column {
                Text(user.name, style = MaterialTheme.typography.h6)
                Text(user.email, style = MaterialTheme.typography.body2)
            }
        }
    }
}
```

### 2.4 Compose 中的 Side Effect

```kotlin
@Composable
fun LifecycleAwareScreen(viewModel: MyViewModel) {
    // LaunchedEffect：进入 Composition 时执行，离开时取消
    LaunchedEffect(Unit) {
        viewModel.loadData()
    }
    
    // DisposableEffect：需要清理的副作用
    DisposableEffect(Unit) {
        val observer = LifecycleEventObserver { _, event -> ... }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    
    // rememberCoroutineScope：在 Composable 外启动协程
    val scope = rememberCoroutineScope()
    Button(onClick = { scope.launch { viewModel.refresh() } }) {
        Text("Refresh")
    }
}
```

---

## 三、Activity 与 Fragment 的生命周期

### 3.1 Activity 生命周期

```
onCreate() → onStart() → onResume() → [Running] 
    → onPause() → onStop() → onDestroy()
              ↕ onRestart()
```

```kotlin
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MyAppTheme {
                Surface {
                    MainScreen()
                }
            }
        }
    }
}
```

### 3.2 Fragment 生命周期

Fragment 的生命周期比 Activity 更复杂，因为它关联 Activity 的生命周期。

```
onAttach() → onCreate() → onCreateView() → onViewCreated() 
→ onStart() → onResume() → [Running] 
→ onPause() → onStop() → onDestroyView() → onDestroy() → onDetach()
```

```kotlin
class MyFragment : Fragment() {
    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        return ComposeView(requireContext()).apply {
            setContent {
                MyScreen()
            }
        }
    }
}
```

### 3.3 生命周期感知组件

```kotlin
// LifecycleObserver（传统方式）
class MyObserver(private val callback: () -> Unit) : DefaultLifecycleObserver {
    override fun onResume(owner: LifecycleOwner) {
        callback()
    }
}

// 通过 lifecycleScope（现代方式）
class MyActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        lifecycleScope.launch {
            lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
                // 仅在 STARTED 及以上状态执行
                observeData()
            }
        }
    }
}
```

---

## 四、ViewModel 与 LiveData

### 4.1 ViewModel

ViewModel 在配置变更（如屏幕旋转）时保持存活：

```kotlin
class MyViewModel : ViewModel() {
    private val _uiState = MutableLiveData<UiState<List<User>>>()
    val uiState: LiveData<UiState<List<User>>> = _uiState
    
    private val repository = UserRepository()
    
    fun loadUsers() {
        _uiState.value = UiState.Loading
        viewModelScope.launch {
            try {
                val users = withContext(Dispatchers.IO) {
                    repository.fetchUsers()
                }
                _uiState.value = UiState.Success(users)
            } catch (e: Exception) {
                _uiState.value = UiState.Error(e.message ?: "Unknown error")
            }
        }
    }
}
```

### 4.2 LiveData

LiveData 是可观察的数据持有者，生命周期感知：

```kotlin
class UserViewModel : ViewModel() {
    // MutableLiveData 是可变的
    private val _name = MutableLiveData<String>()
    // LiveData 对外暴露为不可变
    val name: LiveData<String> = _name
    
    fun updateName(newName: String) {
        _name.value = newName
    }
}

// 在 Activity 中观察
viewModel.name.observe(this) { name ->
    // 自动在生命周期活跃时接收更新
    textView.text = name
}
```

### 4.3 StateFlow（推荐替代 LiveData）

在新项目中，Google 推荐使用 `StateFlow` 替代 `LiveData`：

```kotlin
class MyViewModel : ViewModel() {
    private val _uiState = MutableStateFlow<UiState>(UiState.Loading)
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()
    
    fun loadData() {
        viewModelScope.launch {
            _uiState.value = UiState.Loading
            val data = repository.fetchData()
            _uiState.value = UiState.Success(data)
        }
    }
}

// Compose 中消费
val uiState by viewModel.uiState.collectAsState()
```

---

## 五、Jetpack Compose 中的 MVVM

### 5.1 完整的 Compose + ViewModel 示例

```kotlin
// ViewModel
class MyViewModel : ViewModel() {
    private val _state = MutableStateFlow(MyState())
    val state: StateFlow<MyState> = _state.asStateFlow()
    
    fun onAction(action: MyAction) {
        when (action) {
            is MyAction.Load -> loadData()
            is MyAction.Refresh -> refreshData()
        }
    }
}

// Composable
@Composable
fun MyScreen(viewModel: MyViewModel = viewModel()) {
    val state by viewModel.state.collectAsState()
    
    when (val current = state) {
        is UiState.Loading -> LoadingIndicator()
        is UiState.Success -> UserList(current.users)
        is UiState.Error -> ErrorMessage(current.message)
    }
}
```

---

## 六、最佳实践

### 6.1 架构原则
1. **单向数据流**：UI → Event → ViewModel → State → UI
2. **单一数据源**：状态在 ViewModel 中定义，UI 只消费
3. **关注点分离**：ViewModel 不含 Android 框架引用
4. **测试性**：Repository 可替换，ViewModel 可独立测试

### 6.2 Compose 性能优化
- 使用 `derivedStateOf` 减少不必要的重组
- `remember` 缓存计算密集型结果
- `key` 参数帮助 Compose 识别列表项
- 避免在 Composable 中创建大量对象

```kotlin
@Composable
fun ExpensiveCalculation(items: List<Item>) {
    val processedItems by remember(items) {
        derivedStateOf { items.filter { it.isValid }.map { it.process() } }
    }
    LazyColumn {
        items(processedItems, key = { it.id }) { item -> ItemRow(item) }
    }
}
```

---

## 七、总结

- **Kotlin** 是现代 Android 开发的基石，空安全、协程、扩展函数是三大核心
- **Jetpack Compose** 以声明式 UI 彻底改变了 Android 开发方式
- **Activity/Fragment** 的生命周期需要精心管理
- **ViewModel** 保存 UI 状态、处理业务逻辑，生命周期感知
- **LiveData/StateFlow** 作为数据流在 ViewModel 和 UI 之间传递
- Compose + ViewModel + StateFlow 是现代 Android 开发的标准组合

下一课将探讨更高级的 Android 架构模式：MVVM/MVI/Clean Architecture。
