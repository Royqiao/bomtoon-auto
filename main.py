import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from playwright.sync_api import sync_playwright

BOMTOON_USER = os.environ.get("BOMTOON_USER")
BOMTOON_PASS = os.environ.get("BOMTOON_PASS")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "").strip()
SENDER_PASS = os.environ.get("SENDER_PASS", "").strip()
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL", "").strip()


def send_email(subject, body, image_path=None):
    import traceback

    required = {
        "SENDER_EMAIL": SENDER_EMAIL,
        "SENDER_PASS": SENDER_PASS,
        "RECEIVER_EMAIL": RECEIVER_EMAIL
    }

    missing = [k for k, v in required.items() if not v]

    if missing:
        print(f"❌ 邮件配置缺失: {', '.join(missing)}")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img = MIMEImage(
                    f.read(),
                    name=os.path.basename(image_path)
                )
                msg.attach(img)

        print("正在连接 QQ SMTP 服务器...")

      with smtplib.SMTP("smtp.qq.com", 587, timeout=20) as server:
    server.ehlo()
    server.starttls()
    server.ehlo()

    print("STARTTLS 加密连接成功，正在登录...")

    server.login(
        SENDER_EMAIL.strip(),
        SENDER_PASS.strip()
    )

    print("QQ 邮箱登录成功，正在发送...")

    server.sendmail(
        SENDER_EMAIL.strip(),
        [RECEIVER_EMAIL.strip()],
        msg.as_string()
    )

print("邮件发送成功！")

            if result:
                print(f"⚠️ 部分收件人发送失败: {result}")
                return False

        print(f"✅ 邮件发送成功: {subject}")
        return True

    except Exception as e:
        print(f"❌ 邮件发送失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


def main():
    # 解决变量作用域问题
    current_task = ENV_TASK_TYPE if ENV_TASK_TYPE else "all"

    with sync_playwright() as p:
        print("🚀 启动浏览器...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            print("正在打开登录页面...")
            page.goto("https://www.bomtoon.tw/user/login", timeout=60000)
            page.wait_for_timeout(3000)

            print("正在输入账号密码...")
            page.fill('input[placeholder="請輸入電子信箱"]', BOMTOON_USER)
            page.fill('input[type="password"]', BOMTOON_PASS)

            print("点击登录按钮...")
            try:
                page.get_by_role("button", name="登入").click(timeout=10000)
            except Exception as e:
                print(f"点击按钮失败，尝试回车键: {e}")
                page.press('input[type="password"]', 'Enter')

            page.wait_for_timeout(5000)
            print("登录动作完成，准备前往活动页面...")

            page.goto("https://www.bomtoon.tw/play", timeout=60000)
            page.wait_for_timeout(5000)

            if "user/login" in page.url:
                print("⚠️ 警告：好像还停留在登录页面，登录可能失败了！")
                return

            # --- 执行签到 ---
            if current_task in ["checkin", "all"]:
                print("开始执行每日签到...")
                try:
                    check_btn = page.get_by_role("button", name="CHECK")
                    if check_btn.is_visible() and check_btn.is_enabled():
                        check_btn.click(timeout=10000)
                        page.wait_for_timeout(3000)
                        page.screenshot(path="checkin_result.png", full_page=True)
                        print("✅ 签到成功！")
                        send_email("[Bomtoon] 每日签到成功", "签到完成，详情见附图。", "checkin_result.png")
                    else:
                        print("⚠️ 签到按钮不可用，可能今天已签到。")
                except Exception as e:
                    print(f"签到出错: {e}")

            # --- 执行转盘 ---
            if current_task in ["wheel", "all"]:
                print("开始执行 Lucky 大转盘...")
                try:
                    start_btn = page.get_by_role("button", name="START")
                    if start_btn.is_visible() and start_btn.is_enabled():
                        start_btn.click(timeout=10000)
                        print("已点击转盘，等待动画...")
                        page.wait_for_timeout(8000)
                        page.screenshot(path="wheel_result.png", full_page=True)
                        print("✅ 转盘抽奖完成！")
                        send_email("[Bomtoon] 大转盘抽奖结果", "转盘已触发，请查看附图。", "wheel_result.png")
                    else:
                        print("⚠️ 转盘 START 按钮不可用，可能未到冷却时间。")
                except Exception as e:
                    print(f"转盘出错: {e}")

        except Exception as e:
            print(f"❌ 执行异常: {e}")
            page.screenshot(path="error.png", full_page=True)
            # 遇到异常不再强行发邮件了，免得刷屏报错
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        send_email(
            "测试邮件",
            "这是一封来自 GitHub Actions 的测试邮件"
        )
    except Exception as e:
        print(f"测试邮件异常：{type(e).__name__}: {e}")

    main()
