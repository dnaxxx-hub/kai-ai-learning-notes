# CMake 工程化与构建系统深度实践

> 从零到生产：现代 CMake 的最佳实践

---

## 1. 现代 CMake 的理念

CMake 的发展分为三代：
- **CMake 2.x**：变量驱动，全局可见，混乱
- **CMake 3.0~3.11**：目标驱动，作用域设计
- **CMake 3.12+**：`PRIVATE/PUBLIC/INTERFACE` 属性机制成熟，现代 CMake 风格

**核心原则：** 目标（Target）是构建的基本单元，一切以目标为中心。

```cmake
# ❌ 旧风格（CMake 2.x）
include_directories(/path/to/include)
link_directories(/path/to/lib)
add_executable(myapp main.cpp)
target_link_libraries(myapp mylib)

# ✅ 现代风格（CMake 3.x+）
add_library(mylib SHARED mylib.cpp)
target_include_directories(mylib PUBLIC /path/to/include)
target_link_libraries(myapp PRIVATE mylib)
# 依赖传递：mylib 的 PUBLIC 头文件路径自动传给 myapp
```

---

## 2. 完整工程模板

```
project_root/
├── CMakeLists.txt          # 顶层
├── cmake/
│   └── FindXXX.cmake       # 自定义 find 模块
├── src/
│   ├── CMakeLists.txt
│   ├── main.cpp
│   └── core/
│       ├── CMakeLists.txt
│       ├── engine.h
│       └── engine.cpp
├── lib/
│   └── external_lib/
│       └── CMakeLists.txt  # FetchContent 或子目录
├── tests/
│   ├── CMakeLists.txt
│   ├── test_engine.cpp
│   └── test_utils.cpp
├── examples/
│   ├── example1.cpp
│   └── CMakeLists.txt
├── bench/
│   └── benchmark.cpp
└── cmake/
    └── config.h.in         # 配置模板
```

### 2.1 顶层 CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.20)
project(MyProject VERSION 1.0.0 LANGUAGES CXX C)

# C++ 标准设置
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)  # 禁用编译器扩展

# 构建类型
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# 全局编译选项
add_compile_options(-Wall -Wextra -Wpedantic -Werror)

# 导出编译数据库（供 clang-tidy/clangd 使用）
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# 第三方依赖
include(cmake/dependencies.cmake)

# 子目录
add_subdirectory(src)
add_subdirectory(tests)
add_subdirectory(examples)
```

### 2.2 库的 CMakeLists.txt

```cmake
# src/core/CMakeLists.txt
add_library(core
    engine.h
    engine.cpp
    utils.h
    utils.cpp
)

# 头文件目录
target_include_directories(core
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
        $<INSTALL_INTERFACE:include/core>
)

# 链接其他库
target_link_libraries(core
    PUBLIC fmt::fmt
    PRIVATE spdlog::spdlog
)

# 编译选项
target_compile_options(core
    PRIVATE
        $<$<CONFIG:Debug>:-O0 -g>
        $<$<CONFIG:Release>:-O3 -DNDEBUG>
)

# 特性检查
target_compile_features(core
    PUBLIC cxx_std_20
)
```

### 2.3 可执行文件的 CMakeLists.txt

```cmake
# src/CMakeLists.txt
add_executable(myapp main.cpp)

target_link_libraries(myapp
    PRIVATE core
    PRIVATE fmt::fmt
)

# 安装规则
install(TARGETS myapp
    RUNTIME DESTINATION bin
)

# 平台特定设置
if(WIN32)
    target_compile_definitions(myapp PRIVATE _CRT_SECURE_NO_WARNINGS)
    set_target_properties(myapp PROPERTIES WIN32_EXECUTABLE TRUE)
elseif(APPLE)
    set_target_properties(myapp PROPERTIES
        MACOSX_BUNDLE TRUE
        MACOSX_BUNDLE_INFO_PLIST ${CMAKE_SOURCE_DIR}/Info.plist
    )
endif()
```

---

## 3. 依赖管理

### 3.1 FetchContent（CMake 3.14+）

现代 CMake 推荐使用 FetchContent 管理外部依赖，构建时自动下载。

```cmake
# cmake/dependencies.cmake
include(FetchContent)

# ----- 格式化库 -----
FetchContent_Declare(
    fmt
    GIT_REPOSITORY https://github.com/fmtlib/fmt.git
    GIT_TAG 10.1.1
    GIT_SHALLOW TRUE  # 只克隆最新提交，减少下载量
)
FetchContent_MakeAvailable(fmt)

