from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import CONFIG


@dataclass
class VeeamInput:
    total_data_tb: float
    annual_growth_percent: float
    daily_change_percent: float

    backup_type: str
    primary_retention_days: int
    gfs_weekly_count: int
    gfs_monthly_count: int
    gfs_yearly_count: int

    backup_window_hours: float
    target_rpo_hours: float

    compression_ratio: float = CONFIG["compression_ratio_default"]
    dedupe_ratio: float = CONFIG["dedupe_ratio_default"]
    throughput_mb_per_core: float = CONFIG["throughput_mb_per_core"]
    read_write_overhead: float = CONFIG["read_write_overhead"]

    years_to_plan_for: int = CONFIG["years_to_plan_for"]

    vm_count: int = 0
    avg_vm_size_gb: float = 0.0

    wan_bandwidth_mbps: float = 0.0
    repo_type: str = "sobr"

    hypervisor: str = "vmware"
    has_san_access: bool = False
    on_host_proxy: bool = True

    # Round 2: backup server sizing
    workload_count: int = 0
    concurrent_jobs: int = 5
    indexing_enabled: bool = False
    v13_appliance: bool = True

    # Round 3: filesystem + immutability + synthetic full period
    refs_xfs: bool = True
    immutability_enabled: bool = False
    block_generation_days: int = 10

    # Round 5: capacity tier
    capacity_tier_enabled: bool = False
    capacity_tier_fraction: float = 0.5
    direct_to_object: bool = False
    capacity_tier_immutable: bool = False

    # v3: optional sub-workload inputs
    compliance_framework: str = "none"
    replication_input: Optional[Any] = field(default=None)
    nas_input: Optional[Any] = field(default=None)
    wan_accel_input: Optional[Any] = field(default=None)
    tape_input: Optional[Any] = field(default=None)
    license_input: Optional[Any] = field(default=None)
    veeam_one_input: Optional[Any] = field(default=None)


# ---------------------------------------------------------------------------
# Round 1: NAS/Unstructured workload
# ---------------------------------------------------------------------------


@dataclass
class NasInput:
    source_tb: float
    share_count: int = 70
    file_count_millions: float = 1.0
    daily_change_pct: float = 5.0
    backup_window_hours: float = 8.0
    retention_days: int = 14
    gfs_weekly: int = 0
    gfs_monthly: int = 0
    gfs_yearly: int = 0
    object_storage: bool = False
    immutability_enabled: bool = False
    storage_native_cft: bool = False
    compress_pct: float = 30.0
    growth_rate_pct: float = 0.0
    forecast_years: int = 0


@dataclass
class NasDesign:
    cache_repo_tb: float
    primary_repo_tb: float
    gfs_repo_tb: float
    total_repo_tb: float
    file_proxy_cores: int
    file_proxy_ram_gb: int
    notes: List[str] = field(default_factory=list)


@dataclass
class RepoSizing:
    primary_repo_tb: float
    gfs_repo_tb: float
    total_repo_tb: float


@dataclass
class ProxySizing:
    proxy_count: int
    cores_per_proxy: int
    total_proxy_cores: int
    total_parallel_tasks: int
    required_throughput_mb_s: float
    # Round 6: per-transport sizing
    ram_gb_per_proxy: int = 8
    total_proxy_ram_gb: int = 0
    transport_mode: str = "auto"


@dataclass
class BackupServerSizing:
    cores: int
    ram_gb: int
    v13_appliance: bool = True
    notes: List[str] = field(default_factory=list)


@dataclass
class HardenedRepoHost:
    count: int
    tb_per_host: float
    notes: str = ""


@dataclass
class GatewayServerSizing:
    count: int
    cores_each: int
    ram_gb_each: int
    notes: str = ""


@dataclass
class RolePlan:
    backup_server: BackupServerSizing
    proxies: ProxySizing
    hardened_repos: Optional[HardenedRepoHost] = None
    gateways: Optional[GatewayServerSizing] = None


@dataclass
class RiskScore:
    total_score: int
    level: str
    details: Dict[str, int] = field(default_factory=dict)


@dataclass
class SobrDesign:
    extent_count: int
    extent_size_tb: float
    capacity_tier_tb: float
    archive_tier_tb: float
    recommendation: str


@dataclass
class JobDefinition:
    name: str
    vm_count: int
    total_tb: float
    mode: str
    schedule: str
    repo_target: str


@dataclass
class JobSet:
    jobs: List[JobDefinition] = field(default_factory=list)


@dataclass
class RepoPerfModel:
    required_mb_s: float
    synthetic_full_mb_s: float
    notes: List[str] = field(default_factory=list)


@dataclass
class NetworkPlan:
    required_mbps: float
    achievable_rpo_hours: float
    meets_target: bool
    notes: List[str] = field(default_factory=list)


@dataclass
class CostEstimate:
    monthly_object_usd: float
    yearly_object_usd: float
    yearly_onprem_usd: float
    notes: List[str] = field(default_factory=list)
    # Round 9: 3-year TCO + multi-cloud comparison
    cloud_comparison: Dict[str, float] = field(default_factory=dict)
    three_year_tco: Dict[str, float | str] = field(default_factory=dict)
    break_even_years: float = 0.0


