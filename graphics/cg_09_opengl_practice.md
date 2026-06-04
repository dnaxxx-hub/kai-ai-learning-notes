# 计算机图形学 #9：OpenGL 渲染管线实战

> 从理论到动手——深入 OpenGL 现代可编程管线每一阶段
> 日期：2026-05-13

---

## 1. OpenGL 现代管线总览

### 1.1 可编程管线 vs 固定管线

```
现代可编程管线 (OpenGL 3.3+)
  Vertex Data → [Vertex Shader] → Tessellation → Geometry Shader →
  [Rasterize] → [Fragment Shader] → Framebuffer Ops → Frame Buffer

  方括号内为可编程阶段

  ┌──────────────────┐
  │  Vertex Data     │  VBO/VAO 存储
  │      ↓           │
  │  Vertex Shader   │  逐顶点：坐标变换、属性传递
  │      ↓           │
  │  Primitive Assy  │  组装为三角形
  │      ↓           │
  │  Rasterization   │  扫描线填充 → Fragment
  │      ↓           │
  │  Fragment Sh.    │  逐像素计算颜色/光照
  │      ↓           │
  │  Per-Fragment    │  深度测试、模板测试、混合
  │      ↓           │
  │  Frame Buffer    │  最终像素写入
  └──────────────────┘
```

### 1.2 VAO / VBO / EBO 关系

GPU内存布局：
- **VBO** (Vertex Buffer Object)：顶点数据连续存储 `[x,y,z, nx,ny,nz, u,v, ...]`
- **EBO** (Element Buffer Object)：索引数组 `[0,1,2, 2,1,3, ...]`
- **VAO** (Vertex Array Object)：状态记录器——绑定哪个VBO、属性布局、EBO

```cpp
glGenVertexArrays(1, &VAO);
glGenBuffers(1, &VBO);
glGenBuffers(1, &EBO);

glBindVertexArray(VAO);
glBindBuffer(GL_ARRAY_BUFFER, VBO);
glBufferData(GL_ARRAY_BUFFER, size, data, GL_STATIC_DRAW);
glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 8*sizeof(float), (void*)0);
glEnableVertexAttribArray(0);

glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, EBO);
glBufferData(GL_ELEMENT_ARRAY_BUFFER, size, indices, GL_STATIC_DRAW);
```

**⚠️ 易错：** 忘记绑定VAO就画→崩溃；多个网格共用VAO属性冲突；stride/offset不对齐

### 1.3 Shader 编译链接

```
GLSL源码 → glCreateShader → glShaderSource → glCompileShader
→ glGetShaderiv(编译状态) → glCreateProgram → glAttachShader(vs+fs)
→ glLinkProgram → glUseProgram → glDeleteShader(可删中间对象)
```

**⚠️ 易错：** 不检查编译日志→找半天拼写错误；uniform拼错不报错(值全0)；layout(location)与glVertexAttribPointer index不一致

### 1.4 坐标系变换链

```
Local → Model Matrix → World → View Matrix → Eye → Projection → Clip
→ 透视除法 → NDC [-1,1]³ → Viewport → Screen

Vertex Shader 标准写法：
gl_Position = projection * view * model * vec4(aPos, 1.0);
```

**⚠️ 易错：** 矩阵乘法顺序(projection*view*model*vertex)；Z-fighting(远近裁剪面太远忘记调)

---

## 2. 顶点处理（Vertex Shader）

### 2.1 顶点属性布局

```cpp
struct Vertex {
    glm::vec3 position;    // 偏移0, 12B
    glm::vec3 normal;      // 偏移12, 12B
    glm::vec2 texCoord;    // 偏移24, 8B
};  // 步长=32B

glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE,
    sizeof(Vertex), (void*)offsetof(Vertex, position));
glEnableVertexAttribArray(0);
```

### 2.2 法线变换 — Normal Matrix

**法线不能直接用 model 矩阵变换！** 非均匀缩放会破坏法线的垂直性。

正确做法：
```glsl
// Vertex Shader
uniform mat3 normalMatrix;  // = transpose(inverse(mat3(modelView)))
vNormal = normalize(normalMatrix * aNormal);
```

**⚠️ 易错：** 法线直接用model变换→光照错误；忘记在CPU计算inverse

---

## 3. 光栅化

### 3.1 扫描线填充

- **Edge Walking**：按y逐行扫描，DDA插值左右x，填充之间像素（CPU友好）
- **Edge Equation**：计算点到三条边距离符号，并行友好（GPU实际使用）

### 3.2 透视矫正插值

核心：屏幕空间线性插值 ≠ 世界空间线性插值

透视投影后，屏幕坐标与 1/z 呈线性。GPU自动用 `1/w` 加权插值：
```
f_screen = lerp(f0/w0, f1/w1, t) / lerp(1/w0, 1/w1, t)
```

**⚠️ 易错：** noperspective修饰符禁用透视矫正；不理解smooth/flat/noperspective区别

### 3.3 背面剔除

```cpp
glEnable(GL_CULL_FACE);
glCullFace(GL_BACK);     // 剔除背面
glFrontFace(GL_CCW);     // 逆时针为正面(默认)
```

### 3.4 深度测试

- **Early-Z**：FS执行前深度测试，跳过被遮挡像素（FS不写gl_FragDepth时生效）
- **延迟Z**：FS执行后测试（FS写了gl_FragDepth时）

```cpp
glEnable(GL_DEPTH_TEST);
glDepthFunc(GL_LESS);
glDepthMask(GL_TRUE);   // 写入深度
glDepthMask(GL_FALSE);  // 只读(透明物体用)
```

透明渲染：先不透明物体(深度写入+测试) → 透明物体(不写深度，只读，从远到近排序)

