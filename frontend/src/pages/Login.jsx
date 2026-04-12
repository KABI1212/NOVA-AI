// @ts-nocheck
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Lock, Mail, RefreshCw, Shield } from 'lucide-react';
import toast from 'react-hot-toast';
import { authAPI } from '../services/api';
import { formatApiError } from '../utils/apiErrors';
import { useAuthStore, useThemeStore } from '../utils/store';
import NovaLogo from '../components/common/NovaLogo';

function maskEmail(email) {
  const [localPart, domain] = (email || '').split('@');
  if (!localPart || !domain) {
    return email;
  }

  const visibleStart = localPart.slice(0, 2);
  const masked = `${visibleStart}${'*'.repeat(Math.max(localPart.length - 2, 2))}`;
  return `${masked}@${domain}`;
}

function getMaskedEmailDisplay(challenge, fallbackEmail) {
  return challenge?.masked_email || maskEmail(challenge?.email || fallbackEmail);
}

function formatExpiryLabel(otpExpiresAt) {
  if (!otpExpiresAt) {
    return 'Code expires in 5 minutes.';
  }

  const parsed = new Date(otpExpiresAt);
  if (Number.isNaN(parsed.getTime())) {
    return 'Code expires in 5 minutes.';
  }

  return `Code expires around ${parsed.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  })}.`;
}

function getResendCooldownSeconds(resendAvailableAt) {
  if (!resendAvailableAt) {
    return 0;
  }

  const parsed = new Date(resendAvailableAt);
  if (Number.isNaN(parsed.getTime())) {
    return 0;
  }

  return Math.max(Math.ceil((parsed.getTime() - Date.now()) / 1000), 0);
}

