import uuid
import logging
import random
import string
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.html import escape
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.core.serializers.json import DjangoJSONEncoder
from django_lifecycle import LifecycleModelMixin, hook, AFTER_CREATE, AFTER_UPDATE


from core.azure_communications import send_email

logger = logging.getLogger(__name__)


class MyUserManager(BaseUserManager):
    def create_user(self, email, password=None):
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(email=self.normalize_email(email))

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None):
        user = self.create_user(email,password=password)
        user.is_admin = True
        user.save(using=self._db)
        return user


class User(LifecycleModelMixin, AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    email_verified = models.BooleanField(default=False)
    last_active = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = MyUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_staff(self):
        return self.is_admin
    
    @hook(AFTER_CREATE, on_commit=True)
    def onCreateAccount(self):
        pass

    def send_email_verification(self):
        """Generate email verification token and send email"""
        try:
            token = UserVerificationToken.generate_unique_token()
            UserVerificationToken.objects.create(
                token = token, user = self, expires_on=timezone.now() + timedelta(hours=24))
            
            email_body = f"""
            <html>
                <h1>Hello {escape(self.name)}.</h1>
                <h6>Click here to verify your email: 
                    <a href="http://localhost:5173/verification/verify_email/{self.id}/{token}/">Verify Email</a>
                    The link is valid for 24 hours.
                </h6>
            </html>
            """
            
            content = {
                "subject": "Email Verification",
                "html": email_body,
            }
            
            recipients = [{"address": self.email, "displayName": self.name}]
            send_email(content, recipients)
            
            logger.info(f"Email verification link sent to {self.email}")
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")

class CustomToken(models.Model):
    token = models.CharField(max_length=7, unique=True)
    created_on = models.DateTimeField(auto_now_add=True)
    expires_on = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        abstract = True

    @property
    def is_active(self):
        if not self.active:
            return False
        return self.expires_on is None or timezone.now() < self.expires_on
    
    @classmethod
    def generate_unique_token(cls):
        """Generate a unique 7-character token."""
        while True:
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
            if not cls.objects.filter(token=token).exists():
                return token



class UserVerificationToken(CustomToken):
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class PaymentAgreement(LifecycleModelMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='buyer')
    buyer_email = models.EmailField()
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller')
    name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_breakdown = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    currency = models.CharField(max_length=100, default="KE")
    description = models.TextField(null=True, blank=True)
    document = models.FileField(upload_to='agreement_documents/', null=True, blank=True)
    days_to_deliver = models.PositiveIntegerField(default=0)

    DOWN_PAYMENT = 'down_payment'
    FULL_PAYMENT = 'full_payment'

    TRANSACTION_TYPE_CHOICES = [
        (DOWN_PAYMENT, 'Down Payment'),
        (FULL_PAYMENT, 'Full Payment'),
    ]
    transaction_type = models.CharField(max_length=100, choices=TRANSACTION_TYPE_CHOICES, default=FULL_PAYMENT)

    PENDING = 'pending'
    ACTIVE = 'active'
    COMPLETED = 'completed'
    DISPUTED = 'disputed'
    CANCELED = 'canceled'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (ACTIVE, 'Active'),
        (COMPLETED, 'Completed'),
        (DISPUTED, 'Disputed'),
        (CANCELED, 'Canceled'),
    ]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    extra_data = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Agreement {self.id} between {self.buyer} and {self.seller}"
    
    @hook(AFTER_CREATE, on_commit=True)
    def onCreateAgreement(self):
        # send email to the buyer
        logger.info(f"Email sent to {self.buyer_email}")
        send_email()

class Dispute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agreement = models.ForeignKey(PaymentAgreement, on_delete=models.CASCADE)
    raised_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='raised_by')
    
    OPEN = 'open'
    RESOLVED = 'resolved'

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
    ]
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default=OPEN)
    data = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# class Transaction(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     agreement = models.ForeignKey(EscrowAgreement, on_delete=models.CASCADE)
#     amount = models.DecimalField(max_digits=10, decimal_places=2)
#     transaction_type = models.CharField(max_length=100)
#     status = models.CharField(max_length=100)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)