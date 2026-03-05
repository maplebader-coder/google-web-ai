# Google AI 模式（AI Mode）接口分析文档 v2.3

> **声明**：本文档为逆向分析结果，接口归 Google 所有。

---

## 一、接口总览

| # | 接口名 | 域名 | 路径 | 方法 | 作用 |
|---|--------|------|------|------|------|
| 1 | AI 查询 | `www.google.com` | `/search` | GET | 发送问题，获取 Gemini AI 回答 |
| 2 | 日志上报 | `www.google.com` | `/log` | POST | 客户端行为事件日志上报 |
| 3 | Cookie 轮换 | `www.google.com` | `/RotateCookies` | POST | 每 10 分钟刷新会话 Cookie |
| 4 | 图片上传 | `lensfrontend-pa.clients6.google.com` | `/v1/crupload` | POST | 上传图片（Protobuf 格式） |
| 5 | 状态初始化 | `www.google.com` | `/complete/search` | GET | 初始化 AI 输入框状态及图文会话 |
| 6 | 会话 ID 获取 | `lensfrontend-pa.clients6.google.com` | `/v1/gsessionid` | GET | 获取 Lens 服务的会话 ID 及路由信息 |
| 7 | 账号信息查询 | `accounts.google.com` | `/ListAccounts` | GET | 查询登录用户的 Google 账号信息 |
| 8 | 异步数据获取 | `ogads-pa.clients6.google.com` | `/$rpc/.../GetAsyncData` | POST | 进入 AI 界面时初始化异步数据（gRPC-Web） |
| 9 | 对话历史列表 | `www.google.com` | `/httpservice/web/AimThreadsService/ListThreads` | GET | 加载用户历史 AI 对话列表 |
| 10 | AI 查询（folif） | `www.google.com` | `/async/folif` | GET | 发送问题获取 Gemini AI 流式渲染回答（核心接口补全） |
| 11 | 批量 RPC | `www.google.com` | `/wizrpcui/_/WizRpcUi/data/batchexecute` | POST | 批量 RPC 调用，含 AI 对话状态上报 |
| — | JS 资源包 | `www.google.com` | `/xjs/_/js/...` | GET | AI Mode 前端 JS Bundle（静态资源，非 API） |
| — | CSS 模块 | `www.google.com` | `/xjs/_/ss/.../m={ids}` | GET | AI Mode CSS 样式模块按需加载（静态资源，非 API） |
| 12 | 后台 JS 加载 | `www.google.com` | `/async/bgasy` | GET | 返回需后台异步加载的 JS 文件 URL 列表 |
| 14 | 主页后台初始化 | `www.google.com` | `/async/hpba` | GET | 初始化 AI Mode 基础 JS/CSS Bundle，返回流式 HTML 占位结构 |
| 13 | Cookie 轮换 | `accounts.google.com` | `/RotateCookies` | POST | 刷新/轮换身份认证 Cookie（identity.hfcr） |

---

## 二、AI 查询接口（核心接口）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://www.google.com/search` |
| 请求方法 | GET |
| 内部标识 | 请求文件名显示为 `folif?ei=...` |

### URL 参数

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `q` | `你好 gemini` | 核心参数：用户输入的问题 |
| `udm` | `50` | AI 模式标识，值为 50 时进入 AI 对话模式，缺少则退化为普通搜索 |
| `aep` | `22` | AI 模式专属标记，固定值 22 |
| `ei` | `mNWmacPJJJfJkPlPy_eYmQ8` | 请求唯一标识符（每次请求生成） |
| `yv` | `3` | 接口版本号 |
| `sca_esv` | `e0de6c95d35408ea` | 客户端环境签名/版本哈希 |
| `source` | `hp` | 来源页面，hp = 首页 |
| `stkp` | `Ad3YPqws...Kg3` | 客户端会话跟踪参数 |
| `cs` | `0` | 客户端状态标志 |
| `csuir` | `0` | 客户端 UI 渲染状态标志 |
| `csui` | `3` | 客户端 UI 模式标识 |
| `elrc` | `CmowYTQ3...XM` | 对话上下文令牌（编码形式，支持多轮连续对话） |
| `mstk` | `AUtExfBB...L5g` | 主鉴权令牌：用于身份验证和会话保持，缺少则请求被拒绝 |
| `ved` | `t:244952` | 点击追踪标识符 |
| `async` | `_fmt:adl_snbasecss:...` | 异步资源加载配置 |

---

## 三、日志上报接口

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://www.google.com/log` |
| 请求方法 | POST |

### URL 参数

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `format` | `json` | 数据格式 |
| `hasfast` | `true` | 快速上报模式 |
| `authuser` | `0` | 账号索引（多账号时区分） |

### Request Payload 结构

```
[
  [1, null, null, null, ...],    // [0] 事件标识数组
  596,                            // [1] 事件序号或时间偏移(ms)
  [[1772542146255, null, ...]],   // [2][0][0] Unix 毫秒时间戳
  null, null, null, null,         // [3-6] 保留字段
  null, null, null, null,         // [7-10] 保留字段
  null, null, null, null, null,   // [11-16] 保留字段
  [[null, [..., 89978449]], 9]    // [17] 扩展元数据
]
```

| 位置 | 示例值 | 说明 |
|------|--------|------|
| `[0]` | `[1, null, ...]` | 日志类型/事件标识数组 |
| `[1]` | `596` | 事件序号或时间偏移量（ms） |
| `[2][0][0]` | `1772542146255` | Unix 毫秒时间戳 |
| `[17]` | `[[null, [..., 89978449]], 9]` | 扩展元数据，含数字 ID 和标志位 |

---

## 四、Cookie 轮换接口

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://www.google.com/RotateCookies` |
| 请求方法 | POST |
| 触发时机 | 会话进行中周期性触发（约每 10 分钟） |

### Request Payload

```
[1, "60545914474894441667"]
```

| 索引 | 值 | 说明 |
|------|----|------|
| `[0]` | `1` | 操作类型标识，固定为 1 |
| `[1]` | `"60545914474894441667"` | 用户或会话唯一 ID（长整型字符串） |

### Response

```
];}
[["identity.hfcr",600],["di",88]]
```

| 字段 | 值 | 说明 |
|------|----|------|
| 安全前缀 | `];}` | JSON 劫持防护前缀（解析前需去除） |
| `identity.hfcr` | `600` | Cookie 有效期（秒），即 10 分钟后需再次轮换 |
| `di` | `88` | 服务器响应状态标识 |

### Response Headers

| 字段 | 值 | 说明 |
|------|----|------|
| `Access-Control-Allow-Credentials` | `true` | 允许携带 Cookie 的跨域请求 |
| `Access-Control-Allow-Origin` | `https://www.google.com` | 仅允许 google.com 调用 |
| `Alt-Svc` | `h3=":443"; ma=2592000` | 支持 HTTP/3（QUIC） |
| `Cache-Control` | `private` | 不允许公共缓存 |
| `Content-Encoding` | `gzip` | 响应体 gzip 压缩 |
| `Content-Length` | `733` | 压缩后 733 字节 |
| `Server` | `ESF` | Google 内部服务器（External Serving Framework） |
| `Server-Timing` | `gfet4t7; dur=142` | 服务端处理耗时 142ms |
| `Set-Cookie` | `{多个 Cookie}` | 更新 domain=.google.com 的会话 Cookie |
| `Vary` | `Origin` | 响应随 Origin 请求头变化 |
| `X-Frame-Options` | `SAMEORIGIN` | 防点击劫持 |
| `X-XSS-Protection` | `0` | 禁用旧版 XSS 过滤 |

---

## 五、图片上传接口（crupload）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://lensfrontend-pa.clients6.google.com/v1/crupload` |
| 请求方法 | POST |
| 触发时机 | 用户在普通图片分析场景中上传图片时触发。**图片生成场景（azm=4 流程）不触发本接口。** |
| 服务归属 | Google Lens 前端 API 服务（lensfrontend-pa） |

### Request Headers

| 字段 | 示例值 | 说明 |
|------|--------|------|
| `:authority` | `lensfrontend-pa.clients6.google.com` | 目标服务域名 |
| `:method` | `POST` | HTTP 方法 |
| `:path` | `/v1/crupload` | 接口路径 |
| `Accept` | `*/*` | 接受任意响应类型 |
| `Accept-Encoding` | `gzip, br; add` | 支持 gzip/Brotli 压缩 |
| `Accept-Language` | `zh-CN,...` | 客户端语言偏好 |
| `Authorization` | `Bearer {OAuth2 Token}` | OAuth2 鉴权令牌，跨域调用 Lens 服务必须携带 |
| `Content-Length` | `52492` | 请求体约 51KB（图片序列化后大小） |
| `Content-Type` | `application/x-protobuf` | Protocol Buffers 二进制格式，图片数据序列化后上传 |
| `Cookie` | `{会话 Cookie}` | Google 会话 Cookie |
| `Origin` | `https://www.google.com` | 跨域来源 |
| `Sec-Ch-Ua` | `"Chromium";v="132", "Google Chrome";v="132"` | 浏览器标识 |
| `Sec-Ch-Ua-Mobile` | `?0` | 非移动端 |
| `Sec-Ch-Ua-Platform` | `"Windows"` | 操作系统 |
| `Sec-Fetch-Dest` | `empty` | 非文档型 Fetch 请求 |
| `Sec-Fetch-Mode` | `cors` | 跨域请求模式 |
| `Sec-Fetch-Site` | `cross-site` | 跨站（google.com 调用 clients6.google.com） |
| `User-Agent` | `Mozilla/5.0 (Windows NT 10.0; Win64; x64)...` | 用户代理 |
| `X-Clientdetails` | `{Base64 编码串}` | 客户端平台/版本信息 |

> 说明：Content-Type 为 application/x-protobuf，图片以 Protocol Buffers 格式序列化，无法直接解析请求体，需对应的 .proto 文件才能反序列化查看图片数据。

### Response Headers

| 字段 | 值 | 说明 |
|------|----|------|
| `Access-Control-Allow-Credentials` | `true` | 允许跨域携带 Cookie |
| `Access-Control-Allow-Origin` | `https://www.google.com` | 仅允许 google.com 跨域调用 |
| `Alt-Svc` | `h3=":443"; ma=2592000` | 支持 HTTP/3 |
| `Cache-Control` | `private` | 不允许公共缓存 |
| `Content-Encoding` | `gzip` | 响应体 gzip 压缩 |
| `Content-Length` | `733` | 压缩后 733 字节 |
| `Content-Type` | `text/plain` | 名义 text，实际为 Protobuf 二进制数据 |
| `Server` | `ESF` | Google 内部服务器标识 |
| `Server-Timing` | `gfet4t7; dur=142` | 服务端处理耗时 142ms |
| `Set-Cookie` | `{多个 Cookie}` | 设置/更新 domain=.google.com 的会话 Cookie |
| `Vary` | `Origin` | 响应随 Origin 请求头变化 |
| `X-Content-Type-Options` | `nosniff` | 禁止 MIME 类型嗅探 |
| `X-Frame-Options` | `SAMEORIGIN` | 防点击劫持 |
| `X-XSS-Protection` | `0` | 禁用旧版 XSS 过滤 |

### Request Payload 结构（Protobuf 二进制）

从 DevTools Payload 标签可见请求体为 Protobuf 二进制数据，夹杂有可读字符串如 ICC_PROFILE、mntrRGB XYZ、para、mluc、enUS 等，均为图片嵌入的 ICC 色彩配置信息（Color Profile Metadata），属于 JPEG/PNG 标准元数据。

Response Body（Protobuf 完整解析）

Preview 标签中显示的 Base64 字符串即为 Protobuf 响应体，解码后完整结构如下：

Base64（Preview 显示原文）:
Eno6eAo2STVBd2JMOW1KcnlWajl3...ZHooEg==

解码后 Protobuf 结构树:
  field_2  (外层包装容器, 122 bytes)
    field_7  (核心数据块, 120 bytes)
      field_1  (string, 54B) = I5AwbL9mJryVj9wz81KbT-7C0srOMDzOe2P3xomg9pXsDfpLbdddIw
      field_2  (string, 54B) = a0P4JdQhPBiHMUfuc7HMoZ-pUc0wDZGFjoYQ4P1zZUtc7aGP0fnq8A
      field_6  (metadata, 6B)
        field_4  (string, 2B) = dz
        field_5  (varint)     = 18

