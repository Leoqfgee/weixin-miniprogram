# 校园二手交易平台

## 当前正式版本说明

本项目当前已面向微信云托管正式化改造：小程序前端通过 `wx.cloud.callContainer` 调用云托管 Flask 服务，后端支持 MySQL 文档适配层、真实微信 `code2Session` 登录、真实千问 DashScope API、商品审核、订单交易、聊天、收藏管理和管理员审核流程。

### 登录与身份

- 正式登录入口：`POST /api/v1/auth/wechat-login`，绑定依据只使用微信 `code2Session` 返回的 `openid`。
- `users.openid` 必须唯一，同一个微信号重复登录会命中同一条用户记录。
- 昵称和头像不是绑定依据；新用户登录后如果平台昵称或头像为空，小程序会跳转到“完善资料”页。
- `GET /api/v1/users/me` 返回当前 JWT 对应用户，包含 `openid_mask`，不会返回完整 `session_key`。
- `PUT /api/v1/users/me` 保存平台昵称、头像、联系方式、简介和 `identity_type`。

### 开发测试模式

真实微信登录保留为正式主流程。为了在只有一个微信号时测试多账号交易和管理员审核，后端新增：

```text
POST /api/v1/auth/dev-test-login
Body: {"account":"buyer_a|buyer_b|seller|admin"}
```

该接口只在 `DEV_TEST_LOGIN_ENABLED=1` 时可用。生产环境应保持：

```text
DEV_TEST_LOGIN_ENABLED=0
```

测试账号由 `backend/scripts/init_db.py` 初始化：`buyer_a`、`buyer_b`、`seller`、`admin`。小程序开发版登录页会显示“开发测试账号”面板；体验版和正式版不显示。

### 收藏管理

收藏功能现在不是纯前端筛选，后端会保存收藏时价格 `favorited_price`，并通过接口返回真实分类：

- `GET /api/v1/favorites?type=all`：全部收藏
- `GET /api/v1/favorites?type=price_drop`：收藏后当前价格低于收藏价的“降价宝贝”
- `GET /api/v1/favorites?type=valid`：仍有效的商品，包括在售、交易中和已售出
- `GET /api/v1/favorites?type=invalid`：卖家主动下架的失效商品
- `POST /api/v1/favorites/cleanup-invalid`：清理已下架失效收藏
- `DELETE /api/v1/favorites/{product_id}`：手动取消收藏，已售出商品也可手动移除

### AI 文案

AI 标题和描述润色仍调用真实千问 API，不回退 mock。提示词已针对校园二手场景优化：标题更短、更像真实同学发布；描述保留原始重点，避免夸张营销、虚构配件或保修承诺。

### 小程序 UI 与交互

本轮重点优化页面：发布商品页、商品详情页、聊天页、收藏页、完善资料页、消息列表页和收货地址页。发布时分类和成色为选填；商品详情展示卖家头像昵称并可进入卖家主页；聊天商品卡片和头像支持跳转；收藏页支持全部、降价宝贝、有效宝贝、失效宝贝和清理失效收藏；完善资料页去掉双栏结构，保留微信头像/昵称能力，同时支持相册和拍照设置头像。

### 个人主体限制说明

微信手机号授权、微信支付等能力可能受个人主体小程序权限限制。本项目保留正式接口结构和 mock 支付闭环，不在文档或界面中假装个人主体已经完整打通微信支付。

本项目按课程详细设计报告分阶段开发。当前完成第 1、2、3、4、5、6、7 阶段：Flask 后端基础骨架、用户认证与商品审核主流程、直接购买订单模拟支付交易闭环、微信小程序核心页面、消息评价退款申诉 AI mock、后台日志统计、联调测试与课程演示文档。

## 当前目录

