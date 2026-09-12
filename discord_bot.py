import os
import asyncio
import subprocess
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from core_state import get_app_state
from concurrent.futures import ThreadPoolExecutor

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ADMIN_ID_STR = os.getenv('ADMIN_ID')
ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR and ADMIN_ID_STR.isdigit() else None


# ==================== UI COMPONENTS ====================

class ModeButton(discord.ui.Button):
    def __init__(self, mode_name, target):
        self.mode_name = mode_name
        self.target = target
        style = discord.ButtonStyle.primary if mode_name == "normal" else discord.ButtonStyle.danger
        label = "Chế độ Thường (Normal)" if mode_name == "normal" else "Chế độ Nhanh (Turbo)"
        super().__init__(style=style, label=label)
        
    async def callback(self, interaction: discord.Interaction):
        
        dkhp_state = get_app_state(interaction.user.id)
        if dkhp_state.is_spamming:
            await interaction.response.send_message("⚠️ Bot đang chạy spam một lệnh khác rồi! Bấm [⏹ Dừng Spam] để dừng trước.", ephemeral=True)
            return
            
        await interaction.response.send_message(f"🔥 Bắt đầu chiến dịch spam ID `{self.target['id']}` ({self.target['name']}) ở chế độ `{self.mode_name}`!", ephemeral=True)
        
        def run():
            dkhp_state.run_spam_loop([self.target], self.mode_name)
            
        asyncio.create_task(asyncio.to_thread(run))

class ModeView(discord.ui.View):
    def __init__(self, target):
        super().__init__(timeout=None)
        self.add_item(ModeButton("normal", target))
        self.add_item(ModeButton("turbo", target))

class ClassButton(discord.ui.Button):
    def __init__(self, cls_info):
        self.cls_info = cls_info
        ten = cls_info.get('tenLopHocPhan') or cls_info.get('tenMonHoc') or cls_info.get('tenHocPhan') or ""
        ma = cls_info.get('maLopHocPhan') or ""
        display_name = f"{ma} - {ten}" if ma and ten else (ten or ma or str(cls_info.get('id', 'Unknown')))
        
        label_text = f"Spam {display_name}"
        if len(label_text) > 80:
            label_text = label_text[:77] + "..."
            
        super().__init__(style=discord.ButtonStyle.primary, label=label_text)
        
    async def callback(self, interaction: discord.Interaction):
        
        dkhp_state = get_app_state(interaction.user.id)
        id_lop = self.cls_info.get('id')
        ten = self.cls_info.get('tenLopHocPhan') or self.cls_info.get('tenMonHoc') or self.cls_info.get('tenHocPhan') or ""
        ma = self.cls_info.get('maLopHocPhan') or ""
        ten_lop = f"{ma} - {ten}" if ma and ten else (ten or ma or str(id_lop))
        target = {"id": id_lop, "name": ten_lop, "is_conditional": False}
        
        embed = discord.Embed(title="🚀 Chọn Tốc Độ Spam", description=f"Lớp: **{ten_lop}**", color=discord.Color.orange())
        embed.add_field(name="Chế độ Thường (Normal)", value="Tốc độ an toàn, tránh bị ban IP.", inline=False)
        embed.add_field(name="Chế độ Nhanh (Turbo)", value="Tốc độ cao nhất, tăng tỷ lệ win nhưng dễ bị ban IP.", inline=False)
        
        view = ModeView(target)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ClassView(discord.ui.View):
    def __init__(self, classes):
        super().__init__(timeout=None)
        for cls in classes[:25]:
            self.add_item(ClassButton(cls))

