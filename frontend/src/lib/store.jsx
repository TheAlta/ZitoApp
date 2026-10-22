// App-wide state: session, routing, toasts and sign-in. Pages add their own data hooks.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, get, post } from "./api.js";
import { clearCache } from "./cache.js";
import { fa, normPhone } from "./format.js";
import { fromPath, toPath } from "./routes.js";

export const PROFILE_KEYS = [
  "work_or_study_field",
  "education_level",
  "learning_goal_interests",
  "ai_familiarity_level",
  "daily_learning_time_text",
  "preferred_career_path",
  "referral_source",
];
export const answered = (profile, key) =>
  !!profile?.[key] || (key === "daily_learning_time_text" && profile?.daily_learning_minutes != null);
export const profileComplete = (profile) => !!profile && (profile.completed || PROFILE_KEYS.every((key) => answered(profile, key)));

const StoreContext = createContext(null);

function useSessionState() {
  // role: "loading" | "guest" | "learner" | "admin"
  const [session, setSession] = useState({ role: "loading" });
  const [route, setRoute] = useState(() => fromPath(location.pathname));
  const [toasts, setToasts] = useState([]);
  const [otp, setOtp] = useState(null);

  const go = useCallback((next, { replace = false } = {}) => {
    const path = toPath(next);
    if (path !== location.pathname + location.hash) history[replace ? "replaceState" : "pushState"](null, "", path);
    setRoute(next);
    try {
      window.scrollTo({ top: 0 });
      document.querySelector(".app-main")?.scrollTo({ top: 0 });
    } catch {
      /* scrolling is cosmetic */
    }
  }, []);

  useEffect(() => {
    const onPop = () => setRoute(fromPath(location.pathname));
    addEventListener("popstate", onPop);
    return () => removeEventListener("popstate", onPop);
  }, []);

  const toast = useCallback((text, tone = "ok") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((list) => [...list.slice(-2), { id, text, tone }]);
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), 2600);
  }, []);

  const loadLearner = useCallback(async () => {
    const [me, profile] = await Promise.all([get("/api/me"), get("/api/me/profile")]);
    setSession({ role: "learner", me, profile });
    return { me, profile };
  }, []);

  const refreshSession = useCallback(async () => {
    const wantsAdmin = location.pathname.startsWith("/admin");
    try {
      if (wantsAdmin) {
        const admin = await get("/api/admin/me");
        setSession({ role: "admin", admin });
        return;
      }
      await loadLearner();
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) setSession({ role: "guest" });
      else setSession({ role: "guest", error: error.message });
    }
  }, [loadLearner]);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const setProfile = useCallback((profile) => setSession((s) => ({ ...s, profile })), []);

  const requestOtp = useCallback(
    async (rawPhone, mode, name) => {
      const phone = normPhone(rawPhone);
      if (!phone) return { ok: false, field: "phone", msg: "شماره‌ی موبایل باید ۱۱ رقم باشد و با ۰۹ شروع شود؛ مثل ۰۹۱۲۱۲۳۴۵۶۷." };
      if (mode === "register" && (!name || name.trim().length < 2))
        return { ok: false, field: "name", msg: "اسمت را حداقل با دو حرف بنویس تا روی گواهی بیاید." };
      if (otp && otp.phone === phone && Date.now() < otp.resendAt)
        return { ok: false, field: "wait", msg: `برای ارسال دوباره ${fa(Math.ceil((otp.resendAt - Date.now()) / 1000))} ثانیه صبر کن.` };
      try {
        const data = await post("/api/auth/otp/request", { phone });
        const now = Date.now();
        setOtp({
          phone: data.phone || phone,
          mode,
          name: name?.trim() || "",
          code: data.mock_code || null,
          sentAt: now,
          resendAt: now + (data.resend_after_seconds ?? 60) * 1000,
          expiresAt: now + (data.expires_in_seconds ?? 300) * 1000,
          requiresName: !!data.requires_display_name && !name?.trim(),
        });
        return { ok: true };
      } catch (error) {
        if (error.status === 429) {
          const wait = error.detail?.retry_after_seconds;
          return { ok: false, field: "wait", msg: wait ? `برای ارسال دوباره ${fa(wait)} ثانیه صبر کن.` : error.message };
        }
        return { ok: false, field: "phone", msg: error.message };
      }
    },
    [otp],
  );

  const verifyOtp = useCallback(
    async (code, name) => {
      if (!otp) return { ok: false, field: "code", msg: "اول کد را درخواست کن." };
      if (!/^\d{6}$/.test(code)) return { ok: false, field: "code", msg: `کد ${fa(6)} رقم است.` };
      if (Date.now() > otp.expiresAt) return { ok: false, field: "code", msg: "اعتبار این کد (۵ دقیقه) تمام شده. «ارسال دوباره‌ی کد» را بزن." };
      const displayName = otp.name || name?.trim() || "";
      if (otp.requiresName && displayName.length < 2)
        return { ok: false, field: "name", msg: "این شماره حساب ندارد. اسمت را بنویس تا حساب ساخته شود." };
      try {
        await post("/api/auth/otp/verify", { phone: otp.phone, code, display_name: displayName || null });
      } catch (error) {
        if (error.status === 422) return { ok: false, field: "name", msg: error.message };
        return { ok: false, field: "code", msg: error.message };
      }
      setOtp(null);
      clearCache();
      const { profile } = await loadLearner();
      go({ name: profileComplete(profile) ? "home" : "onboarding" });
      return { ok: true };
    },
    [otp, loadLearner, go],
  );

  const logout = useCallback(async () => {
    const admin = session.role === "admin";
    await post(admin ? "/api/admin/logout" : "/api/auth/logout").catch(() => {});
    clearCache();
    setSession({ role: "guest" });
    go({ name: admin ? "admin-login" : "landing" });
  }, [session.role, go]);

  const adminLogin = useCallback(
    async (username, password) => {
      try {
        await post("/api/admin/login", { username: username.trim(), password });
      } catch (error) {
        return error.status === 401 ? "نام کاربری یا رمز درست نیست." : error.message;
      }
      clearCache();
      setSession({ role: "admin", admin: await get("/api/admin/me") });
      go({ name: "admin" });
      return null;
    },
    [go],
  );

  return {
    session,
    me: session.me,
    profile: session.profile,
    setProfile,
    route,
    go,
    toasts,
    toast,
    otp,
    setOtp,
    requestOtp,
    verifyOtp,
    logout,
    adminLogin,
    refreshSession,
  };
}

export function StoreProvider({ children }) {
  const value = useSessionState();
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const value = useContext(StoreContext);
  if (!value) throw new Error("StoreProvider missing");
  return value;
}

// Small helper for page data: runs a loader and exposes {data, error, loading, reload}.
export function useLoad(loader, deps) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const latest = useRef(0);
  const run = useCallback(async () => {
    const id = ++latest.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await loader();
      if (id === latest.current) setState({ loading: false, data, error: null });
    } catch (error) {
      if (id === latest.current) setState((s) => ({ loading: false, data: s.data, error }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    run();
  }, [run]);
  return useMemo(() => ({ ...state, reload: run, setData: (data) => setState((s) => ({ ...s, data })) }), [state, run]);
}
