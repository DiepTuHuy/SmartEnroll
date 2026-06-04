import subprocess
import sys
import os
import time

def run():
    print("🚀 Khởi động SmartEnroll UTH...")
    
    # 1. Khởi động Flask Server (server.py)
    print("📡 Đang mở API Server (server.py)...")
    backend_proc = subprocess.Popen([sys.executable, "server.py"])
    
    # Đợi 1 giây để backend khởi động
    time.sleep(1)
    
    # 2. Khởi động React Frontend (Vite)
    print("🌍 Đang mở React Frontend (Vite)...")
    frontend_dir = os.path.join(os.getcwd(), "frontend")
    
    import platform
    is_windows = platform.system() == "Windows"
    
    # Kiểm tra node_modules
    if not os.path.exists(os.path.join(frontend_dir, "node_modules")):
        print("📦 Chưa tìm thấy node_modules, đang cài đặt thư viện frontend...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, shell=is_windows)
        
    frontend_proc = subprocess.Popen(["npm", "run", "dev"], cwd=frontend_dir, shell=is_windows)
    
    try:
        # Giữ script chạy liên tục và kiểm tra trạng thái
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("❌ API Server (backend) đã dừng đột ngột.")
                break
            if frontend_proc.poll() is not None:
                print("❌ React dev server (frontend) đã dừng đột ngột.")
                break
    except KeyboardInterrupt:
        print("\n⏹ Đang dọn dẹp và dừng ứng dụng...")
    finally:
        # Tắt các tiến trình con
        try:
            backend_proc.terminate()
            backend_proc.wait(timeout=2)
        except Exception:
            try:
                backend_proc.kill()
            except Exception:
                pass
            
        try:
            frontend_proc.terminate()
            frontend_proc.wait(timeout=2)
        except Exception:
            try:
                frontend_proc.kill()
            except Exception:
                pass
            
        print("👋 Đã đóng toàn bộ ứng dụng.")

if __name__ == "__main__":
    run()