| Protobuf 路径 | 值 | 语义 | 说明 |
|--------------|-----|------|------|
| field_2 | 外层包装 | 响应容器 | 122 字节顶层包装字段 |
| field_7 | 120 字节嵌套 | 上传结果块 | 所有核心返回数据的载体 |
| field_7.field_1 | I5AwbL9mJry...dddIw | 上传图片唯一 ID | 54 字节 URL-safe Base64，标识本次上传图片 |
| field_7.field_2 | a0P4JdQhPBi...q8A | vsrid（视觉搜索会话 ID） | 54 字节，即 /complete/search?vsrid= 中携带的值，将图片与 AI 对话关联 |
| field_7.field_6.field_4 | dz | 格式/服务标识 | 2 字节，可能标识图片处理格式或后端服务代号 |
| field_7.field_6.field_5 | 18 | 状态码或版本号 | varint，可能代表处理成功状态或协议版本 |

关键发现：crupload 响应的 field_7.field_2 即为 vsrid，这解释了为何图片上传完成后 /complete/search 能立刻携带 vsrid 参数——vsrid 正是从 crupload Protobuf 响应中提取的，而非由 gsessionid 接口返回。

---

## 六、AI 输入框状态初始化接口（complete/search）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://www.google.com/complete/search` |
| 请求方法 | GET |
| 触发时机 A | 普通图片上传模式（无 azm 参数）：q=&client=aim-zero-state&xssi=t |
| 触发时机 B | 点击图片生成按钮时：带 **azm=4**，进入图片生成功能初始化（此流程不触发 crupload） |
| 触发时机 C | 普通图片上传 crupload 完成后：带 **azm=7** + vsrid，建立图文分析会话 |

### URL 参数

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `q` | （空） | 查询词，初始化时为空 |
| `client` | `aim-zero-state` | 客户端标识：aim = AI Mode，zero-state = 零状态（输入框为空） |
| `azm` | `4` 或 `7` | 功能阶段标识：4 = 点击上传按钮初始化；7 = 图片上传完成建立图文会话 |
| `vsrid` | `COrd4LrajYjOlgEQ...NQAA` | 视觉搜索会话 ID（Visual Search Request ID）：图片上传后由服务端分配；azm=4 时无此参数 |
| `xssi` | `t` | XSSI 防护标记，响应体前加安全前缀，客户端需去除后解析 |

### 两次调用对比

| 参数 | 第一次（azm=4） | 第二次（azm=7） | 说明 |
|------|---------------|---------------|------|
| `azm` | `4` | `7` | 阶段不同 |
| `vsrid` | 无 | `COrd4LrajYj...NQAA` | 第二次携带图片会话 ID |
| `q` | 空 | 空 | 两次均为空 |
| 触发时机 | 点击图片上传按钮时 | crupload 完成后 | 顺序执行 |

### Response Headers

| 字段 | 值 | 说明 |
|------|----|------|
| `Accept-Ch` | Sec-CH-Prefers-Color-Scheme, Downlink, RTT, Sec-CH-UA-Platform, Sec-CH-UA-Full-Version, Sec-CH-UA-Arch, Sec-CH-UA-Model 等 | 服务端声明需要的 UA Client Hints（颜色方案、网络信息、设备型号等） |
| `Alt-Svc` | `h3=":443"; ma=2592000, h3-29=":443"; ma=2592000` | 支持 HTTP/3 |
| `Cache-Control` | `no-cache, must-revalidate` | 禁止缓存，每次必须重新请求 |
| `Content-Disposition` | `attachment; filename="1txt"` | 强制下载模式，防止浏览器直接渲染（JSON 劫持防护） |
| `Content-Encoding` | `br` | Brotli 压缩 |
| `Content-Security-Policy` | `object-src 'none'; base-uri 'self'; script-src 'nonce-...' 'strict-dynamic'` | 严格 CSP 安全策略 |
| `Content-Type` | `application/json; charset=UTF-8` | JSON 格式响应 |
| `Cross-Origin-Opener-Policy` | `same-origin-allow-popups; report-to="gws"` | 跨源开启策略 |
| `Date` | `Tue, 03 Mar 2026 13:47:09 GMT` | 响应时间 |
| `Expires` | `-1` | 立即过期，强制不缓存 |

> 说明：Content-Disposition: attachment; filename="1txt" 是 Google 防 JSON 劫持的标准做法，配合 xssi=t 参数，响应体以安全前缀 ])}while(1); 开头，客户端必须去除前缀后才能解析 JSON。

---

## 七、完整图文对话流程

```
步骤 1：进入 AI 模式
  GET /search?udm=50&aep=22&source=hp&...
  ↓ 页面切换为 AI 对话界面

步骤 2：用户点击图片上传按钮
  GET /complete/search?q=&client=aim-zero-state&azm=4&xssi=t
  ↓ 初始化 AI 输入框零状态

步骤 3：用户选择本地图片，触发上传
  POST https://lensfrontend-pa.clients6.google.com/v1/crupload
    Authorization: Bearer {OAuth2 Token}
    Content-Type: application/x-protobuf
    Body: {Protobuf 序列化的图片数据，约 51KB}
  ← 服务端返回包含 vsrid 的 Protobuf 响应

步骤 4：图片上传完成，建立图文会话
  GET /complete/search?q=&client=aim-zero-state&azm=7&vsrid={图片ID}&xssi=t
  ↓ 输入框就绪，等待用户输入文字

步骤 5：用户输入文字提问并提交
  GET /search?q={问题}&udm=50&aep=22&mstk={token}&elrc={上下文}&...
  ↓ 发起图文混合 AI 问答（图片通过 vsrid 关联）

步骤 6：接收 Gemini AI 回答（流式返回）
  ← 服务器返回 AI 生成的图文分析内容

步骤 7：周期性刷新 Cookie（每 10 分钟）
  POST /RotateCookies  Body: [1, "{用户ID}"]
  ← [["identity.hfcr",600],["di",88]]
```

---

## 八、关键 Token / ID 汇总

| Token/ID | 所在接口 | 生命周期 | 说明 |
|----------|---------|----------|------|
| `mstk` | /search URL 参数 | 会话级 | 主鉴权令牌，AI 对话必须携带 |
| `elrc` | /search URL 参数 | 每轮对话 | 上下文令牌，支持多轮连续对话 |
| `stkp` | /search URL 参数 | 会话级 | 客户端会话追踪参数 |
| `ei` | /search URL 参数 | 单次请求 | 单次请求唯一 ID |
| `vsrid` | /complete/search URL 参数 | 图片会话级 | 图片上传后的视觉搜索会话 ID |
| `Authorization` Bearer | crupload 请求头 | 会话级 | OAuth2 令牌，跨域调用 Lens 服务鉴权 |
| `identity.hfcr` Cookie | /RotateCookies 响应 | 600 秒 | 通过 RotateCookies 周期刷新 |

---

## 七（续）、完整图文对话流程（含 gsessionid）

```
步骤 0：打开图片上传功能前
  GET https://lensfrontend-pa.clients6.google.com/v1/gsessionid?surface=38&platform=3
    Authorization: SAPISID1HASH {hash值}
  ← 返回 sessionId、gwsSessionId、routingInfo（cell + rack）
  ↓ 获取到 Lens 服务的会话路由信息，确定后续请求分配到哪个服务器

步骤 1-7：（同前述图文对话流程）
```

---

## 九、会话 ID 获取接口（gsessionid）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://lensfrontend-pa.clients6.google.com/v1/gsessionid` |
| 请求方法 | GET |
| 触发时机 | 进入图片上传功能前，最早触发，用于初始化 Lens 服务会话 |
| 服务归属 | Google Lens 前端 API 服务（与 crupload 同域） |

### URL 参数（Payload）

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `surface` | `38` | 调用场景/来源标识，`38` 代表 AI Mode 图片功能入口 |
| `platform` | `3` | 平台标识，`3` 代表 Web 桌面端（Desktop Web） |

### Request Headers

| 字段 | 示例值 | 说明 |
|------|--------|------|
| `:authority` | `lensfrontend-pa.clients6.google.com` | 目标服务域名 |
| `:method` | `GET` | HTTP 方法 |
| `:path` | `/v1/gsessionid?surface=38&platform=3` | 接口路径含参数 |
| `:scheme` | `https` | 协议 |
| `Accept` | `*/*` | 接受任意响应类型 |
| `Accept-Encoding` | `gzip, deflate, br, zstd` | 支持多种压缩算法（包括 zstd） |
| `Accept-Language` | `zh-CN,...` | 客户端语言偏好 |
| `Authorization` | `SAPISID1HASH {36a33401c871...}` | Google SAPISID Hash 鉴权（区别于 Bearer Token），用于验证用户身份 |
| `Cookie` | `{超长 Cookie 串，含 SAPISID, SIDCC, __Secure-1PSIDCC 等}` | 完整 Google 会话 Cookie |
| `Origin` | `https://www.google.com` | 跨域来源 |
| `Referer` | `https://www.google.com` | 来源页面 |
| `Sec-Ch-Ua` | `"Not A(Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"` | 浏览器标识 |
| `Sec-Ch-Ua-Mobile` | `?0` | 非移动端 |
| `Sec-Ch-Ua-Platform` | `"Windows"` | 操作系统 |
| `Sec-Fetch-Dest` | `empty` | 非文档型请求 |
| `Sec-Fetch-Mode` | `cors` | 跨域请求 |
| `Sec-Fetch-Site` | `same-site` | 同站请求（均为 google.com 旗下域名） |
| `User-Agent` | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...` | 用户代理 |
| `X-Browser-Channel` | `stable` | Chrome 版本通道 |
| `X-Browser-Copyright` | `Copyright 2026 Google LLC. All rights reserved.` | 版权声明 |
| `X-Browser-Validation` | `{编码串}` | 浏览器完整性验证 token |
| `X-Browser-Year` | `2026` | 浏览器构建年份 |
| `X-Client-Data` | `CJm2yQElu7blkAQjmzcBCK3 +ygE8qmLAQFuM0BCXChw8Yt/a9AQ8nx8BCMwzwEya/9AQu...` | 客户端实验/特性标志数据（Base64 编码，含 A/B 测试变体信息） |
| `X-Goog-Api-Key` | `AIuaS5yBeQgjqmXlAua5FZXO5t8_EZ_uJm7GE` | **Google API Key**（用于 Lens 服务调用鉴权） |
| `X-Goog-Authuser` | `0` | 账号索引（多账号时区分），`0` 为默认账号 |

> 说明：本接口使用双重鉴权机制，同时携带 `Authorization: SAPISID1HASH` 和 `X-Goog-Api-Key`，前者验证用户身份，后者验证调用方（客户端）身份。

### Response Headers

| 字段 | 值 | 说明 |
|------|----|------|
| `Access-Control-Allow-Credentials` | `true` | 允许跨域携带 Cookie |
| `Access-Control-Allow-Origin` | `https://www.google.com` | 仅允许 google.com 调用 |
| `Access-Control-Expose-Headers` | `vary,vary,vary,content-length` | 允许客户端访问的响应头 |
| `Alt-Svc` | `h3=":443"; ma=2592000, h3-29=":443"; ma=2592000` | 支持 HTTP/3 |
| `Cache-Control` | `private` | 不允许公共缓存 |
| `Content-Encoding` | `gzip` | 响应体 gzip 压缩 |
| `Content-Length` | `196` | 压缩后 196 字节 |
| `Content-Type` | `application/json; charset=UTF-8` | JSON 格式响应 |
| `Date` | `Tue, 03 Mar 2026 13:46:41 GMT` | 响应时间 |
| `Expires` | `Tue, 03 Mar 2026 13:46:41 GMT` | 与 Date 相同，即刻过期 |
| `Server` | `ESF` | Google 内部服务器 |
| `Server-Timing` | `gfet4t7; dur=37` | 服务端处理耗时仅 **37ms**（轻量级接口） |
| `Set-Cookie` | `SIDCC=...`, `__Secure-1PSIDCC=...`, `__Secure-3PSIDCC=...` | 设置/更新多个安全 Cookie，含 HttpOnly、Secure 标志 |
| `Strict-Transport-Security` | `max-age=10886400; includeSubdomains` | HSTS 强制 HTTPS，126 天有效期 |
| `Vary` | `Origin`, `X-Origin`, `Referer` | 响应随来源信息变化 |
| `X-Content-Type-Options` | `nosniff` | 禁止 MIME 嗅探 |
| `X-Frame-Options` | `SAMEORIGIN` | 防点击劫持 |
| `X-Xss-Protection` | `0` | 禁用旧版 XSS 过滤 |

### Response Body

```json
{
  "sessionId": "1tgp8ackmXkpJCft1BedtE1N8fxe8S9rhyNtLjBase1kdkrgD",
  "gwsSessionId": "eVjJ1IUIOBsJmvp3oK_hkUKOhMN1sChkWFbGEMvhVy_jdBB-3A",
  "routingInfo": {
    "cell": "yp",
    "rack": "1N"
  }
}
```

