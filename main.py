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
        print(f"❌ 邮件发送失败：{e}")
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

        print("[TW] 开始检查 Lucky 大转盘...")
        for i in range(5):
            try:
                cooldown_locator = page.locator("text=後再轉一次").first
                if cooldown_locator.is_visible():
                    cooldown_text = cooldown_locator.inner_text()
                    hours = int(re.search(r'(\d+)小時', cooldown_text).group(1)) if '小時' in cooldown_text else 0
                    minutes = int(re.search(r'(\d+)分鐘', cooldown_text).group(1)) if '分鐘' in cooldown_text else 0
                    total_minutes = hours * 60 + minutes
                    
                    if total_minutes <= 30:
                        print(f"[TW] 冷却仅剩 {total_minutes} 分钟，脚本原地等待...")
                        time.sleep(total_minutes * 60 + 30)
                        page.reload()
                        page.wait_for_timeout(5000)
                    else:
                        print(f"⚠️ [TW] 冷却时间较长 ({total_minutes} 分钟 > 30分钟)，本次跳过。")
                        break

                try:
                    chance_text = page.locator("text=轉盤機會").first.inner_text(timeout=5000)
                    match = re.search(r'(\d+)', chance_text)
                    chances = int(match.group(1)) if match else 1
                except Exception:
                    break
                
                if chances <= 0:
                    break

                print(f"[TW] 剩余 {chances} 次机会，点击参与...")
                join_btn = page.get_by_role("button", name="START").first
                if join_btn.is_visible() and join_btn.is_enabled():
                    join_btn.click(timeout=10000, force=True)
                    page.wait_for_timeout(4000)
                else:
                    break

                print("[TW] 点击中间按钮开始旋转...")
                # ⚠️ 修改：智能重试点击内部按钮
                clicked = False
                for _ in range(5):  # 最多等 5 轮，每轮 2 秒
                    try:
                        page.locator('img[src="/images/play/btn-start.png"]').first.click(timeout=2000, force=True)
                        clicked = True
                        break
                    except Exception:
                        page.wait_for_timeout(2000)
                
                if not clicked:
                    try:
                        page.locator('div:has-text("START")').last.click(timeout=2000, force=True)
                        clicked = True
                    except:
                        print("❌ [TW] 弹窗加载失败，实在找不到 START 按钮。")
                        break

                print("[TW] 旋转中，等待动画结束...")
                page.wait_for_timeout(12000) 
                
                page_text = page.locator('body').inner_text()
                if re.search(r'點券\s*3', page_text) or re.search(r'3\s*點券', page_text):
                    result_path = f"tw_wheel_win_{i+1}.png"
                    page.screenshot(path=result_path, full_page=True)
                    print(f"🎉 [TW] 抽到 3 點券！")
                    send_email(f"[Bomtoon TW] 中奖！抽到 3 點券", "恭喜！详情见附图。", result_path)
                else:
                    print(f"💨 [TW] 未抽到 3 點券。")
                
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
            return

        print("[COM] 开始检查每日签到...")
        try:
            is_already_checked = page.locator("text=내일 또 만나요").is_visible()
            if not is_already_checked:
                check_btn = page.locator('button:has-text("출석체크 하기")').first
                if check_btn.is_visible():
                    check_btn.click(timeout=10000)
                    page.wait_for_timeout(3000)
                    page.screenshot(path="com_checkin_result.png", full_page=True)
                    print("✅ [COM] 执行了签到点击！")
                    send_email("[Bomtoon COM] 每日签到操作", "已执行签到，详情见附图。", "com_checkin_result.png")
        except Exception as e:
            print(f"❌ [COM] 签到出错: {e}")

        print("[COM] 开始检查 Lucky 大转盘...")
        for i in range(10):
            try:
                cooldown_locator = page.locator("text=뒤 한번 더").first
                if cooldown_locator.is_visible():
                    cooldown_text = cooldown_locator.inner_text()
                    hours = int(re.search(r'(\d+)시간', cooldown_text).group(1)) if '시간' in cooldown_text else 0
                    minutes = int(re.search(r'(\d+)분', cooldown_text).group(1)) if '분' in cooldown_text else 0
                    total_minutes = hours * 60 + minutes
                    
                    if total_minutes <= 30:
                        print(f"[COM] 冷却仅剩 {total_minutes} 分钟，脚本原地等待...")
                        time.sleep(total_minutes * 60 + 30)
                        page.reload()
                        page.wait_for_timeout(5000)
                    else:
                        print(f"⚠️ [COM] 冷却时间较长 ({total_minutes} 分钟 > 30分钟)，本次跳过。")
                        break

                try:
                    chance_text = page.locator("text=룰렛 티켓").first.inner_text(timeout=5000)
                    match = re.search(r'(\d+)', chance_text)
                    chances = int(match.group(1)) if match else 1
                except Exception:
                    break
                
                if chances <= 0:
                    break

                print(f"[COM] 剩余 {chances} 次机会，点击参与...")
                
                # 1. 精确点击卡片上的【룰렛 돌리기】按钮（图1）
                join_btn = page.locator('button:has-text("룰렛 돌리기")').first
                if join_btn.is_visible():
                    join_btn.scroll_into_view_if_needed()
                    join_btn.click(timeout=10000)
                    page.wait_for_timeout(3000)
                else:
                    print("⚠️ [COM] 未找到参与按钮，退出循环。")
                    break

                print("[COM] 点击中间按钮开始旋转...")
                
                # 2. 精确点击 <dialog> 弹窗内的 START 按钮（图2）
                # 优先定位 dialog 内部包含 btn-start 的 button，彻底避开底层卡片的小图标
                start_btn = page.locator('dialog button:has(img[src*="btn-start.png"])').first
                
                # 备用选择器：如果没走 dialog 标签，则取页面上最后一个 btn-start.png 图片
                start_img_fallback = page.locator('img[src="/images/play/btn-start.png"]').last

                clicked = False
                for _ in range(5):
                    try:
                        if start_btn.is_visible(timeout=1500):
                            start_btn.click(timeout=2000, force=True)
                            clicked = True
                            print("✅ [COM] 成功点击弹窗内的 START 按钮！")
                            break
                        elif start_img_fallback.is_visible(timeout=1500):
                            start_img_fallback.click(timeout=2000, force=True)
                            clicked = True
                            print("✅ [COM] 成功点击弹窗内的 START 图片！")
                            break
                    except Exception:
                        page.wait_for_timeout(1000)

                if not clicked:
                    debug_path = f"com_wheel_fail_{i+1}.png"
                    page.screenshot(path=debug_path, full_page=True)
                    print(f"❌ [COM] 弹窗加载失败，实在找不到 START 按钮（已保存截图 {debug_path}）。")
                    break

                print("[COM] 旋转中，等待动画结束...")
                page.wait_for_timeout(12000) 
                
                # 检查中奖结果
                page_text = page.locator('body').inner_text()
                if re.search(r'코인\s*3', page_text) or re.search(r'3\s*코인', page_text):
                    result_path = f"com_wheel_win_{i+1}.png"
                    page.screenshot(path=result_path, full_page=True)
                    print(f"🎉 [COM] 抽到 3 코인！")
                    send_email(f"[Bomtoon COM] 中奖！抽到 3 코인", "恭喜！详情见附图。", result_path)
                else:
                    print(f"💨 [COM] 未抽到 3 코인。")

                # 关闭弹窗（按 ESC 或点击右上角关闭）
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
