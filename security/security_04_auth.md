# 身份认证与授权

> 日期：2026-05-07 22:22 | 课程：安全路线 Phase 2-2
> 目标：理解"你怎么证明是你，你能做什么"

## 核心问题

```
认证(Authentication): 你是谁？
授权(Authorization):  你能做什么？

登录(认证) → 判断权限(授权)
```

## 认证方式

### 1. Session（传统Web）

```python
# 1. 用户登录 → 服务器创建Session
# 2. 服务器返回Cookie: session_id=abc123
# 3. 后续请求带上Cookie → 服务器查Session

# 优点: 简单，服务端可控
# 缺点: 服务器要存Session（内存/Redis）
#       分布式部署需要共享Session存储
```

### 2. JWT（现代API首选）

```python
# JSON Web Token — 无状态认证

# JWT = header.payload.signature

# header: {"alg": "HS256", "typ": "JWT"}
# payload: {"sub": "user123", "name": "羽", "iat": 1700000000}
# signature: HMACSHA256(base64(header) + "." + base64(payload), secret)

# 流程:
# 1. 登录 → 服务器生成JWT返回
# 2. 前端存JWT（localStorage/HttpOnly Cookie）
# 3. 每次请求带上JWT（Authorization头）
# 4. 服务器验证签名 → 解析payload

# 优点: 无状态（服务器不用存），跨域友好
# 缺点: JWT签发后不能主动撤销（需要黑名单）
```

### 3. OAuth2（第三方登录）

```python
# "用Google/GitHub/微信账号登录"

# 流程:
# 1. 你点"用GitHub登录"
# 2. 跳转到Github → 你同意授权
# 3. GitHub给我们的应用一个"授权码"
# 4. 我们的后台用授权码 → 换取 access_token
# 5. access_token → 可以调GitHub API获取用户信息

# 关键: 你的密码永远不经过我们的服务器
```

### 4. 多因素认证（2FA）

```python
# 密码 + 验证码 + 生物特征 = 三选二

# 因素类型:
# 知识因素: 你知道的（密码）
# 持有因素: 你拥有的（手机/硬件Key）
# 生物因素: 你是什么（指纹/人脸）

# 即使密码泄露了，攻击者没有手机验证码也没用
# 最流行的2FA: TOTP (Google Authenticator/Authy)
# 硬件Key: YubiKey
```

## 授权模型

### RBAC（基于角色的访问控制）

```python
# 用户 → 角色 → 权限

# 用户: 张三
# 角色: 管理员
# 权限: 创建用户/删除用户/查看报表

# 用户: 李四
# 角色: 普通用户
# 权限: 查看报表

# 优点: 简单，管理方便
# 缺点: 粒度不够细
```

### 最小权限原则

```python
# "只给完成任务所需的最小权限"

# ❌ API返回所有用户信息（包括密码hash）
# ✅ API只返回当前登录用户的信息

# ❌ 前端收到所有数据 → 前端自己隐藏
# ✅ 后端只返回用户有权看到的数据

# ❌ 管理员角色有全部权限
# ✅ 即使管理员也细分: 查看/编辑/删除/管理
```

## 安全实践

```python
# 密码存储:
# ❌ 存明文 → 泄漏就完蛋
# ❌ 存 MD5/SHA256 → 彩虹表秒破
# ✅ 存 bcrypt/argon2/scrypt → 慢哈希+加盐

# Cookie安全:
# HttpOnly: JS无法读取 → 防XSS窃取
# Secure: 只在HTTPS下传输
# SameSite: 防CSRF
# Path: 限制路径
```

## 今日收获
- 认证 = 你是谁，授权 = 你能做什么
- Session vs JWT: 有状态 vs 无状态
- OAuth2 = 第三方登录（密码不经过你）
- 2FA = 多一层保险（强烈推荐）
- 最小权限 = 给够用的，不给多余的
- 密码一定要用 bcrypt/argon2 存