| 字段 | 示例值 | 说明 |
|------|--------|------|
| `sessionId` | `1tgp8ackmXkp...krgD` | **Lens 服务会话 ID**：后续 crupload 图片上传请求需携带，标识本次图片处理会话 |
| `gwsSessionId` | `eVjJ1IUIOBsJ...BB-3A` | **GWS（Google Web Server）会话 ID**：与 Google 主服务端的会话绑定标识 |
| `routingInfo.cell` | `yp` | 路由单元（Cell）标识：服务端负载均衡分配的数据中心/服务单元代号 |
| `routingInfo.rack` | `1N` | 路由机架（Rack）标识：具体分配到的服务器机架编号，配合 cell 定位处理节点 |

> 说明：`routingInfo` 中的 `cell` 和 `rack` 是 Google 分布式架构的路由信息，用于将后续的图片上传请求（普通图片分析场景的 crupload）路由到同一个处理节点，保证会话一致性。图片生成场景中 crupload 不会触发，gsessionid 仅用于初始化 Lens 服务上下文。

---

## 十、关键 Token / ID 汇总（更新版）

| Token/ID | 所在接口 | 生命周期 | 说明 |
|----------|---------|----------|------|
| `mstk` | /search URL 参数 | 会话级 | 主鉴权令牌，AI 文字对话必须携带 |
| `elrc` | /search URL 参数 | 每轮对话 | 上下文令牌，支持多轮连续对话 |
| `stkp` | /search URL 参数 | 会话级 | 客户端会话追踪参数 |
| `ei` | /search URL 参数 | 单次请求 | 单次请求唯一 ID |
| `vsrid` | /complete/search URL 参数 | 图片会话级 | 图片上传后的视觉搜索会话 ID，关联图片与对话 |
| `sessionId` | /v1/gsessionid 响应 | 会话级 | Lens 服务会话 ID，crupload 时需携带 |
| `gwsSessionId` | /v1/gsessionid 响应 | 会话级 | GWS 会话绑定 ID |
| `routingInfo` | /v1/gsessionid 响应 | 会话级 | 服务路由信息（cell + rack），保证请求落到同一节点 |
| `Authorization` Bearer | crupload 请求头 | 会话级 | OAuth2 令牌，crupload 上传鉴权 |
| `SAPISID1HASH` | gsessionid 请求头 | 会话级 | Google SAPISID Hash，用户身份验证 |
| `X-Goog-Api-Key` | gsessionid 请求头 | 客户端固定 | Google API Key，调用方（客户端）身份验证 |
| `identity.hfcr` Cookie | /RotateCookies 响应 | 600 秒 | 通过 RotateCookies 周期刷新 |

---

## 十一、鉴权机制对比

| 接口 | 鉴权方式 | 说明 |
|------|---------|------|
| `/search` (AI 查询) | URL 参数 `mstk` | Google 自有会话令牌 |
| `/RotateCookies` | Cookie | 依赖浏览器 Cookie 会话 |
| `/v1/crupload` | `Authorization: Bearer {OAuth2 Token}` | OAuth2 标准令牌 |
| `/v1/gsessionid` | `Authorization: SAPISID1HASH` + `X-Goog-Api-Key` | 双重鉴权：用户身份 + 客户端身份 |
| `/complete/search` | Cookie | 依赖浏览器 Cookie 会话 |

---

## 十二、后续可补充的信息

| 建议 | 操作方式 | 目的 |
|------|---------|------|
| crupload Payload 原始数据 | DevTools → crupload → Payload 标签 | 分析 Protobuf 请求体结构，确认 sessionId 是否传入 |
| 图文对话时的 /search 完整参数 | 上传图片后发问时抓包 | 确认 vsrid 是否也传入 AI 查询接口 |
| /complete/search Response 内容 | Response 标签，去安全前缀后解析 | 了解初始化返回的 JSON 结构 |
| 第二次对话时各 Token 变化 | 连续发两条消息对比 elrc 参数 | 验证多轮对话上下文机制 |

---

## 十三、两种场景对比：普通图片上传 vs 图片生成

### 场景一：普通图片上传 + 提问

用户直接点击 "+" 上传图片，输入文字提问，要求 AI 分析图片内容，AI 返回文字分析结果。

接口调用顺序：
1. GET  /v1/gsessionid?surface=38&platform=3  ->  获取 sessionId + routingInfo
2. POST /v1/crupload  ->  上传图片（仅普通分析场景），返回 vsrid
3. GET  /complete/search?q=&client=aim-zero-state&xssi=t  ->  [无 azm 参数] 普通模式初始化
4. GET  /search?q={问题}&udm=50&aep=22&mstk={token}...  ->  AI 分析图片，返回文字回答

核心特征：complete/search 无 azm 参数，AI 输出为文字分析结果。

---

### 场景二：图片生成模式（点击图片生成按钮）

用户点击 "🧸 图片" 按钮，输入文字描述，要求 AI 生成图片。

接口调用顺序：
1. GET  /v1/gsessionid?surface=38&platform=3  ->  获取 sessionId + routingInfo
2. GET  /complete/search?q=&client=aim-zero-state&azm=4&xssi=t  ->  [带 azm=4] 图片生成功能初始化
3. GET  https://accounts.google.com/ListAccounts?listPages=0&authuser=0...  ->  验证登录账号
4. GET  /search?q={描述文字}&udm=50&aep=22&mstk={token}...  ->  AI 根据描述生成图片并返回
5. POST /RotateCookies  ->  刷新会话 Cookie（如需）

核心特征：complete/search 带 azm=4，额外触发 ListAccounts 账号验证，AI 输出为生成的图片。

注意：图片生成场景不会触发 crupload 接口，无需上传任何图片，整个过程仅靠文字描述驱动。

---

## 十四、账号列表查询接口（ListAccounts）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | https://accounts.google.com/ListAccounts |
| 请求方法 | GET |
| 触发时机 | 仅在图片生成功能（azm=4 流程）启动后触发，普通图片上传不触发 |
| 服务归属 | Google 账号服务（独立域名 accounts.google.com） |
| 目的 | 验证当前登录用户账号状态，确保图片生成服务有身份绑定 |

### URL 参数

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| listPages | 0 | 列表页码，0 = 第一页 |
| authuser | 0 | 账号索引，0 = 默认主账号 |
| pid | 1 | 产品 ID，1 = Google 主服务 |
| gpsia | 1 | Google 产品服务集成标识（Google Product Service Integration Auth） |
| source | ogb | 来源标识：ogb = One Google Bar（顶部导航栏） |
| atic | 1 | 账号类型验证标志（Account Type Identity Check） |
| mo | 1 | 多账号模式标志（Multi-account mode Option） |
| mn | 1 | 多账号指定（Multi-account Number） |
| hl | zh-CN | 界面语言（Host Language） |
| ts | 157 | 时间戳标识或请求序列号 |

### Response 结构

```
[
  "gaia.l.a.r",
  [
    ["gaia.l.a.s", 1, "Maple Bader", "maplebader@gmail.com", "...", "..."]
  ]
]
```

| 字段路径 | 示例值 | 说明 |
|---------|--------|------|
| [0] | "gaia.l.a.r" | 响应类型：GAIA 账号列表响应标识 |
| [1] | 数组 | 所有已登录账号的列表 |
| [1][0][0] | "gaia.l.a.s" | 单账号条目类型标识 |
| [1][0][1] | 1 | 账号索引（对应 authuser 值） |
| [1][0][2] | "Maple Bader" | 用户显示名（Full Name） |
| [1][0][3] | "maplebader@gmail.com" | Gmail 账号邮箱（主登录账号） |
| [1][0][4+] | "..." | 头像 URL、GAIA ID 等其他账号元数据 |

注意：该接口返回用户真实邮箱和姓名，属于敏感个人信息，仅供学习研究分析接口结构。


---

## 十五、异步数据获取接口（GetAsyncData）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://ogads-pa.clients6.google.com/$rpc/google.internal.onegoogle.asyncdata.v1.AsyncDataService/GetAsyncData` |
| 请求方法 | POST |
| 协议类型 | **gRPC-Web**（HTTP/2 + application/json+protobuf） |
| 触发时机 | 进入 AI 对话界面时立即触发，优先于任何用户交互 |
| 服务归属 | `ogads-pa.clients6.google.com`（One Google Async Data Service） |
| 目的 | 获取用户相关的异步通知/状态数据，初始化 AI 界面上下文 |

### Request Headers

| 字段 | 示例值 | 说明 |
|------|--------|------|
| `:authority` | `ogads-pa.clients6.google.com` | 目标域名（独立于 google.com 和 clients6.google.com） |
| `:method` | `POST` | HTTP 方法 |
| `:path` | `/$rpc/google.internal.onegoogle.asyncdata.v1.AsyncDataService/GetAsyncData` | gRPC-Web 完整路径，包含 proto 包名 + 服务名 + 方法名 |
| `Content-Type` | `application/json+protobuf` | gRPC-Web 编码格式（JSON 序列化的 Protobuf） |
| `Authorization` | `SAPISIDHASH {h} SAPISID1PHASH {h} SAPISID3PHASH {h}` | **三重 SAPISID Hash 鉴权**，同时携带标准、1P、3P 三个 Hash |
| `X-Goog-Api-Key` | `AIzaSyCbsbvGCe7C9mCtdaTycZB2eUFuzsYKG_E` | Google API Key（与 gsessionid 接口的 Key 不同） |
| `X-Goog-Authuser` | `0` | 账号索引 |
| `X-User-Agent` | `grpc-web-javascript/0.1` | **gRPC-Web 客户端标识**，表明使用 gRPC-Web 协议 |
| `X-Client-Data` | `{Base64}` | 客户端 A/B 测试变体数据（含 variation_id 和 trigger_variation_id） |
| `X-Browser-Channel` | `stable` | Chrome 版本通道 |
| `X-Browser-Year` | `2026` | 浏览器构建年份 |
| `Priority` | `u=1, i` | 请求优先级：用户可见（u=1）且可中断（i） |
| `Origin` | `https://www.google.com` | 跨域来源 |
| `Referer` | `https://www.google.com/` | 来源页面 |
| `Sec-Fetch-Site` | `same-site` | 同站请求 |

> 关键特征：本接口是文档中唯一使用 gRPC-Web 协议的接口（Content-Type: application/json+protobuf + x-user-agent: grpc-web-javascript/0.1），说明后端采用 gRPC 微服务架构，通过 gRPC-Web 网关暴露给浏览器调用。

### X-Client-Data 解码内容

```
variation_id (用于分析，不影响服务端行为):
  [3300105, 3300131, 3313321, 3325741, 3330194, 3362821, 3395745,
   3397333, 3397436, 3397575, 3397577, 3397683, 3397790, 3397842,
   3397934, 3398046, 3398146, 3398200]

trigger_variation_id (同时触发服务端行为):
  [3392236, 3396285, 3397866]
```

X-Client-Data 是 Base64 编码的 Protobuf，解码后分两类变体 ID：
- variation_id：当前激活的 A/B 测试变体，仅用于数据分析
- trigger_variation_id：不仅用于分析，还会直接触发服务端功能差异

### Request Payload 结构

```json
["1", "", "zh-CN", "de", 1, null, 0, 0, "", "", 1, 0, null, 89978449,
 [[1, 105, 9, 13], 0, 1, 0], [1, null], 11, 1]
```

| 位置 | 值 | 语义 | 说明 |
|------|----|------|------|
| `[0]` | `"1"` | 请求版本 | 固定值 |
| `[1]` | `""` | 保留 | 空 |
| `[2]` | `"zh-CN"` | 界面语言 | 用户当前语言设置 |
| `[3]` | `"de"` | 备用语言/地区 | 浏览器默认语言或地区代码 |
| `[4]` | `1` | 功能标志 | 布尔，1 = 启用 |
| `[5~12]` | `null/0/""` | 保留字段 | — |
| `[13]` | `89978449` | **AI Mode Surface ID** | 与 /log 接口 Payload [17] 中出现的数字完全一致，确认为 AI Mode 产品标识符 |
| `[14]` | `[[1,105,9,13],0,1,0]` | 功能配置数组 | 嵌套数组，105/9/13 可能为界面模块 ID |
| `[15]` | `[1, null]` | 版本/会话信息 | — |
| `[16]` | `11` | 界面状态码 | — |
| `[17]` | `1` | 结束标志 | — |

> 重要发现：[13] 值 89978449 与 /log 接口 [17][[null, [..., 89978449]], 9] 中的数字完全一致，可以确认该值为 AI Mode 的 Surface ID，在日志上报和异步数据拉取两个接口间共享。

### Response Headers

