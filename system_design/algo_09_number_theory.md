# 第9课：数论与组合数学

## 1. 素数测试（Miller-Rabin）

### 原理
基于费马小定理和二次探测性质的概率性素数测试。

### 费马小定理
若 p 是素数，则对所有与 p 互素的 a：$a^{p-1} \equiv 1 \pmod{p}$

### Miller-Rabin 算法
将 $n-1$ 写成 $2^s \cdot d$，检查序列：
1. 随机选取底数 a
2. 计算 $x_0 = a^d \mod n$
3. 重复平方 s 次：
   - 若 $x_i \equiv 1$ 且 $x_{i-1} \not\equiv \pm 1 \pmod{n}$，则 n 为合数
4. 若最终 $x_s \not\equiv 1 \pmod{n}$，则 n 为合数

### 确定性底数选择
- n < 2^32：用 [2, 7, 61]
- n < 2^64：用 [2, 325, 9375, 28178, 450775, 9780504, 1795265022]

### 复杂度
- 单次测试：O(log³n) — 模幂运算
- k 次测试：O(k·log³n)
- 错误概率：(1/4)^k

---

## 2. 快速幂（模幂运算）

### 原理
二分法将指数二进制分解，O(log e) 时间内计算 $a^e \mod m$。

```python
def mod_pow(a, e, m):
    result = 1
    base = a % m
    while e > 0:
        if e & 1:
            result = (result * base) % m
        base = (base * base) % m
        e >>= 1
    return result
```

### 复杂度
- 时间：O(log e)
- 空间：O(1)

### 应用
- 模幂运算（RSA、Diffie-Hellman）
- Miller-Rabin 素数测试的核心子程序
- 矩阵快速幂（Fibonacci 等递推）

---

## 3. 扩展欧几里得算法（EXGCD）

### 原理
求解 $ax + by = \gcd(a, b)$ 的一组整数解 $(x, y)$。

### 算法
递归直到 b = 0 时回代：

```python
def exgcd(a, b):
    if b == 0:
        return (1, 0, a)
    x, y, g = exgcd(b, a % b)
    return (y, x - (a // b) * y, g)
```

### 核心性质
- 始终有解（Bezout 定理）
- $|x| \leq b/g, |y| \leq a/g$
- 通解：$x = x_0 + t(b/g), y = y_0 - t(a/g)$

### 应用
- 求解线性丢番图方程
- 模逆元计算（$a^{-1} \mod m$ 当 gcd(a,m)=1）
- 中国剩余定理（CRT）

---

## 4. 组合数取模

### 方法一：预处理阶乘 + 逆元

当 M 为大素数时：

```python
# 预处理
fac[0] = 1
for i in range(1, N+1):
    fac[i] = fac[i-1] * i % M
ifac[N] = mod_pow(fac[N], M-2, M)  # 费马小定理
for i in range(N-1, -1, -1):
    ifac[i] = ifac[i+1] * (i+1) % M

# C(n,k) = fac[n] * ifac[k] * ifac[n-k] % M
```

### 方法二：Lucas 定理

当 n, k 很大且 M 为较小素数时：

$$
C(n, k) \mod M = C(n \mod M, k \mod M) \cdot C(n/M, k/M) \mod M
$$

递归降幂，将 n, k 按 M 进制分解后分别计算组合数。

### 复杂度
- 预处理阶乘+逆元：O(N) 预处理，O(1) 查询
- Lucas 定理：$O(M \log_M n)$（M 为素数）

### 应用
- 概率统计计算
- 动态规划优化
- 密码学

---

## 5. 欧拉函数 + 欧拉定理

### 欧拉函数 $\varphi(n)$
小于等于 n 且与 n 互素的正整数的个数。

#### 计算公式
若 $n = p_1^{k_1} p_2^{k_2} \cdots p_r^{k_r}$：
$$
\varphi(n) = n \prod_{i=1}^r \left(1 - \frac{1}{p_i}\right)
$$

#### 性质
- $\varphi(p) = p - 1$（p 为素数）
- $\varphi(p^k) = p^k - p^{k-1}$
- $\varphi(mn) = \varphi(m)\varphi(n)$（m, n 互素）
- $\sum_{d|n} \varphi(d) = n$

### 欧拉定理
若 $\gcd(a, n) = 1$，则：
$$
a^{\varphi(n)} \equiv 1 \pmod{n}
$$

### 费马小定理
当 n 为素数 p 时，欧拉定理退化为：
$$
a^{p-1} \equiv 1 \pmod{p}
$$

### 应用
- 模逆元计算（$a^{-1} \equiv a^{\varphi(m)-1} \mod m$）
- RSA 加密的数学基础
- 指数降幂

---

## 6. 复杂度总览

| 算法 | 时间复杂度 | 空间复杂度 | 关键输入 |
|------|-----------|-----------|----------|
| Miller-Rabin | O(k·log³n) | O(1) | k 次测试 |
| 快速幂 | O(log e) | O(1) | 指数 e |
| EXGCD | O(log min(a,b)) | O(log min(a,b)) | a, b |
| C(n,k)阶乘逆元 | O(N) 预处理，O(1) 查询 | O(N) | 模数 M（素数） |
| Lucas定理 | O(M log_M n) | O(M) | 模数 M（小素数）|
| 欧拉函数 | O(√n) 单次 / O(n) 筛法 | O(1) / O(n) | n |

## 7. 关键技巧总结

1. **费马小定理求逆元**：仅当 M 为素数且 a 不被 M 整除时可用
2. **EXGCD 求逆元**：适用范围更广，只需 gcd(a,m)=1
3. **Lucas vs 阶乘**：n 很大且 M 为小素数用 Lucas；M 很大且 n < M 用阶乘预处理
4. **欧拉函数降幂**：当指数极大时可用 $a^b \mod m = a^{(b \mod \varphi(m)) + \varphi(m)} \mod m$（b ≥ φ(m)）
