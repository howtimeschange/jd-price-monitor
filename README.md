# JD Price Monitor（京东价格监控）

> 监控京东自营店铺所有 SKU 的前台价格，自动发现破价商品，通过钉钉推送告警。

## 技术方案

本项目使用 **[bb-browser](https://github.com/epiral/bb-browser)** 方案抓取价格，完全绕过京东反爬检测：

- bb-browser 通过 Chrome 扩展在用户真实浏览器内执行 JS，使用浏览器本身的 Cookie 和网络
- 不需要任何 API Key，不会被风控拦截
- 价格通过滚动触发懒加载，100% 准确

## 项目结构

```
jd-price-monitor/
├── cli.py                    # ✨ 交互式 CLI 入口（推荐）
├── config.yaml               # 主配置文件
├── main.py                   # 巡检核心逻辑（可独立运行）
├── scrape_list.py            # 价格导出核心逻辑（可独立运行）
├── requirements.txt          # Python 依赖
├── crontab.example           # 定时任务示例
├── adapters/
│   └── jd/
│       └── shop-prices.js    # bb-browser 适配器（复制到 ~/.bb-browser/bb-sites/jd/）
└── src/
    ├── config.py             # 配置加载 & 保存
    ├── sku_fetcher.py        # 店铺 SKU 列表抓取
    ├── price_fetcher.py      # 前台价格抓取
    ├── checker.py            # 破价检测逻辑
    ├── dingtalk.py           # 钉钉告警
    └── storage.py            # 历史记录存储
```

## 快速开始

### 1. 前置依赖

- Python 3.9+
- Node.js 18+
- Chrome 浏览器（已登录京东）

### 2. 安装 bb-browser

```bash
npm install -g bb-browser

# 启动 bb-browser daemon
node $(npm root -g)/bb-browser/dist/daemon.js
```

然后在 Chrome 中安装 bb-browser 扩展：
1. 打开 `chrome://extensions/` → 开启"开发者模式"
2. 点击"加载已解压的扩展程序"
3. 选择 `$(npm root -g)/bb-browser/extension` 目录

### 3. 安装适配器

```bash
mkdir -p ~/.bb-browser/bb-sites/jd
cp adapters/jd/shop-prices.js ~/.bb-browser/bb-sites/jd/
```

### 4. 开启 Chrome 远程调试

启动 Chrome 时加上调试端口参数：

```bash
# macOS
open -a "Google Chrome" --args --remote-debugging-port=9222

# Windows
chrome.exe --remote-debugging-port=9222
```

确认连接：
```bash
bb-browser tab list --port 9222
```

### 5. 安装 Python 依赖

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 6. 配置

编辑 `config.yaml`，必填：

```yaml
shop:
  shop_id: "1000462158"        # 你的店铺 ID
  shop_name: "店铺名称"

monitor:
  price_ratio_threshold: 0.50  # 低于吊牌价 50% 时告警

dingtalk:
  webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=你的token"
```

---

## 使用方式

### 推荐：交互式 CLI

```bash
python cli.py
```

启动后显示主菜单，可完成所有操作：

```
  JD Price Monitor  京东价格监控系统

  当前配置
  店铺      ASICS亚瑟士京东自营旗舰店
  阈值      50折  (50%)
  巡检间隔  120 分钟
  Webhook   ✅ 已配置

  请选择操作：
  > 📦  导出全店商品价格  →  Excel
    🔍  立即执行一次破价巡检
    🔁  循环巡检（按间隔自动运行）
    ⏰  创建系统定时任务（cron）
    ⚙️   设置  —  店铺 / 阈值 / Webhook
    ❌  退出
```

**设置菜单**支持：
- 粘贴任意京东店铺 URL，自动解析 shop_id
- 修改破价阈值（如输入 `50` 即 5折）
- 配置钉钉 Webhook，支持加签 + 一键测试
- 修改巡检间隔

**循环巡检**支持前台运行和后台进程两种模式。

**定时任务**支持自动写入 crontab（macOS/Linux）或复制到剪贴板。

### 命令行直接运行

```bash
# 导出价格 Excel
python scrape_list.py

# 单次巡检
python main.py

# 循环巡检
python main.py --loop
```

---

## 工作原理

```
scrape_list.py
│
├── bb-browser tab list        # 找到 mall.jd.com tab
├── bb-browser eval navigate   # 切换到目标页
└── bb-browser site jd/shop-prices  # 在浏览器内执行 adapter
    │
    ├── 等待价格元素渲染（最多 5s）
    ├── 分段滚动（10 步）触发懒加载价格
    ├── 读取 DOM：SKU ID / 名称 / 价格 / 链接
    ├── XHR 补查 p.3.cn（针对仍为空的价格）
    └── 返回 JSON + nextUrl（下一页链接）
```

## 告警示例

破价时钉钉会收到：

```
⚠️ 破价预警 | ASICS亚瑟士京东自营旗舰店
监控阈值：吊牌价 50折
本次发现 2 个 SKU 疑似破价

ASICS亚瑟士男款跑步鞋GEL-KAYANO...
- SKU: 100012043978
- 吊牌价: ¥1299.00 → 前台价: ¥599.00 (46.1%)
- 商品链接
```

## 注意事项

- bb-browser daemon 和 Chrome 必须在运行状态，`scrape_list.py` / `main.py` 才能工作
- `cookies.json` 已加入 `.gitignore`，不会被提交
- 吊牌价来源于商品列表页的划线价；若京东未展示划线价，该 SKU 跳过检测
- 建议在 Mac 不休眠状态下运行，或部署到服务器（需要有图形界面支持 Chrome）

## License

MIT
