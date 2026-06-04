# 发布与监控体系

> 移动开发第8课 — 从签名到APM的完整交付链

## 应用签名与分发

### Android 签名

| 签名类型 | 用途 | 有效期 | 密钥保护 |
|----------|------|--------|---------|
| Debug | 开发调试 | 365天 | 自动生成 |
| Release | Google Play分发 | 25年以上 | 开发者保管 |
| Upload | Play App Signing | 与Release一致 | Google保管 |
| App Signing | 安全加密 | 永久 | 由Play管理 |

### 签名流程
```
Keystore (.jks/.keystore) → keytool 生成 → jarsigner/v2签名
      ↓
APK签名块（V1/V2/V3）
      ↓
Google Play → 重新签名 → APK/Split APK → 用户下载
```

### iOS 签名
- **Development**：真机调试，需设备UDID注册
- **Distribution**：App Store发布
- **Enterprise**：企业内部分发（需Apple企业证书）

## 多渠道分发

### Android 渠道标记
- 应用内埋点自动识别渠道ID
- 渠道APK/AAB差异化打包（不同图标/特性）
- 常见渠道：Google Play、华为、小米、OPPO、vivo、三星

```groovy
// Gradle多渠道配置
android {
    flavorDimensions "store"
    productFlavors {
        googlePlay { dimension "store" }
        huawei { dimension "store" }
        xiaomi { dimension "store" }
    }
}
```

## CI/CD 管线

### Flutter CI/CD

```yaml
# 简化CI流程
stages:
  - lint          # dart analyze, flutter test
  - build_android # flutter build apk --release
  - build_ios     # flutter build ipa --release
  - upload_play   # fastlane supply
  - upload_apple  # fastlane deliver
```

### Fastlane 自动化

```ruby
# Fastfile 配置
lane :deploy do
  # 1. 版本号自增
  increment_build_number
  
  # 2. 构建发布包
  gradle(task: 'clean assembleRelease')
  
  # 3. 上传到Play Console
  upload_to_play_store(
    track: 'production',
    release_status: 'completed'
  )
end
```

## Crashlytics 崩溃管理

### 集成

```dart
// Flutter + Firebase Crashlytics
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  
  FlutterError.onError = (errorDetails) {
    FirebaseCrashlytics.instance.recordFlutterFatalError(errorDetails);
  };
  
  PlatformDispatcher.instance.onError = (error, stack) {
    FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
    return true;
  };
  
  runApp(MyApp());
}
```

### 崩溃分析指标
| 指标 | 含义 | 目标 |
|------|------|------|
| Crash Rate | 崩溃用户/DAU | < 0.1% |
| ANR Rate | 无响应/启动次数 | < 0.05% |
| Fatality | 崩溃后退出率 | 尽量低 |
| OOM Rate | 内存崩溃率 | < 0.01% |

## APM（应用性能监控）

### 关键性能指标

| 指标 | Flutter测量 | Android测量 | iOS测量 |
|------|-------------|-------------|---------|
| 启动时间 | TimeToFirstFrame | Activity启动 | App启动 |
| 帧率 | FrameTiming | Choreographer | CADisplayLink |
| 渲染帧 | Build/Draw/Layout | GPU Profiling | GPU Time |
| 内存 | DevTools Mem | ActivityManager | Xcode Metrics |
| 网络延迟 | Dio/http | OkHttp | URLSession |

### 自定义性能跟踪

```dart
class PerformanceTracker {
  static final _timeline = <String, int>{};
  
  static void start(String label) {
    _timeline[label] = DateTime.now().microsecondsSinceEpoch;
  }
  
  static void end(String label) {
    if (!_timeline.containsKey(label)) return;
    final elapsed = DateTime.now().microsecondsSinceEpoch - _timeline[label]!;
    _reportMetric(label, elapsed);
  }
  
  static void _reportMetric(String label, int us) {
    // 上报到APM服务端
    APMService.instance.record(Metric(
      name: label,
      duration: us,
      timestamp: DateTime.now(),
    ));
  }
}
```

## 灰度发布与A/B测试

### 阶段策略
```
Beta → Internal Test（10%）→ Open Test（30%）→ Production（100%）

每个阶段验证：
1. Crash Rate < 0.1%
2. ANR Rate < 0.05%
3. 性能指标不劣化
4. 核心转化率不下降
```

## 总结
- 签名和安全是发布的基础，密钥管理是最关键的安全风险
- Fastlane实现了90%的发布自动化
- Crashlytics 解决崩溃问题，APM 解决性能问题
- 灰度发布是降低风险的核心手段
