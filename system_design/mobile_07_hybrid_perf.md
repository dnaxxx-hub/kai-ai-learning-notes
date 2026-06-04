# 混合开发策略与性能优化

## 一、混合开发策略概览

移动端开发面临一个经典的难题：**Flutter 的跨平台效率 vs 原生平台的极致体验**。混合开发策略就是在这个光谱上找到最佳平衡点。

### 1.1 常见的混合场景

```
原生 App 嵌入 Flutter 页面（增量迁移）
Flutter App 使用原生模块（性能敏感功能）
原生 + Flutter 混合导航（复杂导航场景）
Flutter + WebView（动态内容渲染）
```

### 1.2 混合开发的核心问题
- **通信开销**：Flutter ↔ Native 序列化/反序列化延迟
- **内存共享**：两套引擎各占内存
- **导航协同**：原生路由与 Flutter 路由的统一
- **生命周期**：Flutter 页面在原生栈中的管理
- **性能瓶颈**：JavaScript Bridge vs Platform Channel

---

## 二、Flutter 嵌入原生

### 2.1 FlutterEngine 预热

Flutter 引擎的创建和 Dart VM 初始化是启动时最大的开销。

```kotlin
// Android：提前预热 FlutterEngine
class MyApplication : Application() {
    lateinit var flutterEngine: FlutterEngine
    
    override fun onCreate() {
        super.onCreate()
        flutterEngine = FlutterEngine(this)
        flutterEngine.dartExecutor.executeDartEntrypoint(
            DartExecutor.DartEntrypoint.createDefault()
        )
        FlutterEngineCache.getInstance().put("my_engine", flutterEngine)
    }
}

// 使用预热引擎
val flutterFragment = FlutterFragment.withCachedEngine("my_engine").build()
```

预热后的 Flutter 页面启动时间可以从 **~2s 降低到 ~200ms**。

### 2.2 FlutterFragment / FlutterActivity

```kotlin
// 在原生 Activity 中嵌入 Flutter 页面
class MyActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        supportFragmentManager.beginTransaction()
            .add(R.id.container, FlutterFragment.createDefault())
            .commit()
    }
}
```

### 2.3 多 FlutterEngine vs 单 Engine + 多 Route

| 策略 | 优点 | 缺点 |
|------|------|------|
| 多 Engine | 隔离性好，独立缓存 | 内存占用高（~20MB/Engine） |
| 单 Engine | 内存低 | 共享状态易冲突 |

推荐策略：**单 Engine + 多 Route**，使用 `Navigator 2.0` 管理路由。

---

## 三、Hot Reload 性能优化

### 3.1 Hot Reload 的工作原理

```
代码修改 → 增量编译（Dart VM 编译） 
→ 发送增量文件到设备 
→ Dart VM 重新加载 
→ Flutter 框架触发重建（WidgetsBinding.reassembleApplications）
```

整个流程期望在 **<1s** 内完成。

### 3.2 影响 Hot Reload 的因素

1. **编译速度**：
   - Native 代码修改（Kotlin/Swift）→ 需完整编译
   - 资源文件修改 → 需重新打包
   - 依赖库变更 → 需重新编译

2. **状态丢失**：
   - `StatefulWidget` 的 `State` 对象默认保留
   - `initState()` 不会重新执行
   - 全局变量和静态变量不会重置

3. **Hot Reload 的限制**：
   - 泛型类型结构变化
   - `enum`/`static final` 常量修改
   - `main()` 方法修改
   - 以上情况需 **Hot Restart**

### 3.3 优化策略

```dart
// ✅ 推荐：将全局初始化放在 widget 外
final apiClient = ApiClient();

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(MyApp());
}

// ❌ 避免：在 build 中创建大量对象
Widget build(BuildContext context) {
  return SomeWidget(
    onPressed: () {}, // 每次重建创建新 closure
  );
}
```

---

## 四、包体积优化

### 4.1 Flutter 包体积组成

```
Flutter App 包 ≈ 
  Flutter Engine（~6MB × 架构数）
  + Dart 代码（编译后 ~1-3MB）
  + Assets/Resources（视具体情况）
  + 原生层（Kotlin/Swift）
```

### 4.2 优化策略

#### 4.2.1 去除不必要的架构支持
```groovy
android {
    defaultConfig {
        ndk {
            abiFilters "arm64-v8a", "armeabi-v7a"
            // 移除 x86, x86_64 减少 ~10MB
        }
    }
}
```