```text
campus_secondhand_platform/
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ config.py
│  │  ├─ extensions.py
│  │  ├─ blueprints/
│  │  ├─ services/
│  │  ├─ repositories/
│  │  ├─ adapters/
│  │  ├─ utils/
│  │  └─ tasks/
│  ├─ scripts/
│  ├─ tests/
│  ├─ requirements.txt
│  ├─ .env.example
│  └─ run.py
├─ uploads/
├─ miniprogram/
├─ docs/
└─ README.md
```

## 第 1 阶段已实现

- Flask app 工厂：`backend/app/__init__.py`
- 配置读取：`backend/app/config.py`
- MongoDB 连接：`backend/app/extensions.py`
- 统一成功/失败响应：`backend/app/utils/response.py`
- 统一异常处理：`backend/app/utils/errors.py`
- `trace_id` 生成与响应头透传：`backend/app/utils/trace.py`
- JWT 基础工具和角色装饰器：`backend/app/utils/jwt.py`
- CORS 配置
- 健康检查接口：`GET /api/v1/health`
- MongoDB 初始化脚本：`backend/scripts/init_db.py`
- 基础测试文件：`backend/tests/test_health.py`

## 第 2 阶段已实现

- `POST /api/v1/auth/password-login`：手机号密码登录
- `POST /api/v1/auth/dev-test-login`：开发环境测试账号快速登录
- `GET /api/v1/users/me`：读取当前登录用户
- `GET /api/v1/categories`：读取基础分类
- `GET /api/v1/products`：读取公开在售商品列表
- `GET /api/v1/products/{id}`：读取商品详情并返回 `allowed_actions`
- `POST /api/v1/products`：卖家发布商品草稿或直接提交审核
- `PUT /api/v1/products/{id}`：卖家编辑自己的草稿/驳回/下架商品
- `POST /api/v1/products/{id}/submit-review`：提交商品审核
- `POST /api/v1/admin/products/{id}/audit`：管理员审核通过或驳回商品
- `POST /api/v1/products/{id}/off-shelf`：卖家下架或管理员强制下架

商品状态由后端 Service 层控制：

```text
draft -> pending_review -> on_sale
draft/rejected/off_shelf -> pending_review
pending_review -> rejected
on_sale -> off_shelf
```

前端不得提交 `status` 字段。接口返回商品详情时会带上 `allowed_actions`，后续小程序页面按该字段展示按钮。

## 第 3 阶段已实现

- `POST /api/v1/orders`：创建订单
- `GET /api/v1/orders`：查看当前用户相关订单
- `GET /api/v1/orders/{id}`：查看订单详情
- `POST /api/v1/orders/{id}/buyer-cancel`：买家取消待付款订单
- `POST /api/v1/payments/prepay`：创建支付单
- `POST /api/v1/payments/mock-confirm`：模拟支付确认
- `POST /api/v1/deliveries/{order_id}/seller-deliver`：卖家确认交付
- `POST /api/v1/deliveries/{order_id}/buyer-confirm`：买家确认收货

交易规则：

- 买家不能购买自己的商品
- 创建订单时后端重新读取商品价格、库存和状态
- 创建订单时写入 `order_items.product_snapshot`
- 创建订单时锁定库存
- 重复下单支持 `X-Idempotency-Key`
- 模拟支付成功后订单进入 `pending_delivery`
- 卖家确认交付后订单进入 `pending_receive`
- 买家确认收货后订单进入 `pending_review`
- 取消待支付订单会关闭支付单并释放库存
- 订单详情返回 `allowed_actions`

订单状态：

```text
pending_payment -> pending_delivery -> pending_receive -> pending_review -> completed
pending_payment -> closed
```

支付状态：

```text
pending -> paid
pending -> failed
paid -> refunded
```

平台担保状态：

```text
holding -> settled
holding -> refunded
```

## 第 4 阶段已实现

微信小程序原生项目骨架已创建在 `miniprogram/`：

- `app.js`
- `app.json`
- `app.wxss`
- `project.config.json`
- `sitemap.json`
- `utils/request.js`
- `utils/auth.js`
- `utils/constants.js`
- `utils/validator.js`
- `components/product-card/`
- `components/empty-state/`
- `components/status-badge/`
- `components/confirm-dialog/`

