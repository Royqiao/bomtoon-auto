import os
import time
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from playwright.sync_api import sync_playwright

# 从 GitHub Secrets 读取配置
BOMTOON_USER = os.environ.get("BOMTOON_USER")
BOMTOON_PASS = os.environ.get("BOMTOON_PASS")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASS = os.environ.get("SENDER_PASS")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
TASK_TYPE = os.environ.get("TASK_TYPE", "checkin") # 'checkin' 或 'wheel'

def send_email(subject, body, image_path=None):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    if image_path and os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            img = MIMEImage(f.read(), name=os.path.basename(image_path))
            msg.attach(img)

    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print("邮件发送成功")
    except Exception as e:
        print(f"邮件发送失败: {e}")

def main():
    with sync_playwright() as p:
        # 启动无头浏览器
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        try:
            # 1. 登录 Bomtoon
            page.goto("https://www.bomtoon.tw/", timeout=60000)
            page.wait_for_timeout(3000)
            
            # 点击登入入口（需根据实际弹窗调整，此处假设点击 header 登录按钮）
            try:
                page.get_by_text("登入", exact=False).first.click(timeout=5000)
                page.wait_for_timeout(2000)
                page.fill('input[type="email"], input[name="email"]', BOMTOON_USER)
                page.fill('input[type="password"], input[name="password"]', BOMTOON_PASS)
                page.get_by_text("登入", exact=True).click(timeout=5000)
                page.wait_for_timeout(5000)
            except Exception as e:
                print(f"登录步骤可能已自动登录或选择器需更新: {e}")

            # 2. 跳转到签到/活动中心
            page.goto("https://www.bomtoon.tw/play", timeout=60000)
            page.wait_for_timeout(5000)

            if TASK_TYPE == "checkin":
                # 执行每日签到
                print("开始执行每日签到...")
                check_btn = page.get_by_role("button", name="CHECK")
                if check_btn.is_visible() and check_btn.is_enabled():
                    check_btn.click()
                    page.wait_for_timeout(3000)
                    page.screenshot(path="checkin_result.png", full_page=True)
                    send_email("[Bomtoon] 每日签到成功", "今天的 Bomtoon 签到已完成，详情见附图。", "checkin_result.png")
                else:
                    print("签到按钮不可用，可能今天已签到。")

            elif TASK_TYPE == "wheel":
                # 执行幸运大转盘抽奖
                print("开始执行 Lucky 大转盘...")
                start_btn = page.get_by_role("button", name="START")
                if start_btn.is_visible() and start_btn.is_enabled():
                    start_btn.click()
                    page.wait_for_timeout(8000) # 等待转盘动画结束
                    page.screenshot(path="wheel_result.png", full_page=True)
                    
                    # 尝试抓取页面上的奖励文本（根据实际 DOM 调整）
                    reward_text = "转盘已触发，请查看附图确认奖励。"
                    try:
                        reward_el = page.locator(".reward-popup, .result-text").first
                        if reward_el.is_visible():
                            reward_text = reward_el.inner_text()
                    except:
                        pass
                    
                    send_email("[Bomtoon] 大转盘抽奖结果", f"抽奖结果：{reward_text}\n请查看附图。", "wheel_result.png")
                else:
                    print("转盘 START 按钮不可用，可能未到冷却时间。")

        except Exception as e:
            print(f"执行过程中出现异常: {e}")
            page.screenshot(path="error.png", full_page=True)
            send_email("[Bomtoon] 任务执行异常", f"错误信息: {e}", "error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
