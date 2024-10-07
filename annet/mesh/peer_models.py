from typing import Literal, Annotated

from .basemodel import BaseMeshModel, Concat
from ..bgp_models import BFDTimers

FamilyName = Literal["ipv4_unicast", "ipv6_unicast", "ipv4_labeled", "ipv6_labeled"]


class _SharedOptionsDTO(BaseMeshModel):
    """
    Options which can be set on connected pair or group of peers
    """
    add_path: bool
    multipath: bool
    advertise_irb: bool
    send_labeled: bool
    send_community: bool
    bfd: bool
    bfd_timers: BFDTimers


class SessionDTO(_SharedOptionsDTO):
    """
    Options which are set on connected pair
    """
    asnum: str
    vrf: str
    name: str
    families: Annotated[set[FamilyName], Concat()]
    group_name: str

    subif: str  # TODO: ????
    bmp_monitor: bool

    import_policy: str
    export_policy: str


class _OptionsDTO(_SharedOptionsDTO):
    """
    Options which can be set on group of peers or peer itself
    """
    unnumbered: bool
    rr_client: bool
    next_hop_self: bool
    extended_next_hop: bool
    send_lcommunity: bool
    send_extcommunity: bool
    import_limit: bool
    teardown_timeout: bool
    redistribute: bool
    passive: bool
    mtu_discovery: bool
    advertise_inactive: bool
    advertise_bgp_static: bool
    allowas_in: bool
    auth_key: bool
    multihop: bool
    multihop_no_nexthop_change: bool
    af_no_install: bool
    rib: bool
    resolve_vpn: bool
    af_rib_group: str | None
    af_loops: int
    hold_time: int
    listen_network: bool
    remove_private: bool
    as_override: bool
    aigp: bool
    no_prepend: bool
    no_explicit_null: bool
    uniq_iface: bool
    advertise_peer_as: bool
    connect_retry: bool
    advertise_external: bool
    listen_only: bool
    soft_reconfiguration_inbound: bool
    not_active: bool
    mtu: int


class PeerDTO(SessionDTO, _OptionsDTO):
    pod: int
    addr: str
    description: str

    lagg: int
    lagg_links_min: int

    group_name: str


class MeshPeerGroup(_OptionsDTO):
    name: str
    remote_as: int
    internal_name: str
    update_source: str | None
    description: str | None
