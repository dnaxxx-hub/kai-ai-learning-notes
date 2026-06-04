# OWASP Top 10：Web最常见的漏洞

> 日期：2026-05-07 22:21 | 课程：安全路线 Phase 2-1
> 目标：理解"攻击者怎么攻击Web应用"

## OWASP

```python
# Open Web Application Security Project
# 每3~4年发布一次"Web应用十大安全风险"
# 2021年最新版
```

## 最常见的Web攻击

### 1. SQL注入

```sql
-- 漏洞: 直接把用户输入拼到SQL里

-- ❌ 漏洞代码
$sql = "SELECT * FROM users WHERE name = '" + userInput + "'";
-- 输入: ' OR '1'='1
-- 变成: SELECT * FROM users WHERE name = '' OR '1'='1'
-- → 返回所有用户数据（登录绕过！）

-- ✅ 修复: 参数化查询（PreparedStatement）
$stmt = $db->prepare("SELECT * FROM users WHERE name = ?");
$stmt->bind_param("s", $userInput);

-- 输入被当成数据，不是SQL代码
```

### 2. XSS（跨站脚本攻击）

```javascript
// 漏洞: 把用户输入直接显示到页面上

// ❌ 漏洞代码
element.innerHTML = userInput;
// 输入: <script>alert('你被黑了')</script>
// → 弹窗/更严重: 窃取Cookie

// 类型:
// 反射型: 攻击者在URL里注入脚本
// 存储型: 脚本存到数据库，其他人访问时执行
// DOM型: 客户端JS动态拼接导致

// ✅ 修复: 输出编码
element.textContent = userInput; 
// 文本不会当作HTML执行

// ✅ React默认防XSS（自动转义插值）
```

### 3. CSRF（跨站请求伪造）

```html
<!-- 漏洞: 利用用户已登录的状态 -->

<!-- 你在银行网站上登录了（Cookie还在） -->
<!-- 攻击者让你访问这个页面 -->
<img src="https://bank.com/transfer?to=attacker&amount=1000">
<!-- → 浏览器自动带上Cookie → 转账成功！ -->

<!-- ✅ 修复: CSRF Token -->
<!-- 每次请求带上随机Token → 攻击者无法伪造 -->
<!-- 现在浏览器的SameSite Cookie也能防 -->
```

### 4. SSRF（服务端请求伪造）

```python
# 漏洞: 服务器根据用户输入去请求内部资源

# 输入一个URL, 服务器去访问它
# 攻击者输入: http://127.0.0.1:3306
# → 服务器访问自己的MySQL端口

# 更危险: 云服务元数据
# http://169.254.169.254/latest/meta-data/
# → 拿到云服务商的临时凭据

# ✅ 修复: 白名单IP/域名，禁止内网地址
```

### 5. 文件上传漏洞

```python
# 漏洞: 允许用户上传文件但没有限制

# 攻击者上传 test.php（内容是一句话木马）
# 访问这个文件 → 命令执行

# ✅ 修复:
# - 限制文件类型（检查Magic Number，不只是扩展名）
# - 文件存储到外部（不在Web根目录）
# - 随机化文件名
# - 限制文件大小
```

## REST API安全

```python
# API比网页更容易被攻击（因为是程序在直接调用）

# 1. 认证: JWT或OAuth2
# 2. 限流: 防止暴力破解/DDoS
# 3. 输入校验: 所有输入都要验证
# 4. HTTPS: 加密传输
# 5. 最小权限: API只给需要的权限

# 常见问题: JWT未验证签名
# 攻击者修改JWT payload → 服务器没检查签名 → 身份伪造
```

## 今日收获
- SQL注入 = 用户输入当SQL拼 → 用PreparedStatement
- XSS = 用户输入当HTML执行 → React自动防，其他要小心
- CSRF = 利用已登录状态发请求 → SameSite Cookie + Token
- SSRF = 服务器访问内网资源 → 白名单
- 文件上传 = 检查内容，不只是扩展名
