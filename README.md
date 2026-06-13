# 校园二手交易平台微信小程序

这是一个“微信小程序 + 微信云托管 Flask 后端 + MySQL 文档适配层 + COS 图片持久化”的校园二手交易平台。

## 核心链路

```text
小程序
  -> wx.cloud.callContainer 调用 Flask API
  -> wx.uploadFile 上传图片到 Flask 后端
  -> Flask 后端上传图片到 COS
  -> 数据库保存商品、用户、文件记录
```

后端 API 前缀是 `/api/v1`。

## 云托管环境变量

正式环境图片必须走 COS，上海地域配置如下：

```text
DB_BACKEND=mysql
STORAGE_BACKEND=cos
COS_BUCKET=campus-secondhand-1440900946
COS_REGION=ap-shanghai
COS_PUBLIC_BASE_URL=https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com
COS_SECRET_ID=腾讯云 SecretId
COS_SECRET_KEY=腾讯云 SecretKey
WECHAT_AUTH_MODE=wechat
WECHAT_APPID=你的小程序 AppID
WECHAT_SECRET=你的小程序 AppSecret
DEV_TEST_LOGIN_ENABLED=1
INIT_TOKEN=你的初始化口令
```

`STORAGE_BACKEND=cos` 时，如果 COS 配置缺失，后端会直接报错，不会自动退回本地 `uploads`。

## 小程序合法域名

当前上传链路是“小程序先传 Flask 后端，后端再传 COS”：

```text
request 合法域名：Flask 云托管后端域名
uploadFile 合法域名：Flask 云托管后端域名
downloadFile 合法域名：https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com
```

旧的 `/uploads/...`、`/uploads/demo/...`、`124.223.146.85` 图片不能自动恢复；项目会显示默认图。要恢复真实图片，需要重新上传，让数据库保存 COS URL。

## 首页商品 Tab

首页有三个真实后端模式：

```text
推荐：GET /api/v1/products?mode=recommend
最新：GET /api/v1/products?mode=latest
热门：GET /api/v1/products?mode=hot
```

- 推荐：对全部在售商品计算推荐分，不再把某些商品直接过滤掉。
- 最新：按 `created_at` 倒序。
- 热门：按 `view_count + favorite_count * 3` 排序。

首页默认打开“最新”，这样刚发布且审核通过的商品最容易被看到。

## 测试账号

开发版小程序会显示测试账号按钮：

```text
测试买家 A：18800000002 / buyer123456
测试买家 B：18800000003 / buyerb123456
测试管理员：18800000000 / admin123456
测试卖家：18800000001 / seller123456
```

测试账号由 `backend/scripts/init_db.py` 创建或更新。测试登录接口需要云托管环境变量：

```text
DEV_TEST_LOGIN_ENABLED=1
```

## 清理并重建演示商品

如果首页出现旧的 `COS????-134927-9` 这类测试商品，重新部署后在云托管“云端调试”调用：

```text
POST /api/v1/debug/demo-products/reset
Header:
X-Init-Token: 你的 INIT_TOKEN
```

这个接口会：

- 删除带 `seed_code` 的旧演示商品。
- 删除标题以 `COS` 开头的旧测试商品。
- 删除标题以 `pytest-` 开头的测试商品。
- 清理这些商品的浏览和收藏记录。
- 重建一批正常中文标题、真实本地演示图的商品。
- 更新测试用户昵称，避免乱码。

本地也可以运行：

```powershell
cd "F:\A 软件工程\campus_secondhand_platform\backend"
F:\ProgramData\anaconda3\envs\weixin-app\python.exe .\scripts\init_db.py --reset-demo
```

普通初始化，不清理旧测试商品：

```powershell
F:\ProgramData\anaconda3\envs\weixin-app\python.exe .\scripts\init_db.py
```

## 本地运行

```powershell
cd "F:\A 软件工程\campus_secondhand_platform\backend"
F:\ProgramData\anaconda3\envs\weixin-app\python.exe .\scripts\init_db.py
F:\ProgramData\anaconda3\envs\weixin-app\python.exe .\run.py
```

本地开发可以用：

```text
STORAGE_BACKEND=local
```

云托管正式演示必须用：

```text
STORAGE_BACKEND=cos
```

## 云托管部署

- 上传代码包使用 `backend/`。
- 端口填 `80`。
- 启动命令使用 Dockerfile 默认命令：

```text
gunicorn --bind 0.0.0.0:${PORT:-80} wsgi:app
```

`.dockerignore` 已排除 `.env`、`.env.*`，云托管优先读取服务设置里的环境变量。

## 验证

1. 重新部署云托管。
2. 调用 `POST /api/v1/debug/demo-products/reset` 清理旧测试商品。
3. 微信开发者工具重新编译。
4. 点“测试买家 B”，应登录成功并回到首页。
5. 首页“最新”能看到刚发布并审核通过的商品。
6. “推荐”和“热门”不再显示 `COS????` 旧测试商品。
7. 商品卡片、测试用户名称、状态文案不应再出现乱码。
