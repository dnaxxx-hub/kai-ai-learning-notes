# Android 架构：MVVM/MVI/Clean Architecture/Hilt/Room/WorkManager

## 一、MVVM 架构模式

### 1.1 分层结构

MVVM（Model-View-ViewModel）是 Android 官方推荐的架构模式：

```
View (Activity/Fragment/Composable)
    ↑↓ 观察 (LiveData/StateFlow)
ViewModel
    ↑↓ 调用
Repository
    ↑↓
Data Sources (Remote/Local)
```

**各层职责**：
- **View**：渲染 UI，转发用户事件，观察 ViewModel 的状态
- **ViewModel**：持有 UI 状态，处理业务逻辑，与 Repository 交互
- **Repository**：单一数据源，协调本地和远程数据
- **Data Source**：具体数据来源（Room DB / Retrofit API / DataStore）

### 1.2 实现示例

```kotlin
// View
@Composable
fun UserScreen(viewModel: UserViewModel = viewModel()) {
    val state by viewModel.state.collectAsState()
    // UI 渲染
}

// ViewModel
class UserViewModel(
    private val repository: UserRepository
) : ViewModel() {
    private val _state = MutableStateFlow(UserUiState())
    val state: StateFlow<UserUiState> = _state.asStateFlow()
    
    fun loadUsers() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true) }
            val users = repository.getUsers()
            _state.update { it.copy(users = users, isLoading = false) }
        }
    }
}

// Repository
class UserRepository(
    private val api: UserApi,
    private val dao: UserDao
) {
    suspend fun getUsers(): List<User> {
        return try {
            val remote = api.fetchUsers()
            dao.insertAll(remote)
            remote
        } catch (e: Exception) {
            dao.getAll() // 降级到缓存
        }
    }
}
```

### 1.3 MVVM 优点
- **关注点分离**：ViewModel 不含 Android 框架引用，可直接测试
- **生命周期安全**：ViewModel 随 Activity 存活，配置变更不丢失
- **可测试性**：ViewModel + Repository 可独立单元测试

---

## 二、MVI 架构模式

MVI（Model-View-Intent）是 MVVM 的演进，强调单向数据流和不可变状态。

### 2.1 核心概念

```
Intent (用户意图) → Model (状态更新) → View (渲染)
```

```kotlin
// Intent（用户操作）
sealed class UserIntent {
    object LoadUsers : UserIntent()
    data class SearchUsers(val query: String) : UserIntent()
    data class DeleteUser(val userId: Long) : UserIntent()
}

// State（不可变状态）
data class UserScreenState(
    val users: List<User> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val searchQuery: String = ""
)

// Side Effect（一次性事件，如导航、Toast）
sealed class UserEffect {
    data class ShowToast(val message: String) : UserEffect()
    data class NavigateToDetail(val userId: Long) : UserEffect()
}

// ViewModel
class UserViewModel : ViewModel() {
    private val _state = MutableStateFlow(UserScreenState())
    val state: StateFlow<UserScreenState> = _state.asStateFlow()
    
    private val _effect = MutableSharedFlow<UserEffect>()
    val effect: SharedFlow<UserEffect> = _effect.asSharedFlow()
    
    fun onIntent(intent: UserIntent) {
        when (intent) {
            is UserIntent.LoadUsers -> loadUsers()
            is UserIntent.DeleteUser -> deleteUser(intent.userId)
        }
    }
}
```

### 2.2 MVVM vs MVI

| 维度 | MVVM | MVI |
|------|------|-----|
| 状态可变性 | 可变（data class copy） | 不可变（统一 State 对象） |
| 事件模型 | 分散的方法调用 | 统一的 Intent |
| 可回溯性 | 较低 | 高（记录所有 Intent） |
| 代码量 | 较少 | 较多 |
| 学习曲线 | 中等 | 较高 |
| 适合场景 | 中小型应用 | 大型复杂应用 |

---

## 三、Clean Architecture

### 3.1 分层设计

Clean Architecture 将应用分为三层，依赖规则：**内层不依赖外层**。

```
┌──────────────────────────────┐
│         Presentation         │  ← Compose UI + ViewModel
├──────────────────────────────┤
│           Domain             │  ← UseCase + Entity（纯 Kotlin）
├──────────────────────────────┤
│            Data              │  ← Repository 实现、Data Source
└──────────────────────────────┘
```

**Domain 层**（最内层，无依赖）：
```kotlin
// 实体
data class User(val id: Long, val name: String, val email: String)

// UseCase（单一职责）
class GetUserUseCase(
    private val userRepository: UserRepository  // 依赖倒置
) {
    suspend operator fun invoke(id: Long): Result<User> {
        return userRepository.getUser(id)
    }
}
```

**Data 层**（实现 Repository 接口）：
```kotlin
interface UserRepository {
    suspend fun getUser(id: Long): Result<User>
}

class UserRepositoryImpl(
    private val api: UserApi,
    private val dao: UserDao
) : UserRepository {
    override suspend fun getUser(id: Long): Result<User> {
        // ... 实现
    }
}
```