已声明页面：

- `pages/login/`
- `pages/index/`
- `pages/category/`
- `pages/product/detail/`
- `pages/publish/edit/`
- `pages/message/index/`
- `pages/order/confirm/`
- `pages/order/detail/`
- `pages/mine/index/`
- `pages/admin/products/`

所有页面均包含 `.js/.json/.wxml/.wxss` 四件套。首页、发布、消息、我的已进入 tabBar；管理端入口位于“我的”页面。

## 第 5 阶段已实现

小程序核心页面已接入后端 API：

- 登录页：支持买家、卖家、管理员三个测试账号一键切换和 mock 登录
- 首页：展示 `on_sale` 商品列表，支持搜索与筛选
- 分类/搜索页：支持关键词、分类、成色筛选
- 商品详情页：展示商品详情，按后端 `allowed_actions` 显示收藏、联系卖家、立即购买、下架按钮
- 发布页：支持基础信息、价格库存、分类、成色、图片上传、AI 标题建议、AI 描述润色、保存草稿、提交审核
- 订单确认页：展示商品与数量，提交订单，金额由后端重新计算
- 订单详情页：展示订单快照、状态步骤、资金担保、交付信息、售后信息和按后端 `allowed_actions.actions` 控制的操作按钮
- 交付表单页：卖家可选择校内面交、校园自提、校内送达、快递邮寄，并上传交付凭证
- 我的页：显示登录态、发布/买到/卖出/收藏/地址/客服入口和管理员入口
- 管理端商品审核页：查看待审核商品，审核通过或驳回
- 管理端申诉仲裁页：查看平台介入详情并执行支持买家、支持卖家、部分退款或关闭申诉

本阶段补充后端接口：

- `GET /api/v1/admin/products?status=pending_review`

图片上传和 AI 功能说明：

- 图片上传已通过 `wx.chooseMedia` + `wx.uploadFile` 接入后端 `POST /api/v1/files/upload`，课程阶段文件保存在本地 `uploads/` 目录
- AI 文案建议为后端 mock，不接入真实大模型，不会直接发布商品

## 第 6 阶段已实现

后端补充接口：

- `POST /api/v1/messages`：发送私聊消息
- `GET /api/v1/messages/conversations`：会话列表
- `GET /api/v1/messages/conversations/{conversation_id}`：会话消息
- `GET /api/v1/notifications`：系统通知列表
- `POST /api/v1/reviews`：已完成订单评价
- `POST /api/v1/refunds`：买家申请退款
- `GET /api/v1/refunds`：买家/卖家退款列表
- `GET /api/v1/refunds/{id}`：退款详情
- `POST /api/v1/refunds/{id}/seller-agree`：卖家同意退款
- `POST /api/v1/refunds/{id}/seller-reject`：卖家拒绝退款
- `POST /api/v1/appeals`：买家申请平台介入
- `GET /api/v1/appeals/{id}`：申诉详情
- `GET /api/v1/admin/appeals`：管理员查看平台介入列表
- `POST /api/v1/admin/appeals/{id}/arbitrate`：管理员处理平台介入
- `POST /api/v1/ai/product-copy`：商品标题建议与描述润色；开发环境支持 mock，配置 `AI_MODE=dashscope` 与百炼 API Key 后调用通义千问
- `GET /api/v1/admin/operation-logs`：操作日志
- `GET /api/v1/admin/stats`：后台基础统计

小程序补充：

- 商品详情页可联系卖家
- 消息页展示会话
- 订单详情页可评价、申请退款
- 新增退款申请页，支持上传最多 6 张售后证据图
- 新增平台介入申请页，支持上传最多 6 张申诉证据图
- 新增退款售后列表页，卖家可处理退款，管理员可仲裁
- 新增申诉仲裁页，管理员可查看订单、支付、担保、交付、退款与申诉凭证
- 发布页 AI 建议调用后端 mock 接口
- 新增后台日志与统计页

