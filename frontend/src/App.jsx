import { useState, useEffect, useRef } from 'react';
import {
  Settings, Play, Square, RefreshCw, Search, Check, AlertCircle, Layers, HelpCircle,
  Trash2, Eye, EyeOff, CheckCircle2, XCircle, Info, ChevronDown, ChevronRight,
  Share2, ExternalLink, Image as ImageIcon, Download, LayoutGrid, Award, LogOut,
  GraduationCap, KeyRound, ListChecks, BadgeCheck, UserRound, X
} from 'lucide-react';
import { motion, AnimatePresence, MotionConfig, animate, useMotionValue, useTransform } from 'framer-motion';

// ---------------------------------------------------------------- motion presets
const spring = { type: 'spring', stiffness: 420, damping: 34 };
const softSpring = { type: 'spring', stiffness: 260, damping: 26 };
const easeOut = [0.16, 1, 0.3, 1];
const menuAnim = {
  initial: { opacity: 0, y: -6, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1 },
  // stop catching clicks the moment the menu starts closing, so a quick next click isn't swallowed
  exit: { opacity: 0, y: -4, scale: 0.98, pointerEvents: 'none' },
  transition: { duration: 0.16, ease: 'easeOut' },
  style: { transformOrigin: 'top center' }
};
const tabAnim = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.28, ease: easeOut }
};
const swapAnim = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.18 }
};
const fillBox = (originY = '50%') => ({ transformBox: 'fill-box', transformOrigin: `50% ${originY}` });

// Original illustration for the greeting card: a timetable with the chosen slot ticked.
// Only a one-off entrance (slot pops in, tick draws itself): no endless loops, so an open tab
// left for hours costs nothing.
function HeroArt() {
  return (
    <svg viewBox="0 0 240 200" fill="none" aria-hidden="true">
      <circle cx="166" cy="64" r="46" fill="#fdf0e1" />
      <circle cx="190" cy="42" r="15" fill="#f08a24" />
      <rect x="46" y="52" width="136" height="124" rx="20" fill="#fff" stroke="#e6e5e1" strokeWidth="2" />
      <rect x="46" y="52" width="136" height="36" rx="20" fill="#161615" />
      <rect x="46" y="70" width="136" height="18" fill="#161615" />
      <rect x="74" y="40" width="8" height="24" rx="4" fill="#3b3a37" />
      <rect x="146" y="40" width="8" height="24" rx="4" fill="#3b3a37" />
      <rect x="62" y="67" width="42" height="6" rx="3" fill="#fff" opacity="0.85" />
      <rect x="110" y="67" width="18" height="6" rx="3" fill="#f08a24" />
      {[100, 126, 152].map(y => [62, 92, 122, 152].map(x => (
        <rect key={`${x}-${y}`} x={x} y={y} width="22" height="18" rx="6" fill="#f6f6f4" />
      )))}
      <rect x="152" y="100" width="22" height="18" rx="6" fill="#ecebfa" />
      <rect x="62" y="152" width="22" height="18" rx="6" fill="#ecebe8" />
      <motion.g
        style={fillBox()}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', stiffness: 320, damping: 14, delay: 0.45 }}
      >
        <rect x="122" y="126" width="22" height="18" rx="6" fill="#f08a24" />
        <motion.path
          d="M127.5 135.5l4 4 7.5-7.5" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.45, delay: 0.8, ease: 'easeOut' }}
        />
      </motion.g>
      <ellipse cx="27" cy="142" rx="7" ry="19" transform="rotate(-24 27 142)" fill="#2a9466" />
      <ellipse cx="40" cy="138" rx="7" ry="21" transform="rotate(16 40 138)" fill="#47b483" />
      <rect x="18" y="160" width="32" height="26" rx="8" fill="#161615" />
      <circle cx="214" cy="150" r="6" fill="#ecebfa" />
      <circle cx="202" cy="172" r="3.5" fill="#f08a24" />
    </svg>
  );
}

// Counts up/down to the new value instead of jumping.
function AnimatedNumber({ value }) {
  const target = Number(value) || 0;
  const mv = useMotionValue(target);
  const text = useTransform(mv, v => Math.round(v).toLocaleString('vi-VN'));
  useEffect(() => {
    const controls = animate(mv, target, { duration: 0.7, ease: easeOut });
    return () => controls.stop();
  }, [mv, target]);
  return <motion.span>{text}</motion.span>;
}

// Check mark that draws itself when a class is picked.
function TickMark({ on }) {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <motion.path
        d="M5 12.5l4.5 4.5L19 7.5" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round"
        initial={false}
        animate={{ pathLength: on ? 1 : 0, opacity: on ? 1 : 0 }}
        transition={{ duration: 0.26, ease: 'easeOut' }}
      />
    </svg>
  );
}