# ----- 测试框架 -----
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.14.0
    GIT_SHALLOW TRUE
)
set(BUILD_GTEST ON CACHE BOOL "" FORCE)
set(BUILD_GMOCK OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# ----- 基准测试 -----
FetchContent_Declare(
    benchmark
    GIT_REPOSITORY https://github.com/google/benchmark.git
    GIT_TAG v1.8.3
    GIT_SHALLOW TRUE
)
set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(benchmark)

# ----- 日志库 -----
FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG v1.12.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(spdlog)
```

### 3.2 使用 find_package 查找系统库

```cmake
# 查找系统安装的库
find_package(OpenSSL REQUIRED)
find_package(ZLIB REQUIRED)
find_package(CURL REQUIRED)

target_link_libraries(core
    PUBLIC OpenSSL::SSL OpenSSL::Crypto
    PRIVATE ZLIB::ZLIB CURL::libcurl
)

# 查找可选依赖
find_package(JPEG)
if(JPEG_FOUND)
    target_compile_definitions(core PRIVATE HAS_JPEG)
    target_link_libraries(core PRIVATE JPEG::JPEG)
endif()
```

### 3.3 包管理器对比

| 管理器 | 特点 | 适用场景 |
|--------|------|----------|
| FetchContent | CMake 内置，零依赖 | 小项目，简单依赖 |
| Conan | 全功能，支持远程仓库 | 中大型项目，复杂依赖树 |
| vcpkg | Microsoft 维护，库多 | Windows/Linux/macOS 支持好 |
| CPM.cmake | FetchContent 的简化包装 | 想用 FetchContent 但讨厌冗长 |

---

## 4. 测试集成

### 4.1 CTest + GoogleTest

```cmake
# tests/CMakeLists.txt
enable_testing()  # 启用 CTest

# 添加测试可执行文件
add_executable(test_core
    test_engine.cpp
    test_utils.cpp
)

target_link_libraries(test_core
    PRIVATE core
    PRIVATE gtest gtest_main
)

# 注册测试
add_test(NAME test_core COMMAND test_core)

# 或者自动发现（CMake 3.10+）
include(GoogleTest)
gtest_discover_tests(test_core)
```

### 4.2 测试示例

```cpp
// tests/test_engine.cpp
#include <gtest/gtest.h>
#include "core/engine.h"

TEST(EngineTest, InitialState) {
    Engine engine;
    EXPECT_FALSE(engine.is_running());
    EXPECT_EQ(engine.get_state(), Engine::State::Stopped);
}

TEST(EngineTest, StartAndStop) {
    Engine engine;
    engine.start();
    EXPECT_TRUE(engine.is_running());
    engine.stop();
    EXPECT_FALSE(engine.is_running());
}

TEST(EngineTest, ProcessData) {
    Engine engine;
    std::vector<int> data = {1, 2, 3, 4, 5};
    auto result = engine.process(data);
    ASSERT_EQ(result.size(), 5);
    EXPECT_EQ(result[0], 2);  // 假设每个元素 double
    EXPECT_EQ(result[4], 10);
}

// 参数化测试
class EngineParamTest : public ::testing::TestWithParam<int> {};
TEST_P(EngineParamTest, Threshold) {
    int threshold = GetParam();
    Engine engine(threshold);
    EXPECT_GT(engine.get_threshold(), 0);
}
INSTANTIATE_TEST_SUITE_P(
    EngineTests,
    EngineParamTest,
    ::testing::Values(1, 10, 100, 1000)
);
```

### 4.3 覆盖率

```cmake
# 启用覆盖率（Debug 模式）
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
        add_compile_options(--coverage)
        add_link_options(--coverage)
    endif()
endif()

# 运行测试后：
# gcovr --root . --html coverage.html
```

---

## 5. 安装与打包

### 5.1 安装规则

```cmake
# 安装库
install(TARGETS core
    EXPORT CoreTargets      # 导出目标，供 find_package 使用
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
    INCLUDES DESTINATION include
)

# 安装头文件
install(DIRECTORY include/
    DESTINATION include
    FILES_MATCHING PATTERN "*.h"
)

# 安装配置文件
install(FILES
    ${CMAKE_BINARY_DIR}/config.h
    DESTINATION include
)

# 导出 CMake 配置文件（让其他项目 find_package 用到）
install(EXPORT CoreTargets
    FILE CoreTargets.cmake
    NAMESPACE core::
    DESTINATION lib/cmake/Core
)

# 创建 CoreConfig.cmake
include(CMakePackageConfigHelpers)
configure_package_config_file(
    cmake/CoreConfig.cmake.in
    ${CMAKE_BINARY_DIR}/CoreConfig.cmake
    INSTALL_DESTINATION lib/cmake/Core
)
write_basic_package_version_file(
    ${CMAKE_BINARY_DIR}/CoreConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    ${CMAKE_BINARY_DIR}/CoreConfig.cmake
    ${CMAKE_BINARY_DIR}/CoreConfigVersion.cmake
    DESTINATION lib/cmake/Core
)
```

### 5.2 CPack 打包

```cmake
# 顶层 CMakeLists.txt 末尾

# 启用 CPack
set(CPACK_PACKAGE_NAME ${PROJECT_NAME})
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "My Project Description")
set(CPACK_RESOURCE_FILE_LICENSE ${CMAKE_SOURCE_DIR}/LICENSE)