#### 4.2.2 图片资源压缩
```yaml
# pubspec.yaml
flutter:
  assets:
    - assets/  # 使用 webp 代替 png
```

```bash
# 批量转换图片为 webp
cwebp -q 80 input.png -o output.webp
```

#### 4.2.3 代码混淆（Shrinking）
```groovy
android {
    buildTypes {
        release {
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt')
        }
    }
}
```

#### 4.2.4 延迟加载（Deferred Components）
```dart
// 声明延迟加载组件
import 'package:myapp/heavy_module.dart' deferred;

// 按需加载
Future<void> loadHeavyFeature() async {
  await HeavyLibrary.loadLibrary();
  HeavyLibrary.showFeature();
}
```

---

## 五、Dynamic Delivery（动态交付）

Android App Bundle + Play Feature Delivery 实现按需下载模块。

### 5.1 配置

```groovy
// 模块级 build.gradle
android {
    dynamicFeatures = [':on_demand_feature']
}

// on_demand_feature/build.gradle
apply plugin: 'com.android.dynamic-feature'

// Feature 模块配置
play {
    defaultInstallTime = install_time_instant  // 即时安装
}

// 按需模块
play {
    installTime = install_time_ondemand  // 按需下载
}
```

### 5.2 Split APK 大小

App Bundle 根据设备配置分发最小 APK：
- 仅包含设备 ABI 架构的 Native 库
- 仅包含对应语言资源
- 仅包含对应密度资源

---

## 六、JavaScript Bridge 优化

### 6.1 WebView JS Bridge

当 Flutter 需要与 WebView 通信时：

```dart
// Flutter：通过 WebView 的 JavaScriptChannel
WebView(
  javascriptChannels: {
    JavascriptChannel(
      name: 'FlutterBridge',
      onMessageReceived: (message) {
        handleMessage(message.message);
      },
    ),
  },
  onWebViewCreated: (controller) {
    _webViewController = controller;
  },
)

// 发送消息到 JS
Future<void> sendToJs(Map<String, dynamic> data) async {
  final json = jsonEncode(data);
  await _webViewController?.runJavascript(
    'window.FlutterBridge.onMessage($json)',
  );
}
```

### 6.2 性能瓶颈

| 通信方式 | 延迟 | 适用场景 |
|----------|------|----------|
| MethodChannel | ~1ms | Flutter ↔ Native |
| JS Bridge | ~10-100ms | Flutter ↔ WebView |
| Dart FFI | <1μs | 计算密集型 |

**优化建议**：
- 避免高频 JS Bridge 调用
- 批量传输数据（合并多次调用）
- 大数据使用文件传输
- 计算密集型使用 FFI

---

## 七、整体性能优化清单

### 7.1 启动速度
1. **FlutterEngine 预热**：提前初始化引擎
2. **Splash Screen**：原生层快速展示
3. **延迟加载**：首页只加载关键数据
4. **预编译**：使用 AOT 编译发布包

### 7.2 运行时性能
1. **减少 Widget 重建**：使用 `const`、合理设置 `Key`
2. **列表优化**：`ListView.builder` / `Gridview.builder`
3. **图片缓存**：`cached_network_image`
4. **避免 Repaint**：`RepaintBoundary` 隔离
5. **Profile 模式测试**：真机 Profile 模式

### 7.3 内存管理
1. **及时 dispose**：StreamSubscription, AnimationController
2. **图片尺寸控制**：解码为显示尺寸而非原图
3. **避免全局状态膨胀**：关掉不用的页面释放内存
4. **OOM 监控**：Flutter DevTools Memory 面板

### 7.4 网络优化
1. **连接复用**：HTTP/2 keep-alive
2. **数据压缩**：GZip 压缩请求/响应
3. **请求合并**：GraphQL 代替 REST
4. **预缓存**：Service Worker / 本地缓存

---

## 八、总结

- **混合开发**的核心在于平衡跨平台效率和原生性能
- **FlutterEngine 预热**是加速启动的关键技术
- **Hot Reload** 虽然强大，但理解其限制才能高效使用
- **包体积优化**从 ABI 过滤、图片压缩、代码混淆多方面入手
- **Dynamic Delivery** 实现按需下载，显著减小首次安装包
- **JS Bridge** 是真混合方案的性能瓶颈，应控制调用频率
- 性能优化是一个持续的过程，需要定期用 Profile 模式测试

混合开发和性能优化是大型应用的必修课。下一课将探讨应用的发布与监控体系。
