# 163 邮箱 SMTP 配置指南

## 配置步骤

1. 登录 mail.163.com → 设置 → POP3/SMTP/IMAP
2. 开启「IMAP/SMTP服务」
3. 手机验证 → 生成**授权码**（不是邮箱密码）
4. 保存到 `~/.zshrc`: `export SMTP_163_AUTH='授权码'`

## SMTP 参数

```
主机: smtp.163.com
端口: 465 (SSL)
用户: 18649723134@163.com
密码: <授权码>
```

## Python 发送示例

```python
import smtplib
from email.mime.text import MIMEText

msg = MIMEText('正文', 'plain', 'utf-8')
msg['Subject'] = '主题'
msg['From'] = '18649723134@163.com'
msg['To'] = 'recipient@example.com'

with smtplib.SMTP_SSL('smtp.163.com', 465, timeout=15) as server:
    server.login('18649723134@163.com', '<授权码>')
    server.send_message(msg)
```

## 限制

- 500 封/天
- 单封收件人数限制
- 国内企邮（飞书/阿里/腾讯）送达率高
- 国际邮箱可能进垃圾箱

## 发送工作流

1. 起草邮件 → 展示给用户确认
2. 用户批准 → 发送到目标 + 同时发送副本到 xiongbojian007@gmail.com
3. 每封单独确认，不批量发送
