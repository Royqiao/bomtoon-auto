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
    if not all([BOMTOON_USER, BOMTOON_PASS]):
        print("⚠️ [TW] 未配置账号密码，跳过执行。")
        return

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

        if "user/login" in page.url:
            print("❌ [TW] 登录失败（仍留在登录页），终止后续任务。")
            return
            
        page.goto("https://www.bomtoon.tw/play", timeout=60000)
        page.wait_for_timeout(6000)

        # 1. 每日签到
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

        # 签到后清空可能存在的提示遮罩并刷新页面拉取最新票数
        page.keyboard.press("Escape")
        page.wait_for_timeout(1000)
        page.reload()
        page.wait_for_timeout(5000)

        # 2. 检查大转盘
        print("[TW] 开始检查 Lucky 大转盘...")
        for i in range(10):
            try:
                # 滚动到转盘区域确保渲染
                roulette_card = page.locator('text=Lucky').first
                if roulette_card.is_visible():
                    roulette_card.scroll_into_view_if_needed()
                    page.wait_for_timeout(1500)

                # 【优先检查剩余机会】
                chances = 0
                try:
                    chance_loc = page.locator("text=轉盤機會").first
                    if chance_loc.is_visible(timeout=5000):
                        chance_text = chance_loc.inner_text()
                        match = re.search(r'(\d+)', chance_text)
                        if match:
                            chances = int(match.group(1))
                except Exception as e:
                    print(f"⚠️ [TW] 读取转盘机会异常: {e}")

                print(f"[TW] 当前识别到可用转盘机会: {chances} 次")

                # 只有机会用完（<=0）时，才检查冷却倒计时
                if chances <= 0:
                    cooldown_locator = page.locator("text=後再轉一次").first
                    if cooldown_locator.is_visible():
                        cooldown_text = cooldown_locator.inner_text()
                        hours = int(re.search(r'(\d+)小時', cooldown_text).group(1)) if '小時' in cooldown_text else 0
                        minutes = int(re.search(r'(\d+)分鐘', cooldown_text).group(1)) if '分鐘' in cooldown_text else 0
                        total_minutes = hours * 60 + minutes

                        if 0 < total_minutes <= 30:
                            print(f"[TW] 次数已用完，冷却仅剩 {total_minutes} 分钟，原地等待...")
                            time.sleep(total_minutes * 60 + 30)
                            page.reload()
                            page.wait_for_timeout(5000)
                            continue
                        else:
                            print(f"ℹ️ [TW] 次数已用完，冷却较长 ({total_minutes} 分钟)，结束转盘任务。")
                            break
                    else:
                        print("ℹ️ [TW] 没有剩余转盘机会，结束转盘任务。")
                        break

                print(f"[TW] 准备进行第 {i+1} 次抽奖...")
                join_btn = page.get_by_role("button", name="START").first
                if not join_btn.is_visible():
                    join_btn = page.locator('button:has-text("START")').first

                if join_btn.is_visible():
                    join_btn.scroll_into_view_if_needed()
                    join_btn.click(timeout=10000)
                    page.wait_for_timeout(4000)
                else:
                    print("⚠️ [TW] 未找到外层进入转盘按钮。")
                    break

                print("[TW] 点击中间按钮开始旋转...")
                clicked = False
                start_candidates = [
                    page.locator('dialog button:has(img[src*="btn-start.png"])').first,
                    page.locator('dialog img[src*="btn-start.png"]').first,
                    page.locator('img[src="/images/play/btn-start.png"]').last,
                    page.locator('img[src*="btn-start"]').last
                ]

                for target in start_candidates:
                    try:
                        if target.is_visible(timeout=1500):
                            target.click(timeout=2000, force=True)
                            clicked = True
                            print("✅ [TW] 成功点击中心 START 按钮！")
                            break
                    except Exception:
                        continue

                if not clicked:
                    print("❌ [TW] 弹窗加载失败，未找到 START 按钮。")
                    page.screenshot(path=f"tw_fail_round_{i+1}.png")
                    break

                print("[TW] 旋转中，等待动画结束...")
                page.wait_for_timeout(12000)

               # 检查中奖结果（严格只识别 "免費點券 3C"，抽到 1C 或其他奖项不发邮件）
                page_text = page.locator('body').inner_text()
                
                # 严格匹配：必须是“免費點券”紧跟“3C”（不区分大小写，兼容中间是否有空格）
                is_win_tw = bool(re.search(r'免費點券\s*3\s*C', page_text, re.IGNORECASE))

                if is_win_tw:
                    result_path = f"tw_wheel_win_{i+1}.png"
                    page.screenshot(path=result_path, full_page=True)
                    print("🎉 [TW] 抽到 3 點券（免費點券 3C）！")
                    send_email("[Bomtoon TW] 中奖！抽到 3 點券", "恭喜抽中免費點券 3C！详情见附图。", result_path)
                else:
                    print("💨 [TW] 未抽到 3 點券。")

                page.keyboard.press("Escape")
                page.wait_for_timeout(2000)
                page.reload()
                page.wait_for_timeout(6000)

            except Exception as e:
                print(f"❌ [TW] 转盘循环异常: {e}")
                break

    except Exception as e:
        print(f"❌ [TW] 执行异常: {e}")