**⚠️ 易错：** 忘记`glClear(GL_DEPTH_BUFFER_BIT)` ← 最常见的渲染bug；透明物体不排序

---

## 4. 片元处理（Fragment Shader）

### 4.1 Blinn-Phong 逐像素光照

```glsl
// Gouraud(逐顶点)：VS算光照→插值→输出，低模高光走样严重
// Phong(逐像素)：VS传法线/位置→FS逐像素算，平滑精确

vec3 norm = normalize(vNormal);
vec3 lightDir = normalize(lightPos - vFragPos);
vec3 viewDir = normalize(-vFragPos);

// Ambient
vec3 ambient = 0.1 * lightColor;

// Diffuse
float diff = max(dot(norm, lightDir), 0.0);
vec3 diffuse = diff * lightColor;

// Specular (Blinn-Phong: 半程向量)
vec3 halfDir = normalize(lightDir + viewDir);
float spec = pow(max(dot(norm, halfDir), 0.0), shininess);
vec3 specular = spec * lightColor * 0.5;

FragColor = vec4(ambient + diffuse + specular, 1.0);
```

### 4.2 纹理采样

| 模式 | OpenGL | 效果 |
|------|--------|------|
| 最近邻 | GL_NEAREST | 像素风 |
| 双线性 | GL_LINEAR | 平滑 |
| 三线性MIP | GL_LINEAR_MIPMAP_LINEAR | 最佳质量 |

### 4.3 法线贴图 — TBN变换

切线空间的法线贴图 → 通过TBN矩阵转到世界空间：
```glsl
vec3 normal = texture(uNormalMap, vTexCoord).rgb;
normal = normalize(normal * 2.0 - 1.0);           // [0,1]→[-1,1]
vec3 worldNormal = normalize(uTBN * normal);       // 切线→世界
```

**⚠️ 易错：** 忘记[0,1]→[-1,1]映射→光照完全错误；TBN方向反了→凹凸颠倒

---

## 5. 帧缓冲与后期处理

### 5.1 FBO (Framebuffer Object)

```
FBO:
  ├── Color Attachment 0 (纹理)
  ├── Depth Attachment (Renderbuffer)
  └── Stencil Attachment
```

```cpp
unsigned int fbo;
glGenFramebuffers(1, &fbo);
glBindFramebuffer(GL_FRAMEBUFFER, fbo);
// 创建颜色纹理 + 深度RBO + 挂载
// 检查: glCheckFramebufferStatus → GL_FRAMEBUFFER_COMPLETE
```

### 5.2 HDR + ToneMapping

- FBO用 `GL_RGB16F`（非8bit，否则HDR无效）
- ToneMapping：Reinhard `hdr/(hdr+1)` 或 Exposure `1-exp(-hdr*exposure)`
- Gamma校正：`pow(color, 1/2.2)`

### 5.3 Bloom

5个Pass：渲染→提取亮色→水平高斯模糊→垂直高斯模糊→混合

### 5.4 延迟渲染 (Deferred Shading)

- **前向渲染**：n物体×m光源 = n×m次draw call
- **延迟渲染**：
  - Pass1 G-Buffer：位置/法线/颜色写入3张纹理（与几何复杂度无关）
  - Pass2 Lighting：读G-Buffer算光照（每像素一次）

G-Buffer典型布局：RT0位置(xyz)+材质 / RT1法线(xyz)+roughness / RT2颜色(rgb)+metallic

---

## 6. 优化策略

### 6.1 GPU→CPU 数据传输

- **Orphan Buffer**：glBufferData(size, NULL)分配新缓冲，旧缓冲继续用
- **Persistent Mapping (GL4.4+)**：直接写指针，无需每帧map/unmap
- **Ring Buffer**：2-3缓冲+fence同步交替

### 6.2 Draw Call 合并

- **Batch Rendering**：合并小物体到一个VBO
- **Instancing**：`glDrawElementsInstanced`，VS中gl_InstanceID读不同变换矩阵（1000个小球=1次draw call）
- **Indirect Drawing**：参数放GPU缓冲（GL4.3+）

### 6.3 纹理压缩

| 格式 | 比 | 场景 |
|------|----|------|
| BC1(DXT1) | 6:1 | 无Alpha纹理 |
| BC3(DXT5) | 4:1 | 有Alpha纹理 |
| BC5 | 4:1 | 法线贴图 |
| BC7 | 3:1 | 高质量 |
| ASTC | 灵活 | 移动端 |

### 6.4 状态切换排序

```
最优排序: Shader → Texture → Mesh
不要每帧切shader；Texture binding顺序固定减少切换
```

---

## 7. 调试

```cpp
// GL 4.3+ Debug Callback
void GLAPIENTRY debugCallback(GLenum source, GLenum type, GLuint id,
    GLenum severity, GLsizei length, const GLchar* message, ...) {
    std::cerr << "[GL Debug] " << message << std::endl;
}
glDebugMessageCallback(debugCallback, nullptr);
glEnable(GL_DEBUG_OUTPUT);
```

常用工具：RenderDoc(帧级调试)、NVIDIA Nsight(性能分析)

---

## 8. 总结

核心要点：
1. **VAO/VBO结构**是OpenGL一切的基础
2. **变换链**决定顶点最终位置，矩阵顺序极易出错
3. **法线变换**必须用Normal Matrix(transpose(inverse(modelView)))
4. **逐像素光照**比逐顶点更平滑
5. **FBO多Pass**是后期效果的基石
6. **延迟渲染**解决多光源性能问题
7. **优化核心**：减少draw call、减少状态切换、Persistent Mapping
8. **调试**：Debug Callback + RenderDoc

下一步实战方向：在5070Ti上用OpenGL 4.x写一个带PBR+Bloom的小场景渲染器。
