# Flutter 原生通信：Platform Channel 与插件开发

## 一、Flutter 与原生平台的通信架构

Flutter 应用运行在 Dart VM 中，但 Android 的 Camera、GPS、传感器等硬件 API 需要通过原生代码（Java/Kotlin/ObjC/Swift）访问。为此，Flutter 设计了分层通信架构：

```
Flutter (Dart)
    ↓↑ Platform Channel (序列化/反序列化)
Flutter Engine (C++)
    ↓↑ Method Invocation
Android (Java/Kotlin) / iOS (ObjC/Swift)
```

通信路径：
1. Dart 端发起调用
2. 通过 Platform Channel 序列化为二进制消息
3. 经过 Engine 转发到原生端
4. 原生端反序列化并执行
5. 结果原路返回

---

## 二、三种 Platform Channel

### 2.1 MethodChannel（方法调用）

最常用的通道类型，采用请求-响应模式。

**Dart 端**：
```dart
import 'package:flutter/services.dart';

class BatteryPlugin {
  static const _channel = MethodChannel('com.example/battery');
  
  Future<int> getBatteryLevel() async {
    try {
      final int result = await _channel.invokeMethod('getBatteryLevel');
      return result;
    } on PlatformException catch (e) {
      print("Failed: '${e.message}'");
      return -1;
    }
  }
}
```

**Android 端（Kotlin）**：
```kotlin
class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.example/battery"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                if (call.method == "getBatteryLevel") {
                    val batteryLevel = getBatteryLevel()
                    if (batteryLevel != -1) {
                        result.success(batteryLevel)
                    } else {
                        result.error("UNAVAILABLE", "Battery level not available", null)
                    }
                } else {
                    result.notImplemented()
                }
            }
    }
}
```

**iOS 端（Swift）**：
```swift
@UIApplicationMain
@objc class AppDelegate: FlutterAppDelegate {
    override func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        let controller = window?.rootViewController as! FlutterViewController
        let channel = FlutterMethodChannel(
            name: "com.example/battery",
            binaryMessenger: controller.binaryMessenger
        )
        
        channel.setMethodCallHandler { [weak self] (call, result) in
            guard call.method == "getBatteryLevel" else {
                result(FlutterMethodNotImplemented)
                return
            }
            self?.receiveBatteryLevel(result: result)
        }
        
        return super.application(application, didFinishLaunchingWithOptions: launchOptions)
    }
}
```

### 2.2 EventChannel（事件流）

用于持续的、事件驱动的通信，如传感器数据、位置更新等。

**Dart 端**：
```dart
class SensorStream {
  static const _eventChannel = EventChannel('com.example/sensor');
  
  Stream<double> get sensorStream {
    return _eventChannel.receiveBroadcastStream().cast<double>();
  }
}
```

**Android 端**：
```kotlin
EventChannel(flutterEngine.dartExecutor.binaryMessenger, "com.example/sensor")
    .setStreamHandler(object : EventChannel.StreamHandler {
        override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
            // 注册传感器监听
            sensorManager.registerListener(object : SensorEventListener {
                override fun onSensorChanged(event: SensorEvent?) {
                    events?.success(event?.values?.get(0))
                }
            })
        }
        
        override fun onCancel(arguments: Any?) {
            sensorManager.unregisterListener(listener)
        }
    })
```

### 2.3 BasicMessageChannel（消息传递）

最基础的通道，支持自定义编解码器，适合双向通信。

```dart
// Dart
final channel = BasicMessageChannel<String>(
  'com.example/chat',
  StringCodec(),
);

// 发送消息
channel.send('Hello from Dart');

// 接收消息
channel.setMessageHandler((message) async {
  return 'Reply from Dart';
});
```

---

## 三、编解码器与性能

### 3.1 内置编解码器

| 编解码器 | 用途 | 性能 |
|----------|------|------|
| `JSONMessageCodec` | JSON 对象 | 中等 |
| `StringCodec` | UTF-8 字符串 | 高 |
| `BinaryCodec` | 字节数组 | 最高 |
| `StandardMessageCodec` | 默认，支持 List/Map | 通用 |

### 3.2 性能考量

- **数据序列化开销**：每次 MethodChannel 调用都涉及序列化和反序列化
- **主线程限制**：原生端的处理默认在主线程
- **大数据传输**：超过 1MB 的数据应使用文件共享或内存映射
- **高频调用**：如陀螺仪数据，用 EventChannel 而非重复 MethodChannel

```dart
// 避免：高频轮询
Timer.periodic(Duration(milliseconds: 16), (_) {
  channel.invokeMethod('getData'); // 60fps 调用，性能差
});

// 推荐：使用 EventChannel 订阅
EventChannel('com.example/sensor').receiveBroadcastStream().listen((data) {
  // 原生端主动推送
});
```

---

## 四、Pigeon —— 类型安全的代码生成方案