| 字段 | 值 | 说明 |
|------|----|------|
| `Access-Control-Allow-Credentials` | `true` | 允许跨域携带 Cookie |
| `Access-Control-Allow-Origin` | `https://www.google.com` | 仅允许 google.com 调用 |
| `Access-Control-Expose-Headers` | `x-google-eom, vary×3, content-encoding, date, server, content-length` | 暴露给客户端的头，含 x-google-eom（gRPC-Web 消息结束标记） |
| `Cache-Control` | `private` | 不允许公共缓存 |
| `Content-Encoding` | `gzip` | gzip 压缩 |
| `Content-Length` | `30` | 压缩后仅 30 字节（响应极短） |
| `Content-Type` | `application/json+protobuf; charset=UTF-8` | gRPC-Web JSON+Protobuf 响应 |
| `Server` | `ESF` | Google 内部服务器 |
| `Server-Timing` | `gfet4t7; dur=135` | 服务端处理耗时 135ms |
| `Set-Cookie` | SIDCC + __Secure-1PSIDCC + __Secure-3PSIDCC | 刷新三个安全 Cookie，有效期 1 年 |
| `Strict-Transport-Security` | `max-age=10886400; includeSubdomains` | HSTS 强制 HTTPS，126 天 |
| `Vary` | Origin, X-Origin, Referer | 响应随来源变化 |

### Response Body

```json
[null, null, null, null, null, null, null, null, null, null, 0]
```

| 字段 | 值 | 说明 |
|------|----|------|
| `[0]~[9]` | `null` | 所有数据字段均为 null（无待推送的异步数据） |
| `[10]` | `0` | 状态码：0 = 成功，当前无异步数据 |

说明：Response 全为 null 表示当前没有待推送的异步数据（无新通知、无待处理任务）。这符合初次进入 AI 界面的场景——服务确认连通并返回空状态。若有异步事件（如服务端主动推送消息），相应字段会有具体值。


---

## 十六、对话历史列表接口（ListThreads）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://www.google.com/httpservice/web/AimThreadsService/ListThreads` |
| 请求方法 | GET |
| 触发时机 | 进入 AI 对话界面时触发，紧随 GetAsyncData 之后，出现**两次**（不同 sca_esv 参数） |
| 服务归属 | `www.google.com`，路径前缀 `/httpservice/web/AimThreadsService/` 表明是 AI Mode Thread 服务的 HTTP 包装层 |
| 目的 | 加载当前用户的历史 AI 对话（Thread）列表，用于侧边栏历史记录展示 |

### URL 参数（Payload）

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `aep` | `22` | AI 模式专用标记，与 /search?aep=22 一致 |
| `sca_esv` | `ad175a4a610f2e0b` | Session Content Aware ESV，会话级内容安全校验值，两次调用该值可能不同 |
| `source` | `hp` | 来源标识：hp = HomePage（Google 主页入口） |
| `udm` | `50` | UI Display Mode，50 = AI Mode，与 /search?udm=50 一致 |
| `reqpld` | `[null,null,0]` | 请求 Payload（Request Payload 的 URL 编码形式），JSON 数组，含分页/筛选参数 |
| `msc` | `gwsclient` | 客户端类型标识：gwsclient = GWS（Google Web Server）客户端 |
| `opi` | `89978449` | AI Mode Surface ID，与 GetAsyncData [13]、/log [17] 中的数字完全一致 |

### Response Headers（关键字段）

| 字段 | 值 | 说明 |
|------|----|------|
| `Accept-Ch` | Downlink, RTT, Sec-CH-UA-Form-Factors, Sec-CH-UA-Platform, Sec-CH-UA-Platform-Version, Sec-CH-UA-Full-Version, Sec-CH-UA-Arch, Sec-CH-UA-Model, Sec-CH-UA-Bitness, Sec-CH-UA-Full-Version-List, Sec-CH-UA-WoW64 | 服务端请求大量 UA Client Hints，包含网络状态、设备架构、操作系统版本等 |
| `Cache-Control` | `no-cache, must-revalidate` | 禁止缓存，每次必须重新验证（对话历史实时性要求高） |
| `Content-Disposition` | `attachment; filename="1txt"` | **与 /complete/search 相同的 XSSI 防劫持头**，强制下载而非直接渲染 |
| `Content-Encoding` | `br` | Brotli 压缩（与 /complete/search 相同） |
| `Content-Security-Policy` | `object-src 'none'; base-uri 'self'; script-src 'nonce-{nonce}' 'strict-dynamic' ...` | 严格 CSP 策略 |
| `Cross-Origin-Opener-Policy` | `same-origin-allow-popups; report-to="gws"` | 跨源开启隔离 |
| `Permissions-Policy` | `unload=()` | 禁止 unload 事件 |
| `Pragma` | `no-cache` | HTTP/1.1 兼容的无缓存标记 |
| `Report-To` | `{"group":"gws", "max_age":2592000, "endpoints":[...csp.withgoogle.com...]}` | CSP 违规上报端点 |
| `Reporting-Endpoints` | `default="{csp.withgoogle.com/csp/gws-team}"` | 安全报告端点 |
| `Set-Cookie` | SIDCC + __Secure-1PSIDCC + __Secure-3PSIDCC | 刷新三个安全 Cookie |

> **规律发现**：ListThreads 的响应头特征与 `/complete/search` 高度相似——同样使用 `Content-Disposition: attachment; filename="1txt"` 和 Brotli 压缩，说明两者都经过 GWS 的同一安全层处理，响应体可能同样带有 XSSI 安全前缀（需剥离后才能解析 JSON）。

### 接口路径解析

```
/httpservice/web/AimThreadsService/ListThreads
  │
  ├─ /httpservice/web/   → GWS HTTP Service 包装层（将内部 RPC 服务暴露为 HTTP 接口）
  ├─ AimThreadsService   → AI Mode Thread 服务（管理 AI 对话历史）
  └─ ListThreads         → 列表方法（返回 Thread 列表）
```

服务命名规律：`Aim` 前缀 = AI Mode（与路径 `/httpservice/web/Aim*` 一致），`ThreadsService` 管理对话线程，`ListThreads` 对应 gRPC 风格的 List 方法。

---

## 十七、前端 JS 资源包（xjs Bundle）

> **注意**：本节记录的不是 API 接口，而是 AI Mode 前端代码的静态资源加载机制，便于理解整体架构。

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径示例 | `https://www.google.com/xjs/_/js/md=2/k=xjs.aimh_d.zh.CCka0IlbpDM.2019.O/am={模块位掩码}/rs=ACT90oF4qeN7zLCuhZpa6mwSBv8eO0UzGQ` |
| 请求方法 | GET |
| 响应类型 | `text/javascript` |
| 缓存策略 | `Cache-Control: public, immutable, max-age=31536000`（**1 年强缓存**） |
| 加载状态 | `200 OK (from disk cache)`（已从磁盘缓存加载，0ms 网络耗时） |
| 触发时机 | 进入 AI 对话界面时加载，通常命中缓存 |

### URL 参数解析

| 参数 | 示例值 | 说明 |
|------|--------|------|
| `md` | `2` | 模块描述格式版本 |
| `k` | `xjs.aimh_d.zh.CCka0IlbpDM.2019.O` | **Bundle 标识键**，格式见下表 |
| `am` | `AAAA...（超长 Base64 位掩码）` | **模块位掩码（Module Bitmask）**：每一位代表一个 JS 模块是否启用，决定打包哪些代码 |
| `rs` | `ACT90oF4qeN7zLCuhZpa6mwSBv8eO0UzGQ` | **资源签名哈希**，用于缓存破坏（Cache-busting）和完整性校验 |

### Bundle Key（k 参数）解析

```
xjs.aimh_d.zh.CCka0IlbpDM.2019.O
 │    │    │  │            │    │
 │    │    │  │            │    └─ 构建变体标识（O = Optimized/Original）
 │    │    │  │            └────── 构建日期/版本（2019 为内部版本号）
 │    │    │  └─────────────────── 版本哈希（CCka0IlbpDM，每次发版变化）
 │    │    └────────────────────── 语言（zh = 中文）
 │    └─────────────────────────── 模块名：aimh_d = AI Mode Handler Desktop
 └──────────────────────────────── xjs = Google eXtended JavaScript 系统
```

### Response Headers（关键字段）

| 字段 | 值 | 说明 |
|------|----|------|
| `Cache-Control` | `public, immutable, max-age=31536000` | **1 年不变缓存**，immutable 表示内容永不更改（版本更新通过 rs 哈希区分） |
| `Age` | `28310` | 该资源已在 CDN 缓存约 7.9 小时 |
| `Content-Encoding` | `gzip` | gzip 压缩 |
| `Content-Length` | `2018` | 压缩后 2018 字节（含 chunk manifest） |
| `Content-Type` | `text/javascript; charset=UTF-8` | JavaScript 文件 |
| `Alt-Svc` | `h3=":443"; ma=2592000` | 支持 HTTP/3 |

### Preview 内容（chunkTypes）

```
chunkTypes: "10000111111101110001000101011111111000111111"  (18.0 kB)
```

`chunkTypes` 是一个二进制字符串，每一位（0/1）对应一个 JS 代码块（chunk）是否被包含在本次 Bundle 中。这是 Google xjs 系统的模块按需加载机制——`am` 位掩码参数决定加载哪些模块，服务端根据参数动态裁剪 JS 包体积。


---

## 十八、AI 查询接口完整说明（folif）

> 本章是对文档第二章"AI 查询接口"的完整补充，补充了完整 URL 参数、async 字段解析及 Response 说明。

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求完整路径 | `https://www.google.com/async/folif` |
| 请求方法 | GET |
| 触发时机 | 用户在输入框提交问题后触发 |
| 返回格式 | HTML 片段（`_fmt:adl`），由浏览器直接渲染展示 |

### 完整 URL 参数（Payload）

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `ei` | `04KoaZzyEavo7_UPqKyC8QY` | **Event ID（页面级）**：当前页面的事件唯一标识，与 bgasy/batchexecute 等接口共用同一 ei |
| `yv` | `3` | 接口版本号（yv = "Yet another Version"），固定值 3 |
| `aep` | `22` | AI 模式标识，与 /search?aep=22 一致 |
| `sca_esv` | `ad175a4a610f2e0b` | Session Content Aware ESV，会话级内容安全校验值 |
| `source` | `hp` | 来源：hp = Google 主页 |
| `udm` | `50` | UI Display Mode，50 = AI Mode |
| `stkp` | `Ad3YPqxKaWPX...Q8F` | **Search Token Key Parameter**：请求签名 Token，用于防篡改校验，每次请求唯一 |
| `cs` | `0` | Client State，客户端状态标志 |
| `csuir` | `0` | Client State UI Refresh，UI 刷新标志 |
| `elrc` | `CmowYTVGVH...` | **Extended LRC（对话上下文 Token）**：多轮对话时携带上轮的上下文，编码了对话历史引用，每轮对话后由服务端更新 |
| `q` | `你好` | 用户输入的问题文字 |
| `ved` | `1t:244952` | **Visit Event Data**：点击/请求事件数据，格式为 `{type}:{id}`，用于统计和上下文追踪 |
| `async` | `_fmt:adl,_snbasecss:...,_xsrf:...` | **异步渲染参数组**（见下方详细解析） |

### async 参数详细解析

`async` 字段是用逗号分隔的多个键值对，控制 AI 回复的渲染方式：

| 子参数 | 示例值 | 说明 |
|--------|--------|------|
| `_fmt` | `adl` | **响应格式（Format）**：`adl` = Async Data Loading，指定以 HTML 片段格式返回，浏览器直接注入 DOM |
| `_snbasecss` | `https://www.gstatic.com/_.../ss/k=search-next.aim.yFhdBPGw6AI.L.B1.O/am=EAIA.../...` | **基础 CSS URL**：AI Mode 回复渲染所需的样式表地址，包含 Bundle Key、模块位掩码，结构与 xjs JS Bundle 一致 |
| `_xsrf` | `AKPOr1S1Dh4bvvFznt0dg29SRCTRDgWk2g:1772651219449` | **XSRF Token**：跨站请求伪造防护 Token，格式为 `{token}:{timestamp}` |

> **_snbasecss 中的 am 模块位掩码**：与 xjs JS Bundle 的 am 参数机制相同，控制加载哪些 CSS 模块。可以从 `excm=` 参数中看到排除的模块列表（ASY0Wd, Aiz46d, AzSnD, DTOZZd 等），这些是从基础包中剔除的模块。

### Response（AI 回答渲染内容）

folif 接口返回的不是 JSON，而是**可直接注入 DOM 的 HTML 片段**（`_fmt:adl`）。Preview 标签中看到的就是渲染后的效果：