// Small confetti burst played when a registration succeeds (deterministic spread, no randomness).
const BURST_COLORS = ['#f08a24', '#2a9466', '#5753c4', '#f6b36b'];
function SuccessBurst() {
  return (
    <span className="burst" aria-hidden="true">
      {Array.from({ length: 14 }, (_, i) => {
        const angle = (i / 14) * Math.PI * 2 + (i % 2 ? 0.22 : -0.14);
        const distance = 40 + ((i * 13) % 26);
        return (
          <motion.i
            key={i}
            style={{ background: BURST_COLORS[i % BURST_COLORS.length] }}
            initial={{ x: 0, y: 0, scale: 0.5, opacity: 1, rotate: 0 }}
            animate={{ x: Math.cos(angle) * distance, y: Math.sin(angle) * distance, scale: 1, opacity: 0, rotate: 160 }}
            transition={{ duration: 0.95, ease: easeOut }}
          />
        );
      })}
    </span>
  );
}

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
  const [coursesError, setCoursesError] = useState(''); // shown inline under the course picker
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
  // Login runs as a background job on the local server; the UI only polls its progress.
  const [autoRetryLogin, setAutoRetryLogin] = useState(true); // keep retrying until the portal lets us in
  const [loginJob, setLoginJob] = useState(null); // { status, attempts, last_error, retry_in, elapsed }
  const loginPollingRef = useRef(false);
  const [tokenExpiresAt, setTokenExpiresAt] = useState(null); // epoch seconds from the saved JWT
  const [tokenStillValid, setTokenStillValid] = useState(false); // > 1h left: no need to log in again
  const [tokenOk, setTokenOk] = useState(null); // last answer from the portal: true / false / null (unknown)
  const [tokenCheckedAt, setTokenCheckedAt] = useState(null); // epoch seconds of that answer

  // Spam states
  const [isSpamming, setIsSpamming] = useState(false);
  const [spamMode, setSpamMode] = useState('normal'); // normal, turbo
  const [spamStats, setSpamStats] = useState({ total_requests: 0, success_count: 0, error_count: 0 });
  const [logs, setLogs] = useState([]);
  const [burstKey, setBurstKey] = useState(0); // replays the confetti burst
  const [toast, setToast] = useState(null);    // { id, text }
  const prevSuccessRef = useRef(null);

  // Update stats from the server and celebrate when the success count goes up.
  const lastStatsJsonRef = useRef('');
  const applySpamStats = (stats) => {
    // Unchanged stats -> no state update -> no re-render of the whole page.
    const json = JSON.stringify(stats || {});
    if (json === lastStatsJsonRef.current) return;
    lastStatsJsonRef.current = json;
    setSpamStats(stats);
    const success = stats?.success_count ?? 0;
    const prev = prevSuccessRef.current;
    prevSuccessRef.current = success;
    if (prev !== null && success > prev) {
      const id = Date.now();
      const gained = success - prev;
      setBurstKey(k => k + 1);
      setToast({ id, text: gained > 1 ? `Đăng ký thành công thêm ${gained} lớp` : 'Đăng ký thành công 1 lớp' });
      setTimeout(() => setToast(t => (t && t.id === id ? null : t)), 4500);
    }
  };
  
  // UI views
  const [showToken, setShowToken] = useState(false);
  const [showCookie, setShowCookie] = useState(false);
  const terminalEndRef = useRef(null);

  // Active tab state: 'enroll' or 'drl'
  const [activeTab, setActiveTab] = useState('enroll');
  // DRL feature states
  const [announcements, setAnnouncements] = useState([]);
  const [announcementsLoading, setAnnouncementsLoading] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareStep, setShareStep] = useState('');
  const [shareError, setShareError] = useState(null);
  const [shareStatus, setShareStatus] = useState('idle');

  // Facebook credentials states
  const [fbUsername, setFbUsername] = useState('');
  const [fbPassword, setFbPassword] = useState('');
  const [showFbPassword, setShowFbPassword] = useState(false);
  const [editFbLogin, setEditFbLogin] = useState(false);

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

  // Fetch UTH announcements/events from server
  const fetchAnnouncements = async () => {
    if (!configExists) return;
    setAnnouncementsLoading(true);
    try {
      const res = await fetch('/api/announcements');
      const data = await res.json();
      if (data.success) {
        setAnnouncements(data.data || []);
      } else {
        await alert("Không thể tải danh sách sự kiện: " + data.message);
      }
    } catch (err) {
      console.error("Lỗi cào sự kiện:", err);
    } finally {
      setAnnouncementsLoading(false);
    }
  };

  // Save Facebook login credentials directly from DRL tab
  const handleSaveFacebookCredentials = async (e) => {
    e.preventDefault();
    if (!fbUsername || !fbPassword) {
      await alert("Vui lòng điền đầy đủ tài khoản và mật khẩu Facebook!");
      return;
    }
    
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
          password: password,
          fb_username: fbUsername,
          fb_password: fbPassword
        })
      });
      const data = await res.json();
      if (data.success) {
        setEditFbLogin(false);
        fetchConfig();
        await alert("Lưu tài khoản Facebook thành công!");
      } else {
        await alert("Lỗi lưu tài khoản Facebook: " + data.message);
      }
    } catch (err) {
      await alert("Lỗi kết nối lưu cấu hình: " + err.message);
    }
  };

  // Run the Facebook auto-sharing flow and poll progress status
  const handleShareFacebook = async (eventId, title) => {
    setShowShareModal(true);
    setShareStep('Đang khởi động tiến trình chia sẻ...');
    setShareError(null);
    setShareStatus('running');
    
    try {
      const res = await fetch('/api/share/facebook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ eventId, title })
      });
      const data = await res.json();
      if (!data.success) {
        setShareStatus('error');
        setShareError(data.message);
        return;
      }
      
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch('/api/share/status');
          const statusData = await statusRes.json();
          setShareStatus(statusData.status);
          setShareStep(statusData.step);
          setShareError(statusData.error);
          
          if (statusData.status === 'success' || statusData.status === 'error') {
            clearInterval(pollInterval);
            if (statusData.status === 'success') {
              fetchAnnouncements(); // Refresh list to show screenshots
            }
          }
        } catch (err) {
          console.error("Lỗi thăm dò trạng thái:", err);
        }
      }, 1000);
      
    } catch (err) {
      setShareStatus('error');
      setShareError(err.message);
    }
  };

  // Clear the "expired" flag after any successful call to the portal
  const resetSessionTimer = () => {
    setIsTokenExpired(false);
  };

  // Sync config + real token status from the local server.
  // syncForm: also fill form fields (only on page load / after a new login, not on the 30s poll,
  //           otherwise it overwrites what the user is typing or the period they picked).
  // initial:  on page load, go straight to the dashboard if the saved token is still good.
  // Mirror of `config` so the poll can tell whether anything actually changed.
  const configRef = useRef(null);
  useEffect(() => { configRef.current = config; }, [config]);

  const fetchConfig = async ({ syncForm = true, initial = false } = {}) => {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      const exp = data.token_expires_at || null;
      const notExpiredByDate = !exp || exp * 1000 > Date.now();
      setTokenExpiresAt(exp);
      setTokenStillValid(!!exp && exp * 1000 > Date.now() + 60 * 60 * 1000);
      setTokenCheckedAt(data.token_checked_at || null);
      setTokenOk(data.token_ok ?? null);
      if (data.exists) {
        // Only hand React a new object when the content changed. A fresh object every 30 s used to
        // re-trigger the courses/registered-classes effect, i.e. 3+ portal requests twice a minute.
        if (JSON.stringify(data.config) !== JSON.stringify(configRef.current)) {
          setConfig(data.config);
        }
        setConfigExists(true);
        // Only the server knows if the portal still accepts the token (it checks every few minutes).
        setIsTokenExpired(data.token_ok === false || !notExpiredByDate);
        if (syncForm) {
          setManToken(data.config.token || '');
          setManCookie(data.config.cookie || '');
          setManIdDot(data.config.id_dot || '');
          setManUserAgent(data.config.user_agent || '');
          setUsername(data.config.username || '');
          setPassword(data.config.password || '');
          setFbUsername(data.config.fb_username || '');
          setFbPassword(data.config.fb_password || '');
          if (data.config.id_dot) {
            setSelectedDot(data.config.id_dot);
          }
        }
        if (initial && data.token_ok !== false && notExpiredByDate) {
          setShowLoginOverlay(false);
        }
      } else {
        setConfig(null);
        setConfigExists(false);
        setIsTokenExpired(false);
        if (syncForm) {
          setUsername('');
          setPassword('');
        }
      }
    } catch (err) {
      console.error("Lỗi lấy cấu hình:", err);
    }
  };

  useEffect(() => {
    fetchConfig({ initial: true });
  }, []);

  // Keep token status in sync with the server (which re-logins on its own if the portal drops the token)
  useEffect(() => {
    let interval;
    if (configExists) {
      interval = setInterval(() => {
        if (!document.hidden) fetchConfig({ syncForm: false });
      }, 30000); // Poll every 30 seconds, skipped while the tab is hidden
    }
    return () => clearInterval(interval);
  }, [configExists]);

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
          // ids come back as numbers while the saved one is a string: compare as strings,
          // otherwise the same period gets "re-selected" and courses are fetched twice
          const hasCurrent = loadedDots.some(d => String(d.id || d.idDot) === String(selectedDot));
          if (!hasCurrent) {
            setSelectedDot(String(loadedDots[0].id || loadedDots[0].idDot));
          }
        }
      } else {
        if (res.status === 401 || data.expired || (data.message && data.message.includes("Token hết hạn"))) {
          setIsTokenExpired(true);
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

  useEffect(() => {
    if (configExists && activeTab === 'drl') {
      fetchAnnouncements();
    }
  }, [configExists, activeTab]);

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
        setCoursesError('');
        setIsTokenExpired(false);
        resetSessionTimer();
      } else {
        setCourses([]);
        if (res.status === 401 || data.expired || (data.message && data.message.includes("Token hết hạn"))) {
          setIsTokenExpired(true);
        } else {
          // inline instead of a modal: e.g. 403 outside the registration window is expected, not an emergency
          setCoursesError(data.message || 'Không tải được danh sách môn.');
        }
      }
    } catch (err) {
      console.error(err);
      setCoursesError('Không kết nối được server SmartEnroll trên máy này.');
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

  // Poll spam status: every second while running, every 5 s otherwise, nothing while the tab is hidden
  // (the spam itself runs on the local server, so a hidden tab misses nothing).
  useEffect(() => {
    const interval = setInterval(async () => {
      if (document.hidden) return;
      try {
        const res = await fetch('/api/spam/status');
        const data = await res.json();
        setIsSpamming(data.is_spamming);
        applySpamStats(data.stats);
        if (isSpamming || data.is_spamming) {
          const next = data.logs || [];
          // keep the same array when nothing new was logged, so React skips the re-render
          setLogs(prev => (prev.length === next.length && prev[prev.length - 1] === next[next.length - 1] ? prev : next));
        }
      } catch (err) {
        console.error(err);
      }
    }, isSpamming ? 1000 : 5000);
    return () => clearInterval(interval);
  }, [isSpamming]);

  // Auto scroll terminal
  useEffect(() => {
    const box = terminalEndRef.current;
    if (box) {
      box.scrollTop = box.scrollHeight;
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
          password: password,
          fb_username: fbUsername,
          fb_password: fbPassword
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

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  const applyLoginSuccess = async (cfg) => {
    setConfig(cfg);
    setConfigExists(true);
    setIsTokenExpired(false);
    resetSessionTimer();
    setManToken(cfg.token || '');
    setManCookie(cfg.cookie || '');
    setManIdDot(cfg.id_dot || '');
    setManUserAgent(cfg.user_agent || '');
    if (cfg.id_dot) {
      setSelectedDot(cfg.id_dot);
    }
    fetchConfig(); // picks up token expiry
    setShowLoginOverlay(false);
    await alert('Đăng nhập cổng UTH thành công!');
  };

  // Poll the background login job until it finishes. Survives brief outages of the local server.
  const pollLoginStatus = async () => {
    if (loginPollingRef.current) return;
    loginPollingRef.current = true;
    setLoginLoading(true);
    let localServerDown = 0;
    while (loginPollingRef.current) {
      let data;
      try {
        const res = await fetch('/api/config/login/status', { cache: 'no-store' });
        data = await res.json();
        localServerDown = 0;
      } catch {
        localServerDown++;
        setLoginError(`Không liên lạc được server SmartEnroll trên máy này (lần ${localServerDown}). Hãy kiểm tra cửa sổ server còn chạy không — đang chờ kết nối lại...`);
        await sleep(1500);
        continue;
      }
      setLoginJob(data);
      if (data.status === 'running') {
        setLoginError('');
        await sleep(1000);
        continue;
      }
      if (!loginPollingRef.current) break; // user pressed stop meanwhile
      loginPollingRef.current = false;
      setLoginLoading(false);
      if (data.status === 'success' && data.config) {
        setLoginJob(null);
        await applyLoginSuccess(data.config);
      } else if (data.status === 'failed') {
        setLoginError(data.last_error || 'Đăng nhập thất bại!');
      } else if (data.status === 'idle') {
        setLoginError('Server SmartEnroll vừa khởi động lại, tiến trình đăng nhập đã mất. Hãy bấm đăng nhập lại.');
      }
      return;
    }
    setLoginLoading(false);
  };

  const stopLogin = async () => {
    loginPollingRef.current = false;
    setLoginLoading(false);
    try {
      await fetch('/api/config/login/stop', { method: 'POST' });
    } catch (err) {
      console.error(err);
    }
    setLoginError('Đã dừng đăng nhập.');
  };

  // Login handler (the same button stops a running login)
  const handleLogin = async (e) => {
    if (e) e.preventDefault();
    if (loginLoading) {
      await stopLogin();
      return;
    }
    if (!username || !password) {
      setLoginError('Vui lòng điền đầy đủ tài khoản và mật khẩu!');
      return;
    }

    setLoginLoading(true);
    setLoginError('');
    setLoginJob(null);

    // The local server may still be starting up: give it a few seconds before giving up.
    let data = null;
    for (let i = 0; i < 8 && !data; i++) {
      try {
        const res = await fetch('/api/config/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password, persistent: autoRetryLogin })
        });
        data = await res.json();
      } catch (err) {
        console.error(err);
        setLoginError('Đang chờ server SmartEnroll trên máy này phản hồi...');
        await sleep(1000);
      }
    }
    if (!data) {
      setLoginLoading(false);
      setLoginError('Không kết nối được server SmartEnroll trên máy này. Hãy kiểm tra cửa sổ server (server.py) còn chạy không.');
      return;
    }
    if (!data.success) {
      setLoginLoading(false);
      setLoginError(data.message || 'Không thể bắt đầu đăng nhập!');
      return;
    }
    setLoginError('');
    pollLoginStatus();
  };

  // Resume progress display if a login job is already running (e.g. after reloading the page)
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/config/login/status');
        const data = await res.json();
        if (data.status === 'running') {
          if (data.username) setUsername(data.username);
          setLoginJob(data);
          pollLoginStatus();
        }
      } catch (err) {
        console.error(err);
      }
    })();
    return () => { loginPollingRef.current = false; };
  }, []);

  const formatExpiry = (ts) => new Date(ts * 1000).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric' });

  // Progress panel shown under both login forms while the background job runs
  const renderLoginProgress = () => {
    if (!loginLoading || !loginJob) return null;
    const attempts = loginJob.attempts || 0;
    const elapsed = Math.round(loginJob.elapsed || 0);
    return (
      <div className="notice notice-info progress-note">
        <RefreshCw size={15} className="spin" />
        <div>
          <strong>{attempts === 0 ? 'Đang gửi yêu cầu đăng nhập…' : `Cổng trường đang nghẽn, đã thử ${attempts} lần (${elapsed}s)`}</strong>
          {loginJob.last_error && (
            <div className="sub">
              Lần gần nhất: {loginJob.last_error}
              {loginJob.retry_in != null && loginJob.retry_in > 0 && ` · thử lại sau ${loginJob.retry_in.toFixed(1)}s`}
            </div>
          )}
          <div className="sub">Đăng nhập chạy trên server ở máy bạn, đóng hay tải lại tab cũng không bị ngắt.</div>
        </div>
      </div>
    );
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
        setTokenExpiresAt(null);
        setTokenStillValid(false);
        setTokenOk(null);
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

  // ---------------------------------------------------------------- view helpers
  const [topSearchOpen, setTopSearchOpen] = useState(false);
  const scannerRef = useRef(null);
  const resultsRef = useRef(null);
  const consoleRef = useRef(null);
  const registeredRef = useRef(null);
  const accountRef = useRef(null);

  const scrollToRef = (ref) => ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  const courseLabel = (c) => `[${c.maHocPhan}] ${c.tenHocPhan || c.tenMonHoc || ''}`;
  const selectedCourseObj = courses.find(c => c.maHocPhan === selectedCourse);
  const visibleClasses = classes.filter(cls => !hideConflicting || !cls.is_conflicting);
  const hiddenConflicts = classes.length - visibleClasses.length;
  const totalCredits = registeredClasses.reduce((sum, rc) => sum + (Number(rc.soTinChi) || 0), 0);

  const status = isSpamming
    ? { cls: 'is-running', text: 'Đang gửi đăng ký' }
    : !configExists
      ? { cls: 'is-pending', text: 'Chưa đăng nhập' }
      : isTokenExpired
        ? { cls: 'is-expired', text: 'Phiên đăng nhập hết hạn' }
        : { cls: 'is-ready', text: 'Sẵn sàng' };

  const portalCheckText = tokenOk === false
    ? 'Bị từ chối, đang đăng nhập lại'
    : tokenOk && tokenCheckedAt
      ? `Còn hiệu lực lúc ${new Date(tokenCheckedAt * 1000).toLocaleTimeString('vi-VN')}`
      : 'Đang kiểm tra…';

  const logTone = (log) => {
    if (log.includes('THÀNH CÔNG') || log.includes('🎉')) return 'success';
    if (log.includes('Lỗi') || log.includes('❌') || log.includes('💀')) return 'danger';
    if (log.includes('⚠️')) return 'warning';
    if (log.includes('ℹ️')) return 'info';
    return '';
  };

  let heroText;
  let heroAction;
  if (!configExists) {
    heroText = <>Bạn chưa đăng nhập cổng trường. Hãy đăng nhập <strong>trước giờ mở đăng ký</strong> để không phải chen vào lúc cổng nghẽn.</>;
    heroAction = <button type="button" className="btn btn-dark" onClick={() => setShowLoginOverlay(true)}>Đăng nhập</button>;
  } else if (isTokenExpired) {
    heroText = <>Cổng trường không còn chấp nhận phiên đăng nhập này. Server đang tự đăng nhập lại; nếu vẫn báo hết hạn, hãy đăng nhập lại.</>;
    heroAction = <button type="button" className="btn btn-dark" onClick={() => setShowLoginOverlay(true)}>Đăng nhập lại</button>;
  } else if (isSpamming) {
    heroText = <>Tool đang gửi đăng ký liên tục. Cứ để máy chạy, kết quả hiện ở <strong>nhật ký</strong> bên dưới.</>;
    heroAction = <button type="button" className="btn btn-dark" onClick={() => scrollToRef(consoleRef)}>Xem nhật ký</button>;
  } else {
    heroText = <>Phiên đăng nhập còn hạn{tokenExpiresAt ? <> đến <strong>{formatExpiry(tokenExpiresAt)}</strong></> : null}. Chọn lớp, rồi bấm chạy spam trước giờ mở đăng ký vài phút.</>;
    heroAction = <button type="button" className="btn btn-dark" onClick={() => scrollToRef(scannerRef)}>Chọn lớp học phần</button>;
  }

  const renderAutoConfigStatus = () => (
    <>
      {isAutoRunning && (
        <div className="notice notice-info">
          <Info size={15} />
          <div>
            <strong>Lấy token qua Chrome</strong>
            <ol>
              <li>Một cửa sổ Chrome sẽ tự mở.</li>
              <li>Bạn đăng nhập tay vào portal.</li>
              <li>Tool tự bắt token, đợt học rồi đóng Chrome.</li>
            </ol>
          </div>
        </div>
      )}
      {autoStatus === 'success' && !isAutoRunning && (
        <div className="notice notice-ok"><CheckCircle2 size={15} /><span>Đã lấy token từ Chrome.</span></div>
      )}
      {autoStatus === 'failed' && !isAutoRunning && (
        <div className="notice notice-err"><XCircle size={15} /><span>Không lấy được token. Hãy thử lại.</span></div>
      )}
    </>
  );

  const seenLogs = {};
  const keyedLogs = logs.map(text => {
    seenLogs[text] = (seenLogs[text] || 0) + 1;
    return { key: `${text}#${seenLogs[text]}`, text };
  });

  const fadeUp = (delay = 0) => ({
    initial: { opacity: 0, y: 14 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.35, delay, ease: [0.16, 1, 0.3, 1] }
  });

  return (
    <MotionConfig reducedMotion="user">
    <div className="shell">
      {/* ---------------------------------------------------------- SIDEBAR */}
      <aside className="sidebar" aria-label="Điều hướng">
        <div className="sidebar-logo" title="SmartEnroll UTH">
          <GraduationCap size={22} />
        </div>
        <nav className="nav">
          <button
            type="button"
            className={`nav-btn ${activeTab === 'enroll' ? 'active' : ''} ${isSpamming ? 'is-busy' : ''}`}
            onClick={() => setActiveTab('enroll')}
            title="Đăng ký học phần"
            aria-label="Đăng ký học phần"
            aria-current={activeTab === 'enroll' ? 'page' : undefined}
          >
            {activeTab === 'enroll' && <motion.span layoutId="nav-indicator" className="nav-indicator" transition={spring} />}
            <LayoutGrid size={20} />
          </button>
          <button
            type="button"
            className={`nav-btn ${activeTab === 'drl' ? 'active' : ''}`}
            onClick={() => setActiveTab('drl')}
            title="Điểm rèn luyện"
            aria-label="Điểm rèn luyện"
            aria-current={activeTab === 'drl' ? 'page' : undefined}
          >
            {activeTab === 'drl' && <motion.span layoutId="nav-indicator" className="nav-indicator" transition={spring} />}
            <Award size={20} />
          </button>
          <button
            type="button"
            className="nav-btn"
            onClick={() => window.open('/api/export', '_blank')}
            disabled={!configExists}
            title="Xuất dữ liệu học tập (JSON)"
            aria-label="Xuất dữ liệu học tập"
          >
            <Download size={20} />
          </button>
          <button
            type="button"
            className="nav-btn"
            onClick={() => setShowManual(true)}
            title="Cấu hình thủ công"
            aria-label="Cấu hình thủ công"
          >
            <Settings size={20} />
          </button>
          <div className="nav-bottom">
            <button
              type="button"
              className="nav-btn nav-danger"
              onClick={handleLogout}
              disabled={!configExists}
              title="Đăng xuất"
              aria-label="Đăng xuất"
            >
              <LogOut size={20} />
            </button>
          </div>
        </nav>
      </aside>

      <main className="main">
        {/* -------------------------------------------------------- TOP BAR */}
        <header className="topbar">
          <div className="top-search">
            <Search size={18} />
            <input
              type="search"
              value={courseSearch}
              onChange={(e) => { setCourseSearch(e.target.value); setTopSearchOpen(true); }}
              onFocus={() => setTopSearchOpen(true)}
              onBlur={() => setTopSearchOpen(false)}
              placeholder="Tìm môn học theo mã hoặc tên…"
              aria-label="Tìm môn học"
            />
            <AnimatePresence>
            {topSearchOpen && courseSearch.trim() && (
              <motion.div className="menu" {...menuAnim}>
                <div className="menu-list">
                  {filteredCourses.length > 0 ? (
                    filteredCourses.slice(0, 8).map((c, i) => (
                      <button
                        type="button"
                        key={`${c.maHocPhan}-${i}`}
                        className={`menu-item ${selectedCourse === c.maHocPhan ? 'selected' : ''}`}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          setSelectedCourse(c.maHocPhan);
                          setTopSearchOpen(false);
                          setActiveTab('enroll');
                          setTimeout(() => scrollToRef(scannerRef), 50);
                        }}
                      >
                        <span>{courseLabel(c)}</span>
                        {c.isBatBuoc && <span className="tag">Bắt buộc</span>}
                      </button>
                    ))
                  ) : (
                    <div className="menu-empty">{coursesLoading ? 'Đang tải danh sách môn…' : 'Không tìm thấy môn nào'}</div>
                  )}
                </div>
              </motion.div>
            )}
            </AnimatePresence>
          </div>

          <div className="topbar-right">
            <span className={`status-chip ${status.cls}`}>
              <span className="dot" />
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={status.text}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.16 }}
                >
                  {status.text}
                </motion.span>
              </AnimatePresence>
            </span>
            <div className="user">
              <div className="user-text">
                <div className="user-name">{config?.username || 'Khách'}</div>
                <div className="user-sub">Sinh viên UTH</div>
              </div>
              <div className="avatar"><UserRound size={20} /></div>
            </div>
          </div>
        </header>

        {/* ===================================================== TAB: ĐĂNG KÝ */}
        <AnimatePresence mode="wait">
        {activeTab === 'enroll' && (
          <motion.div key="enroll" className="dash-grid" {...tabAnim}>
            <div className="col">
              {/* HERO */}
              <motion.section className="card hero" {...fadeUp(0)}>
                <div>
                  <h1>Xin chào{config?.username ? `, ${config.username}` : ''}.</h1>
                  <motion.p key={status.cls} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
                    {heroText}
                  </motion.p>
                  {heroAction}
                </div>
                <div className="hero-art"><HeroArt /></div>
              </motion.section>

              {/* TÌM LỚP */}
              <motion.section
                ref={scannerRef}
                className="card"
                style={{ position: 'relative', zIndex: dropdownOpen ? 5 : 'auto' }}
                {...fadeUp(0.05)}
              >
                <div className="card-head">
                  <div>
                    <h2 className="card-title">Tìm lớp học phần</h2>
                    <p className="card-sub">Chọn đợt, loại đăng ký và môn học, rồi quét để xem lịch và sĩ số từng lớp.</p>
                  </div>
                </div>

                <div className="stack">
                  <div className="grid-2">
                    <label className="field">
                      <span className="label">Đợt học</span>
                      <select
                        className="select"
                        value={selectedDot}
                        onChange={(e) => setSelectedDot(e.target.value)}
                        disabled={!configExists}
                      >
                        {dots.length > 0 ? (
                          dots.map(d => (
                            <option key={d.id || d.idDot} value={d.id || d.idDot}>
                              {d.tenHocKy || d.tenDot || d.id || d.idDot}
                            </option>
                          ))
                        ) : (
                          <option value={config?.id_dot || ''}>{config?.id_dot || '—'}</option>
                        )}
                      </select>
                    </label>
                    <label className="field">
                      <span className="label">Loại đăng ký</span>
                      <select className="select" value={regType} onChange={(e) => setRegType(e.target.value)}>
                        <option value="new">Học mới</option>
                        <option value="repeat">Học lại</option>
                        <option value="improve">Học cải thiện</option>
                        <option value="cond_new">Môn điều kiện (học mới)</option>
                        <option value="cond_repeat">Môn điều kiện (học lại)</option>
                      </select>
                    </label>
                  </div>

                  <div className="field combo">
                    <span className="label">Môn học</span>
                    <button
                      type="button"
                      className="combo-trigger"
                      onClick={() => setDropdownOpen(!dropdownOpen)}
                      aria-expanded={dropdownOpen}
                    >
                      <span className={selectedCourse ? '' : 'placeholder'}>
                        {selectedCourse
                          ? (selectedCourseObj ? courseLabel(selectedCourseObj) : `[${selectedCourse}]`)
                          : 'Chọn môn học'}
                      </span>
                      <ChevronDown size={16} />
                    </button>
                    {coursesError && !dropdownOpen && <div className="field-note error">{coursesError}</div>}

                    <AnimatePresence>
                    {dropdownOpen && (
                      <motion.div className="menu" {...menuAnim}>
                        <div className="menu-search">
                          <Search size={15} />
                          <input
                            type="text"
                            value={courseSearch}
                            onChange={(e) => setCourseSearch(e.target.value)}
                            placeholder="Tìm theo mã hoặc tên môn…"
                            autoFocus
                          />
                        </div>
                        <div className="menu-list">
                          {coursesLoading ? (
                            <div className="menu-empty">Đang tải danh sách môn…</div>
                          ) : isTokenExpired ? (
                            <div className="menu-empty error">Phiên đăng nhập hết hạn. Hãy đăng nhập lại.</div>
                          ) : coursesError && courses.length === 0 ? (
                            <div className="menu-empty error">{coursesError}</div>
                          ) : filteredCourses.length > 0 ? (
                            filteredCourses.map((c, index) => (
                              <button
                                type="button"
                                key={`${c.maHocPhan}-${index}`}
                                className={`menu-item ${selectedCourse === c.maHocPhan ? 'selected' : ''}`}
                                onClick={() => {
                                  setSelectedCourse(c.maHocPhan);
                                  setDropdownOpen(false);
                                }}
                              >
                                <span>{courseLabel(c)}</span>
                                {c.isBatBuoc && <span className="tag">Bắt buộc</span>}
                              </button>
                            ))
                          ) : (
                            <div className="menu-empty">Không tìm thấy môn nào</div>
                          )}
                        </div>
                      </motion.div>
                    )}
                    </AnimatePresence>
                  </div>

                  <div className="grid-2">
                    <label className="field">
                      <span className="label">Thứ</span>
                      <select className="select" value={filterThu} onChange={(e) => setFilterThu(e.target.value)}>
                        <option value="Tất cả">Tất cả các ngày</option>
                        <option value="Thứ 2">Thứ Hai</option>
                        <option value="Thứ 3">Thứ Ba</option>
                        <option value="Thứ 4">Thứ Tư</option>
                        <option value="Thứ 5">Thứ Năm</option>
                        <option value="Thứ 6">Thứ Sáu</option>
                        <option value="Thứ 7">Thứ Bảy</option>
                        <option value="Chủ nhật">Chủ nhật</option>
                      </select>
                    </label>
                    <label className="field">
                      <span className="label">Ca học</span>
                      <select className="select" value={filterCa} onChange={(e) => setFilterCa(e.target.value)}>
                        <option value="Tất cả">Tất cả các ca</option>
                        <option value="Ca 1 (Tiết 1-3)">Ca 1 (tiết 1–3)</option>
                        <option value="Ca 2 (Tiết 4-6)">Ca 2 (tiết 4–6)</option>
                        <option value="Ca 3 (Tiết 7-9)">Ca 3 (tiết 7–9)</option>
                        <option value="Ca 4 (Tiết 10-12)">Ca 4 (tiết 10–12)</option>
                        <option value="Ca 5 (Tiết 13-15)">Ca 5 (tiết 13–15)</option>
                      </select>
                    </label>
                  </div>

                  <button
                    type="button"
                    className="btn btn-dark btn-block"
                    onClick={handleScanClasses}
                    disabled={isScanning || !configExists}
                  >
                    {isScanning ? <RefreshCw size={16} className="spin" /> : <Search size={16} />}
                    {isScanning ? 'Đang quét chi tiết lớp…' : 'Quét chi tiết lớp học phần'}
                  </button>
                </div>
              </motion.section>

              {/* KẾT QUẢ QUÉT */}
              <motion.section ref={resultsRef} className="card" {...fadeUp(0.1)}>
                <div className="card-head">
                  <div>
                    <h2 className="card-title">Kết quả quét</h2>
                    <p className="card-sub">
                      {classes.length > 0
                        ? `${visibleClasses.length} lớp${hiddenConflicts > 0 ? `, đang ẩn ${hiddenConflicts} lớp trùng lịch` : ''}. Chọn tối đa 1 lớp cho mỗi môn.`
                        : 'Chọn môn ở trên rồi bấm quét để xem danh sách lớp.'}
                    </p>
                  </div>
                  <div className="head-actions">
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={hideConflicting}
                        onChange={(e) => setHideConflicting(e.target.checked)}
                      />
                      Ẩn lớp trùng lịch
                    </label>
                    {checkedClasses.length > 0 && (
                      <button type="button" className="btn btn-light btn-sm" onClick={handleClearSelection}>
                        <Trash2 size={13} />
                        Bỏ chọn ({checkedClasses.length})
                      </button>
                    )}
                  </div>
                </div>

                {isScanning ? (
                  <div className="class-grid" aria-busy="true" aria-label="Đang quét lớp">
                    {[0, 1, 2, 3, 4, 5].map(i => <div key={i} className="skeleton" />)}
                  </div>
                ) : visibleClasses.length > 0 ? (
                  <motion.div className="class-grid" layoutScroll>
                    <AnimatePresence mode="popLayout">
                    {visibleClasses.map((cls, idx) => {
                      const isSelected = checkedClasses.some(c => c.id === cls.id);
                      const isFull = String(cls.status || '').includes('FULL');
                      return (
                        <motion.button
                          type="button"
                          key={cls.id}
                          layout
                          initial={{ opacity: 0, y: 12 }}
                          animate={{
                            opacity: cls.is_conflicting && !isSelected ? 0.55 : 1,
                            y: 0,
                            transition: { duration: 0.35, ease: easeOut, delay: Math.min(idx, 12) * 0.03 }
                          }}
                          exit={{ opacity: 0, scale: 0.94, pointerEvents: 'none', transition: { duration: 0.18 } }}
                          whileHover={{ y: -3, transition: { duration: 0.18 } }}
                          whileTap={{ scale: 0.98, transition: { duration: 0.1 } }}
                          transition={softSpring}
                          className={`class-card ${isSelected ? 'selected' : ''} ${cls.is_conflicting ? 'conflict' : ''}`}
                          onClick={() => handleToggleClass(cls)}
                          aria-pressed={isSelected}
                        >
                          <span className="class-top">
                            <span className="class-code">{cls.maLopHocPhan}</span>
                            <span className="class-tick"><TickMark on={isSelected} /></span>
                          </span>
                          <span className="class-name">{cls.tenMonHoc}</span>
                          <span className="class-sched">{cls.schedule}</span>
                          {cls.is_conflicting && (
                            <span className="conflict-note">Trùng lịch: {cls.conflict_with}</span>
                          )}
                          <span className="class-foot">
                            <span className={`meter ${isFull ? 'full' : ''}`}>
                              <motion.span
                                initial={{ scaleX: 0 }}
                                animate={{ scaleX: Math.min(Number(cls.capacity_percent) || 0, 100) / 100 }}
                                transition={{ duration: 0.8, ease: easeOut, delay: 0.15 + Math.min(idx, 12) * 0.03 }}
                              />
                            </span>
                            <span className={`pct ${isFull ? 'full' : ''}`}>
                              {cls.capacity_percent}%{isFull ? ' · đầy' : ''}
                            </span>
                          </span>
                        </motion.button>
                      );
                    })}
                    </AnimatePresence>
                  </motion.div>
                ) : classes.length > 0 ? (
                  <div className="empty">
                    <Layers size={26} />
                    Tất cả lớp đều trùng lịch với lớp bạn đã đăng ký. Bỏ tick “Ẩn lớp trùng lịch” để xem.
                  </div>
                ) : (
                  <div className="empty">
                    <Layers size={26} />
                    Chưa có lớp nào. Chọn môn học ở trên rồi bấm quét.
                  </div>
                )}

                <AnimatePresence>
                {checkedClasses.length > 0 && (
                  <motion.div
                    className="chips-box"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.22, ease: easeOut }}
                  >
                    <div className="chips-title">Đã chọn để spam ({checkedClasses.length})</div>
                    <div className="chips">
                      <AnimatePresence initial={false}>
                      {checkedClasses.map(c => (
                        <motion.span
                          key={c.id}
                          className="chip"
                          layout
                          initial={{ opacity: 0, scale: 0.85 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.85 }}
                          transition={spring}
                        >
                          <span>{c.maLopHocPhan} · {c.tenMonHoc}</span>
                          <button
                            type="button"
                            aria-label={`Bỏ chọn ${c.tenMonHoc}`}
                            onClick={() => setCheckedClasses(checkedClasses.filter(x => x.id !== c.id))}
                          >
                            <X size={13} />
                          </button>
                        </motion.span>
                      ))}
                      </AnimatePresence>
                    </div>
                  </motion.div>
                )}
                </AnimatePresence>
              </motion.section>

              {/* TRÌNH ĐIỀU KHIỂN SPAM */}
              <motion.section ref={consoleRef} className="card" {...fadeUp(0.15)}>
                <div className="card-head">
                  <div>
                    <h2 className="card-title">Trình điều khiển spam</h2>
                    <p className="card-sub">
                      {spamMode === 'turbo'
                        ? 'Turbo: 3 luồng cho mỗi lớp, tối đa 12 request cùng lúc.'
                        : 'Thường: mỗi lớp gửi khoảng 1 request mỗi giây.'}
                    </p>
                  </div>
                  <div className="seg" role="group" aria-label="Chế độ tốc độ">
                    <button
                      type="button"
                      className={spamMode === 'normal' ? 'on' : ''}
                      onClick={() => setSpamMode('normal')}
                      disabled={isSpamming}
                      aria-pressed={spamMode === 'normal'}
                    >
                      Thường
                    </button>
                    <button
                      type="button"
                      className={spamMode === 'turbo' ? 'on' : ''}
                      onClick={() => setSpamMode('turbo')}
                      disabled={isSpamming}
                      aria-pressed={spamMode === 'turbo'}
                    >
                      Turbo
                    </button>
                  </div>
                </div>

                <div className="stat-row">
                  <div className="mini-stat">
                    <div className="k">Đã gửi</div>
                    <div className="v"><AnimatedNumber value={spamStats.total_requests} /></div>
                  </div>
                  <div className="mini-stat">
                    <div className="k">Thành công</div>
                    <div className="v green"><AnimatedNumber value={spamStats.success_count} /></div>
                    {burstKey > 0 && <SuccessBurst key={burstKey} />}
                  </div>
                  <div className="mini-stat">
                    <div className="k">Chưa được</div>
                    <div className="v red"><AnimatedNumber value={spamStats.error_count} /></div>
                  </div>
                </div>
                {(spamStats.timeouts > 0 || spamStats.relogins > 0) && (
                  <p className="console-meta">
                    Timeout: {spamStats.timeouts || 0} · Tự đăng nhập lại: {spamStats.relogins || 0}
                  </p>
                )}

                <div className="terminal-wrap">
                <AnimatePresence>
                  {isSpamming && (
                    <motion.span
                      className="run-bar"
                      aria-hidden="true"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    />
                  )}
                </AnimatePresence>
                <div className="terminal" ref={terminalEndRef} role="log" aria-live="polite">
                  {logs.length > 0 ? (
                    <AnimatePresence initial={false}>
                      {keyedLogs.map(({ key, text }) => (
                        <motion.div
                          key={key}
                          className={`t-line ${logTone(text)}`}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.25, ease: 'easeOut' }}
                        >
                          {text}
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  ) : (
                    <div className="t-empty">Nhật ký trống. Bấm chạy spam để bắt đầu.</div>
                  )}
                  {isSpamming && <div className="t-live">➤ Đang gửi liên tục…</div>}
                </div>
                </div>

                <AnimatePresence mode="wait" initial={false}>
                {!isSpamming ? (
                  <motion.button
                    key="start"
                    type="button"
                    className="btn btn-dark btn-lg btn-block"
                    onClick={handleStartSpam}
                    disabled={checkedClasses.length === 0}
                    whileTap={{ scale: 0.985 }}
                    {...swapAnim}
                  >
                    <Play size={17} />
                    Chạy spam đăng ký ({checkedClasses.length} lớp)
                  </motion.button>
                ) : (
                  <motion.button
                    key="stop"
                    type="button"
                    className="btn btn-danger btn-lg btn-block"
                    onClick={handleStopSpam}
                    whileTap={{ scale: 0.985 }}
                    {...swapAnim}
                  >
                    <Square size={15} />
                    Dừng spam
                  </motion.button>
                )}
                </AnimatePresence>
              </motion.section>
            </div>

            {/* ---------------------------------------------------- RIGHT PANEL */}
            <motion.aside className="side-panel" {...fadeUp(0.08)}>
              <motion.button type="button" className="stat-card" onClick={() => scrollToRef(accountRef)} {...fadeUp(0.12)} whileHover={{ y: -2, transition: { duration: 0.15 } }} whileTap={{ scale: 0.98, transition: { duration: 0.1 } }}>
                <span className={`stat-icon ${isTokenExpired || !configExists ? 'tone-red' : 'tone-orange'}`}>
                  <KeyRound size={18} />
                </span>
                <span className="stat-body">
                  <span className="stat-label">Phiên đăng nhập</span>
                  <span className="stat-value">{!configExists ? 'Chưa có' : isTokenExpired ? 'Hết hạn' : 'Còn hạn'}</span>
                  <span className="stat-sub">{tokenExpiresAt ? `đến ${formatExpiry(tokenExpiresAt)}` : 'Chưa rõ hạn'}</span>
                </span>
                <ChevronRight size={18} className="stat-chev" />
              </motion.button>

              <motion.button type="button" className="stat-card" onClick={() => scrollToRef(resultsRef)} {...fadeUp(0.18)} whileHover={{ y: -2, transition: { duration: 0.15 } }} whileTap={{ scale: 0.98, transition: { duration: 0.1 } }}>
                <span className="stat-icon tone-lavender"><ListChecks size={18} /></span>
                <span className="stat-body">
                  <span className="stat-label">Lớp đã chọn để spam</span>
                  <span className="stat-value"><AnimatedNumber value={checkedClasses.length} /></span>
                  <span className="stat-sub">
                    {checkedClasses.length > 0 ? checkedClasses.map(c => c.maLopHocPhan).join(', ') : 'Chưa chọn lớp nào'}
                  </span>
                </span>
                <ChevronRight size={18} className="stat-chev" />
              </motion.button>

              <motion.button type="button" className="stat-card" onClick={() => scrollToRef(registeredRef)} {...fadeUp(0.24)} whileHover={{ y: -2, transition: { duration: 0.15 } }} whileTap={{ scale: 0.98, transition: { duration: 0.1 } }}>
                <span className="stat-icon tone-green"><BadgeCheck size={18} /></span>
                <span className="stat-body">
                  <span className="stat-label">Đã đăng ký trong đợt</span>
                  <span className="stat-value"><AnimatedNumber value={registeredClasses.length} /></span>
                  <span className="stat-sub">{totalCredits} tín chỉ</span>
                </span>
                <ChevronRight size={18} className="stat-chev" />
              </motion.button>

              <div className="side-head" ref={registeredRef}>
                <span className="side-title">Học phần đã đăng ký</span>
                <button
                  type="button"
                  className="link-btn"
                  onClick={fetchRegisteredClasses}
                  disabled={registeredLoading || !configExists}
                >
                  <RefreshCw size={13} className={registeredLoading ? 'spin' : ''} />
                  Tải lại
                </button>
              </div>

              {registeredLoading ? (
                <div className="side-empty">Đang tải danh sách…</div>
              ) : registeredClasses.length > 0 ? (
                <div className="reg-list">
                  <AnimatePresence initial={false}>
                  {registeredClasses.map((rc, idx) => {
                    const rcId = rc.id || rc.idDangKy;
                    const rcName = rc.tenLopHocPhan || rc.tenHocPhan || rc.tenMonHoc || 'Học phần';
                    const rcCode = rc.maLopHocPhan || rc.maHocPhan || '';
                    const rcCredits = rc.soTinChi || 0;
                    return (
                      <motion.div
                        key={rcId || idx}
                        className="reg-item"
                        layout
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, x: 24 }}
                        transition={softSpring}
                      >
                        <div className="reg-text">
                          <span className="reg-name" title={rcName}>{rcName}</span>
                          <span className="reg-meta">{rcCode} · {rcCredits} TC</span>
                          {rc.scheduleText && <span className="reg-sched" title={rc.scheduleText}>{rc.scheduleText}</span>}
                        </div>
                        <button
                          type="button"
                          className="btn btn-danger-soft btn-sm"
                          onClick={() => handleDeregisterClass(rcId, rcName, rc.isConditional)}
                        >
                          Hủy
                        </button>
                      </motion.div>
                    );
                  })}
                  </AnimatePresence>
                </div>
              ) : (
                <div className="side-empty">Chưa có môn nào trong đợt này.</div>
              )}

              <div className="account" ref={accountRef}>
                <div className="account-title">Tài khoản cổng trường</div>
                {configExists ? (
                  <>
                    <div className="kv">
                      <span className="k">MSSV</span>
                      <span className="v">{config?.username || 'Lấy từ Chrome'}</span>
                    </div>
                    <div className="kv">
                      <span className="k">Token</span>
                      <span className="v">
                        <span className="mask">{showToken ? config?.token : '••••••••••••'}</span>
                        <button
                          type="button"
                          className="icon-btn"
                          onClick={() => setShowToken(!showToken)}
                          aria-label={showToken ? 'Ẩn token' : 'Hiện token'}
                        >
                          {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </span>
                    </div>
                    <div className="kv">
                      <span className="k">Cookie</span>
                      <span className="v">
                        <span className="mask">{showCookie ? config?.cookie : '••••••••••••'}</span>
                        <button
                          type="button"
                          className="icon-btn"
                          onClick={() => setShowCookie(!showCookie)}
                          aria-label={showCookie ? 'Ẩn cookie' : 'Hiện cookie'}
                        >
                          {showCookie ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </span>
                    </div>
                    <div className="kv">
                      <span className="k">Hạn token</span>
                      <span className={`v ${isTokenExpired ? 'bad' : ''}`}>
                        {isTokenExpired ? 'Hết hạn' : tokenExpiresAt ? formatExpiry(tokenExpiresAt) : 'Không rõ'}
                      </span>
                    </div>
                    <div className="kv">
                      <span className="k">Cổng trường</span>
                      <span className={`v ${tokenOk === false ? 'bad' : tokenOk ? 'ok' : ''}`}>{portalCheckText}</span>
                    </div>
                  </>
                ) : (
                  <div className="notice notice-neutral">
                    <Info size={15} />
                    <span>Chưa đăng nhập. Đăng nhập để tool tự nạp token và giữ phiên.</span>
                  </div>
                )}

                <div className="divider" />

                <div className="account-actions">
                  {!configExists && (
                    <button type="button" className="btn btn-dark btn-block" onClick={() => setShowLoginOverlay(true)}>
                      Đăng nhập
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-light btn-block"
                    onClick={handleStartAutoConfig}
                    disabled={isAutoRunning}
                  >
                    <RefreshCw size={14} className={isAutoRunning ? 'spin' : ''} />
                    {isAutoRunning ? 'Đang chờ bạn đăng nhập trong Chrome…' : 'Lấy token qua Chrome'}
                  </button>
                  <button type="button" className="btn btn-light btn-block" onClick={() => setShowManual(true)}>
                    <Settings size={14} />
                    Nhập cấu hình thủ công
                  </button>
                  {renderAutoConfigStatus()}
                  {configExists && (
                    <button type="button" className="btn btn-danger-soft btn-block" onClick={handleLogout}>
                      <LogOut size={14} />
                      Đăng xuất
                    </button>
                  )}
                </div>
              </div>
            </motion.aside>
          </motion.div>
        )}

        {/* =============================================== TAB: ĐIỂM RÈN LUYỆN */}
        {activeTab === 'drl' && (
          <motion.section key="drl" className="card" {...tabAnim}>
            <div className="card-head">
              <div>
                <h2 className="card-title">Điểm rèn luyện: chia sẻ thông báo UTH</h2>
                <p className="card-sub">
                  Chia sẻ thông báo, sự kiện của trường lên Facebook cá nhân để tích điểm rèn luyện.
                  Ảnh chụp màn hình sau khi chia sẻ được lưu vào thư mục <strong>DRL</strong> làm minh chứng.
                </p>
              </div>
              <button
                type="button"
                className="link-btn"
                onClick={fetchAnnouncements}
                disabled={announcementsLoading || !configExists}
              >
                <RefreshCw size={13} className={announcementsLoading ? 'spin' : ''} />
                Tải lại
              </button>
            </div>

            {(!config?.fb_username || editFbLogin) ? (
              <form className="stack narrow" onSubmit={handleSaveFacebookCredentials}>
                <div>
                  <h3 className="card-title">Kết nối Facebook</h3>
                  <p className="card-sub">Bot dùng tài khoản này để tự đăng nhập và chia sẻ bài lên dòng thời gian của bạn.</p>
                </div>
                <label className="field">
                  <span className="label">Email hoặc số điện thoại Facebook</span>
                  <input
                    type="text"
                    className="input"
                    value={fbUsername}
                    onChange={(e) => setFbUsername(e.target.value)}
                    placeholder="Nhập email hoặc số điện thoại"
                    autoComplete="username"
                    required
                  />
                </label>
                <div className="field">
                  <label className="label" htmlFor="fb-pass">Mật khẩu Facebook</label>
                  <div className="input-wrap">
                    <input
                      id="fb-pass"
                      type={showFbPassword ? 'text' : 'password'}
                      className="input"
                      value={fbPassword}
                      onChange={(e) => setFbPassword(e.target.value)}
                      placeholder="Nhập mật khẩu Facebook"
                      autoComplete="current-password"
                      required
                    />
                    <button
                      type="button"
                      className="input-eye"
                      onClick={() => setShowFbPassword(!showFbPassword)}
                      aria-label={showFbPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                    >
                      {showFbPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
                <div className="btn-row">
                  {config?.fb_username && (
                    <button type="button" className="btn btn-light" onClick={() => setEditFbLogin(false)}>Hủy</button>
                  )}
                  <button type="submit" className="btn btn-dark">Lưu tài khoản</button>
                </div>
              </form>
            ) : (
              <>
                <div className="linked-row">
                  <span><span className="muted">Đang liên kết Facebook: </span><strong>{config?.fb_username}</strong></span>
                  <button
                    type="button"
                    className="btn btn-light btn-sm"
                    onClick={() => {
                      setFbUsername(config?.fb_username || '');
                      setFbPassword(config?.fb_password || '');
                      setEditFbLogin(true);
                    }}
                  >
                    Đổi tài khoản
                  </button>
                </div>

                {announcementsLoading ? (
                  <div className="empty">
                    <RefreshCw size={22} className="spin" />
                    Đang tải thông báo từ cổng trường…
                  </div>
                ) : announcements.length > 0 ? (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th style={{ width: '9%' }}>ID</th>
                          <th>Thông báo</th>
                          <th style={{ width: '15%' }}>Trạng thái</th>
                          <th style={{ width: '24%', textAlign: 'right' }}>Thao tác</th>
                        </tr>
                      </thead>
                      <tbody>
                        {announcements.map((item, idx) => (
                          <tr key={idx}>
                            <td className="muted mono">#{item.id}</td>
                            <td>
                              <div className="cell-title">{item.title}</div>
                              <a className="text-link" href={item.link} target="_blank" rel="noreferrer">
                                <ExternalLink size={12} />
                                Mở trên cổng trường
                              </a>
                            </td>
                            <td>
                              {item.status === 'shared' ? (
                                <span className="pill pill-green"><Check size={12} />Đã chia sẻ</span>
                              ) : (
                                <span className="pill pill-grey">Chưa chia sẻ</span>
                              )}
                            </td>
                            <td>
                              <div className="cell-actions">
                                <button
                                  type="button"
                                  className="btn btn-dark btn-sm"
                                  onClick={() => handleShareFacebook(item.id, item.title)}
                                  disabled={shareStatus === 'running'}
                                >
                                  <Share2 size={13} />
                                  Chia sẻ
                                </button>
                                {item.status === 'shared' && item.screenshot && (
                                  <a className="btn btn-light btn-sm" href={item.screenshot} target="_blank" rel="noreferrer">
                                    <ImageIcon size={13} />
                                    Minh chứng
                                  </a>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty">
                    <Share2 size={26} />
                    Không tìm thấy thông báo nào trên cổng trường.
                  </div>
                )}
              </>
            )}
          </motion.section>
        )}
        </AnimatePresence>
      </main>

      {/* ---------------------------------------------------- MANUAL CONFIG MODAL */}
      <AnimatePresence>
        {showManual && (
          <motion.div
            className="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(e) => { if (e.target === e.currentTarget) setShowManual(false); }}
          >
            <motion.form
              className="modal modal-wide"
              onSubmit={handleSaveManualConfig}
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8 }}
            >
              <div className="modal-head">
                <div className="modal-icon tone-orange"><Settings size={20} /></div>
                <div>
                  <h3>Cấu hình thủ công</h3>
                  <p className="modal-sub">Dán token và cookie lấy từ trình duyệt khi không đăng nhập được bằng mật khẩu.</p>
                </div>
              </div>

              <div className="stack">
                <label className="field">
                  <span className="label">Token Bearer</span>
                  <input className="input" type="text" value={manToken} onChange={(e) => setManToken(e.target.value)} placeholder="Không cần chữ Bearer" required />
                </label>
                <label className="field">
                  <span className="label">Cookie</span>
                  <input className="input" type="text" value={manCookie} onChange={(e) => setManCookie(e.target.value)} placeholder="Chuỗi cookie của portal" required />
                </label>
                <div className="grid-2">
                  <label className="field">
                    <span className="label">MSSV (không bắt buộc)</span>
                    <input className="input" type="text" value={username} onChange={(e) => setUsername(e.target.value)} />
                  </label>
                  <label className="field">
                    <span className="label">Mật khẩu portal (không bắt buộc)</span>
                    <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
                  </label>
                </div>
                <div className="grid-2">
                  <label className="field">
                    <span className="label">Tài khoản Facebook</span>
                    <input className="input" type="text" value={fbUsername} onChange={(e) => setFbUsername(e.target.value)} placeholder="Để tự đăng nhập Facebook" />
                  </label>
                  <div className="field">
                    <label className="label" htmlFor="man-fb-pass">Mật khẩu Facebook</label>
                    <div className="input-wrap">
                      <input
                        id="man-fb-pass"
                        className="input"
                        type={showFbPassword ? 'text' : 'password'}
                        value={fbPassword}
                        onChange={(e) => setFbPassword(e.target.value)}
                      />
                      <button
                        type="button"
                        className="input-eye"
                        onClick={() => setShowFbPassword(!showFbPassword)}
                        aria-label={showFbPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                      >
                        {showFbPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="grid-2">
                  <label className="field">
                    <span className="label">ID đợt học</span>
                    <input className="input" type="text" value={manIdDot} onChange={(e) => setManIdDot(e.target.value)} placeholder="76" required />
                  </label>
                  <label className="field">
                    <span className="label">User agent</span>
                    <input className="input" type="text" value={manUserAgent} onChange={(e) => setManUserAgent(e.target.value)} required />
                  </label>
                </div>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn btn-light" onClick={() => setShowManual(false)}>Hủy</button>
                <button type="submit" className="btn btn-dark">Lưu cấu hình</button>
              </div>
            </motion.form>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ---------------------------------------------------- FACEBOOK SHARE PROGRESS */}
      <AnimatePresence>
      {showShareModal && (
        <motion.div className="backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.div
            className="modal modal-wide"
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={softSpring}
          >
            <div className="modal-head">
              <div className="modal-icon tone-lavender"><Share2 size={20} /></div>
              <div>
                <h3>Đang chia sẻ lên Facebook</h3>
                <p className="modal-sub">Trình duyệt tự động (Selenium)</p>
              </div>
            </div>

            <div className="share-stage">
              {shareStatus === 'running' && <div className="ring" />}
              {shareStatus === 'success' && <CheckCircle2 size={30} className="ico-ok" />}
              {shareStatus === 'error' && <XCircle size={30} className="ico-err" />}
              <div>{shareStep || 'Đang chuẩn bị…'}</div>
              {shareError && <div className="notice notice-err">Lỗi: {shareError}</div>}
            </div>

            {shareStep.includes('đăng nhập tài khoản Facebook') && (
              <div className="notice notice-info mb">
                <Info size={15} />
                <span>
                  <strong>Lần đầu dùng:</strong> mở cửa sổ Chrome vừa hiện trên thanh Taskbar/Dock, đăng nhập Facebook.
                  Đăng nhập xong, bot tự phát hiện và làm nốt các bước còn lại.
                </span>
              </div>
            )}

            <div className="modal-actions end">
              <button
                type="button"
                className="btn btn-light"
                onClick={() => setShowShareModal(false)}
                disabled={shareStatus === 'running'}
              >
                Đóng
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>

      {/* ---------------------------------------------------- LOGIN SCREEN */}
      <AnimatePresence>
      {showLoginOverlay && (
        <motion.div
          className="login-screen"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, pointerEvents: 'none', transition: { duration: 0.35, ease: 'easeOut' } }}
        >
          <motion.div
            className="login-card"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.98 }}
            transition={softSpring}
          >
            <div className="login-brand">
              <motion.div
                className="login-logo"
                initial={{ scale: 0, rotate: -40 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ ...spring, delay: 0.15 }}
              >
                <GraduationCap size={24} />
              </motion.div>
              <div>
                <h1>SmartEnroll UTH</h1>
                <p className="login-sub">Đăng ký học phần tự động cho sinh viên UTH</p>
              </div>
            </div>

            <form className="stack" onSubmit={handleLogin}>
              <label className="field">
                <span className="label">Mã số sinh viên</span>
                <input
                  type="text"
                  className="input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Nhập MSSV"
                  autoComplete="username"
                  required
                />
              </label>

              <div className="field">
                <label className="label" htmlFor="login-pass">Mật khẩu cổng UTH</label>
                <div className="input-wrap">
                  <input
                    id="login-pass"
                    type={showPassword ? 'text' : 'password'}
                    className="input"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Nhập mật khẩu"
                    autoComplete="current-password"
                    required
                  />
                  <button
                    type="button"
                    className="input-eye"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {configExists && tokenStillValid && !loginLoading && (
                <div className="notice notice-ok">
                  <CheckCircle2 size={15} />
                  <span>
                    Phiên đã lưu còn hạn đến <strong>{formatExpiry(tokenExpiresAt)}</strong>.
                    Không cần đăng nhập lại, bấm <strong>Vào thẳng Dashboard</strong>.
                  </span>
                </div>
              )}

              {renderLoginProgress()}

              {loginError && (
                <div className="notice notice-err">
                  <AlertCircle size={15} />
                  <span>{loginError}</span>
                </div>
              )}

              <label className="check align-top">
                <input
                  type="checkbox"
                  checked={autoRetryLogin}
                  disabled={loginLoading}
                  onChange={() => setAutoRetryLogin(!autoRetryLogin)}
                />
                <span>Tự động thử lại đến khi vào được (khi cổng trường nghẽn)</span>
              </label>

              <button
                type="submit"
                className={`btn btn-lg btn-block ${loginLoading ? 'btn-danger' : (configExists && tokenStillValid ? 'btn-light' : 'btn-dark')}`}
              >
                {loginLoading ? 'Đang đăng nhập… bấm để dừng' : 'Đăng nhập'}
              </button>

              {configExists && (
                <button
                  type="button"
                  className={`btn btn-lg btn-block ${tokenStillValid && !loginLoading ? 'btn-dark' : 'btn-light'}`}
                  onClick={() => setShowLoginOverlay(false)}
                >
                  Vào thẳng Dashboard
                </button>
              )}

              <div className="login-alt">
                <button type="button" className="link-btn" onClick={handleStartAutoConfig} disabled={isAutoRunning}>
                  {isAutoRunning ? 'Đang chờ bạn đăng nhập trong Chrome…' : 'Không đăng nhập được? Lấy token qua Chrome'}
                </button>
              </div>
              {renderAutoConfigStatus()}
            </form>
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>

      {/* ---------------------------------------------------- ALERT / CONFIRM DIALOG */}
      <AnimatePresence>
        {customDialog && (
          <motion.div
            className="backdrop dialog-layer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="modal modal-center"
              role="alertdialog"
              aria-modal="true"
              initial={{ opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 6 }}
              transition={spring}
            >
              <div className={`modal-icon ${customDialog.type === 'confirm' ? 'tone-lavender' : (customDialog.status === 'success' ? 'tone-green' : 'tone-red')}`}>
                {customDialog.type === 'confirm'
                  ? <HelpCircle size={22} />
                  : (customDialog.status === 'success' ? <CheckCircle2 size={22} /> : <XCircle size={22} />)}
              </div>
              <h3>{customDialog.type === 'confirm' ? 'Xác nhận' : 'Thông báo'}</h3>
              <p className="modal-text">{customDialog.message}</p>
              <div className="modal-actions">
                {customDialog.type === 'confirm' && (
                  <button
                    type="button"
                    className="btn btn-light"
                    onClick={() => {
                      customDialog.resolve(false);
                      setCustomDialog(null);
                    }}
                  >
                    Hủy
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-dark"
                  autoFocus
                  onClick={() => {
                    customDialog.resolve(true);
                    setCustomDialog(null);
                  }}
                >
                  {customDialog.type === 'confirm' ? 'Đồng ý' : 'Đã hiểu'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ---------------------------------------------------- SUCCESS TOAST */}
      <AnimatePresence>
        {toast && (
          <motion.div
            key={toast.id}
            className="toast"
            role="status"
            initial={{ opacity: 0, y: 28, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 14, scale: 0.97 }}
            transition={spring}
          >
            <span className="toast-icon"><BadgeCheck size={18} /></span>
            {toast.text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
    </MotionConfig>
  );
}
