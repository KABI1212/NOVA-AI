import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Lock, Mail, RefreshCw, Shield, User } from 'lucide-react';
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

function Signup() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const { isDark } = useThemeStore();
  const [step, setStep] = useState('details');
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    full_name: '',
  });
  const [otp, setOtp] = useState('');
  const [challenge, setChallenge] = useState(null);
  const [submittingDetails, setSubmittingDetails] = useState(false);
  const [verifyingOtp, setVerifyingOtp] = useState(false);
  const [resendingOtp, setResendingOtp] = useState(false);

  const expiryLabel = formatExpiryLabel(challenge?.otp_expires_at);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmittingDetails(true);

    try {
      const payload = {
        email: formData.email.trim(),
        username: formData.username.trim(),
        password: formData.password,
        full_name: formData.full_name.trim(),
      };

      const response = await authAPI.signup(payload);

      setChallenge(response.data);
      setOtp('');
      setStep('otp');

      if (response.data.delivery_mode === 'email') {
        toast.success(response.data.message || 'Verification code sent to your email');
      } else {
        toast((response.data.message || 'Verification code logged by backend').slice(0, 180), {
          icon: 'i',
        });
      }
    } catch (error) {
      toast.error(formatApiError(error, 'Signup failed'));
    } finally {
      setSubmittingDetails(false);
    }
  };

  const handleOtpSubmit = async (e) => {
    e.preventDefault();
    setVerifyingOtp(true);

    try {
      const response = await authAPI.verifyLoginOtp({
        email: challenge.email,
        otp,
        challenge_token: challenge.challenge_token,
      });
      const { access_token, user } = response.data;
      setAuth(user, access_token);
      toast.success('Account verified successfully!');
      navigate('/chat');
    } catch (error) {
      toast.error(formatApiError(error, 'Verification failed'));
    } finally {
      setVerifyingOtp(false);
    }
  };

  const handleResendOtp = async () => {
    if (!challenge) {
      return;
    }

    setResendingOtp(true);

    try {
      const response = await authAPI.resendLoginOtp({
        email: challenge.email,
        challenge_token: challenge.challenge_token,
      });
      setChallenge(response.data);
      setOtp('');

      if (response.data.delivery_mode === 'email') {
        toast.success(response.data.message || 'A new verification code was sent');
      } else {
        toast((response.data.message || 'Verification code logged by backend').slice(0, 180), {
          icon: 'i',
        });
      }
    } catch (error) {
      toast.error(formatApiError(error, 'Could not resend the code'));
    } finally {
      setResendingOtp(false);
    }
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
          {step === 'details' ? (
            <>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
                Create Account
              </h2>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Full Name
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      className="input-field pl-10"
                      placeholder="John Doe"
                      value={formData.full_name}
                      onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Username
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      required
                      className="input-field pl-10"
                      placeholder="johndoe"
                      value={formData.username}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    />
                  </div>
                </div>

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
                  disabled={submittingDetails}
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {submittingDetails ? 'Creating account...' : 'Create Account'}
                </button>
              </form>
            </>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
                Verify Your Email
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 leading-6">
                Your account has been created. Enter the 6-digit code sent to{' '}
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {maskEmail(challenge?.email || formData.email)}
                </span>
                . {expiryLabel}
              </p>

              {challenge?.delivery_mode === 'log' ? (
                <div className="mb-6 rounded-lg border border-amber-300/60 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
                  Email delivery is not configured yet. The OTP was written to the backend logs instead of being sent by email.
                  {challenge?.dev_otp_code ? (
                    <div className="mt-3 flex items-center justify-between gap-3 rounded-md bg-white/70 px-3 py-2 font-mono text-base tracking-[0.3em] text-amber-950 dark:bg-black/20 dark:text-amber-50">
                      <span>{challenge.dev_otp_code}</span>
                      <button
                        type="button"
                        onClick={() => setOtp(challenge.dev_otp_code)}
                        className="rounded-md border border-amber-400/60 px-2 py-1 text-xs font-semibold tracking-normal text-amber-900 transition hover:bg-amber-100 dark:border-amber-300/30 dark:text-amber-100 dark:hover:bg-amber-400/10"
                      >
                        Use Code
                      </button>
                    </div>
                  ) : null}
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
                  {verifyingOtp ? 'Verifying...' : 'Verify and Continue'}
                </button>
              </form>

              <div className="mt-4">
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={resendingOtp}
                  className="btn-secondary w-full disabled:opacity-50 inline-flex items-center justify-center gap-2"
                >
                  <RefreshCw className={`w-4 h-4 ${resendingOtp ? 'animate-spin' : ''}`} />
                  {resendingOtp ? 'Sending new code...' : 'Resend Code'}
                </button>
              </div>
            </>
          )}

          <p className="mt-6 text-center text-sm text-gray-600 dark:text-gray-400">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-600 hover:text-primary-700 font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}

export default Signup;
