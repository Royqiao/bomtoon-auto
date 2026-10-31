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

# 任务类型：checkin, wheel, 或者留空(全部执行)
TASK_TYPE = os.environ.get("TASK_TYPE", "").strip().lower()

def send_email(subject, body, image_path=None):
    """发送邮件通知"""
    if not all([SENDER_EMAIL, SENDER_PASS, RECEIVER_EMAIL]):
        print("邮件配置不完整，跳过发送。")
        return

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
        print(f"✅ 邮件发送成功: {subject}")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

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
            # ================= 1. 登录阶段 =================
            print("正在打开登录页面...")
            page.goto("https://www.bomtoon.tw/user/login", timeout=60000)
            page.wait_for_timeout(3000) # 等待页面渲染
            
            print("正在输入账号密码...")
            # 根据你找到的网页代码：账号框 placeholder，密码框 type
            page.fill('input[placeholder="請輸入電子信箱"]', BOMTOON_USER)
            page.fill('input[type="password"]', BOMTOON_PASS)
            
            print("点击登录按钮...")
            # 尝试点击包含“登入”文字的元素，如果找不到则尝试提交按钮
            try:
                page.get_by_text("登入", exact=True).click(timeout=5000)
            except:
                page.locator('button[type="submit"]').first.click(timeout=5000)
                
            page.wait_for_timeout(5000) # 等待登录完成并跳转
            
            # ================= 2. 任务执行阶段 =================
            print("正在前往活动中心页面...")
            page.goto("https://www.bomtoon.tw/play", timeout=60000)
            page.wait_for_timeout(5000)
            
            # 如果没有指定 TASK_TYPE（比如你在网页上手动点击 Run workflow），默认把签到和转盘都跑一遍
            if not TASK_TYPE:
                TASK_TYPE = "all"

            # --- 执行签到 ---
            if TASK_TYPE in ["checkin", "all"]:
                print("开始执行每日签到...")
                try:
                    check_btn = page.get_by_role("button", name="CHECK")
                    if check_btn.is_visible() and check_btn.is_enabled():
                        check_btn.click()
                        page.wait_for_timeout(3000)
                        page.screenshot(path="checkin_result.png", full_page=True)
                        print("签到成功，准备发送邮件。")
                        send_email("[Bomtoon] 每日签到成功", "今天的 Bomtoon 签到已完成，详情见附图。", "checkin_result.png")
                    else:
                        print("⚠️ 签到按钮不可用，可能今天已签到。")
                except Exception as e:
                    print(f"签到执行出错: {e}")

            # --- 执行转盘 ---
            if TASK_TYPE in ["wheel", "all"]:
                print("开始执行 Lucky 大转盘...")
                try:
                    start_btn = page.get_by_role("button", name="START")
                    if start_btn.is_visible() and start_btn.is_enabled():
                        start_btn.click()
                        print("已点击转盘，等待动画结束...")
                        page.wait_for_timeout(8000) # 等待转盘动画结束
                        page.screenshot(path="wheel_result.png", full_page=True)
                        
                        # 尝试抓取页面上的奖励文本（需要根据实际网页微调）
                        reward_text = "转盘已触发，请查看附图确认奖励。"
                        try:
                            # 尝试捕获弹窗或页面上的结果文本
                            reward_el = page.locator(".reward-popup, .result-text, [class*='toast'], [class*='modal']").first
                            if reward_el.is_visible():
                                reward_text = reward_el.inner_text()
                        except:
                            pass
                        
                        print(f"抽奖结束，发送邮件: {reward_text}")
                        send_email("[Bomtoon] 大转盘抽奖结果", f"抽奖结果：{reward_text}\n请查看附图。", "wheel_result.png")
                    else:
                        print("⚠️ 转盘 START 按钮不可用，可能未到冷却时间。")
                except Exception as e:
                    print(f"转盘执行出错: {e}")

        except Exception as e:
            print(f"❌ 执行过程中出现严重异常: {e}")
            page.screenshot(path="error.png", full_page=True)
            send_email("[Bomtoon] 任务执行异常", f"错误信息: {e}\n请查看附图错误现场。", "error.png")
        finally:
            browser.close()
            print("浏览器已关闭。")

if __name__ == "__main__":
    main()