```
你好！很高兴能为您提供帮助。请问今天有什么我可以为您效劳的吗？

如果您有具体的问题或需要查找的信息，可以直接告诉我，我会为您提供精准的建议。

您是想了解某个特定话题，还是需要我帮您完成某项任务？

AI 回答可能包含错误。了解详情
[Search Labs] [响应良好] [响应较差]

→ 您想了解什么话题？
→ 您有今天想讨论的新闻吗？
→ 帮我查一下天气
```

| 内容类型 | 说明 |
|---------|------|
| 主回复文本 | Gemini 生成的回答，Markdown 渲染为 HTML |
| 免责声明 | "AI 回答可能包含错误" + 了解详情链接 |
| 反馈按钮 | Search Labs 标记、响应良好、响应较差（对应 /log 接口上报事件） |
| 推荐问题（Chips） | 底部推荐的跟进问题，点击后触发新一轮 folif 请求 |

> **重要**：folif 使用 `_fmt:adl` 返回 HTML 片段而非 JSON，这意味着 AI 的回答内容直接以 HTML 形式嵌入页面，无法从 Response 中获取结构化 JSON 数据。若需要结构化数据，需分析页面 DOM 或另找接口。

### folif vs batchexecute 的关系

```
用户提交问题
  │
  ├─→ GET /async/folif  ← 主请求，获取 AI 回答 HTML
  │        (异步渲染到 DOM)
  │
  └─→ POST /wizrpcui/.../batchexecute  ← 辅助请求，上报对话状态
           (gY9iS RPC，记录 AI 回复的 Thread 状态)
```

两者并行触发，folif 负责内容渲染，batchexecute 负责状态同步。

---

## 十九、批量 RPC 接口（batchexecute）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://www.google.com/wizrpcui/_/WizRpcUi/data/batchexecute` |
| 请求方法 | POST |
| 触发时机 | folif 请求完成后（AI 回复展示后）紧随触发 |
| 服务归属 | `WizRpcUi`（Wizard RPC UI），Google 通用 RPC-over-HTTP 框架 |
| 目的 | 批量执行 RPC 调用，本次调用 `gY9iS` 方法，用于同步 AI 对话的 Thread 状态（如 mstk 有效性） |

### URL 参数（Query String）

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `rpcids` | `gY9iS` | **本次 batch 中调用的 RPC 方法 ID**，多个用逗号分隔，本次只有 gY9iS |
| `source-path` | `/search` | 调用来源页面路径 |
| `hl` | `zh` | 界面语言 |
| `_reqid` | `11279` | 客户端请求序列号，每次递增 |
| `rt` | `c` | 返回类型：`c` = chunked（分块响应格式） |

### Request Form Data（POST Body）

| 字段 | 示例值 | 说明 |
|------|--------|------|
| `freq` | `[["gY9iS",[[10904,true]],null,null,"generic"]]` | **RPC 调用参数数组**，格式见下方解析 |
| `at` | `AKlEnShR9pu-J4IydRjKJmkk_otE:1772651219387` | **Anti-CSRF Token**：格式与 folif 的 _xsrf 类似，`{token}:{timestamp}` |

#### freq 字段解析

```json
[
  [
    "gY9iS",          // RPC 方法 ID
    [[10904, true]],  // 方法参数：10904 = Thread/消息 ID，true = 状态标志（已完成？）
    null,             // 保留字段
    null,             // 保留字段
    "generic"         // 调用类型标识
  ]
]
```

| 位置 | 值 | 说明 |
|------|----|------|
| `[0][0]` | `"gY9iS"` | RPC 方法名，与 URL 中 rpcids 一致 |
| `[0][1]` | `[[10904, true]]` | 方法参数，10904 为对话消息 ID，true 为完成状态 |
| `[0][4]` | `"generic"` | 调用分类 |

### Response 结构（分块格式）

Response 采用 WizRpcUi 的 **HTTP Chunked + XSSI** 格式：

```
)]}'                    ← XSSI 安全前缀（需剥离）

118                     ← 第一块长度（字节）
[["wrb.fr","gY9iS","[[[10904,true]]]",null,null,null,"generic"],
 ["di",38],
 ["af.httprm",37,"-4992609514330737408",6]]

25                      ← 第二块长度（字节）
[["e",4,null,null,154]]
```

**分块解析：**

| 消息类型 | 内容 | 说明 |
|---------|------|------|
| `wrb.fr` | `["gY9iS", "[[[10904,true]]]", null, null, null, "generic"]` | **WizRpc Frame Response**：gY9iS 方法的返回值，`[[[10904,true]]]` 确认消息 ID 10904 状态为 true（成功） |
| `di` | `38` | **Data Index**：数据序列号，用于客户端追踪响应顺序 |
| `af.httprm` | `[37, "-4992609514330737408", 6]` | **HTTP Request Metrics**：HTTP 请求度量，包含请求 ID、内部追踪 ID（负数长整型）、耗时指标 |
| `e` | `[4, null, null, 154]` | **End / Status 帧**：4 = 状态码（成功），154 = 总响应字节数或处理时间 |

> **WizRpcUi 框架说明**：路径 `/wizrpcui/_/WizRpcUi/data/batchexecute` 是 Google 内部通用的 RPC-over-HTTP 框架，多个 Google 产品（Search、Drive、Gmail 等）都使用同一框架。`batchexecute` 端点支持在单次 HTTP 请求中批量执行多个 RPC 方法（`rpcids` 可以是逗号分隔的列表），降低网络开销。


---

## 二十、后台异步 JS 加载接口（bgasy）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://www.google.com/async/bgasy` |
| 请求方法 | GET |
| 触发时机 | 进入 AI 对话界面时触发，与 GetAsyncData、ListThreads 并行发出，属于初始化阶段的一部分 |
| 响应格式 | `_fmt:jspb`（JSON Protocol Buffer），带 XSSI 前缀 |
| 目的 | 告知浏览器需要在**后台（Background）异步（Async）**预加载哪些 JS 文件，不阻塞主界面渲染 |

### 接口名称解析

```
bgasy = Background Async（后台异步）
/async/bgasy ← Google /async/ 框架下的后台资源调度接口
```

与 `/async/folif`（AI 查询）同属 `/async/` 路径下，但用途完全不同：folif 返回 AI 回复内容，bgasy 返回待加载的 JS 资源清单。

### URL 参数（Payload）

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `ei` | `04KoaZzyEavo7_UPqKyC8QY` | 页面级 Event ID，与 folif、batchexecute 共用同一个 ei |
| `opi` | `89978449` | AI Mode Surface ID，第四次出现，进一步确认为全局标识符 |
| `aep` | `22` | AI 模式标识，与其他 AI Mode 接口一致 |
| `sca_esv` | `ad175a4a610f2e0b` | 会话级内容安全校验值 |
| `source` | `hp` | 来源：hp = Google 主页 |
| `udm` | `50` | UI Display Mode，50 = AI Mode |
| `yv` | `3` | 接口版本号，与 folif 一致 |
| `cs` | `0` | Client State 标志 |
| `async` | `_fmt:jspb` | **响应格式指定**：`jspb` = JSON Protocol Buffer，与 folif 的 `adl` 不同 |

> **关键参数对比**：bgasy 使用 `async=_fmt:jspb`（JSON），而 folif 使用 `async=_fmt:adl,...`（HTML 片段），两者都通过 `async` 参数控制响应格式，但格式完全不同。

### Response 结构

响应采用 JSON Protocol Buffer 格式，带 XSSI 安全前缀：

```
)]}'
{
  "bgasy": [
    "https://www.google.com/js/bg/_COTswsSH9GjaEOfs_jf_S_v6j-opCtxrprjjeN8Dbt2.js",
    "..."
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| XSSI 前缀 | `)]}'` | 与 ListThreads、batchexecute 相同的 XSSI 安全前缀，客户端需先剥离此前缀再解析 JSON |
| `bgasy` | `string[]` | **待后台加载的 JS 文件 URL 数组**，每个 URL 指向 `/js/bg/` 路径下的脚本文件 |

### JS 文件 URL 解析

```
https://www.google.com/js/bg/_COTswsSH9GjaEOfs_jf_S_v6j-opCtxrprjjeN8Dbt2.js
                          │  │
                          │  └── 内容哈希（用于缓存破坏和完整性校验）
                          └───── /js/bg/ = Background JS 目录（专用于后台非关键脚本）
```

`/js/bg/` 路径下的脚本与 `/xjs/` 下的主 Bundle 不同：
- `/xjs/` → 主前端 Bundle，包含 AI Mode 核心功能代码，强缓存（1 年）
- `/js/bg/` → 后台非关键脚本，按需后台加载，通常是延迟初始化或可选功能模块

### 与其他接口的关系

```
进入 AI Mode 界面时并行触发的初始化接口群：
┌─────────────────────────────────────────────────┐
│  GET /v1/gsessionid          → 获取会话路由 ID  │
│  POST GetAsyncData (gRPC-Web) → 拉取异步通知    │
│  GET ListThreads              → 加载历史对话    │
│  GET bgasy                    → 获取待预加载 JS  ← 本接口
│  GET /xjs/.../rs=...         → 加载主 JS Bundle │
└─────────────────────────────────────────────────┘
```

bgasy 在整个初始化流程中属于**资源预调度**阶段：浏览器拿到 bgasy 返回的 URL 列表后，会在空闲时间后台加载这些脚本，不阻塞 AI 对话界面的首屏展示。

### 接口总结表更新（opi=89978449 出现位置汇总）

至此，`opi=89978449` 已在以下 5 个接口中出现：

| 接口 | 出现位置 |
|------|---------|
| `/async/folif` | URL 参数（通过 `async=...opi=...` 内嵌） |
| `/async/bgasy` | URL 参数 `opi=89978449` |
| `GetAsyncData` | Payload `[13]` 字段值 `89978449` |
| `/log` | Payload `[17]` 中嵌套 |
| `ListThreads` | URL 参数 `opi=89978449` |

这证明 `89978449` 是 AI Mode（`udm=50`）在 Google 系统中的全局唯一产品标识符（Surface ID），贯穿所有 AI Mode 相关接口。


---

## 二十一、CSS 模块按需加载（xjs /ss/ 系列）

> **说明**：本节与第十七章（JS Bundle）为同一套 xjs 资源系统，区别在于路径为 `/xjs/_/ss/`（StyleSheet）而非 `/xjs/_/js/`，专门负责加载 CSS 样式模块。

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径模式 | `https://www.google.com/xjs/_/ss/k={bundle_key}/am={bitmask}/.../m={modules}?xjs=s4` |
| 请求方法 | GET |
| 响应类型 | CSS（`text/css`） |
| 缓存策略 | `Cache-Control: public, immutable, max-age=31536000`（1 年强缓存，与 JS Bundle 相同） |
| 加载状态 | `200 OK (from disk cache)`（命中磁盘缓存，无网络请求） |
| 触发时机 | 进入 AI 界面时按需加载，多个并行请求，每个请求加载一组 CSS 模块 |

### 三个请求的 m 参数对比

| 请求 | `m=` 参数值 | 加载的 CSS 模块 |
|------|------------|----------------|
| 请求 1 | `sy1x8,Z0vsl,sy50o` | 3 个模块（组合加载） |
| 请求 2 | `syu8` | 1 个模块（单独加载） |
| 请求 3 | `sy7i7` | 1 个模块（单独加载） |

### URL 结构完整解析

```
https://www.google.com/xjs/_/ss/
  k=xjs.aimh_d.H3zs-IUKkb0.L.B1.O   ← Bundle Key（与 JS Bundle 完全相同）
  /am=AAAIA...BA                      ← 模块位掩码（Module Bitmask，与 JS Bundle 相同）
  /d=0                                ← Debug 标志：0 = 生产模式
  /br=1                               ← Brotli 支持：1 = 支持
  /rs=ACT90oFf3-nZ_cD0jyuDG_gJ64z2rP6_JQ  ← 资源签名哈希（与 JS Bundle 不同，CSS 有独立哈希）
  /cb=loaded_h_0                      ← Callback 名称：loaded_h_0（加载完成回调）
  /m=sy1x8,Z0vsl,sy50o                ← 本次加载的具体 CSS 模块 ID 列表
  ?xjs=s4                             ← xjs 版本标识：s4
```

### xjs /ss/ vs /js/ 对比

| 维度 | `/xjs/_/js/`（JS Bundle） | `/xjs/_/ss/`（CSS 模块） |
|------|--------------------------|-------------------------|
| 用途 | JavaScript 功能代码 | CSS 样式规则 |
| Bundle Key（k=） | 相同（`xjs.aimh_d.H3zs-IUKkb0.L.B1.O`） | 相同 |
| 模块位掩码（am=） | 相同的 Base64 位掩码 | 相同的 Base64 位掩码 |
| 资源哈希（rs=） | `ACT90oFf3-nZ_...JQ`（独立） | `ACT90oFf3-nZ_...JQ`（与 JS 相同） |
| 回调（cb=） | `loaded_h_0` | `loaded_h_0` |
| m= 参数 | 一次性加载整个 Bundle | 按 CSS 模块 ID 分批加载 |
| 缓存策略 | 1 年强缓存，immutable | 1 年强缓存，immutable |
| 版本标识 | `?xjs=s4` | `?xjs=s4` |

