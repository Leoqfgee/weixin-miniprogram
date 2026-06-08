# 校园二手交易平台微信小程序

本项目是一个校园二手交易小程序，当前部署形态为：

```text
微信小程序 -> 微信云托管 Flask 后端 -> MySQL 文档适配层 -> COS 图片持久化
```

后端 API 前缀为 `/api/v1`，小程序通过 `wx.cloud.callContainer` 和 `wx.uploadFile` 调用云托管 Flask 服务。

## 核心功能

- 微信真实登录：后端使用 `code2Session` 返回的 `openid` 作为唯一绑定依据。
- 商品发布与审核：卖家发布商品，管理员审核通过后进入在售列表。
- 图片持久化：商品图、头像、聊天图、售后/申诉凭证通过后端上传到 COS。
- 首页商品流：支持真实后端模式 `推荐 / 最新 / 热门`。
- 交易闭环：下单、模拟支付、交付、确认收货、评价。
- 售后与平台介入：退款申请、卖家处理、管理员仲裁。
- 消息会话：买卖双方围绕商品沟通。

## COS 图片持久化

正式链路如下：

```text
小程序 wx.uploadFile
  -> Flask 后端 POST /api/v1/files/upload
  -> qcloud_cos.CosS3Client.put_object 上传到 COS
  -> db.files 保存 storage_backend/object_key/url
  -> 商品、头像、凭证字段保存 COS URL
```

云托管环境变量必须使用上海地域：

```text
STORAGE_BACKEND=cos
COS_BUCKET=campus-secondhand-1440900946
COS_REGION=ap-shanghai
COS_PUBLIC_BASE_URL=https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com
COS_SECRET_ID=从云托管环境变量读取
COS_SECRET_KEY=从云托管环境变量读取
```

`STORAGE_BACKEND=cos` 时，如果 COS 配置缺失，后端不会自动退回本地 uploads，而是返回明确错误：

```text
COS 配置缺失，请检查 COS_BUCKET、COS_REGION、COS_SECRET_ID、COS_SECRET_KEY、COS_PUBLIC_BASE_URL
```

COS 对象路径按用途分目录：

```text
product/yyyy/mm/uuid.jpg
avatar/yyyy/mm/uuid.jpg
chat/yyyy/mm/uuid.jpg
refund/yyyy/mm/uuid.jpg
appeal/yyyy/mm/uuid.jpg
```

## 小程序合法域名

当前链路是“先传后端，后端再传 COS”，所以微信公众平台需要配置：

```text
request 合法域名：Flask 云托管后端域名
uploadFile 合法域名：Flask 云托管后端域名
downloadFile 合法域名：https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com
```

旧的 `/uploads/...`、`/uploads/demo/...`、`124.223.146.85` 图片无法从云托管容器自动恢复。项目会把这些旧地址归一化为默认图或 HTTPS 旧地址兜底；要恢复真实图片，需要重新上传，让数据库保存 COS URL。

## 首页推荐 / 最新 / 热门

首页顶部已改为真实可交互的胶囊 Tab：

- 推荐：后端根据用户浏览历史 `product_views`、收藏分类、购买分类做轻量推荐；没有历史时回退热门或最新。
- 最新：`GET /api/v1/products?mode=latest`，按 `created_at` 倒序。
- 热门：`GET /api/v1/products?mode=hot`，后端按 `view_count + favorite_count * 3` 排序。

进入商品详情时，后端会记录或更新当前用户的浏览记录：

```text
product_views: user_id, product_id, category_id, viewed_at
```

同一用户同一商品不会重复插入，只更新 `viewed_at`。

## 常用接口

```text
GET  /api/v1/health
GET  /api/v1/debug/storage
POST /api/v1/auth/wechat-login
GET  /api/v1/users/me
PUT  /api/v1/users/me
GET  /api/v1/products?mode=recommend|latest|hot
GET  /api/v1/products/{id}
POST /api/v1/products
POST /api/v1/files/upload
```

`GET /api/v1/debug/storage` 只在开发模式或 `DEV_TEST_LOGIN_ENABLED=1` 时可用，只返回是否配置了 Secret，不返回密钥原文。

## 本地运行

```powershell
cd "F:\A 软件工程\campus_secondhand_platform\backend"
F:\ProgramData\anaconda3\envs\weixin-app\python.exe .\scripts\init_db.py
F:\ProgramData\anaconda3\envs\weixin-app\python.exe .\run.py
```

本地开发可以使用：

```text
STORAGE_BACKEND=local
```

本地 `uploads/` 仅用于开发调试，云托管正式演示必须使用 COS。

## 云托管部署要点

- 上传代码包使用 `backend/`。
- 端口填 `80`。
- 启动命令使用 Dockerfile 默认命令：

```text
gunicorn --bind 0.0.0.0:${PORT:-80} wsgi:app
```

- `.dockerignore` 已排除 `.env`、`.env.*`，云托管优先读取服务设置里的环境变量。

## 验证图片显示

1. 调用 `GET /api/v1/debug/storage`，确认：
   - `storage_backend=cos`
   - `cos_region=ap-shanghai`
   - `cos_public_base_url=https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com`
   - `has_cos_secret_id=true`
   - `has_cos_secret_key=true`
2. 上传头像，接口返回 URL 必须是 `https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com/avatar/...`。
3. 发布商品图，接口返回 URL 必须是 `https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com/product/...`。
4. 在 COS 控制台确认出现 `avatar/yyyy/mm/...` 和 `product/yyyy/mm/...` 文件。
5. 检查数据库：
   - `files.storage_backend=cos`
   - `files.object_key=product/yyyy/mm/...` 或 `avatar/yyyy/mm/...`
   - `files.url` 是 ap-shanghai COS URL
   - `products.images` 保存 COS URL
   - `users.avatar_url` 保存 COS URL
6. 重启或重新部署云托管后，个人头像、商品详情图、首页商品图仍然显示。

## 验证首页 Tab

1. 打开首页，顶部应显示“推荐 / 最新 / 热门”胶囊 Tab。
2. 点击“最新”，请求 `GET /api/v1/products?mode=latest`，商品按发布时间倒序。
3. 点击“热门”，请求 `GET /api/v1/products?mode=hot`，商品按浏览量和收藏量综合排序。
4. 登录用户进入几个商品详情，再回首页点“推荐”，应优先出现相关分类商品。
5. 切换账号后回到首页，应重新请求列表，不显示上一个账号的推荐结果。
