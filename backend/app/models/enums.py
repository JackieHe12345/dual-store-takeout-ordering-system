from enum import StrEnum


class DomainType(StrEnum):
    CUSTOMER = "CUSTOMER"
    STAFF = "STAFF"


class RoleCode(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    STORE_ADMIN = "STORE_ADMIN"
    ORDER_OPERATOR = "ORDER_OPERATOR"
    KITCHEN_OPERATOR = "KITCHEN_OPERATOR"
    DELIVERY_OPERATOR = "DELIVERY_OPERATOR"


class CoordinateSystem(StrEnum):
    GCJ_02 = "GCJ-02"
    BD_09 = "BD-09"
    WGS_84 = "WGS-84"
