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

首页分类、关键词和排序会组合生效：

```text
GET /api/v1/products?category=book&keyword=高数&mode=latest
GET /api/v1/products?category=digital&mode=hot
```

商品卡片右上角收藏按钮调用真实收藏接口：

```text
POST /api/v1/favorites
DELETE /api/v1/favorites/{product_id}
```

未登录时，小程序会引导到登录页。

## UI 参考页落地说明

本次已按 `校园二手小程序UI参考页面合集_一次性完整实现版.docx` 收敛页面和功能边界：

- 首页删除大横幅 Banner，保留标题、搜索、分类、推荐/最新/热门、商品双列列表。
- 登录页保留微信登录、手机号登录/注册和“开发测试账号”卡片。
- 发布页顺序为图片、标题、AI 标题建议、描述、AI 润色描述、价格、分类、成色、交易校区、底部操作。
- 商品详情保留轮播、价格、分享、收藏、描述、卖家信息、所在校区、猜你喜欢、底部操作。
- 聊天页保留订单/商品卡片、文字消息、图片/视频上传、已读状态和发送按钮。
- 订单详情按买家/卖家视角切换联系人和操作按钮。
- 售后列表保留“我买的 / 我卖的”和中文状态筛选，售后详情只展示当前视角的对方联系人。
- 我的页面展示当前账号真实统计，空数据为 0，切换账号后刷新 `/users/me`。

明确不展示的内容：

- 地图导航、查看地图按钮。
- 标签体系、原价/划线价、保修。
- 假认证、回复快、态度好、交易愉快等没有真实数据支撑的标签。
- 底部“分类”Tab；分类入口只保留在首页和筛选页。

### 参考图二次重做验收

本次按用户补充的 11 张参考图重新收紧前端视觉，重点调整卡片层级、间距、圆角、按钮位置和绿色主视觉，不是单纯换色。覆盖页面：

```text
登录页、首页、发布商品页、消息列表页、我的页面、商品详情页、个人主页、
买家订单详情页、卖家订单详情页、售后管理页、售后详情页、聊天页
```

首页分类固定从统一字典渲染为 `数码电子 / 教材书籍 / 服饰鞋包 / 生活家居 / 全部分类`，即使分类接口短暂失败也会显示本地统一字典，不会只剩两个分类。

功能边界同步处理：

- 首页“筛选”进入真实分类筛选页，不保留无功能假入口。
- 登录页保留微信登录、手机号登录、手机号注册和开发测试账号入口。
- 商品详情页只展示后端已有的商品描述、卖家信息、所在校区、推荐、收藏、私聊和购买；不展示无真实字段支撑的认证、保修、态度标签。
- 订单和售后页只显示中文状态文案，不展示裸 ID、`undefined`、`null` 或横杠占位。

本地静态预览图板位于：

```text
ui-preview/ui-preview-contact-sheet.png
```

该图板用于逐页说明页面结构和视觉层级；最终以微信开发者工具编译后的真机/模拟器效果为准。

## 统一商品分类

统一分类字典定义在：

```text
backend/app/domain/categories.py
miniprogram/utils/constants.js
```

稳定编码和中文名如下：

```text
digital  数码电子
book     教材书籍
clothing 服饰鞋包
home     生活家居
other    其他
```

数据库商品字段：

```text
category         稳定分类编码
category_name    前端展示中文名
category_source  manual / auto / seed / legacy
category_id      兼容旧分类表的 ObjectId
```

后端接口支持：

- `POST /api/v1/products`：发布时保存分类；未传分类时自动分类。
- `PUT /api/v1/products/{id}`：编辑时支持修改分类。
- `GET /api/v1/products`：支持 `category`，并能与 `keyword`、`mode`、`min_price`、`max_price`、`date_from`、`date_to` 组合。
- `GET /api/v1/products/{id}`：返回 `category/category_name/category_source`。
- `GET /api/v1/products/{id}/recommendations`：返回真实猜你喜欢商品，排除当前商品和不可交易商品。

自动分类优先使用关键词规则，不生成字典外分类。手动选择分类时写入 `category_source=manual`，不会被自动分类覆盖；无法判断时归为 `other`。

验收样例：

```text
高等数学 同济七版 上册 -> 教材书籍
罗技机械键盘 茶轴 -> 数码电子
白色双肩包 -> 服饰鞋包
宿舍台灯 -> 生活家居
无法判断的商品 -> 其他
```

## 统一校区

商品和个人资料里的校区只允许以下两个值：

```text
东校区
西校区
```

发布商品、编辑商品、资料编辑和分类筛选均使用固定选项，不再支持手填校区。后端会校验商品发布、商品编辑、商品列表筛选、注册和资料更新中的 `campus` 字段；传入其他值会返回参数校验错误。

历史数据中的 `主校区` 统一映射为 `东校区`。如果部署环境还有旧数据，可在后端目录运行迁移脚本：

```powershell
cd "F:\A 软件工程\campus_secondhand_platform\backend"
F:\ProgramData\anaconda3\envs\weixin-app\python.exe .\scripts\normalize_campus.py
F:\ProgramData\anaconda3\envs\weixin-app\python.exe .\scripts\normalize_campus.py --apply
```

第一条命令只统计匹配数量，第二条命令才会实际写入。

## 猜你喜欢与分享

商品详情页的“猜你喜欢”来自真实接口：

```text
GET /api/v1/products/{product_id}/recommendations?limit=6
```

推荐逻辑优先同分类、同校区和价格相近商品，再参考浏览/收藏热度与发布时间；没有真实推荐时前端隐藏模块。

商品详情页分享使用小程序 `onShareAppMessage`，分享路径携带商品 ID：

```text
/pages/product/detail/index?id={product_id}
```

如果分享进入的商品已不可见，后端会返回明确的 404 提示，而不是展示空页面。

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

本地后端验证：

```powershell
cd "F:\A 软件工程\campus_secondhand_platform\backend"
$env:PYTHONNOUSERSITE='1'
F:\ProgramData\anaconda3\envs\weixin-app\python.exe -m compileall app scripts
F:\ProgramData\anaconda3\envs\weixin-app\python.exe -m pytest -q
```

本次校区与发布页相关验证结果：`24 passed`。

1. 重新部署云托管。
2. 调用 `POST /api/v1/debug/demo-products/reset` 清理旧测试商品。
3. 微信开发者工具重新编译。
4. 点“测试买家 B”，应登录成功并回到首页。
5. 首页“最新”能看到刚发布并审核通过的商品。
6. “推荐”和“热门”不再显示 `COS????` 旧测试商品。
7. 商品卡片、测试用户名称、状态文案不应再出现乱码。

## 2026-06-20 UI 路由页修复记录

- 已按 `miniprogram/app.json` 确认真实路由，未新建未路由的假页面。
- 重构页面：首页、发布商品、消息列表、我的、商品详情、个人主页、我买到的、我卖出的、订单详情、售后管理、售后详情、聊天页。
- 新增 `miniprogram/utils/format.js` 统一金额、时间、校区、商品/订单/售后状态映射，避免模板直出 `undefined`、`null`、`--`、`主校区` 或 ISO 时间。
- 商品卡片组件已改为图片内右上角收藏按钮，并格式化价格、校区、分类、库存、卖家和浏览量。
- 验证：`node --check` 通过；目标 WXML 标签配对检查通过；目标文件无 BOM。
- 本机未找到可调用的微信开发者工具 CLI 或 miniprogram-ci，因此未伪造模拟器截图，需在微信开发者工具中进一步真机预览。