# Windows NSIS 安装器
if(WIN32)
    set(CPACK_GENERATOR NSIS)
    set(CPACK_NSIS_DISPLAY_NAME "MyProject")
    set(CPACK_NSIS_INSTALL_ROOT "$PROGRAMFILES")
endif()

# Linux DEB/RPM
if(UNIX)
    set(CPACK_GENERATOR DEB;RPM)
    set(CPACK_DEBIAN_PACKAGE_MAINTAINER "developer@example.com")
endif()

include(CPack)

# 打包命令：
# cmake --build . --target package
# 或
# cpack
```

---

## 6. 预编译头与增量编译加速

### 6.1 预编译头

```cmake
# CMake 3.16+ 支持 target_precompile_headers

# 在核心库中
target_precompile_headers(core PRIVATE
    <vector>
    <string>
    <memory>
    <algorithm>
    <iostream>
    <fmt/core.h>
)

# 或者让所有使用该 target 的目标都共享预编译头
target_precompile_headers(core INTERFACE
    <vector>
    <string>
)
```

### 6.2 单元编译（Unity Build）

```cmake
# CMake 3.16+ 支持 Unity Build
# 将多个源文件合并编译，减少编译单元数

# 全局启用
set(CMAKE_UNITY_BUILD ON CACHE BOOL "Enable unity builds")

# 或针对特定 target
set_target_properties(core PROPERTIES
    UNITY_BUILD ON
    UNITY_BUILD_BATCH_SIZE 8  # 每批合并 8 个源文件
)
```

### 6.3 其他加速技巧

```cmake
# 1. 使用 ninja 替代 make
# cmake -G Ninja ...

# 2. 使用 ccache
find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    set(CMAKE_CXX_COMPILER_LAUNCHER ${CCACHE_PROGRAM})
endif()

# 3. 并行编译（默认已启用，但可以显式设置）
# cmake --build . -j 16

# 4. 模块化（C++20 Modules）
# CMake 3.28+ 支持
if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.28)
    set(CMAKE_EXPERIMENTAL_CXX_MODULE_DYNDEP ON)
endif()
```

---

## 7. 量化交易系统的 CMake 方案

针对 libkds/KVStore 的工程化：

```cmake
cmake_minimum_required(VERSION 3.20)
project(kai_quant VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_C_STANDARD 11)

# ----- C 核心库 -----
add_library(kds SHARED
    src/kds/darr.c
    src/kds/hmap.c
    src/kds/rbuf.c
    src/kds/bheap.c
)

target_include_directories(kds PUBLIC include/kds)
target_compile_options(kds PRIVATE -Wall -Wextra -Werror)

# ----- C++ KVStore -----
add_library(kvstore SHARED
    src/kvstore/store.cpp
    src/kvstore/wal.cpp
    src/kvstore/memtable.cpp
)

target_include_directories(kvstore PUBLIC include/kvstore)
target_link_libraries(kvstore PRIVATE kds)

# ----- C++ Python 绑定 -----
add_library(pykvstore MODULE
    src/python/pybinding.cpp
)

target_link_libraries(pykvstore PRIVATE kvstore Python3::Python)

# ----- C++ 策略引擎 -----
add_library(strategy
    src/strategy/sma.cpp
    src/strategy/bollinger.cpp
    src/strategy/rsi.cpp
)

target_link_libraries(strategy
    PRIVATE kvstore
    PUBLIC fmt::fmt Eigen3::Eigen
)

# ----- 测试 -----
if(BUILD_TESTING)
    enable_testing()
    add_executable(test_kds test/test_darr.c test/test_hmap.c)
    target_link_libraries(test_kds PRIVATE kds)
    add_test(NAME test_kds COMMAND test_kds)
endif()
```

---

## 8. CI/CD 集成

### 8.1 GitHub Actions

```yaml
# .github/workflows/build.yml
name: Build and Test

on: [push, pull_request]

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        build_type: [Debug, Release]
    
    runs-on: ${{ matrix.os }}
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Configure
      run: |
        cmake -B build \
          -DCMAKE_BUILD_TYPE=${{ matrix.build_type }} \
          -DBUILD_TESTING=ON
    
    - name: Build
      run: cmake --build build -j $(nproc)
    
    - name: Test
      run: cd build && ctest --output-on-failure
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v4
      with:
        name: binaries-${{ matrix.os }}-${{ matrix.build_type }}
        path: build/bin/
```

---

## 结论

| 功能 | 推荐做法 | CMake 版本 |
|------|----------|-----------|
| 依赖管理 | FetchContent | 3.14+ |
| 测试 | GoogleTest + CTest | 3.10+ |
| 打包 | CPack (NSIS/DEB/RPM) | 内置 |
| 预编译头 | target_precompile_headers | 3.16+ |
| 增量编译 | Unity Build + ccache + Ninja | 3.16+ |
| 模块化 | C++20 Modules | 3.28+ (实验) |
