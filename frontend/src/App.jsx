import React, { useState, useEffect, useRef } from 'react';
import { 
  Settings, Play, Square, RefreshCw, Search, Check, AlertCircle, 
  Terminal, ShieldAlert, Cpu, Layers, HelpCircle, CheckSquare, 
  Trash2, Eye, EyeOff, CheckCircle2, XCircle, Info, ChevronDown
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function App() {
  // App States
  const [config, setConfig] = useState(null);
  const [configExists, setConfigExists] = useState(false);
  const [isTokenExpired, setIsTokenExpired] = useState(false);
  const [showManual, setShowManual] = useState(false);
  
  // Manual Config inputs
  const [manToken, setManToken] = useState('');
  const [manCookie, setManCookie] = useState('');
  const [manIdDot, setManIdDot] = useState('');
  const [manUserAgent, setManUserAgent] = useState('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
  
  // Auto Config Status
  const [autoStatus, setAutoStatus] = useState('idle'); // idle, running, success, failed
  const [isAutoRunning, setIsAutoRunning] = useState(false);

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

  // Spam states
  const [isSpamming, setIsSpamming] = useState(false);
  const [spamStats, setSpamStats] = useState({ total_requests: 0, success_count: 0, error_count: 0 });
  const [logs, setLogs] = useState([]);
  
  // UI views
  const [showToken, setShowToken] = useState(false);
  const [showCookie, setShowCookie] = useState(false);
  const terminalEndRef = useRef(null);

  // Fetch initial config
  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      if (data.exists) {
        setConfig(data.config);
        setConfigExists(true);
        setIsTokenExpired(false);
        setManToken(data.config.token || '');
        setManCookie(data.config.cookie || '');
        setManIdDot(data.config.id_dot || '');
        setManUserAgent(data.config.user_agent || '');
      } else {
        setConfig(null);
        setConfigExists(false);
        setIsTokenExpired(false);
      }
    } catch (err) {
      console.error("Lỗi lấy cấu hình:", err);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  // Fetch courses list once config is loaded
  const fetchCourses = async () => {
    if (!configExists) return;
    setCoursesLoading(true);
    try {
      const res = await fetch('/api/courses');
      const data = await res.json();
      if (data.success) {
        setCourses(data.data || []);
        setIsTokenExpired(false);
      } else {
        if (res.status === 401 || data.expired || (data.message && data.message.includes("Token hết hạn"))) {
          setIsTokenExpired(true);
          setCourses([]);
        } else {
          alert("Lỗi tải môn học: " + data.message);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setCoursesLoading(false);
    }
  };

  useEffect(() => {
    if (configExists) {
      fetchCourses();
    }
  }, [configExists, config]);

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
        alert(data.message);
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
          user_agent: manUserAgent
        })
      });
      const data = await res.json();
      if (data.success) {
        setShowManual(false);
        fetchConfig();
        alert("Đã lưu cấu hình!");
      } else {
        alert("Lỗi: " + data.message);
      }
    } catch (err) {
      alert("Lỗi lưu cấu hình: " + err.message);
    }
  };

  // Scan classes
  const handleScanClasses = async () => {
    if (!selectedCourse) {
      alert("Vui lòng chọn môn học để quét!");
      return;
    }
    setIsScanning(true);
    setClasses([]);
    try {
      const res = await fetch(`/api/classes?maHocPhan=${selectedCourse}&thu=${encodeURIComponent(filterThu)}&ca=${encodeURIComponent(filterCa)}`);
      const data = await res.json();
      if (data.success) {
        setClasses(data.data || []);
        if (data.data.length === 0) {
          alert("Không tìm thấy lớp nào phù hợp bộ lọc.");
        }
      } else {
        alert("Lỗi quét lớp: " + data.message);
      }
    } catch (err) {
      alert("Lỗi mạng: " + err.message);
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
      const filtered = checkedClasses.filter(c => c.tenMonHoc !== cls.tenMonHoc);
      setCheckedClasses([...filtered, cls]);
    }
  };

  // Start Spamming
  const handleStartSpam = async () => {
    if (checkedClasses.length === 0) {
      alert("Vui lòng tích chọn lớp học phần muốn đăng ký!");
      return;
    }
    try {
      const res = await fetch('/api/spam/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          targets: checkedClasses.map(c => ({ id: c.id, name: c.tenMonHoc }))
        })
      });
      const data = await res.json();
      if (data.success) {
        setIsSpamming(true);
      } else {
        alert("Lỗi: " + data.message);
      }
    } catch (err) {
      alert("Lỗi khởi động spam: " + err.message);
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
                      <div className="config-item">
                        <span className="config-key">ID Đợt học phần (id_dot):</span>
                        <span className="config-value glow">{config.id_dot}</span>
                      </div>
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
                          <span style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {showCookie ? config.cookie : '••••••••••••••••••••••••'}
                          </span>
                          <button onClick={() => setShowCookie(!showCookie)} className="eye-button">
                            {showCookie ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="alert alert-danger">
                      <ShieldAlert className="w-5 h-5 shrink-0" />
                      <div>
                        Chưa tìm thấy tệp cấu hình <code>config.json</code>. Vui lòng bấm vào nút tự động lấy token phía dưới.
                      </div>
                    </div>
                  )}

                  {/* AUTO CONFIG LOGIC */}
                  <div>
                    <button
                      onClick={handleStartAutoConfig}
                      disabled={isAutoRunning}
                      className="btn btn-primary"
                    >
                      <RefreshCw className={`w-4 h-4 ${isAutoRunning ? 'spin-loading' : ''}`} />
                      {isAutoRunning ? 'ĐANG ĐỌC TỰ ĐỘNG CHROME...' : 'TỰ ĐỘNG LẤY TOKEN & ID ĐỢT'}
                    </button>

                    {/* Step guidance during auto retrieval */}
                    {isAutoRunning && (
                      <motion.div 
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        className="alert alert-info"
                        style={{ marginTop: '14px', flexDirection: 'column' }}
                      >
                        <div style={{ fontWeight: '700', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Info className="w-4 h-4 text-yellow-400 shrink-0" />
                          Hướng dẫn bắt Token và ID Đợt:
                        </div>
                        <ol className="alert-steps">
                          <li>Cửa sổ trình duyệt Chrome ẩn danh sẽ khởi động.</li>
                          <li>Vui lòng <span className="highlight">ĐĂNG NHẬP</span> tài khoản portal của bạn bằng tay.</li>
                          <li>Hệ thống sẽ tự động quét lấy Token và tìm Đợt đăng ký mới nhất từ API trường rồi đóng Chrome ngay lập tức!</li>
                        </ol>
                      </motion.div>
                    )}

                    {/* Feedback states */}
                    {autoStatus === 'success' && !isAutoRunning && (
                      <div className="alert alert-success" style={{ marginTop: '12px' }}>
                        <CheckCircle2 className="w-4 h-4" />
                        Đã nạp Token và ID Đợt thành công! Trình duyệt đã tắt.
                      </div>
                    )}
                    {autoStatus === 'failed' && !isAutoRunning && (
                      <div className="alert alert-danger" style={{ marginTop: '12px' }}>
                        <XCircle className="w-4 h-4" />
                        Có lỗi xảy ra hoặc bạn đã đóng Chrome sớm. Hãy thử lại.
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
                    <div className="form-group">
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
                        {classes.map((cls, idx) => {
                          const isSelected = checkedClasses.some(c => c.id === cls.id);
                          return (
                            <motion.tr 
                              key={cls.id}
                              initial={{ opacity: 0, y: 10 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0 }}
                              transition={{ delay: idx * 0.02 }}
                              onClick={() => handleToggleClass(cls)}
                              className={isSelected ? 'selected' : ''}
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
                              <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{cls.schedule}</td>
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
                3. Trình điều khiển Spam và Console log
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
    </div>
  );
}