当前 mock 说明：

- AI 文案生成仍为后端 mock，不接入真实大模型
- 系统通知接口已预留，课程阶段可为空列表
- 退款为流程状态模拟，不接入真实资金退款
- 售后证据当前保存图片 URL 数组，可复用 `POST /api/v1/files/upload` 上传到本地 `uploads/`
- 交付信息和凭证为课程阶段模拟记录，不接入真实物流 API；快递方式只保存快递公司和单号

## 第 7 阶段已实现

- 初始化脚本补充幂等演示商品：2 个在售商品、1 个待审核商品
- 后端测试隔离到 `campus_secondhand_test`，避免测试数据污染本地演示主库
- 已完成后端 `pytest` 测试、真实 HTTP 冒烟联调、小程序页面四件套检查
- 已检查小程序页面/组件未直接使用 `wx.request`、`fetch`、`axios`、DOM/BOM 或 `localStorage`
- README 补充最终运行步骤、测试步骤、课程演示流程、mock 范围和上线注意事项

初始化后首页可直接看到演示商品，管理员审核页可看到待审核演示商品。

## 本地环境

- Python 3.10+ 建议
- MongoDB 已启动
- MongoDB 地址：`mongodb://localhost:27017`
- 数据库名：`campus_secondhand`

## Windows PowerShell / Conda 运行命令

进入项目后端目录：

```powershell
cd "F:\A 软件工程\campus_secondhand_platform\backend"
```

使用已创建的 Anaconda 环境：

```powershell
conda activate weixin-app
```

安装依赖：

```powershell
pip install -r requirements.txt
```

复制环境变量示例：

```powershell
Copy-Item .env.example .env
```

初始化 MongoDB 集合、索引和测试数据：

```powershell
python .\scripts\init_db.py
```

启动 Flask 后端：

```powershell
python .\run.py
```

默认监听 `0.0.0.0:5000`。这样微信开发者工具扫码预览时，手机才能通过电脑的局域网 IP 访问 Flask。

访问健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/v1/health
```

## 测试

```powershell
cd "F:\A 软件工程\campus_secondhand_platform\backend"
conda activate weixin-app
python -m pytest -q
```

如果使用 Conda 环境，也可以直接运行：

```powershell
F:\ProgramData\anaconda3\envs\weixin-app\python.exe -m pytest
```

测试会使用独立数据库 `campus_secondhand_test`，测试结束后自动删除该测试库；本地演示主库 `campus_secondhand` 不会被 pytest 商品污染。

## 测试账号

初始化脚本会创建以下测试账号，后续第 2 阶段 mock 登录会使用这些数据：

| 角色 | 手机号 | 密码 |
|---|---|---|
| 管理员 | `18800000000` | `admin123456` |
| 测试卖家 | `18800000001` | `seller123456` |
| 测试买家 | `18800000002` | `buyer123456` |

当前角色命名统一为 `buyer`、`seller`、`admin`。买家账号默认拥有 `buyer` 角色，卖家账号同时拥有 `buyer` 和 `seller` 角色，管理员账号拥有 `admin` 角色。

## 初始化演示数据

`python .\scripts\init_db.py` 会自动创建集合、索引、分类、账号和演示商品。演示商品包含：

| 类型 | 商品 | 状态 | 用途 |
|---|---|---|---|
| 在售商品 | 九成新机械键盘 | `on_sale` | 买家首页浏览、收藏、直接创建订单 |
| 在售商品 | 高等数学教材套装 | `on_sale` | 首页列表和搜索演示 |
| 待审核商品 | 宿舍护眼台灯 | `pending_review` | 管理员商品审核演示 |

这些数据通过 `seed_code` 幂等更新，重复运行初始化脚本不会重复插入演示商品。

## 第 2 阶段接口测试示例

登录卖家：

```powershell
$login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/auth/password-login" -ContentType "application/json" -Body '{"phone":"18800000001","password":"seller123456"}'
$token = $login.data.token
```

查看当前用户：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/v1/users/me" -Headers @{ Authorization = "Bearer $token" }
```