### CSS 模块 ID 命名规律

```
sy1x8  → "sy" 前缀 + 随机哈希（Search Y 系列的模块标识）
Z0vsl  → 大写字母开头，区分大小写
sy50o  → 与 sy1x8 同类
syu8   → "sy" 前缀，单字符序号
sy7i7  → "sy" 前缀，混合序号
```

CSS 模块 ID 遵循 Google 的混淆命名规范（与 HTML 中的 class 名称如 `.AgWCw`、`.pTDPyc` 类似），均为编译时生成的缩短标识符。

### 加载架构总结

```
xjs 资源系统（同一 Bundle Key + am 位掩码）
├── /xjs/_/js/...    → JavaScript 功能代码（整体加载）
└── /xjs/_/ss/...    → CSS 样式代码（按模块 ID 分批加载）
    ├── m=sy1x8,Z0vsl,sy50o  （第一批，3 个模块）
    ├── m=syu8               （第二批，1 个模块）
    └── m=sy7i7              （第三批，1 个模块）
```

xjs 系统通过相同的 Bundle Key 和位掩码统一管理 JS 与 CSS 资源版本，实现原子化发布（JS 和 CSS 版本始终对应）。CSS 模块支持细粒度按需加载，可以只加载页面当前用到的样式，减少无效 CSS 传输。


---

## 二十三、主页后台初始化接口（hpba）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://www.google.com/async/hpba` |
| 接口全称 | **Homepage Background Async（主页后台异步初始化）** |
| 请求方法 | GET |
| 响应格式 | `_fmt:prog`（Progressive / 渐进式流式传输），带 XSSI 前缀 |
| 触发时机 | 进入 AI Mode 界面初始化阶段，排列在 GetAsyncData / ListThreads 之后，bgasy 之前 |
| 核心职责 | 向客户端一次性传递三种基础资源的 Bundle URL（JS + CSS + 组合包），并注入初始 HTML 占位结构 |

---

### URL 参数完整解析

#### 标准参数

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `vet` | `12ahUKEwiIo62p8IeTAxXb...` | **Visit Event Token**：与 folif 的 `ved` 格式相同，用于追踪用户访问路径 |
| `ei` | `lQCpaciEJ9uDxc8P25a3oA0` | **Event ID**：页面级唯一事件标识，与其他接口共享同一个 ei |
| `opi` | `89978449` | **AI Mode Surface ID**：第五次出现（hpba、bgasy、folif、GetAsyncData、ListThreads） |
| `aep` | `26` | **⚠️ 注意：hpba 使用 aep=26，而非其他 AI Mode 接口的 aep=22**，说明 hpba 属于不同的功能子系统 |
| `sca_esv` | `ad175a4a610f2e0b` | 会话级内容安全校验值，与全局会话一致 |
| `source` | `hp` | 来源：hp = Google 主页（Homepage） |
| `udm` | `50` | UI Display Mode：50 = AI Mode |
| `yv` | `3` | 接口版本号 |
| `q` | `你好`（URL 编码：`%E4%BD%A0%E5%A5%BD`） | **当前查询词**，hpba 携带用户的实际问题，用于在初始化时预热相关资源 |

#### hpba 专属参数（其他接口无此参数）

| 参数名 | 示例值 | 说明 |
|--------|--------|------|
| `sp_imghp` | `false` | **Image Homepage**：是否为图片主页模式，false = 文字对话模式 |
| `sp_hpte` | `0` | **Homepage Type Extension**：主页类型扩展标志，0 = 默认类型 |
| `sp_hpep` | `3` | **Homepage Entry Point**：入口点标识，3 = 通过 AI 对话框进入 |
| `sp_aae` | `0` | **Auto Answer Enable**：自动回答标志，0 = 关闭 |
| `stick` | （空） | 粘性参数，用于固定特定搜索上下文（本次为空） |
| `aioh` | `0` | **AI Override Hint**：AI 模式覆盖提示，0 = 不强制覆盖 |
| `ntc` | `0` | **New Tab Count**：新标签页计数，0 = 非新标签页打开 |
| `mstk` | `AUtExfA9Nd9ugUe3...（长 Token）` | **Module State Token**：模块状态签名令牌，包含当前页面已加载的模块状态，服务端用于决定 hpba 需要返回哪些补充资源，防止重复加载 |

#### async 参数（最复杂，包含三个 Bundle 配置）

`async` 参数值由逗号分隔的多个键值对组成，本次传入了 5 个键：

```
async=
  _basejs:{BASE_JS_URL},
  _basecss:{BASE_CSS_URL},
  _basecomb:{BASE_COMB_URL},
  _fmt:prog,
  _id:nh7Mab
```

**`_basejs`** — 基础 JavaScript Bundle URL：
```
/xjs/_/js/k=xjs.aimh_d.zh.q6J5ixOY29c.2019.O
  /am={bitmask}
  /dg=0/br=1/ichc=1
  /rs=ACT90oH1BLI-oOwM1RvC2JaFo_ZR17dfvw
  /cb=loaded_h_0
```

**`_basecss`** — 基础 CSS Bundle URL：
```
/xjs/_/ss/k=xjs.aimh_d.EaP6mBllLJA.L.B1.O
  /am={bitmask}
  /br=1
  /cb=loaded_h_0
  /rs=ACT90oHtct_arLVXFam5lyK3wIY5zwpeoA
```

**`_basecomb`** — **组合 Bundle URL（JS+CSS 合并）**：
```
/xjs/_/js/k=xjs.aimh_d.zh.q6J5ixOY29c.2019.O
  /ck=xjs.aimh_d.EaP6mBllLJA.L.B1.O   ← 同时包含 JS key 和 CSS key
  /am={combined_bitmask}
  /d=1/ed=1/dg=0/br=1/ujg=1/ichc=1
  /rs=ACT90oH2j55EkqGfjhwqhgnOD1gm95PpRA
  /cb=loaded_h_0
```

| async 子键 | 说明 |
|-----------|------|
| `_basejs` | 纯 JS Bundle URL，服务端用于验证客户端当前已加载的 JS 版本 |
| `_basecss` | 纯 CSS Bundle URL，同上 |
| `_basecomb` | JS+CSS 组合 Bundle，包含两个 key（`k=` JS版本，`ck=` CSS版本），额外参数 `d=1/ed=1/ujg=1` 表示调试/增量/UJG(Unified JS Generator) 模式，是最完整的版本描述 |
| `_fmt:prog` | **响应格式：渐进式流式传输**（区别于 folif 的 `adl` HTML 模式和 bgasy 的 `jspb` JSON 模式） |
| `_id:nh7Mab` | **目标 DOM 元素 ID**：服务端返回的 HTML 片段将被注入到页面中 `id="nh7Mab"` 的元素内 |

---

### Response 格式详解（prog 渐进式流式传输）

原始响应（逐块解析）：

```
)]}'
21;["nQCpad3gCIXZ7M8PnuS-CQ","2389"]
c;[2,null,"0"]
1b;<div jsname="Nll0ne"></div>
c;[9,null,"0"]
0;
```

格式规则：每行由 `{十六进制长度};{内容}` 组成：

| 原始行 | 十六进制长度 | 解码字节数 | 内容类型 | 内容解析 |
|--------|------------|----------|---------|---------|
| `)]}'` | — | — | XSSI 前缀 | 标准防劫持前缀，客户端剥离后再解析 |
| `21;[...]` | `0x21` = 33字节 | 33 | **页面初始化 Token** | `["nQCpad3gCIXZ7M8PnuS-CQ", "2389"]`，第一个元素为页面会话 Nonce，第二个为序列号 |
| `c;[2,null,"0"]` | `c`（控制帧） | — | **控制指令** | `[2, null, "0"]`：操作码 2，目标 null，参数 "0"（可能为"准备就绪"信号） |
| `1b;<div ...>` | `0x1b` = 27字节 | 27 | **HTML 片段** | `<div jsname="Nll0ne"></div>`：注入页面的 HTML 占位容器 |
| `c;[9,null,"0"]` | `c`（控制帧） | — | **控制指令** | `[9, null, "0"]`：操作码 9（可能为"渲染完成"信号） |
| `0;` | `0x0` = 0字节 | 0 | **流结束** | 空块，标识流式传输结束（类似 HTTP Chunked Transfer 的 `0\r\n\r\n`） |

#### prog 格式与其他接口响应格式对比

| 接口 | `_fmt` 值 | 响应内容 | 适用场景 |
|------|----------|---------|---------|
| `hpba` | `prog`（渐进式） | 控制帧 + HTML 片段，流式推送 | 初始化阶段的 HTML 骨架注入 |
| `folif` | `adl`（异步数据加载） | 完整 AI 回复 HTML | AI 回复内容注入 |
| `bgasy` | `jspb`（JSON Protobuf） | JSON 数组（JS URL 列表） | 后台资源 URL 分发 |
| `batchexecute` | `c`（分块） | HTTP Chunked + XSSI | RPC 状态同步 |

#### `jsname="Nll0ne"` 含义

`jsname` 是 Google Closure 编译器（Closure Compiler）的模板绑定属性，`Nll0ne` 是混淆后的组件名称。这个空 `<div>` 是 AI Mode 界面某个功能区块的**占位容器**，后续由 JS 代码通过 `jsname` 属性找到该 DOM 节点并填充内容。

---

### hpba 在初始化流程中的作用

```
初始化阶段请求流：
┌──────────────────────────────────────────────────────────────┐
│ GetAsyncData  → 检查是否有异步通知                           │
│ ListThreads   → 加载历史对话列表                             │
│ hpba          → 发送当前 Bundle 版本 + 首个问题 q=           │
│                 ↓                                            │
│                 服务端核验 mstk（Module State Token）         │
│                 ↓                                            │
│                 返回：Bundle URL 配置 + HTML 占位结构         │
│ bgasy         → 获取后台 JS 文件清单                          │
│ folif         → 执行实际 AI 查询                              │
└──────────────────────────────────────────────────────────────┘
```

hpba 的独特之处在于它是初始化流程中**唯一携带 `q=` 问题内容的非 AI 查询接口**，说明它需要根据用户输入的问题来决定加载哪些模块（通过 `mstk` 和 Bundle 位掩码配合实现）。

---

### aep=26 vs aep=22 差异分析

| 参数值 | 使用接口 | 推断含义 |
|--------|---------|---------|
| `aep=22` | folif、bgasy、ListThreads | AI Mode 主查询/数据流子系统 |
| `aep=26` | hpba | AI Mode 主页初始化子系统（Homepage Initialization） |

`aep`（Application Endpoint / Feature Flag）的不同值标识了 AI Mode 内部不同的功能子系统，服务端据此路由到不同的处理逻辑。


---

## 二十二、Cookie 轮换接口（RotateCookies）

### 基本信息

| 项目 | 内容 |
|------|------|
| 请求路径 | `https://accounts.google.com/RotateCookies` |
| 请求方法 | POST |
| 触发时机 | 每隔 600 秒（10 分钟）周期性触发，在 AI 对话全程持续运行 |
| 服务归属 | `accounts.google.com`（Google 账号安全服务） |
| 核心目的 | **在 HTTP Response Header 层静默替换核心身份 Cookie**，防止长期有效的静态 Cookie 被截获滥用 |

### 为什么需要 RotateCookies？

传统网站的 Session Cookie 可能数月不变，但这对 Google 这种高安全级别的生态是不可接受的。RotateCookies 解决两个问题：

**1. 安全防御（防止 Cookie 盗用）**：若黑客通过 XSS 或恶意插件窃取了 `__Secure-1PSID` 等核心 Cookie，可以伪造用户身份。RotateCookies 通过定期让旧 Cookie 失效、生成全新值，将被盗 Cookie 的可利用时间窗口压缩到 10 分钟以内。

**2. 无缝续期（保持会话活跃）**：只要浏览器处于活跃状态，该接口定期向服务器证明"用户仍在使用"，服务器下发新的更长生命周期 Cookie，使用户无需频繁重新输入密码。

### Request Payload

```json
[1, "-4790807444101731124"]
```

| 位置 | 值 | 说明 |
|------|----|------|
| `[0]` | `1` | 操作类型：1 = 轮换（Rotate），固定值 |
| `[1]` | `"-4790807444101731124"` | **当前 Cookie 的身份标识符**，负数长整型字符串（与 batchexecute 响应中 `af.httprm` 格式相同），服务端用于验证当前 Cookie 合法性后才生成新 Cookie |