class SubjectSelect(discord.ui.Select):
    def __init__(self, subjects):
        self.subjects = subjects
        options = []
        for sub in subjects[:25]:
            ten = sub.get('tenHocPhan', 'Unknown')
            if sub.get('isBatBuoc'):
                ten += " (Bắt buộc)"
            ma = sub.get('maHocPhan', 'Unknown')
            tc = sub.get('soTinChi', '?')
            if len(ten) > 97:
                ten = ten[:94] + "..."
            options.append(discord.SelectOption(label=ten, description=f"Mã: {ma} | Tín chỉ: {tc}", value=ma))
            
        super().__init__(placeholder="Chọn nhiều môn học để xem lớp...", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        from core_state import get_app_state
        import asyncio
        import concurrent.futures
        
        dkhp_state = get_app_state(interaction.user.id)
        
        await interaction.response.defer(ephemeral=True)
        
        for ma_hoc_phan in self.values:
            await interaction.followup.send(f"⏳ Đang tải lớp & thời khóa biểu của môn `{ma_hoc_phan}`...", ephemeral=True)
            
            url = "https://portal.ut.edu.vn/api/v1/dkhp/getLopHocPhanChoDangKy"
            params = {
                "idDot": dkhp_state.config.get('id_dot'),
                "maHocPhan": ma_hoc_phan,
                "isLocTrung": "false",
                "isLocTrungWithoutElearning": "false"
            }
            
            def fetch(m_params):
                try:
                    resp = dkhp_state.request_with_retry("GET", url, params=m_params, timeout=10)
                    if resp.status_code == 200:
                        cls_data = resp.json().get('data') or resp.json().get('body') or []
                        if cls_data:
                            def get_tkb(c):
                                details = dkhp_state.fetch_class_detail(c.get('id'))
                                c['tkb_str'] = dkhp_state.format_schedule(details)
                                return c
                            
                            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                                cls_data = list(executor.map(get_tkb, cls_data))
                        return cls_data
                except Exception as e:
                    return None
                return None

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, fetch, params)
            
            if data is None:
                await interaction.followup.send(f"❌ Lỗi mạng hoặc token hết hạn khi tải môn {ma_hoc_phan}.", ephemeral=True)
                continue
                
            if not data:
                await interaction.followup.send(f"Không có lớp nào đang mở cho môn {ma_hoc_phan}.", ephemeral=True)
                continue

            embed = discord.Embed(title=f"🏫 Các Lớp: {ma_hoc_phan}", color=discord.Color.green())
            for cls in data[:25]:
                ten = cls.get('tenLopHocPhan') or cls.get('tenMonHoc') or cls.get('tenHocPhan') or ""
                ma = cls.get('maLopHocPhan') or ""
                id_lop = cls.get('id', 'Unknown')
                display_name = f"{ma} - {ten}" if ma and ten else (ten or ma or str(id_lop))
                sl = f"{cls.get('soLuongDaDangKy', 0)}/{cls.get('soLuong', 0)}"
                tkb = cls.get('tkb_str', 'Không có thông vị lịch học')
                embed.add_field(name=display_name, value=f"**Mã Lớp (ID):** `{id_lop}` | **Sĩ số:** {sl}\n🕒 {tkb}", inline=False)
                
            if len(data) > 25:
                embed.set_footer(text=f"Hiển thị 25/{len(data)} lớp. Bấm nút bên dưới để chọn chế độ SPAM!")
            else:
                embed.set_footer(text="Bấm nút bên dưới tương ứng với lớp để chọn chế độ SPAM!")
                
            view = ClassView(data)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class SubjectView(discord.ui.View):
    def __init__(self, subjects):
        super().__init__(timeout=None)
        self.add_item(SubjectSelect(subjects))

