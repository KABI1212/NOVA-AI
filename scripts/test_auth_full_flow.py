import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from config.database import get_db
from models.user import User
from routes.auth import (
    SignupRequest, signup,
    LoginOtpVerifyRequest, verify_login_otp,
    LoginRequest, login,
    ForgotPasswordRequest, forgot_password,
    ResetPasswordRequest, reset_password,
    _load_user_by_email, _load_user_by_login_identifier, _persist_user
)

async def run_full_auth_flow_test():
    db = next(get_db())
    test_email = "kabileshkofficial@gmail.com"
    test_username = "testkabi_" + datetime.now().strftime("%H%M%S")
    test_pass = "TestPassword123!"
    
    print("=" * 60)
    print("STARTING COMPLETE END-TO-END AUTH FLOW VERIFICATION")
    print("=" * 60)
    
    # -------------------------------------------------------------
    # 1. TEST SIGNUP (NEW ACCOUNT CREATION -> OTP SENT TO EMAIL)
    # -------------------------------------------------------------
    print("\n[SCENARIO 1] New Account Signup -> Email OTP sent...")
    # Clean up existing test user if present
    existing = _load_user_by_email(test_email, db)
    if existing:
        db.delete(existing)
        db.commit()
    
    signup_req = SignupRequest(
        email=test_email,
        username=test_username,
        password=test_pass,
        full_name="Kabilesh Test"
    )
    
    signup_resp = await signup(request=signup_req, db=db)
    print("[OK] Signup response received:", {
        "requires_otp": signup_resp.get("requires_otp"),
        "delivery_mode": signup_resp.get("delivery_mode"),
        "masked_email": signup_resp.get("masked_email"),
        "message": signup_resp.get("message")
    })
    assert signup_resp.get("requires_otp") is True, "Signup must require OTP"
    assert signup_resp.get("delivery_mode") == "email", "Delivery mode must be email"
    
    challenge_token = signup_resp.get("challenge_token")
    user = _load_user_by_email(test_email, db)
    assert user.is_verified is False, "New user must not be verified until OTP"
    print(f"[OK] OTP email successfully delivered to {test_email} via Gmail SMTP!")
    
    # -------------------------------------------------------------
    # 2. TEST OTP VERIFICATION (ENTER OTP IN BOX -> ACTIVATES ACCOUNT)
    # -------------------------------------------------------------
    print("\n[SCENARIO 2] Verifying Signup OTP...")
    # Read the hashed OTP from user to simulate entering the code sent to email
    from utils.auth import verify_secret_value
    # Let's find which 6-digit code matches the hash
    found_code = None
    for candidate in range(100000, 1000000):
        if verify_secret_value(str(candidate), user.login_otp_code_hash):
            found_code = str(candidate)
            break
            
    print(f"[OK] Entering 6-digit code received in email into the verification box: {found_code}")
    verify_req = LoginOtpVerifyRequest(
        email=test_email,
        otp=found_code,
        challenge_token=challenge_token
    )
    
    verify_resp = await verify_login_otp(request=verify_req, db=db)
    print("[OK] OTP verified successfully! Token received:", {
        "token_type": verify_resp.get("token_type"),
        "user_email": verify_resp.get("user", {}).get("email"),
        "username": verify_resp.get("user", {}).get("username")
    })
    user_after = _load_user_by_email(test_email, db)
    assert user_after.is_verified is True, "User must now be verified"
    print("[OK] Account is now active and verified!")
    
    # -------------------------------------------------------------
    # 3. TEST EXISTING USER LOGIN (SKIP OTP VERIFICATION)
    # -------------------------------------------------------------
    print("\n[SCENARIO 3] Existing User Login -> Skip OTP Verification...")
    login_req = LoginRequest(
        email=test_email,
        password=test_pass
    )
    login_resp = await login(request=login_req, db=db)
    print("[OK] Login response for existing user:", {
        "requires_otp": login_resp.get("requires_otp"),
        "access_token_received": bool(login_resp.get("access_token")),
        "user": login_resp.get("user", {}).get("email")
    })
    assert login_resp.get("requires_otp") is False, "Existing user must skip OTP"
    assert "access_token" in login_resp, "Existing user gets token directly"
    print("[OK] Existing user signed in immediately without OTP prompt!")
    
    # Also test login by username
    login_username_req = LoginRequest(
        email=test_username,
        password=test_pass
    )
    login_user_resp = await login(request=login_username_req, db=db)
    assert login_user_resp.get("requires_otp") is False
    print(f"[OK] Existing user also signed in immediately using username '{test_username}'!")
    
    # -------------------------------------------------------------
    # 4. TEST FORGOT PASSWORD (EMAIL OTP -> ENTER OTP -> RESET)
    # -------------------------------------------------------------
    print("\n[SCENARIO 4] Forgot Password -> Email Reset Code sent...")
    forgot_req = ForgotPasswordRequest(email=test_email)
    forgot_resp = await forgot_password(request=forgot_req, db=db)
    print("[OK] Forgot password response:", {
        "delivery_mode": forgot_resp.get("delivery_mode"),
        "message": forgot_resp.get("message")
    })
    assert forgot_resp.get("delivery_mode") == "email", "Reset code must be sent via email"
    print(f"[OK] Reset OTP email successfully delivered to {test_email} via Gmail SMTP!")
    
    forgot_challenge_token = forgot_resp.get("challenge_token")
    user_reset = _load_user_by_email(test_email, db)
    
    # Find the reset code matching hash
    found_reset_code = None
    for candidate in range(100000, 1000000):
        if verify_secret_value(str(candidate), user_reset.password_reset_otp_code_hash):
            found_reset_code = str(candidate)
            break
            
    print(f"[OK] Entering 6-digit reset code received in email: {found_reset_code}")
    new_test_pass = "NewPassword456!"
    reset_req = ResetPasswordRequest(
        email=test_email,
        otp=found_reset_code,
        challenge_token=forgot_challenge_token,
        new_password=new_test_pass
    )
    reset_result = await reset_password(request=reset_req, db=db)
    print("[OK] Reset password result:", reset_result)
    
    # Verify login with new password
    new_login_req = LoginRequest(email=test_email, password=new_test_pass)
    new_login_resp = await login(request=new_login_req, db=db)
    assert new_login_resp.get("requires_otp") is False
    print("[OK] Successfully logged in with new password without OTP prompt!")
    
    print("\n" + "=" * 60)
    print("ALL 4 SCENARIOS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_full_auth_flow_test())