### Response Body

响应带 XSSI 安全前缀：

```
)]}'
[["identity.hfcr", 600], ["di", 24]]
```

#### XSSI 前缀 `)]}'` 的安全机制

此前缀是 Google 首创的**防 JSON 劫持（XSSI, Cross-Site Script Inclusion）**机制：
- **攻击原理**：早年黑客可在恶意网站用 `<script src="https://accounts.google.com/RotateCookies">` 标签，利用浏览器自动跨域携带 Cookie 的特性，将返回的 JSON 数组当做 JS 代码执行并窃取数据
- **防御效果**：加上 `)]}'` 后，浏览器解析 `<script>` 标签时遇到该前缀会立即抛出 JS 语法错误，阻断执行
- **合法读取方式**：Google 前端代码通过 XHR/Fetch API 获取纯文本响应后，手动切割掉第一行 `)]}'`，剩余内容即为合法 JSON，可安全执行 `JSON.parse()`

#### Response Body 字段解析

| 字段 | 值 | 含义 |
|------|----|------|
| `identity.hfcr` | `600` | **Host/First-party Cookie Rotation 成功指令**：`hfcr` = Host Facet Cookie Rotation；`600` 为 TTL（秒），告知前端"请在 600 秒后再次发起轮换"，这正是该接口每 10 分钟出现一次的直接原因 |
| `di` | `24` | **Data Index（数据序列号）**：前端状态机同步用的版本计数器，值 24 表示当前身份策略已更新到第 24 个节点；与 batchexecute 中的 `di` 字段同义 |

### Response Headers（核心：Set-Cookie）

> **此接口真正的核心动作不在 Body，而在 Response Headers 的 Set-Cookie 指令中。**

从截图确认的完整响应头：

| Header | 值 | 说明 |
|--------|----|------|
| `Content-Type` | `application/json; charset=utf-8` | 标准 JSON 响应 |
| `Cache-Control` | `no-cache, no-store, max-age=0, must-revalidate` | **严格禁止缓存**，每次必须向服务端实时获取新 Cookie |
| `Expires` | `Mon, 01 Jan 1990 00:00:00 GMT` | 过去的时间，强制浏览器不缓存（与 Cache-Control 双重保险） |
| `Pragma` | `no-cache` | HTTP/1.0 兼容的缓存禁止指令 |
| `Server` | `GSE` | **Google Server Engine**（Google 自研服务器） |
| `Cross-Origin-Opener-Policy` | `same-origin` | 跨域开启者策略，防止跨源窗口访问 |
| `Cross-Origin-Embedder-Policy` | `require-corp` | 要求跨源资源声明 CORP 头 |
| `Strict-Transport-Security` | （存在） | 强制 HTTPS，防止降级攻击 |
| `X-Xss-Protection` | `0` | 禁用浏览器内置 XSS 过滤器（Google 使用自己的 CSP 策略代替） |
| `X-Frame-Options` | `SAMEORIGIN` | 防止 iframe 嵌套点击劫持 |

**Set-Cookie 替换列表**（从截图观察到的被轮换的 Cookie）：

| 被替换的 Cookie | 有效期 | 属性 | 说明 |
|----------------|--------|------|------|
| `__Secure-1PSID` | 2027-03-05（1年） | Secure; HttpOnly; Priority=HIGH; SameSite=None | 第一方主会话 Cookie，轮换后旧值立即失效 |
| `__Secure-3PSID` | 2027-03-05（1年） | Secure; HttpOnly; Priority=HIGH; SameSite=None | 第三方主会话 Cookie，同步替换 |
| `SIDCC` | （随新值更新） | — | 会话 Cookie 计数器，同步更新以匹配新 SID |
| `__Secure-1PSIDCC` | — | Secure; Priority=HIGH; SameSite=None | 第一方 Cookie Counter，随 1PSID 同步轮换 |
| `__Secure-3PSIDCC` | — | Secure; Priority=HIGH; SameSite=None | 第三方 Cookie Counter，随 3PSID 同步轮换 |
| `__Secure-1PSIDTS` | — | Secure | 第一方会话时间戳，更新为当前轮换时间 |

> **关键特性**：新旧 Cookie 的替换是**原子操作**——服务端在同一个 HTTP 响应中通过多个 Set-Cookie 头一次性替换所有相关 Cookie，确保 1PSID / 3PSID / SIDCC / PSIDCC / PSIDTS 这一组 Cookie 的版本始终保持一致，不会出现新旧混用导致身份验证失败的情况。

### 轮换生命周期时序

```
进入 AI Mode 页面
        │
        ▼
RotateCookies（第1次，初始化）
        │
        ▼
AI 对话进行中（folif、batchexecute、log...）
        │
   每 600 秒
        │
        ▼
RotateCookies（第N次，周期轮换）
  ├─ Body: identity.hfcr=600 → 客户端设置下次轮换定时器
  └─ Set-Cookie: 静默替换 __Secure-1PSID / 3PSID / SIDCC 等
        │
        ▼
  继续 AI 对话（使用新 Cookie 鉴权）
```

### 与 accounts.google.com 域名下其他接口对比

| 接口 | 路径 | 触发场景 | 目的 |
|------|------|---------|------|
| `ListAccounts` | `/ListAccounts` | 账号验证流程（图片生成及对话过程中） | 读取账号信息，验证登录状态 |
| `RotateCookies` | `/RotateCookies` | 所有 AI Mode 会话，每 600 秒 | 静默替换核心身份 Cookie，缩小被盗用的时间窗口 |


---

## 附录 A：Cookie 体系完整分析

本附录基于 DevTools Application → Cookies 面板，对 AI Mode 涉及的三个域名下的所有 Cookie 进行完整记录和分析。

---

### A.1 www.google.com 域名下的 Cookie

| Cookie 名称 | 示例值（截断） | 大小 | Secure | HttpOnly | SameSite | 作用与说明 |
|------------|--------------|------|--------|----------|----------|-----------|
| `__Secure-1PAPISID` | `6EQPfWmqcJWDkluf/Aq8sVPtU...` | 51 | ✓ | — | — | **Google API 会话 ID（1P 版）**：用于第一方（same-site）请求的 API 身份认证，配合 SAPISID 生成 SAPISIDHASH |
| `__Secure-1PSID` | `g.a0007Qh2jM67zfcZ-b1igMvRk...` | 167 | ✓ | ✓ | — | **第一方安全会话 ID**：核心身份认证 Cookie，HttpOnly 防止 JS 读取，是登录状态的主要凭证 |
| `__Secure-1PSIDCC` | `AKEyXzUV2tqVtok1iBu-sJtlkUgA...` | 91 | ✓ | ✓ | — | **1P 会话 CC（Cookie Counter）**：用于检测 Cookie 篡改和异常登录，由 RotateCookies 周期刷新 |
| `__Secure-1PSIDTS` | `sidts-CJEBBj1CYgn3NoLV16Zqlt...` | 93 | ✓ | — | — | **1P 会话时间戳（Timestamp）**：记录会话 Cookie 最后刷新时间，防止重放攻击 |
| `__Secure-3PAPISID` | `6EQPfWmqcJWDkluf/Aq8sVPtU...` | 51 | ✓ | — | None | **Google API 会话 ID（3P 版）**：用于第三方（cross-site）请求，SameSite=None 允许跨域携带，用于嵌入场景 |
| `__Secure-3PSID` | `g.a0007Qh2jM67zfcZ-b1igMvRk...` | 167 | ✓ | ✓ | None | **第三方安全会话 ID**：与 1PSID 配对，用于跨域场景，如 Google 服务嵌入第三方页面 |
| `__Secure-3PSIDCC` | `AKEyXzU2UBOD42YirdCRPxGo6X1...` | 91 | ✓ | ✓ | None | **3P 会话 CC**：第三方场景的 Cookie 计数器，同样由 RotateCookies 刷新 |
| `__Secure-3PSIDTS` | `sidts-CJEBBj1CYgn3NoLV16Zqlt...` | 93 | ✓ | — | None | **3P 会话时间戳**：第三方场景的时间戳防重放 |
| `__Secure-BUCKET` | `CNAE` | 19 | ✓ | — | — | **A/B 测试分桶（Bucket）**：将用户分配到特定实验组，`CNAE` 为分桶编码（Base64 Protobuf），影响功能特性的开关 |
| `__Secure-ENID` | `32.SE=7f4EIeb-5Qi5mZrX0iTo8d...` | 405 | ✓ | — | Lax | **增强网络 ID（Enhanced Network ID）**：格式 `{版本}.SE={token}`，版本号 32，用于个性化和广告相关的扩展身份标识 |
| `__Secure-OSID` | `g.a0007QjP_urSDt9GrrVmPBuIVr...` | 166 | ✓ | — | None | **原始会话 ID（Original Session ID）**：跨域场景的原始会话标识，用于多产品间的会话关联 |
| `__Secure-STRP` | `AD6DoguqQdlhva9c6aztWArMu...` | 113 | ✓ | — | Strict | **安全令牌（Secure Token Rotation Prevention）**：SameSite=Strict 最严格保护，防止 CSRF，仅 same-site 请求携带 |
| `_ga` | `GA1.1.1905956853.1772211628` | 30 | — | — | — | **Google Analytics 客户端 ID**：GA4 的设备级唯一标识，格式 `GA1.{version}.{clientId}.{timestamp}`，用于统计分析（非认证） |
| `_ga_6VGGZHLMLM2` | `GS2.1.s17722116295o15g1St17...` | 59 | — | — | — | **GA4 会话级追踪**：特定 GA4 数据流的会话状态，记录会话开始时间和页面浏览数 |
| `_gcl_au` | `1.1.1386131360.1772211629` | 32 | — | — | — | **Google Ads 转化链接器（Conversion Linker）**：用于跨域归因广告转化，追踪用户点击广告后的行为 |
| `AEC` | `AaJma5t_QkFTwkTl_cI2DKIHfSV...` | 61 | ✓ | — | Lax | **Anti-Abuse Enforcement Cookie**：反滥用机制 Cookie，用于检测和阻止自动化脚本、爬虫和账号滥用行为 |
| `APISID` | `APA_URZFwv63_TLL/AQJAaaAyjC...` | 40 | — | — | — | **API Session ID**：非安全版本的 API 会话 ID，早期遗留 Cookie，现已被 `__Secure-*PAPISID` 系列取代 |
| `DV` | `M3Lh97AYe85LIBy4P1MyROuvk...` | 80 | — | — | — | **Device Verification Token**：设备验证令牌，用于异常登录检测（如新设备、新地点），与安全评分相关 |
| `HSID` | `A7Ok4u_OQO_AJ520p` | 21 | — | ✓ | — | **HTTPS Session ID**：早期安全会话 Cookie，HttpOnly，现已被 `__Secure-1PSID` 系列取代，仍作为兼容性保留 |
| `NID` | `529=MDmwYuqwZzeOhr5xpGA...` | 1417 | — | ✓ | — | **Notice/Network ID**：**最大的 Cookie（1417 字节）**，HttpOnly，存储大量用户偏好设置（语言、安全搜索、结果数量等），也包含 CSRF 防护 Token 和会话上下文 |
| `OSID` | `g.a0007QjP_urSDt9GrrVmPBuIVr...` | 157 | — | — | — | **非安全版原始会话 ID**：`__Secure-OSID` 的非 HTTPS 兼容版本，保留用于兼容 |
| `OTZ` | `8498461_24_24_24` | 21 | — | — | — | **One-Time Zone Cookie**：存储用户时区信息（格式 `{id}_{offset}_{...}`），用于本地化显示 |
| `SAPISID` | `6EQPfWmqcJWDkluf/Aq8sVPtU...` | 41 | ✓ | — | — | **Secure API Session ID**：所有 API 请求的 Authorization Header（`SAPISIDHASH`）由此 Cookie 的值 + 时间戳 + Origin SHA1 哈希生成 |
| `SEARCH_SAMESITE` | `CgQIo6AB` | 23 | — | — | Strict | **Search SameSite 标志**：Base64 编码的 Protobuf，包含 Search 功能特性的 SameSite 相关配置 |
| `SID` | `g.a0007Qh2jM67zfcZ-b1igMvRk...` | 156 | — | — | — | **Session ID**：早期主会话 Cookie，现已被 `__Secure-1PSID` 取代，仍保留用于 HTTP（非 HTTPS）兼容场景 |
| `SIDCC` | `AKEyXzWE1yyCEwqsJnATxsHG3...` | 80 | — | — | — | **Session Cookie Counter**：会话 Cookie 计数器，用于检测 Cookie 被篡改或复制，与 `__Secure-1PSIDCC` 配对（非安全版） |
| `SOCS` | `CAAbBgiAvYPNBg` | 18 | — | — | Lax | **Same-Origin Cookie Settings**：Base64 Protobuf，存储用户的 Cookie 同意/拒绝设置（GDPR/隐私合规相关） |
| `SSID` | `Az2POOfrDWlqXdSqt` | 21 | — | ✓ | — | **Secure Session ID**：早期安全会话 Cookie，HttpOnly，现已被新版取代，保留兼容 |

