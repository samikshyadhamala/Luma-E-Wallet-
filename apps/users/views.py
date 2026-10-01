from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from apps.users.forms import InitialPINForm, KYCForm, LoginForm, LoginOTPForm, ProfileForm, RegisterForm
from apps.users.security import issue_login_otp, verify_login_otp

def _after_login_url(user):
    if user.is_staff:
        return "staff_operations:dashboard"
    return "users:initial_pin" if not user.kycprofile.transaction_pin_hash else "wallets:dashboard"

@never_cache
def register(request):
    if request.user.is_authenticated: return redirect("wallets:dashboard")
    form=RegisterForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        user=form.save()
        try: issue_login_otp(user)
        except Exception:
            user.delete(); form.add_error(None,"We could not send the verification email. Check your email configuration.")
        else:
            request.session["pending_login_user_id"]=user.pk; request.session["pending_login_purpose"]="register"
            return render(request,"users/login.html",{"form":LoginOTPForm(),"otp_required":True})
    return render(request,"users/register.html",{"form":form})

@never_cache
def login_view(request):
    if request.user.is_authenticated: return redirect(_after_login_url(request.user))
    pending_user_id=request.session.get("pending_login_user_id")
    if pending_user_id:
        otp_form=LoginOTPForm(request.POST or None)
        if request.method=="POST" and otp_form.is_valid():
            from django.contrib.auth import get_user_model
            user=get_user_model().objects.filter(pk=pending_user_id,is_active=True).first()
            if user:
                valid,error=verify_login_otp(user,otp_form.cleaned_data["code"])
                if valid:
                    purpose=request.session.pop("pending_login_purpose","login"); request.session.pop("pending_login_user_id",None)
                    if purpose=="register":
                        messages.success(request,"Email confirmed. Sign in with your username and password to continue.")
                        return redirect("users:login")
                    login(request,user); return redirect(_after_login_url(user))
                otp_form.add_error(None,error)
            else:
                request.session.pop("pending_login_user_id",None); request.session.pop("pending_login_purpose",None)
                otp_form.add_error(None,"This login request is no longer valid.")
        return render(request,"users/login.html",{"form":otp_form,"otp_required":True})
    form=LoginForm(request,data=request.POST or None)
    if request.method=="POST" and form.is_valid():
        user=form.get_user()
        if not user.email: form.add_error(None,"An email address is required for login verification.")
        else:
            try: issue_login_otp(user)
            except Exception: form.add_error(None,"We could not send the verification email. Check your email configuration.")
            else:
                request.session["pending_login_user_id"]=user.pk; request.session["pending_login_purpose"]="login"
                return render(request,"users/login.html",{"form":LoginOTPForm(),"otp_required":True})
    return render(request,"users/login.html",{"form":form})

@login_required
@never_cache
def initial_pin(request):
    profile=request.user.kycprofile
    if profile.transaction_pin_hash: return redirect("wallets:dashboard")
    form=InitialPINForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        profile.transaction_pin_hash=make_password(form.cleaned_data["transaction_pin"])
        profile.save(update_fields=["transaction_pin_hash","updated_at"])
        messages.success(request,"Your transaction PIN is set.")
        return redirect("wallets:dashboard")
    return render(request,"users/initial_pin.html",{"form":form})

@login_required
@never_cache
def kyc(request):
    profile=request.user.kycprofile; form=KYCForm(request.POST or None,request.FILES or None,instance=profile)
    if request.method=="POST" and form.is_valid():
        profile=form.save(commit=False); profile.status=profile.Status.PENDING; profile.rejection_reason=""; profile.save()
        messages.success(request,"Verification details submitted for review."); return redirect("wallets:dashboard")
    return render(request,"users/kyc.html",{"form":form,"profile":profile})

@login_required
@never_cache
def profile(request):
    if not request.user.kycprofile.transaction_pin_hash: return redirect("users:initial_pin")
    form=ProfileForm(request.POST or None,instance=request.user,profile=request.user.kycprofile)
    if request.method=="POST" and form.is_valid():
        user=form.save(); update_session_auth_hash(request,user)
        messages.success(request,"Account settings updated."); return redirect("users:profile")
    return render(request,"users/profile.html",{"form":form})
