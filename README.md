# 校园二手交易平台

本项目按课程详细设计报告分阶段开发。当前完成第 1、2、3、4、5、6、7 阶段：Flask 后端基础骨架、用户认证与商品审核主流程、购物车订单模拟支付交易闭环、微信小程序核心页面、消息评价退款申诉 AI mock、后台日志统计、联调测试与课程演示文档。

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

- `POST /api/v1/auth/mock-login`：测试账号 mock 登录
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

- `POST /api/v1/cart/items`：加入购物车
- `GET /api/v1/cart`：查看购物车
- `PUT /api/v1/cart/items/{product_id}`：修改购物车商品数量
- `DELETE /api/v1/cart/items/{product_id}`：删除购物车商品
- `POST /api/v1/orders`：创建订单
- `GET /api/v1/orders`：查看当前用户相关订单
- `GET /api/v1/orders/{id}`：查看订单详情
- `POST /api/v1/orders/{id}/cancel`：取消待支付订单
- `POST /api/v1/payments/mock-confirm`：模拟支付确认
- `POST /api/v1/deliveries/{order_id}/confirm`：买家确认收货

交易规则：

- 买家不能购买自己的商品
- 创建订单时后端重新读取商品价格、库存和状态
- 创建订单时写入 `order_items.product_snapshot`
- 创建订单时锁定库存
- 重复下单支持 `X-Idempotency-Key`
- 模拟支付成功后订单进入 `paid`
- 买家确认收货后订单进入 `completed`
- 取消待支付订单会关闭支付单并释放库存
- 订单详情返回 `allowed_actions`

订单状态：

```text
pending_payment -> paid -> completed
pending_payment -> closed
```

支付状态：

```text
pending -> paid
pending -> failed
pending -> closed
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
- `pages/cart/index/`
- `pages/order/confirm/`
- `pages/order/detail/`
- `pages/mine/index/`
- `pages/admin/products/`

所有页面均包含 `.js/.json/.wxml/.wxss` 四件套。首页、发布、消息、我的已进入 tabBar；管理端入口位于“我的”页面。

## 第 5 阶段已实现

小程序核心页面已接入后端 API：

- 登录页：支持买家、卖家、管理员三个测试账号一键切换和 mock 登录
- 首页：展示 `on_sale` 商品列表，支持跳转搜索和购物车
- 分类/搜索页：支持关键词、分类、成色筛选
- 商品详情页：展示商品详情，按后端 `allowed_actions` 显示加入购物车、立即购买、下架按钮
- 发布页：支持基础信息、价格库存、分类、成色、图片路径 mock、AI 文案 mock、保存草稿、提交审核
- 购物车页：查看购物车、修改数量、删除商品、去结算
- 订单确认页：展示商品与数量，提交订单，金额由后端重新计算
- 订单详情页：展示订单快照、模拟支付、取消订单、确认收货
- 我的页：显示登录态、购物车入口、管理员入口
- 管理端商品审核页：查看待审核商品，审核通过或驳回

本阶段补充后端接口：

- `GET /api/v1/admin/products?status=pending_review`

图片上传和 AI 功能说明：

- 图片上传本阶段为小程序本地路径 mock，后续可接入后端 `uploads/` 文件接口
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
- `POST /api/v1/refunds/{id}/seller-handle`：卖家处理退款
- `POST /api/v1/admin/refunds/{id}/arbitrate`：管理员仲裁
- `GET /api/v1/admin/refunds`：管理员查看退款
- `POST /api/v1/ai/product-copy`：AI 文案 mock
- `GET /api/v1/admin/operation-logs`：操作日志
- `GET /api/v1/admin/stats`：后台基础统计

小程序补充：

- 商品详情页可联系卖家
- 消息页展示会话
- 订单详情页可评价、申请退款
- 新增退款申请页
- 新增退款售后列表页，卖家可处理退款，管理员可仲裁
- 发布页 AI 建议调用后端 mock 接口
- 新增后台日志与统计页

当前 mock 说明：

- AI 文案生成仍为后端 mock，不接入真实大模型
- 系统通知接口已预留，课程阶段可为空列表
- 退款为流程状态模拟，不接入真实资金退款
- 图片证据仍以路径数组形式保存，真实上传接口留到后续完善

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

## 初始化演示数据

`python .\scripts\init_db.py` 会自动创建集合、索引、分类、账号和演示商品。演示商品包含：

| 类型 | 商品 | 状态 | 用途 |
|---|---|---|---|
| 在售商品 | 九成新机械键盘 | `on_sale` | 买家首页浏览、加入购物车、创建订单 |
| 在售商品 | 高等数学教材套装 | `on_sale` | 首页列表和搜索演示 |
| 待审核商品 | 宿舍护眼台灯 | `pending_review` | 管理员商品审核演示 |

这些数据通过 `seed_code` 幂等更新，重复运行初始化脚本不会重复插入演示商品。

## 第 2 阶段接口测试示例

登录卖家：

```powershell
$login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/auth/mock-login" -ContentType "application/json" -Body '{"phone":"18800000001","password":"seller123456"}'
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