class PeriodSelect(discord.ui.Select):
    def __init__(self, dots):
        options = []
        
        def get_term_name(dot_id_str):
            try:
                dot_id = int(dot_id_str)
                if dot_id >= 71:
                    diff = dot_id - 71
                    year_offset = diff // 3
                    term_offset = diff % 3
                    start_year = 24 + year_offset
                    end_year = 25 + year_offset
                    term_str = "HK1" if term_offset == 0 else ("HK2" if term_offset == 1 else "HK Hè")
                    return f"{term_str} {start_year}-{end_year}"
            except:
                pass
            return None

        # Sort dots descending by ID to ensure newest is first
        try:
            dots = sorted(dots, key=lambda x: int(x.get('id') or x.get('idDot') or x.get('maDot') or 0), reverse=True)
        except:
            pass

        for i, d in enumerate(dots[:25]):
            dot_id = str(d.get('id') or d.get('idDot') or d.get('maDot'))
            api_name = d.get('tenHocKy') or d.get('tenDot') or d.get('tenDotDangKy')
            derived = get_term_name(dot_id)
            ten = str(api_name) if api_name else (derived if derived else f"Đợt {dot_id}")
            
            if i == 0:
                ten = f"{ten} (Mới nhất)"
            if len(ten) > 97:
                ten = ten[:94] + "..."
            options.append(discord.SelectOption(label=ten, value=dot_id))
            
        super().__init__(placeholder="Chọn đợt đăng ký để thao tác...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):

        dkhp_state = get_app_state(interaction.user.id)
        selected = self.values[0]
        dkhp_state.config['id_dot'] = selected
        
        await interaction.response.send_message(f"✅ Đã chuyển sang đợt đăng ký ID: `{selected}`.\nBạn có thể bấm [📚 Đăng ký Học phần] để tải môn học của đợt này.", ephemeral=True)

class PeriodView(discord.ui.View):
    def __init__(self, dots):
        super().__init__(timeout=None)
        self.add_item(PeriodSelect(dots))

class LoginModal(discord.ui.Modal, title='Đăng nhập Cổng Trường'):
    username = discord.ui.TextInput(
        label='Mã số sinh viên',
        placeholder='Nhập MSSV...',
        required=True
    )
    password = discord.ui.TextInput(
        label='Mật khẩu',
        style=discord.TextStyle.short,
        placeholder='Nhập mật khẩu...',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):

        dkhp_state = get_app_state(interaction.user.id)
        await interaction.response.send_message("⏳ Đang tiến hành đăng nhập vào portal...", ephemeral=True)
        def do_login():
            return dkhp_state.login_with_credentials(self.username.value, self.password.value)
            
        success = await asyncio.to_thread(do_login)
        if success:
            await interaction.followup.send(f"✅ Đăng nhập thành công tài khoản `{self.username.value}`!", ephemeral=True)
        else:
            error = dkhp_state.last_login_error
            await interaction.followup.send(f"❌ Đăng nhập thất bại: {error}", ephemeral=True)

class ShareModal(discord.ui.Modal, title='Chia sẻ Sự kiện DRL'):
    event_id = discord.ui.TextInput(
        label='Mã sự kiện (ID)',
        placeholder='Ví dụ: 12345',
        required=True
    )
    event_title = discord.ui.TextInput(
        label='Tên sự kiện',
        style=discord.TextStyle.short,
        placeholder='Ví dụ: Hiến máu tình nguyện...',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):

        dkhp_state = get_app_state(interaction.user.id)
        await interaction.response.send_message(f"⏳ Đang xử lý sự kiện **{self.event_id.value}**...\nVui lòng chờ khoảng 30-45 giây.", ephemeral=True)
        
        def run_script():
            python_exe = os.path.join(os.getcwd(), "venv", "bin", "python")
            if not os.path.exists(python_exe):
                python_exe = "python"
                
            process = subprocess.Popen(
                [python_exe, "facebook_share.py", self.event_id.value, self.event_title.value],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            screenshot_path = None
            for line in process.stdout:
                if "[STATUS] SUCCESS:" in line:
                    filename = line.split("SUCCESS:")[1].strip()
                    screenshot_path = os.path.join(os.getcwd(), "DRL", filename)
            process.wait()
            return screenshot_path, process.returncode

        try:
            screenshot_path, return_code = await asyncio.to_thread(run_script)
            if screenshot_path and os.path.exists(screenshot_path):
                file = discord.File(screenshot_path, filename=os.path.basename(screenshot_path))
                await interaction.followup.send(content=f"✅ Đã share thành công sự kiện **{self.event_id.value}**!", file=file, ephemeral=True)
            else:
                await interaction.followup.send(content=f"❌ Xong nhưng không tìm thấy ảnh minh chứng.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(content=f"❌ Lỗi: {e}", ephemeral=True)


class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔑 Đăng nhập", style=discord.ButtonStyle.success)
    async def btn_login(self, interaction: discord.Interaction, button: discord.ui.Button):
        dkhp_state = get_app_state(interaction.user.id)
        await interaction.response.send_modal(LoginModal())
        
    @discord.ui.button(label="📅 Chọn đợt ĐK", style=discord.ButtonStyle.secondary)
    async def btn_period(self, interaction: discord.Interaction, button: discord.ui.Button):
        dkhp_state = get_app_state(interaction.user.id)
        if not dkhp_state.config:
            await interaction.response.send_message("❌ Bạn chưa Đăng nhập. Hãy bấm nút [🔑 Đăng nhập] trước!", ephemeral=True)
            return
            
        await interaction.response.send_message("⏳ Đang lấy danh sách các đợt đăng ký...", ephemeral=True)
        
        url = "https://portal.ut.edu.vn/api/v1/dkhp/getDot"
        def fetch():
            try:
                resp = dkhp_state.request_with_retry("GET", url, timeout=5)
                if resp.status_code == 200:
                    return resp.json().get('data') or resp.json().get('body') or []
                return []
            except:
                return []
                
        dots = await asyncio.to_thread(fetch)
        if not dots:
            await interaction.followup.send("❌ Lỗi hoặc không có đợt đăng ký nào được mở.", ephemeral=True)
            return
            
        view = PeriodView(dots)
        await interaction.followup.send("Vui lòng chọn đợt đăng ký mà bạn muốn thao tác ở menu dưới đây:", view=view, ephemeral=True)

    @discord.ui.button(label="📚 Đăng ký Học phần", style=discord.ButtonStyle.primary)
    async def btn_dkhp(self, interaction: discord.Interaction, button: discord.ui.Button):
        dkhp_state = get_app_state(interaction.user.id)
        if not dkhp_state.config:
            await interaction.response.send_message("❌ Bạn chưa Đăng nhập. Hãy bấm nút [🔑 Đăng nhập] trước!", ephemeral=True)
            return
            
        await interaction.response.send_message("⏳ Đang lấy danh sách môn học đợt này...", ephemeral=True)
        
        id_dot = dkhp_state.config.get('id_dot')
        url = "https://portal.ut.edu.vn/api/v1/dkhp/getHocPhanHocMoi"
            
        def fetch():
            try:
                resp = dkhp_state.request_with_retry("GET", url, params={"idDot": id_dot}, timeout=10)
                if resp.status_code == 200:
                    return resp.json().get('data') or resp.json().get('body') or []
                return None
            except:
                return None

        data = await asyncio.to_thread(fetch)
        if data is None:
            await interaction.followup.send("❌ Lỗi mạng. Vui lòng thử lại.", ephemeral=True)
            return
            
        if not data:
            await interaction.followup.send("Không có môn học nào trong đợt này.", ephemeral=True)
            return

        embed = discord.Embed(title="📚 Danh sách Môn học", color=discord.Color.blue())
        for item in data[:25]:
            ten = item.get('tenHocPhan', 'Unknown')
            if item.get('isBatBuoc'):
                ten += " (Bắt buộc)"
            ma = item.get('maHocPhan', 'Unknown')
            tc = item.get('soTinChi', '?')
            embed.add_field(name=ten, value=f"**Mã:** `{ma}` | **Tín chỉ:** {tc}", inline=False)
            
        if len(data) > 25:
            embed.set_footer(text=f"Hiển thị 25/{len(data)} môn. Chọn môn ở menu bên dưới để xem lớp.")
        else:
            embed.set_footer(text="Chọn môn ở menu bên dưới để xem chi tiết lớp.")
            
        view = SubjectView(data)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="📊 Trạng thái", style=discord.ButtonStyle.secondary)
    async def btn_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        dkhp_state = get_app_state(interaction.user.id)
        is_spam = "Đang chạy 🔥" if dkhp_state.is_spamming else "Nghỉ ngơi 💤"
        total = dkhp_state.stats["total_requests"]
        succ = dkhp_state.stats["success_count"]
        
        embed = discord.Embed(title="📊 Trạng Thái Hệ Thống", color=discord.Color.purple())
        embed.add_field(name="Tiến trình Spam", value=is_spam, inline=False)
        embed.add_field(name="Tổng request đã bắn", value=str(total), inline=True)
        embed.add_field(name="Thành công", value=str(succ), inline=True)
        
        if dkhp_state.logs:
            latest_log = "\n".join(dkhp_state.logs[-5:])
            embed.add_field(name="Log gần nhất", value=f"```\n{latest_log}\n```", inline=False)
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="⏹ Dừng Spam", style=discord.ButtonStyle.danger)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        dkhp_state = get_app_state(interaction.user.id)
        if not dkhp_state.is_spamming:
            await interaction.response.send_message("Bot đang không chạy spam nào.", ephemeral=True)
            return
        dkhp_state.is_spamming = False
        await interaction.response.send_message("⏹ Đã gửi lệnh dừng Spam!", ephemeral=True)

    @discord.ui.button(label="🔗 Share DRL", style=discord.ButtonStyle.secondary)
    async def btn_share(self, interaction: discord.Interaction, button: discord.ui.Button):
        dkhp_state = get_app_state(interaction.user.id)
        await interaction.response.send_modal(ShareModal())

    @discord.ui.button(label="🌐 Mở Web", style=discord.ButtonStyle.success)
    async def btn_open_web(self, interaction: discord.Interaction, button: discord.ui.Button):
        dkhp_state = get_app_state(interaction.user.id)
        await interaction.response.send_message("⏳ Đang mở trang điều khiển trên trình duyệt của máy chủ...", ephemeral=True)
        try:
            import urllib.request
            import webbrowser
            import sys
            try:
                urllib.request.urlopen("http://localhost:5001", timeout=1)
                webbrowser.open("http://localhost:5001")
            except Exception:
                python_exe = os.path.join(os.getcwd(), "venv", "bin", "python")
                if not os.path.exists(python_exe):
                    python_exe = sys.executable
                subprocess.Popen([python_exe, "server.py"], cwd=os.getcwd())
            await interaction.edit_original_response(content="✅ Đã mở trang điều khiển trên trình duyệt thành công!")
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Không thể mở web: {e}")

# ==================== BOT SETUP ====================

class SmartEnrollBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Đã đồng bộ Slash Commands cho {self.user}.")

bot = SmartEnrollBot()

async def is_admin(interaction: discord.Interaction) -> bool:
    if ADMIN_ID is None:
        return True 
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng Bot cá nhân này!", ephemeral=True)
        return False
    return True

bot.tree.interaction_check = is_admin

@bot.event
async def on_ready():
    print(f'✅ Đăng nhập thành công với tài khoản: {bot.user}')
    if ADMIN_ID:
        print(f'🔒 Chế độ PRIVATE BOT: Chỉ phục vụ User ID {ADMIN_ID}')
    else:
        print('⚠️ Chế độ PUBLIC BOT: Bất kỳ ai cũng có thể dùng. Vui lòng set ADMIN_ID trong .env!')

@bot.tree.command(name="ping", description="Kiểm tra trạng thái bot")
async def ping(interaction: discord.Interaction):
    dkhp_state = get_app_state(interaction.user.id)
    await interaction.response.send_message("Bot đang hoạt động ổn định! 🚀", ephemeral=True)

@bot.tree.command(name="start", description="Mở Bảng điều khiển trung tâm (Dashboard)")
async def start(interaction: discord.Interaction):
    dkhp_state = get_app_state(interaction.user.id)
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title="☕ SmartEnroll Dashboard", 
        description="Chào mừng bạn đến với bảng điều khiển trung tâm.\nVui lòng sử dụng các nút bấm bên dưới để thao tác.", 
        color=discord.Color.gold()
    )
    
    logged_in = "Đã đăng nhập ✅" if dkhp_state.config else "Chưa đăng nhập ❌"
    spamming = "Đang chạy 🔥" if dkhp_state.is_spamming else "Nghỉ ngơi 💤"
    
    embed.add_field(name="Tài khoản", value=logged_in, inline=True)
    embed.add_field(name="Tiến trình", value=spamming, inline=True)
    
    if dkhp_state.config:
        username = dkhp_state.config.get('username', 'Không rõ')
        id_dot = dkhp_state.config.get('id_dot')
        
        def get_term_name(dot_id_str):
            try:
                dot_id = int(dot_id_str)
                if dot_id >= 71:
                    diff = dot_id - 71
                    year_offset = diff // 3
                    term_offset = diff % 3
                    start_year = 24 + year_offset
                    end_year = 25 + year_offset
                    term_str = "HK1" if term_offset == 0 else ("HK2" if term_offset == 1 else "HK Hè")
                    return f"{term_str} {start_year}-{end_year}"
            except:
                pass
            return f"Đợt {dot_id_str}"
            
        term_name = get_term_name(id_dot) if id_dot else "Chưa chọn đợt"
        
        embed.add_field(name="Họ tên Sinh viên", value=f"MSSV: `{username}`", inline=False)
        embed.add_field(name="Học kỳ đăng ký hiện tại", value=f"**{term_name}**", inline=False)
        
        def fetch_registered():
            url = "https://portal.ut.edu.vn/api/v1/dkhp/getLHPDaDangKy"
            try:
                resp = dkhp_state.request_with_retry("GET", url, params={"idDot": id_dot}, timeout=5)
                if resp.status_code == 200:
                    return resp.json().get('data') or resp.json().get('body') or []
            except:
                pass
            return []
            
        reg_courses = await asyncio.to_thread(fetch_registered)
        if reg_courses:
            course_list = ""
            for c in reg_courses:
                ten = c.get('tenHocPhan') or c.get('tenMonHoc') or c.get('tenLopHocPhan') or ""
                ma = c.get('maLopHocPhan') or c.get('maHocPhan') or ""
                tc = c.get('soTinChi', '?')
                course_list += f"- `{ma}`: {ten} ({tc} TC)\n"
            if len(course_list) > 1024:
                course_list = course_list[:1020] + "..."
            embed.add_field(name="Môn học đã đăng ký", value=course_list, inline=False)
        else:
            embed.add_field(name="Môn học đã đăng ký", value="Chưa đăng ký môn nào.", inline=False)

    await interaction.followup.send(embed=embed, view=DashboardView(), ephemeral=True)

