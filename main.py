import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from playwright.sync_api import sync_playwright

# ================= 读取环境配置 =================
BOMTOON_USER = os.environ.get("BOMTOON_USER")
BOMTOON_PASS = os.environ.get("BOMTOON_PASS")
BOMTOON_COM_USER = os.environ.get("BOMTOON_COM_USER")
BOMTOON_COM_PASS = os.environ.get("BOMTOON_COM_PASS")

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "").strip()
SENDER_PASS = os.environ.get("SENDER_PASS", "").strip()
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL", "").strip()


# ================= 邮件发送工具函数 =================
def send_email(subject, body, image_path=None):
    if not all([SENDER_EMAIL, SENDER_PASS, RECEIVER_EMAIL]):
        print("邮件配置不完整，跳过发送。")
        return False
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
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
            
        print(f"✅ 邮件发送成功：{subject}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败：{type(e).__name__}: {e}")
        return False


# ================= 平台 1：Bomtoon 台湾版 =================
def task_bomtoon_tw(page):
    print("\n========== 🚀 [Bomtoon TW] 开始执行 ==========")
    try:
        page.goto("https://www.bomtoon.tw/user/login", timeout=60000)
        page.wait_for_timeout(3000)
        page.fill('input[placeholder="請輸入電子信箱"]', BOMTOON_USER)
        page.fill('input[type="password"]', BOMTOON_PASS)
        try:
            page.get_by_role("button", name="登入").click(timeout=10000)
        except Exception:
            page.press('input[type="password"]', 'Enter')
        page.wait_for_timeout(5000)

        page.goto("https://www.bomtoon.tw/play", timeout=60000)
        page.wait_for_timeout(5000)

        # 签到
        print("[TW] 开始检查每日签到...")
        try:
            check_btn = page.get_by_role("button", name="CHECK")
            if check_btn.is_visible() and check_btn.is_enabled():
                check_btn.click(timeout=10000)
                page.wait_for_timeout(3000)
                page.screenshot(path="tw_checkin_result.png", full_page=True)
                print("✅ [TW] 签到成功！")
                send_email("[Bomtoon TW] 每日签到成功", "签到完成，详情见附图。", "tw_checkin_result.png")
            else:
                print("⚠️ [TW] 签到按钮不可用，可能今天已签到。")
        except Exception as e:
            print(f"❌ [TW] 签到出错: {e}")

        # 转盘
        print("[TW] 开始检查 Lucky 大转盘...")
        try:
            start_btn = page.get_by_role("button", name="START")
            if start_btn.is_visible() and start_btn.is_enabled():
                start_btn.click(timeout=10000)
                page.wait_for_timeout(10000)
                page.screenshot(path="tw_wheel_result.png", full_page=True)
                print("✅ [TW] 转盘抽奖完成！")
                send_email("[Bomtoon TW] 大转盘抽奖结果", "转盘已触发，请查看附图。", "tw_wheel_result.png")
            else:
                print("⚠️ [TW] 转盘 START 按钮不可用。")
        except Exception as e:
            print(f"❌ [TW] 转盘出错: {e}")

    except Exception as e:
        print(f"❌ [TW] 执行异常: {e}")


# ================= 平台 2：Bomtoon 国际版 =================
def task_bomtoon_com(page):
    print("\n========== 🚀 [Bomtoon COM] 开始执行 ==========")
    if not all([BOMTOON_COM_USER, BOMTOON_COM_PASS]):
        print("⚠️ [COM] 未配置账号密码，跳过。")
        return

    try:
        page.goto("https://www.bomtoon.com/user/login", timeout=60000)
        page.wait_for_timeout(3000)
        page.fill('input[placeholder="이메일을 입력해주세요."]', BOMTOON_COM_USER)
        page.fill('input[type="password"]', BOMTOON_COM_PASS)
        try:
            page.locator('button:has-text("로그인")').first.click(timeout=10000)
        except Exception:
            page.press('input[type="password"]', 'Enter')
        page.wait_for_timeout(5000)

        page.goto("https://www.bomtoon.com/play", timeout=60000)
        page.wait_for_timeout(5000)

        if "user/login" in page.url:
            print("⚠️ [COM] 登录失败，跳过。")
            return

        # --- 执行签到 (加入了防误判逻辑) ---
        print("[COM] 开始检查每日签到...")
        try:
            # 检查按钮文本是否变成了表示“已签到”的词
            # 很多韩国网站签完后按钮会变成 "출석완료" (签到完成)
            check_btn = page.locator('button:has-text("CHECK"), button:has-text("출석체크")').first
            
            if check_btn.is_visible() and check_btn.is_enabled():
                # 先截个图，记录点击前的状态
                check_btn.click(timeout=10000)
                page.wait_for_timeout(3000) # 等待弹窗出现
                page.screenshot(path="com_checkin_result.png", full_page=True)
                
                # 点击后，检查页面上是否出现了“已完成”或者“已签到”的字眼
                page_content = page.content()
                if any(word in page_content for word in ["이미 출석", "출석 완료", "이미 완료", "Already checked", "已完成"]):
                    print("⚠️ [COM] 点击了签到，但网页提示今天已经签过了，取消发邮件。")
                else:
                    print("✅ [COM] 签到成功！")
                    send_email("[Bomtoon COM] 每日签到成功", "签到完成，详情见附图。", "com_checkin_result.png")
            else:
                print("⚠️ [COM] 签到按钮不可用，可能今天已签到。")
        except Exception as e:
            print(f"❌ [COM] 签到出错: {e}")

        # --- 执行转盘 ---
        print("[COM] 开始检查 Lucky 大转盘...")
        try:
            start_btn = page.locator('button:has-text("START")').first
            if start_btn.is_visible() and start_btn.is_enabled():
                start_btn.click(timeout=10000)
                page.wait_for_timeout(10000)
                page.screenshot(path="com_wheel_result.png", full_page=True)
                print("✅ [COM] 转盘抽奖完成！")
                send_email("[Bomtoon COM] 大转盘抽奖结果", "转盘已触发，请查看附图。", "com_wheel_result.png")
            else:
                print("⚠️ [COM] 转盘 START 按钮不可用。")
        except Exception as e:
            print(f"❌ [COM] 转盘出错: {e}")

    except Exception as e:
        print(f"❌ [COM] 执行异常: {e}")


def main():
    with sync_playwright() as p:
        print("🚀 启动浏览器...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        page_tw = context.new_page()
        task_bomtoon_tw(page_tw)
        page_tw.close()

        page_com = context.new_page()
        task_bomtoon_com(page_com)
        page_com.close()

        browser.close()
        print("\n✅ 所有平台任务执行完毕。")

if __name__ == "__main__":
    main()
