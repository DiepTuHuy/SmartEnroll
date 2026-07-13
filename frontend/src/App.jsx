import React, { useState, useEffect, useRef } from 'react';
import { 
  Settings, Play, Square, RefreshCw, Search, Check, AlertCircle, 
  Terminal, ShieldAlert, Cpu, Layers, HelpCircle, CheckSquare, 
  Trash2, Eye, EyeOff, CheckCircle2, XCircle, Info, ChevronDown, ShieldCheck
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function App() {
  // App States
  const [config, setConfig] = useState(null);
  const [configExists, setConfigExists] = useState(false);
  const [isTokenExpired, setIsTokenExpired] = useState(false);
  const [showManual, setShowManual] = useState(false);
  
  // Semester periods and registration types
  const [dots, setDots] = useState([]);
  const [selectedDot, setSelectedDot] = useState('');
  const [regType, setRegType] = useState('new'); // new, repeat, improve

  // Token countdown timer states
  const [timeLeft, setTimeLeft] = useState(900); // 15 minutes default
  const [timerActive, setTimerActive] = useState(false);

  // Registered classes states
  const [registeredClasses, setRegisteredClasses] = useState([]);
  const [registeredLoading, setRegisteredLoading] = useState(false);

  // Manual Config inputs
  const [manToken, setManToken] = useState('');
  const [manCookie, setManCookie] = useState('');
  const [manIdDot, setManIdDot] = useState('');
  const [manUserAgent, setManUserAgent] = useState('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
  
  // Auto Config Status
  const [autoStatus, setAutoStatus] = useState('idle'); // idle, running, success, failed
  const [isAutoRunning, setIsAutoRunning] = useState(false);

  // UTH Credentials login states
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');

  // Course & Class scanning states
  const [courses, setCourses] = useState([]);
  const [coursesLoading, setCoursesLoading] = useState(false);
  const [selectedCourse, setSelectedCourse] = useState('');
  const [courseSearch, setCourseSearch] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [filterThu, setFilterThu] = useState('Tất cả');
  const [filterCa, setFilterCa] = useState('Tất cả');
  
  const [classes, setClasses] = useState([]);
  const [isScanning, setIsScanning] = useState(false);
  const [checkedClasses, setCheckedClasses] = useState([]); // Array of checked class IDs
  const [hideConflicting, setHideConflicting] = useState(false); // Hide conflicting classes toggle
  const [customDialog, setCustomDialog] = useState(null); // Custom alert/confirm modal dialog
  const [showLoginOverlay, setShowLoginOverlay] = useState(true); // Fullscreen login modal on app entry
  const [showPassword, setShowPassword] = useState(false); // Toggle password field visibility

  // Spam states
  const [isSpamming, setIsSpamming] = useState(false);
  const [spamMode, setSpamMode] = useState('normal'); // normal, turbo
  const [spamStats, setSpamStats] = useState({ total_requests: 0, success_count: 0, error_count: 0 });
  const [logs, setLogs] = useState([]);
  
  // UI views
  const [showToken, setShowToken] = useState(false);
  const [showCookie, setShowCookie] = useState(false);
  const terminalEndRef = useRef(null);

  // Locally override standard browser alert and confirm with modern custom modal promises
  const alert = (msg, status = 'success') => {
    let detectedStatus = status;
    const lowerMsg = msg.toLowerCase();
    if (lowerMsg.includes('lỗi') || lowerMsg.includes('thất bại') || lowerMsg.includes('hết hạn') || lowerMsg.includes('chưa')) {
      detectedStatus = 'error';
    }
    return new Promise((resolve) => {
      setCustomDialog({ type: 'alert', status: detectedStatus, message: msg, resolve });
    });
  };

  const confirm = (msg) => {
    return new Promise((resolve) => {
      setCustomDialog({ type: 'confirm', message: msg, resolve });
    });
  };

  // Reset the 15-minute token countdown timer
  const resetSessionTimer = () => {
    setTimeLeft(900); // 15 minutes
    setIsTokenExpired(false);
  };

  // Format seconds into MM:SS
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Keep countdown timer active depending on login status
  useEffect(() => {
    if (!configExists || isTokenExpired) {
      setTimerActive(false);
      if (isTokenExpired) {
        setTimeLeft(0);
      }
      return;
    }
    setTimerActive(true);
  }, [configExists, isTokenExpired]);

  // Countdown loop
  useEffect(() => {
    let interval;
    if (timerActive && timeLeft > 0) {
      interval = setInterval(() => {
        if (isSpamming) {
          // Keep session alive while actively spamming
          setTimeLeft(900);
        } else {
          setTimeLeft(prev => {
            if (prev <= 1) {
              setIsTokenExpired(true);
              setTimerActive(false);
              return 0;
            }
            return prev - 1;
          });
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [timerActive, timeLeft, isSpamming]);

  // Fetch initial config
  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      if (data.exists) {
        setConfig(data.config);
        setConfigExists(true);
        setIsTokenExpired(false);
        resetSessionTimer();
        setManToken(data.config.token || '');
        setManCookie(data.config.cookie || '');
        setManIdDot(data.config.id_dot || '');
        setManUserAgent(data.config.user_agent || '');
        setUsername(data.config.username || '');
        setPassword(data.config.password || '');
        if (data.config.id_dot) {
          setSelectedDot(data.config.id_dot);
        }
      } else {
        setConfig(null);
        setConfigExists(false);
        setIsTokenExpired(false);
        setUsername('');
        setPassword('');
      }
    } catch (err) {
      console.error("Lỗi lấy cấu hình:", err);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  // Periodic config sync to keep session timer fresh when background auto-refresher updates token
  useEffect(() => {
    let interval;
    if (configExists && !isTokenExpired) {
      interval = setInterval(() => {
        fetchConfig();
      }, 30000); // Poll every 30 seconds
    }
    return () => clearInterval(interval);
  }, [configExists, isTokenExpired]);

  // Fetch available registration periods
  const fetchDots = async (type) => {
    if (!configExists) return;
    const isCond = type === 'cond_new' || type === 'cond_repeat';
    try {
      const res = await fetch(`/api/dots?type=${isCond ? 'conditional' : 'normal'}`);
      const data = await res.json();
      if (data.success) {
        const loadedDots = data.data || [];
        setDots(loadedDots);
        if (loadedDots.length > 0) {
          const hasCurrent = loadedDots.some(d => (d.id || d.idDot) === selectedDot);
          if (!hasCurrent) {
            setSelectedDot(loadedDots[0].id || loadedDots[0].idDot);
          }
        }
      } else {
        if (res.status === 401 || data.expired || (data.message && data.message.includes("Token hết hạn"))) {
          setIsTokenExpired(true);
          setTimeLeft(0);
          setDots([]);
        }
      }
    } catch (err) {
      console.error("Lỗi lấy danh sách đợt:", err);
    }
  };

  useEffect(() => {
    if (configExists) {
      fetchDots(regType);
    }
  }, [configExists, regType]);

  // Fetch courses list once config is loaded
  const fetchCourses = async () => {
    if (!configExists) return;
    const dot = selectedDot || config?.id_dot;
    if (!dot) return;

    setCoursesLoading(true);
    try {
      const res = await fetch(`/api/courses?type=${regType}&idDot=${dot}`);
      const data = await res.json();
      if (data.success) {
        setCourses(data.data || []);
        setIsTokenExpired(false);
        resetSessionTimer();
      } else {
        if (res.status === 401 || data.expired || (data.message && data.message.includes("Token hết hạn"))) {
          setIsTokenExpired(true);
          setCourses([]);
        } else {
          await alert("Lỗi tải môn học: " + data.message);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setCoursesLoading(false);
    }
  };

  // Fetch registered courses from UTH
  const fetchRegisteredClasses = async () => {
    if (!configExists) return;
    const dot = selectedDot || config?.id_dot;
    if (!dot) return;

    setRegisteredLoading(true);
    try {
      const res = await fetch(`/api/registered?idDot=${dot}`);
      const data = await res.json();
      if (data.success) {
        setRegisteredClasses(data.data || []);
      } else {
        if (res.status === 401 || data.expired || (data.message && data.message.includes("Token hết hạn"))) {
          setIsTokenExpired(true);
          setRegisteredClasses([]);
        } else {
          console.error("Lỗi tải lớp đã đăng ký:", data.message);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setRegisteredLoading(false);
    }
  };

  // Deregister a class section
  const handleDeregisterClass = async (idDangKy, className) => {
    const confirmDeregister = await confirm(`Bạn có chắc chắn muốn hủy đăng ký lớp "${className}" không?`);
    if (!confirmDeregister) return;

    try {
      const res = await fetch('/api/deregister', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idDangKy: idDangKy })
      });
      const data = await res.json();
      if (data.success) {
        await alert("Hủy đăng ký thành công!");
        resetSessionTimer();
        fetchRegisteredClasses(); // Reload list
      } else {
        if (res.status === 401 || data.expired || (data.message && data.message.includes("Token hết hạn"))) {
          setIsTokenExpired(true);
          setTimeLeft(0);
          await alert("Lỗi hủy đăng ký: Phiên đăng nhập (Token) của bạn đã hết hạn. Vui lòng bấm lấy lại Token!");
        } else {
          await alert("Lỗi hủy đăng ký: " + data.message);
        }
      }
    } catch (err) {
      await alert("Lỗi mạng khi hủy đăng ký: " + err.message);
    }
  };

  useEffect(() => {
    if (configExists) {
      fetchCourses();
      fetchRegisteredClasses();
    }
  }, [configExists, config, regType, selectedDot]);

  // Poll Auto config status
  useEffect(() => {
    let interval;
    if (isAutoRunning) {
      interval = setInterval(async () => {
        try {
          const res = await fetch('/api/config/auto/status');
          const data = await res.json();
          setAutoStatus(data.status);
          setIsAutoRunning(data.running);
          if (!data.running) {
            if (data.status === 'success') {
              fetchConfig();
            }
          }
        } catch (err) {
          console.error(err);
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isAutoRunning]);

  // Poll Spam status
  useEffect(() => {
    let interval;
    if (isSpamming) {
      interval = setInterval(async () => {
        try {
          const res = await fetch('/api/spam/status');
          const data = await res.json();
          setIsSpamming(data.is_spamming);
          setSpamStats(data.stats);
          setLogs(data.logs || []);
        } catch (err) {
          console.error(err);
        }
      }, 1000);
    } else {
      interval = setInterval(async () => {
        try {
          const res = await fetch('/api/spam/status');
          const data = await res.json();
          setIsSpamming(data.is_spamming);
          setSpamStats(data.stats);
          if (data.is_spamming) {
            setLogs(data.logs || []);
          }
        } catch (err) {
          console.error(err);
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [isSpamming]);

  // Auto scroll terminal
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // Trigger Automatic config capture
  const handleStartAutoConfig = async () => {
    try {
      setAutoStatus('running');
      setIsAutoRunning(true);
      const res = await fetch('/api/config/auto', { method: 'POST' });
      const data = await res.json();
      if (!data.success) {
        await alert(data.message);
        setIsAutoRunning(false);
        setAutoStatus('failed');
      }
    } catch (err) {
      console.error(err);
      setIsAutoRunning(false);
      setAutoStatus('failed');
    }
  };

  // Submit manual config
  const handleSaveManualConfig = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/config/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: manToken,
          cookie: manCookie,
          id_dot: manIdDot,
          user_agent: manUserAgent,
          username: username,
          password: password
        })
      });
      const data = await res.json();
      if (data.success) {
        setShowManual(false);
        fetchConfig();
        resetSessionTimer();
        await alert("Đã lưu cấu hình!");
      } else {
        await alert("Lỗi: " + data.message);
      }
    } catch (err) {
      await alert("Lỗi lưu cấu hình: " + err.message);
    }
  };

  // Login handler
  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setLoginError('Vui lòng điền đầy đủ tài khoản và mật khẩu!');
      return;
    }
    setLoginLoading(true);
    setLoginError('');
    try {
      const res = await fetch('/api/config/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (res.status === 200 && data.success) {
        setConfig(data.config);
        setConfigExists(true);
        setIsTokenExpired(false);
        resetSessionTimer();
        setManToken(data.config.token || '');
        setManCookie(data.config.cookie || '');
        setManIdDot(data.config.id_dot || '');
        setManUserAgent(data.config.user_agent || '');
        if (data.config.id_dot) {
          setSelectedDot(data.config.id_dot);
        }
        setShowLoginOverlay(false);
        await alert('Đăng nhập cổng UTH thành công!');
      } else {
        setLoginError(data.message || 'Tài khoản hoặc mật khẩu không chính xác!');
      }
    } catch (err) {
      console.error(err);
      setLoginError('Không thể kết nối đến server SmartEnroll!');
    } finally {
      setLoginLoading(false);
    }
  };

  // Logout handler
  const handleLogout = async () => {
    if (!(await confirm('Bạn có chắc chắn muốn đăng xuất và xóa tài khoản đã lưu?'))) return;
    try {
      const res = await fetch('/api/config/logout', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setConfig(null);
        setConfigExists(false);
        setUsername('');
        setPassword('');
        setManToken('');
        setManCookie('');
        setManIdDot('');
        setShowLoginOverlay(true);
        await alert('Đăng xuất thành công!');
      } else {
        await alert(data.message || 'Lỗi đăng xuất!');
      }
    } catch (err) {
      console.error(err);
      await alert('Lỗi kết nối server!');
    }
  };

  // Scan classes
  const handleScanClasses = async () => {
    if (!selectedCourse) {
      await alert("Vui lòng chọn môn học để quét!");
      return;
    }
    setIsScanning(true);
    setClasses([]);
    try {
      const dot = selectedDot || config?.id_dot;
      const res = await fetch(`/api/classes?maHocPhan=${selectedCourse}&idDot=${dot}&thu=${encodeURIComponent(filterThu)}&ca=${encodeURIComponent(filterCa)}&isConditional=${regType === 'cond_new' || regType === 'cond_repeat'}`);
      const data = await res.json();
      if (data.success) {
        setClasses(data.data || []);
        resetSessionTimer();
        if (data.data.length === 0) {
          await alert("Không tìm thấy lớp nào phù hợp bộ lọc.");
        }
      } else {
        if (res.status === 401 || data.expired || (data.message && data.message.includes("Token hết hạn"))) {
          setIsTokenExpired(true);
          setTimeLeft(0);
          await alert("Lỗi quét lớp: Phiên đăng nhập (Token) của bạn đã hết hạn hoặc bị hủy trên máy chủ trường. Vui lòng bấm lấy lại Token!");
        } else {
          await alert("Lỗi quét lớp: " + data.message);
        }
      }
    } catch (err) {
      await alert("Lỗi mạng: " + err.message);
    } finally {
      setIsScanning(false);
    }
  };

  // Class selection logic (Single choice per subject)
  const handleToggleClass = (cls) => {
    const isChecked = checkedClasses.some(c => c.id === cls.id);
    if (isChecked) {
      setCheckedClasses(checkedClasses.filter(c => c.id !== cls.id));
    } else {
      const classWithFlags = { ...cls, is_conditional: regType === 'cond_new' || regType === 'cond_repeat' };
      const filtered = checkedClasses.filter(c => c.tenMonHoc !== cls.tenMonHoc);
      setCheckedClasses([...filtered, classWithFlags]);
    }
  };

  // Start Spamming
  const handleStartSpam = async () => {
    if (checkedClasses.length === 0) {
      await alert("Vui lòng tích chọn lớp học phần muốn đăng ký!");
      return;
    }
    try {
      const res = await fetch('/api/spam/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: spamMode,
          targets: checkedClasses.map(c => ({ 
            id: c.id, 
            name: c.tenMonHoc,
            is_conditional: !!c.is_conditional
          }))
        })
      });
      const data = await res.json();
      if (data.success) {
        setIsSpamming(true);
      } else {
        await alert("Lỗi: " + data.message);
      }
    } catch (err) {
      await alert("Lỗi khởi động spam: " + err.message);
    }
  };

  // Stop Spamming
  const handleStopSpam = async () => {
    try {
      const res = await fetch('/api/spam/stop', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setIsSpamming(false);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  // Clear selections
  const handleClearSelection = () => {
    setCheckedClasses([]);
  };

  // Filter courses by search input
  const filteredCourses = courses.filter(c => {
    const label = `[${c.maHocPhan}] ${c.tenHocPhan || c.tenMonHoc || ''}`.toLowerCase();
    return label.includes(courseSearch.toLowerCase());
  });

  return (
    <div className="app-container">
      {/* HEADER SECTION */}
      <motion.header 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="app-header"
      >
        <div className="brand-wrapper">
          <div className="brand-icon">
            <Cpu className="w-8 h-8 text-purple-400" />
          </div>
          <div>
            <h1 className="app-title">SmartEnroll UTH</h1>
            <p className="app-subtitle">Hệ thống hỗ trợ đăng ký học phần tự động thông minh</p>
          </div>
        </div>
        
        <div className="header-badges">
          <div className={`badge ${isTokenExpired ? 'badge-expired' : configExists ? 'badge-ready' : 'badge-pending'}`}>
            <span className="badge-dot pulse-indicator"></span>
            {isTokenExpired ? 'Cấu hình: HẾT HẠN' : configExists ? 'Cấu hình: ĐÃ SẴN SÀNG' : 'Cấu hình: CHƯA CÓ'}
          </div>
          
          {isSpamming && (
            <div className="badge badge-active">
              <span className="badge-dot pulse-indicator"></span>
              ĐANG SPAM ĐĂNG KÝ
            </div>
          )}
        </div>
      </motion.header>

      {/* MAIN CONTAINER */}
      <div className="main-grid">
        
        {/* LEFT COLUMN: CONFIG & SCANNER */}
        <div className="col-flex">
          
          {/* CONFIGURATION CARD */}
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="card"
          >
            <div className="card-header">
              <h2 className="card-title purple">
                <Settings className="w-5 h-5" />
                Cấu hình Đăng nhập & Đợt
              </h2>
              <button 
                onClick={() => setShowManual(!showManual)}
                className="btn-text"
              >
                {showManual ? 'Hiện trạng thái' : 'Cập nhật thủ công'}
              </button>
            </div>

            <AnimatePresence mode="wait">
              {!showManual ? (
                <motion.div 
                  key="status"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
                >
                  {configExists ? (
                    <div className="config-display">
                      {config && (
                        <div className="config-item" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span className="config-key">Sinh viên đăng nhập:</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontWeight: '700', color: '#10b981' }}>
                              {config.username || 'Quét từ Chrome'}
                            </span>
                            <button 
                              onClick={handleLogout} 
                              className="btn btn-outline" 
                              style={{ padding: '2px 8px', fontSize: '0.8rem', minHeight: 'auto', border: '1px solid #ef4444', color: '#ef4444' }}
                            >
                              Đăng xuất
                            </button>
                          </div>
                        </div>
                      )}
                      <div className="config-item">
                        <span className="config-key">Token đăng nhập:</span>
                        <div className="config-value">
                          <span>{showToken ? config.token : '••••••••••••••••••••••••'}</span>
                          <button onClick={() => setShowToken(!showToken)} className="eye-button">
                            {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                      <div className="config-item">
                        <span className="config-key">Cookie Portal UTH:</span>
                        <div className="config-value">
                          <span>
                            {showCookie ? config.cookie : '••••••••••••••••••••••••'}
                          </span>
                          <button onClick={() => setShowCookie(!showCookie)} className="eye-button">
                            {showCookie ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                      
                      <div className="config-item" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '12px' }}>
                        <span className="config-key">Chọn Đợt học:</span>
                        <select 
                          value={selectedDot} 
                          onChange={(e) => setSelectedDot(e.target.value)}
                          className="select-input"
                          style={{ maxWidth: '220px', background: 'rgba(16, 12, 34, 0.85)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' }}
                        >
                          {dots.length > 0 ? (
                            dots.map(d => (
                              <option key={d.id || d.idDot} value={d.id || d.idDot}>
                                {d.tenHocKy || d.tenDot || d.id || d.idDot}
                              </option>
                            ))
                          ) : (
                            <option value={config.id_dot}>{config.id_dot}</option>
                          )}
                        </select>
                      </div>

                      <div className="config-item">
                        <span className="config-key">Loại Đăng ký:</span>
                        <select 
                          value={regType} 
                          onChange={(e) => setRegType(e.target.value)}
                          className="select-input"
                          style={{ maxWidth: '220px', background: 'rgba(16, 12, 34, 0.85)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' }}
                        >
                          <option value="new">Học mới (Đăng ký học phần)</option>
                          <option value="repeat">Học lại</option>
                          <option value="improve">Học cải thiện</option>
                          <option value="cond_new">Môn điều kiện (Học mới)</option>
                          <option value="cond_repeat">Môn điều kiện (Học lại)</option>
                        </select>
                      </div>

                      <div className="config-item" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '12px' }}>
                        <span className="config-key">Thời hạn Token:</span>
                        <span 
                          style={{ 
                            fontWeight: '700', 
                            fontSize: '0.95rem', 
                            fontFamily: 'var(--font-mono)', 
                            color: timeLeft < 180 ? '#fb7185' : '#38bdf8',
                            textShadow: timeLeft < 180 ? '0 0 8px rgba(244, 63, 94, 0.5)' : '0 0 8px rgba(14, 165, 233, 0.5)'
                          }}
                        >
                          {timeLeft > 0 ? formatTime(timeLeft) : 'HẾT HẠN (00:00)'}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      <div className="alert alert-info" style={{ margin: 0 }}>
                        <Info className="w-5 h-5 shrink-0 text-sky-400" />
                        <div style={{ fontSize: '0.85rem', lineHeight: '1.4' }}>
                          Đăng nhập bằng tài khoản cổng sinh viên UTH để SmartEnroll tự động nạp cấu hình và duy trì phiên hoạt động liên tục.
                        </div>
                      </div>
                      
                      <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '12px', background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="input-label" style={{ fontSize: '0.8rem', marginBottom: '4px' }}>Mã số sinh viên (MSSV)</label>
                          <input 
                            type="text" 
                            value={username} 
                            onChange={(e) => setUsername(e.target.value)} 
                            placeholder="Nhập MSSV..." 
                            className="text-input" 
                            style={{ padding: '8px 12px' }}
                            required
                          />
                        </div>
                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="input-label" style={{ fontSize: '0.8rem', marginBottom: '4px' }}>Mật khẩu cổng UTH</label>
                          <div style={{ position: 'relative' }}>
                            <input 
                              type={showPassword ? "text" : "password"} 
                              value={password} 
                              onChange={(e) => setPassword(e.target.value)} 
                              placeholder="Nhập mật khẩu..." 
                              className="text-input" 
                              style={{ padding: '8px 40px 8px 12px', width: '100%' }}
                              required
                            />
                            <button
                              type="button"
                              onClick={() => setShowPassword(!showPassword)}
                              style={{
                                position: 'absolute',
                                right: '12px',
                                top: '50%',
                                transform: 'translateY(-50%)',
                                background: 'none',
                                border: 'none',
                                padding: 0,
                                color: 'rgba(255, 255, 255, 0.4)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center'
                              }}
                            >
                              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                        </div>
                        {loginError && (
                          <div style={{ color: '#fb7185', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <AlertCircle className="w-4 h-4 shrink-0" />
                            {loginError}
                          </div>
                        )}
                        <button 
                          type="submit" 
                          disabled={loginLoading} 
                          className="btn btn-primary" 
                          style={{ width: '100%', marginTop: '4px', display: 'flex', justifyContent: 'center' }}
                        >
                          {loginLoading ? 'ĐANG ĐĂNG NHẬP...' : 'ĐĂNG NHẬP CỔNG TRƯỜNG'}
                        </button>
                      </form>
                    </div>
                  )}

                  {/* AUTO CONFIG LOGIC */}
                  <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '16px', marginTop: '4px' }}>
                    {!configExists && (
                      <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)', marginBottom: '8px', textAlign: 'center', letterSpacing: '0.5px' }}>
                        — HOẶC DÙNG DỰ PHÒNG CHROME —
                      </div>
                    )}
                    <button
                      onClick={handleStartAutoConfig}
                      disabled={isAutoRunning}
                      className={configExists ? "btn btn-outline" : "btn btn-outline"}
                      style={{ width: '100%', display: 'flex', justifyContent: 'center', gap: '8px' }}
                    >
                      <RefreshCw className={`w-4 h-4 ${isAutoRunning ? 'spin-loading' : ''}`} />
                      {isAutoRunning ? 'ĐANG ĐỌC TỰ ĐỘNG CHROME...' : 'QUÉT TOKEN TỪ CHROME'}
                    </button>

                    {/* Step guidance during auto retrieval */}
                    {isAutoRunning && (
                      <motion.div 
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        className="alert alert-info"
                        style={{ marginTop: '14px', flexDirection: 'column' }}
                      >
                        <div style={{ fontWeight: '700', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}>
                          <Info className="w-4 h-4 text-yellow-400 shrink-0" />
                          Hướng dẫn bắt Token và ID Đợt:
                        </div>
                        <ol className="alert-steps" style={{ fontSize: '0.8rem', marginTop: '6px' }}>
                          <li>Trình duyệt Chrome ẩn danh sẽ tự mở ra.</li>
                          <li>Bạn vui lòng <span className="highlight">ĐĂNG NHẬP</span> tay vào portal.</li>
                          <li>Hệ thống tự động quét Token, Đợt học và đóng trình duyệt.</li>
                        </ol>
                      </motion.div>
                    )}

                    {/* Feedback states */}
                    {autoStatus === 'success' && !isAutoRunning && (
                      <div className="alert alert-success" style={{ marginTop: '12px' }}>
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        Nạp Token từ Chrome thành công!
                      </div>
                    )}
                    {autoStatus === 'failed' && !isAutoRunning && (
                      <div className="alert alert-danger" style={{ marginTop: '12px' }}>
                        <XCircle className="w-4 h-4 text-rose-400" />
                        Không tìm thấy cấu hình. Hãy thử lại.
                      </div>
                    )}
                  </div>
                </motion.div>
              ) : (
                <motion.form 
                  key="manual"
                  onSubmit={handleSaveManualConfig}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
                >
                  <div className="form-group">
                    <label className="input-label">Token Bearer</label>
                    <input 
                      type="text" 
                      value={manToken} 
                      onChange={(e) => setManToken(e.target.value)} 
                      placeholder="Không cần chữ Bearer..."
                      className="text-input"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="input-label">Cookie</label>
                    <input 
                      type="text" 
                      value={manCookie} 
                      onChange={(e) => setManCookie(e.target.value)} 
                      placeholder="Nhập chuỗi Cookie..."
                      className="text-input"
                      required
                    />
                  </div>
                  <div className="grid-2">
                    <div className="form-group">
                      <label className="input-label">Mã số sinh viên (MSSV)</label>
                      <input 
                        type="text" 
                        value={username} 
                        onChange={(e) => setUsername(e.target.value)} 
                        placeholder="Không bắt buộc..." 
                        className="text-input" 
                      />
                    </div>
                    <div className="form-group">
                      <label className="input-label">Mật khẩu Portal UTH</label>
                      <input 
                        type="password" 
                        value={password} 
                        onChange={(e) => setPassword(e.target.value)} 
                        placeholder="Không bắt buộc..." 
                        className="text-input" 
                      />
                    </div>
                  </div>
                  <div className="grid-3">
                    <div className="form-group">
                      <label className="input-label">ID Đợt học</label>
                      <input 
                        type="text" 
                        value={manIdDot} 
                        onChange={(e) => setManIdDot(e.target.value)} 
                        placeholder="76..." 
                        className="text-input" 
                        required
                      />
                    </div>
                    <div className="form-group" style={{ gridColumn: 'span 2' }}>
                      <label className="input-label">User Agent</label>
                      <input 
                        type="text" 
                        value={manUserAgent} 
                        onChange={(e) => setManUserAgent(e.target.value)} 
                        placeholder="Mozilla/5.0..." 
                        className="text-input" 
                        required
                      />
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                    <button
                      type="submit"
                      className="btn btn-secondary"
                    >
                      LƯU THỦ CÔNG
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowManual(false)}
                      className="btn btn-outline"
                    >
                      HỦY
                    </button>
                  </div>
                </motion.form>
              )}
            </AnimatePresence>
          </motion.div>

          {/* CLASS SCANNER CARD */}
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="card"
            style={{ zIndex: dropdownOpen ? 10 : 1, position: 'relative' }}
          >
            <h2 className="card-title cyan" style={{ marginBottom: '20px' }}>
              <Search className="w-5 h-5" />
              1. Tìm kiếm lớp học phần
            </h2>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Course Selection Dropdown with Search */}
              <div className="form-group" style={{ position: 'relative', marginBottom: '0' }}>
                <label className="input-label">Môn học cần đăng ký</label>
                <div 
                  className="custom-select-trigger"
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                >
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '90%' }}>
                    {selectedCourse 
                      ? courses.find(c => c.maHocPhan === selectedCourse)
                        ? `[${selectedCourse}] ${courses.find(c => c.maHocPhan === selectedCourse).tenHocPhan || courses.find(c => c.maHocPhan === selectedCourse).tenMonHoc}`
                        : `[${selectedCourse}]`
                      : '--- Chọn môn học ---'}
                  </span>
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                </div>

                {dropdownOpen && (
                  <div className="dropdown-menu">
                    <div className="dropdown-search-wrapper">
                      <Search className="w-4 h-4 text-gray-400 shrink-0" />
                      <input 
                        type="text" 
                        value={courseSearch}
                        onChange={(e) => setCourseSearch(e.target.value)}
                        placeholder="Tìm kiếm theo mã môn hoặc tên môn..."
                        className="dropdown-search-input"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                    <div className="dropdown-list">
                      {coursesLoading ? (
                        <div style={{ padding: '16px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>Đang tải danh sách môn...</div>
                      ) : isTokenExpired ? (
                        <div style={{ padding: '16px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--danger-hover)', fontWeight: '500' }}>
                          ⚠️ Phiên đăng nhập hết hạn. Hãy bấm "Tự động lấy Token & id đợt"!
                        </div>
                      ) : filteredCourses.length > 0 ? (
                        filteredCourses.map((c, index) => {
                          const lbl = `[${c.maHocPhan}] ${c.tenHocPhan || c.tenMonHoc || ''}`;
                          const isRequired = c.isBatBuoc;
                          return (
                            <div 
                              key={index}
                              onClick={() => {
                                setSelectedCourse(c.maHocPhan);
                                setDropdownOpen(false);
                              }}
                              className={`dropdown-item ${selectedCourse === c.maHocPhan ? 'selected' : ''}`}
                            >
                              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '80%' }}>{lbl}</span>
                              {isRequired && (
                                <span style={{ background: 'rgba(244,63,94,0.15)', color: '#fda4af', border: '1px solid rgba(244,63,94,0.3)', padding: '2px 6px', borderRadius: '4px', fontSize: '8px', fontWeight: 'bold' }}>BẮT BUỘC</span>
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <div style={{ padding: '16px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-dark)' }}>Không tìm thấy môn nào</div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Filters */}
              <div className="grid-2">
                <div className="form-group" style={{ marginBottom: '0' }}>
                  <label className="input-label">Lọc Thứ</label>
                  <select 
                    value={filterThu} 
                    onChange={(e) => setFilterThu(e.target.value)}
                    className="select-input"
                  >
                    <option value="Tất cả">Tất cả các ngày</option>
                    <option value="Thứ 2">Thứ Hai</option>
                    <option value="Thứ 3">Thứ Ba</option>
                    <option value="Thứ 4">Thứ Tư</option>
                    <option value="Thứ 5">Thứ Năm</option>
                    <option value="Thứ 6">Thứ Sáu</option>
                    <option value="Thứ 7">Thứ Bảy</option>
                    <option value="Chủ nhật">Chủ nhật</option>
                  </select>
                </div>
                <div className="form-group" style={{ marginBottom: '0' }}>
                  <label className="input-label">Lọc Ca Học</label>
                  <select 
                    value={filterCa} 
                    onChange={(e) => setFilterCa(e.target.value)}
                    className="select-input"
                  >
                    <option value="Tất cả">Tất cả các ca</option>
                    <option value="Ca 1 (Tiết 1-3)">Ca 1 (Tiết 1-3)</option>
                    <option value="Ca 2 (Tiết 4-6)">Ca 2 (Tiết 4-6)</option>
                    <option value="Ca 3 (Tiết 7-9)">Ca 3 (Tiết 7-9)</option>
                    <option value="Ca 4 (Tiết 10-12)">Ca 4 (Tiết 10-12)</option>
                    <option value="Ca 5 (Tiết 13-15)">Ca 5 (Tiết 13-15)</option>
                  </select>
                </div>
              </div>

              {/* Scan Button */}
              <button
                onClick={handleScanClasses}
                disabled={isScanning || !configExists}
                className="btn btn-secondary"
                style={{ marginTop: '8px' }}
              >
                <Search className="w-4 h-4" />
                {isScanning ? 'ĐANG QUÉT CHI TIẾT LỚP...' : 'QUÉT CHI TIẾT LỚP HỌC PHẦN'}
              </button>
            </div>
          </motion.div>

          {/* REGISTERED CLASSES CARD */}
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
            className="card"
            style={{ marginTop: '16px' }}
          >
            <div className="card-header" style={{ marginBottom: '14px' }}>
              <h2 className="card-title purple">
                <CheckSquare className="w-5 h-5" />
                3. Học phần đã đăng ký thành công
              </h2>
              <button 
                onClick={fetchRegisteredClasses}
                disabled={registeredLoading || !configExists}
                className="eye-button"
                title="Tải lại danh sách lớp đã đăng ký"
                style={{ padding: '6px' }}
              >
                <RefreshCw className={`w-4 h-4 ${registeredLoading ? 'spin-loading' : ''}`} />
              </button>
            </div>

            <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
              {registeredLoading ? (
                <div style={{ padding: '20px', textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Đang tải danh sách học phần đã đăng ký...
                </div>
              ) : registeredClasses.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {registeredClasses.map((rc, idx) => {
                    const rcId = rc.id || rc.idDangKy;
                    const rcName = rc.tenLopHocPhan || rc.tenHocPhan || rc.tenMonHoc || 'Học phần';
                    const rcCode = rc.maLopHocPhan || rc.maHocPhan || '';
                    const rcCredits = rc.soTinChi || 0;
                    return (
                      <div 
                        key={idx} 
                        style={{ 
                          background: 'rgba(255, 255, 255, 0.02)', 
                          border: '1px solid rgba(255, 255, 255, 0.05)', 
                          borderRadius: '8px', 
                          padding: '10px 14px', 
                          display: 'flex', 
                          justifyContent: 'space-between', 
                          alignItems: 'center',
                          gap: '10px'
                        }}
                      >
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', overflow: 'hidden' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {rcName}
                          </span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            Mã lớp: {rcCode} ({rcCredits} TC)
                          </span>
                          {rc.scheduleText && (
                            <span style={{ fontSize: '0.7rem', color: '#38bdf8', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              📅 {rc.scheduleText}
                            </span>
                          )}
                        </div>
                        <button 
                          onClick={() => handleDeregisterClass(rcId, rcName, rc.isConditional)}
                          className="btn btn-outline"
                          style={{ 
                            width: 'auto', 
                            padding: '6px 12px', 
                            fontSize: '0.75rem', 
                            borderColor: 'rgba(244, 63, 94, 0.4)', 
                            color: '#fb7185',
                            background: 'rgba(244, 63, 94, 0.05)'
                          }}
                        >
                          Hủy đăng ký
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ padding: '20px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-dark)', border: '1px dashed rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                  Chưa có môn nào đã đăng ký trong đợt này.
                </div>
              )}
            </div>
          </motion.div>

        </div>

        {/* RIGHT COLUMN: SCAN RESULTS & SPAM CONSOLE */}
        <div className="col-flex">
          
          {/* SCAN RESULTS TABLE */}
          <motion.div 
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="card"
            style={{ display: 'flex', flexDirection: 'column', minHeight: '380px' }}
          >
            <div className="card-header" style={{ marginBottom: '10px' }}>
              <div>
                <h2 className="card-title cyan">
                  <Layers className="w-5 h-5" />
                  2. Kết quả quét lớp học phần
                </h2>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Tích chọn lớp để Spam. Chỉ được chọn tối đa 1 lớp cho mỗi môn học.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--text-muted)', cursor: 'pointer', background: 'rgba(255,255,255,0.02)', padding: '6px 10px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <input
                    type="checkbox"
                    checked={hideConflicting}
                    onChange={(e) => setHideConflicting(e.target.checked)}
                    style={{ cursor: 'pointer', margin: 0 }}
                  />
                  <span>Ẩn lớp trùng lịch</span>
                </label>

                {checkedClasses.length > 0 && (
                  <button 
                    onClick={handleClearSelection}
                    className="btn btn-outline"
                    style={{ width: 'auto', padding: '6px 12px', fontSize: '0.75rem' }}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Xóa chọn ({checkedClasses.length})
                  </button>
                )}
              </div>
            </div>

            <div className="table-container" style={{ flex: '1', minHeight: '220px' }}>
              {isScanning ? (
                <div style={{ height: '220px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px', color: 'var(--text-muted)' }}>
                  <div className="spin-loading">
                    <RefreshCw className="w-8 h-8 text-cyan-400" />
                  </div>
                  <span style={{ fontSize: '0.8rem' }} className="pulse-indicator">Hệ thống đang truy quét thông tin sĩ số và lịch học...</span>
                </div>
              ) : classes.length > 0 ? (
                <div style={{ overflowX: 'auto', maxHeight: '340px' }}>
                  <table className="custom-table">
                    <thead>
                      <tr>
                        <th style={{ width: '50px', textAlign: 'center' }}>Chọn</th>
                        <th style={{ width: '110px' }}>Mã Lớp</th>
                        <th>Tên Môn Học</th>
                        <th>Lịch Học Chi Tiết</th>
                        <th style={{ width: '110px', textAlign: 'center' }}>Sĩ số (%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <AnimatePresence>
                        {classes.filter(cls => !hideConflicting || !cls.is_conflicting).map((cls, idx) => {
                          const isSelected = checkedClasses.some(c => c.id === cls.id);
                          return (
                            <motion.tr 
                              key={cls.id}
                              initial={{ opacity: 0, y: 10 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0 }}
                              transition={{ delay: idx * 0.02 }}
                              onClick={() => handleToggleClass(cls)}
                              className={`${isSelected ? 'selected' : ''}`}
                              style={{ opacity: cls.is_conflicting ? 0.6 : 1 }}
                            >
                              <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                                <input 
                                  type="checkbox" 
                                  checked={isSelected}
                                  onChange={() => handleToggleClass(cls)}
                                  style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                                />
                              </td>
                              <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', fontWeight: '600' }}>{cls.maLopHocPhan}</td>
                              <td style={{ fontWeight: '600' }}>{cls.tenMonHoc}</td>
                              <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                <div>{cls.schedule}</div>
                                {cls.is_conflicting && (
                                  <div style={{ color: '#f43f5e', fontSize: '0.7rem', marginTop: '3px', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '3px' }}>
                                    ⚠️ Trùng: {cls.conflict_with}
                                  </div>
                                )}
                              </td>
                              <td>
                                <div className="progress-container">
                                  <span className={`percent-text ${cls.status.includes("FULL") ? 'full' : 'available'}`}>
                                    {cls.status}
                                  </span>
                                  <div className="progress-bar-bg">
                                    <div 
                                      className={`progress-bar-fill ${cls.status.includes("FULL") ? 'full' : 'available'}`}
                                      style={{ width: `${Math.min(cls.capacity_percent, 100)}%` }}
                                    ></div>
                                  </div>
                                </div>
                              </td>
                            </motion.tr>
                          );
                        })}
                      </AnimatePresence>
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ height: '220px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dark)', gap: '8px' }}>
                  <HelpCircle className="w-8 h-8" />
                  <span style={{ fontSize: '0.8rem' }}>Không có lớp học phần nào để hiển thị. Hãy thực hiện Quét Chi Tiết.</span>
                </div>
              )}
            </div>

            {/* Checked Classes list preview */}
            {checkedClasses.length > 0 && (
              <div className="selection-preview-box">
                <div className="selection-preview-title">
                  <CheckSquare className="w-3.5 h-3.5" />
                  Lớp đã chọn để Spam ({checkedClasses.length}):
                </div>
                <div className="badge-list">
                  {checkedClasses.map(c => (
                    <div key={c.id} className="selected-badge">
                      <span>[{c.maLopHocPhan}] {c.tenMonHoc}</span>
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          setCheckedClasses(checkedClasses.filter(x => x.id !== c.id));
                        }}
                        className="selected-badge-close"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>

          {/* SPAM ACTION PANEL */}
          <motion.div 
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="card"
          >
            <div className="card-header" style={{ marginBottom: '16px' }}>
              <h2 className="card-title rose">
                <Terminal className="w-5 h-5" />
                4. Trình điều khiển Spam và Console log
              </h2>
              
              {/* Stats tags */}
              <div className="stats-bar">
                <span className="stat-tag">
                  Gửi: <strong>{spamStats.total_requests}</strong>
                </span>
                <span className="stat-tag success">
                  Thành công: <strong>{spamStats.success_count}</strong>
                </span>
                <span className="stat-tag danger">
                  Lỗi: <strong>{spamStats.error_count}</strong>
                </span>
              </div>
            </div>

            {/* Real-time console terminal */}
            <div className="terminal-box">
              {logs.length > 0 ? (
                logs.map((log, index) => {
                  let logClass = 'terminal-line';
                  if (log.includes('THÀNH CÔNG') || log.includes('🎉')) logClass += ' success';
                  if (log.includes('Lỗi') || log.includes('❌') || log.includes('💀')) logClass += ' danger';
                  if (log.includes('⚠️')) logClass += ' warning';
                  if (log.includes('ℹ️')) logClass += ' info';
                  return (
                    <div key={index} className={logClass}>
                      {log}
                    </div>
                  );
                })
              ) : (
                <div className="terminal-empty">
                  Nhật ký hoạt động trống. Nhấn Bắt đầu Spam để hiển thị.
                </div>
              )}
              {isSpamming && (
                <div className="terminal-pulse">
                  ➤ Đang rà soát và spam liên tục...<span className="cursor-blink">|</span>
                </div>
              )}
              <div ref={terminalEndRef} />
            </div>

            {/* Speed Mode Selector */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(255,255,255,0.02)', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', marginBottom: '14px' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Chế độ Tốc độ:</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setSpamMode('normal')}
                  disabled={isSpamming}
                  className="btn"
                  style={{
                    padding: '6px 12px',
                    fontSize: '0.75rem',
                    minHeight: 'auto',
                    background: spamMode === 'normal' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                    border: spamMode === 'normal' ? '1px solid #38bdf8' : '1px solid rgba(255,255,255,0.1)',
                    color: spamMode === 'normal' ? '#38bdf8' : 'rgba(255,255,255,0.6)',
                    cursor: isSpamming ? 'not-allowed' : 'pointer'
                  }}
                >
                  ⚡ Thường (An toàn)
                </button>
                <button
                  onClick={() => setSpamMode('turbo')}
                  disabled={isSpamming}
                  className="btn"
                  style={{
                    padding: '6px 12px',
                    fontSize: '0.75rem',
                    minHeight: 'auto',
                    background: spamMode === 'turbo' ? 'rgba(244, 63, 94, 0.2)' : 'transparent',
                    border: spamMode === 'turbo' ? '1px solid #f43f5e' : '1px solid rgba(255,255,255,0.1)',
                    color: spamMode === 'turbo' ? '#f43f5e' : 'rgba(255,255,255,0.6)',
                    cursor: isSpamming ? 'not-allowed' : 'pointer'
                  }}
                >
                  🚀 Turbo (Gửi song song)
                </button>
              </div>
            </div>

            {/* Play / Stop Action Button */}
            <div>
              {!isSpamming ? (
                <button
                  onClick={handleStartSpam}
                  disabled={checkedClasses.length === 0}
                  className="btn btn-danger"
                  style={{ padding: '16px', fontSize: '1rem' }}
                >
                  <Play className="w-5 h-5 fill-current" />
                  CHẠY SPAM ĐĂNG KÝ ({checkedClasses.length} LỚP)
                </button>
              ) : (
                <button
                  onClick={handleStopSpam}
                  className="btn btn-secondary"
                  style={{ padding: '16px', fontSize: '1rem', background: 'linear-gradient(135deg, #d97706 0%, #b45309 100%)', boxShadow: '0 4px 15px rgba(217, 119, 6, 0.3)' }}
                >
                  <Square className="w-5 h-5 fill-current" />
                  DỪNG SPAM ĐĂNG KÝ
                </button>
              )}
            </div>
          </motion.div>

        </div>

      </div>

      {/* 🔐 SCREEN OVERLAY: LOGIN ON APP ENTRY */}
      {showLoginOverlay && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'radial-gradient(circle at center, rgba(16, 12, 34, 0.98) 0%, rgba(5, 3, 15, 0.99) 100%)',
          backdropFilter: 'blur(20px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px'
        }}>
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            style={{
              background: 'rgba(23, 20, 41, 0.75)',
              border: '1px solid rgba(56, 189, 248, 0.15)',
              borderRadius: '24px',
              padding: '36px',
              maxWidth: '460px',
              width: '100%',
              boxShadow: '0 30px 60px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05), 0 0 40px rgba(14, 165, 233, 0.05)',
              position: 'relative',
              overflow: 'hidden'
            }}
          >
            {/* Glowing background details */}
            <div style={{ position: 'absolute', top: '-10%', left: '-10%', width: '150px', height: '150px', background: 'var(--accent-glow)', filter: 'blur(60px)', opacity: 0.2, pointerEvents: 'none' }}></div>
            
            <div style={{ textAlign: 'center', marginBottom: '28px' }}>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '16px',
                background: 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px auto',
                boxShadow: '0 8px 20px rgba(14, 165, 233, 0.3)'
              }}>
                <ShieldCheck className="w-8 h-8 text-white" />
              </div>
              <h1 style={{ fontSize: '1.6rem', fontWeight: '800', background: 'linear-gradient(135deg, #fff 0%, #cbd5e1 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '6px' }}>
                SmartEnroll UTH
              </h1>
              <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>
                Công cụ hỗ trợ đăng ký học phần tối ưu & thông minh
              </p>
            </div>
            
            <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="input-label" style={{ fontSize: '0.8rem', marginBottom: '6px' }}>Mã số sinh viên (MSSV)</label>
                <input 
                  type="text" 
                  value={username} 
                  onChange={(e) => setUsername(e.target.value)} 
                  placeholder="Nhập MSSV..." 
                  className="text-input" 
                  style={{ padding: '12px 14px', fontSize: '0.9rem' }}
                  required
                />
              </div>
              
              <div className="form-group" style={{ margin: 0 }}>
                <label className="input-label" style={{ fontSize: '0.8rem', marginBottom: '6px' }}>Mật khẩu cổng UTH</label>
                <div style={{ position: 'relative' }}>
                  <input 
                    type={showPassword ? "text" : "password"} 
                    value={password} 
                    onChange={(e) => setPassword(e.target.value)} 
                    placeholder="Nhập mật khẩu..." 
                    className="text-input" 
                    style={{ padding: '12px 42px 12px 14px', width: '100%', fontSize: '0.9rem' }}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute',
                      right: '14px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      color: 'rgba(255, 255, 255, 0.4)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center'
                    }}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              
              {loginError && (
                <div style={{ color: '#fb7185', fontSize: '0.825rem', display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(244, 63, 94, 0.08)', padding: '10px 12px', borderRadius: '8px', border: '1px solid rgba(244, 63, 94, 0.15)' }}>
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{loginError}</span>
                </div>
              )}
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '10px' }}>
                <button 
                  type="submit" 
                  disabled={loginLoading} 
                  className="btn btn-primary" 
                  style={{ width: '100%', padding: '12px', display: 'flex', justifyContent: 'center', fontSize: '0.9rem', fontWeight: '600' }}
                >
                  {loginLoading ? 'ĐANG ĐĂNG NHẬP...' : 'XÁC NHẬN ĐĂNG NHẬP'}
                </button>
                
                {configExists && (
                  <button 
                    type="button" 
                    onClick={() => setShowLoginOverlay(false)} 
                    className="btn btn-outline" 
                    style={{ width: '100%', padding: '12px', fontSize: '0.85rem' }}
                  >
                    Bỏ qua & Vào thẳng Dashboard
                  </button>
                )}
              </div>
            </form>
          </motion.div>
        </div>
      )}

      {/* 🔔 CUSTOM NOTIFICATION / CONFIRMATION DIALOG MODAL */}
      <AnimatePresence>
        {customDialog && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(5, 3, 15, 0.85)',
            backdropFilter: 'blur(12px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10000,
            padding: '20px'
          }}>
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -10 }}
              style={{
                background: 'rgba(23, 20, 41, 0.95)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '16px',
                padding: '24px',
                maxWidth: '440px',
                width: '100%',
                boxShadow: '0 20px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
                textAlign: 'center'
              }}
            >
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: customDialog.type === 'confirm' 
                  ? 'rgba(56, 189, 248, 0.1)' 
                  : (customDialog.status === 'success' ? 'rgba(52, 211, 153, 0.1)' : 'rgba(244, 63, 94, 0.1)'),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px auto',
                color: customDialog.type === 'confirm' 
                  ? '#38bdf8' 
                  : (customDialog.status === 'success' ? '#34d399' : '#fb7185')
              }}>
                {customDialog.type === 'confirm' ? (
                  <HelpCircle className="w-6 h-6" />
                ) : (
                  customDialog.status === 'success' ? <CheckCircle2 className="w-6 h-6" /> : <XCircle className="w-6 h-6" />
                )}
              </div>
              
              <h3 style={{
                fontSize: '1.05rem',
                fontWeight: '600',
                color: '#fff',
                marginBottom: '10px'
              }}>
                {customDialog.type === 'confirm' ? 'Xác nhận yêu cầu' : 'Thông báo hệ thống'}
              </h3>
              
              <p style={{
                fontSize: '0.875rem',
                color: 'rgba(255,255,255,0.7)',
                lineHeight: '1.5',
                marginBottom: '24px'
              }}>
                {customDialog.message}
              </p>
              
              <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                {customDialog.type === 'confirm' && (
                  <button
                    onClick={() => {
                      customDialog.resolve(false);
                      setCustomDialog(null);
                    }}
                    className="btn btn-outline"
                    style={{ flex: 1, padding: '10px' }}
                  >
                    Hủy bỏ
                  </button>
                )}
                <button
                  onClick={() => {
                    customDialog.resolve(true);
                    setCustomDialog(null);
                  }}
                  className="btn btn-primary"
                  style={{ flex: 1, padding: '10px' }}
                >
                  Đồng ý
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
