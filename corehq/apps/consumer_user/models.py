from datetime import timedelta

from django.contrib.auth.models import User
from django.core.signing import TimestampSigner
from django.db import models
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from oauth2_provider.settings import oauth2_settings

from corehq.apps.consumer_user.const import (
    CONSUMER_INVITATION_ACCEPTED,
    CONSUMER_INVITATION_ERROR,
    CONSUMER_INVITATION_STATUS,
)
from corehq.apps.hqcase.utils import update_case
from corehq.util.models import GetOrNoneManager


class ConsumerUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    objects = GetOrNoneManager()


class ConsumerUserCaseRelationship(models.Model):
    consumer_user = models.ForeignKey(ConsumerUser, on_delete=models.CASCADE)
    case_id = models.CharField(max_length=255, unique=True)
    domain = models.CharField(max_length=255)


class ConsumerUserInvitation(models.Model):
    email = models.EmailField()
    case_id = models.CharField(max_length=255)
    demographic_case_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    accepted = models.BooleanField(default=False)
    invited_by = models.CharField(max_length=255)
    invited_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['demographic_case_id'],
                condition=models.Q(accepted=False, active=True),
                name="multiple_open_invites",
            )
        ]

    def make_inactive(self):
        self.active = False
        self.save(update_fields=['active'])

    def accept_for_consumer_user(self, consumer_user):
        self.accepted = True
        self.save(update_fields=['accepted'])

        ConsumerUserCaseRelationship.objects.create(
            case_id=self.demographic_case_id,
            domain=self.domain,
            consumer_user=consumer_user
        )
        update_case(
            self.domain,
            self.case_id,
            {
                CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_ACCEPTED,
                CONSUMER_INVITATION_ERROR: "",
            }
        )

    def signature(self):
        """Creates an encrypted key that can be used in a URL to accept this invitation
        """
        return TimestampSigner().sign(urlsafe_base64_encode(force_bytes(self.pk)))

    @classmethod
    def from_signed_id(cls, signed_invitation_id):
        invitation_id = urlsafe_base64_decode(
            TimestampSigner().unsign(signed_invitation_id, max_age=timedelta(days=30))
        )
        return cls.objects.get(pk=invitation_id)


class CaseRelationshipOauthToken(models.Model):
    """Join table between Oauth access tokens and a case relationship, to ensure
    the access token was created for this particular case.

    """
    consumer_user_case_relationship = models.ForeignKey(ConsumerUserCaseRelationship, on_delete=models.CASCADE)
    access_token = models.ForeignKey(oauth2_settings.ACCESS_TOKEN_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['consumer_user_case_relationship', 'access_token'],
                name='unique-relationship-access-token'
            )
        ]

    @classmethod
    def create_from_case_id(cls, case_id, access_token):
        try:
            consumer_user_case_relationship = ConsumerUserCaseRelationship.objects.get(case_id=case_id)
        except ConsumerUserCaseRelationship.DoesNotExist:
            return False

        try:
            existing = cls.objects.get(consumer_user_case_relationship=consumer_user_case_relationship)
            existing.access_token = access_token
            existing.save()
            return existing
        except cls.DoesNotExist:
            return cls.objects.create(
                consumer_user_case_relationship=consumer_user_case_relationship, access_token=access_token
            )
