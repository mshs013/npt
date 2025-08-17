from django.db import models
from django.core.exceptions import ValidationError
from netaddr import EUI, mac_unix_expanded


def validate_mac(value):
    """Validate that value is a proper MAC address"""
    try:
        EUI(value)
    except Exception:
        raise ValidationError(f"{value} is not a valid MAC address")


class MACAddressField(models.CharField):
    description = "MAC Address"

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 17  # 00:11:22:33:44:55 format
        kwargs.setdefault("validators", []).append(validate_mac)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if not value:
            return value
        try:
            return str(EUI(value, dialect=mac_unix_expanded))
        except Exception:
            raise ValidationError(f"{value} is not a valid MAC address")

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)
