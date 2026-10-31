import os
import time
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from playwright.sync_api import sync_playwright

BOMTOON_USER = os.environ.get("BOMTOON_USER")
BOMTOON_PASS = os.environ.get("BOMTOON_PASS")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASS = os.environ.get("SENDER_PASS")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
TASK_TYPE = os.environ.get("TASK_TYPE", "").strip().lower()

def send_email(subject, body, image_path=None, retries=3):
    if not all([SENDER_EMAIL, SENDER_PASS, RECEIVER_EMAIL]):
        print("邮件配置不完整，跳过发送。")
        return

    for attempt in range(retries):
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    img = MIMEImage(f.read(), name=os.path.basename(image_path))
                    msg.attach(img)

            with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=15) as server:
                server.login(SENDER_EMAIL, SENDER_PASS)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            print(f"✅ 邮件发送成功: {subject}")
            return
        except Exception as e:
            print(f"❌ 第 {attempt + 1} 次邮件发送失败: {e}")
            if attempt < retries - 1:
                time.sleep(3)
    print("❌ 邮件发送最终失败。")

def main():
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
                # 精确打击：找 role 为 button 且名字是“登入”的元素
                page.get_by_role("button", name="登入").click(timeout=10000)
            except Exception as e:
                print(f"尝试点击按钮失败，改用回车键提交: {e}")
                # 备用方案：直接在密码框里按回车键
                page.press('input[type="password"]', 'Enter')

            page.wait_for_timeout(5000)
            print("登录动作完成，准备前往活动页面...")

            page.goto("https://www.bomtoon.tw/play", timeout=60000)
            page.wait_for_timeout(5000)

            # 判断是否真的登录成功了
            if "user/login" in page.url:
                print("⚠️ 警告：好像还停留在登录页面，登录可能失败了！")
                page.screenshot(path="login_fail.png", full_page=True)
                send_email("[Bomtoon] 登录失败", "脚本未能成功登录，请查看截图。", "login_fail.png")
                return

            if not TASK_TYPE:
                TASK_TYPE = "all"

            if TASK_TYPE in ["checkin", "all"]:
                print("开始执行每日签到...")
                try:
                    check_btn = page.get_by_role("button", name="CHECK")
                    if check_btn.is_visible() and check_btn.is_enabled():
                        check_btn.click(timeout=10000)
                        page.wait_for_timeout(3000)
                        page.screenshot(path="checkin_result.png", full_page=True)
                        send_email("[Bomtoon] 每日签到成功", "签到完成，详情见附图。", "checkin_result.png")
                    else:
                        print("⚠️ 签到按钮不可用，可能今天已签到。")
                except Exception as e:
                    print(f"签到出错: {e}")

            if TASK_TYPE in ["wheel", "all"]:
                print("开始执行 Lucky 大转盘...")
                try:
                    start_btn = page.get_by_role("button", name="START")
                    if start_btn.is_visible() and start_btn.is_enabled():
                        start_btn.click(timeout=10000)
                        print("已点击转盘，等待动画...")
                        page.wait_for_timeout(8000)
                        page.screenshot(path="wheel_result.png", full_page=True)
                        send_email("[Bomtoon] 大转盘抽奖结果", "转盘已触发，请查看附图。", "wheel_result.png")
                    else:
                        print("⚠️ 转盘 START 按钮不可用。")
                except Exception as e:
                    print(f"转盘出错: {e}")

        except Exception as e:
            print(f"❌ 执行异常: {e}")
            page.screenshot(path="error.png", full_page=True)
            send_email("[Bomtoon] 任务执行异常", f"错误信息: {e}", "error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
