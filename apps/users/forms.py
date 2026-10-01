from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.hashers import make_password
from apps.users.models import KYCProfile
class RegisterForm(UserCreationForm):
    email=forms.EmailField()
    class Meta:
        model=get_user_model(); fields=("username","email","password1","password2")
class LoginForm(AuthenticationForm):
    username=forms.CharField(widget=forms.TextInput(attrs={"autofocus":True}))
class LoginOTPForm(forms.Form):
    code=forms.CharField(min_length=6,max_length=6,label="Email verification code")
class KYCForm(forms.ModelForm):
    current_password = forms.CharField(widget=forms.PasswordInput, label="Current password")

    def clean_current_password(self):
        password = self.cleaned_data["current_password"]
        if self.instance.pk and not self.instance.user.check_password(password):
            raise forms.ValidationError("Your current password is incorrect.")
        return password

    class Meta:
        model=KYCProfile; fields=("full_name","phone_number","id_number","document")
        widgets={"document":forms.ClearableFileInput(attrs={"accept":".pdf,.jpg,.jpeg,.png"})}
class ProfileForm(forms.ModelForm):
    current_password=forms.CharField(widget=forms.PasswordInput,label="Current password")
    phone_number=forms.CharField(required=False,max_length=30,label="Phone number")
    transaction_pin=forms.CharField(required=False,min_length=4,max_length=4,widget=forms.PasswordInput,label="New 4-digit transaction PIN")
    transaction_pin_confirmation=forms.CharField(required=False,min_length=4,max_length=4,widget=forms.PasswordInput,label="Confirm transaction PIN")
    new_password=forms.CharField(required=False,min_length=8,widget=forms.PasswordInput,label="New password")
    new_password_confirmation=forms.CharField(required=False,widget=forms.PasswordInput,label="Confirm new password")
    class Meta:
        model=get_user_model(); fields=("first_name","last_name","email")
    def __init__(self,*args,profile,**kwargs):
        self.profile=profile; super().__init__(*args,**kwargs); self.fields["phone_number"].initial=profile.phone_number
    def clean(self):
        data=super().clean(); pin=data.get("transaction_pin"); new=data.get("new_password")
        if data.get("current_password") and not self.instance.check_password(data["current_password"]): self.add_error("current_password","Your current password is incorrect.")
        if pin and not pin.isdigit(): self.add_error("transaction_pin","PIN must contain exactly four numbers.")
        if pin != data.get("transaction_pin_confirmation"): self.add_error("transaction_pin_confirmation","PINs do not match.")
        if new and len(new)<8: self.add_error("new_password","Password must contain at least 8 characters.")
        if new != data.get("new_password_confirmation"): self.add_error("new_password_confirmation","Passwords do not match.")
        return data
    def save(self,commit=True):
        user=super().save(commit=commit); phone=self.cleaned_data.get("phone_number","")
        if self.profile.phone_number!=phone:
            self.profile.phone_number=phone; self.profile.save(update_fields=["phone_number","updated_at"])
        pin=self.cleaned_data.get("transaction_pin")
        if pin:
            self.profile.transaction_pin_hash=make_password(pin); self.profile.save(update_fields=["transaction_pin_hash","updated_at"])
        new=self.cleaned_data.get("new_password")
        if new: user.set_password(new); user.save(update_fields=["password"])
        return user
class InitialPINForm(forms.Form):
    transaction_pin=forms.CharField(min_length=4,max_length=4,widget=forms.PasswordInput,label="4-digit transaction PIN")
    transaction_pin_confirmation=forms.CharField(min_length=4,max_length=4,widget=forms.PasswordInput,label="Confirm 4-digit PIN")
    def clean(self):
        data=super().clean(); pin=data.get("transaction_pin","")
        if pin and not pin.isdigit(): self.add_error("transaction_pin","PIN must contain exactly four numbers.")
        if pin!=data.get("transaction_pin_confirmation",""): self.add_error("transaction_pin_confirmation","PINs do not match.")
        return data