查看分类：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/v1/categories"
```

查看在售商品：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/v1/products"
```

## 第 3 阶段接口测试示例

创建订单：

```powershell
$idem = [guid]::NewGuid().ToString()
$order = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/orders" -Headers @{ Authorization = "Bearer $token"; "X-Idempotency-Key" = $idem } -ContentType "application/json" -Body '{"product_id":"商品ID","quantity":1,"delivery_type":"meetup","meet_location":"图书馆门口"}'
```

模拟支付：

```powershell
$orderId = $order.data.id
$prepay = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/payments/prepay" -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" -Body "{`"order_id`":`"$orderId`"}"
$paymentId = $prepay.data.payment.id
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/payments/mock-confirm" -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" -Body "{`"payment_id`":`"$paymentId`",`"mock_result`":`"success`"}"
```

卖家确认交付：

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/deliveries/$orderId/seller-deliver" -Headers @{ Authorization = "Bearer $sellerToken" } -ContentType "application/json" -Body '{"delivery_type":"offline_meetup","meet_location":"图书馆门口","delivery_note":"已当面交付"}'
```

确认收货：

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/deliveries/$orderId/buyer-confirm" -Headers @{ Authorization = "Bearer $token" }
```

## 当前本地模式说明

- 支付模式：`PAYMENT_MODE=mock`
- AI 正式模式：`AI_MODE=qwen`；配置 `DASHSCOPE_API_KEY`、`QWEN_MODEL=qwen-plus` 后调用千问 DashScope API
- 微信登录本地默认使用 mock code2Session，也保留手机号密码测试登录
- 真实支付和对象存储暂未接入
- 模拟支付：只改变本地支付单和订单状态，不接入真实资金
- 退款流程：只做状态流转和金额校验，不接入真实退款渠道
- AI 文案：标题建议由用户选择后应用，描述润色只修改描述；用户仍需确认内容真实后发布
- 图片上传：当前上传到后端本地 `uploads/` 目录，后续可替换为对象存储

## 小程序环境与接口地址

小程序前端已创建到 `miniprogram/` 目录。接口地址集中配置在：

```text
miniprogram/utils/constants.js
```

当前按微信小程序真实环境分为：

```text
develop：开发版，本地调试，可临时使用 http://电脑局域网IP:5000/api/v1
trial：体验版，必须使用公网 HTTPS，例如 https://api.your-domain.com/api/v1
release：正式版，必须使用公网 HTTPS，例如 https://api.your-domain.com/api/v1
```

真实小程序不应该依赖手机和电脑在同一个 Wi-Fi。体验版和正式版应该请求已部署的公网 HTTPS 后端，并在微信公众平台配置合法服务器域名。

### 本地开发说明

微信开发者工具本地调试时，可在开发版 `develop` 中临时使用：

```text
http://10.6.14.70:5000/api/v1
```

这个地址只用于本地开发调试，不是正式小程序方案。开发阶段可勾选“不校验合法域名、web-view、TLS 版本以及 HTTPS 证书”。

### 体验版/正式版说明

体验版和正式版应将 `trial`、`release` 的地址替换为真实 HTTPS 域名：

```text
https://api.your-domain.com/api/v1
```

并在微信公众平台完成：

- 开发管理 -> 开发设置 -> 服务器域名
- request 合法域名填写 `https://api.your-domain.com`
- 域名必须支持 HTTPS，证书有效，不能只用 IP
- 域名通常需要备案，具体以微信公众平台当前规则为准

后端部署到公网后，可以用下面的地址检查：

```text
https://api.your-domain.com/api/v1/health
```

## 后端公网部署说明

项目已提供生产部署入口：

```text
backend/wsgi.py
```

云服务器部署建议：

