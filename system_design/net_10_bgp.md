# 计算机网络 #10：BGP

## BGP 基础
- 边界网关协议，Internet 的全球路由协议
- AS（自治系统）：由相同管理策略的网络集合
- eBGP：不同 AS 之间 → AS-PATH + NEXT-HOP
- iBGP：AS 内部 → 全互联或路由反射器

## BGP 选路（NPAUS 规则）
当收到同一前缀的多个路由时，按顺序比较：
1. **Weight**（Cisco 私有，越高越优先）
2. **Local Preference**（AS 内传播，越高越优先）
3. **AS Path**（越短越优先）
4. **Origin**（IGP < EGP < Incomplete）
5. **MED**（较低值优先）
6. 小于 iBGP > eBGP
7. 最小 IGP metric to NEXT-HOP

## eBGP 流程
```text
AS 100 ──→ AS 200 ──→ AS 300
├── eBGP    ├── eBGP
└── iBGP  ──┘

AS 200 收到 1.0.0.0/24 from AS 100：
  1. 检查 AS-PATH = [100]，接受
  2. 应用入站策略（route-map）
  3. 安装到路由表（非 BGP 表）
  4. 通告给 iBGP 对等体（不改变 NEXT-HOP）
  5. 通告给 eBGP 对等体（AS 300 时 AS-PATH = [200, 100]）
```

## BGP 属性
| 属性 | 类别 | 作用 |
|------|------|------|
| AS_PATH | Well-known mandatory | 防环 + 选路 |
| NEXT_HOP | Well-known mandatory | 下一跳 |
| LOCAL_PREF | Well-known discretionary | AS 内选路 |
| COMMUNITY | Optional transitive | 打标签（标志性设计） |
| MED | Optional non-transitive | 多出口选路 |

## BGP 安全性
- **RPKI**（Resource Public Key Infrastructure）：验证前缀所有权
  - ROA（Route Origin Authorization）签名声明
  - 路由器检查 ROA：Valid / Invalid / NotFound
- **BGPsec**：给 AS_PATH 加签名，防路径劫持（部署极少）
- 常见攻击：前缀劫持（YouTube 2008 被巴基斯坦封禁）