### 3.2 依赖规则
- Domain 层不依赖任何 Android 框架
- Data 层依赖 Domain 层（实现 Repository 接口）
- Presentation 层依赖 Domain 层（注入 UseCase）

---

## 四、Hilt DI（依赖注入）

### 4.1 基本用法

```kotlin
// Application 入口
@HiltAndroidApp
class MyApplication : Application()

// Activity
@AndroidEntryPoint
class MainActivity : ComponentActivity() { ... }

// ViewModel 注入
@HiltViewModel
class UserViewModel @Inject constructor(
    private val getUserUseCase: GetUserUseCase
) : ViewModel() { ... }

// 提供依赖
@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides
    @Singleton
    fun provideUserApi(): UserApi {
        return Retrofit.Builder()
            .baseUrl("https://api.example.com")
            .build()
            .create(UserApi::class.java)
    }
    
    @Provides
    fun provideUserRepository(
        api: UserApi,
        dao: UserDao
    ): UserRepository = UserRepositoryImpl(api, dao)
}
```

### 4.2 Hilt 组件层级

| 组件 | 生命周期 | 适用范围 |
|------|----------|----------|
| `SingletonComponent` | Application | 全局单例 |
| `ViewModelComponent` | ViewModel | ViewModel 级别 |
| `ActivityComponent` | Activity | Activity 级别 |
| `FragmentComponent` | Fragment | Fragment 级别 |

---

## 五、Room 数据库

### 5.1 基本定义

```kotlin
@Entity(tableName = "users")
data class UserEntity(
    @PrimaryKey val id: Long,
    @ColumnInfo(name = "full_name") val name: String,
    val email: String,
    val age: Int
)

@Dao
interface UserDao {
    @Query("SELECT * FROM users WHERE id = :id")
    suspend fun getUser(id: Long): UserEntity?
    
    @Query("SELECT * FROM users")
    fun getAllUsers(): Flow<List<UserEntity>>  // Flow 观察变化
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(users: List<UserEntity>)
    
    @Delete
    suspend fun delete(user: UserEntity)
}

@Database(
    entities = [UserEntity::class],
    version = 1,
    exportSchema = true
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun userDao(): UserDao
}
```

### 5.2 Room 特性
- **编译时 SQL 校验**：SQL 语法错误在编译时即可发现
- **Flow 支持**：数据库变化自动推送
- **迁移机制**：`Migration` 类处理版本升级
- **事务支持**：`@Transaction` 注解确保原子性

---

## 六、WorkManager

### 6.1 适用场景

WorkManager 用于**可延迟的、可靠的后台任务**：
- 上传日志
- 同步数据
- 清理缓存
- 发送分析事件

### 6.2 基本用法

```kotlin
class SyncWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {
    
    override suspend fun doWork(): Result {
        return try {
            syncData()
            Result.success()
        } catch (e: Exception) {
            if (runAttemptCount < 3) {
                Result.retry()  // 指数退避重试
            } else {
                Result.failure()
            }
        }
    }
}

// 调度任务
val request = PeriodicWorkRequestBuilder<SyncWorker>(
    15, TimeUnit.MINUTES
).setConstraints(
    Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .setRequiresCharging(true)
        .build()
).build()

WorkManager.getInstance(context)
    .enqueueUniquePeriodicWork(
        "sync",
        ExistingPeriodicWorkPolicy.KEEP,
        request
    )
```

### 6.3 约束条件
- 网络状态（CONNECTED/UNMETERED）
- 充电状态
- 空闲状态
- 存储空间充足

---

## 七、架构选择策略

### 7.1 按项目规模

| 规模 | 推荐架构 |
|------|----------|
| 小型（1-3 屏） | MVVM + Hilt + Room |
| 中型（4-10 屏） | MVVM + Clean + Hilt + Room |
| 大型（10+ 屏） | MVI + Clean + Hilt + Room + WorkManager |
| 超大型（多模块） | MVI + Clean + 模块化 + Compose Navigation |

### 7.2 常见陷阱
1. **过度抽象**：小项目强行 Clean Architecture
2. **忽略 Domain 层**：直接让 ViewModel 依赖 Data 层
3. **UseCase 滥用**：一个方法也包装成 UseCase
4. **ViewModel 膨胀**：一个 ViewModel 管理多个不相关的页面
5. **忘记 Testability**：没有为 Repository 定义接口

---

## 八、总结

- **MVVM** 是 Google 官方推荐的基础架构，分层清晰
- **MVI** 通过不可变状态和统一 Intent 提升了可控性和调试体验
- **Clean Architecture** 通过依赖倒置实现了真正的解耦
- **Hilt** 基于 Dagger 简化了依赖注入配置
- **Room** 提供类型安全的本地持久化，编译时校验 SQL
- **WorkManager** 处理可靠的后台任务，自动适配各种系统版本
- 架构选择应根据项目规模和团队能力决定，避免过度工程

掌握了这些架构组件，你就能构建可维护、可测试的企业级 Android 应用。下一课将探讨混合开发策略与性能优化。