@dataclass
class Blueprint:
    role_plan: RolePlan
    jobs: JobSet
    sobr: SobrDesign
    repo_perf: RepoPerfModel
    network: NetworkPlan
    cost: CostEstimate
    notes: List[str] = field(default_factory=list)
    orca: Optional["OrcaDesign"] = None


@dataclass
class VeeamDesign:
    input: VeeamInput
    repo: RepoSizing
    roles: RolePlan
    jobs: JobSet
    sobr: SobrDesign
    repo_perf: RepoPerfModel
    network: NetworkPlan
    cost: CostEstimate
    blueprint: Blueprint
    risk: RiskScore
    notes: Dict[str, str]
    orca: Optional["OrcaDesign"] = None
    replication: Optional["ReplicationDesign"] = field(default=None)
    nas: Optional["NasDesign"] = field(default=None)
    wan_accel: Optional["WanAccelDesign"] = field(default=None)
    license_estimate: Optional["LicenseEstimate"] = field(default=None)
    tape: Optional["TapeDesign"] = field(default=None)
    veeam_one: Optional["VeeamOneDesign"] = field(default=None)
    compliance: Optional["ComplianceResult"] = field(default=None)


@dataclass
class SiteDesign:
    name: str
    design: VeeamDesign


@dataclass
class MultiSiteDesign:
    sites: List[SiteDesign]
    total_repo_tb: float
    notes: Dict[str, str]


# ---------------------------------------------------------------------------
# Round 4: ObjectFirst Orca
# ---------------------------------------------------------------------------


@dataclass
class OrcaDesign:
    node_count: int
    usable_tb_per_node: float = 96.0
    total_usable_tb: float = 0.0
    concurrent_stream_capacity: int = 0
    scale_out_recommended: bool = False
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Round 7: Replication + CDP
# ---------------------------------------------------------------------------


@dataclass
class ReplicationInput:
    source_tb: float
    vm_count: int
    wan_mbps: float
    rpo_hours: float = 1.0
    cdp_enabled: bool = False
    rpo_seconds: int = 15
    compression: bool = True
    daily_change_pct: float = 5.0


@dataclass
class ReplicationDesign:
    required_mbps: float
    meets_rpo: bool
    replica_storage_tb: float
    cdp_proxy_cores: int = 0
    cdp_journal_tb: float = 0.0
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Round 8: Agent / Physical
# ---------------------------------------------------------------------------


@dataclass
class AgentInput:
    machine_count: int
    avg_size_gb: float
    daily_change_pct: float = 5.0
    backup_window_hours: float = 8.0
    retention_days: int = 14
    os_type: str = "windows"
    network_bandwidth_mbps: float = 1000.0


@dataclass
class AgentDesign:
    total_repo_tb: float
    coordinator_cores: int
    coordinator_ram_gb: int
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# v3 Round 4: WAN Accelerator
# ---------------------------------------------------------------------------


@dataclass
class WanAccelInput:
    source_tb: float
    wan_mbps: float
    backup_copy_frequency_hours: float = 24.0
    dedupe_ratio: float = 3.0
    compression_ratio: float = 1.6


@dataclass
class WanAccelDesign:
    source_appliance_count: int
    target_appliance_count: int
    cache_size_gb_per_source: int
    effective_mbps: float
    meets_copy_window: bool
    backup_copy_window_hours: float
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# v3 Round 5: Licensing
# ---------------------------------------------------------------------------


@dataclass
class LicenseInput:
    vm_count: int
    physical_count: int = 0
    nas_tb: float = 0.0
    cloud_workloads: int = 0
    license_type: str = "vul"


@dataclass
class LicenseEstimate:
    protected_workloads: int
    estimated_sockets: int
    tier: str
    annual_maintenance_usd: float
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# v3 Round 6: Tape / Archive
# ---------------------------------------------------------------------------


@dataclass
class TapeInput:
    archive_tb: float
    lto_generation: int = 9
    retention_years: int = 7
    daily_change_pct: float = 1.0


@dataclass
class TapeDesign:
    cartridge_count: int
    drive_count_recommended: int
    library_slots_needed: int
    lto_generation: int
    tb_per_cartridge: float
    annual_media_cost_usd: float
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# v3 Round 7: Veeam ONE
# ---------------------------------------------------------------------------


@dataclass
class VeeamOneInput:
    protected_vms: int
    protected_physical: int = 0
    retention_days: int = 30
    enterprise_manager: bool = False
    vspc_tenants: int = 0


@dataclass
class VeeamOneDesign:
    server_cores: int
    server_ram_gb: int
    database_size_gb: int
    em_cores: int = 0
    em_ram_gb: int = 0
    vspc_cores: int = 0
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# v3 Round 8: Compliance
# ---------------------------------------------------------------------------


@dataclass
class ComplianceInput:
    framework: str
    current_retention_days: int
    immutability_enabled: bool = False
    encryption_enabled: bool = True
    offsite_copy_enabled: bool = False
    target_rpo_hours: float = 24.0


@dataclass
class ComplianceResult:
    framework: str
    compliant: bool
    gaps: List[str] = field(default_factory=list)
    recommended_retention_days: int = 0
    risk_level: str = "compliant"
