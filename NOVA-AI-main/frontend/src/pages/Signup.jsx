// @ts-nocheck
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Lock, Mail, RefreshCw, Shield, User } from 'lucide-react';
import toast from 'react-hot-toast';
import { authAPI } from '../services/api';
import { useAuthStore, useThemeStore } from '../utils/store';
import NovaLogo from '../components/common/NovaLogo';

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
  const [challenge, setChallenge] = useState(null);
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await authAPI.signup({
        ...formData,
        email: formData.email.trim(),
        username: formData.username.trim(),
        full_name: formData.full_name.trim(),
      });
      if (!response.data?.requires_otp) {
        const { access_token, user } = response.data;
        setAuth(user, access_token);
        toast.success('Account created successfully!');
        navigate('/chat');
        return;
      }
      setChallenge(response.data);
      setOtp('');
      setStep('otp');
      toast.success(response.data?.message || 'Verification code sent to your email.');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  const handleOtpSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

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
      toast.error(error.response?.data?.detail || 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (!challenge) {
      return;
    }

    setLoading(true);
    try {
      const response = await authAPI.resendLoginOtp({
        email: challenge.email,
        challenge_token: challenge.challenge_token,
      });
      setChallenge(response.data);
      setOtp('');
      toast.success(response.data?.message || 'A new code has been sent.');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not resend code');
    } finally {
      setLoading(false);
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
                      minLength={8}
                      className="input-field pl-10"
                      placeholder="********"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    />
                  </div>
                </div>

                <button type="submit" disabled={loading} className="btn-primary w-full disabled:opacity-50">
                  {loading ? 'Creating account...' : 'Create Account'}
                </button>
              </form>
            </>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
                Verify Your Email
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 leading-6">
                Enter the 6-digit code sent by NOVA AI to{' '}
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {challenge?.masked_email || challenge?.email}
                </span>
                .
              </p>

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

                <button type="submit" disabled={loading || otp.length !== 6} className="btn-primary w-full disabled:opacity-50">
                  {loading ? 'Verifying...' : 'Verify and Continue'}
                </button>
              </form>

              <button
                type="button"
                onClick={handleResendOtp}
                disabled={loading}
                className="btn-secondary w-full disabled:opacity-50 inline-flex items-center justify-center gap-2 mt-4"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Resend Code
              </button>
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