- 使用 Linux 云服务器部署 Flask 后端
- 使用 Nginx 配置 HTTPS 和反向代理
- 使用 `backend/wsgi.py` 作为 WSGI 入口
- 使用 `.env.production.example` 作为生产环境变量模板
- MongoDB 可部署在同一云服务器内网或托管数据库
- `uploads/` 目录在生产环境应放到服务器持久化目录，后续可替换为对象存储

## 微信开发者工具导入说明

1. 启动后端：

```powershell
conda activate weixin-app
cd "F:\A 软件工程\campus_secondhand_platform\backend"
python run.py
```

2. 打开微信开发者工具，选择“导入项目”。
3. 项目目录选择：

```text
F:\A 软件工程\campus_secondhand_platform\miniprogram
```

4. AppID 可先使用测试号或 `project.config.json` 中的占位值 `touristappid`。
5. 本地联调阶段勾选“不校验合法域名、web-view、TLS 版本以及 HTTPS 证书”。

如果登录页提示“网络连接失败”，优先检查 Flask 是否仍在运行，并访问：

```text
http://127.0.0.1:5000/api/v1/health
```

不要把 `backend/` 导入微信开发者工具；微信开发者工具只导入 `miniprogram/` 目录。

## 课程演示流程（当前阶段）

1. 启动后端并确认健康检查：

```text
http://127.0.0.1:5000/api/v1/health
```

2. 微信开发者工具导入 `miniprogram/`。
3. 用卖家账号登录：`18800000001 / seller123456`。
4. 进入“发布”，填写商品，点击“AI 建议”，然后“提交审核”。
5. 切换管理员账号：`18800000000 / admin123456`。
6. 进入“我的”里的管理员入口，审核通过商品。
7. 切换买家账号：`18800000002 / buyer123456`。
8. 首页刷新后查看商品，进入详情，收藏、联系卖家或立即购买。
9. 创建订单，进入订单详情，点击模拟支付。
10. 切换卖家账号，进入订单详情并确认交付。
11. 切换买家账号，确认收货，订单进入待评价。
12. 买家提交评价后，订单进入交易完成。
13. 订单详情页可申请退款；卖家进入“我的 -> 退款售后”处理退款，管理员可在同一入口仲裁。
14. 管理员进入“我的 -> 后台日志与统计”查看审计记录。

## MongoDB 检查说明

本项目不依赖 `mongosh` 执行初始化。即使 `mongosh` 不在 PATH 中，也可以通过 Python 初始化脚本创建集合、索引和测试数据。

确认 MongoDB 可用：

```powershell
cd "F:\A 软件工程\campus_secondhand_platform\backend"
conda activate weixin-app
python .\scripts\init_db.py
```

如果输出 `database initialized: campus_secondhand`，说明 Python 已能连接 MongoDB。

## 最终交付检查

- `backend/` 可本地启动，统一 API 前缀为 `/api/v1`
- `miniprogram/` 可被微信开发者工具导入
- MongoDB 可自动初始化集合、索引、分类、账号和演示商品
- 首页可展示在售商品
- 可完成微信登录 mock、发布商品、管理员审核、直接购买、订单、模拟支付、平台担保、交付、确认收货
- 可演示消息、评价、退款、AI mock、后台日志和统计
- 前端请求统一走 `miniprogram/utils/request.js`
- 商品、订单、支付、退款状态由后端 Service 层控制

## 真实化改进说明

在初版课程流程基础上，已补充更接近真实微信小程序的关键能力：