---

### A.2 accounts.google.com 域名下的 Cookie

> 此域名负责 Google 账号认证，Cookie 与 `ListAccounts`、`RotateCookies` 接口直接相关。

| Cookie 名称 | 大小 | Secure | HttpOnly | SameSite | 作用与说明 |
|------------|------|--------|----------|----------|-----------|
| `__Host-1PLSID` | 21 | ✓ | ✓ | — | **Host 级第一方登录 Session ID**：`__Host-` 前缀是最高安全级别，强制 Path=/、无 Domain，防止子域 Cookie 污染，用于账号登录状态 |
| `__Host-3PLSID` | 194 | ✓ | ✓ | — | **Host 级第三方登录 Session ID**：跨域场景的账号登录 Cookie，同样 `__Host-` 最高安全级别 |
| `__Secure-GAPS` | 124 | ✓ | — | — | **Google Accounts Persistent Session**：账号持久化会话 Token，用于"保持登录"功能，有效期较长 |
| `__Secure-1PAPISID/3PAPISID` | 51 | ✓ | — | — | 与 google.com 共享的 API Session ID（跨域同步） |
| `__Secure-1PSID/3PSID` | 167 | ✓ | ✓ | — | 与 google.com 共享的主会话 Cookie（跨域同步） |
| `__Secure-1/3PSIDCC` | 90/91 | ✓ | ✓ | — | 与 google.com 共享的 Cookie Counter（跨域同步） |
| `__Secure-BUCKET/ENID/STRP` | — | ✓ | — | — | 与 google.com 共享的分桶/增强 ID/安全令牌 |
| `ACCOUNT_CHOOSER` | 305 | ✓ | — | — | **账号选择器状态**：记录多账号切换器的状态，存储账号列表和上次使用的账号，供 `ListAccounts` 接口使用 |
| `LSID` | 185 | ✓ | ✓ | — | **Login Session ID**：账号登录专用 Session Cookie，HttpOnly 保护 |
| `LSOLH` | 129 | ✓ | — | — | **Login Session One-Login Hash**：单点登录（SSO）的哈希验证 Cookie，防止会话固定攻击 |
| `SMSV` | 166 | ✓ | ✓ | — | **Session Management Security Version**：账号会话安全版本标识，用于追踪账号安全状态变化（如密码修改、安全设置变更后强制重新验证） |
| `OTZ` | 21 | — | — | — | 时区 Cookie（与 google.com 共享） |
| `NID/SAPISID/...` | — | — | — | — | 与 google.com 共享的通用 Cookie |

---

### A.3 ogs.google.com 域名下的 Cookie

> `ogs.google.com`（One Google Shell）是 Google 统一 Shell 服务域名，负责跨产品的顶部导航栏（用户头像、Google 产品切换器等）。

| Cookie 名称 | 大小 | Secure | 说明 |
|------------|------|--------|------|
| `__Secure-1/3PAPISID` | 51 | ✓ | 跨域同步的 API Session ID |
| `__Secure-1/3PSID` | 167 | ✓ | 跨域同步的主会话 Cookie |
| `__Secure-1/3PSIDCC` | 91/93 | ✓ | Cookie Counter，由 RotateCookies 同步刷新 |
| `__Secure-BUCKET/ENID/STRP` | — | ✓ | 分桶/增强 ID/安全令牌（跨域同步） |
| `_ga/_ga_*` | 28/59 | — | GA4 统计 Cookie（跨域共享） |
| `OTZ` | 21 | — | 时区 Cookie |
| `OTZ`（第二条） | 21 | — | `OTZ` 在 ogs 下有两条，可能对应不同路径 |
| `SIDCC` | 80 | — | Cookie Counter 非安全版（兼容） |
| `SOCS` | 18 | — | Cookie 同意设置 |

---

### A.4 Cookie 安全层级总结

Google 的 Cookie 命名前缀反映了严格的安全层级：

```
安全级别（从高到低）：
┌─────────────────────────────────────────────────────────────┐
│ __Host-*    最高级：强制 Path=/，无 Domain，防子域污染      │
│             例：__Host-1PLSID, __Host-3PLSID               │
├─────────────────────────────────────────────────────────────┤
│ __Secure-*  高级：必须 HTTPS，可设 Domain 和 Path           │
│             例：__Secure-1PSID, __Secure-3PSID 等           │
├─────────────────────────────────────────────────────────────┤
│ 无前缀      普通级：HTTP/HTTPS 均可，向后兼容               │
│             例：SID, HSID, SSID, NID（早期遗留）            │
└─────────────────────────────────────────────────────────────┘
```

### A.5 AI Mode 相关的核心 Cookie 对接口的依赖关系

| Cookie | 使用该 Cookie 的接口 | 用途 |
|--------|-------------------|------|
| `SAPISID` + `__Secure-1PAPISID` | GetAsyncData, gsessionid | 生成 `SAPISIDHASH` 三重鉴权 Header |
| `SID` + `__Secure-1PSID` + `__Secure-3PSID` | 所有接口 | 主会话认证，服务端验证登录状态 |
| `SIDCC` + `__Secure-1/3PSIDCC` | RotateCookies | Cookie Counter，由 RotateCookies 每 600 秒刷新 |
| `NID` | folif, /search, complete/search | 包含 XSRF Token（与 `_xsrf` 参数对应） |
| `ACCOUNT_CHOOSER` | ListAccounts | 提供账号列表数据来源 |
| `SOCS` | 所有接口 | Cookie 同意状态，影响数据处理行为 |
| `__Secure-BUCKET` | GetAsyncData (X-Client-Data) | A/B 测试分桶，与 variation_id 对应 |
| `AEC` | 所有接口 | 反滥用验证，拦截异常请求 |


---

### A.6 AI Mode 场景下 Cookie 的特殊作用

在 AI 对话模式中，Cookie 承担了比普通搜索更复杂的职责：

| 职责 | 相关 Cookie | 说明 |
|------|------------|------|
| **上下文记忆** | `__Secure-1PSID`、`SID` | AI 通过会话 Cookie 识别用户身份，能根据历史习惯（常用位置、语言）提供个性化回答 |
| **持续对话维持** | `__Secure-1PSID`、`HSID`、`SSID` | 维持 Session 连续性，翻页或刷新后对话历史不丢失，ListThreads 接口依赖这些 Cookie 拉取历史记录 |
| **实时搜索鉴权** | `SAPISID`（生成 SAPISIDHASH） | folif 接口的联网搜索（如天气查询）需要实时鉴权，防止未授权调用 |
| **A/B 功能分配** | `__Secure-BUCKET` | 决定用户被分配到哪个功能实验组，影响 AI 回复样式、推荐问题 Chips 数量等 |
| **Cookie 自动续期** | `__Secure-1/3PSIDCC`、`SIDCC` | RotateCookies 每 600 秒刷新这些 Cookie，确保长对话不因 Cookie 过期中断 |
| **账号切换支持** | `ACCOUNT_CHOOSER` | 多账号环境下，ListAccounts 读取此 Cookie 确定当前活跃账号，支持 `authuser` 参数切换 |
| **同意合规** | `SOCS` | GDPR/隐私合规要求，记录用户是否同意数据处理，影响 AI 个性化功能的开关状态 |


---

## 附录 B：真实场景请求时序复现

本附录基于实际抓包截图，完整复现 AI Mode 两个典型场景的请求时序。

---

### B.1 场景：天气查询（联网实时搜索）

**用户输入**：`帮我查一下天气`

**AI 返回内容**（截图实录）：
> 北京目前（2026年3月4日）正处于雨雪天气中，且伴有大雾预警，出行请务必注意安全。
> 今天（3月4日，周三）：雨夹雪转小雪。白天最高气温约 2°C，夜间最低气温降至 -4°C。
> 预警信息：北京市气象台已发布大雾黄色预警，能见度较低；同时发布了道路结冰黄色预警……
> ——引用来源：北京市密云区人民政府 +4

**完整请求时序**（与截图 Network 面板对应）：

```
时间线 →

[初始化阶段，进入页面时]
① GET  complete/search?q=&client=aim-zero-state&xssi=t
② POST GetAsyncData (ogads-pa.clients6.google.com)
③ GET  rs=ACT90oF4qeN7...  (xjs JS Bundle，命中磁盘缓存)
④ GET  ListThreads?aep=22&...   (加载历史对话，第1次)
⑤ GET  ListThreads?aep=22&...   (加载历史对话，第2次)
⑥ GET  complete/search?q=&client=aim-zero-state&xssi=t
⑦ GET  m=gGOqee,UMk45c,bplExb...?xjs=s4  (JS 模块按需加载)
⑧ GET  m=sy1x9,Z0vsl,sy516...?xjs=s4      (CSS 模块按需加载)
⑨ GET  hpba?vet=12ahUKEwjg...              (Homepage Background Async)
⑩ GET  m=sysd.syr3,syoa.sy1je?xjs=s4      (CSS 模块按需加载)
⑪ GET  m=syu8?xjs=s4                       (CSS 模块按需加载)
⑫ GET  bgasy?ei=...&opi=89978449...        (后台 JS 资源清单)
⑬ GET  m=sy7iq?xjs=s4                      (CSS 模块按需加载)

[用户提交问题："帮我查一下天气"]
⑭ POST log?format=json&hasfast=true&authuser=0   (上报点击事件)
⑮ GET  complete/search?q=&client=aim-zero-state&xssi=t
⑯ GET  folif?ei=...&q=帮我查一下天气&...         (AI 查询，获取实时天气)
⑰ POST batchexecute?rpcids=gY9iS...              (同步 Thread 状态)
⑱ POST log?format=json&hasfast=true&authuser=0   (上报 AI 回复展示事件)
⑲ POST log?format=json&hasfast=true&authuser=0   (上报用户反馈/引用点击)
⑳ GET  folif?ei=...（第2次，推荐问题 Chips 加载）
㉑ POST batchexecute?rpcids=gY9iS...
⑳② POST log?format=json&...
⑳③ POST RotateCookies                            (周期性刷新身份 Cookie)
⑳④ GET  ListAccounts?listPages=0&authuser=0...   (验证账号，出现于此)
⑳⑤ POST log?format=json&...
```

> **关键观察**：
> - 天气查询触发了 folif 的**实时联网搜索**，AI 引用了"北京市密云区人民政府 +4"等真实数据源，证明 folif 并非静态知识库回答，而是集成了实时 Web 搜索。
> - `RotateCookies` 出现在对话中期，符合 600 秒轮换周期。
> - `ListAccounts` 在本次非图片生成场景中也出现了（⑳④），说明其触发时机不仅限于图片生成流程，可能也用于对话过程中的账号状态验证。
> - `log` 接口在整个流程中出现了约 8 次，基本每个用户行为节点都有对应的上报。

---

### B.2 ListAccounts Response 真实结构确认

从截图 Preview 标签可直接观察到 ListAccounts 的真实响应（JSON 树形展开）：

```json
[
  "gaia.l.a.r",
  [
    [
      "gaia.l.a.s",
      1,
      "Maple Bader",
      "maplebader@gmail.com",
      "...",
      "..."
    ]
  ]
]
```

| 字段路径 | 类型 | 确认值 | 说明 |
|---------|------|--------|------|
| `[0]` | string | `"gaia.l.a.r"` | GAIA List Response 类型标识 |
| `[1]` | array | `[...]` | 账号数组（支持多账号） |
| `[1][0][0]` | string | `"gaia.l.a.s"` | GAIA Account Entry 标识 |
| `[1][0][1]` | number | `1` | 账号索引，对应 `authuser=0/1/2...` |
| `[1][0][2]` | string | `"Maple Bader"` | 用户显示名（Full Name），**真实 PII** |
| `[1][0][3]` | string | `"maplebader@gmail.com"` | Gmail 邮箱地址，**真实 PII** |
| `[1][0][4]` | string | `"..."` | 头像图片 URL |
| `[1][0][5]` | string | `"..."` | GAIA ID 等扩展元数据 |

此结构已通过实际抓包截图**直接确认**，与第十四章文档记录完全吻合。

---

### B.3 hpba 接口

已完整记录于第二十三章，参见上文。


---

文档版本：v2.3  更新日期：2026-03-04
新增接口：七、会话 ID 获取（gsessionid）；补充鉴权机制对比表
