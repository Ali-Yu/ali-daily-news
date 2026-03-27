
# 📰 Daily News Digest Bot

每天北京时间 **08:00** 自动抓取中国、台湾、日本、美国/英国热点新闻，通过 **Gemini 2.5 Flash** 生成约10分钟朗读内容，以精美 HTML 邮件发送到你的邮箱。

---

## 📁 项目结构

```
├── .github/
│   └── workflows/
│       └── daily_digest.yml   # GitHub Actions 定时任务
├── scripts/
│   └── news_digest.py         # 主程序
├── requirements.txt
└── README.md
```

---

## 🚀 部署步骤

### 第一步：准备163邮箱授权码

> 用于发送邮件，**不是登录密码**

1. 登录 [163邮箱](https://mail.163.com)
2. 右上角 → **设置** → **POP3/SMTP/IMAP**
3. 开启 **SMTP服务**
4. 生成**授权码**，保存备用

---

### 第二步：在 GitHub 仓库配置 Secrets

进入你的 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

依次添加以下4个 Secret：

| Secret 名称      | 值                                      |
|------------------|-----------------------------------------|
| `GEMINI_API_KEY` | 你的 Gemini API Key                     |
| `SMTP_USER`      | 你的163邮箱地址（如 alibro666@163.com） |
| `SMTP_PASSWORD`  | 第一步获取的163授权码                   |
| `TO_EMAIL`       | 收件邮箱（alibro666@163.com）           |

---

### 第三步：上传文件到仓库

将以下文件按目录结构上传到你的 GitHub 仓库：

```
.github/workflows/daily_digest.yml
scripts/news_digest.py
requirements.txt
```

---

### 第四步：测试运行

1. 进入仓库 → **Actions** 标签
2. 点击 **Daily News Digest**
3. 点击右侧 **Run workflow** → **Run workflow**
4. 等待约3~5分钟，检查邮箱

---

## ⏰ 定时计划

| 时区         | 时间        |
|--------------|-------------|
| 北京时间 CST | 每天 08:00  |
| UTC          | 每天 00:00  |

---

## 📡 新闻来源

| 模块             | 来源                     | 语言                   |
|------------------|--------------------------|------------------------|
| 🇨🇳 中国        | 新华网、中国数字时代     | 简体中文               |
| 🇹🇼 台湾        | 自由时报                 | 简体中文               |
| 🇯🇵 日本        | 朝日新聞                 | 日文（汉字标注假名）   |
| 🇺🇸🇬🇧 US&UK  | NYT、Washington Post、BBC | 英文                  |

---

## 🔧 自定义

- **修改发送时间**：编辑 `.github/workflows/daily_digest.yml` 中的 `cron` 表达式
- **添加新闻源**：编辑 `scripts/news_digest.py` 中的 `MODULES` 列表，增加 `feeds` 条目
- **调整内容长度**：修改各模块 `prompt` 中的字数目标

---

## ❗ 常见问题

**Q: 163邮箱发送失败？**
A: 确认使用的是**授权码**而非登录密码；确认 SMTP 服务已开启。

**Q: Gemini API 报错？**
A: 检查 `GEMINI_API_KEY` 是否正确；免费额度是否用完。

**Q: RSS 抓取失败？**
A: 部分源可能有地区限制，GitHub Actions 服务器在美国，通常可正常访问。