# ================= 平台 2：Bomtoon 国际版 =================
def task_bomtoon_com(page):
    print("\n========== 🚀 [Bomtoon COM] 开始执行 ==========")
    if not all([BOMTOON_COM_USER, BOMTOON_COM_PASS]):
        print("⚠️ [COM] 未配置账号密码，跳过执行。")
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
        
        if "user/login" in page.url:
            print("❌ [COM] 登录失败，留在登录页。")
            return
        
        page.goto("https://www.bomtoon.com/play", timeout=60000)
        page.wait_for_timeout(6000)

        

        # 1. 每日签到
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
            else:
                print("⚠️ [COM] 签到按钮不可用（今日已签到）。")
        except Exception as e:
            print(f"❌ [COM] 签到出错: {e}")

        # 签到后清空可能遮挡的提示框，刷新页面拉取最新转盘券
        page.keyboard.press("Escape")
        page.wait_for_timeout(1000)
        page.reload()
        page.wait_for_timeout(5000)

        # 2. 检查大转盘
        print("[COM] 开始检查 Lucky 大转盘...")
        for i in range(10):
            try:
                # 滚动到转盘卡片区域
                roulette_card = page.locator('text=Lucky 봄 룰렛').first
                if roulette_card.is_visible():
                    roulette_card.scroll_into_view_if_needed()
                    page.wait_for_timeout(1500)

                # 【优先检查剩余票数】
                chances = 0
                try:
                    chance_loc = page.locator("text=룰렛 티켓").first
                    if chance_loc.is_visible(timeout=5000):
                        chance_text = chance_loc.inner_text()
                        match = re.search(r'(\d+)', chance_text)
                        if match:
                            chances = int(match.group(1))
                except Exception as e:
                    print(f"⚠️ [COM] 读取转盘票数异常: {e}")

                print(f"[COM] 当前识别到可用转盘机会: {chances} 次")

                # 只有机会用完（<=0）时，才检查倒计时
                if chances <= 0:
                    cooldown_locator = page.locator("text=뒤 한번 더").first
                    if cooldown_locator.is_visible():
                        cooldown_text = cooldown_locator.inner_text()
                        hours = int(re.search(r'(\d+)시간', cooldown_text).group(1)) if '시간' in cooldown_text else 0
                        minutes = int(re.search(r'(\d+)분', cooldown_text).group(1)) if '분' in cooldown_text else 0
                        total_minutes = hours * 60 + minutes

                        if 0 < total_minutes <= 30:
                            print(f"[COM] 票已用完，免费转盘冷却仅剩 {total_minutes} 分钟，原地等待...")
                            time.sleep(total_minutes * 60 + 30)
                            page.reload()
                            page.wait_for_timeout(5000)
                            continue
                        else:
                            print(f"ℹ️ [COM] 票已用完，冷却时间较长 ({total_minutes} 分钟)，结束转盘任务。")
                            break
                    else:
                        print("ℹ️ [COM] 没有剩余转盘次数，结束转盘任务。")
                        break

                print(f"[COM] 准备进行第 {i+1} 次抽奖...")
                # 精确点击【룰렛 돌리기】按钮
                join_btn = page.locator('button:has-text("룰렛 돌리기")').first
                if join_btn.is_visible():
                    join_btn.scroll_into_view_if_needed()
                    join_btn.click(timeout=10000)
                    page.wait_for_timeout(4000)
                else:
                    print("⚠️ [COM] 未找到【룰렛 돌리기】按钮。")
                    break

                print("[COM] 点击中间按钮开始旋转...")
                clicked = False
                
                # 精确匹配策略：优先匹配 <dialog> 内部的按钮或图片，避开背景层和底部时间轴
                start_candidates = [
                    page.locator('dialog button:has(img[src*="btn-start.png"])').first,
                    page.locator('dialog img[src*="btn-start.png"]').first,
                    page.locator('img[src="/images/play/btn-start.png"]').last,
                    page.locator('img[src*="btn-start"]').last
                ]

                for target in start_candidates:
                    try:
                        if target.is_visible(timeout=1500):
                            target.click(timeout=2000, force=True)
                            clicked = True
                            print("✅ [COM] 成功点击弹窗内的 START 按钮！")
                            break
                    except Exception:
                        continue

                if not clicked:
                    debug_path = f"com_fail_round_{i+1}.png"
                    page.screenshot(path=debug_path, full_page=True)
                    print(f"❌ [COM] 弹窗加载失败，实在找不到 START 按钮（已保存截图 {debug_path}）。")
                    break

                print("[COM] 旋转中，等待动画结束...")
                page.wait_for_timeout(12000)

              # 检查中奖结果（增强兼容：支持 "3 보너스 코인"、"3 코인"、"보너스 코인 3" 等各种格式）
                page_text = page.locator('body').inner_text()
                
                # 只要同时出现 "3" 和 "코인"，或者明确出现 "3 보너스 코인"
                is_win = (
                    re.search(r'3\s*(보너스\s*)?코인', page_text) or 
                    re.search(r'(보너스\s*)?코인\s*3', page_text) or
                    "3 보너스 코인" in page_text
                )

                if is_win:
                    result_path = f"com_wheel_win_{i+1}.png"
                    page.screenshot(path=result_path, full_page=True)
                    print("🎉 [COM] 抽到 3 코인！")
                    send_email("[Bomtoon COM] 中奖！抽到 3 코인", "恭喜抽中 3 코인！详情见附图。", result_path)
                else:
                    print("💨 [COM] 未抽到 3 코인。")

                # 关闭弹窗、刷新页面
                page.keyboard.press("Escape")
                page.wait_for_timeout(2000)
                page.reload()
                page.wait_for_timeout(6000)

            except Exception as e:
                print(f"❌ [COM] 转盘循环异常: {e}")
                break

    except Exception as e:
        print(f"❌ [COM] 执行异常: {e}")

# ================= 主程序入口 =================
def main():
    with sync_playwright() as p:
        print("🚀 启动浏览器...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        
        # 执行台湾版任务
        page_tw = context.new_page()
        task_bomtoon_tw(page_tw)
        page_tw.close()

        # 执行国际版任务
        page_com = context.new_page()
        task_bomtoon_com(page_com)
        page_com.close()

        browser.close()
        print("\n✅ 所有平台任务执行完毕。")

if __name__ == "__main__":
    main()
