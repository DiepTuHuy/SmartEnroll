import os
import sys
import time
import json
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".smartenroll_config.json")

def print_status(status_msg):
    print(f"[STATUS] {status_msg}", flush=True)

def dismiss_facebook_popups(driver):
    """Đóng các popup/dialog của Facebook (Review audience, Update settings, v.v.)
    Không đóng hộp thoại Share hoặc Create post."""
    try:
        for _ in range(4):
            closed_any = False

            # Bấm Continue / Save trong các dialog xác nhận quyền riêng tư
            spans = driver.find_elements(By.XPATH,
                "//div[@role='dialog']//span[text()='Continue' or text()='Tiếp tục' "
                "or text()='Save' or text()='Lưu' or text()='Got it' or text()='Đã hiểu' "
                "or text()='Next' or text()='Tiếp']")
            for el in spans:
                try:
                    # Bỏ qua nếu nằm bên trong Create post dialog
                    in_composer = el.find_elements(By.XPATH,
                        "./ancestor::div[@aria-label='Create post' or @aria-label='Tạo bài viết']")
                    if in_composer:
                        continue
                    if el.is_displayed():
                        try:
                            el.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", el)
                        time.sleep(2)
                        closed_any = True
                        break
                except Exception:
                    pass

            if closed_any:
                continue

            # Bấm nút Close/Got it chung — nhưng không đóng composer
            generic_close = driver.find_elements(By.XPATH,
                "//*[@aria-label='Close' or @aria-label='Đóng' "
                "or @aria-label='Got it' or @aria-label='Đã hiểu']")
            for el in generic_close:
                try:
                    in_composer = el.find_elements(By.XPATH,
                        "./ancestor::div[@aria-label='Create post' or @aria-label='Tạo bài viết' "
                        "or @aria-label='Close composer dialogue']")
                    if in_composer:
                        continue
                    if el.is_displayed():
                        try:
                            el.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", el)
                        time.sleep(2)
                        closed_any = True
                        break
                except Exception:
                    pass

            if not closed_any:
                break
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        print_status("ERROR: Thiếu ID sự kiện")
        return

    event_id = sys.argv[1]
    event_title = sys.argv[2] if len(sys.argv) > 2 else f"Thông báo sự kiện {event_id}"

    # 1. Đọc config từ file cấu hình SmartEnroll
    if not os.path.exists(CONFIG_FILE):
        print_status("ERROR: Không tìm thấy file cấu hình .smartenroll_config.json")
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    username = config.get("username")
    password = config.get("password")

    if not username or not password:
        print_status("ERROR: Cấu hình tài khoản/mật khẩu trống")
        return

    print_status("STARTING_CHROME")
    options = webdriver.ChromeOptions()

    # Sử dụng profile Chrome riêng biệt để lưu session đăng nhập FB
    profile_dir = os.path.join(os.getcwd(), ".chrome_profile_std")

    # Xoá lock file cũ nếu có
    lock_file = os.path.join(profile_dir, "SingletonLock")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except Exception:
            pass

    options.add_argument(f"user-data-dir={profile_dir}")
    options.add_argument("--disable-notifications")
    options.add_argument("--start-maximized")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print_status(f"ERROR: Không thể khởi chạy Chrome. Lỗi: {str(e)}")
        return

    try:
        # 2. Đăng nhập Cổng thông tin UTH
        print_status("LOGGING_IN_PORTAL")
        driver.get("https://portal.ut.edu.vn/")
        time.sleep(4)

        if "/login" in driver.current_url or len(driver.find_elements(By.TAG_NAME, "input")) > 0:
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                type_attr = inp.get_attribute("type")
                placeholder = inp.get_attribute("placeholder") or ""
                if type_attr == "text" or "sinh viên" in placeholder.lower() or "mssv" in placeholder.lower() or "tài khoản" in placeholder.lower():
                    inp.clear()
                    inp.send_keys(username)
                elif type_attr == "password" or "mật khẩu" in placeholder.lower():
                    inp.clear()
                    inp.send_keys(password)

            time.sleep(1)
            buttons = driver.find_elements(By.TAG_NAME, "button")
            clicked = False
            for b in buttons:
                b_text = b.text.strip()
                if "Đăng nhập" in b_text or "ĐĂNG NHẬP" in b_text:
                    b.click()
                    clicked = True
                    break

            if not clicked:
                for b in buttons:
                    if b.get_attribute("type") == "submit":
                        b.click()
                        break
            time.sleep(6)

        # 3. Điều hướng tới trang sự kiện trên portal để ghi nhận lịch sử
        print_status("LOADING_PORTAL_EVENT")
        event_url = f"https://portal.ut.edu.vn/event/{event_id}"
        driver.get(event_url)
        time.sleep(3)

        # 4. Mở Facebook
        print_status("NAVIGATING_FACEBOOK")
        driver.get("https://www.facebook.com")
        time.sleep(4)

        # Tự động đăng nhập Facebook nếu có cấu hình
        fb_username = config.get("fb_username")
        fb_password = config.get("fb_password")

        email_fields = driver.find_elements(By.XPATH, "//input[@id='email' or @name='email']")
        pass_fields = driver.find_elements(By.XPATH, "//input[@id='pass' or @name='pass']")

        if email_fields and pass_fields and fb_username and fb_password:
            print_status("LOGGING_IN_FB")
            try:
                email_fields[0].clear()
                email_fields[0].send_keys(fb_username)
                pass_fields[0].clear()
                pass_fields[0].send_keys(fb_password)
                time.sleep(1)

                login_buttons = driver.find_elements(By.XPATH, "//button[@name='login' or @type='submit']")
                if login_buttons:
                    login_buttons[0].click()
                else:
                    pass_fields[0].submit()

                print_status("WAITING_FB_REDIRECT")
                time.sleep(7)
            except Exception as e:
                print(f"Error autofilling Facebook login: {e}")

        # Chờ đăng nhập Facebook thành công (tối đa 3 phút)
        logged_in = False
        print_status("CHECKING_FB_LOGIN")
        for i in range(180):
            try:
                post_box = driver.find_elements(By.XPATH,
                    "//*[contains(@aria-label, 'on your mind') or contains(text(), 'on your mind') "
                    "or contains(@aria-label, 'đang nghĩ gì') or contains(text(), 'đang nghĩ gì') "
                    "or contains(@aria-label, 'Bạn đang nghĩ gì thế')]")
                nav_links = driver.find_elements(By.XPATH,
                    "//a[contains(@href, '/friends/') or contains(@href, '/groups/') "
                    "or contains(@href, '/watch/') or contains(@href, '/marketplace/')]")

                if post_box or nav_links:
                    logged_in = True
                    break
            except Exception:
                pass

            if i % 10 == 0:
                print_status("WAITING_FB_LOGIN")
            time.sleep(1)

        if not logged_in:
            print_status("ERROR: Hết thời gian chờ đăng nhập Facebook")
            return

        # 5. Tìm kiếm bài viết bằng 100% tiêu đề sự kiện gốc
        print_status("SEARCHING_FB")

        # Dùng toàn bộ tiêu đề — không rút ngắn, không lọc từ
        search_query = event_title.strip()
        encoded_query = urllib.parse.quote(search_query)
        search_url = f"https://www.facebook.com/search/posts?q={encoded_query}"
        print(f"Search URL: {search_url}", flush=True)

        driver.get(search_url)
        time.sleep(5)
        dismiss_facebook_popups(driver)

        # 6. Tìm bài viết đầu tiên trong kết quả
        print_status("FINDING_POST")

        # Cuộn để load kết quả
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(2)

        # Nút Share trên Facebook có aria-label cố định này
        share_buttons = driver.find_elements(By.XPATH,
            "//div[@role='button' and @aria-label='Send this to friends or post it on your profile.']")

        # Fallback tiếng Việt
        if not share_buttons:
            share_buttons = driver.find_elements(By.XPATH,
                "//div[@role='button' and @aria-label='Gửi cho bạn bè hoặc đăng lên trang cá nhân của bạn.']")

        print(f"Found {len(share_buttons)} share buttons", flush=True)

        # Lấy nút Share đầu tiên hiển thị (Facebook đã sắp xếp kết quả theo độ phù hợp)
        target_share_btn = None
        for btn in share_buttons:
            if btn.is_displayed():
                target_share_btn = btn
                break

        if not target_share_btn:
            print_status("ERROR: Không tìm thấy bài viết nào trên Facebook Search")
            return

        # 7. Cuộn đến nút Share và bấm
        print_status("SHARING_POST")

        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_share_btn)
            time.sleep(2)
        except Exception:
            pass

        try:
            target_share_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", target_share_btn)

        time.sleep(3)

        # 8. Bấm "Share now" trong popup để đăng lên trang cá nhân
        # Popup mặc định đã chọn "Feed" (trang cá nhân)
        print_status("CONFIRMING_SHARE")

        # Thay đổi quyền riêng tư thành Public (Công khai) nếu chưa được thiết lập
        privacy_btn = None
        privacy_xpaths = [
            "//div[@role='dialog']//div[@role='button' and (contains(@aria-label, 'privacy') or contains(@aria-label, 'riêng tư') or contains(@aria-label, 'audience') or contains(@aria-label, 'đối tượng'))]",
            "//div[@role='dialog']//div[@role='button' and (text()='Friends' or text()='Bạn bè' or text()='Public' or text()='Công khai')]",
            "//div[@role='dialog']//*[contains(text(), 'Friends') or contains(text(), 'Bạn bè') or contains(text(), 'Public') or contains(text(), 'Công khai')]/ancestor::div[@role='button']"
        ]

        for xpath in privacy_xpaths:
            try:
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed():
                        privacy_btn = el
                        break
                if privacy_btn:
                    break
            except Exception:
                pass

        if privacy_btn:
            p_text = privacy_btn.text.lower()
            p_aria = (privacy_btn.get_attribute("aria-label") or "").lower()
            if "public" not in p_text and "công khai" not in p_text and "public" not in p_aria and "công khai" not in p_aria:
                try:
                    privacy_btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", privacy_btn)
                time.sleep(3)

                # Chọn option "Public" hoặc "Công khai"
                public_opt = None
                public_xpaths = [
                    "//*[text()='Public']",
                    "//*[text()='Công khai']",
                    "//span[text()='Public']",
                    "//span[text()='Công khai']",
                    "//div[@role='button']//*[contains(text(), 'Public') or contains(text(), 'Công khai')]"
                ]
                for xpath in public_xpaths:
                    try:
                        els = driver.find_elements(By.XPATH, xpath)
                        for el in els:
                            if el.is_displayed():
                                public_opt = el
                                break
                        if public_opt:
                            break
                    except Exception:
                        pass

                if public_opt:
                    try:
                        public_opt.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", public_opt)
                    time.sleep(2)

                    # Bấm nút "Done" để xác nhận
                    done_btn = None
                    done_xpaths = [
                        "//div[@role='dialog']//div[@role='button']//*[text()='Done' or text()='Xong']",
                        "//div[@role='dialog']//span[text()='Done' or text()='Xong']/ancestor::div[@role='button']",
                        "//div[@role='dialog']//div[@role='button' and @aria-label='Done']",
                        "//div[@role='dialog']//div[@role='button' and (contains(., 'Done') or contains(., 'Xong'))]"
                    ]
                    for xpath in done_xpaths:
                        try:
                            els = driver.find_elements(By.XPATH, xpath)
                            for el in els:
                                if el.is_displayed():
                                    done_btn = el
                                    break
                            if done_btn:
                                break
                        except Exception:
                            pass

                    if done_btn:
                        try:
                            done_btn.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", done_btn)
                        time.sleep(3)
                    else:
                        print("Warning: Done button in privacy selector not found")
                else:
                    print("Warning: Public option not found in privacy selector")
            else:
                print("Privacy is already Public")
        else:
            print("Warning: Privacy selector button not found")

        # Bấm "Share now"
        share_now_clicked = False
        for xpath in [
            "//div[@role='button' and @aria-label='Share now']",
            "//span[text()='Share now']/ancestor::div[@role='button']",
            "//span[text()='Chia sẻ ngay']/ancestor::div[@role='button']",
        ]:
            try:
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed():
                        try:
                            el.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", el)
                        share_now_clicked = True
                        break
                if share_now_clicked:
                    break
            except Exception:
                pass

        if not share_now_clicked:
            print_status("ERROR: Không tìm thấy nút Share now để xác nhận chia sẻ")
            return

        time.sleep(8)  # Đợi bài viết được đăng lên dòng thời gian

        # 9. Truy cập trang cá nhân để chụp ảnh minh chứng bài viết đã được chia sẻ công khai
        print_status("TAKING_SCREENSHOT")
        driver.get("https://www.facebook.com/me")
        time.sleep(7)

        # Cuộn xuống để tìm bài viết vừa chia sẻ trên dòng thời gian
        post_container = None
        exact_found = False
        clean_title = event_title.strip()
        search_sub = clean_title[:30] if len(clean_title) > 30 else clean_title

        for scroll_step in range(6):
            # Tìm xem có bài viết nào chứa tiêu đề sự kiện không
            xpaths = [
                f"//*[contains(text(), '{search_sub}')]",
                f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_sub.lower()}')]"
            ]
            found_el = None
            for xpath in xpaths:
                try:
                    els = driver.find_elements(By.XPATH, xpath)
                    for el in els:
                        if el.is_displayed():
                            found_el = el
                            break
                    if found_el:
                        break
                except Exception:
                    pass

            if found_el:
                # Tìm container cha ngoài cùng có chứa tên tác giả "Từ Huy Diệp" và có role="article"
                ancestor = found_el
                candidate = None
                for level in range(1, 16):
                    try:
                        ancestor = ancestor.find_element(By.XPATH, "..")
                        role = ancestor.get_attribute("role")
                        text = ancestor.text
                        if "Từ Huy Diệp" in text:
                            if role == "article":
                                post_container = ancestor
                                exact_found = True
                                break
                            else:
                                candidate = ancestor
                    except Exception:
                        break
                if not exact_found and candidate:
                    post_container = candidate
                    exact_found = True
                    
                if exact_found:
                    print(f"Found exact post card by matching text at step {scroll_step}", flush=True)
                    break

            # Fallback nếu chưa tìm thấy: lưu bài viết có tên tác giả "Từ Huy Diệp" đầu tiên xuất hiện
            if not post_container:
                try:
                    name_elements = driver.find_elements(By.XPATH, "//*[text()='Từ Huy Diệp' or contains(text(), 'Từ Huy Diệp')]")
                    for ne in name_elements:
                        if ne.is_displayed():
                            ancestor = ne
                            for _ in range(8):
                                try:
                                    ancestor = ancestor.find_element(By.XPATH, "..")
                                    if ancestor.get_attribute("role") == "article":
                                        post_container = ancestor
                                        break
                                except Exception:
                                    break
                            if post_container:
                                print(f"Stored fallback post card from step {scroll_step}", flush=True)
                                break
                except Exception:
                    pass

            # Cuộn xuống một chút để load thêm dữ liệu
            driver.execute_script("window.scrollBy(0, 600);")
            time.sleep(2)

        os.makedirs("DRL", exist_ok=True)
        timestamp = int(time.time())
        filename = f"share_event_{event_id}_{timestamp}.png"
        screenshot_path = os.path.join("DRL", filename)

        if post_container:
            # Cuộn bài viết lên trên cùng và chừa lề cho thanh điều hướng
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", post_container)
                time.sleep(1)
                driver.execute_script("window.scrollBy(0, -150);")
                time.sleep(2)
            except Exception:
                pass
            
            # Chụp ảnh cắt riêng khung bài viết (element screenshot) để ra ảnh sạch đẹp nhất
            try:
                post_container.screenshot(screenshot_path)
                print("Captured element-level screenshot of the post card", flush=True)
            except Exception as e:
                print(f"Element screenshot failed, falling back to full window screenshot. Error: {e}", flush=True)
                driver.save_screenshot(screenshot_path)
        else:
            print("Warning: Không tìm thấy khung bài viết để cuộn, sẽ chụp toàn màn hình tại vị trí hiện tại", flush=True)
            driver.save_screenshot(screenshot_path)

        print_status(f"SUCCESS:{filename}")

    except Exception as e:
        print_status(f"ERROR: Trục trặc tự động hóa. Lỗi: {str(e)}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