加入购物车：

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/cart/items" -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" -Body '{"product_id":"商品ID","quantity":1}'
```

创建订单：

```powershell
$idem = [guid]::NewGuid().ToString()
$order = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/orders" -Headers @{ Authorization = "Bearer $token"; "X-Idempotency-Key" = $idem } -ContentType "application/json" -Body '{"product_id":"商品ID","quantity":1,"delivery_type":"meetup","meet_location":"图书馆门口"}'
```

模拟支付：

```powershell
$paymentId = $order.data.payment.id
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/payments/mock-confirm" -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" -Body "{`"payment_id`":`"$paymentId`",`"mock_result`":`"success`"}"
```

确认收货：

```powershell
$orderId = $order.data.id
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/v1/deliveries/$orderId/confirm" -Headers @{ Authorization = "Bearer $token" }
```

## 当前 mock 说明

- 支付模式：`PAYMENT_MODE=mock`
- AI 模式：`AI_MODE=mock`
- 微信登录、真实支付、真实 AI 调用、对象存储暂未接入
- 微信登录：使用手机号和密码 mock 登录，不调用微信真实登录接口
- 模拟支付：只改变本地支付单和订单状态，不接入真实资金
- 退款流程：只做状态流转和金额校验，不接入真实退款渠道
- AI 文案：后端生成 mock 建议，用户仍需手动确认后发布
- 图片上传：当前小程序保存本地路径/示例路径，后续可扩展为后端 `uploads/` 文件接口

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
8. 首页刷新后查看商品，进入详情，加入购物车或立即购买。
9. 创建订单，进入订单详情，点击模拟支付。
10. 支付后点击确认收货，订单进入已完成。
11. 订单详情页可提交评价或申请退款。
12. 卖家进入“我的 -> 退款售后”处理退款；管理员可在同一入口仲裁。
13. 管理员进入“我的 -> 后台日志与统计”查看审计记录。

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
- 可完成 mock 登录、发布商品、管理员审核、购物车、订单、模拟支付、确认收货
- 可演示消息、评价、退款、AI mock、后台日志和统计
- 前端请求统一走 `miniprogram/utils/request.js`
- 商品、订单、支付、退款状态由后端 Service 层控制

## 真实化改进说明

在初版课程流程基础上，已补充更接近真实微信小程序的关键能力：

- 微信登录适配器：新增 `POST /api/v1/auth/wechat-login`，本地开发默认 mock，生产可切换真实 code2Session
- 账号体系：新增注册、绑定手机号、修改密码、退出登录接口
- 图片上传：新增 `POST /api/v1/files/upload`，小程序使用 `wx.chooseMedia` + `wx.uploadFile` 上传到后端 `uploads/`
- 订单状态机：买家下单后进入 `pending_seller_confirm`，卖家确认后进入 `pending_payment`
- 卖家操作：新增卖家确认交易、卖家取消交易、卖家确认交付
- 买家收货：买家只能在卖家确认交付后确认收货
- 支付结构：新增 `PaymentAdapter`、`MockPaymentAdapter`、`WechatPayAdapter`，课程阶段仍使用 mock 支付

新增接口：

```text
POST /api/v1/auth/wechat-login
POST /api/v1/auth/register
POST /api/v1/auth/bind-phone
POST /api/v1/auth/change-password
POST /api/v1/auth/logout
POST /api/v1/files/upload
POST /api/v1/orders/{id}/seller-confirm
POST /api/v1/orders/{id}/seller-cancel
POST /api/v1/deliveries/{order_id}/seller-deliver
```

新的订单主流程：

```text
pending_seller_confirm -> pending_payment -> paid -> delivering -> completed
pending_seller_confirm -> seller_cancelled
pending_seller_confirm/pending_payment -> closed
```

## 小程序上传注意事项

当前项目以本地课程演示为主。真机预览或正式上传前需要：

- 将 Flask 后端部署到 HTTPS 服务
- 在微信公众平台配置合法服务器域名
- 将 `miniprogram/utils/constants.js` 中 `trial`、`release` 的 `API_BASE_URL` 改为线上 HTTPS API 地址
- 接入真实图片上传接口后，再替换当前图片路径 mock
- 如果要接入真实微信登录、支付或 AI，需要把对应 Adapter 从 mock 实现替换为真实服务封装

真实小程序上线检查清单：

- `https://api.your-domain.com/api/v1/health` 可公网访问
- HTTPS 证书有效，手机浏览器访问无证书警告
- 微信公众平台已配置 request 合法域名
- 小程序体验版/正式版请求地址不是 `127.0.0.1`、不是局域网 IP、不是 HTTP
- 后端生产环境 `FLASK_DEBUG=0`
- 生产环境 `SECRET_KEY`、`JWT_SECRET` 已替换为随机强密钥
- 服务器防火墙开放 443，由 Nginx 转发到 Flask WSGI 服务