- 微信登录适配器：新增 `POST /api/v1/auth/wechat-login`，本地开发默认 mock，生产可切换真实 code2Session
- 账号体系：新增注册、绑定手机号、修改密码、退出登录接口
- 图片上传：新增 `POST /api/v1/files/upload`，小程序使用 `wx.chooseMedia` + `wx.uploadFile` 上传到后端 `uploads/`
- 订单状态机：买家下单后直接进入 `pending_payment`，商品从 `on_sale` 锁定为 `locked`
- 平台担保：支付成功后创建 `escrow_records.status=holding`，不把担保塞进订单状态
- 卖家操作：新增卖家确认交付、卖家取消并进入退款处理
- 交付方式：支持校内面交、自提、校内送达和快递；小程序端提供交付表单和凭证上传
- 买家收货：卖家交付后订单进入 `pending_receive`，买家确认后进入 `pending_review`
- 支付结构：新增 `PaymentAdapter`、`MockPaymentAdapter`、`WechatPayAdapter`，课程阶段仍使用 mock 支付
- 退款/平台介入：订单只用 `refunding` 表示售后中，具体进度放在 `refunds` 和 `appeals`

新增接口：

```text
POST /api/v1/auth/wechat-login
POST /api/v1/auth/register
POST /api/v1/auth/bind-phone
POST /api/v1/auth/change-password
POST /api/v1/auth/logout
POST /api/v1/files/upload
POST /api/v1/payments/prepay
POST /api/v1/payments/mock-confirm
POST /api/v1/orders/{id}/buyer-cancel
POST /api/v1/orders/{id}/close-timeout
POST /api/v1/orders/{id}/seller-cancel
POST /api/v1/deliveries/{order_id}/seller-deliver
GET  /api/v1/deliveries/{order_id}
POST /api/v1/deliveries/{order_id}/buyer-confirm
POST /api/v1/deliveries/{order_id}/buyer-reject
POST /api/v1/refunds/{id}/seller-agree
POST /api/v1/refunds/{id}/seller-reject
POST /api/v1/appeals
GET  /api/v1/appeals/{id}
GET  /api/v1/admin/appeals
POST /api/v1/admin/appeals/{id}/arbitrate
```

新的订单主流程：

```text
pending_payment -> pending_delivery -> pending_receive -> pending_review -> completed
pending_payment -> closed
pending_delivery/pending_receive -> refunding -> refunded
```

状态说明：

```text
pending_payment   待付款
pending_delivery  待交付
pending_receive   待收货
pending_review    待评价
completed         交易完成
closed            已关闭
refunding         退款/售后中
refunded          已退款
```

订单状态只表示交易主链路，旧的卖家确认、担保、退款请求、争议类节点已从 `orders.status` 中清理。支付状态放在 `payments.status`，平台担保状态放在 `escrow_records.status`，退款进度放在 `refunds.status`，平台介入进度放在 `appeals.status`。

超时任务可手动运行：

```powershell
cd "F:\A 软件工程\campus_secondhand_platform\backend"
conda activate weixin-app
python .\scripts\run_order_timeout.py
```

当前超时规则：

```text
pending_payment 超过 30 分钟未支付 -> closed，商品恢复 on_sale
pending_receive 超过 7 天未确认 -> 自动确认收货，担保 settled
refunding 超过 48 小时卖家未处理 -> 写入业务提醒日志
```

## 小程序上传注意事项

当前项目以本地课程演示为主。真机预览或正式上传前需要：

- 将 Flask 后端部署到 HTTPS 服务
- 在微信公众平台配置合法服务器域名
- 将 `miniprogram/utils/constants.js` 中 `trial`、`release` 的 `API_BASE_URL` 改为线上 HTTPS API 地址
- 如需上线高并发或长期保存图片，建议把本地 `uploads/` 替换为对象存储
- 如果要接入真实微信登录、支付或 AI，需要把对应 Adapter 从 mock 实现替换为真实服务封装

真实小程序上线检查清单：

- `https://api.your-domain.com/api/v1/health` 可公网访问
- HTTPS 证书有效，手机浏览器访问无证书警告
- 微信公众平台已配置 request 合法域名
- 小程序体验版/正式版请求地址不是 `127.0.0.1`、不是局域网 IP、不是 HTTP
- 后端生产环境 `FLASK_DEBUG=0`
- 生产环境 `SECRET_KEY`、`JWT_SECRET` 已替换为随机强密钥
- 服务器防火墙开放 443，由 Nginx 转发到 Flask WSGI 服务