function Login() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const { isDark } = useThemeStore();
  const [step, setStep] = useState('credentials');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [otp, setOtp] = useState('');
  const [challenge, setChallenge] = useState(null);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotChallenge, setForgotChallenge] = useState(null);
  const [forgotOtp, setForgotOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [submittingCredentials, setSubmittingCredentials] = useState(false);
  const [verifyingOtp, setVerifyingOtp] = useState(false);
  const [resendingOtp, setResendingOtp] = useState(false);
  const [resendCooldownSeconds, setResendCooldownSeconds] = useState(0);
  const [requestingResetCode, setRequestingResetCode] = useState(false);
  const [resendingResetCode, setResendingResetCode] = useState(false);
  const [resettingPassword, setResettingPassword] = useState(false);
  const [authError, setAuthError] = useState('');

  const expiryLabel = formatExpiryLabel(challenge?.otp_expires_at);
  const forgotExpiryLabel = formatExpiryLabel(forgotChallenge?.otp_expires_at);
  const maskedEmail = getMaskedEmailDisplay(challenge, formData.email);
  const resendAttemptsRemaining = Number(challenge?.resend_attempts_remaining ?? 0);
  const otpAttemptsRemaining = Number(challenge?.otp_attempts_remaining ?? 0);
  const debugLoginOtpCode = String(challenge?.dev_otp_code || '').trim();
  const debugResetOtpCode = String(forgotChallenge?.dev_otp_code || '').trim();
  const resendDisabled =
    resendingOtp || resendCooldownSeconds > 0 || (challenge ? resendAttemptsRemaining <= 0 : false);

  useEffect(() => {
    const updateCooldown = () =>
      setResendCooldownSeconds(getResendCooldownSeconds(challenge?.resend_available_at));

    updateCooldown();

    if (!challenge?.resend_available_at) {
      return undefined;
    }

    const intervalId = window.setInterval(updateCooldown, 1000);
    return () => window.clearInterval(intervalId);
  }, [challenge?.resend_available_at]);

  const handleCredentialSubmit = async (e) => {
    e.preventDefault();
    setSubmittingCredentials(true);
    setAuthError('');

    try {
      const payload = {
        email: formData.email.trim(),
        password: formData.password,
      };

      const response = await authAPI.login(payload);

      if (response.data?.requires_otp) {
        setChallenge(response.data);
        setOtp('');
        setStep('otp');
        toast.success(response.data.message || 'OTP sent to your email.');
      } else {
        const { access_token, user } = response.data;
        setAuth(user, access_token);
        toast.success('Welcome back!');
        navigate('/chat');
      }
    } catch (error) {
      const message = formatApiError(error, 'Login failed');
      setAuthError(message);
      toast.error(message);
    } finally {
      setSubmittingCredentials(false);
    }
  };

  const handleOtpSubmit = async (e) => {
    e.preventDefault();
    setVerifyingOtp(true);
    setAuthError('');

    try {
      const response = await authAPI.verifyLoginOtp({
        email: challenge.email,
        otp,
        challenge_token: challenge.challenge_token,
      });
      const { access_token, user } = response.data;
      setAuth(user, access_token);
      toast.success('Welcome back!');
      navigate('/chat');
    } catch (error) {
      const message = formatApiError(error, 'Verification failed');
      setAuthError(message);
      toast.error(message);
    } finally {
      setVerifyingOtp(false);
    }
  };

  const handleResendOtp = async () => {
    if (!challenge) {
      return;
    }

    setResendingOtp(true);
    setAuthError('');

    try {
      const response = await authAPI.resendLoginOtp({
        email: challenge.email,
        challenge_token: challenge.challenge_token,
      });
      setChallenge(response.data);
      setOtp('');
      toast.success(response.data.message || 'A new OTP has been sent to your email.');
    } catch (error) {
      const message = formatApiError(error, 'Could not resend the code');
      setAuthError(message);
      toast.error(message);
    } finally {
      setResendingOtp(false);
    }
  };

  const handleStartForgotPassword = () => {
    setAuthError('');
    setForgotEmail(formData.email.trim());
    setForgotChallenge(null);
    setForgotOtp('');
    setNewPassword('');
    setConfirmNewPassword('');
    setStep('forgot-email');
  };

  const handleForgotPasswordRequestSubmit = async (e) => {
    e.preventDefault();
    const email = forgotEmail.trim();
    if (!email) {
      const message = 'Please enter your registered email.';
      setAuthError(message);
      toast.error(message);
      return;
    }

    setRequestingResetCode(true);
    setAuthError('');
    try {
      const response = await authAPI.forgotPassword({ email });
      if (response.data?.challenge_token && response.data?.email) {
        setForgotChallenge(response.data);
        setForgotOtp('');
        setNewPassword('');
        setConfirmNewPassword('');
        setStep('forgot-reset');
      } else {
        setForgotChallenge(null);
      }
      toast.success(response.data.message || 'If an account exists, a password reset code has been sent.');
    } catch (error) {
      const message = formatApiError(error, 'Could not send password reset code');
      setAuthError(message);
      toast.error(message);
    } finally {
      setRequestingResetCode(false);
    }
  };

  const handleResendResetCode = async () => {
    if (!forgotChallenge?.email) {
      return;
    }

    setResendingResetCode(true);
    setAuthError('');
    try {
      const response = await authAPI.forgotPassword({ email: forgotChallenge.email });
      if (response.data?.challenge_token && response.data?.email) {
        setForgotChallenge(response.data);
        setForgotOtp('');
      } else {
        setForgotChallenge(null);
        setStep('forgot-email');
      }
      toast.success(response.data.message || 'If an account exists, a password reset code has been sent.');
    } catch (error) {
      const message = formatApiError(error, 'Could not resend reset code');
      setAuthError(message);
      toast.error(message);
    } finally {
      setResendingResetCode(false);
    }
  };

  const handleResetPasswordSubmit = async (e) => {
    e.preventDefault();
    if (!forgotChallenge?.email || !forgotChallenge?.challenge_token) {
      const message = 'Please request a new reset code.';
      setAuthError(message);
      toast.error(message);
      return;
    }

    if (newPassword.length < 8) {
      const message = 'New password must be at least 8 characters.';
      setAuthError(message);
      toast.error(message);
      return;
    }

    if (newPassword !== confirmNewPassword) {
      const message = 'Passwords do not match.';
      setAuthError(message);
      toast.error(message);
      return;
    }

    setResettingPassword(true);
    setAuthError('');
    try {
      await authAPI.resetPassword({
        email: forgotChallenge.email,
        otp: forgotOtp,
        challenge_token: forgotChallenge.challenge_token,
        new_password: newPassword,
      });
      setFormData((previous) => ({
        ...previous,
        email: forgotChallenge.email || previous.email,
        password: '',
      }));
      setStep('credentials');
      setForgotChallenge(null);
      setForgotOtp('');
      setNewPassword('');
      setConfirmNewPassword('');
      toast.success('Password updated. Please sign in with your new password.');
    } catch (error) {
      const message = formatApiError(error, 'Could not reset password');
      setAuthError(message);
      toast.error(message);
    } finally {
      setResettingPassword(false);
    }
  };

  const handleBackToCredentials = () => {
    setAuthError('');
    setStep('credentials');
    setOtp('');
    setChallenge(null);
    setForgotOtp('');
    setForgotChallenge(null);
    setNewPassword('');
    setConfirmNewPassword('');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-blue-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <NovaLogo size={40} textColor={isDark ? '#ffffff' : '#111111'} />
          </div>
          <p className="text-gray-600 dark:text-gray-400">
            Your Intelligent Assistant
          </p>
        </div>

        <div className="card p-8">
          {authError ? (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {authError}
            </div>
          ) : null}
          {step === 'credentials' ? (
            <>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
                Welcome Back
              </h2>

              <form onSubmit={handleCredentialSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Email
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="email"
                      required
                      className="input-field pl-10"
                      placeholder="you@example.com"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="password"
                      required
                      className="input-field pl-10"
                      placeholder="********"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={submittingCredentials}
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {submittingCredentials ? 'Signing in...' : 'Sign In'}
                </button>

                <button
                  type="button"
                  onClick={handleStartForgotPassword}
                  className="w-full text-sm text-primary-600 hover:text-primary-700 font-medium"
                >
                  Forgot password?
                </button>
              </form>
            </>
          ) : step === 'otp' ? (
            <>
              <button
                type="button"
                onClick={handleBackToCredentials}
                className="inline-flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 mb-4"
              >
                <ArrowLeft className="w-4 h-4" />
                Use a different email
              </button>

              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
                Enter Verification Code
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 leading-6">
                We sent a 6-digit code to{' '}
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {maskedEmail}
                </span>
                . {expiryLabel}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                {otpAttemptsRemaining} verification attempts remaining. {resendAttemptsRemaining} resend attempts remaining.
              </p>
              {debugLoginOtpCode ? (
                <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  Debug OTP: <span className="font-semibold tracking-[0.3em]">{debugLoginOtpCode}</span>
                </div>
              ) : null}
              <form onSubmit={handleOtpSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Verification Code
                  </label>
                  <div className="relative">
                    <Shield className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      required
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      className="input-field pl-10 tracking-[0.45em]"
                      placeholder="000000"
                      maxLength={6}
                      value={otp}
                      onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={verifyingOtp || otp.length !== 6}
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {verifyingOtp ? 'Verifying...' : 'Verify and Sign In'}
                </button>
              </form>

              <div className="mt-4 flex flex-col gap-3">
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={resendDisabled}
                  className="btn-secondary w-full disabled:opacity-50 inline-flex items-center justify-center gap-2"
                >
                  <RefreshCw className={`w-4 h-4 ${resendingOtp ? 'animate-spin' : ''}`} />
                  {resendingOtp
                    ? 'Sending new code...'
                    : resendCooldownSeconds > 0
                      ? `Resend in ${resendCooldownSeconds}s`
                      : resendAttemptsRemaining <= 0
                        ? 'No Resends Left'
                        : 'Resend Code'}
                </button>
              </div>
            </>
          ) : step === 'forgot-email' ? (
            <>
              <button
                type="button"
                onClick={handleBackToCredentials}
                className="inline-flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 mb-4"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to sign in
              </button>

              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
                Forgot Password
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 leading-6">
                Enter your registered email and we&apos;ll send you a verification code to reset your password.
              </p>

              <form onSubmit={handleForgotPasswordRequestSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Registered Email
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="email"
                      required
                      className="input-field pl-10"
                      placeholder="you@example.com"
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={requestingResetCode}
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {requestingResetCode ? 'Sending code...' : 'Send Reset Code'}
                </button>
              </form>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setStep('forgot-email')}
                className="inline-flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 mb-4"
              >
                <ArrowLeft className="w-4 h-4" />
                Use a different email
              </button>

              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
                Reset Your Password
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 leading-6">
                Enter the 6-digit code sent to{' '}
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {maskEmail(forgotChallenge?.email || forgotEmail)}
                </span>
                , then set a new password. {forgotExpiryLabel}
              </p>
              {debugResetOtpCode ? (
                <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  Debug reset code: <span className="font-semibold tracking-[0.3em]">{debugResetOtpCode}</span>
                </div>
              ) : null}

              <form onSubmit={handleResetPasswordSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Verification Code
                  </label>
                  <div className="relative">
                    <Shield className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      required
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      className="input-field pl-10 tracking-[0.45em]"
                      placeholder="000000"
                      maxLength={6}
                      value={forgotOtp}
                      onChange={(e) => setForgotOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    New Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="password"
                      required
                      className="input-field pl-10"
                      placeholder="At least 8 characters"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Confirm New Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="password"
                      required
                      className="input-field pl-10"
                      placeholder="Re-enter new password"
                      value={confirmNewPassword}
                      onChange={(e) => setConfirmNewPassword(e.target.value)}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={
                    resettingPassword ||
                    forgotOtp.length !== 6 ||
                    !newPassword ||
                    !confirmNewPassword
                  }
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {resettingPassword ? 'Resetting password...' : 'Reset Password'}
                </button>
              </form>

              <div className="mt-4 flex flex-col gap-3">
                <button
                  type="button"
                  onClick={handleResendResetCode}
                  disabled={resendingResetCode}
                  className="btn-secondary w-full disabled:opacity-50 inline-flex items-center justify-center gap-2"
                >
                  <RefreshCw className={`w-4 h-4 ${resendingResetCode ? 'animate-spin' : ''}`} />
                  {resendingResetCode ? 'Sending new code...' : 'Resend Code'}
                </button>
              </div>
            </>
          )}

          <p className="mt-6 text-center text-sm text-gray-600 dark:text-gray-400">
            Don&apos;t have an account?{' '}
            <Link to="/signup" className="text-primary-600 hover:text-primary-700 font-medium">
              Sign up
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}

export default Login;
