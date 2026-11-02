import os
import time
import re
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
        page.wait_for_timeout(8000)

        # --- 签到 ---
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
                print("⚠️ [TW] 签到按钮不可用（已签到）。")
        except Exception as e:
            print(f"❌ [TW] 签到出错: {e}")

        # --- 执行转盘 ---
        print("[TW] 开始检查 Lucky 大转盘...")
        for i in range(5):
            try:
                try:
                    chance_text = page.locator("text=轉盤機會").first.inner_text(timeout=5000)
                    print(f"[TW] 当前状态: {chance_text}")
                    match = re.search(r'(\d+)', chance_text)
                    chances = int(match.group(1)) if match else 1
                except Exception:
                    print("⚠️ [TW] 未找到次数文本，可能次数已用完，结束抽奖。")
                    break
                
                if chances <= 0:
                    print("⚠️ [TW] 没有转盘次数了，结束抽奖。")
                    break

                print(f"[TW] 剩余 {chances} 次机会，点击参与...")
                join_btn = page.get_by_role("button", name="START").first
                if join_btn.is_visible() and join_btn.is_enabled():
                    join_btn.click(timeout=10000)
                    page.wait_for_timeout(4000)
                else:
                    print("⚠️ [TW] 下方参与按钮不可用。")
                    break

                print("[TW] 点击中间按钮开始旋转...")
                try:
                    page.locator('img[src="/images/play/btn-start.png"]').first.click(timeout=5000, force=True)
                except Exception:
                    page.locator('div:has-text("START")').last.click(timeout=5000, force=True)

                print("[TW] 旋转中，等待动画结束...")
                page.wait_for_timeout(12000) # 等待 12 秒
                
                # --- 判断中奖结果 ---
                page_text = page.locator('body').inner_text()
                # 匹配包含“點券”且包含“3”的文本
                if re.search(r'點券\s*3', page_text) or re.search(r'3\s*點券', page_text):
                    result_path = f"tw_wheel_win_{i+1}.png"
                    page.screenshot(path=result_path, full_page=True)
                    print(f"🎉 [TW] 第 {i+1} 次抽到 3 點券！发送邮件。")
                    send_email(f"[Bomtoon TW] 中奖！抽到 3 點券", "恭喜！转盘抽到了 3 點券，详情见附图。", result_path)
                else:
                    print(f"💨 [TW] 第 {i+1} 次未抽到 3 點券，不发邮件。")
                
                # 刷新页面准备下一次
                page.keyboard.press("Escape")
                page.wait_for_timeout(2000)
                page.reload()
                page.wait_for_timeout(8000)

            except Exception as e:
                print(f"❌ [TW] 转盘循环中断: {e}")
                break

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
        page.wait_for_timeout(8000)

        if "user/login" in page.url:
            print("⚠️ [COM] 登录失败，跳过。")
            return

        # --- 执行签到 ---
        print("[COM] 开始检查每日签到...")
        try:
            is_already_checked = page.locator("text=내일 또 만나요").is_visible()
            if is_already_checked:
                print("⚠️ [COM] 视觉确认：页面显示已签到，跳过。")
            else:
                check_btn = page.locator('button:has-text("출석체크 하기")').first
                if check_btn.is_visible():
                    check_btn.click(timeout=10000)
                    page.wait_for_timeout(3000)
                    page.screenshot(path="com_checkin_result.png", full_page=True)
                    print("✅ [COM] 执行了签到点击！")
                    send_email("[Bomtoon COM] 每日签到操作", "已执行签到，详情见附图。", "com_checkin_result.png")
                else:
                    print("⚠️ [COM] 找不到签到按钮。")
        except Exception as e:
            print(f"❌ [COM] 签到出错: {e}")

        # --- 执行转盘 ---
        print("[COM] 开始检查 Lucky 大转盘...")
        for i in range(10):
            try:
                try:
                    chance_text = page.locator("text=룰렛 티켓").first.inner_text(timeout=5000)
                    print(f"[COM] 当前状态: {chance_text}")
                    match = re.search(r'(\d+)', chance_text)
                    chances = int(match.group(1)) if match else 1
                except Exception:
                    print("⚠️ [COM] 未找到次数文本，可能次数已用完，结束抽奖。")
                    break
                
                if chances <= 0:
                    print("⚠️ [COM] 没有转盘次数了，结束抽奖。")
                    break

                print(f"[COM] 剩余 {chances} 次机会，点击参与...")
                join_btn = page.locator('button:has-text("룰렛 돌리기")').first
                if join_btn.is_visible() and join_btn.is_enabled():
                    join_btn.click(timeout=10000)
                    page.wait_for_timeout(6000) 
                else:
                    print("⚠️ [COM] 外部转盘参与按钮不可用。")
                    break

                print("[COM] 点击中间按钮开始旋转...")
                try:
                    page.locator('img[src="/images/play/btn-start.png"]').first.click(timeout=5000, force=True)
                except Exception:
                    page.locator('div:has-text("START")').last.click(timeout=5000, force=True)

                print("[COM] 旋转中，等待动画结束...")
                page.wait_for_timeout(12000) 
                
                # --- 判断中奖结果 ---
                page_text = page.locator('body').inner_text()
                # 匹配包含“코인”且包含“3”的文本
                if re.search(r'코인\s*3', page_text) or re.search(r'3\s*코인', page_text):
                    result_path = f"com_wheel_win_{i+1}.png"
                    page.screenshot(path=result_path, full_page=True)
                    print(f"🎉 [COM] 第 {i+1} 次抽到 3 코인！发送邮件。")
                    send_email(f"[Bomtoon COM] 中奖！抽到 3 코인", "恭喜！转盘抽到了 3 코인，详情见附图。", result_path)
                else:
                    print(f"💨 [COM] 第 {i+1} 次未抽到 3 코인，不发邮件。")

                # 刷新页面准备下一次
                page.keyboard.press("Escape")
                page.wait_for_timeout(2000)
                page.reload()
                page.wait_for_timeout(8000)

            except Exception as e:
                print(f"❌ [COM] 转盘循环中断: {e}")
                break

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