@bot.tree.command(name="export", description="Trích xuất dữ liệu học tập ra file JSON")
async def export_json(interaction: discord.Interaction):
    dkhp_state = get_app_state(interaction.user.id)
    if not dkhp_state.config:
        await interaction.response.send_message("❌ Bạn chưa Đăng nhập. Vui lòng dùng /start và đăng nhập trước!", ephemeral=True)
        return
        
    await interaction.response.send_message("⏳ Đang thu thập dữ liệu (điểm số, các môn đã đăng ký, chưa đăng ký...). Quá trình này có thể mất vài giây...", ephemeral=True)
    
    try:
        from export_json import build_export_data
        data = await build_export_data(dkhp_state)
        
        import io
        import json
        file_bytes = json.dumps(data, ensure_ascii=False, indent=4).encode('utf-8')
        file_obj = io.BytesIO(file_bytes)
        
        await interaction.followup.send("✅ Trích xuất dữ liệu thành công! Đây là file JSON của bạn:", file=discord.File(fp=file_obj, filename="DuLieuHocTap.json"), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Có lỗi xảy ra trong quá trình trích xuất: {e}", ephemeral=True)

if __name__ == "__main__":
    if not TOKEN or TOKEN == "your_token_here":
        print("❌ LỖI: Vui lòng thiết lập biến môi trường DISCORD_TOKEN trong file .env")
    else:
        bot.run(TOKEN)