Pigeon 是 Flutter 官方推荐的代码生成工具，解决了手写 MethodChannel 的痛点。

### 4.1 定义接口（pigeon 文件）

```dart
// battery_api.dart (pigeon 模板)
import 'package:pigeon/pigeon.dart';

class BatteryRequest {
  int? timeoutMs;
}

class BatteryReply {
  int? level;
  String? status;
}

@HostApi()
abstract class BatteryApi {
  BatteryReply getBatteryLevel(BatteryRequest request);
}

@FlutterApi()
abstract class BatteryCallback {
  void onBatteryLow(int level);
}
```

### 4.2 生成代码

```bash
flutter pub run pigeon \
  --input pigeons/battery_api.dart \
  --dart_out lib/generated/battery_api.dart \
  --java_out android/app/src/main/java/.../BatteryApi.java \
  --swift_out ios/Runner/BatteryApi.swift
```

### 4.3 优势
- **编译安全**：类型错误在编译时捕获
- **自动双向代码**：Dart、Android、iOS 同步生成
- **减少样板代码**：不用手写 MethodChannel 字符串匹配
- **版本管理**：接口变更通过 PR 追踪

---

## 五、Dart FFI（Foreign Function Interface）

当需要更高的性能（如图像处理、加密运算）时，Dart FFI 允许直接调用 C/C++ 库。

```dart
import 'dart:ffi';
import 'package:ffi/ffi.dart';

// 1. 定义 C 函数签名
typedef SumNative = Int32 Function(Int32 a, Int32 b);
typedef SumDart = int Function(int a, int b);

// 2. 加载动态库
final dylib = DynamicLibrary.open('libnative_lib.so');
final sumFunc = dylib.lookupFunction<SumNative, SumDart>('sum');

// 3. 调用
void main() {
  final result = sumFunc(3, 4);
  print('3 + 4 = $result');
}
```

### 5.1 FFI vs MethodChannel

| 维度 | Dart FFI | MethodChannel |
|------|----------|---------------|
| 延迟 | <1μs | ~100μs-1ms |
| 适用场景 | 计算密集型 | 平台 API 调用 |
| 调用原生 SDK | ❌ | ✅ |
| 内存管理 | 手动 | 自动 |
| 类型安全 | 低 | 中等（Pigeon 高） |

---

## 六、插件开发实战

### 6.1 创建插件项目

```bash
flutter create --template=plugin --platforms=android,ios my_plugin
```

### 6.2 插件目录结构

```
my_plugin/
├── lib/
│   └── my_plugin.dart        # Dart API 层
├── android/
│   └── src/main/kotlin/.../MyPlugin.kt
├── ios/
│   └── Classes/MyPlugin.swift
├── example/
└── pubspec.yaml
```

### 6.3 最佳实践

1. **API 设计**：以 Dart 接口为主，隐藏原生实现细节
2. **异步处理**：耗时代理操作必须异步
3. **错误处理**：统一转换为 Dart 异常
4. **后台线程**：原生端耗时操作放后台线程运行
5. **注册生命周期**：正确注册和注销监听器

```dart
// 良好的插件 API 设计
class MyPlugin {
  static const _channel = MethodChannel('com.example/my_plugin');
  
  // 隐藏了 method 名称和参数细节
  Future<String> getDeviceInfo() async {
    try {
      return await _channel.invokeMethod('getDeviceInfo');
    } on PlatformException catch (e) {
      throw MyPluginException(e.message ?? 'Unknown error');
    }
  }
}
```

---

## 七、性能优化与陷阱

### 7.1 性能优化

1. **批量传输**：合并多次小调用为一次大调用
2. **避免阻塞主线程**：原生端耗时操作放后台线程
3. **对象缓存**：避免频繁创建临时对象
4. **消息压缩**：大数据用二进制而非 JSON

### 7.2 常见陷阱

1. **通道名称冲突**：使用包名做前缀（`com.example/xxx`）
2. **内存泄漏**：忘记 dispose StreamSubscription
3. **线程安全**：原生端的方法处理可能不在主线程
4. **平台差异**：Android 的 Activity 生命周期 vs iOS 的 ViewController
5. **热重载失效**：原生代码修改需重新编译

---

## 八、总结

- **MethodChannel** 是最常用的通道，适用于请求-响应场景
- **EventChannel** 适用于持续事件流
- **BasicMessageChannel** 提供灵活的二进制通信
- **Pigeon** 代码生成解决类型安全问题
- **Dart FFI** 提供接近原生的性能
- 插件开发应遵循异步、类型安全、生命周期管理的原则
- 根据场景选择合适的通信方式：平台 API 用 MethodChannel，传感器用 EventChannel，计算密集用 FFI

掌握 Flutter 与原生平台的通信机制，是开发真正可用的移动应用的必要技能。下一课将转向 Android 原生开发：Kotlin 与 Jetpack Compose。
